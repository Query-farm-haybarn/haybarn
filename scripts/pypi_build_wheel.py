#!/usr/bin/env python3
"""Build a single platform-tagged PyPI wheel for a haybarn extension.

The wheel is a "data wheel" — no Python C-API code, just the signed
.duckdb_extension(.gz) binary carried as package data, plus the
haybarn-metadata.json blob in dist-info/.

Modeled directly on haybarn/tools/pypi-cli/build_wheel.py (same direct-
zipfile construction, no `build`/`wheel` deps).

Package naming follows ideas/extension-version-pinning.md:

    Display:   haybarn-ext-<name>-h<M>-<m>-<p>
    Wheel:     haybarn_ext_<name>_h<M>_<m>_<p>-<version>-py3-none-<plat>.whl
    Import:    haybarn_ext_<name>_h<M>_<m>_<p>

Version field is the extension's own semver where tagged, else the CalVer
YYYYMM.DD.HHMMSS from commit time (computed via compute_calver.py).

Usage:
    python3 pypi_build_wheel.py \\
        --extension waddle \\
        --haybarn-version 1.5.2 \\
        --version 0.0.2 \\
        --platform-tag manylinux_2_28_x86_64 \\
        --binary /tmp/extension/waddle.duckdb_extension.gz \\
        --haybarn-metadata stage/haybarn-metadata.json \\
        --license LICENSE \\
        --out-dir dist/

Produces e.g. dist/haybarn_ext_waddle_h1_5_2-0.0.2-py3-none-manylinux_2_28_x86_64.whl
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import pathlib
import sys
import zipfile

HOMEPAGE = "https://github.com/Query-farm-haybarn/haybarn-community-extensions"


def haybarn_suffix(haybarn_version: str) -> str:
    """1.5.2 → h1-5-2 (per the package-naming convention)."""
    parts = haybarn_version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SystemExit(
            f"pypi_build_wheel: --haybarn-version must be MAJOR.MINOR.PATCH, "
            f"got {haybarn_version!r}"
        )
    return f"h{parts[0]}-{parts[1]}-{parts[2]}"


def package_names(extension: str, haybarn_version: str) -> tuple[str, str]:
    """Returns (display_name, normalized_name).

    Display name uses hyphens (haybarn-ext-waddle-h1-5-2) per the convention.
    Normalized name (PEP 503 + PEP 427) uses underscores in the wheel filename
    and as the importable Python module name.
    """
    suffix = haybarn_suffix(haybarn_version)
    display = f"haybarn-ext-{extension}-{suffix}"
    # PEP 503 normalization replaces runs of `-`, `_`, `.` with `_` for
    # filename / import-name use. Underscoring the whole display name is the
    # right transform here.
    normalized = display.replace("-", "_")
    return display, normalized


def _b64nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _record_line(arcname: str, data: bytes) -> str:
    digest = _b64nopad(hashlib.sha256(data).digest())
    return f"{arcname},sha256={digest},{len(data)}\n"


def build_wheel(
    extension: str,
    haybarn_version: str,
    version: str,
    platform_tag: str,
    binary_path: pathlib.Path,
    metadata_blob: bytes,
    readme: bytes,
    license_text: bytes,
    out_dir: pathlib.Path,
) -> pathlib.Path:
    display, normalized = package_names(extension, haybarn_version)
    distinfo = f"{normalized}-{version}.dist-info"
    wheel_filename = f"{normalized}-{version}-py3-none-{platform_tag}.whl"

    bin_data = binary_path.read_bytes()
    bin_name = binary_path.name  # e.g. waddle.duckdb_extension.gz

    # Minimal __init__.py — the package needs one so pip will install it as
    # a real package, but no Python runtime logic belongs here. Engine
    # discovery (per extensions-from-npm-pypi.md Phase 3) finds the binary
    # by scanning for the package directory + the haybarn-metadata.json
    # validation gate, not by importing.
    init_py = (
        f'"""Haybarn extension {extension!r} for haybarn {haybarn_version}.\n\n'
        f'Data-only package. The binary lives next to this file as\n'
        f'{bin_name!r}; haybarn discovers it via the haybarn-metadata.json\n'
        f'blob in this distribution\'s dist-info/ directory.\n'
        f'"""\n'
    ).encode()

    summary = (
        f"Haybarn extension {extension!r} built against haybarn {haybarn_version}."
    )

    # No Requires-Dist on the haybarn engine for now. The PyPI package
    # name is `haybarn-cli` (not `haybarn`), and the currently-published
    # versions are pre-release (1.5.2rcN) which pip won't resolve without
    # --pre. Declaring a hard dep would block `pip install` of the
    # extension. The package-name suffix `-h<M>-<m>-<p>` still pins the
    # haybarn ABI for users who care; the engine itself verifies the RSA
    # signature on load anyway.
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {display}",
        f"Version: {version}",
        f"Summary: {summary}",
        f"Home-page: {HOMEPAGE}",
        "License: MIT",
        "License-File: LICENSE",
        "Requires-Python: >=3.8",
        "Description-Content-Type: text/markdown",
        "Classifier: License :: OSI Approved :: MIT License",
        "Classifier: Operating System :: POSIX :: Linux",
        "Classifier: Operating System :: MacOS :: MacOS X",
        "Classifier: Operating System :: Microsoft :: Windows",
        "Classifier: Programming Language :: Python :: 3",
        "Classifier: Topic :: Database",
        f"Project-URL: Homepage, {HOMEPAGE}",
        f"Project-URL: Source, {HOMEPAGE}",
        "",
    ]
    metadata_header = ("\n".join(metadata_lines) + "\n").encode()
    if readme:
        metadata = metadata_header + readme
    else:
        metadata = metadata_header + (summary + "\n").encode()

    wheel_meta = (
        "Wheel-Version: 1.0\n"
        "Generator: haybarn pypi_build_wheel.py\n"
        "Root-Is-Purelib: false\n"
        f"Tag: py3-none-{platform_tag}\n"
    ).encode()

    files: list[tuple[str, bytes, int]] = [
        (f"{normalized}/__init__.py",            init_py,       0o644),
        (f"{normalized}/{bin_name}",             bin_data,      0o644),
        (f"{distinfo}/METADATA",                 metadata,      0o644),
        (f"{distinfo}/WHEEL",                    wheel_meta,    0o644),
        # The unsigned metadata blob — informational only; trust comes from
        # registry immutability + engine RSA + lockfile sha256.
        (f"{distinfo}/haybarn-metadata.json",    metadata_blob, 0o644),
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
    ap.add_argument("--extension",       required=True,
                    help="extension name, e.g. waddle")
    ap.add_argument("--haybarn-version", required=True,
                    help="target haybarn patch, e.g. 1.5.2 — drives the "
                         "package-name suffix AND the exact peer dep")
    ap.add_argument("--version",         required=True,
                    help="PyPI version field (semver or CalVer, already computed)")
    ap.add_argument("--platform-tag",    required=True,
                    help="PEP 425 platform tag, e.g. manylinux_2_28_x86_64")
    ap.add_argument("--binary",          required=True, type=pathlib.Path,
                    help="path to the .duckdb_extension(.gz) binary")
    ap.add_argument("--haybarn-metadata", required=True, type=pathlib.Path,
                    help="path to pre-generated haybarn-metadata.json")
    ap.add_argument("--readme",          type=pathlib.Path, default=None,
                    help="optional README to embed in METADATA")
    ap.add_argument("--license",         type=pathlib.Path, default=None,
                    dest="license_path")
    ap.add_argument("--out-dir",         required=True, type=pathlib.Path)
    args = ap.parse_args(argv)

    if not args.binary.is_file():
        print(f"pypi_build_wheel: --binary {args.binary} not found", file=sys.stderr)
        return 2
    if not args.haybarn_metadata.is_file():
        print(f"pypi_build_wheel: --haybarn-metadata {args.haybarn_metadata} not found",
              file=sys.stderr)
        return 2

    metadata_blob = args.haybarn_metadata.read_bytes()
    readme = args.readme.read_bytes() if args.readme and args.readme.exists() else b""
    license_text = args.license_path.read_bytes() if args.license_path and args.license_path.exists() else b""

    build_wheel(
        extension=args.extension,
        haybarn_version=args.haybarn_version,
        version=args.version,
        platform_tag=args.platform_tag,
        binary_path=args.binary,
        metadata_blob=metadata_blob,
        readme=readme,
        license_text=license_text,
        out_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
