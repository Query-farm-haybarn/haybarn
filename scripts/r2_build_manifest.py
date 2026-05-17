#!/usr/bin/env python3
"""Build the per-build R2 manifest.json that ships alongside an extension
binary on R2.

This is a *superset* of haybarn-metadata.json (the unsigned blob shipped
inside pip wheels / npm packages). The R2 manifest adds:

  - platform / object — the per-platform R2 layout context
  - haybarn_engine_commit — the engine SHA the binary was built against
  - signed_by — forward hook for trust-store evolution
  - channels — which distribution channels this build was shipped to
  - previous_commit — hash-chain link to the build this one supersedes
                       (read from the existing current.json on R2 if any)

The output is written to a local path; the workflow GPG-signs it
separately with `gpg --detach-sign --armor` to produce manifest.json.asc.

R2 is mutable storage, which is why the manifest is signed: tamper-
evidence has to be provided by us, not the storage provider. pip and npm
don't need this layer (they enforce per-(name,version) immutability at
the registry level — see ideas/extension-version-pinning.md for the full
trust-path comparison).

Usage:
    python3 r2_build_manifest.py \\
        --extension waddle \\
        --duckdb-version v1.5.2 \\
        --platform linux_amd64 \\
        --ext-commit 5df4b94... \\
        --ext-version-label 0.0.2 \\
        --sha256 9f2c... \\
        --object waddle.duckdb_extension.gz \\
        --built-at 2026-05-17T12:42:11Z \\
        --haybarn-engine-commit 111577c34c \\
        --signed-by haybarn-extension-signing-2026 \\
        --channels r2-community,pypi,npm \\
        --previous-commit 8e1a72b... \\
        --out manifest.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


def build_manifest(
    extension: str,
    duckdb_version: str,
    platform: str,
    ext_commit: str,
    ext_version_label: str,
    sha256: str,
    obj: str,
    built_at: str,
    haybarn_engine_commit: str,
    signed_by: str,
    channels: list[str],
    previous_commit: str,
) -> dict:
    return {
        "extension":             extension,
        "duckdb_version":        duckdb_version,
        "platform":              platform,
        "ext_commit":            ext_commit,
        "version_label":         ext_version_label,
        "sha256":                sha256,
        "object":                obj,
        "built_at":              built_at,
        "haybarn_engine_commit": haybarn_engine_commit,
        "signed_by":             signed_by,
        "channels":              channels,
        # Empty string is fine — first build of an extension has no prior.
        # Consumers walking the chain stop when they see "".
        "previous_commit":       previous_commit,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--extension",             required=True)
    ap.add_argument("--duckdb-version",        required=True,
                    help="e.g. v1.5.2")
    ap.add_argument("--platform",              required=True,
                    help="e.g. linux_amd64, osx_arm64, windows_amd64")
    ap.add_argument("--ext-commit",            required=True)
    ap.add_argument("--ext-version-label",     default="")
    ap.add_argument("--sha256",                required=True)
    ap.add_argument("--object",                required=True,
                    dest="obj",
                    help="binary filename, e.g. waddle.duckdb_extension.gz")
    ap.add_argument("--built-at",              required=True)
    ap.add_argument("--haybarn-engine-commit", required=True)
    ap.add_argument("--signed-by",             required=True,
                    help="signing-identity name (forward hook for trust-store)")
    ap.add_argument("--channels",              required=True,
                    help="comma-separated channels this build is published to "
                         "(e.g. r2-community,pypi,npm)")
    ap.add_argument("--previous-commit",       default="",
                    help="ext_commit of the build this supersedes, "
                         "or empty if first build")
    ap.add_argument("--out",                   required=True,
                    type=pathlib.Path)
    args = ap.parse_args(argv)

    if len(args.ext_commit) != 40:
        print(f"r2_build_manifest: --ext-commit must be 40-char SHA1",
              file=sys.stderr)
        return 2
    if args.previous_commit and len(args.previous_commit) != 40:
        print(f"r2_build_manifest: --previous-commit must be 40-char SHA1 "
              f"or empty, got {len(args.previous_commit)} chars",
              file=sys.stderr)
        return 2

    channels = [c.strip() for c in args.channels.split(",") if c.strip()]

    manifest = build_manifest(
        extension=args.extension,
        duckdb_version=args.duckdb_version,
        platform=args.platform,
        ext_commit=args.ext_commit,
        ext_version_label=args.ext_version_label,
        sha256=args.sha256,
        obj=args.obj,
        built_at=args.built_at,
        haybarn_engine_commit=args.haybarn_engine_commit,
        signed_by=args.signed_by,
        channels=channels,
        previous_commit=args.previous_commit,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
