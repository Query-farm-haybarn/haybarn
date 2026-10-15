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


HAYBARN_SITE_URL = "https://query.farm/products/haybarn/"
HAYBARN_ICON_URL = (
    "https://raw.githubusercontent.com/Query-farm-haybarn/.github/"
    "haybarn/profile/assets/haybarn-icon.png"
)
QUERY_FARM_WORDMARK_URL = "https://query.farm/media-kit/logo/wordmark-light.png"


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
        "homepage": "https://query.farm/products/haybarn/",
        "repository": {
            "type": "git",
            "url": "git+https://github.com/Query-farm-haybarn/haybarn.git",
        },
        "license": "MIT",
        "os": [host_os],
        "cpu": [host_cpu],
        "files": ["bin", "README.md"],
        "publishConfig": {"access": "public"},
    }
    if host_libc != "-":
        spec["libc"] = [host_libc]

    out = stage / "package.json"
    out.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {out}")

    plat = f"{host_os}/{host_cpu}" + (f" ({host_libc})" if host_libc != "-" else "")
    meta_link = f"[`{meta_name}`](https://www.npmjs.com/package/{meta_name})"
    readme = "\n".join([
        '<p align="center">',
        f'  <a href="{HAYBARN_SITE_URL}"><img src="{HAYBARN_ICON_URL}" '
        'alt="Haybarn" width="96" height="96"></a>',
        '</p>',
        '<p align="center">',
        f'  <a href="https://query.farm"><img src="{QUERY_FARM_WORDMARK_URL}" '
        'alt="Query.Farm" height="28"></a>',
        '</p>',
        "",
        f"# `{pkg}`",
        "",
        f"> **Part of {meta_link}** — install that package, not this one.",
        "",
        f"**[Haybarn]({HAYBARN_SITE_URL})** is a derived distribution of DuckDB "
        "from [Query.Farm](https://query.farm): the same SQL, APIs and database "
        "files, with signed releases, rebuilt and signed extensions, engine "
        "improvements, and supply-chain review built in.",
        "",
        f"This is the Haybarn {product} binary for **{plat}**. npm installs it "
        f"automatically as an optional dependency of {meta_link} on matching "
        "platforms.",
        "",
        "```sh",
        f"npx {meta_name}@rc",
        "```",
        "",
        "## Trademark",
        "",
        "Haybarn is an independent derived distribution of DuckDB published by "
        "[Query Farm LLC](https://query.farm). Not affiliated with or endorsed by "
        "the DuckDB Foundation. DuckDB is a trademark of the DuckDB Foundation.",
        "",
    ])
    (stage / "README.md").write_text(readme)
    print(f"wrote {stage / 'README.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
