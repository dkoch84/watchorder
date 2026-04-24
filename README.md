# Watch Order

[![GitHub](https://img.shields.io/badge/GitHub-repository.dkoch84-black?logo=github)](https://github.com/dkoch84/repository.dkoch84) [![Kodi Repository](https://img.shields.io/badge/Kodi_Repo-dank__repository-blue)](https://dkoch84.github.io/repository.dkoch84/) [![Download Repository](https://img.shields.io/badge/Download-repository.dank--1.0.0.zip-green)](https://dkoch84.github.io/repository.dkoch84/repository.dank-1.0.0.zip)

A Kodi video plugin that replaces the standard library browser with a **collection-aware** TV and movie browser. Group related TV shows and movies into collections, manage linked movies across franchise boundaries, and sync your setup across multiple Kodi installs via MySQL.

## Features

- **TV Collections** — combine related shows (e.g. a franchise with multiple series) into one item in the title listing. Collections are managed entirely through context menus.
- **Movie Collections** — group related movies into collections, or import existing Kodi movie sets with the *Migrate Movie Sets* action in addon settings.
- **Linked movies** — movies linked to a TV show in Kodi appear alongside its seasons and episodes. Move them between the show's episode list and the collection level via context menu, and reorder them freely among seasons.
- **Shared collections** — optionally sync collection config across multiple Kodi installs using the same MySQL server. Enable in addon settings; requires MySQL configured in `advancedsettings.xml`.
- **Tag filtering** — browse TV shows and movies by library tag. Root menu includes dedicated "TV Shows by Tag" and "Movies by Tag" folders. Useful for skin widgets scoped to a genre or category.
- **Flatten seasons** — respects Kodi's *Settings > Media > Videos > "Flatten TV show seasons"* setting. Single-season shows (with no specials) skip straight to the episode list.
- **Select first unwatched** — respects Kodi's *"Select first unwatched TV show season/episode"* setting, auto-scrolling to your next unwatched season or episode.
- **Include specials** — respects Kodi's *"Include All Seasons and Specials"* setting when determining the first unwatched item.
- **Forced views** — on first run, sets skin forced views for seasons (Big Icons), episodes (Landscape), TV shows (PosterInfo), and movies (PosterInfo) if not already configured.
- **Playback tracking** — saves resume points every 5 seconds during playback and auto-marks episodes and movies as watched when playback reaches the end, including when the user stops in the closing credits. Matches Kodi's own "near end" thresholds (last 3 minutes *or* last 8% of runtime).

## Installation

1. Download the [repository zip](https://dkoch84.github.io/repository.dkoch84/repository.dank-1.0.0.zip).
2. In Kodi, go to *Settings > Addons > Install from zip file* and select the downloaded zip.
3. Go to *Install from repository > dank_repository > Video add-ons* and install **Watch Order**.

## Usage

Use as a replacement for `library://video/tvshows/titles/` and `library://video/movies/titles/` in skin widgets and shortcuts. The plugin URL is:

```
plugin://plugin.video.watchorder/
```

The root menu provides four entries: **TV Shows**, **Movies**, **TV Shows by Tag**, and **Movies by Tag**.

### Tag filtering

Pass a `tag` parameter to filter by a library tag:

```
plugin://plugin.video.watchorder/?tag=anime
```

Bare `?tag=` URLs are supported for backward compatibility and go straight to TV listings. Use `?tag=_all` to skip the picker and list all shows.

### TV Collections

- **Create** — right-click a show > *Add to TV Collection* > pick an existing collection or create a new one.
- **Reorder** — inside a collection, right-click a show > *Move Up* / *Move Down*.
- **Art** — right-click a collection > *Set Collection Art* to pick poster/fanart from member shows.
- **Edit/Delete** — right-click a collection > *Edit TV Collection* to rename, add a description, or delete.

### Movie Collections

- **Create** — right-click a movie > *Add to Movie Collection* > pick an existing collection or create a new one.
- **Migrate** — go to *Addon Settings > Movie Collections > Migrate Movie Sets* to import all Kodi movie sets as collections (sorted by year, preserving set art and plot).
- **Reorder/Art/Edit** — same context menu workflow as TV collections.

### Linked Movies

Kodi's "Link to TV Show" feature (set in the movie information dialog) is respected by the plugin. Movies linked to a TV show appear in that show's listing.

- **At show level** — linked movies appear alongside seasons or in the flattened episode list. Right-click > *Move Up* / *Move Down* to position them between seasons.
- **Move to collection** — right-click a linked movie > *Move to Collection* to promote it to the collection level, where it appears alongside TV shows.
- **Move back** — right-click a collection-level movie > *Move to Episodes* to return it to the show's listing.

### Collections-only mode

Right-click any item in the TV or movie listing and select *Collections Only* to hide all non-collection items. Select *Show All* to restore.

### Shared collections

Enable *Shared collections* in addon settings to sync your collection configuration across multiple Kodi installs using the same MySQL server configured in `advancedsettings.xml`. Requires the `script.module.myconnpy` addon. Falls back to local JSON storage when unavailable.

## Playback tracking

The plugin runs a background `PlaybackMonitor` that keeps Kodi's library in sync with how you actually watched a video, so resume points and watched flags stay accurate whether playback ends naturally, is stopped in the credits, or is stopped mid-video.

### What gets saved

| Event | Action |
|---|---|
| Playback starts | Caches runtime so later callbacks stay correct even if Kodi has already torn down the player. |
| Every 5 seconds during playback | Saves the current position as a resume point (unless playback is already in the "near end" zone — see below). |
| Playback paused | Saves the current position as a resume point. |
| Playback ends naturally (`onPlayBackEnded`) | Marks as watched, clears the resume point. |
| Playback stopped (`onPlayBackStopped`) in the near-end zone | Marks as watched, clears the resume point. |
| Playback stopped (`onPlayBackStopped`) before the near-end zone | Saves the current position as a resume point. |

The manual *Set Watched* / *Set Unwatched* context menu entries also clear the resume point when marking as watched, so a subsequent play starts from the beginning.

### Near-end threshold

Playback is treated as "effectively complete" — i.e. marked as watched instead of saving a resume point — when **either** of these is true:

- the remaining time is ≤ **3 minutes** (`COMPLETE_SECONDS_FROM_END = 180`), **or**
- the remaining time is ≤ **8%** of the runtime (`COMPLETE_PERCENT_FROM_END = 0.08`).

These defaults match Kodi's built-in `<ignoresecondsatend>` / `<ignorepercentatend>` values from `advancedsettings.xml`. The two thresholds are deliberately generous so that stopping anywhere in the closing credits counts as watched. Concretely, a 23-minute Simpsons episode (1381 s) is marked watched once the player is past ≈ 1201 s (the 3-minute rule kicks in first for anything shorter than ~37.5 minutes; the percentage rule dominates for longer runtimes).

Both constants live on `PlaybackMonitor` in `main.py` and can be adjusted if you want different behaviour:

```python
class PlaybackMonitor(xbmc.Monitor):
    COMPLETE_SECONDS_FROM_END = 180   # last 3 minutes count as watched
    COMPLETE_PERCENT_FROM_END = 0.08  # or last 8% of runtime
```

## Kodi settings respected

These Kodi settings (under *Settings > Media > Videos*) are read and applied by the plugin since they don't natively apply to addon directories:

| Setting | Effect |
|---|---|
| Flatten TV show seasons | `Never` / `If only one season` / `Always` — controls whether the season list is skipped |
| Select first unwatched TV show season/episode | `Never` / `On first entry` / `Always` — auto-scrolls to the first unwatched item |
| Include All Seasons and Specials | Controls whether specials (season 0) count when finding the first unwatched item |

## License

MIT
