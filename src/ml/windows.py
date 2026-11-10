"""Rolling-origin evaluation windows (ADR-003 section 2.2).

Each window has a calendar cutoff T shared by every market of a group: models are trained
only on (origin, target) pairs whose *target* month is <= T, so no future price can leak
into training (the "buffer" pairs with origin < T < target are excluded). Evaluation uses
the 12 target months after T, with the model frozen at T.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ml.data import month_index


@dataclass(frozen=True)
class Window:
    name: str
    cutoff: int  # month index of T (last month usable as a training target)
    role: str  # "calibration", "validation", "test"
    calibrated_by: str | None  # window whose residuals calibrate this window's intervals

    @property
    def eval_months(self) -> range:
        return range(self.cutoff + 1, self.cutoff + 13)


CAL_2021 = Window("CAL_W0_2021", month_index(2020, 12), "calibration", None)
VAL_W1 = Window("VAL_W1_2022", month_index(2021, 12), "validation", "CAL_W0_2021")
VAL_W2 = Window("VAL_W2_24_25", month_index(2024, 6), "validation", None)
TEST_W3 = Window("TEST_W3_25_26", month_index(2025, 8), "test", "VAL_W2_24_25")

WINDOWS: tuple[Window, ...] = (CAL_2021, VAL_W1, VAL_W2, TEST_W3)
SELECTION_WINDOWS = (VAL_W1.name, VAL_W2.name)  # champion chosen here, never on W3
HORIZONS = (1, 3, 6)
HISTORY_CAP_MONTHS = 120  # train on at most the 10 most recent years before T
MIN_TRAIN_OBSERVATIONS = 24  # a series is evaluated in a window only with >= 24 months before T
