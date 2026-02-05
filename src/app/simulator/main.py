import logging
import threading
import time
from typing import Optional

from src.app.config import KAFKA_BROKER, KAFKA_TOPIC, SPEED_FACTOR, DATA_PATH, MOTE_LOCS_PATH
from src.app.simulator.data_loader import load_data_loader
from src.app.simulator.producer import Producer
from src.app.simulator.emitter import emit_mote

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, broker: str = KAFKA_BROKER, topic: str = KAFKA_TOPIC, max_motes: Optional[int] = None):
        self.producer = Producer(broker=broker, topic=topic)
        self.mote_data, _ = load_data_loader(DATA_PATH, MOTE_LOCS_PATH)
        self.max_motes = max_motes
        self.threads = []
        self.stop_event = threading.Event()

    def start(self):
        mote_ids = list(self.mote_data.keys())
        if self.max_motes:
            mote_ids = mote_ids[: self.max_motes]

        logger.info("Starting orchestrator for %d motes", len(mote_ids))
        for mote_id in mote_ids:
            t = threading.Thread(target=self._run_mote, args=(mote_id,))
            t.daemon = True
            t.start()
            self.threads.append(t)

    def _run_mote(self, mote_id: int):
        df = self.mote_data[mote_id]
        try:
            emit_mote(mote_id, df, self.producer, SPEED_FACTOR, stop_event=self.stop_event)
        except Exception:
            logger.exception("Orchestrator error for mote %s", mote_id)

    def stop(self):
        logger.info("Stopping orchestrator: signalling stop to emitters")
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=1.0)
        logger.info("Flushing producer and closing")
        self.producer.flush()
        self.producer.close()


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
