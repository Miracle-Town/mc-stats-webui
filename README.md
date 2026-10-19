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
- 🏷️ Branding via `config/mc-stats-webui/config.json` (title, slogan, tagline, window title, icon, bind, port)
- ⚡ In-memory stats cache (see below)

## ⚙️ Configuration

Edit `config/mc-stats-webui/config.json` and restart the server.
The old `config/mc-stats-webui.json` is automatically migrated if the new file does
not exist; otherwise, the new file takes priority.

| Option | Default | Description |
| --- | --- | --- |
| `port` | `25580` | Web server port (1–65535). |
| `bind` | `"0.0.0.0"` | Web server listening address. |
| `world` | `""` | World folder relative to the server directory; empty uses the active world. |
| `title` | `"Ranking"` | Homepage heading. |
| `slogan` | `"Server stats."` | Homepage description. |
| `tagline` | `"by borrageiros"` | Splash text beside the heading. |
| `windowTitle` | `"{page} - Server Ranking"` | Browser title; must include `{page}` or `<page>`. |
| `icon` | `""` | Icon filename beside `config.json`, e.g. `"icon.png"`; empty uses `server-icon.png`. |

Icons support PNG, ICO, SVG, WebP, JPEG and GIF. Missing or invalid images fall back
to the built-in icon. Replacing the image file does not require a restart.

## 🧠 Stats cache

On world start the mod loads every player stats file into RAM. The API serves that snapshot — it does not re-scan the disk on each request.

When a connected player gains stats, their UUID is marked dirty. Every ~15 s (and before each API snapshot) dirty players are flushed with vanilla `save()`, then that one entry is reloaded into the cache. Offline players drop out of the dirty set and reload from disk if needed.

| URL | What |
| --- | --- |
| `http://localhost:25580/` | Web UI |
| `http://localhost:25580/api/players` | JSON API |

More detail: [endpoints](docs/endpoints.md) · [stats & champion](docs/stats-analysis.md)

## 🛠️ Development

**Needs:** Java 25 · Python 3.9+ · Git · WebP tools (`cwebp` and `dwebp`) · Node 24+ · [Yarn via Corepack](https://yarnpkg.com/corepack) · Fabric for Minecraft 26.1.2, 26.2 or 26.3

```bash
./gradlew generateMcResources
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
at compile time, with no runtime reflection. MC resources, SvelteKit intermediates
and the static UI are isolated under `build/<minecraft_version>/`. Build versions
sequentially in one checkout because Gradle/Loom and the toolchain share build state.

### Minecraft icon atlases

Packaging automatically runs the pinned [MinecraftImageGenerator](https://github.com/Aerhhh/MinecraftImageGenerator)
tooling to render icons and pack 64px sprites into atlases of at most 2048×2048px.
The PNG atlases are converted with `cwebp -lossless -exact`; `dwebp` decodes each
result and `scripts/convert_mc_atlases.py` checks every RGBA pixel before publishing,
including RGB values under fully transparent pixels.
PNG intermediates stay in `mc/work/`, while `mc/generated/atlas/` contains WebP files.
Vite imports them through `?url` and emits hashed WebP assets into the packaged UI.
Each sprite has a 1px transparent gutter. `McItem` reads generated coordinates and
shares one image load per atlas; unknown IDs use a letter placeholder without probing PNG URLs.
Rendering, language extraction and atlas generation happen only in the build pipeline,
never at server startup or during browser requests.

Generated assets live in `build/<version>/mc/generated/`; rendered source images and
extracted Minecraft assets live in `build/<version>/mc/work/`. Shared pinned build
tools live in `build/tools/mc-atlas/`. Generated JSON and images are not committed
or written into `web/src` or `web/static`.
Each `lang/<locale>.json` contains block, item, entity, stat and advancement translations.
Advancement display-key aliases are merged into the same dictionary; stats and
advancement pages share these files through `web/src/lib/mc/lang.ts`.

Gradle skips unchanged resource tasks. A version/toolchain/input fingerprint plus
file checksums also allows reuse when switching back to a previously built version
or restoring the CI asset cache. Changing tool versions or integration scripts,
changing the MC version, deleting outputs, or corrupting an asset invalidates reuse.
`clean` removes the selected version's outputs; the next package regenerates them.

```bash
# Prepare another version for frontend development, then read its existing assets.
./gradlew generateMcResources -Pminecraft_version=26.1.2
cd web
MC_VERSION=26.1.2 corepack yarn dev
MC_VERSION=26.1.2 corepack yarn check
```

From the repository root, force regeneration with:

```bash
./gradlew generateMcResources -Pminecraft_version=26.3 -Pforce_mc_resources=true
```

`scripts/mc-atlas/toolchain.json` locks generator, renderer and dependency versions;
it also sets the lossless WebP compression effort (`webp.quality` and `webp.method`).
Changing these values or the converter invalidates the resource cache. Page/CSS edits
reuse the existing WebP files without running conversion again.
`tooling.patch` pins Marmalade and makes incomplete renders and missing-texture
checkerboards fail the build. It also includes drawable non-item blocks from the
client blockstate registry and prefers current item models over obsolete hard-coded
block-entity icons (signs and beds). Upstream supplies configurable paths, atlas paging,
64px tiles and 1px gutters through explicit CLI flags. The Java renderer reads the
unmodified client JAR; no model rewrites or legacy texture copies are needed.
Entity and non-item block aliases are resolved at build time. The web build includes
only atlases, indexes, translations and the skin renderer's elytra texture;
the generator, rendering libraries and raw textures are not shipped.

The generator is pinned to `284b679`, using the Apache-2.0 Java
[asset-renderer](https://github.com/minecraft-library/asset-renderer) library pinned
by upstream to `addedec7a2`. Rendering uses the JDK; WebP verification uses Python’s
standard library and accepts the non-interlaced 8-bit RGB/RGBA PNGs from the pipeline;
no .NET SDK, ImageSharp or Six Labors license is required.
Install the WebP command-line tools before building:

```bash
brew install webp                 # macOS
sudo apt-get install webp         # Debian / Ubuntu
# Windows: install the WebP tools and add cwebp.exe and dwebp.exe to PATH.
```

CI installs WebP tools automatically. Previous Six Labors repository secrets and
local license settings are unused and can be removed.

Frontend commands use `web/tsconfig.base.json` and generate the effective TypeScript
config at `build/<version>/tsconfig.web.json`. The tracked `web/tsconfig.json` is the
editor entry; `yarn prepare`, `dev`, `build` and `check` refresh an ignored
`web/.svelte-kit/tsconfig.json` pointer to the selected version's framework config.
Resource-cache regression checks run as part of `./gradlew check`.

CI builds all three versions on pull requests, pushes to `main`, and release tags.
A tag such as `v1.2.2` releases all three JARs; an existing version-specific tag such
as `v1.2.2+26.1.2` releases only the matching JAR.
