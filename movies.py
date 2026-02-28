import xbmc
import xbmcgui
import xbmcplugin

from collections_mod import (
    load_config, save_config, _get_collections, _set_collections, _items_key,
)


def get_library_movies(tag=None, properties=None):
    from main import jsonrpc
    if properties is None:
        properties = [
            "title", "art", "year", "genre", "rating", "plot",
            "dateadded", "lastplayed", "file", "playcount", "runtime",
            "resume",
        ]
    params = {"properties": properties}
    if tag:
        params["filter"] = {"field": "tag", "operator": "is", "value": tag}
    result = jsonrpc("VideoLibrary.GetMovies", params)
    if result and "movies" in result:
        return result["movies"]
    return []


def list_movies(tag=None, collections_only=False):
    """Collection-aware movie browser with 'Filter by Tag' folder."""
    from main import HANDLE, build_url, watched_menu_item

    config = load_config()
    collections = _get_collections(config, "movie")
    library_movies = get_library_movies(tag=tag)
    library_lookup = {m["title"].lower(): m for m in library_movies}

    title_to_collection = {}
    for idx, col in enumerate(collections):
        for movie_title in col.get("movies", []):
            title_to_collection[movie_title.lower()] = idx

    sorted_movies = sorted(library_movies, key=lambda m: m["title"].lower())

    xbmcplugin.setContent(HANDLE, "movies")
    collections_shown = set()

    # Toggle URL for collections-only filter
    toggle_params = {"action": "root_movies"}
    if tag:
        toggle_params["tag"] = tag
    if not collections_only:
        toggle_params["collections_only"] = "1"
    toggle_url = build_url(toggle_params)
    toggle_label = "Show All" if collections_only else "Collections Only"

    for movie in sorted_movies:
        col_idx = title_to_collection.get(movie["title"].lower())

        if col_idx is not None:
            if col_idx in collections_shown:
                continue
            collections_shown.add(col_idx)

            col = collections[col_idx]
            art = {}
            for member_title in col["movies"]:
                member = library_lookup.get(member_title.lower())
                if member and member.get("art"):
                    art = dict(member["art"])
                    break
            configured_art = col.get("art", {})
            art.update(configured_art)

            li = xbmcgui.ListItem(col["name"])
            tag_info = li.getVideoInfoTag()
            tag_info.setMediaType("movie")
            tag_info.setTitle(col["name"])
            tag_info.setPlot(col.get("description", ""))

            max_lp = ""
            max_da = ""
            for member_title in col["movies"]:
                member = library_lookup.get(member_title.lower())
                if member:
                    lp = member.get("lastplayed", "")
                    if lp > max_lp:
                        max_lp = lp
                    da = member.get("dateadded", "")
                    if da > max_da:
                        max_da = da
            if max_lp:
                tag_info.setLastPlayed(max_lp)
            if max_da:
                tag_info.setDateAdded(max_da)

            if art:
                li.setArt(art)

            li.addContextMenuItems([
                (
                    toggle_label,
                    "Container.Update({})".format(toggle_url),
                ),
                (
                    "Set Collection Art",
                    "RunPlugin({})".format(build_url({
                        "action": "set_movie_collection_art",
                        "index": col_idx,
                    })),
                ),
                (
                    "Edit Movie Collection",
                    "RunPlugin({})".format(build_url({
                        "action": "edit_movie_collection",
                        "index": col_idx,
                    })),
                ),
            ])

            url = build_url({"action": "movie_collection", "index": col_idx})
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
        else:
            if collections_only:
                continue

            li = xbmcgui.ListItem(movie["title"])
            tag_info = li.getVideoInfoTag()
            tag_info.setMediaType("movie")
            tag_info.setTitle(movie["title"])
            tag_info.setPlot(movie.get("plot", ""))
            tag_info.setYear(movie.get("year", 0))
            tag_info.setRating(movie.get("rating", 0.0))
            if movie.get("dateadded"):
                tag_info.setDateAdded(movie["dateadded"])
            if movie.get("lastplayed"):
                tag_info.setLastPlayed(movie["lastplayed"])
            genres = movie.get("genre", [])
            if genres:
                tag_info.setGenres(genres)
            runtime = movie.get("runtime", 0)
            if runtime:
                tag_info.setDuration(runtime)
            playcount = movie.get("playcount", 0)
            if playcount:
                tag_info.setPlaycount(playcount)

            resume = movie.get("resume", {})
            if resume.get("position", 0) > 0:
                tag_info.setResumePoint(
                    resume["position"], resume.get("total", 0)
                )

            if movie.get("art"):
                li.setArt(movie["art"])

            li.addContextMenuItems([
                watched_menu_item(build_url, "movie",
                                  movie.get("playcount", 0),
                                  id=movie["movieid"]),

                (
                    toggle_label,
                    "Container.Update({})".format(toggle_url),
                ),
                (
                    "Add to Movie Collection",
                    "RunPlugin({})".format(build_url({
                        "action": "add_to_movie_collection",
                        "title": movie["title"],
                    })),
                ),
            ])

            li.setProperty("IsPlayable", "true")
            url = build_url({
                "action": "play_movie",
                "movieid": movie["movieid"],
                "file": movie.get("file", ""),
            })
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_DATEADDED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LASTPLAYED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(HANDLE)


def play_movie(movieid, file):
    from main import HANDLE, jsonrpc
    import main as main_module

    if not file:
        result = jsonrpc(
            "VideoLibrary.GetMovieDetails",
            {"movieid": movieid, "properties": ["file"]},
        )
        if result and "moviedetails" in result:
            file = result["moviedetails"].get("file", "")
    if file:
        li = xbmcgui.ListItem(path=file)
        tag = li.getVideoInfoTag()
        tag.setMediaType("movie")
        tag.setDbId(movieid)

        # Set up playback monitoring for auto-marking as watched
        main_module._current_movieid = movieid
        main_module._current_episodeid = None
        if main_module._playback_monitor_instance is None:
            main_module._playback_monitor_instance = main_module.PlaybackMonitor()

        xbmcplugin.setResolvedUrl(HANDLE, True, li)
    else:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def action_migrate_movie_sets():
    """Import Kodi movie sets into our movie collections."""
    from main import ADDON_ID, jsonrpc

    config = load_config()
    collections = _get_collections(config, "movie")
    existing_names = {c["name"].lower() for c in collections}

    result = jsonrpc(
        "VideoLibrary.GetMovieSets",
        {"properties": ["title", "art", "plot"]},
    )
    sets = result.get("sets", []) if result else []

    if not sets:
        xbmcgui.Dialog().notification(
            "Watch Order",
            "No movie sets found in library",
            xbmcgui.NOTIFICATION_INFO,
        )
        return

    progress = xbmcgui.DialogProgress()
    progress.create("Migrating Movie Sets", "Scanning...")

    imported = 0
    skipped = 0

    for i, movie_set in enumerate(sets):
        if progress.iscanceled():
            break

        set_name = movie_set.get("title", "")
        progress.update(
            int((i / len(sets)) * 100),
            "Processing: {}".format(set_name),
        )

        if set_name.lower() in existing_names:
            skipped += 1
            continue

        # Get member movies sorted by year
        detail = jsonrpc(
            "VideoLibrary.GetMovieSetDetails",
            {
                "setid": movie_set["setid"],
                "properties": ["title"],
                "movies": {
                    "properties": ["title"],
                    "sort": {"method": "year", "order": "ascending"},
                },
            },
        )
        if not detail or "setdetails" not in detail:
            continue

        members = detail["setdetails"].get("movies", [])
        movie_titles = [m["title"] for m in members]
        if not movie_titles:
            continue

        new_col = {"name": set_name, "movies": movie_titles}

        set_art = movie_set.get("art", {})
        if set_art:
            new_col["art"] = set_art

        set_plot = movie_set.get("plot", "")
        if set_plot:
            new_col["description"] = set_plot

        collections.append(new_col)
        existing_names.add(set_name.lower())
        imported += 1

    progress.close()

    if imported > 0:
        _set_collections(config, "movie", collections)
        save_config(config)

    msg = "Imported {} collection{}".format(imported, "s" if imported != 1 else "")
    if skipped:
        msg += " ({} skipped, already exist)".format(skipped)
    xbmcgui.Dialog().ok("Migrate Movie Sets", msg)
