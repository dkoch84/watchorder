import json

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs


# Config key / item-array-name mapping
_TYPE_MAP = {
    "tv": {"config_key": "collections", "items_key": "shows"},
    "movie": {"config_key": "movie_collections", "items_key": "movies"},
}

DEFAULT_CONFIG = {"collections": [], "movie_collections": []}


def _get_collections(config, media_type):
    key = _TYPE_MAP[media_type]["config_key"]
    return config.get(key, [])


def _set_collections(config, media_type, collections):
    key = _TYPE_MAP[media_type]["config_key"]
    config[key] = collections


def _items_key(media_type):
    return _TYPE_MAP[media_type]["items_key"]


def _label(media_type):
    return "TV" if media_type == "tv" else "Movie"


# -- Config I/O ---------------------------------------------------------------

def _ensure_keys(config):
    """Apply migrations and ensure all top-level keys exist."""
    if "watch_orders" in config and "collections" not in config:
        config["collections"] = config.pop("watch_orders")
    if "movie_collections" not in config:
        config["movie_collections"] = []
    return config


def load_config():
    from main import ADDON_ID, CONFIG_DIR, CONFIG_PATH
    from db import db_load_config

    # Try MySQL first
    mysql_config = db_load_config()
    if mysql_config is not None:
        return _ensure_keys(mysql_config)

    # Fall back to local JSON
    if not xbmcvfs.exists(CONFIG_DIR):
        xbmcvfs.mkdirs(CONFIG_DIR)
    if not xbmcvfs.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
    try:
        with xbmcvfs.File(CONFIG_PATH, "r") as f:
            config = json.loads(f.read())
        _ensure_keys(config)
        return config
    except Exception as e:
        xbmc.log(
            "{}: Failed to load config: {}".format(ADDON_ID, e), xbmc.LOGERROR
        )
        return dict(DEFAULT_CONFIG)


def save_config(config):
    from main import CONFIG_DIR, CONFIG_PATH
    from db import db_save_config

    # Always write local JSON first (backup / fallback)
    if not xbmcvfs.exists(CONFIG_DIR):
        xbmcvfs.mkdirs(CONFIG_DIR)
    with xbmcvfs.File(CONFIG_PATH, "w") as f:
        f.write(json.dumps(config, indent=4))

    # Best-effort write to MySQL
    db_save_config(config)


# -- Tag folders ---------------------------------------------------------------

def list_tag_folders(media_type):
    """Show tag sub-folders for TV or Movies."""
    from main import HANDLE, build_url

    if media_type == "tv":
        from tv import get_library_shows
        items = get_library_shows(properties=["title", "tag"])
    else:
        from movies import get_library_movies
        items = get_library_movies(properties=["title", "tag"])

    tags = set()
    for item in items:
        for t in item.get("tag", []):
            tags.add(t)

    action = "root_tv" if media_type == "tv" else "root_movies"
    xbmcplugin.setContent(HANDLE, "files")

    for t in sorted(tags):
        li = xbmcgui.ListItem(t)
        url = build_url({"action": action, "tag": t})
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


# -- Collection item listing ---------------------------------------------------

def list_collection_items(collection_index, media_type):
    """Show the ordered items (shows or movies) inside a collection."""
    from main import HANDLE, build_url, jsonrpc, watched_menu_item

    config = load_config()
    collections = _get_collections(config, media_type)
    if collection_index >= len(collections):
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    col = collections[collection_index]
    ikey = _items_key(media_type)

    if media_type == "tv":
        from tv import get_library_shows, _build_movie_li, _MOVIE_PROPS
        library_items = get_library_shows()
        lookup_key = "title"
        content_type = "tvshows"
        media_type_tag = "tvshow"
        item_action = "seasons"
        item_id_key = "tvshowid"
        is_folder = True
    else:
        from movies import get_library_movies
        library_items = get_library_movies()
        lookup_key = "title"
        content_type = "movies"
        media_type_tag = "movie"
        item_action = "play_movie"
        item_id_key = "movieid"
        is_folder = False

    library_lookup = {s[lookup_key].lower(): s for s in library_items}

    xbmcplugin.setContent(HANDLE, content_type)
    missing = []

    for pos, title in enumerate(col[ikey]):
        # Handle linked movies at collection level (TV only)
        if media_type == "tv" and isinstance(title, str) and title.startswith("movie:"):
            try:
                movieid = int(title.split(":")[1])
            except (ValueError, IndexError):
                continue
            result = jsonrpc(
                "VideoLibrary.GetMovieDetails",
                {"movieid": movieid, "properties": _MOVIE_PROPS},
            )
            if not result or "moviedetails" not in result:
                continue
            movie = result["moviedetails"]
            li, url = _build_movie_li(movie, build_url)
            ctx = [
                watched_menu_item(build_url, "movie",
                                  movie.get("playcount", 0),
                                  id=movie["movieid"]),
            ]
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
            if pos < len(col[ikey]) - 1:
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
                "Move to Episodes",
                "RunPlugin({})".format(build_url({
                    "action": "move_linked_to_show",
                    "index": collection_index,
                    "pos": pos,
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
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
            continue

        item = library_lookup.get(title.lower())
        if not item:
            missing.append(title)
            continue

        li = xbmcgui.ListItem(item["title"])
        tag_info = li.getVideoInfoTag()
        tag_info.setMediaType(media_type_tag)
        tag_info.setTitle(item["title"])
        tag_info.setPlot(item.get("plot", ""))
        tag_info.setYear(item.get("year", 0))
        tag_info.setRating(item.get("rating", 0.0))
        if item.get("dateadded"):
            tag_info.setDateAdded(item["dateadded"])
        if item.get("lastplayed"):
            tag_info.setLastPlayed(item["lastplayed"])
        genres = item.get("genre", [])
        if genres:
            tag_info.setGenres(genres)
        if item.get("art"):
            li.setArt(item["art"])

        # Context menu
        if media_type == "tv":
            item_pc = 1 if item.get("watchedepisodes", 0) >= item.get("episode", 1) else 0
            ctx = [watched_menu_item(build_url, "tvshow", item_pc,
                                     tvshowid=item[item_id_key])]
        else:
            ctx = [watched_menu_item(build_url, "movie",
                                     item.get("playcount", 0),
                                     id=item[item_id_key])]
        action_prefix = "" if media_type == "tv" else "movie_"
        if pos > 0:
            ctx.append((
                "Move Up",
                "RunPlugin({})".format(build_url({
                    "action": "move_in_{}collection".format(action_prefix),
                    "index": collection_index,
                    "pos": pos,
                    "direction": "up",
                })),
            ))
        if pos < len(col[ikey]) - 1:
            ctx.append((
                "Move Down",
                "RunPlugin({})".format(build_url({
                    "action": "move_in_{}collection".format(action_prefix),
                    "index": collection_index,
                    "pos": pos,
                    "direction": "down",
                })),
            ))
        ctx.append((
            "Remove from {} Collection".format(_label(media_type)),
            "RunPlugin({})".format(build_url({
                "action": "remove_from_{}collection".format(action_prefix),
                "index": collection_index,
                "pos": pos,
            })),
        ))
        li.addContextMenuItems(ctx)

        if media_type == "tv":
            url = build_url({
                "action": item_action,
                "tvshowid": item[item_id_key],
            })
        else:
            li.setProperty("IsPlayable", "true")
            url = build_url({
                "action": item_action,
                "movieid": item[item_id_key],
                "file": item.get("file", ""),
            })
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)

    if missing:
        from main import ADDON_ID
        xbmc.log(
            "{}: Items not in library: {}".format(ADDON_ID, ", ".join(missing)),
            xbmc.LOGWARNING,
        )
        xbmcgui.Dialog().notification(
            "{} Collections".format(_label(media_type)),
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


# -- Collection actions --------------------------------------------------------

def action_add_to_collection(title, media_type):
    """Dialog to add an item to an existing or new collection."""
    config = load_config()
    collections = _get_collections(config, media_type)
    ikey = _items_key(media_type)

    choices = [col["name"] for col in collections] + ["[ New Collection ]"]
    dlg = xbmcgui.Dialog()
    idx = dlg.select("Add \"{}\" to Collection".format(title), choices)
    if idx < 0:
        return

    if idx == len(collections):
        name = dlg.input("New Collection Name")
        if not name:
            return
        collections.append({"name": name, ikey: [title]})
    else:
        if title.lower() in [s.lower() for s in collections[idx][ikey]]:
            dlg.notification(
                "{} Collections".format(_label(media_type)),
                "Already in \"{}\"".format(collections[idx]["name"]),
                xbmcgui.NOTIFICATION_INFO,
            )
            return
        collections[idx][ikey].append(title)

    _set_collections(config, media_type, collections)
    save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def action_edit_collection(collection_index, media_type):
    """Dialog to rename or delete a collection."""
    config = load_config()
    collections = _get_collections(config, media_type)
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
            _set_collections(config, media_type, collections)
            save_config(config)
            xbmc.executebuiltin("Container.Refresh")
    elif choice == 1:
        desc = dlg.input(
            "Collection Description",
            defaultt=col.get("description", ""),
        )
        if desc != col.get("description", ""):
            collections[collection_index]["description"] = desc
            _set_collections(config, media_type, collections)
            save_config(config)
            xbmc.executebuiltin("Container.Refresh")
    elif choice == 2:
        if dlg.yesno(
            "Delete Collection",
            "Delete \"{}\"?\n\nItems will not be removed from your library.".format(
                col["name"]
            ),
        ):
            collections.pop(collection_index)
            _set_collections(config, media_type, collections)
            save_config(config)
            xbmc.executebuiltin("Container.Refresh")


def action_set_collection_art(collection_index, media_type):
    """Visual art picker — choose poster and fanart from collection members."""
    config = load_config()
    collections = _get_collections(config, media_type)
    if collection_index >= len(collections):
        return

    col = collections[collection_index]
    ikey = _items_key(media_type)
    dlg = xbmcgui.Dialog()

    art_type_idx = dlg.select(
        "Set Art for \"{}\"".format(col["name"]),
        ["Poster", "Fanart"],
    )
    if art_type_idx < 0:
        return
    art_key = ["poster", "fanart"][art_type_idx]

    if media_type == "tv":
        from tv import get_library_shows
        library_items = get_library_shows()
    else:
        from movies import get_library_movies
        library_items = get_library_movies()

    library_lookup = {s["title"].lower(): s for s in library_items}

    items = []
    art_urls = []
    current_url = col.get("art", {}).get(art_key, "")
    preselect = -1

    for title in col[ikey]:
        item = library_lookup.get(title.lower())
        if not item:
            continue
        url = item.get("art", {}).get(art_key, "")
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
            "{} Collections".format(_label(media_type)),
            "No {} art found".format(art_key),
            xbmcgui.NOTIFICATION_INFO,
        )
        return

    kwargs = {"useDetails": True}
    if preselect >= 0:
        kwargs["preselect"] = preselect
    choice = dlg.select(
        "Select {}".format(art_key.title()), items, **kwargs
    )
    if choice < 0:
        return

    if "art" not in col:
        col["art"] = {}
    col["art"][art_key] = art_urls[choice]
    _set_collections(config, media_type, collections)
    save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def action_move_in_collection(collection_index, pos, direction, media_type):
    """Move an item up or down within a collection."""
    config = load_config()
    collections = _get_collections(config, media_type)
    if collection_index >= len(collections):
        return

    ikey = _items_key(media_type)
    items = collections[collection_index][ikey]
    if direction == "up" and pos > 0:
        items[pos], items[pos - 1] = items[pos - 1], items[pos]
    elif direction == "down" and pos < len(items) - 1:
        items[pos], items[pos + 1] = items[pos + 1], items[pos]

    _set_collections(config, media_type, collections)
    save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def action_remove_from_collection(collection_index, pos, media_type):
    """Remove an item from a collection."""
    config = load_config()
    collections = _get_collections(config, media_type)
    if collection_index >= len(collections):
        return

    ikey = _items_key(media_type)
    items = collections[collection_index][ikey]
    if pos < len(items):
        items.pop(pos)
        if not items:
            collections.pop(collection_index)
        _set_collections(config, media_type, collections)
        save_config(config)
        xbmc.executebuiltin("Container.Refresh")
