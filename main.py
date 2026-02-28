import json
import sys
from urllib.parse import parse_qs, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

# Track current playback for auto-marking as watched
_playback_monitor_instance = None
_current_episodeid = None
_current_movieid = None
_playback_monitor_thread = None

CONFIG_DIR = xbmcvfs.translatePath(
    "special://userdata/addon_data/{}/".format(ADDON_ID)
)
CONFIG_PATH = CONFIG_DIR + "collections.json"


def build_url(params):
    return "{}?{}".format(BASE_URL, urlencode(params))


def jsonrpc(method, params=None):
    request = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params:
        request["params"] = params
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
        return response.get("result")
    except Exception as e:
        xbmc.log("{}: JSON-RPC error: {}".format(ADDON_ID, e), xbmc.LOGERROR)
        return None


def get_kodi_setting(setting_id):
    result = jsonrpc("Settings.GetSettingValue", {"setting": setting_id})
    if result and "value" in result:
        return result["value"]
    return None


def _select_first_unwatched(first_unwatched_index):
    if first_unwatched_index is None or first_unwatched_index < 0:
        return
    setting = get_kodi_setting("videolibrary.tvshowsselectfirstunwatcheditem")
    if not setting or setting == 0:
        return
    xbmc.sleep(150)
    container_id = xbmc.getInfoLabel("System.CurrentControlID")
    if container_id:
        xbmc.executebuiltin(
            "SetFocus({},{},absolute)".format(container_id, first_unwatched_index)
        )


def watched_menu_item(build_url, media, playcount, **params):
    """Build a 'Mark as Watched/Unwatched' context menu tuple."""
    label = "Set Unwatched" if playcount > 0 else "Set Watched"
    url_params = {"action": "set_watched", "media": media,
                  "playcount": 0 if playcount > 0 else 1}
    url_params.update(params)
    return (label, "RunPlugin({})".format(build_url(url_params)))


def action_set_watched(params):
    """Set watched state for a library item via JSON-RPC."""
    media = params["media"][0]
    playcount = int(params["playcount"][0])

    if media == "episode":
        details = {"episodeid": int(params["id"][0]), "playcount": playcount}
        # Clear resume point when marking as watched
        if playcount > 0:
            details["resume"] = {"position": 0, "total": 0}
        jsonrpc("VideoLibrary.SetEpisodeDetails", details)
    elif media == "movie":
        details = {"movieid": int(params["id"][0]), "playcount": playcount}
        # Clear resume point when marking as watched
        if playcount > 0:
            details["resume"] = {"position": 0, "total": 0}
        jsonrpc("VideoLibrary.SetMovieDetails", details)
    elif media == "season":
        result = jsonrpc("VideoLibrary.GetEpisodes", {
            "tvshowid": int(params["tvshowid"][0]),
            "season": int(params["season"][0]),
            "properties": ["title"],
        })
        for ep in (result or {}).get("episodes", []):
            details = {"episodeid": ep["episodeid"], "playcount": playcount}
            if playcount > 0:
                details["resume"] = {"position": 0, "total": 0}
            jsonrpc("VideoLibrary.SetEpisodeDetails", details)
    elif media == "tvshow":
        result = jsonrpc("VideoLibrary.GetEpisodes", {
            "tvshowid": int(params["tvshowid"][0]),
            "properties": ["title"],
        })
        for ep in (result or {}).get("episodes", []):
            details = {"episodeid": ep["episodeid"], "playcount": playcount}
            if playcount > 0:
                details["resume"] = {"position": 0, "total": 0}
            jsonrpc("VideoLibrary.SetEpisodeDetails", details)

    xbmc.executebuiltin("Container.Refresh")


class PlaybackMonitor(xbmc.Monitor):
    """Monitor playback to auto-mark episodes/movies as watched and save resume points."""

    def __init__(self):
        """Initialize the playback monitor."""
        super().__init__()
        self.player = xbmc.Player()
        self.last_position_saved = 0
        self.save_interval = 5  # Save resume point every 5 seconds
        self._start_periodic_save()

    def onPlayBackEnded(self):
        """Called when playback ends."""
        global _current_episodeid, _current_movieid

        if _current_episodeid is not None:
            try:
                # Mark as watched and clear resume point
                jsonrpc("VideoLibrary.SetEpisodeDetails", {
                    "episodeid": _current_episodeid,
                    "playcount": 1,
                    "resume": {"position": 0, "total": 0}
                })
                xbmc.log("{}:Auto-marked episode {} as watched".format(ADDON_ID, _current_episodeid), xbmc.LOGINFO)
            except Exception as e:
                xbmc.log("{}:Failed to mark episode as watched: {}".format(ADDON_ID, e), xbmc.LOGERROR)
            _current_episodeid = None

        if _current_movieid is not None:
            try:
                # Mark as watched and clear resume point
                jsonrpc("VideoLibrary.SetMovieDetails", {
                    "movieid": _current_movieid,
                    "playcount": 1,
                    "resume": {"position": 0, "total": 0}
                })
                xbmc.log("{}:Auto-marked movie {} as watched".format(ADDON_ID, _current_movieid), xbmc.LOGINFO)
            except Exception as e:
                xbmc.log("{}:Failed to mark movie as watched: {}".format(ADDON_ID, e), xbmc.LOGERROR)
            _current_movieid = None

        self.last_position_saved = 0

    def onPlayBackStopped(self):
        """Called when playback is stopped."""
        global _current_episodeid, _current_movieid

        # Check if we're near the end (95%+) and mark as watched
        if self.player.isPlaying() or (self.player.getTime() > 0):
            try:
                position = self.player.getTime()
                duration = self.player.getTotalTime()
                if duration > 0:
                    watched_percent = (position / duration) * 100
                    if watched_percent >= 95:
                        # Mark as watched and clear resume point
                        if _current_episodeid is not None:
                            jsonrpc("VideoLibrary.SetEpisodeDetails", {
                                "episodeid": _current_episodeid,
                                "playcount": 1,
                                "resume": {"position": 0, "total": 0}
                            })
                            xbmc.log("{}:Auto-marked episode {} as watched (stopped at {}%)".format(
                                ADDON_ID, _current_episodeid, int(watched_percent)), xbmc.LOGINFO)
                        elif _current_movieid is not None:
                            jsonrpc("VideoLibrary.SetMovieDetails", {
                                "movieid": _current_movieid,
                                "playcount": 1,
                                "resume": {"position": 0, "total": 0}
                            })
                            xbmc.log("{}:Auto-marked movie {} as watched (stopped at {}%)".format(
                                ADDON_ID, _current_movieid, int(watched_percent)), xbmc.LOGINFO)
                    else:
                        # Save resume point for partial playback
                        self._save_resume_point()
            except Exception as e:
                xbmc.log("{}:Error checking playback position on stop: {}".format(ADDON_ID, e), xbmc.LOGWARNING)

        _current_episodeid = None
        _current_movieid = None
        self.last_position_saved = 0

    def onPlayBackPaused(self):
        """Called when playback is paused."""
        self._save_resume_point()

    def _save_resume_point(self):
        """Save the current playback position as resume point."""
        global _current_episodeid, _current_movieid

        if not self.player.isPlaying():
            return

        try:
            position = self.player.getTime()
            duration = self.player.getTotalTime()

            # Only save if there's meaningful progress (more than 1% watched, but not nearly finished)
            if duration > 0 and position > 10:
                watched_percent = (position / duration) * 100
                # Don't save if already 95%+ watched (treat as fully watched)
                if watched_percent < 95:
                    if _current_episodeid is not None:
                        jsonrpc("VideoLibrary.SetEpisodeDetails", {
                            "episodeid": _current_episodeid,
                            "resume": {"position": position, "total": duration}
                        })
                    elif _current_movieid is not None:
                        jsonrpc("VideoLibrary.SetMovieDetails", {
                            "movieid": _current_movieid,
                            "resume": {"position": position, "total": duration}
                        })
        except Exception as e:
            xbmc.log("{}:Failed to save resume point: {}".format(ADDON_ID, e), xbmc.LOGWARNING)

    def _start_periodic_save(self):
        """Start periodic saving of resume point during playback."""
        import threading

        def periodic_save():
            while not self.abortRequested():
                # Wait for the save interval or until abort is requested
                if self.waitForAbort(self.save_interval):
                    break
                # Save resume point if currently playing
                if self.player.isPlaying():
                    self._save_resume_point()

        # Start background thread for periodic saves
        save_thread = threading.Thread(target=periodic_save, daemon=True)
        save_thread.start()


_forced_views_checked = False


def ensure_forced_views():
    global _forced_views_checked
    if _forced_views_checked:
        return
    _forced_views_checked = True
    seasons_view = xbmc.getInfoLabel('Skin.String(Skin.ForcedView.seasons)')
    episodes_view = xbmc.getInfoLabel('Skin.String(Skin.ForcedView.episodes)')
    if not seasons_view:
        name = xbmc.getInfoLabel('$LOCALIZE[538]')  # "Big icons"
        if name:
            xbmc.executebuiltin(
                'Skin.SetString(Skin.ForcedView.seasons,{})'.format(name)
            )
    if not episodes_view:
        name = xbmc.getInfoLabel('$LOCALIZE[31289]')  # "Landscape"
        if name:
            xbmc.executebuiltin(
                'Skin.SetString(Skin.ForcedView.episodes,{})'.format(name)
            )
    tvshows_view = xbmc.getInfoLabel('Skin.String(Skin.ForcedView.tvshows)')
    if not tvshows_view:
        name = xbmc.getInfoLabel('$LOCALIZE[31286]')  # "PosterInfo"
        if name:
            xbmc.executebuiltin(
                'Skin.SetString(Skin.ForcedView.tvshows,{})'.format(name)
            )
    movies_view = xbmc.getInfoLabel('Skin.String(Skin.ForcedView.movies)')
    if not movies_view:
        name = xbmc.getInfoLabel('$LOCALIZE[31286]')  # "PosterInfo"
        if name:
            xbmc.executebuiltin(
                'Skin.SetString(Skin.ForcedView.movies,{})'.format(name)
            )


def root_menu():
    """Root directory: TV Shows and Movies."""
    xbmcplugin.setContent(HANDLE, "files")

    li = xbmcgui.ListItem("TV Shows")
    li.setArt({"icon": "DefaultTVShows.png", "thumb": "DefaultTVShows.png"})
    url = build_url({"action": "root_tv"})
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    li = xbmcgui.ListItem("Movies")
    li.setArt({"icon": "DefaultMovies.png", "thumb": "DefaultMovies.png"})
    url = build_url({"action": "root_movies"})
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    li = xbmcgui.ListItem("TV Shows by Tag")
    li.setArt({"icon": "DefaultTags.png", "thumb": "DefaultTags.png"})
    url = build_url({"action": "tv_tags"})
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    li = xbmcgui.ListItem("Movies by Tag")
    li.setArt({"icon": "DefaultTags.png", "thumb": "DefaultTags.png"})
    url = build_url({"action": "movie_tags"})
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def router():
    ensure_forced_views()
    params = parse_qs(sys.argv[2].lstrip("?"))
    action = params.get("action", [None])[0]
    tag = params.get("tag", [None])[0]

    # -- Backward compatibility: bare ?tag= URLs go straight to TV listings --
    if action is None and tag is not None:
        from tv import list_titles
        if tag == "_all":
            list_titles(tag=None)
        else:
            list_titles(tag=tag)
        return

    # -- Root --
    if action is None:
        root_menu()
        return

    collections_only = params.get("collections_only", ["0"])[0] == "1"

    # -- TV routes --
    if action == "root_tv":
        from tv import list_titles
        list_titles(tag=tag, collections_only=collections_only)
    elif action == "tv_tags":
        from collections_mod import list_tag_folders
        list_tag_folders("tv")
    elif action == "collection":
        from collections_mod import list_collection_items
        list_collection_items(int(params["index"][0]), "tv")
    elif action == "seasons":
        from tv import list_seasons
        list_seasons(int(params["tvshowid"][0]))
    elif action == "episodes":
        from tv import list_episodes
        list_episodes(
            int(params["tvshowid"][0]),
            int(params["season"][0]),
        )
    elif action == "play":
        from tv import play_episode
        play_episode(
            int(params["episodeid"][0]),
            params.get("file", [""])[0],
        )
    elif action == "add_to_collection":
        from collections_mod import action_add_to_collection
        action_add_to_collection(params["title"][0], "tv")
    elif action == "edit_collection":
        from collections_mod import action_edit_collection
        action_edit_collection(int(params["index"][0]), "tv")
    elif action == "set_collection_art":
        from collections_mod import action_set_collection_art
        action_set_collection_art(int(params["index"][0]), "tv")
    elif action == "move_in_collection":
        from collections_mod import action_move_in_collection
        action_move_in_collection(
            int(params["index"][0]),
            int(params["pos"][0]),
            params["direction"][0],
            "tv",
        )
    elif action == "remove_from_collection":
        from collections_mod import action_remove_from_collection
        action_remove_from_collection(
            int(params["index"][0]),
            int(params["pos"][0]),
            "tv",
        )
    elif action == "move_show_item":
        from tv import action_move_show_item
        action_move_show_item(
            int(params["tvshowid"][0]),
            int(params["pos"][0]),
            params["direction"][0],
        )
    elif action == "move_linked_to_collection":
        from tv import action_move_linked_to_collection
        action_move_linked_to_collection(
            int(params["movieid"][0]),
            int(params["tvshowid"][0]),
        )
    elif action == "move_linked_to_show":
        from tv import action_move_linked_to_show
        action_move_linked_to_show(
            int(params["index"][0]),
            int(params["pos"][0]),
        )

    # -- Movie routes --
    elif action == "root_movies":
        from movies import list_movies
        list_movies(tag=tag, collections_only=collections_only)
    elif action == "movie_tags":
        from collections_mod import list_tag_folders
        list_tag_folders("movie")
    elif action == "movie_collection":
        from collections_mod import list_collection_items
        list_collection_items(int(params["index"][0]), "movie")
    elif action == "list_movies":
        from movies import list_movies
        list_movies(tag=params.get("tag", [None])[0])
    elif action == "play_movie":
        from movies import play_movie
        play_movie(
            int(params["movieid"][0]),
            params.get("file", [""])[0],
        )
    elif action == "add_to_movie_collection":
        from collections_mod import action_add_to_collection
        action_add_to_collection(params["title"][0], "movie")
    elif action == "edit_movie_collection":
        from collections_mod import action_edit_collection
        action_edit_collection(int(params["index"][0]), "movie")
    elif action == "set_movie_collection_art":
        from collections_mod import action_set_collection_art
        action_set_collection_art(int(params["index"][0]), "movie")
    elif action == "move_in_movie_collection":
        from collections_mod import action_move_in_collection
        action_move_in_collection(
            int(params["index"][0]),
            int(params["pos"][0]),
            params["direction"][0],
            "movie",
        )
    elif action == "remove_from_movie_collection":
        from collections_mod import action_remove_from_collection
        action_remove_from_collection(
            int(params["index"][0]),
            int(params["pos"][0]),
            "movie",
        )

    # -- Watched state --
    elif action == "set_watched":
        action_set_watched(params)

    # -- Migration --
    elif action == "migrate_sets":
        from movies import action_migrate_movie_sets
        action_migrate_movie_sets()


if __name__ == "__main__":
    router()
