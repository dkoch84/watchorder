# Watch Order

[![GitHub](https://img.shields.io/badge/GitHub-repository.dkoch84-black?logo=github)](https://github.com/dkoch84/repository.dkoch84) [![Kodi Repository](https://img.shields.io/badge/Kodi_Repo-dank__repository-blue)](https://dkoch84.github.io/repository.dkoch84/) [![Download Repository](https://img.shields.io/badge/Download-repository.dank--1.0.0.zip-green)](https://dkoch84.github.io/repository.dkoch84/repository.dank-1.0.0.zip)

A Kodi video plugin that adds **TV Collections** to the library — group related TV shows into a single entry, just like Kodi's movie collections.

## Features

- **TV Collections** — combine related shows (e.g. a franchise with multiple series) into one item in the title listing. Collections are managed entirely through context menus.
- **Tag filtering** — browse shows by library tag. Useful for skin widgets scoped to a genre or category.
- **Flatten seasons** — respects Kodi's *Settings > Media > Videos > "Flatten TV show seasons"* setting. Single-season shows (with no specials) skip straight to the episode list.
- **Select first unwatched** — respects Kodi's *"Select first unwatched TV show season/episode"* setting, auto-scrolling to your next unwatched season or episode.
- **Forced views** — on first run, sets skin forced views for seasons (Big Icons) and episodes (Landscape) if not already configured.

## Installation

1. Download the [repository zip](https://dkoch84.github.io/repository.dkoch84/repository.dank-1.0.0.zip).
2. In Kodi, go to *Settings > Addons > Install from zip file* and select the downloaded zip.
3. Go to *Install from repository > dank_repository > Video add-ons* and install **Watch Order**.

## Usage

Use as a replacement for `library://video/tvshows/titles/` in skin widgets and shortcuts. The plugin URL is:

```
plugin://plugin.video.watchorder/
```

### Tag filtering

Pass a `tag` parameter to filter by a library tag:

```
plugin://plugin.video.watchorder/?tag=anime
```

The root level (no tag) shows a tag picker. Use `?tag=_all` to skip the picker and list all shows.

### Collections

- **Create** — right-click a show > *Add to TV Collection* > pick an existing collection or create a new one.
- **Reorder** — inside a collection, right-click a show > *Move Up* / *Move Down*.
- **Art** — right-click a collection > *Set Collection Art* to pick poster/fanart from member shows.
- **Edit/Delete** — right-click a collection > *Edit TV Collection* to rename, add a description, or delete.

Collections are stored in `~/.kodi/userdata/addon_data/plugin.video.watchorder/collections.json`.

## Kodi settings respected

These Kodi settings (under *Settings > Media > Videos*) are read and applied by the plugin since they don't natively apply to addon directories:

| Setting | Effect |
|---|---|
| Flatten TV show seasons | `Never` / `If only one season` / `Always` — controls whether the season list is skipped |
| Select first unwatched TV show season/episode | `Never` / `On first entry` / `Always` — auto-scrolls to the first unwatched item |

## License

MIT
