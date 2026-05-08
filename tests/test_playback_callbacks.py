"""Tests for the ``PlaybackMonitor`` callback surface.

These exercise ``onAVStarted``, ``onPlayBackEnded``, ``onPlayBackStopped``,
``onPlayBackPaused`` and the resume-point helpers with enough fakery to
drive every interesting branch added by Task #255 without spinning up Kodi.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_player(monitor, *, playing=True, position=0, duration=0):
    monitor.player._playing = playing
    monitor.player._time = position
    monitor.player._total = duration


# ---------------------------------------------------------------------------
# onAVStarted — primes the duration/position cache
# ---------------------------------------------------------------------------

def test_on_av_started_primes_cache(monitor):
    _set_player(monitor, playing=True, position=42, duration=1381)
    monitor.onAVStarted()
    assert monitor.last_known_duration == 1381
    assert monitor.last_known_position == 42


def test_on_av_started_ignores_when_not_playing(monitor):
    _set_player(monitor, playing=False, position=0, duration=0)
    monitor.onAVStarted()
    assert monitor.last_known_duration == 0
    assert monitor.last_known_position == 0


def test_on_av_started_swallows_player_errors(monitor, monkeypatch):
    """A misbehaving Player should not raise out of the callback."""

    def boom():  # pragma: no cover - trivial
        raise RuntimeError("player unavailable")

    monkeypatch.setattr(monitor.player, "isPlaying", boom)
    # Must not raise.
    monitor.onAVStarted()


# ---------------------------------------------------------------------------
# onPlayBackEnded — always marks watched, clears resume
# ---------------------------------------------------------------------------

def test_on_playback_ended_marks_episode_watched(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = 77
    monitor.onPlayBackEnded()

    assert jsonrpc_calls == [(
        "VideoLibrary.SetEpisodeDetails",
        {"episodeid": 77, "playcount": 1, "resume": {"position": 0, "total": 0}},
    )]
    assert monitor.current_episodeid is None


def test_on_playback_ended_marks_movie_watched(main, monitor, jsonrpc_calls):
    monitor.current_movieid = 999
    monitor.onPlayBackEnded()

    assert jsonrpc_calls == [(
        "VideoLibrary.SetMovieDetails",
        {"movieid": 999, "playcount": 1, "resume": {"position": 0, "total": 0}},
    )]
    assert monitor.current_movieid is None


def test_on_playback_ended_resets_cache_fields(monitor, main):
    monitor.current_episodeid = None
    monitor.current_movieid = None
    monitor.last_known_position = 500
    monitor.last_known_duration = 1000

    monitor.onPlayBackEnded()

    assert monitor.last_known_position == 0
    assert monitor.last_known_duration == 0


def test_on_playback_ended_swallows_jsonrpc_errors(main, monitor, monkeypatch):
    monitor.current_episodeid = 42

    def boom(*_a, **_kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "jsonrpc", boom)
    # Must not raise.
    monitor.onPlayBackEnded()
    # Even after a failure, the current-id must be cleared.
    assert monitor.current_episodeid is None


# ---------------------------------------------------------------------------
# onPlayBackStopped — marks watched when effectively complete,
# otherwise saves a resume point.  Must also fall back to cached values.
# ---------------------------------------------------------------------------

def test_on_stopped_with_live_values_at_end_marks_watched(main, monitor, jsonrpc_calls):
    """User stops Simpsons 4x03 at 21:50 — should be marked watched."""

    monitor.current_episodeid = 4003
    _set_player(monitor, playing=True, position=1310, duration=1381)

    monitor.onPlayBackStopped()

    assert jsonrpc_calls == [(
        "VideoLibrary.SetEpisodeDetails",
        {"episodeid": 4003, "playcount": 1, "resume": {"position": 0, "total": 0}},
    )]
    assert monitor.current_episodeid is None


def test_on_stopped_movie_at_end_marks_watched(main, monitor, jsonrpc_calls):
    monitor.current_movieid = 555
    # 2h movie stopped with 60s left.
    _set_player(monitor, playing=True, position=7140, duration=7200)

    monitor.onPlayBackStopped()

    assert jsonrpc_calls == [(
        "VideoLibrary.SetMovieDetails",
        {"movieid": 555, "playcount": 1, "resume": {"position": 0, "total": 0}},
    )]
    assert monitor.current_movieid is None


def test_on_stopped_midway_saves_resume_point(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = 101
    _set_player(monitor, playing=True, position=600, duration=1381)

    monitor.onPlayBackStopped()

    assert jsonrpc_calls == [(
        "VideoLibrary.SetEpisodeDetails",
        {"episodeid": 101, "resume": {"position": 600, "total": 1381}},
    )]
    # Episode id should still be cleared after the stop.
    assert monitor.current_episodeid is None


def test_on_stopped_uses_cached_values_when_player_returns_zero(
    main, monitor, jsonrpc_calls
):
    """Some Kodi builds return 0 from ``getTime()`` once the player has
    already stopped.  The cached-value fallback must cover that case."""

    monitor.current_episodeid = 4003
    monitor.last_known_position = 1310
    monitor.last_known_duration = 1381
    _set_player(monitor, playing=False, position=0, duration=0)

    monitor.onPlayBackStopped()

    assert jsonrpc_calls == [(
        "VideoLibrary.SetEpisodeDetails",
        {"episodeid": 4003, "playcount": 1, "resume": {"position": 0, "total": 0}},
    )]


def test_on_stopped_with_no_values_at_all_is_noop(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = 4003
    # Neither live nor cached values — nothing to do.
    _set_player(monitor, playing=False, position=0, duration=0)
    monitor.last_known_position = 0
    monitor.last_known_duration = 0

    monitor.onPlayBackStopped()

    assert jsonrpc_calls == []
    assert monitor.current_episodeid is None  # state still reset


def test_on_stopped_handles_player_getTime_exception(main, monitor, monkeypatch,
                                                     jsonrpc_calls):
    """If ``player.getTime()`` blows up, the cached values must still cover."""

    monitor.current_movieid = 77
    monitor.last_known_position = 7140
    monitor.last_known_duration = 7200

    def boom():  # pragma: no cover - trivial
        raise RuntimeError("boom")

    monkeypatch.setattr(monitor.player, "getTime", boom)

    monitor.onPlayBackStopped()

    assert ("VideoLibrary.SetMovieDetails", {
        "movieid": 77,
        "playcount": 1,
        "resume": {"position": 0, "total": 0},
    }) in jsonrpc_calls


def test_on_stopped_resets_cache_fields(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = 101
    _set_player(monitor, playing=True, position=1310, duration=1381)

    monitor.onPlayBackStopped()

    assert monitor.last_known_position == 0
    assert monitor.last_known_duration == 0


def test_on_stopped_with_no_current_id_does_not_call_jsonrpc(
    main, monitor, jsonrpc_calls
):
    """If nothing is currently tracked, the callback must not mark anything
    as watched — even if a previous cached position looks like it's near the
    end."""

    monitor.current_episodeid = None
    monitor.current_movieid = None
    _set_player(monitor, playing=True, position=1310, duration=1381)

    monitor.onPlayBackStopped()

    assert jsonrpc_calls == []


# ---------------------------------------------------------------------------
# Resume-point helpers
# ---------------------------------------------------------------------------

def test_save_resume_point_midway(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = 55
    _set_player(monitor, playing=True, position=400, duration=1381)

    monitor._save_resume_point()

    assert jsonrpc_calls == [(
        "VideoLibrary.SetEpisodeDetails",
        {"episodeid": 55, "resume": {"position": 400, "total": 1381}},
    )]
    # Live values feed the cache so the stop handler can recover them.
    assert monitor.last_known_position == 400
    assert monitor.last_known_duration == 1381


def test_save_resume_point_near_end_does_not_persist(main, monitor, jsonrpc_calls):
    """Regression: the old code would save a resume point at 94% — which
    Kodi would then resume back into on the next play — instead of marking
    the episode watched.  With the new predicate the save is suppressed."""

    monitor.current_episodeid = 4003
    _set_player(monitor, playing=True, position=1310, duration=1381)

    monitor._save_resume_point()

    # The live values are still cached so that onPlayBackStopped can mark it
    # watched, but no resume point is persisted.
    assert jsonrpc_calls == []
    assert monitor.last_known_position == 1310
    assert monitor.last_known_duration == 1381


def test_save_resume_point_when_not_playing_is_noop(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = 55
    _set_player(monitor, playing=False, position=400, duration=1381)
    monitor._save_resume_point()
    assert jsonrpc_calls == []


def test_save_resume_point_with_trivial_position_is_noop(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = 55
    # ``position <= 10`` is treated as "the user just started it"; no save.
    monitor._save_resume_point_with(position=5, duration=1381)
    monitor._save_resume_point_with(position=0, duration=1381)
    monitor._save_resume_point_with(position=400, duration=0)
    assert jsonrpc_calls == []


def test_save_resume_point_with_for_movie(main, monitor, jsonrpc_calls):
    monitor.current_movieid = 7
    monitor._save_resume_point_with(position=1500, duration=6000)
    assert jsonrpc_calls == [(
        "VideoLibrary.SetMovieDetails",
        {"movieid": 7, "resume": {"position": 1500, "total": 6000}},
    )]


def test_save_resume_point_with_when_no_tracked_id(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = None
    monitor.current_movieid = None
    monitor._save_resume_point_with(position=400, duration=1381)
    assert jsonrpc_calls == []


def test_save_resume_point_swallows_jsonrpc_errors(main, monitor, monkeypatch):
    monitor.current_episodeid = 55

    def boom(*_a, **_kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(main, "jsonrpc", boom)
    # Must not raise.
    monitor._save_resume_point_with(position=400, duration=1381)


def test_on_paused_saves_resume_point(main, monitor, jsonrpc_calls):
    monitor.current_episodeid = 55
    _set_player(monitor, playing=True, position=400, duration=1381)
    monitor.onPlayBackPaused()
    assert jsonrpc_calls == [(
        "VideoLibrary.SetEpisodeDetails",
        {"episodeid": 55, "resume": {"position": 400, "total": 1381}},
    )]


# ---------------------------------------------------------------------------
# Integration-ish scenarios
# ---------------------------------------------------------------------------

def test_full_playback_lifecycle_end_to_end(main, monitor, jsonrpc_calls):
    """Start, accumulate a few resume points, then let Kodi fire
    ``onPlayBackEnded``.  The episode must wind up watched and the globals
    must be reset."""

    import xbmc
    monitor.player._info_tag = xbmc.VideoInfoTag(media_type="episode", db_id=4003)
    _set_player(monitor, playing=True, position=0, duration=1381)
    monitor.onAVStarted()

    _set_player(monitor, playing=True, position=300, duration=1381)
    monitor._save_resume_point()
    _set_player(monitor, playing=True, position=600, duration=1381)
    monitor._save_resume_point()

    # Playback ends normally at the natural end of the file.
    monitor.onPlayBackEnded()

    # One watched-mark, plus the two resume saves.
    method_names = [call[0] for call in jsonrpc_calls]
    assert method_names.count("VideoLibrary.SetEpisodeDetails") == 3
    final = jsonrpc_calls[-1]
    assert final == (
        "VideoLibrary.SetEpisodeDetails",
        {"episodeid": 4003, "playcount": 1, "resume": {"position": 0, "total": 0}},
    )
    assert monitor.current_episodeid is None


def test_stopped_near_end_after_cache_primed_by_periodic_save(
    main, monitor, jsonrpc_calls
):
    """Kodi sometimes zeroes out the player state between the last periodic
    save and the ``onPlayBackStopped`` callback.  The cache primed during
    the save must keep the watched-mark path reliable."""

    monitor.current_episodeid = 4003

    # Periodic tick a few seconds before the user hits Stop.
    _set_player(monitor, playing=True, position=1310, duration=1381)
    monitor._save_resume_point()  # suppressed (near end) but caches values

    # Player is torn down by the time onPlayBackStopped fires.
    _set_player(monitor, playing=False, position=0, duration=0)
    monitor.onPlayBackStopped()

    assert jsonrpc_calls == [(
        "VideoLibrary.SetEpisodeDetails",
        {"episodeid": 4003, "playcount": 1, "resume": {"position": 0, "total": 0}},
    )]


@pytest.mark.parametrize(
    "position, duration, expect_watched",
    [
        (1310, 1381, True),    # primary bug: 71s remain — seconds rule
        (1201, 1381, True),    # 180s remain, exactly at seconds rule
        (1200, 1381, False),   # 181s remain / 13% — both rules fail
        (1100, 1381, False),   # 281s remain — save resume
        (700, 1381, False),    # midway — save resume
        (1381, 1381, True),    # fully played
    ],
)
def test_stopped_matrix(main, monitor, jsonrpc_calls, position, duration,
                        expect_watched):
    monitor.current_episodeid = 1
    _set_player(monitor, playing=True, position=position, duration=duration)
    monitor.onPlayBackStopped()

    if expect_watched:
        assert jsonrpc_calls[-1][1]["playcount"] == 1
        assert jsonrpc_calls[-1][1]["resume"] == {"position": 0, "total": 0}
    else:
        assert jsonrpc_calls[-1][1]["resume"] == {
            "position": position, "total": duration,
        }
        assert "playcount" not in jsonrpc_calls[-1][1]
