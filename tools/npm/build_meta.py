#!/usr/bin/env python3
"""Emit a meta-package's package.json into $STAGE (haybarn or haybarn-unittest).

Run from the npm publish workflow with:
  STAGE        destination directory (already exists)
  VERSION      npm semver, e.g. 1.5.2-rc7
  PRESENT_ZIPS comma-separated list of release-asset zip basenames that
               actually exist in this release (used to decide which
               optional dependencies to declare — we drop leaves that
               weren't built)

Optional family knobs (defaults reproduce the `haybarn` CLI meta byte-for-byte):
  META_NAME    package name (default "haybarn")
  BIN_NAME     the bin command name (default "haybarn")
  SHIM_FILE    launcher shim filename (default "haybarn.cjs")
  ZIP_PREFIX   release-zip basename prefix (default "haybarn_cli-")
  LEAF_PREFIX  leaf-slug prefix (default "cli-")
  DESCRIPTION  package description (default the CLI blurb)
  KEYWORDS     comma-separated keywords (default "haybarn,duckdb,cli,olap,sql")

The meta has one bin entry (the shim) and platform leaves listed under
optionalDependencies. Order matters for npm install-time platform
selection — we list them grouped by OS, x64 before arm64, and musl
after glibc.
"""

import json
import os
import pathlib
import sys


# (release-zip platform suffix, leaf-slug platform suffix). The family prefixes
# (ZIP_PREFIX / LEAF_PREFIX) are prepended below — only the prefixes differ
# between the CLI and unittest families; the platform fan-out is identical.
PLATFORMS = [
    ("linux-amd64",       "linux-x64"),
    ("linux-arm64",       "linux-arm64"),
    ("linux-amd64-musl",  "linux-x64-musl"),
    ("linux-arm64-musl",  "linux-arm64-musl"),
    ("osx-amd64",         "darwin-x64"),
    ("osx-arm64",         "darwin-arm64"),
    ("windows-amd64",     "win32-x64"),
]


def main() -> int:
    try:
        stage = pathlib.Path(os.environ["STAGE"])
        version = os.environ["VERSION"]
        present = set(os.environ.get("PRESENT_ZIPS", "").split(","))
    except KeyError as e:
        print(f"build_meta: missing env var {e}", file=sys.stderr)
        return 2

    meta_name = os.environ.get("META_NAME", "haybarn")
    bin_name = os.environ.get("BIN_NAME", "haybarn")
    shim_file = os.environ.get("SHIM_FILE", "haybarn.cjs")
    zip_prefix = os.environ.get("ZIP_PREFIX", "haybarn_cli-")
    leaf_prefix = os.environ.get("LEAF_PREFIX", "cli-")
    description = os.environ.get(
        "DESCRIPTION",
        "Haybarn — an independent derived distribution of DuckDB. "
        "Run via `npx haybarn`. Published by Query Farm LLC.",
    )
    keywords = os.environ.get("KEYWORDS", "haybarn,duckdb,cli,olap,sql").split(",")

    present.discard("")
    optional = {}
    for zip_plat, slug_plat in PLATFORMS:
        zip_name = f"{zip_prefix}{zip_plat}.zip"
        if zip_name in present:
            optional[f"@haybarn/{leaf_prefix}{slug_plat}"] = version

    spec = {
        "name": meta_name,
        "version": version,
        "description": description,
        "homepage": "https://github.com/Query-farm-haybarn/haybarn",
        "repository": {
            "type": "git",
            "url": "git+https://github.com/Query-farm-haybarn/haybarn.git",
        },
        "license": "MIT",
        "bin": {bin_name: shim_file},
        "files": [shim_file, "README.md", "LICENSE"],
        "engines": {"node": ">=18"},
        "keywords": keywords,
        "optionalDependencies": optional,
        "publishConfig": {"access": "public"},
    }

    out = stage / "package.json"
    out.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
