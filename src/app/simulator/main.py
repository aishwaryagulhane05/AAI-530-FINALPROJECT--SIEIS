"""Simulator entry point to run the orchestrator in the foreground."""

import logging
import time
from pathlib import Path
import sys

# Add project root to sys.path so imports work when run directly
_project_root = Path(__file__).parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.app.simulator.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    orch = Orchestrator()
    try:
        orch.start()
        # Keep main thread alive while child threads run
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received — stopping")
        orch.stop()


if __name__ == "__main__":
    main()
