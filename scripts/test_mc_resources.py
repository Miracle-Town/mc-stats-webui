"""Resource-cache isolation and malformed-input regression checks."""
import hashlib
import json
import shutil
import struct
import zlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from generate_mc_resources import build_index, reusable_output, validate_client_version
from convert_mc_atlases import convert_atlases, read_png_rgba, verify_pixels


def write_png(path, width, height, pixels, colour=6, filtered=None):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    channels = 4 if colour == 6 else 3
    rows = filtered if filtered is not None else b"".join(
        b"\0" + pixels[y * width * channels:(y + 1) * width * channels] for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0))
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
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_png_filter_vectors(self):
        expected = bytes(range(10, 170, 10))
        vectors = (
            (list(range(10, 90, 10)), list(range(90, 170, 10))),
            ([10, 20, 30, 40, 40, 40, 40, 40], [90, 100, 110, 120, 40, 40, 40, 40]),
            (list(range(10, 90, 10)), [80] * 8),
            ([10, 20, 30, 40, 45, 50, 55, 60], [85, 90, 95, 100, 60, 60, 60, 60]),
            ([10, 20, 30, 40, 40, 40, 40, 40], [80, 80, 80, 80, 40, 40, 40, 40]),
        )
        for filter_type, (first, second) in enumerate(vectors):
            with self.subTest(filter=filter_type):
                png = self.root / f"filter-{filter_type}.png"
                write_png(png, 2, 2, expected, filtered=bytes([filter_type] + first + [filter_type] + second))
                self.assertEqual(read_png_rgba(png), (2, 2, expected))

    def test_rgb_png_expands_to_opaque_rgba(self):
        png = self.root / "rgb.png"
        write_png(png, 2, 1, bytes([1, 2, 3, 4, 5, 6]), colour=2)
        self.assertEqual(read_png_rgba(png), (2, 1, bytes([1, 2, 3, 255, 4, 5, 6, 255])))

    def test_png_rejects_corrupt_data(self):
        png = self.root / "corrupt.png"
        write_png(png, 1, 1, bytes(4))
        data = bytearray(png.read_bytes())
        data[20] ^= 1
        png.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "checksum"):
            read_png_rgba(png)

    def test_first_and_numbered_pages_preserve_transparent_rgba(self):
        for tool in ("cwebp", "dwebp"):
            self.assertIsNotNone(shutil.which(tool), f"Install {tool} to test lossless WebP conversion")
        source, output = self.root / "input", self.root / "output"
        source.mkdir()
        # Includes invisible colour, partial alpha, and opaque pixels.
        pixels = bytes([17, 33, 55, 0, 255, 0, 200, 127, 1, 2, 3, 255, 0, 255, 0, 1])
        for name in ("minecraft_texture_atlas.png", "minecraft_texture_atlas-1.png"):
            write_png(source / name, 2, 2, pixels)
        convert_atlases(source, output, 100, 6)
        self.assertEqual(sorted(p.name for p in output.iterdir()), ["items-0.webp", "items-1.webp"])

    def test_verifier_rejects_changed_pixels_and_dimensions(self):
        original = self.root / "original.png"
        write_png(original, 1, 1, bytes([17, 33, 55, 0]))
        for width, pixels in ((1, bytes([18, 33, 55, 0])), (2, bytes(8))):
            changed = self.root / "changed.png"
            write_png(changed, width, 1, pixels)
            with self.assertRaisesRegex(ValueError, "changed"):
                verify_pixels(original, changed)



if __name__ == "__main__":
    unittest.main()
