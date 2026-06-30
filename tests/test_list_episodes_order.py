"""Episode listing order (task #503).

watchorder builds the episode list from ``VideoLibrary.GetEpisodes``, which
returns rows in episodeid order.  That normally matches episode order, but a
*rescraped* episode gets a fresh (high) episodeid and would sort to the end of
the season.  ``list_episodes`` must sort by season/episode so an episode always
lands in its numbered position regardless of episodeid.
"""

from __future__ import annotations

from urllib.parse import urlparse, parse_qs


def _episode_id_order_from_calls(add_calls):
    """Pull the episodeid out of each addDirectoryItem URL, in call order."""
    ids = []
    for call in add_calls:
        url = call[0][1]
        q = parse_qs(urlparse(url).query)
        if q.get("action", [""])[0] == "play" and "episodeid" in q:
            ids.append(int(q["episodeid"][0]))
    return ids


def test_episodes_sorted_by_episode_not_episodeid(main, monkeypatch):
    import tv
    import xbmcplugin

    # Episode 5 has a much higher episodeid (as if rescraped) and is returned
    # out of position by the library.
    episodes = [
        {"episodeid": 101, "season": 1, "episode": 1, "title": "E1", "playcount": 1},
        {"episodeid": 102, "season": 1, "episode": 2, "title": "E2", "playcount": 1},
        {"episodeid": 103, "season": 1, "episode": 3, "title": "E3", "playcount": 1},
        {"episodeid": 104, "season": 1, "episode": 4, "title": "E4", "playcount": 1},
        {"episodeid": 106, "season": 1, "episode": 6, "title": "E6", "playcount": 0},
        {"episodeid": 999, "season": 1, "episode": 5, "title": "E5", "playcount": 0},
    ]
    monkeypatch.setattr(
        main, "jsonrpc",
        lambda method, params=None: {"episodes": list(episodes)},
        raising=False,
    )
    monkeypatch.setattr(main, "_select_first_unwatched", lambda *_a, **_k: None,
                        raising=False)

    xbmcplugin.addDirectoryItem.reset_mock()
    tv.list_episodes(899, 1)

    ids = _episode_id_order_from_calls(xbmcplugin.addDirectoryItem.call_args_list)
    # The high-id episode 5 (999) must appear in 5th position, not last.
    assert ids == [101, 102, 103, 104, 999, 106]
