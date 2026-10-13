# ⛏️ mc-stats-webui

**Live competitive rankings for your Minecraft survival server.**

A **Fabric server mod** that embeds a small web UI + API. Players open it in a browser — no client mod needed.

![Ranking home screenshot](screenshots/screenshot.png)

## [MORE SCREENSHOTS](screenshots/README.md)

## ✨ Features

- 🏆 Home podium with **Champion**, **Most dedicated**, and **Most efficient** crowns
- 🥇 Vanilla advancements: who has the most, who unlocked a specific one, and a player’s full list
- 🆚 Side-by-side player compare
- 📊 Leaderboards for the whole vanilla stats catalog (custom, mined, killed, …)
- 🧮 Transparent scoring (“How we rank”) — farms inflate some boards on purpose
- 🌐 UI in **English / Español / Français / 简体中文** · light / dark / system theme
- 🏷️ Branding via `config/mc-stats-webui.json` (title, slogan, tagline, window title, bind, port)
- ⚡ In-memory stats cache (see below)

## 🧠 Stats cache

On world start the mod loads every player stats file into RAM. The API serves that snapshot — it does not re-scan the disk on each request.

When a connected player gains stats, their UUID is marked dirty. Every ~15 s (and before each API snapshot) dirty players are flushed with vanilla `save()`, then that one entry is reloaded into the cache. Offline players drop out of the dirty set and reload from disk if needed.

| URL | What |
| --- | --- |
| `http://localhost:25580/` | Web UI |
| `http://localhost:25580/api/players` | JSON API |

More detail: [endpoints](docs/endpoints.md) · [stats & champion](docs/stats-analysis.md)

## 🛠️ Development

**Needs:** Java 25 · Node 24+ · [Yarn via Corepack](https://yarnpkg.com/corepack) · Fabric for Minecraft 26.1.2, 26.2 or 26.3

```bash
cd web
corepack yarn install
corepack yarn dev
```

UI: `http://localhost:5173` (proxies `/api` → `25580`)

```bash
./gradlew build
```

The SvelteKit UI is built static and shipped **inside the JAR**.

### Supported Minecraft versions

The default build targets **26.3**. Build each supported version from the same branch:

```bash
./gradlew build -Pminecraft_version=26.1.2
./gradlew build -Pminecraft_version=26.2
./gradlew build -Pminecraft_version=26.3
```

Install the JAR matching your server from `build/<minecraft_version>/libs/`,
alongside Fabric Loader 0.19.5+ and Fabric API for that Minecraft version.
Each JAR targets its own Minecraft version; the advancement API adapter is selected
at compile time, with no runtime reflection. Build the versions sequentially in a
single checkout because texture extraction and the web build share output files.

CI builds all three versions on pull requests, pushes to `main`, and release tags.
A tag such as `v1.2.2` releases all three JARs; an existing version-specific tag such
as `v1.2.2+26.1.2` releases only the matching JAR.

### Simplified Chinese

Choose **简体中文** in the language menu. Chinese browser locales select it automatically;
the choice is saved locally. UI text, ranking explanations, vanilla advancements,
and vanilla item, block and entity names are translated. Minecraft translations are
extracted from the selected version's official language assets. Modded identifiers
without a translation retain their readable fallback names.

```bash
cd web
corepack yarn check
cd ..
node --experimental-strip-types scripts/check_translations.ts
```
