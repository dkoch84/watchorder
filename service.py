"""Watchorder background service.

Kodi runs this once at login and keeps it alive for the session, which is what
keeps the ``PlaybackMonitor`` callbacks (``onAVStarted`` / ``onPlayBackStopped``
/ ``onPlayBackEnded``) wired up. The plugin script (``main.py``) is a one-shot
process and cannot host long-lived monitors.
"""

import xbmc

from main import ADDON_ID, PlaybackMonitor

xbmc.log("{}: service starting".format(ADDON_ID), xbmc.LOGINFO)
player = PlaybackMonitor()
abort_monitor = xbmc.Monitor()
xbmc.log("{}: PlaybackMonitor active".format(ADDON_ID), xbmc.LOGINFO)
while not abort_monitor.abortRequested():
    if abort_monitor.waitForAbort(1):
        break
xbmc.log("{}: service exiting".format(ADDON_ID), xbmc.LOGINFO)
