"""Model families compared on every (country, commodity group, horizon).

All models predict a price *level*; the learned ones work internally on log-returns
(see features.py) and convert back with exp(ln P[t] + predicted return).
"""

from __future__ import annotations

from typing import Protocol

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.ml.features import NUMERIC_FEATURES

RANDOM_SEED = 42
NAIVE = "Naive"
SEASONAL_NAIVE = "SeasonalNaive"
RIDGE = "Ridge_Seasonal"
LIGHTGBM = "LightGBM_Global"
MODEL_NAMES = (NAIVE, SEASONAL_NAIVE, RIDGE, LIGHTGBM)
BASELINES = (NAIVE, SEASONAL_NAIVE)


class ForecastModel(Protocol):
    name: str

    def fit(self, train: pd.DataFrame) -> ForecastModel: ...

    def predict(self, rows: pd.DataFrame) -> np.ndarray: ...


class Naive:
    """Persistence benchmark: the price in h months = the last observed price.

    Hard to beat on short horizons for prices; reported so that gains are not only
    measured against the (weaker at h=1) seasonal naive.
    """

    name = NAIVE

    def fit(self, train: pd.DataFrame) -> Naive:
        return self

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        return rows["anchor_value"].to_numpy()


class SeasonalNaive:
    """Reference model: next year's price = the price observed 12 months earlier."""

    name = SEASONAL_NAIVE

    def fit(self, train: pd.DataFrame) -> SeasonalNaive:
        return self

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        return rows["snaive_value"].to_numpy()


def _commodity_dummies(rows: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    codes = pd.Categorical(rows["commodity_code"], categories=categories)
    return pd.get_dummies(codes, prefix="commodity", dtype=float).set_index(rows.index)


class RidgeSeasonal:
    """Linear model on the same features; missing lags -> 0 plus an indicator column."""

    name = RIDGE

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self.categories: list[str] = []
        self.pipeline = None

    def _matrix(self, rows: pd.DataFrame) -> pd.DataFrame:
        numeric = rows[NUMERIC_FEATURES]
        missing = numeric.isna().astype(float).add_suffix("_missing")
        return pd.concat(
            [numeric.fillna(0.0), missing, _commodity_dummies(rows, self.categories)], axis=1
        )

    def fit(self, train: pd.DataFrame) -> RidgeSeasonal:
        self.categories = sorted(train["commodity_code"].unique())
        self.pipeline = make_pipeline(StandardScaler(), Ridge(alpha=self.alpha))
        self.pipeline.fit(self._matrix(train), train["target"])
        return self

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        returns = self.pipeline.predict(self._matrix(rows))
        return np.exp(rows["anchor_log"].to_numpy() + returns)


class LightGBMGlobal:
    """Gradient-boosted trees shared by all markets of a group (native NaN handling)."""

    name = LIGHTGBM
    PARAMS = {
        "objective": "regression_l1",  # robust to price spikes, aligned with MAE
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 30,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.8,
        "random_state": RANDOM_SEED,
        "deterministic": True,
        "n_jobs": 2,
        "verbose": -1,
    }

    def __init__(self) -> None:
        self.categories: list[str] = []
        self.model: lgb.LGBMRegressor | None = None

    def _matrix(self, rows: pd.DataFrame) -> pd.DataFrame:
        frame = rows[NUMERIC_FEATURES].copy()
        frame["commodity"] = pd.Categorical(rows["commodity_code"], categories=self.categories)
        return frame

    def fit(self, train: pd.DataFrame) -> LightGBMGlobal:
        self.categories = sorted(train["commodity_code"].unique())
        self.model = lgb.LGBMRegressor(**self.PARAMS)
        self.model.fit(self._matrix(train), train["target"])
        return self

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        returns = self.model.predict(self._matrix(rows))
        return np.exp(rows["anchor_log"].to_numpy() + returns)


def make_model(name: str) -> ForecastModel:
    models = {
        NAIVE: Naive,
        SEASONAL_NAIVE: SeasonalNaive,
        RIDGE: RidgeSeasonal,
        LIGHTGBM: LightGBMGlobal,
    }
    return models[name]()
