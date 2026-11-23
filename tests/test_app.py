"""Headless app tests with Streamlit's AppTest (no browser, no real data needed)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_missing_cache_shows_setup_steps_instead_of_crashing(tmp_path, monkeypatch):
    monkeypatch.setenv("OPSCOPE_CACHE", str(tmp_path))  # empty folder: no cache built yet
    from opscope.load import load
    load.cache_clear()
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("Build the cache" in w.value for w in at.warning)
    load.cache_clear()
