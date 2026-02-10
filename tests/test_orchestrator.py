"""Tests for orchestrator threading and shutdown behavior."""

import threading

from src.app.simulator import orchestrator as orch_module


class DummyProducer:
    def __init__(self, *args, **kwargs):
        self.flush_called = False
        self.close_called = False

    def flush(self):
        self.flush_called = True

    def close(self):
        self.close_called = True


def test_orchestrator_start_and_stop(monkeypatch):
    """Start threads for motes and stop cleanly."""
    # Arrange: fake data loader and emitter
    mote_ids = [1, 2]
    mote_data = {mote_id: object() for mote_id in mote_ids}

    def fake_load_data_loader(data_path, mote_locs_path):
        return mote_data, {}

    events = {mote_id: threading.Event() for mote_id in mote_ids}

    def fake_emit_mote(mote_id, df, producer, speed_factor, stop_event=None):
        events[mote_id].set()

    monkeypatch.setattr(orch_module, "load_data_loader", fake_load_data_loader)
    monkeypatch.setattr(orch_module, "emit_mote", fake_emit_mote)
    monkeypatch.setattr(orch_module, "Producer", DummyProducer)

    # Act
    orch = orch_module.Orchestrator(max_motes=None)
    orch.start()
    orch.stop()

    # Assert: each mote thread invoked emit_mote
    assert all(evt.is_set() for evt in events.values())
    assert orch.producer.flush_called is True
    assert orch.producer.close_called is True


def test_orchestrator_max_motes(monkeypatch):
    """Respects max_motes limit when starting threads."""
    mote_ids = [1, 2, 3]
    mote_data = {mote_id: object() for mote_id in mote_ids}

    def fake_load_data_loader(data_path, mote_locs_path):
        return mote_data, {}

    started = []

    def fake_emit_mote(mote_id, df, producer, speed_factor, stop_event=None):
        started.append(mote_id)

    monkeypatch.setattr(orch_module, "load_data_loader", fake_load_data_loader)
    monkeypatch.setattr(orch_module, "emit_mote", fake_emit_mote)
    monkeypatch.setattr(orch_module, "Producer", DummyProducer)

    orch = orch_module.Orchestrator(max_motes=2)
    orch.start()
    orch.stop()

    assert len(started) == 2
    assert set(started).issubset(set(mote_ids))
