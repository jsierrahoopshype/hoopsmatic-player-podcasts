import json

from pp import config, history


def test_rollup_moves_old_dailies_into_their_week(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path)
    history.write_daily("2026-06-30", "t", {"UCa": {"x": 10, "y": 3}})       # a Tuesday
    history.write_daily("2026-10-20", "t", {"UCa": {"x": 50}})
    history.write_weekly("2026-06-29", {"UCa": {"x": 9}})
    rolled = history.rollup("2026-10-26")
    assert rolled == ["2026-06-30"]
    assert not history.daily_path("2026-06-30").exists() and history.daily_path("2026-10-20").exists()
    wk = history.load_weekly("2026-06-29")
    assert wk["v"]["UCa"] == {"x": 9, "y": 3}          # the weekly reading stays; only what it lacked is added


def test_daily_file_is_compact_and_same_day_runs_update_it(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path)
    history.write_daily("2026-10-26", "06:15", {"UCa": {"x": 10, "y": 3}}, {"UCa": {"x": [2, 10]}})
    history.write_daily("2026-10-26", "18:15", {"UCa": {"x": 12}})
    doc = json.loads(history.daily_path("2026-10-26").read_text())
    assert doc == {"at": "18:15", "date": "2026-10-26", "l": {"UCa": {"x": [2, 10]}}, "v": {"UCa": {"x": 12, "y": 3}}}
    assert '    "UCa": {"x": 12, "y": 3}\n' in history.daily_path("2026-10-26").read_text()   # one line per source


def test_legacy_snapshot_is_migrated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path)
    (tmp_path / "2026-10-26.json").write_text(json.dumps({"fetched_at": "2026-10-26T06:20:00Z", "sources": {
        "UCa": {"videos": {"x": {"views": 100, "likes": 5, "title": "T", "published": "p"}}}}}))
    assert history.migrate_legacy() == ["2026-10-26"]
    assert not (tmp_path / "2026-10-26.json").exists()
    assert history.load_daily("2026-10-26")["v"] == {"UCa": {"x": 100}}
    assert history.load_daily("2026-10-26")["l"] == {"UCa": {"x": [5, 100]}}


def test_views_gained_math(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path)
    history.write_daily("2026-10-19", "t", {"UCa": {"x": 100, "y": 50}})
    history.write_daily("2026-10-26", "t", {"UCa": {"x": 160, "y": 40, "z": 30, "w": 7}})
    day, then = history.views_on("2026-10-19")
    _, now = history.views_on("2026-10-26")
    assert day == "2026-10-19"
    g = history.gained(now, then, new_ids={"z"})
    # x gained 60; y went down (YouTube trims) -> 0; z is new -> all its views; w unknown -> left out
    assert g == {"x": 60, "y": 0, "z": 30}
    assert history.views_on("2026-10-10") == (None, None)


def test_views_on_falls_back_to_a_weekly_file_nearby(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path)
    history.write_weekly("2026-10-19", {"UCa": {"x": 5}})
    assert history.views_on("2026-10-20") == ("2026-10-19", {"x": 5})
