"""Resource-cache isolation and malformed-input regression checks."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from generate_mc_resources import normalize_models, reusable_output, validate_client_version


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

    def test_new_texture_reference_preserves_sprite_and_rejects_unknown_fields(self):
        models = self.root / "models/block"
        models.mkdir(parents=True)
        file = models / "glass.json"
        file.write_text(json.dumps({"textures": {"all": {"sprite": "minecraft:block/glass", "force_translucent": True}}}))
        normalize_models(self.root)
        self.assertEqual(json.loads(file.read_text())["textures"]["all"], "minecraft:block/glass")
        file.write_text(json.dumps({"textures": {"all": {"sprite": "minecraft:block/glass", "new_semantics": True}}}))
        with self.assertRaises(ValueError):
            normalize_models(self.root)


if __name__ == "__main__":
    unittest.main()
