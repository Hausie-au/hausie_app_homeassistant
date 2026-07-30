import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from hausie_addon.addon_server import _install_midea_ac_lan


def build_release(files: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class MideaInstallerTests(unittest.TestCase):
    def test_installs_release_and_replaces_existing_component(self) -> None:
        release = build_release(
            {
                "manifest.json": json.dumps(
                    {"domain": "midea_ac_lan", "version": "1.2.3"}
                ),
                "__init__.py": "NEW = True\n",
                "translations/en.json": "{}",
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = root / "custom_components" / "midea_ac_lan"
            existing.mkdir(parents=True)
            (existing / "old.py").write_text("old", encoding="utf-8")

            result = _install_midea_ac_lan(
                archive_bytes=release,
                config_root=root,
            )

            self.assertEqual(result["version"], "1.2.3")
            self.assertTrue((existing / "__init__.py").exists())
            self.assertFalse((existing / "old.py").exists())

    def test_rejects_archive_path_traversal(self) -> None:
        release = build_release(
            {
                "../escape.py": "unsafe",
                "manifest.json": json.dumps(
                    {"domain": "midea_ac_lan", "version": "1.2.3"}
                ),
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with self.assertRaisesRegex(RuntimeError, "unsafe archive path"):
                _install_midea_ac_lan(
                    archive_bytes=release,
                    config_root=root,
                )

            self.assertFalse((root / "escape.py").exists())

    def test_invalid_release_preserves_existing_component(self) -> None:
        release = build_release({"manifest.json": json.dumps({"domain": "wrong"})})
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = root / "custom_components" / "midea_ac_lan"
            existing.mkdir(parents=True)
            original = existing / "__init__.py"
            original.write_text("ORIGINAL = True\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "valid midea_ac_lan component"):
                _install_midea_ac_lan(
                    archive_bytes=release,
                    config_root=root,
                )

            self.assertEqual(
                original.read_text(encoding="utf-8"),
                "ORIGINAL = True\n",
            )


if __name__ == "__main__":
    unittest.main()
