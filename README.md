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

## Kodi settings respected

These Kodi settings (under *Settings > Media > Videos*) are read and applied by the plugin since they don't natively apply to addon directories:

| Setting | Effect |
|---|---|
| Flatten TV show seasons | `Never` / `If only one season` / `Always` — controls whether the season list is skipped |
| Select first unwatched TV show season/episode | `Never` / `On first entry` / `Always` — auto-scrolls to the first unwatched item |
| Include All Seasons and Specials | Controls whether specials (season 0) count when finding the first unwatched item |

## License

MIT
