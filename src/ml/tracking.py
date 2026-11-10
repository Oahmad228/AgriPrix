"""MLflow tracking: 1 parent run per campaign + 1 child run per (country, group, model).

With 19 groups x 3 model families this gives 57 child runs, which keeps the MLflow UI
readable; per-series details live in PostgreSQL (fact_model_metrics_by_series).
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import get_settings
from src.ml.models import LIGHTGBM, RIDGE, LightGBMGlobal
from src.ml.windows import HISTORY_CAP_MONTHS, MIN_TRAIN_OBSERVATIONS, WINDOWS

if TYPE_CHECKING:
    from src.ml.data import Panel
    from src.ml.train import TrainingResult

EXPERIMENT = "agriprix-forecasting"


@dataclass
class TrackingIds:
    parent_run_id: str | None = None
    group_runs: dict[tuple[str, str, str], str] = field(default_factory=dict)


NO_MLFLOW = TrackingIds()


def _clean(name: str) -> str:
    return name.replace("/", "_")


def log_campaign(run_id: int, git_sha: str, panel: Panel, result: TrainingResult) -> TrackingIds:
    import mlflow

    mlflow.set_tracking_uri(get_settings().mlflow_tracking_uri)
    mlflow.set_experiment(EXPERIMENT)
    ids = TrackingIds()
    metrics = result.metrics
    with mlflow.start_run(run_name=f"campaign-run{run_id}") as parent:
        ids.parent_run_id = parent.info.run_id
        mlflow.set_tags({"training_run_id": run_id, "git_sha": git_sha})
        mlflow.log_params(
            {
                "eligible_series": len(panel.series),
                "groups": panel.series.groupby(["country_iso3", "commodity_group"]).ngroups,
                "windows": ",".join(w.name for w in WINDOWS),
                "history_cap_months": HISTORY_CAP_MONTHS,
                "min_train_observations": MIN_TRAIN_OBSERVATIONS,
            }
        )
        mlflow.log_metrics({k: v for k, v in result.report.items() if v == v})  # drop NaN
        with tempfile.TemporaryDirectory() as tmp:
            result.champions.to_csv(Path(tmp) / "champions.csv", index=False)
            (Path(tmp) / "report.json").write_text(json.dumps(result.report, indent=2))
            mlflow.log_artifacts(tmp)

        for (country, group, model), block in metrics.groupby(
            ["country_iso3", "commodity_group", "model_name"]
        ):
            with mlflow.start_run(run_name=f"{country}-{group}-{model}", nested=True) as child:
                ids.group_runs[(country, group, model)] = child.info.run_id
                mlflow.set_tags({"country": country, "commodity_group": group, "model": model})
                params = {"n_series": int(block["series_id"].nunique())}
                if model == LIGHTGBM:
                    params |= {f"lgbm_{k}": v for k, v in LightGBMGlobal.PARAMS.items()}
                if model == RIDGE:
                    params |= {"ridge_alpha": 1.0}
                mlflow.log_params(params)
                summary = block.groupby(["eval_window", "horizon_months"]).agg(
                    median_mase=("mase", "median"),
                    median_rel_mae=("rel_mae", "median"),
                    mean_mape=("mape", "mean"),
                    mean_picp_80=("picp_80", "mean"),
                )
                values = {}
                for (window, horizon), row in summary.iterrows():
                    for metric, value in row.items():
                        if value == value:  # skip NaN
                            values[_clean(f"{window}_h{horizon}_{metric}")] = float(value)
                mlflow.log_metrics(values)
    return ids
