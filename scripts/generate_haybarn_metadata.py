#!/usr/bin/env python3
"""Generate the haybarn-metadata.json blob shipped inside pip wheels and
npm packages.

Per ideas/extension-version-pinning.md, this blob is *informational and
unsigned* on pip/npm — trust is provided by registry immutability + the
engine's existing RSA signature on the binary + the lockfile's sha256.
The blob's job is to carry the extension commit sha and other identity
fields so consumers can inspect them via `pip show` / `npm view` and so
the lockfile sync tool can verify the right build is installed.

The R2 manifest.json shipped next to the binary on R2 is a superset of
this shape — see r2_build_manifest.py.

Usage:
    python3 generate_haybarn_metadata.py \\
        --extension waddle \\
        --ext-commit 5df4b9401665d23ec5f9dd08f248df08c9075232 \\
        --haybarn-version 1.5.2 \\
        --ext-version-label 0.0.2 \\
        --sha256 9f2c... \\
        --built-at 2026-05-17T12:42:11Z \\
        --out haybarn-metadata.json

Produces:
    {
      "ext_commit":        "5df4b94…",
      "haybarn_version":   "1.5.2",
      "ext_version_label": "0.0.2",
      "sha256":            "9f2c…",
      "built_at":          "2026-05-17T12:42:11Z"
    }
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


def build_metadata(
    extension: str,
    ext_commit: str,
    haybarn_version: str,
    ext_version_label: str,
    sha256: str,
    built_at: str,
) -> dict:
    return {
        # `extension` isn't strictly necessary (the package name carries it)
        # but it's a tiny field and lets the blob be self-describing for
        # tools that inspect it without the wheel/package context.
        "extension":         extension,
        "ext_commit":        ext_commit,
        "haybarn_version":   haybarn_version,
        # Empty string when the extension has no semver tag — lockfile sync
        # uses ext_commit as the identity in that case.
        "ext_version_label": ext_version_label,
        "sha256":            sha256,
        "built_at":          built_at,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--extension",         required=True)
    ap.add_argument("--ext-commit",        required=True,
                    help="40-char SHA1 of the extension source commit")
    ap.add_argument("--haybarn-version",   required=True,
                    help="haybarn engine version this build targets, e.g. 1.5.2")
    ap.add_argument("--ext-version-label", default="",
                    help="extension's own semver if it has one, else empty")
    ap.add_argument("--sha256",            required=True,
                    help="sha256 of the .duckdb_extension binary (uncompressed)")
    ap.add_argument("--built-at",          required=True,
                    help="ISO-8601 UTC build timestamp")
    ap.add_argument("--out",               required=True, type=pathlib.Path,
                    help="output path for haybarn-metadata.json")
    args = ap.parse_args(argv)

    if len(args.ext_commit) != 40:
        print(f"generate_haybarn_metadata: --ext-commit must be a 40-char SHA1, "
              f"got {len(args.ext_commit)} chars", file=sys.stderr)
        return 2

    blob = build_metadata(
        extension=args.extension,
        ext_commit=args.ext_commit,
        haybarn_version=args.haybarn_version,
        ext_version_label=args.ext_version_label,
        sha256=args.sha256,
        built_at=args.built_at,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(blob, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
