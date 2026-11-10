"""Reproduce the Phase 0-2 audit (738 eligible series) on the frozen 2026-11-03 files.

The raw files are not versioned (licence/size), so this test runs only where the snapshot
exists locally (data/raw/snapshot_20261103) and is reported as SKIPPED elsewhere (CI).
"""

from pathlib import Path

import pytest
from src.etl.reconcile import eligible_counts

SNAPSHOT = Path("data/raw/snapshot_20261103")
# docs/05-conception.md section 2.2 (audit of the 2026-11-03 files).
AUDITED = {"BFA": 275, "MLI": 230, "NER": 187, "SEN": 45, "MAR": 1}


@pytest.mark.skipif(not SNAPSHOT.exists(), reason="audit snapshot not available locally")
def test_etl_reproduces_phase_2_audit_counts() -> None:
    counts = eligible_counts(SNAPSHOT)
    assert counts == AUDITED
    assert sum(counts.values()) == 738
