"""Tests for :func:`main.action_set_watched`.

Task #255 didn't touch this function directly, but the plan note calls out
that the manual "Set Watched" path is expected to already clear the resume
point when marking watched.  These tests lock that behaviour in so future
churn cannot regress the user-visible fix.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Individual items
# ---------------------------------------------------------------------------

def test_set_watched_episode_clears_resume(main, jsonrpc_calls):
    main.action_set_watched({
        "media": ["episode"],
        "playcount": ["1"],
        "id": ["42"],
    })

    assert ("VideoLibrary.SetEpisodeDetails", {
        "episodeid": 42,
        "playcount": 1,
        "resume": {"position": 0, "total": 0},
    }) in jsonrpc_calls


def test_set_unwatched_episode_does_not_touch_resume(main, jsonrpc_calls):
    main.action_set_watched({
        "media": ["episode"],
        "playcount": ["0"],
        "id": ["42"],
    })

    # When unwatching we don't want to accidentally wipe the existing resume
    # point (the user may want to pick back up mid-episode).
    assert ("VideoLibrary.SetEpisodeDetails", {
        "episodeid": 42,
        "playcount": 0,
    }) in jsonrpc_calls


def test_set_watched_movie_clears_resume(main, jsonrpc_calls):
    main.action_set_watched({
        "media": ["movie"],
        "playcount": ["1"],
        "id": ["9"],
    })

    assert ("VideoLibrary.SetMovieDetails", {
        "movieid": 9,
        "playcount": 1,
        "resume": {"position": 0, "total": 0},
    }) in jsonrpc_calls


def test_set_unwatched_movie_does_not_touch_resume(main, jsonrpc_calls):
    main.action_set_watched({
        "media": ["movie"],
        "playcount": ["0"],
        "id": ["9"],
    })
    assert ("VideoLibrary.SetMovieDetails", {
        "movieid": 9,
        "playcount": 0,
    }) in jsonrpc_calls


# ---------------------------------------------------------------------------
# Bulk-set flows (season / tvshow)
# ---------------------------------------------------------------------------

@pytest.fixture
def bulk_main(main, monkeypatch):
    """Patch :func:`jsonrpc` so GetEpisodes returns a canned episode list and
    SetEpisodeDetails records its calls."""

    recorded = []

    def fake_jsonrpc(method, params=None):
        if method == "VideoLibrary.GetEpisodes":
            return {
                "episodes": [
                    {"episodeid": 1, "title": "Pilot"},
                    {"episodeid": 2, "title": "Chapter Two"},
                    {"episodeid": 3, "title": "Chapter Three"},
                ],
            }
        recorded.append((method, params))
        return {}

    monkeypatch.setattr(main, "jsonrpc", fake_jsonrpc)
    main._recorded = recorded  # type: ignore[attr-defined]
    return main


def test_set_watched_season_marks_every_episode(bulk_main):
    bulk_main.action_set_watched({
        "media": ["season"],
        "playcount": ["1"],
        "tvshowid": ["10"],
        "season": ["1"],
    })

    ids = [p["episodeid"] for (_m, p) in bulk_main._recorded]
    assert ids == [1, 2, 3]
    for (_m, params) in bulk_main._recorded:
        assert params["playcount"] == 1
        assert params["resume"] == {"position": 0, "total": 0}


def test_set_unwatched_season_leaves_resume_alone(bulk_main):
    bulk_main.action_set_watched({
        "media": ["season"],
        "playcount": ["0"],
        "tvshowid": ["10"],
        "season": ["1"],
    })

    for (_m, params) in bulk_main._recorded:
        assert "resume" not in params
        assert params["playcount"] == 0


def test_set_watched_tvshow_marks_every_episode(bulk_main):
    bulk_main.action_set_watched({
        "media": ["tvshow"],
        "playcount": ["1"],
        "tvshowid": ["10"],
    })

    assert len(bulk_main._recorded) == 3
    for (_m, params) in bulk_main._recorded:
        assert params["playcount"] == 1
        assert params["resume"] == {"position": 0, "total": 0}
