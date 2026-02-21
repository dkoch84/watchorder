import xbmc
import xbmcgui
import xbmcplugin

from collections_mod import load_config, _get_collections, _items_key


def get_library_shows(tag=None, properties=None):
    from main import jsonrpc
    if properties is None:
        properties = [
            "title", "art", "year", "genre", "rating", "plot",
            "dateadded", "lastplayed", "watchedepisodes", "episode",
        ]
    params = {"properties": properties}
    if tag:
        params["filter"] = {"field": "tag", "operator": "is", "value": tag}
    result = jsonrpc("VideoLibrary.GetTVShows", params)
    if result and "tvshows" in result:
        return result["tvshows"]
    return []


def list_titles(tag=None, collections_only=False):
    """Collection-aware title browser with 'Filter by Tag' folder."""
    from main import HANDLE, build_url, watched_menu_item

    config = load_config()
    collections = _get_collections(config, "tv")
    library_shows = get_library_shows(tag=tag)
    library_lookup = {s["title"].lower(): s for s in library_shows}

    title_to_collection = {}
    for idx, col in enumerate(collections):
        for show_title in col.get("shows", []):
            title_to_collection[show_title.lower()] = idx

    sorted_shows = sorted(library_shows, key=lambda s: s["title"].lower())

    xbmcplugin.setContent(HANDLE, "tvshows")
    collections_shown = set()

    # Toggle URL for collections-only filter
    toggle_params = {"action": "root_tv"}
    if tag:
        toggle_params["tag"] = tag
    if not collections_only:
        toggle_params["collections_only"] = "1"
    toggle_url = build_url(toggle_params)
    toggle_label = "Show All" if collections_only else "Collections Only"

    for show in sorted_shows:
        col_idx = title_to_collection.get(show["title"].lower())

        if col_idx is not None:
            if col_idx in collections_shown:
                continue
            collections_shown.add(col_idx)

            col = collections[col_idx]
            art = {}
            for member_title in col["shows"]:
                member = library_lookup.get(member_title.lower())
                if member and member.get("art"):
                    art = dict(member["art"])
                    break
            configured_art = col.get("art", {})
            art.update(configured_art)

            li = xbmcgui.ListItem(col["name"])
            tag_info = li.getVideoInfoTag()
            tag_info.setMediaType("tvshow")
            tag_info.setTitle(col["name"])
            tag_info.setPlot(col.get("description", ""))

            max_lp = ""
            max_da = ""
            for member_title in col["shows"]:
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
            if collections_only:
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

            show_pc = 1 if show.get("watchedepisodes", 0) >= show.get("episode", 1) else 0
            li.addContextMenuItems([
                watched_menu_item(build_url, "tvshow", show_pc,
                                  tvshowid=show["tvshowid"]),

                (
                    toggle_label,
                    "Container.Update({})".format(toggle_url),
                ),
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


def _collection_level_movie_ids(config=None):
    """Return set of movie IDs placed at collection level."""
    if config is None:
        config = load_config()
    ids = set()
    for col in config.get("collections", []):
        for entry in col.get("shows", []):
            if isinstance(entry, str) and entry.startswith("movie:"):
                try:
                    ids.add(int(entry.split(":")[1]))
                except (ValueError, IndexError):
                    pass
    return ids


def _build_movie_li(movie, build_url):
    """Build a ListItem for a linked movie."""
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
    li.setProperty("IsPlayable", "true")
    url = build_url({
        "action": "play_movie",
        "movieid": movie["movieid"],
        "file": movie.get("file", ""),
    })
    return li, url


_MOVIE_PROPS = [
    "title", "art", "year", "genre", "rating", "plot",
    "file", "playcount", "runtime", "resume",
    "dateadded", "lastplayed",
]


def _fetch_linked_movies(tvshowid, jsonrpc, config=None):
    """Fetch linked movie details, returning {movieid: details} dict.

    Excludes movies placed at collection level.
    """
    from db import get_linked_movie_ids

    linked_ids = get_linked_movie_ids(tvshowid)
    if not linked_ids:
        return {}
    col_ids = _collection_level_movie_ids(config=config)
    movie_details = {}
    for mid in linked_ids:
        if mid in col_ids:
            continue
        result = jsonrpc(
            "VideoLibrary.GetMovieDetails",
            {"movieid": mid, "properties": _MOVIE_PROPS},
        )
        if result and "moviedetails" in result:
            movie_details[mid] = result["moviedetails"]
    return movie_details


def _merge_show_items(seasons, movie_details, tvshowid, config=None):
    """Merge seasons and linked movies using stored order or default."""
    if config is None:
        config = load_config()
    stored = config.get("show_item_order", {}).get(str(tvshowid), [])

    season_map = {s["season"]: s for s in seasons}

    if stored and movie_details:
        items = []
        seen_s = set()
        seen_m = set()
        for entry in stored:
            if entry["type"] == "season" and entry["id"] in season_map:
                items.append(("season", season_map[entry["id"]]))
                seen_s.add(entry["id"])
            elif entry["type"] == "movie" and entry["id"] in movie_details:
                items.append(("movie", movie_details[entry["id"]]))
                seen_m.add(entry["id"])
        for s in seasons:
            if s["season"] not in seen_s:
                items.append(("season", s))
        for mid, m in movie_details.items():
            if mid not in seen_m:
                items.append(("movie", m))
    else:
        items = [("season", s) for s in seasons]
        items.extend(("movie", m) for m in movie_details.values())

    return items


def _find_collection_for_show(tvshowid, jsonrpc, config=None, show_title=None):
    """Find the collection index that contains the given show, or -1."""
    if show_title is None:
        result = jsonrpc(
            "VideoLibrary.GetTVShowDetails",
            {"tvshowid": tvshowid, "properties": ["title"]},
        )
        if not result or "tvshowdetails" not in result:
            return -1
        show_title = result["tvshowdetails"]["title"]

    show_title_lower = show_title.lower()
    if config is None:
        config = load_config()
    for idx, col in enumerate(config.get("collections", [])):
        for entry in col.get("shows", []):
            if isinstance(entry, str) and not entry.startswith("movie:"):
                if entry.lower() == show_title_lower:
                    return idx
    return -1


def list_seasons(tvshowid):
    from main import HANDLE, build_url, jsonrpc, get_kodi_setting, _select_first_unwatched, watched_menu_item

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

    flatten = get_kodi_setting("videolibrary.flattentvshows")
    if flatten == 2:
        list_episodes(tvshowid, None)
        return
    if flatten == 1:
        non_special = [s for s in seasons if s["season"] != 0]
        has_specials = any(s["season"] == 0 for s in seasons)
        if len(non_special) == 1 and not has_specials:
            list_episodes(tvshowid, None)
            return

    show_result = jsonrpc(
        "VideoLibrary.GetTVShowDetails",
        {"tvshowid": tvshowid, "properties": ["plot", "genre", "title"]},
    )
    show_info = show_result.get("tvshowdetails", {}) if show_result else {}

    config = load_config()
    movie_details = _fetch_linked_movies(tvshowid, jsonrpc, config=config)
    items = _merge_show_items(seasons, movie_details, tvshowid, config=config)

    col_idx = _find_collection_for_show(
        tvshowid, jsonrpc, config=config,
        show_title=show_info.get("title"),
    )

    try:
        xbmcplugin.setContent(HANDLE, "seasons")
        include_specials = get_kodi_setting(
            "videolibrary.tvshowsincludeallseasonsandspecials"
        )
        skip_specials = include_specials not in (1, 3)
        first_unwatched_index = None

        for idx, (item_type, data) in enumerate(items):
            if item_type == "season":
                if first_unwatched_index is None and data.get("playcount", 0) == 0:
                    if not (skip_specials and data["season"] == 0):
                        first_unwatched_index = idx

                label = data.get("label", "Season {}".format(data["season"]))
                li = xbmcgui.ListItem(label)
                tag_info = li.getVideoInfoTag()
                tag_info.setMediaType("season")
                tag_info.setSeason(data["season"])
                tag_info.setPlot(show_info.get("plot", ""))
                show_genres = show_info.get("genre", [])
                if show_genres:
                    tag_info.setGenres(show_genres)
                if data.get("art"):
                    li.setArt(data["art"])
                li.addContextMenuItems([
                    watched_menu_item(build_url, "season",
                                      data.get("playcount", 0),
                                      tvshowid=tvshowid,
                                      season=data["season"]),
    
                ])
                url = build_url({
                    "action": "episodes",
                    "tvshowid": tvshowid,
                    "season": data["season"],
                })
                xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
            else:
                li, url = _build_movie_li(data, build_url)
                ctx = [
                    watched_menu_item(build_url, "movie",
                                      data.get("playcount", 0),
                                      id=data["movieid"]),
                ]
                if idx > 0:
                    ctx.append((
                        "Move Up",
                        "RunPlugin({})".format(build_url({
                            "action": "move_show_item",
                            "tvshowid": tvshowid,
                            "pos": idx,
                            "direction": "up",
                        })),
                    ))
                if idx < len(items) - 1:
                    ctx.append((
                        "Move Down",
                        "RunPlugin({})".format(build_url({
                            "action": "move_show_item",
                            "tvshowid": tvshowid,
                            "pos": idx,
                            "direction": "down",
                        })),
                    ))
                if col_idx >= 0:
                    ctx.append((
                        "Move to Collection",
                        "RunPlugin({})".format(build_url({
                            "action": "move_linked_to_collection",
                            "movieid": data["movieid"],
                            "tvshowid": tvshowid,
                        })),
                    ))

                li.addContextMenuItems(ctx)
                xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
        xbmcplugin.endOfDirectory(HANDLE)
        _select_first_unwatched(first_unwatched_index)
    except RuntimeError:
        pass


def action_move_show_item(tvshowid, pos, direction):
    """Move a linked movie up or down in the show's season/movie listing."""
    from main import jsonrpc
    from db import get_linked_movie_ids
    from collections_mod import save_config

    # Rebuild current item order
    result = jsonrpc(
        "VideoLibrary.GetSeasons",
        {"tvshowid": tvshowid, "properties": ["season"]},
    )
    seasons = result.get("seasons", []) if result else []
    season_set = {s["season"] for s in seasons}

    config = load_config()

    linked_ids = get_linked_movie_ids(tvshowid)
    col_ids = _collection_level_movie_ids(config=config)
    linked_ids = [mid for mid in linked_ids if mid not in col_ids]
    movie_set = set(linked_ids)
    stored = config.get("show_item_order", {}).get(str(tvshowid), [])

    if stored:
        items = []
        seen_s = set()
        seen_m = set()
        for entry in stored:
            if entry["type"] == "season" and entry["id"] in season_set:
                items.append(entry)
                seen_s.add(entry["id"])
            elif entry["type"] == "movie" and entry["id"] in movie_set:
                items.append(entry)
                seen_m.add(entry["id"])
        for s in seasons:
            if s["season"] not in seen_s:
                items.append({"type": "season", "id": s["season"]})
        for mid in linked_ids:
            if mid not in seen_m:
                items.append({"type": "movie", "id": mid})
    else:
        items = [{"type": "season", "id": s["season"]} for s in seasons]
        items.extend({"type": "movie", "id": mid} for mid in linked_ids)

    if direction == "up" and pos > 0:
        items[pos], items[pos - 1] = items[pos - 1], items[pos]
    elif direction == "down" and pos < len(items) - 1:
        items[pos], items[pos + 1] = items[pos + 1], items[pos]

    config.setdefault("show_item_order", {})[str(tvshowid)] = items
    save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def action_move_linked_to_collection(movieid, tvshowid):
    """Move a linked movie from show level to collection level."""
    from main import jsonrpc
    from collections_mod import save_config

    col_idx = _find_collection_for_show(tvshowid, jsonrpc)
    if col_idx < 0:
        xbmcgui.Dialog().notification(
            "Watch Order", "Show is not in a collection",
            xbmcgui.NOTIFICATION_INFO,
        )
        return

    config = load_config()
    collections = config.get("collections", [])
    if col_idx >= len(collections):
        return

    marker = "movie:{}".format(movieid)
    shows_list = collections[col_idx].get("shows", [])
    if marker in shows_list:
        return

    # Find the show title to insert the movie after it
    result = jsonrpc(
        "VideoLibrary.GetTVShowDetails",
        {"tvshowid": tvshowid, "properties": ["title"]},
    )
    show_title = ""
    if result and "tvshowdetails" in result:
        show_title = result["tvshowdetails"]["title"]

    insert_pos = len(shows_list)
    if show_title:
        for i, entry in enumerate(shows_list):
            if isinstance(entry, str) and not entry.startswith("movie:"):
                if entry.lower() == show_title.lower():
                    insert_pos = i + 1
                    break

    shows_list.insert(insert_pos, marker)
    save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def action_move_linked_to_show(collection_index, pos):
    """Move a linked movie from collection level back to show level."""
    from collections_mod import save_config

    config = load_config()
    collections = config.get("collections", [])
    if collection_index >= len(collections):
        return

    shows_list = collections[collection_index].get("shows", [])
    if pos < len(shows_list):
        entry = shows_list[pos]
        if isinstance(entry, str) and entry.startswith("movie:"):
            shows_list.pop(pos)
            save_config(config)
    xbmc.executebuiltin("Container.Refresh")


def list_episodes(tvshowid, season):
    from main import HANDLE, build_url, jsonrpc, get_kodi_setting, _select_first_unwatched, watched_menu_item

    params = {
        "tvshowid": tvshowid,
        "properties": [
            "title", "plot", "season", "episode", "showtitle",
            "firstaired", "runtime", "rating", "director", "writer",
            "art", "file", "playcount", "resume", "lastplayed", "dateadded",
        ],
    }
    if season is not None:
        params["season"] = season
    result = jsonrpc("VideoLibrary.GetEpisodes", params)
    episodes = result.get("episodes", []) if result else []
    if not episodes:
        xbmcgui.Dialog().notification(
            "TV Collections", "No episodes found", xbmcgui.NOTIFICATION_INFO
        )
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    try:
        xbmcplugin.setContent(HANDLE, "episodes")
        skip_specials = False
        if season is None:
            include_specials = get_kodi_setting(
                "videolibrary.tvshowsincludeallseasonsandspecials"
            )
            skip_specials = include_specials not in (1, 3)
        first_unwatched_index = None
        for idx, ep in enumerate(episodes):
            if first_unwatched_index is None and ep.get("playcount", 0) == 0:
                if not (skip_specials and ep["season"] == 0):
                    first_unwatched_index = idx

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

            li.addContextMenuItems([
                watched_menu_item(build_url, "episode",
                                  ep.get("playcount", 0),
                                  id=ep["episodeid"]),

            ])
            li.setProperty("IsPlayable", "true")
            url = build_url({
                "action": "play",
                "episodeid": ep["episodeid"],
                "file": ep.get("file", ""),
            })
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

        if season is None:
            _add_linked_movies(tvshowid)

        xbmcplugin.endOfDirectory(HANDLE)
        _select_first_unwatched(first_unwatched_index)
    except RuntimeError:
        pass


def _add_linked_movies(tvshowid):
    """Add movies linked to a TV show to the current directory listing.

    Excludes movies placed at collection level.
    """
    from main import HANDLE, build_url, jsonrpc, watched_menu_item
    from db import get_linked_movie_ids

    linked_ids = get_linked_movie_ids(tvshowid)
    if not linked_ids:
        return

    config = load_config()
    col_ids = _collection_level_movie_ids(config=config)
    col_idx = _find_collection_for_show(tvshowid, jsonrpc, config=config)

    for mid in linked_ids:
        if mid in col_ids:
            continue
        result = jsonrpc(
            "VideoLibrary.GetMovieDetails",
            {"movieid": mid, "properties": _MOVIE_PROPS},
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
        if col_idx >= 0:
            ctx.append((
                "Move to Collection",
                "RunPlugin({})".format(build_url({
                    "action": "move_linked_to_collection",
                    "movieid": movie["movieid"],
                    "tvshowid": tvshowid,
                })),
            ))
        li.addContextMenuItems(ctx)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)


def play_episode(episodeid, file):
    from main import HANDLE, jsonrpc

    if not file:
        result = jsonrpc(
            "VideoLibrary.GetEpisodeDetails",
            {"episodeid": episodeid, "properties": ["file"]},
        )
        if result and "episodedetails" in result:
            file = result["episodedetails"].get("file", "")
    if file:
        li = xbmcgui.ListItem(path=file)
        tag = li.getVideoInfoTag()
        tag.setMediaType("episode")
        tag.setDbId(episodeid)
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
    else:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
