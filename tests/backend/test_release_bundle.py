import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath

from scripts.create_source_bundle import create_source_bundle, should_include


class TestSourceBundleSafety(unittest.TestCase):
    def test_excludes_environment_file_but_keeps_example(self):
        self.assertFalse(should_include(PurePosixPath(".env")))
        self.assertFalse(should_include(PurePosixPath(".env.production")))
        self.assertTrue(should_include(PurePosixPath(".env.example")))

    def test_excludes_git_and_virtual_environment(self):
        self.assertFalse(should_include(Path(".git/config")))
        self.assertFalse(should_include(Path(".venv/Lib/site-packages/pkg.py")))
        self.assertFalse(should_include(Path("client/.dart_tool/package_config.json")))

    def test_excludes_signing_material_and_local_databases(self):
        self.assertFalse(should_include(Path("client/android/key.properties")))
        self.assertFalse(should_include(Path("client/android/app/release.jks")))
        self.assertFalse(should_include(Path("data/stickers.sqlite3")))


    def test_created_bundle_omits_secrets_and_local_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "project"
            (root / "backend").mkdir(parents=True)
            (root / ".git").mkdir()
            (root / ".venv" / "Scripts").mkdir(parents=True)
            (root / "client" / "android").mkdir(parents=True)
            (root / "backend" / "main.py").write_text("app = None", encoding="utf-8")
            (root / ".env").write_text("SECRET=do-not-ship", encoding="utf-8")
            (root / ".env.example").write_text("SECRET=", encoding="utf-8")
            (root / ".git" / "config").write_text("git metadata", encoding="utf-8")
            (root / ".venv" / "Scripts" / "python.exe").write_bytes(b"binary")
            (root / "client" / "android" / "key.properties").write_text("storePassword=secret", encoding="utf-8")
            bundle = parent / "project-safe.zip"

            count, _ = create_source_bundle(root, bundle)
            with zipfile.ZipFile(bundle) as archive:
                names = set(archive.namelist())

        self.assertEqual(count, 2)
        self.assertIn("project/backend/main.py", names)
        self.assertIn("project/.env.example", names)
        self.assertFalse(any(name.endswith("/.env") for name in names))
        self.assertFalse(any("/.git/" in name for name in names))
        self.assertFalse(any("/.venv/" in name for name in names))
        self.assertFalse(any(name.endswith("key.properties") for name in names))

    def test_keeps_source_code_and_required_project_metadata(self):
        self.assertTrue(should_include(Path("backend/main.py")))
        self.assertTrue(should_include(Path("client/lib/main.dart")))
        self.assertTrue(should_include(Path("requirements.txt")))
        self.assertTrue(should_include(Path(".gitignore")))


if __name__ == "__main__":
    unittest.main()
