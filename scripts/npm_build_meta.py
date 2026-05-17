#!/usr/bin/env python3
"""Emit the @haybarn/ext-<name>-h<M>-<m>-<p> meta-package's package.json
into $STAGE.

Mirrors haybarn/tools/npm/build_meta.py from the engine repo. Run from
the deploy workflow with:

  STAGE             destination directory (already exists)
  PKG               meta package name, e.g. @haybarn/ext-waddle-h1-5-2
  VERSION           npm semver, e.g. 0.0.2
  EXTENSION         extension name, e.g. waddle
  HAYBARN_VERSION   haybarn patch this meta targets, e.g. 1.5.2
  HAYBARN_METADATA  path to the unsigned haybarn-metadata.json blob
                    (embedded as the top-level "haybarn" object)
  PRESENT_LEAVES    comma-separated list of leaf-package basenames that
                    actually got built this run (used to filter
                    optionalDependencies — leaves whose build failed get
                    dropped rather than declared with a missing version).
                    Each entry is just the leaf slug, e.g.
                    "linux-x64,linux-arm64,darwin-arm64".

The meta declares per-platform leaves under optionalDependencies, plus
an exact peerDependency on haybarn matching the package-name suffix.
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
        metadata_path = pathlib.Path(os.environ["HAYBARN_METADATA"])
        present = os.environ.get("PRESENT_LEAVES", "")
    except KeyError as e:
        print(f"npm_build_meta: missing env var {e}", file=sys.stderr)
        return 2

    if not metadata_path.is_file():
        print(f"npm_build_meta: HAYBARN_METADATA {metadata_path} not found",
              file=sys.stderr)
        return 2

    metadata_blob = json.loads(metadata_path.read_text())

    present_leaves = [p.strip() for p in present.split(",") if p.strip()]
    if not present_leaves:
        print("npm_build_meta: no PRESENT_LEAVES — meta with no leaves would "
              "be useless. Aborting rather than publishing a broken meta.",
              file=sys.stderr)
        return 2

    optional = {f"{pkg}-{slug}": version for slug in present_leaves}

    # See npm_build_leaf.py — repository URL has to match the source
    # repo from the npm provenance attestation.
    repo_slug = os.environ.get("GITHUB_REPOSITORY",
                               "Query-farm-haybarn/haybarn-community-extensions")
    repo_url = f"https://github.com/{repo_slug}"

    spec = {
        "name": pkg,
        "version": version,
        "description": (
            f"Haybarn extension {extension!r} — built against haybarn "
            f"{haybarn_version}. Install this meta-package; npm will pull "
            "only the binary leaf matching your platform."
        ),
        "homepage": repo_url,
        "repository": {
            "type": "git",
            "url": f"git+{repo_url}.git",
        },
        "license": "MIT",
        "keywords": ["haybarn", "duckdb", "extension", extension],
        # peerDependencies intentionally omitted for now. The `haybarn`
        # package on npm only has pre-release versions (1.5.2-rcN); a
        # strict pin to "1.5.2" would warn against an unsatisfiable
        # version on every install. The package-name suffix
        # `-h<M>-<m>-<p>` still encodes the haybarn ABI; the engine
        # verifies the RSA signature on load.
        "optionalDependencies": optional,
        "haybarn": metadata_blob,
        "publishConfig": {"access": "public"},
    }

    out = stage / "package.json"
    out.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
