#!/usr/bin/env python3
"""Emit a leaf @haybarn/ext-<name>-h<M>-<m>-<p>-<os>-<arch> package.json
into $STAGE.

Mirrors haybarn/tools/npm/build_leaf.py from the engine repo's CLI
publish flow. Run from the deploy workflow with these env vars set:

  STAGE             destination directory (already exists)
  PKG               full scoped package name,
                    e.g. @haybarn/ext-waddle-h1-5-2-linux-x64
  VERSION           npm semver, e.g. 0.0.2
  EXTENSION         extension name, e.g. waddle
  HAYBARN_VERSION   haybarn patch this leaf targets, e.g. 1.5.2
  OS                one of: linux, darwin, win32
  CPU               one of: x64, arm64
  LIBC              one of: glibc, musl, '-'  ('-' means omit the libc field)
  HAYBARN_METADATA  path to the unsigned haybarn-metadata.json blob to
                    embed in the leaf's package.json top-level "haybarn"
                    object

The leaf carries a single .duckdb_extension binary in bin/. Platform-
pinned via npm's `os`/`cpu`/`libc` so npm installs only the matching leaf.

Trust on npm: the binary's existing RSA signature (verified by the
haybarn engine at dlopen) + npm's per-(name,version) immutability.
"""

import json
import os
import pathlib
import sys


def main() -> int:
    try:
        stage = pathlib.Path(os.environ["STAGE"])
        pkg = os.environ["PKG"]
        version = os.environ["VERSION"]
        extension = os.environ["EXTENSION"]
        haybarn_version = os.environ["HAYBARN_VERSION"]
        host_os = os.environ["OS"]
        host_cpu = os.environ["CPU"]
        host_libc = os.environ["LIBC"]
        metadata_path = pathlib.Path(os.environ["HAYBARN_METADATA"])
    except KeyError as e:
        print(f"npm_build_leaf: missing env var {e}", file=sys.stderr)
        return 2

    if not metadata_path.is_file():
        print(f"npm_build_leaf: HAYBARN_METADATA {metadata_path} not found",
              file=sys.stderr)
        return 2

    metadata_blob = json.loads(metadata_path.read_text())

    desc = (
        f"Haybarn extension {extension!r} for {host_os}/{host_cpu}"
    )
    if host_libc != "-":
        desc += f" ({host_libc})"
    desc += (
        f". Built against haybarn {haybarn_version}. Installed automatically "
        f"by the @haybarn/ext-{extension}-h"
        f"{haybarn_version.replace('.', '-')} meta-package; "
        "use that, not this leaf, in your dependencies."
    )

    spec = {
        "name": pkg,
        "version": version,
        "description": desc,
        "homepage": "https://github.com/Query-farm-haybarn/haybarn-community-extensions",
        "repository": {
            "type": "git",
            "url": "git+https://github.com/Query-farm-haybarn/haybarn-community-extensions.git",
        },
        "license": "MIT",
        "os": [host_os],
        "cpu": [host_cpu],
        # bin/ contains the .duckdb_extension(.gz). Haybarn engine
        # discovery (Phase 3 patch) scans for this dir + the metadata
        # blob to validate.
        "files": ["bin", "haybarn-metadata.json"],
        # Top-level "haybarn" object — npm preserves arbitrary fields
        # and exposes them via `npm view`. This is the discovery
        # validation gate; without this block, the engine-side scan
        # ignores the directory.
        "haybarn": metadata_blob,
        "publishConfig": {"access": "public"},
    }
    if host_libc != "-":
        spec["libc"] = [host_libc]

    out = stage / "package.json"
    out.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
