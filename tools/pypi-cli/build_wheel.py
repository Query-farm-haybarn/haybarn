#!/usr/bin/env python3
"""Build a single platform-tagged wheel for haybarn-cli from a release zip.

Usage:
  python3 build_wheel.py \\
      --src-zip release-assets/haybarn_cli-linux-amd64.zip \\
      --platform-tag manylinux_2_28_x86_64 \\
      --version 1.5.2-rc7 \\
      --out-dir dist/

The wheel format is just a renamed zip with a specific layout. We construct
it directly via the zipfile module rather than pulling in `wheel`/`build`
as deps — the wheel is a "binary data only" wheel (Python shim + bundled
binary) with no compiled extensions, so the standard build-system dance
is unnecessary.

Reference: PEP 427 (wheel binary format), PEP 425 (compat tags),
PEP 600 (manylinux_x_y), PEP 656 (musllinux_x_y).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import pathlib
import re
import sys
import zipfile

PROJECT = "haybarn-cli"          # display / PyPI name (with hyphen)
DIST = "haybarn_cli"             # PEP 503 normalized name (underscore), used in wheel filename + dist-info dir
ENTRY_MODULE = "haybarn_cli"     # the Python package the shim lives in (matches DIST)

SUMMARY = "Haybarn CLI — pre-built haybarn binary, runnable via uvx haybarn-cli or pipx run haybarn-cli."
HOMEPAGE = "https://github.com/Query-farm-haybarn/haybarn"


def npm_to_pep440(version: str) -> str:
    """Convert haybarn release-tag style (1.5.2-rc7) to PEP 440 (1.5.2rc7)."""
    return re.sub(r"-(rc\d+)$", r"\1", version)


def _b64nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _record_line(arcname: str, data: bytes) -> str:
    digest = _b64nopad(hashlib.sha256(data).digest())
    return f"{arcname},sha256={digest},{len(data)}\n"


def _extract_binary(src_zip: pathlib.Path, binary_name: str) -> bytes:
    with zipfile.ZipFile(src_zip) as zf:
        candidates = [
            n for n in zf.namelist()
            if pathlib.PurePosixPath(n).name == binary_name
        ]
        if not candidates:
            raise SystemExit(
                f"build_wheel: no {binary_name} entry in {src_zip} "
                f"(saw: {zf.namelist()})"
            )
        return zf.read(candidates[0])


def build_wheel(
    src_zip: pathlib.Path,
    platform_tag: str,
    version: str,
    shim_path: pathlib.Path,
    readme_path: pathlib.Path | None,
    license_path: pathlib.Path | None,
    out_dir: pathlib.Path,
) -> pathlib.Path:
    pep_version = npm_to_pep440(version)
    distinfo = f"{DIST}-{pep_version}.dist-info"
    wheel_filename = f"{DIST}-{pep_version}-py3-none-{platform_tag}.whl"
    binary_name = "haybarn.exe" if platform_tag.startswith("win") else "haybarn"

    bin_data = _extract_binary(src_zip, binary_name)
    shim_data = shim_path.read_bytes()

    readme = readme_path.read_bytes() if readme_path and readme_path.exists() else b""
    license_text = license_path.read_bytes() if license_path and license_path.exists() else b""

    metadata = (
        "Metadata-Version: 2.1\n"
        f"Name: {PROJECT}\n"
        f"Version: {pep_version}\n"
        f"Summary: {SUMMARY}\n"
        f"Home-page: {HOMEPAGE}\n"
        f"License: MIT\n"
        "License-File: LICENSE\n"
        "Requires-Python: >=3.8\n"
        "Description-Content-Type: text/markdown\n"
        "Classifier: License :: OSI Approved :: MIT License\n"
        "Classifier: Operating System :: POSIX :: Linux\n"
        "Classifier: Operating System :: MacOS :: MacOS X\n"
        "Classifier: Operating System :: Microsoft :: Windows\n"
        "Classifier: Programming Language :: Python :: 3\n"
        "Classifier: Topic :: Database\n"
        f"Project-URL: Homepage, {HOMEPAGE}\n"
        f"Project-URL: Source, {HOMEPAGE}\n"
        "\n"
    )
    if readme:
        metadata = metadata.encode() + readme
    else:
        metadata = metadata.encode() + SUMMARY.encode() + b"\n"

    wheel_meta = (
        "Wheel-Version: 1.0\n"
        "Generator: haybarn build_wheel.py\n"
        "Root-Is-Purelib: false\n"
        f"Tag: py3-none-{platform_tag}\n"
    ).encode()

    entry_points = (
        "[console_scripts]\n"
        f"haybarn = {ENTRY_MODULE}:main\n"
        f"haybarn-cli = {ENTRY_MODULE}:main\n"
    ).encode()

    files: list[tuple[str, bytes, int]] = [
        (f"{DIST}/__init__.py",          shim_data,     0o644),
        (f"{DIST}/_bin/{binary_name}",   bin_data,      0o755),
        (f"{distinfo}/METADATA",         metadata,      0o644),
        (f"{distinfo}/WHEEL",            wheel_meta,    0o644),
        (f"{distinfo}/entry_points.txt", entry_points,  0o644),
    ]
    if license_text:
        files.append((f"{distinfo}/LICENSE", license_text, 0o644))

    record_lines = [_record_line(name, data) for name, data, _ in files]
    record_lines.append(f"{distinfo}/RECORD,,\n")  # RECORD's own entry has empty hash + size
    files.append((f"{distinfo}/RECORD", "".join(record_lines).encode(), 0o644))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / wheel_filename
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, data, mode in files:
            info = zipfile.ZipInfo(arcname)
            # PEP 427: external_attr stores Unix mode in the high 16 bits.
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    print(f"wrote {out_path}  ({out_path.stat().st_size:,} bytes)")
    return out_path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src-zip", type=pathlib.Path, required=True,
                    help="release zip containing the haybarn binary")
    ap.add_argument("--platform-tag", required=True,
                    help="PEP 425 platform tag (e.g. manylinux_2_28_x86_64)")
    ap.add_argument("--version", required=True,
                    help="version string (haybarn-v<this>); converted to PEP 440")
    ap.add_argument("--shim", type=pathlib.Path,
                    default=pathlib.Path(__file__).parent / "haybarn_cli" / "__init__.py",
                    help="path to the Python shim that becomes haybarn_cli/__init__.py")
    ap.add_argument("--readme", type=pathlib.Path, default=None,
                    help="optional README to embed in METADATA")
    ap.add_argument("--license", type=pathlib.Path, default=None,
                    help="optional LICENSE to embed in dist-info")
    ap.add_argument("--out-dir", type=pathlib.Path, required=True,
                    help="directory to write the wheel into")
    args = ap.parse_args(argv)

    if not args.src_zip.is_file():
        print(f"build_wheel: src zip {args.src_zip} not found", file=sys.stderr)
        return 2
    if not args.shim.is_file():
        print(f"build_wheel: shim {args.shim} not found", file=sys.stderr)
        return 2

    build_wheel(
        src_zip=args.src_zip,
        platform_tag=args.platform_tag,
        version=args.version,
        shim_path=args.shim,
        readme_path=args.readme,
        license_path=args.license,
        out_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
