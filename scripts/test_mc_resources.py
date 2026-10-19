"""Resource-cache isolation and malformed-input regression checks."""
import hashlib
import json
import shutil
import struct
import subprocess
import zlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from generate_mc_resources import build_index, reusable_output, validate_client_version

ROOT = Path(__file__).resolve().parents[1]


def write_png(path, width, height, pixels):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class ResourceCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def manifest(self, version="26.3", fingerprint="toolchain-a"):
        asset = self.root / "atlas.png"
        asset.write_bytes(b"atlas-content")
        data = {"minecraftVersion": version, "pipelineFingerprint": fingerprint,
                "files": {"atlas.png": hashlib.sha256(asset.read_bytes()).hexdigest()}}
        (self.root / "manifest.json").write_text(json.dumps(data))
        return data

    def test_version_and_toolchain_must_both_match(self):
        self.manifest()
        self.assertTrue(reusable_output(self.root, "26.3", "toolchain-a"))
        self.assertFalse(reusable_output(self.root, "26.2", "toolchain-a"))
        self.assertFalse(reusable_output(self.root, "26.3", "toolchain-b"))

    def test_modified_or_missing_asset_is_not_reused(self):
        self.manifest()
        (self.root / "atlas.png").write_bytes(b"corrupted")
        self.assertFalse(reusable_output(self.root, "26.3", "toolchain-a"))
        (self.root / "atlas.png").unlink()
        self.assertFalse(reusable_output(self.root, "26.3", "toolchain-a"))

    def test_manifest_cannot_reference_another_version_directory(self):
        data = self.manifest()
        data["files"] = {"../26.2/atlas.png": "anything"}
        (self.root / "manifest.json").write_text(json.dumps(data))
        self.assertFalse(reusable_output(self.root, "26.3", "toolchain-a"))

    def test_client_jar_must_match_requested_version(self):
        jar = self.root / "client.jar"
        with zipfile.ZipFile(jar, "w") as source:
            source.writestr("version.json", json.dumps({"id": "26.2"}))
        validate_client_version(jar, "26.2")
        with self.assertRaises(ValueError):
            validate_client_version(jar, "26.3")

    def test_upstream_atlas_filenames_and_coordinates(self):
        raw, output = self.root / "raw", self.root / "generated"
        (raw / "json").mkdir(parents=True)
        (raw / "spritesheets").mkdir()
        (output / "atlas").mkdir(parents=True)
        names = ["barrier", "diamond_sword", "diamond_pickaxe", "clock", "experience_bottle",
                 "nether_star", "player_head", "shield", "chest", "red_bed", "stone",
                 "potato", "carrot", "beetroot", "redstone"]
        entries = []
        for i, name in enumerate(names):
            page = i % 2
            atlas = "minecraft_texture_atlas.png" if page == 0 else "minecraft_texture_atlas-1.png"
            entries.append({"name": name, "page": page, "atlas": atlas, "x": 1, "y": 1, "size": 2})
        (raw / "json/atlas_coordinates.json").write_text(json.dumps(entries))
        for page, atlas in enumerate(("minecraft_texture_atlas.png", "minecraft_texture_atlas-1.png")):
            write_png(raw / "spritesheets" / atlas, 4, 4, bytes(64))
            (output / "atlas" / f"items-{page}.webp").write_bytes(b"RIFF\0\0\0\0WEBP")
        index = build_index(raw, output, {"tileSize": 2, "atlasWidth": 4}, "26.3")
        self.assertEqual(len(index["atlases"]), 2)
        self.assertEqual(index["sprites"]["minecraft:diamond_sword"]["atlas"], 1)
        self.assertEqual(index["sprites"]["minecraft:air"], index["sprites"]["minecraft:barrier"])
        entries[0]["atlas"] = "../escape.png"
        (raw / "json/atlas_coordinates.json").write_text(json.dumps(entries))
        with self.assertRaises(ValueError):
            build_index(raw, output, {"tileSize": 2, "atlasWidth": 4}, "26.3")


class WebpConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.classes = Path(cls.temp.name)
        subprocess.run(["javac", "-d", str(cls.classes), str(ROOT / "scripts/mc-atlas/WebpConverter.java")], check=True)
        probe = cls.classes / "VerifyPixels.java"
        probe.write_text('import java.nio.file.Path; class VerifyPixels { public static void main(String[] a) throws Exception { WebpConverter.verifyPixels(Path.of(a[0]), Path.of(a[1])); } }')
        subprocess.run(["javac", "-cp", str(cls.classes), "-d", str(cls.classes), str(probe)], check=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_first_and_numbered_pages_preserve_transparent_rgba(self):
        for tool in ("cwebp", "dwebp"):
            self.assertIsNotNone(shutil.which(tool), f"Install {tool} to test lossless WebP conversion")
        source, output = self.root / "input", self.root / "output"
        source.mkdir()
        # Includes invisible colour, partial alpha, and opaque pixels.
        pixels = bytes([17, 33, 55, 0, 255, 0, 200, 127, 1, 2, 3, 255, 0, 255, 0, 1])
        for name in ("minecraft_texture_atlas.png", "minecraft_texture_atlas-1.png"):
            write_png(source / name, 2, 2, pixels)
        subprocess.run(["java", "-Djava.awt.headless=true", "-cp", str(self.classes), "WebpConverter",
                        str(source), str(output), "100", "6"], check=True)
        self.assertEqual(sorted(p.name for p in output.iterdir()), ["items-0.webp", "items-1.webp"])

    def test_verifier_rejects_changed_pixels_and_dimensions(self):
        original = self.root / "original.png"
        write_png(original, 1, 1, bytes([17, 33, 55, 0]))
        for width, pixels in ((1, bytes([18, 33, 55, 0])), (2, bytes(8))):
            changed = self.root / "changed.png"
            write_png(changed, width, 1, pixels)
            result = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", str(self.classes),
                                     "VerifyPixels", str(original), str(changed)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("changed", result.stderr)


if __name__ == "__main__":
    unittest.main()
