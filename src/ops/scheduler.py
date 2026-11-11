"""Long-running scheduler service: triggers the monthly refresh (EF-16).

Runs inside Docker (service `scheduler` in docker-compose.prod.yml), no cron on the host.
Each month on REFRESH_DAY at REFRESH_HOUR (UTC) it runs `python -m src.ops.refresh` in a
child process (memory is released after each run). On failure (e.g. the HDX firewall),
it retries once a day, at most MAX_RETRIES times, then waits for the next month.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

logger = logging.getLogger("agriprix.scheduler")
MAX_RETRIES = 3


def next_run(now: datetime, day: int, hour: int) -> datetime:
    """Next monthly slot strictly after ``now`` (day clamped to 28 to exist every month)."""
    day = min(max(day, 1), 28)
    candidate = now.replace(day=day, hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
        candidate = candidate.replace(year=year, month=month)
    return candidate


def run_once(command: list[str]) -> bool:
    logger.info("Starting refresh: %s", " ".join(command))
    result = subprocess.run(command, check=False)  # noqa: S603 - fixed internal command
    logger.info("Refresh finished with exit code %s", result.returncode)
    return result.returncode == 0


def main() -> int:  # pragma: no cover - infinite service loop, logic tested via next_run
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    day = int(os.getenv("REFRESH_DAY", "20"))
    hour = int(os.getenv("REFRESH_HOUR", "3"))
    command = [sys.executable, "-m", "src.ops.refresh"]
    retries = 0
    target = next_run(datetime.now(UTC), day, hour)
    while True:
        logger.info("Next refresh scheduled at %s UTC", target.isoformat(timespec="minutes"))
        while (wait := (target - datetime.now(UTC)).total_seconds()) > 0:
            time.sleep(min(wait, 3600))
        if run_once(command) or retries >= MAX_RETRIES:
            retries = 0
            target = next_run(datetime.now(UTC), day, hour)
        else:
            retries += 1
            target = datetime.now(UTC) + timedelta(days=1)
            logger.warning("Refresh failed, retry %d/%d in 24 h", retries, MAX_RETRIES)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
