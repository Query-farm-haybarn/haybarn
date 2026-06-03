#!/usr/bin/env python3
"""Emit a leaf @haybarn/cli-* (or @haybarn/unittest-*) package.json into $STAGE.

Run from the npm publish workflow with these env vars set:
  STAGE     destination directory (already exists)
  PKG       full scoped package name, e.g. @haybarn/cli-linux-x64
  VERSION   npm semver, e.g. 1.5.2-rc7
  OS        one of: linux, darwin, win32
  CPU       one of: x64, arm64
  LIBC      one of: glibc, musl, '-'  (where '-' means omit the libc field)
  PRODUCT   optional; the product noun in the description (default "CLI").
            The unittest publish workflow passes "unittest binary".
  META_NAME optional; the meta-package this leaf belongs to (default
            "haybarn"). The unittest workflow passes "haybarn-unittest".

The leaf carries a single native binary in bin/. Platform-pinned via npm's
`os`/`cpu`/`libc` fields so npm installs only the leaf matching the runtime.
The PRODUCT/META_NAME defaults reproduce the CLI leaf byte-for-byte.
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
        host_os = os.environ["OS"]
        host_cpu = os.environ["CPU"]
        host_libc = os.environ["LIBC"]
    except KeyError as e:
        print(f"build_leaf: missing env var {e}", file=sys.stderr)
        return 2

    product = os.environ.get("PRODUCT", "CLI")
    meta_name = os.environ.get("META_NAME", "haybarn")

    desc = f"Haybarn {product} for {host_os}/{host_cpu}"
    if host_libc != "-":
        desc += f" ({host_libc})"
    desc += (
        f". Installed automatically by the `{meta_name}` meta-package; "
        "use that, not this leaf, in your dependencies."
    )

    spec = {
        "name": pkg,
        "version": version,
        "description": desc,
        "homepage": "https://github.com/Query-farm-haybarn/haybarn",
        "repository": {
            "type": "git",
            "url": "git+https://github.com/Query-farm-haybarn/haybarn.git",
        },
        "license": "MIT",
        "os": [host_os],
        "cpu": [host_cpu],
        "files": ["bin"],
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
