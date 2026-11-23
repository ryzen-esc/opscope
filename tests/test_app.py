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


def test_every_page_renders_with_the_real_cache():
    """Smoke test against the local cache (skipped where the data hasn't been built)."""
    import pytest
    from opscope.ingest.build import cache_dir
    if not (cache_dir() / "games.parquet").exists():
        pytest.skip("no local cache (build it with python -m opscope.ingest.build)")
    from opscope.load import load
    load.cache_clear()
    at = AppTest.from_file(APP, default_timeout=300).run()
    for page in ("views/report.py", "views/operator.py", "views/utility.py", "views/about.py"):
        at.switch_page(page).run()
        assert not at.exception, (page, [e.value for e in at.exception])
