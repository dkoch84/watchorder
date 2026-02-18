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

CONFIG_DIR = xbmcvfs.translatePath(
    "special://userdata/addon_data/{}/".format(ADDON_ID)
)
CONFIG_PATH = CONFIG_DIR + "collections.json"

DEFAULT_CONFIG = {"collections": []}


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


def load_config():
    if not xbmcvfs.exists(CONFIG_DIR):
        xbmcvfs.mkdirs(CONFIG_DIR)
    if not xbmcvfs.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
    try:
        with xbmcvfs.File(CONFIG_PATH, "r") as f:
            config = json.loads(f.read())
        # Migrate old format
        if "watch_orders" in config and "collections" not in config:
            config["collections"] = config.pop("watch_orders")
            save_config(config)
        return config
    except Exception as e:
        xbmc.log(
            "{}: Failed to load config: {}".format(ADDON_ID, e), xbmc.LOGERROR
        )
        return DEFAULT_CONFIG


def save_config(config):
    if not xbmcvfs.exists(CONFIG_DIR):
        xbmcvfs.mkdirs(CONFIG_DIR)
    with xbmcvfs.File(CONFIG_PATH, "w") as f:
        f.write(json.dumps(config, indent=4))


def get_library_shows(tag=None, properties=None):
    if properties is None:
        properties = [
            "title", "art", "year", "genre", "rating", "plot",
            "dateadded", "lastplayed",
        ]
    params = {"properties": properties}
    if tag:
        params["filter"] = {"field": "tag", "operator": "is", "value": tag}
    result = jsonrpc("VideoLibrary.GetTVShows", params)
    if result and "tvshows" in result:
        return result["tvshows"]
    return []


def list_tags():
    """Show available tags as folders for shortcut/widget target selection."""
    shows = get_library_shows(properties=["title", "tag"])
    tags = set()
    for show in shows:
        for t in show.get("tag", []):
            tags.add(t)

    xbmcplugin.setContent(HANDLE, "files")

    li = xbmcgui.ListItem("All Shows")
    url = build_url({"tag": "_all"})
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    for t in sorted(tags):
        li = xbmcgui.ListItem(t)
        url = build_url({"tag": t})
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def list_titles(tag=None):
    """Collection-aware title browser — replaces the old root listing."""
    config = load_config()
    collections = config.get("collections", [])
    library_shows = get_library_shows(tag=tag)
    library_lookup = {s["title"].lower(): s for s in library_shows}

    # Build a lookup: lowered show title → collection index
    title_to_collection = {}
    for idx, col in enumerate(collections):
        for show_title in col.get("shows", []):
            title_to_collection[show_title.lower()] = idx

    # Sort shows alphabetically by title
    sorted_shows = sorted(library_shows, key=lambda s: s["title"].lower())

    xbmcplugin.setContent(HANDLE, "tvshows")
    collections_shown = set()

    for show in sorted_shows:
        col_idx = title_to_collection.get(show["title"].lower())

        if col_idx is not None:
            if col_idx in collections_shown:
                continue
            collections_shown.add(col_idx)

            col = collections[col_idx]
            # Start with first member's art as defaults
            art = {}
            for member_title in col["shows"]:
                member = library_lookup.get(member_title.lower())
                if member and member.get("art"):
                    art = dict(member["art"])
                    break
            # Override with user-configured art (poster, fanart, etc.)
            configured_art = col.get("art", {})
            art.update(configured_art)

            li = xbmcgui.ListItem(col["name"])
            tag_info = li.getVideoInfoTag()
            tag_info.setMediaType("tvshow")
            tag_info.setTitle(col["name"])
            tag_info.setPlot(col.get("description", ""))

            # Max lastplayed across member shows
            max_lp = ""
            for member_title in col["shows"]:
                member = library_lookup.get(member_title.lower())
                if member:
                    lp = member.get("lastplayed", "")
                    if lp > max_lp:
                        max_lp = lp
            if max_lp:
                tag_info.setLastPlayed(max_lp)

            if art:
                li.setArt(art)

            # Context menu for collection entries
            li.addContextMenuItems([
                (
                    "Set Collection Art",
                    "RunPlugin({})".format(build_url({
                        "action": "set_collection_art",
                        "index": col_idx,
                    })),
                ),
                (
                    "Edit TV Collection",
                    "RunPlugin({})".format(build_url({
                        "action": "edit_collection",
                        "index": col_idx,
                    })),
                ),
            ])

            url = build_url({"action": "collection", "index": col_idx})
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
        else:
            li = xbmcgui.ListItem(show["title"])
            tag_info = li.getVideoInfoTag()
            tag_info.setMediaType("tvshow")
            tag_info.setTitle(show["title"])
            tag_info.setPlot(show.get("plot", ""))
            tag_info.setYear(show.get("year", 0))
            tag_info.setRating(show.get("rating", 0.0))
            if show.get("dateadded"):
                tag_info.setDateAdded(show["dateadded"])
            if show.get("lastplayed"):
                tag_info.setLastPlayed(show["lastplayed"])
            genres = show.get("genre", [])
            if genres:
                tag_info.setGenres(genres)
            if show.get("art"):
                li.setArt(show["art"])

            # Context menu for regular shows
            li.addContextMenuItems([
                (
                    "Add to TV Collection",
                    "RunPlugin({})".format(build_url({
                        "action": "add_to_collection",
                        "title": show["title"],
                    })),
                ),
            ])

            url = build_url({
                "action": "seasons",
                "tvshowid": show["tvshowid"],
            })
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_DATEADDED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LASTPLAYED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(HANDLE)


def list_collection_shows(collection_index):
    """Show the ordered shows inside a collection."""
    config = load_config()
    collections = config.get("collections", [])
    if collection_index >= len(collections):
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    col = collections[collection_index]
    library_shows = get_library_shows()
    library_lookup = {s["title"].lower(): s for s in library_shows}

    xbmcplugin.setContent(HANDLE, "tvshows")
    missing = []
    for pos, title in enumerate(col["shows"]):
        show = library_lookup.get(title.lower())
        if not show:
            missing.append(title)
            continue

        li = xbmcgui.ListItem(show["title"])
        tag_info = li.getVideoInfoTag()
        tag_info.setMediaType("tvshow")
        tag_info.setTitle(show["title"])
        tag_info.setPlot(show.get("plot", ""))
        tag_info.setYear(show.get("year", 0))
        tag_info.setRating(show.get("rating", 0.0))
        if show.get("dateadded"):
            tag_info.setDateAdded(show["dateadded"])
        if show.get("lastplayed"):
            tag_info.setLastPlayed(show["lastplayed"])
        genres = show.get("genre", [])
        if genres:
            tag_info.setGenres(genres)
        if show.get("art"):
            li.setArt(show["art"])

        # Context menu for shows inside a collection
        ctx = []
        if pos > 0:
            ctx.append((
                "Move Up",
                "RunPlugin({})".format(build_url({
                    "action": "move_in_collection",
                    "index": collection_index,
                    "pos": pos,
                    "direction": "up",
                })),
            ))
        if pos < len(col["shows"]) - 1:
            ctx.append((
                "Move Down",
                "RunPlugin({})".format(build_url({
                    "action": "move_in_collection",
                    "index": collection_index,
                    "pos": pos,
                    "direction": "down",
                })),
            ))
        ctx.append((
            "Remove from TV Collection",
            "RunPlugin({})".format(build_url({
                "action": "remove_from_collection",
                "index": collection_index,
                "pos": pos,
            })),
        ))
        li.addContextMenuItems(ctx)

        url = build_url({
            "action": "seasons",
            "tvshowid": show["tvshowid"],
        })
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    if missing:
        xbmc.log(
            "{}: Shows not in library: {}".format(ADDON_ID, ", ".join(missing)),
            xbmc.LOGWARNING,
        )
        xbmcgui.Dialog().notification(
            "TV Collections",
            "Not found: {}".format(", ".join(missing)),
            xbmcgui.NOTIFICATION_WARNING,
            5000,
        )

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_DATEADDED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LASTPLAYED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(HANDLE)


def action_add_to_collection(title):
    """Dialog to add a show to an existing or new collection."""
    config = load_config()
    collections = config.get("collections", [])

    choices = [col["name"] for col in collections] + ["[ New Collection ]"]
    dlg = xbmcgui.Dialog()
    idx = dlg.select("Add \"{}\" to Collection".format(title), choices)
    if idx < 0:
        return

    if idx == len(collections):
        name = dlg.input("New Collection Name")
        if not name:
            return
        collections.append({"name": name, "shows": [title]})
    else:
        if title.lower() in [s.lower() for s in collections[idx]["shows"]]:
            dlg.notification(
                "TV Collections",
                "Already in \"{}\"".format(collections[idx]["name"]),
                xbmcgui.NOTIFICATION_INFO,
            )
            return
        collections[idx]["shows"].append(title)

    config["collections"] = collections
    save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def action_edit_collection(collection_index):
    """Dialog to rename or delete a collection."""
    config = load_config()
    collections = config.get("collections", [])
    if collection_index >= len(collections):
        return

    col = collections[collection_index]
    dlg = xbmcgui.Dialog()
    choice = dlg.select(
        "Edit \"{}\"".format(col["name"]),
        ["Rename", "Edit Description", "Delete"],
    )
    if choice < 0:
        return

    if choice == 0:
        new_name = dlg.input("Rename Collection", defaultt=col["name"])
        if new_name and new_name != col["name"]:
            collections[collection_index]["name"] = new_name
            config["collections"] = collections
            save_config(config)
            xbmc.executebuiltin("Container.Refresh")
    elif choice == 1:
        desc = dlg.input(
            "Collection Description",
            defaultt=col.get("description", ""),
        )
        if desc != col.get("description", ""):
            collections[collection_index]["description"] = desc
            config["collections"] = collections
            save_config(config)
            xbmc.executebuiltin("Container.Refresh")
    elif choice == 2:
        if dlg.yesno("Delete Collection",
                      "Delete \"{}\"?\n\nShows will not be removed from your library.".format(col["name"])):
            collections.pop(collection_index)
            config["collections"] = collections
            save_config(config)
            xbmc.executebuiltin("Container.Refresh")


def action_set_collection_art(collection_index):
    """Visual art picker — choose poster and fanart from collection members."""
    config = load_config()
    collections = config.get("collections", [])
    if collection_index >= len(collections):
        return

    col = collections[collection_index]
    dlg = xbmcgui.Dialog()

    # Step 1: pick which art type to set
    art_type_idx = dlg.select(
        "Set Art for \"{}\"".format(col["name"]),
        ["Poster", "Fanart"],
    )
    if art_type_idx < 0:
        return
    art_key = ["poster", "fanart"][art_type_idx]

    # Step 2: gather that art type from all member shows
    library_shows = get_library_shows()
    library_lookup = {s["title"].lower(): s for s in library_shows}

    items = []
    art_urls = []
    current_url = col.get("art", {}).get(art_key, "")
    preselect = -1

    for title in col["shows"]:
        show = library_lookup.get(title.lower())
        if not show:
            continue
        url = show.get("art", {}).get(art_key, "")
        if not url:
            continue

        li = xbmcgui.ListItem(title)
        li.setArt({"icon": url, "thumb": url})
        items.append(li)

        if url == current_url:
            preselect = len(art_urls)
        art_urls.append(url)

    if not items:
        dlg.notification(
            "TV Collections",
            "No {} art found".format(art_key),
            xbmcgui.NOTIFICATION_INFO,
        )
        return

    # Step 3: show visual picker
    kwargs = {"useDetails": True}
    if preselect >= 0:
        kwargs["preselect"] = preselect
    choice = dlg.select(
        "Select {}".format(art_key.title()), items, **kwargs
    )
    if choice < 0:
        return

    # Step 4: save
    if "art" not in col:
        col["art"] = {}
    col["art"][art_key] = art_urls[choice]
    config["collections"] = collections
    save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def action_move_in_collection(collection_index, pos, direction):
    """Move a show up or down within a collection."""
    config = load_config()
    collections = config.get("collections", [])
    if collection_index >= len(collections):
        return

    shows = collections[collection_index]["shows"]
    if direction == "up" and pos > 0:
        shows[pos], shows[pos - 1] = shows[pos - 1], shows[pos]
    elif direction == "down" and pos < len(shows) - 1:
        shows[pos], shows[pos + 1] = shows[pos + 1], shows[pos]

    config["collections"] = collections
    save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def action_remove_from_collection(collection_index, pos):
    """Remove a show from a collection."""
    config = load_config()
    collections = config.get("collections", [])
    if collection_index >= len(collections):
        return

    shows = collections[collection_index]["shows"]
    if pos < len(shows):
        shows.pop(pos)
        # If collection is now empty, remove it entirely
        if not shows:
            collections.pop(collection_index)
        config["collections"] = collections
        save_config(config)
        xbmc.executebuiltin("Container.Refresh")


def list_seasons(tvshowid):
    result = jsonrpc(
        "VideoLibrary.GetSeasons",
        {
            "tvshowid": tvshowid,
            "properties": [
                "season", "showtitle", "art", "watchedepisodes",
                "episode", "playcount",
            ],
        },
    )
    seasons = result.get("seasons", []) if result else []
    if not seasons:
        xbmcgui.Dialog().notification(
            "TV Collections", "No seasons found", xbmcgui.NOTIFICATION_INFO
        )
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    try:
        xbmcplugin.setContent(HANDLE, "seasons")
        for season in seasons:
            label = season.get("label", "Season {}".format(season["season"]))
            li = xbmcgui.ListItem(label)

            tag_info = li.getVideoInfoTag()
            tag_info.setMediaType("season")
            tag_info.setSeason(season["season"])

            if season.get("art"):
                li.setArt(season["art"])

            url = build_url({
                "action": "episodes",
                "tvshowid": tvshowid,
                "season": season["season"],
            })
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
        xbmcplugin.endOfDirectory(HANDLE)
    except RuntimeError:
        pass


def list_episodes(tvshowid, season):
    result = jsonrpc(
        "VideoLibrary.GetEpisodes",
        {
            "tvshowid": tvshowid,
            "season": season,
            "properties": [
                "title", "plot", "season", "episode", "showtitle",
                "firstaired", "runtime", "rating", "director", "writer",
                "art", "file", "playcount", "resume", "lastplayed", "dateadded",
            ],
        },
    )
    episodes = result.get("episodes", []) if result else []
    if not episodes:
        xbmcgui.Dialog().notification(
            "TV Collections", "No episodes found", xbmcgui.NOTIFICATION_INFO
        )
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    try:
        xbmcplugin.setContent(HANDLE, "episodes")
        for ep in episodes:
            label = "{}x{:02d}. {}".format(ep["season"], ep["episode"], ep["title"])
            li = xbmcgui.ListItem(label)

            tag_info = li.getVideoInfoTag()
            tag_info.setMediaType("episode")
            tag_info.setTitle(ep["title"])
            tag_info.setTvShowTitle(ep.get("showtitle", ""))
            tag_info.setSeason(ep["season"])
            tag_info.setEpisode(ep["episode"])
            tag_info.setPlot(ep.get("plot", ""))
            tag_info.setFirstAired(ep.get("firstaired", ""))
            tag_info.setRating(ep.get("rating", 0.0))
            tag_info.setPlaycount(ep.get("playcount", 0))
            tag_info.setLastPlayed(ep.get("lastplayed", ""))
            if ep.get("dateadded"):
                tag_info.setDateAdded(ep["dateadded"])

            runtime = ep.get("runtime", 0)
            if runtime:
                tag_info.setDuration(runtime)

            directors = ep.get("director", [])
            if directors:
                tag_info.setDirectors(directors)

            writers = ep.get("writer", [])
            if writers:
                tag_info.setWriters(writers)

            resume = ep.get("resume", {})
            if resume.get("position", 0) > 0:
                tag_info.setResumePoint(resume["position"], resume.get("total", 0))

            if ep.get("art"):
                li.setArt(ep["art"])

            li.setProperty("IsPlayable", "true")
            url = build_url({
                "action": "play",
                "episodeid": ep["episodeid"],
                "file": ep.get("file", ""),
            })
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

        xbmcplugin.endOfDirectory(HANDLE)
    except RuntimeError:
        pass


def play_episode(episodeid, file):
    if not file:
        result = jsonrpc(
            "VideoLibrary.GetEpisodeDetails",
            {"episodeid": episodeid, "properties": ["file"]},
        )
        if result and "episodedetails" in result:
            file = result["episodedetails"].get("file", "")
    if file:
        li = xbmcgui.ListItem(path=file)
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
    else:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def router():
    ensure_forced_views()
    params = parse_qs(sys.argv[2].lstrip("?"))
    action = params.get("action", [None])[0]

    if action is None:
        tag = params.get("tag", [None])[0]
        if tag is None:
            list_tags()
        elif tag == "_all":
            list_titles(tag=None)
        else:
            list_titles(tag=tag)
    elif action == "collection":
        list_collection_shows(int(params["index"][0]))
    elif action == "seasons":
        list_seasons(int(params["tvshowid"][0]))
    elif action == "episodes":
        list_episodes(
            int(params["tvshowid"][0]),
            int(params["season"][0]),
        )
    elif action == "play":
        play_episode(
            int(params["episodeid"][0]),
            params.get("file", [""])[0],
        )
    elif action == "add_to_collection":
        action_add_to_collection(params["title"][0])
    elif action == "edit_collection":
        action_edit_collection(int(params["index"][0]))
    elif action == "set_collection_art":
        action_set_collection_art(int(params["index"][0]))
    elif action == "move_in_collection":
        action_move_in_collection(
            int(params["index"][0]),
            int(params["pos"][0]),
            params["direction"][0],
        )
    elif action == "remove_from_collection":
        action_remove_from_collection(
            int(params["index"][0]),
            int(params["pos"][0]),
        )


if __name__ == "__main__":
    router()
