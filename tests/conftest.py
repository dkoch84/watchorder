"""Shared pytest fixtures for Watchorder tests.

The addon imports a handful of Kodi-only modules at the top of ``main.py``
(``xbmc``, ``xbmcaddon``, ``xbmcgui``, ``xbmcplugin``, ``xbmcvfs``). Tests run
outside Kodi, so this file installs lightweight fakes into ``sys.modules``
before ``main`` is imported and then exposes helper fixtures that the
individual test modules reuse.
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from unittest.mock import MagicMock

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _install_kodi_fakes() -> None:
    """Install minimal ``xbmc*`` fakes into :mod:`sys.modules`.

    Only the attributes ``main.py`` touches at import time are populated.
    Tests that need richer behaviour patch individual callables after the
    modules are in place.
    """

    # --- xbmc ---------------------------------------------------------------
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGINFO = 1
    xbmc.LOGERROR = 4
    xbmc.LOGWARNING = 3
    xbmc.log = MagicMock()
    xbmc.sleep = MagicMock()
    xbmc.executebuiltin = MagicMock()
    xbmc.executeJSONRPC = MagicMock(return_value='{"result": {}}')
    xbmc.getInfoLabel = MagicMock(return_value="")

    class _Monitor:
        def __init__(self):  # pragma: no cover - trivial
            pass

        def abortRequested(self):  # pragma: no cover - trivial
            return True

        def waitForAbort(self, _seconds):  # pragma: no cover - trivial
            # Return True so the periodic-save thread exits immediately during
            # tests.  The real implementation returns True when abort was
            # requested while waiting.
            return True

    class _VideoInfoTag:
        def __init__(self, media_type="", db_id=0):
            self._media_type = media_type
            self._db_id = db_id

        def getMediaType(self):
            return self._media_type

        def getDbId(self):
            return self._db_id

    class _Player:
        def __init__(self):  # pragma: no cover - trivial
            self._playing = False
            self._time = 0
            self._total = 0
            self._info_tag = _VideoInfoTag()

        def isPlaying(self):  # pragma: no cover - trivial
            return self._playing

        def getTime(self):  # pragma: no cover - trivial
            return self._time

        def getTotalTime(self):  # pragma: no cover - trivial
            return self._total

        def getVideoInfoTag(self):  # pragma: no cover - trivial
            return self._info_tag

    xbmc.VideoInfoTag = _VideoInfoTag

    xbmc.Monitor = _Monitor
    xbmc.Player = _Player

    # --- xbmcaddon ----------------------------------------------------------
    xbmcaddon = types.ModuleType("xbmcaddon")

    class _Addon:
        def __init__(self, *_args, **_kwargs):
            self._info = {"id": "plugin.video.watchorder"}

        def getAddonInfo(self, key):
            return self._info.get(key, "")

        def getSetting(self, _key):  # pragma: no cover - unused here
            return ""

    xbmcaddon.Addon = _Addon

    # --- xbmcgui / xbmcplugin / xbmcvfs ------------------------------------
    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.ListItem = MagicMock()
    xbmcgui.Dialog = MagicMock()

    # Home-window property store backs the addon's lightweight cache
    # (collections_mod._cache_get/_set, used by config and settings caching).
    _window_props = {}

    class _Window:
        def __init__(self, _window_id=0):
            pass

        def getProperty(self, key):
            return _window_props.get(key, "")

        def setProperty(self, key, value):
            _window_props[key] = value

        def clearProperty(self, key):
            _window_props.pop(key, None)

    xbmcgui.Window = _Window

    xbmcplugin = types.ModuleType("xbmcplugin")
    xbmcplugin.setContent = MagicMock()
    xbmcplugin.setResolvedUrl = MagicMock()
    xbmcplugin.addDirectoryItem = MagicMock()
    xbmcplugin.addSortMethod = MagicMock()
    xbmcplugin.endOfDirectory = MagicMock()
    xbmcplugin.SORT_METHOD_NONE = 0

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = MagicMock(side_effect=lambda p: p)

    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcgui"] = xbmcgui
    sys.modules["xbmcplugin"] = xbmcplugin
    sys.modules["xbmcvfs"] = xbmcvfs


_install_kodi_fakes()

# ``main.py`` reads ``sys.argv[1]`` at import time; provide a stub so import
# succeeds.  Individual tests may override ``sys.argv`` as needed.
sys.argv = ["plugin://plugin.video.watchorder/", "0", ""]

# Import *after* the fakes are registered.
import main as main_module  # noqa: E402  pylint: disable=wrong-import-position


@pytest.fixture
def main():
    """Return a freshly-reloaded :mod:`main` module.

    Each test gets a clean copy so that module-level globals (e.g. the current
    episode/movie id) don't leak between tests.
    """

    importlib.reload(main_module)
    return main_module


@pytest.fixture
def jsonrpc_calls(monkeypatch, main):
    """Capture every ``main.jsonrpc(method, params)`` invocation."""

    calls = []

    def _fake(method, params=None):
        calls.append((method, params))
        return {}

    monkeypatch.setattr(main, "jsonrpc", _fake)
    return calls


@pytest.fixture
def monitor(main, monkeypatch):
    """Build a ``PlaybackMonitor`` with the background thread disabled."""

    # Prevent ``_start_periodic_save`` from spinning up a real thread during
    # construction.  The tests drive the code paths that matter directly.
    monkeypatch.setattr(
        main.PlaybackMonitor,
        "_start_periodic_save",
        lambda self: None,
    )
    return main.PlaybackMonitor()
