"""Extract version-specific translations from the Minecraft client JAR."""
from __future__ import annotations

import json
import os
import urllib.request
import zipfile
from pathlib import Path

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ASSET_CDN = "https://resources.download.minecraft.net"
USER_AGENT = "mc-stats-webui asset build"
_VERSION_META: dict[str, dict] = {}
LANG_FILES = {
    "en": "assets/minecraft/lang/en_us.json",
    "es": "assets/minecraft/lang/es_es.json",
    "fr": "assets/minecraft/lang/fr_fr.json",
    "zh-CN": "assets/minecraft/lang/zh_cn.json",
}

def gradle_home() -> Path:
	env = os.environ.get("GRADLE_USER_HOME")
	if env:
		return Path(env)
	return Path.home() / ".gradle"

def default_jar(version: str) -> Path:
	return gradle_home() / "caches" / "fabric-loom" / version / "minecraft-client.jar"

def fetch_json(url: str):
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
	with urllib.request.urlopen(request) as response:
		return json.load(response)

def version_meta(version: str) -> dict:
	cached = _VERSION_META.get(version)
	if cached:
		return cached
	manifest = fetch_json(MANIFEST_URL)
	entry = next((item for item in manifest["versions"] if item["id"] == version), None)
	if not entry:
		raise SystemExit(f"Minecraft version not found in manifest: {version}")
	meta = fetch_json(entry["url"])
	_VERSION_META[version] = meta
	return meta

def download_client_jar(version: str, dest: Path) -> None:
	print(f"Downloading Minecraft {version} client jar…")
	meta = version_meta(version)
	client = meta.get("downloads", {}).get("client")
	if not client or "url" not in client:
		raise SystemExit(f"No client download for Minecraft {version}")
	dest.parent.mkdir(parents=True, exist_ok=True)
	tmp = dest.with_suffix(".jar.tmp")
	urllib.request.urlretrieve(client["url"], tmp)
	tmp.replace(dest)
	print(f"Saved {dest}")

def download_lang_asset(version: str, filename: str) -> dict | None:
	cache = default_jar(version).parent / "lang" / filename
	if cache.is_file():
		try:
			data = json.loads(cache.read_text(encoding="utf-8"))
			if isinstance(data, dict) and data:
				return data
		except json.JSONDecodeError:
			pass
	meta = version_meta(version)
	index = meta.get("assetIndex")
	if not isinstance(index, dict) or "url" not in index:
		return None
	assets = fetch_json(index["url"])
	obj = assets.get("objects", {}).get(f"minecraft/lang/{filename}")
	if not isinstance(obj, dict) or "hash" not in obj:
		return None
	digest = str(obj["hash"])
	url = f"{ASSET_CDN}/{digest[:2]}/{digest}"
	print(f"Downloading {filename}…")
	data = fetch_json(url)
	if not isinstance(data, dict):
		return None
	cache.parent.mkdir(parents=True, exist_ok=True)
	cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
	return data

def resolve_jar(version: str, jar_arg: str | None) -> Path:
	jar = Path(jar_arg) if jar_arg else default_jar(version)
	if jar.is_file():
		return jar
	download_client_jar(version, jar)
	if not jar.is_file():
		raise SystemExit(f"Missing Minecraft client jar: {jar}")
	return jar

def load_json(jar: zipfile.ZipFile, path: str):
	try:
		return json.loads(jar.read(path))
	except KeyError:
		return None

def lang_entries(data) -> dict[str, str]:
	if not isinstance(data, dict):
		return {}
	return {
		key: value
		for key, value in data.items()
		if isinstance(key, str) and key.startswith("advancements.") and isinstance(value, str)
	}

def write_vanilla_lang(jar: zipfile.ZipFile, version: str, output: Path) -> None:
	lang_dir = output / "lang"
	# Some advancement IDs differ from their translation keys (e.g. bred_all_animals).
	# Read the actual display keys so all locales work with the API's advancement IDs.
	aliases: dict[str, str] = {}
	prefix = "data/minecraft/advancement/"
	for path in jar.namelist():
		if not path.startswith(prefix) or not path.endswith(".json"):
			continue
		display = (load_json(jar, path) or {}).get("display", {})
		base = "advancements." + path[len(prefix):-5].replace("/", ".")
		for kind in ("title", "description"):
			component = display.get(kind)
			if isinstance(component, dict) and isinstance(component.get("translate"), str):
				aliases[f"{base}.{kind}"] = component["translate"]
	for locale, path in LANG_FILES.items():
		data = load_json(jar, path)
		entries = lang_entries(data)
		if not entries:
			data = download_lang_asset(version, Path(path).name)
			entries = lang_entries(data)
		if not entries:
			raise SystemExit(f"Missing advancement translations for {locale} in Minecraft {version}")
		vanilla = {
			key: value for key, value in data.items()
			if key.startswith(("block.", "item.", "entity.", "stat.", "advancements.")) and isinstance(value, str)
		}
		for key, source in aliases.items():
			if source in vanilla:
				vanilla[key] = vanilla[source]
		lang_dir.mkdir(parents=True, exist_ok=True)
		(lang_dir / f"{locale}.json").write_text(
			json.dumps(vanilla, indent="\t", ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
		)
	print(f"Wrote vanilla translations and advancement aliases to {lang_dir}")
