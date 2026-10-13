"""Run MinecraftImageGenerator once per Gradle resource build, then publish validated assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path

from mc_metadata import resolve_jar, write_vanilla_lang

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts/mc-atlas/toolchain.json"
REQUIRED_ICONS = ("barrier", "diamond_sword", "diamond_pickaxe", "clock", "experience_bottle",
                  "nether_star", "player_head", "shield", "chest", "red_bed", "stone")


def fingerprint(version: str, jar: Path) -> str:
    digest = hashlib.sha256(version.encode())
    inputs = [ROOT / "scripts/generate_mc_resources.py", ROOT / "scripts/mc_metadata.py",
              ROOT / "scripts/prepare_mc_tooling.py", *sorted((ROOT / "scripts/mc-atlas").glob("*"))]
    for path in inputs:
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    with jar.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reusable_output(output: Path, version: str, expected: str) -> bool:
    try:
        manifest = json.loads((output / "manifest.json").read_text())
        if manifest["minecraftVersion"] != version or manifest["pipelineFingerprint"] != expected:
            return False
        files = manifest["files"]
        if not files:
            return False
        for relative, checksum in files.items():
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                return False
            if hashlib.sha256((output / path).read_bytes()).hexdigest() != checksum:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def validate_client_version(jar: Path, version: str) -> None:
    with zipfile.ZipFile(jar) as source:
        actual = json.loads(source.read("version.json")).get("id")
    if actual != version:
        raise ValueError(f"Client JAR version {actual} does not match requested version {version}")


def publish(staging: Path, output: Path) -> None:
    previous = output.with_name(output.name + ".previous")
    if previous.exists():
        shutil.rmtree(previous)
    if output.exists():
        output.rename(previous)
    try:
        staging.rename(output)
    except OSError:
        if previous.exists():
            previous.rename(output)
        raise
    if previous.exists():
        shutil.rmtree(previous)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) != 24:
        raise ValueError(f"Invalid PNG: {path}")
    return struct.unpack(">II", header[16:24])


def normalize_models(assets: Path) -> None:
    # 26.3 allows {sprite, force_translucent} texture references. The pinned
    # renderer expects strings; keep the sprite and its original PNG alpha.
    for path in sorted((assets / "models").rglob("*.json")):
        model = json.loads(path.read_text())
        changed = False
        for key, value in model.get("textures", {}).items():
            if isinstance(value, dict):
                if set(value) - {"sprite", "force_translucent"} or not isinstance(value.get("sprite"), str):
                    raise ValueError(f"Unsupported model texture reference in {path}: {value}")
                model["textures"][key] = value["sprite"]
                changed = True
        if changed:
            write_json(path, model)


def install_texture_aliases(assets: Path) -> None:
    aliases = json.loads((ROOT / "scripts/mc-atlas/texture-aliases.json").read_text())
    for legacy, current in aliases.items():
        source = assets / "textures" / f"{current}.png"
        dest = assets / "textures" / f"{legacy}.png"
        if not dest.exists() and source.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)


def build_index(raw: Path, output: Path, lock: dict, version: str) -> dict:
    entries = json.loads((raw / "json/atlas_coordinates.json").read_text())
    pages = sorted({entry["page"] for entry in entries})
    if pages != list(range(len(pages))) or not entries:
        raise ValueError("Atlas pages are empty or non-contiguous")
    atlases = []
    (output / "atlas").mkdir(parents=True)
    for page in pages:
        source = raw / f"spritesheets/minecraft_texture_atlas-{page}.png"
        width, height = png_size(source)
        if width > lock["atlasWidth"] or height > lock["atlasWidth"]:
            raise ValueError(f"Oversized atlas: {source}")
        name = f"items-{page}.png"
        shutil.copyfile(source, output / "atlas" / name)
        atlases.append({"file": f"atlas/{name}", "width": width, "height": height})
    sprites = {}
    for entry in entries:
        name, page, x, y, size = (entry[k] for k in ("name", "page", "x", "y", "size"))
        if size != lock["tileSize"] or min(x, y) < 0:
            raise ValueError(f"Invalid sprite: {entry}")
        if x + size > atlases[page]["width"] or y + size > atlases[page]["height"]:
            raise ValueError(f"Sprite outside atlas: {entry}")
        identifier = name if ":" in name else f"minecraft:{name}"
        if identifier in sprites:
            raise ValueError(f"Duplicate sprite: {identifier}")
        sprites[identifier] = {"atlas": page, "x": x, "y": y, "size": size}
    # Resolve aliases at build time; browsers never probe guessed PNG paths.
    aliases = json.loads((ROOT / "scripts/mc-atlas/aliases.json").read_text())
    for identifier in list(sprites):
        if identifier.endswith("_spawn_egg"):
            aliases.setdefault(identifier.removesuffix("_spawn_egg"), identifier)
        if identifier.endswith(("_sign", "_hanging_sign")) and "_wall_" not in identifier:
            suffix = "_hanging_sign" if identifier.endswith("_hanging_sign") else "_sign"
            aliases.setdefault(identifier.removesuffix(suffix) + "_wall" + suffix, identifier)
        if identifier.endswith(("_head", "_skull")):
            namespace, name = identifier.split(":", 1)
            aliases.setdefault(f"{namespace}:{name.replace('_head', '_wall_head').replace('_skull', '_wall_skull')}", identifier)
    for alias, target in aliases.items():
        if target not in sprites:
            raise ValueError(f"Missing alias target: {alias} -> {target}")
        sprites[alias] = sprites[target]
    missing = [name for name in REQUIRED_ICONS if f"minecraft:{name}" not in sprites]
    if missing:
        raise ValueError(f"Required icons missing: {missing}")
    index = {"schemaVersion": 1, "minecraftVersion": version, "atlases": atlases, "sprites": sprites}
    write_json(output / "icons.json", index)
    imports = [f"import atlas{i} from './{atlas['file']}?url';" for i, atlas in enumerate(atlases)]
    (output / "atlas.ts").write_text("\n".join(imports) + "\nexport default [" +
                                     ", ".join(f"atlas{i}" for i in pages) + "];\n")
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--tooling", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--jar")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    tooling, output, work = args.tooling.resolve(), args.output.resolve(), args.work.resolve()
    lock = json.loads(CONFIG.read_text())
    if json.loads((tooling / "toolchain.json").read_text()) != lock:
        raise ValueError("Prepared toolchain does not match toolchain.json")
    jar_path = resolve_jar(args.version, args.jar)
    validate_client_version(jar_path, args.version)
    expected = fingerprint(args.version, jar_path)
    if not args.force and reusable_output(output, args.version, expected):
        print(f"Reusing validated Minecraft {args.version} resources: {output}")
        return
    subprocess.run(["dotnet", "--version"], check=True)
    # Always recreate this version's extracted input when the task is invalidated.
    assets = work / "minecraft-assets"
    if assets.exists():
        shutil.rmtree(assets)
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(jar_path) as jar:
        prefix = "assets/minecraft/"
        for name in jar.namelist():
            if not name.startswith(prefix) or name.endswith("/"):
                continue
            relative = Path(name[len(prefix):])
            if ".." in relative.parts or relative.is_absolute():
                raise ValueError(f"Unsafe resource path: {name}")
            dest = assets / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(jar.read(name))
        write_vanilla_lang(jar, args.version, staging)
        wings = "assets/minecraft/textures/entity/equipment/wings/elytra.png"
        (staging / "elytra.png").write_bytes(jar.read(wings))
    normalize_models(assets)
    install_texture_aliases(assets)
    raw = work / "atlas-output"
    if raw.exists():
        shutil.rmtree(raw)
    command = ["java", "-Djava.awt.headless=true", f"-Dmc.workDir={work}", f"-Dmc.outputDir={raw}",
               f"-Dmc.rendererDir={tooling / 'renderer'}", f"-Dmc.tileSize={lock['tileSize']}",
               f"-Dmc.atlasWidth={lock['atlasWidth']}", "-cp", (tooling / "classpath.txt").read_text().strip(),
               "net.aerh.imagegenerator.tooling.minecraft.MinecraftAssetTool",
               "--render", "--spritesheet", "--no-clean", "--debug", f"--version={args.version}",
               f"--size={lock['tileSize']}"]
    env = os.environ.copy()
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    env["DOTNET_NOLOGO"] = "1"
    env["DOTNET_CLI_HOME"] = str(tooling / "dotnet-home")
    env["NUGET_PACKAGES"] = str(tooling / "nuget-cache")
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    index = build_index(raw, staging, lock, args.version)
    files = {str(path.relative_to(staging)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(staging.rglob("*")) if path.is_file()}
    write_json(staging / "manifest.json", {"minecraftVersion": args.version, "pipelineFingerprint": expected, "toolchain": lock,
               "spriteCount": len(index["sprites"]), "files": files})
    publish(staging, output)
    print(f"Published {len(index['sprites'])} icons in {len(index['atlases'])} atlases to {output}")


if __name__ == "__main__":
    main()
