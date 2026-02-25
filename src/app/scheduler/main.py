"""
SIEIS Scheduler Entry Point
============================
Starts APScheduler with two daily cron jobs:

  Job A  00:00 UTC  remap_and_restart   — refresh incremental data + restart simulator
  Job B  02:00 UTC  retrain_and_reload  — retrain anomaly model + hot-reload API

Environment Variables (all optional, with defaults):
  SCHEDULER_TIMEZONE      UTC
  JOB_A_HOUR              0       (midnight UTC)
  JOB_A_MINUTE            0
  JOB_B_HOUR              2       (2 AM UTC)
  JOB_B_MINUTE            0
  RUN_JOBS_ON_START       false   set "true" to fire both jobs immediately at startup
                                  (useful for smoke-testing without waiting for midnight)

Usage:
  docker-compose up scheduler          # normal operation
  RUN_JOBS_ON_START=true docker-compose up scheduler   # immediate test run
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on path when run inside Docker (/app)
_project_root = Path(__file__).parents[3]  # src/app/scheduler -> project root
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from src.app.scheduler.jobs import remap_and_restart, retrain_and_reload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Config from environment ───────────────────────────────────────────────────
TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "UTC")
JOB_A_HOUR = int(os.getenv("JOB_A_HOUR", "0"))
JOB_A_MINUTE = int(os.getenv("JOB_A_MINUTE", "0"))
JOB_B_HOUR = int(os.getenv("JOB_B_HOUR", "2"))
JOB_B_MINUTE = int(os.getenv("JOB_B_MINUTE", "0"))
RUN_JOBS_ON_START = os.getenv("RUN_JOBS_ON_START", "false").lower() == "true"


# ── Event listener for job success / failure alerts ──────────────────────────

def _job_listener(event):
    """Log job outcomes clearly — makes docker logs easy to grep."""
    job = event.job_id
    if event.exception:
        logger.error("JOB FAILED  [%s]: %s", job, event.exception)
    else:
        logger.info("JOB SUCCESS [%s]", job)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("SIEIS Scheduler starting")
    logger.info("  Timezone : %s", TIMEZONE)
    logger.info("  Job A    : %02d:%02d  remap_and_restart", JOB_A_HOUR, JOB_A_MINUTE)
    logger.info("  Job B    : %02d:%02d  retrain_and_reload", JOB_B_HOUR, JOB_B_MINUTE)
    logger.info("  Immediate: %s", RUN_JOBS_ON_START)
    logger.info("=" * 60)

    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # ── Job A: Daily data refresh ──────────────────────────────────────────
    scheduler.add_job(
        remap_and_restart,
        trigger=CronTrigger(hour=JOB_A_HOUR, minute=JOB_A_MINUTE, timezone=TIMEZONE),
        id="job_a_data_refresh",
        name="Daily Data Refresh (remap + restart simulator)",
        max_instances=1,
        coalesce=True,          # if missed, run once (not multiple catch-ups)
        misfire_grace_time=300, # 5-min grace window before marking as missed
    )

    # ── Job B: Daily model retrain ─────────────────────────────────────────
    scheduler.add_job(
        retrain_and_reload,
        trigger=CronTrigger(hour=JOB_B_HOUR, minute=JOB_B_MINUTE, timezone=TIMEZONE),
        id="job_b_model_retrain",
        name="Daily Model Retrain (train + reload API)",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600, # 10-min grace (training can be slow)
    )

    # ── Immediate run for smoke-testing ────────────────────────────────────
    if RUN_JOBS_ON_START:
        logger.info("RUN_JOBS_ON_START=true — triggering both jobs now for testing")
        scheduler.add_job(
            remap_and_restart,
            id="job_a_immediate",
            name="Immediate Test: remap_and_restart",
        )
        scheduler.add_job(
            retrain_and_reload,
            id="job_b_immediate",
            name="Immediate Test: retrain_and_reload",
        )

    # ── Start (blocks forever) ─────────────────────────────────────────────
    logger.info("Scheduler running. Next runs:")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped gracefully")


if __name__ == "__main__":
    main()
