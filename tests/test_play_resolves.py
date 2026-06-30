"""Tests for ``play_episode`` / ``play_movie`` resolved-item metadata.

Task #503 root cause: the resolved ``ListItem`` carried a dbid + media type
but no season/episode/title.  Kodi writes a resolved item's InfoTag back to the
library row (matched by dbid) on playback completion, so the empty fields
clobbered the episode's season/episode/title to (-1/-1/"") — orphaning it out
of its show.  The fix populates the identity metadata so any writeback is a
no-op.  These tests assert that metadata is set on the resolved item.
"""

from __future__ import annotations


def _resolved_tag(main, monkeypatch, module_name, func, idkey, idval, details):
    """Drive a play_* resolver and return the VideoInfoTag mock it populated."""
    import importlib
    mod = importlib.import_module(module_name)

    monkeypatch.setattr(
        main, "jsonrpc", lambda method, params=None: details, raising=False
    )

    import xbmcgui
    import xbmcplugin
    li = xbmcgui.ListItem.return_value
    tag = li.getVideoInfoTag.return_value
    tag.reset_mock()
    xbmcplugin.setResolvedUrl.reset_mock()

    func(mod)(idval, "")
    return tag, xbmcplugin.setResolvedUrl


def test_play_episode_sets_identity_metadata(main, monkeypatch):
    details = {"episodedetails": {
        "file": "nfs://x/ep.mkv", "title": "My First Battalion",
        "season": 1, "episode": 5, "showtitle": "Saga of Tanya the Evil",
    }}
    tag, resolved = _resolved_tag(
        main, monkeypatch, "tv", lambda m: m.play_episode, "episodeid", 29188,
        details,
    )

    tag.setDbId.assert_called_once_with(29188)
    tag.setMediaType.assert_called_once_with("episode")
    tag.setTitle.assert_called_once_with("My First Battalion")
    tag.setSeason.assert_called_once_with(1)
    tag.setEpisode.assert_called_once_with(5)
    tag.setTvShowTitle.assert_called_once_with("Saga of Tanya the Evil")
    # Resolved successfully.
    assert resolved.call_args[0][1] is True


def test_play_episode_handles_zero_season_specials(main, monkeypatch):
    """Season 0 (specials) must still be written — it's a valid value, not a
    reason to skip the setter (the guard is ``is not None``, not truthiness)."""
    details = {"episodedetails": {
        "file": "nfs://x/sp.mkv", "title": "Special",
        "season": 0, "episode": 0, "showtitle": "Show",
    }}
    tag, _ = _resolved_tag(
        main, monkeypatch, "tv", lambda m: m.play_episode, "episodeid", 1, details,
    )
    tag.setSeason.assert_called_once_with(0)
    tag.setEpisode.assert_called_once_with(0)


def test_play_movie_sets_identity_metadata(main, monkeypatch):
    details = {"moviedetails": {
        "file": "nfs://x/movie.mkv", "title": "Some Movie", "year": 1999,
    }}
    tag, resolved = _resolved_tag(
        main, monkeypatch, "movies", lambda m: m.play_movie, "movieid", 555,
        details,
    )

    tag.setDbId.assert_called_once_with(555)
    tag.setMediaType.assert_called_once_with("movie")
    tag.setTitle.assert_called_once_with("Some Movie")
    tag.setYear.assert_called_once_with(1999)
    assert resolved.call_args[0][1] is True
