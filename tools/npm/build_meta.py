#!/usr/bin/env python3
"""Emit the haybarn meta-package's package.json into $STAGE.

Run from the npm publish workflow with:
  STAGE        destination directory (already exists)
  VERSION      npm semver, e.g. 1.5.2-rc7
  PRESENT_ZIPS comma-separated list of release-asset zip basenames that
               actually exist in this release (used to decide which
               optional dependencies to declare — we drop leaves that
               weren't built)

The meta has one bin entry (the shim) and platform leaves listed under
optionalDependencies. Order matters for npm install-time platform
selection — we list them grouped by OS, x64 before arm64, and musl
after glibc.
"""

import json
import os
import pathlib
import sys


# zip basename → (leaf-slug, npm-os, npm-cpu, libc-or-'-')
LEAVES = [
    ("haybarn_cli-linux-amd64.zip",       "cli-linux-x64"),
    ("haybarn_cli-linux-arm64.zip",       "cli-linux-arm64"),
    ("haybarn_cli-linux-amd64-musl.zip",  "cli-linux-x64-musl"),
    ("haybarn_cli-linux-arm64-musl.zip",  "cli-linux-arm64-musl"),
    ("haybarn_cli-osx-amd64.zip",         "cli-darwin-x64"),
    ("haybarn_cli-osx-arm64.zip",         "cli-darwin-arm64"),
    ("haybarn_cli-windows-amd64.zip",     "cli-win32-x64"),
]


def main() -> int:
    try:
        stage = pathlib.Path(os.environ["STAGE"])
        version = os.environ["VERSION"]
        present = set(os.environ.get("PRESENT_ZIPS", "").split(","))
    except KeyError as e:
        print(f"build_meta: missing env var {e}", file=sys.stderr)
        return 2

    present.discard("")
    optional = {}
    for zip_name, slug in LEAVES:
        if zip_name in present:
            optional[f"@haybarn/{slug}"] = version

    spec = {
        "name": "haybarn",
        "version": version,
        "description": (
            "Haybarn — an independent derived distribution of DuckDB. "
            "Run via `npx haybarn`. Published by Query Farm LLC."
        ),
        "homepage": "https://github.com/Query-farm-haybarn/haybarn",
        "repository": {
            "type": "git",
            "url": "git+https://github.com/Query-farm-haybarn/haybarn.git",
        },
        "license": "MIT",
        "bin": {"haybarn": "haybarn.cjs"},
        "files": ["haybarn.cjs", "README.md", "LICENSE"],
        "engines": {"node": ">=18"},
        "keywords": ["haybarn", "duckdb", "cli", "olap", "sql"],
        "optionalDependencies": optional,
        "publishConfig": {"access": "public"},
    }

    out = stage / "package.json"
    out.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
