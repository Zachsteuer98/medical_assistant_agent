import logging

import pytest

from app.main import configure_logging


def test_configure_logging_emits_app_info_events(monkeypatch: pytest.MonkeyPatch):
    # Regression: uvicorn never configured the root logger, so ask_completed and client_chain
    # INFO events were dropped in production.
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.WARNING)

    configure_logging()

    assert logging.getLogger("medical_assistant").isEnabledFor(logging.INFO)
    assert root.handlers


def test_configure_logging_keeps_an_existing_setup(monkeypatch: pytest.MonkeyPatch):
    root = logging.getLogger()
    existing = logging.NullHandler()
    monkeypatch.setattr(root, "handlers", [existing])
    monkeypatch.setattr(root, "level", logging.ERROR)

    configure_logging()

    assert root.handlers == [existing]
    assert root.level == logging.ERROR
