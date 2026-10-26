#!/usr/bin/env python3

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/ci/stage_prebuilt.sh"


class StagePrebuiltTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.platforms = (
            "linux-amd64",
            "linux-arm64",
            "linux-amd64-musl",
            "linux-arm64-musl",
            "osx-arm64",
            "windows-amd64",
            "windows-amd64-mingw",
        )
        for platform in self.platforms:
            self.archive(platform).write_bytes(b"archive")
        self.log = self.root / "uploads.jsonl"
        aws = self.root / "aws"
        aws.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "with open(os.environ['UPLOAD_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if os.environ.get('FAIL_UPLOAD') == Path(sys.argv[-2]).name:\n"
            "    sys.exit(1)\n"
        )
        aws.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
            "UPLOAD_LOG": str(self.log),
            "FAIL_UPLOAD": "",
            "GITHUB_SHA": "74a0e8098851234567890123456789012345678901",
            "OVERRIDE_GIT_DESCRIBE": "v2.0.0",
            "R2_BUCKET": "test-staging",
        }
        self.prefix = "s3://test-staging/staging/74a0e80988"

    def archive(self, platform):
        return self.artifacts / f"duckdb-static-libs-{platform}.tar.gz"

    def run_staging(self):
        return subprocess.run(["bash", str(SCRIPT)], cwd=self.root, env=self.env, capture_output=True, text=True)

    def uploads(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_stages_every_platform_under_consumer_names_before_the_pointer(self):
        result = self.run_staging()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        uploads = self.uploads()
        expected = {
            f"{self.prefix}/v2.0.0/duckdb/duckdb/github_release/duckdb-static-libs-{platform}.tar.gz"
            for platform in (*self.platforms[:-1], "windows-mingw")
        }
        self.assertEqual({upload[-1] for upload in uploads[:-1]}, expected)
        self.assertEqual(len(uploads), 8)
        self.assertEqual(uploads[-2][-2], "artifacts/duckdb-static-libs-windows-amd64-mingw.tar.gz")
        self.assertEqual(uploads[-1][-1], f"{self.prefix}/latest_alpha_version.txt")
        self.assertEqual((self.root / "latest_alpha_version.txt").read_text(), "v2.0.0\n")

    def test_missing_platform_prevents_all_uploads_even_with_an_extra_archive(self):
        for platform in self.platforms:
            with self.subTest(platform=platform):
                self.archive(platform).unlink()
                self.archive("unrelated").write_bytes(b"archive")
                result = self.run_staging()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(str(self.archive(platform).relative_to(self.root)), result.stdout)
                self.assertEqual(self.uploads(), [])
                self.archive(platform).write_bytes(b"archive")

    def test_empty_archive_prevents_all_uploads(self):
        self.archive("windows-amd64-mingw").write_bytes(b"")
        self.assertNotEqual(self.run_staging().returncode, 0)
        self.assertEqual(self.uploads(), [])

    def test_failed_upload_does_not_publish_pointer(self):
        self.env["FAIL_UPLOAD"] = self.archive("windows-amd64-mingw").name
        self.assertNotEqual(self.run_staging().returncode, 0)
        self.assertEqual(len(self.uploads()), 7)
        self.assertFalse((self.root / "latest_alpha_version.txt").exists())

    def test_invalid_version_prevents_all_uploads(self):
        self.env["OVERRIDE_GIT_DESCRIBE"] = "main"
        self.assertNotEqual(self.run_staging().returncode, 0)
        self.assertEqual(self.uploads(), [])


if __name__ == "__main__":
    unittest.main()
