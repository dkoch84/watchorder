"""get_kodi_setting window-property cache.

Display-preference settings are read on most navigations but change rarely, so
they are cached briefly to avoid repeating the JSON-RPC lookup.  These tests
guard the cache's correctness — especially that a falsy-but-valid value (0) is
cached and returned, and that a failed lookup is *not* pinned for the TTL.
"""

from __future__ import annotations


def _clear(setting_id):
    import xbmcgui
    xbmcgui.Window(10000).clearProperty("watchorder.setting." + setting_id)


def test_setting_read_is_cached_within_ttl(main, monkeypatch):
    _clear("videolibrary.flattentvshows")
    calls = []

    def fake(method, params=None):
        calls.append((method, params))
        return {"value": 2}

    monkeypatch.setattr(main, "jsonrpc", fake, raising=False)

    assert main.get_kodi_setting("videolibrary.flattentvshows") == 2
    assert main.get_kodi_setting("videolibrary.flattentvshows") == 2
    # Two reads, one underlying JSON-RPC.
    assert len(calls) == 1


def test_zero_value_is_cached_and_returned(main, monkeypatch):
    """0 is a valid setting value (e.g. flatten=off) — it must round-trip
    through the cache, not be treated as a miss."""
    _clear("videolibrary.flattentvshows")
    calls = []

    def fake(method, params=None):
        calls.append(1)
        return {"value": 0}

    monkeypatch.setattr(main, "jsonrpc", fake, raising=False)

    assert main.get_kodi_setting("videolibrary.flattentvshows") == 0
    assert main.get_kodi_setting("videolibrary.flattentvshows") == 0
    assert len(calls) == 1


def test_failed_lookup_is_not_cached(main, monkeypatch):
    """A JSON-RPC that returns no value must not pin None for the whole TTL."""
    _clear("videolibrary.missing")
    calls = []

    def fake(method, params=None):
        calls.append(1)
        return {}

    monkeypatch.setattr(main, "jsonrpc", fake, raising=False)

    assert main.get_kodi_setting("videolibrary.missing") is None
    assert main.get_kodi_setting("videolibrary.missing") is None
    # Re-fetched each time — not cached.
    assert len(calls) == 2
