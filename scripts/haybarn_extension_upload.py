#!/usr/bin/env python3
"""Haybarn: sign + compress core extension binaries and publish the mutable
"latest" tree to R2.

Replaces the shell chain extension-upload-repository.sh ->
extension-upload-single.sh -> compute-extension-hash.sh, which used
fixed-name temp files (private.pem, and `split` chunks xaa/xab/... ) in the
process working directory. Those fixed names made the chain impossible to
parallelize: concurrent invocations clobbered each other's private.pem and
split chunks. Doing it in Python keeps every binary's work in memory, so the
sign+compress phase parallelizes cleanly across a process pool.

Signature format (must match the engine verifier exactly):
  The DuckDB extension signature is an RSA PKCS#1 v1.5 signature over a
  *two-level* hash. The binary body (everything but the trailing 256-byte
  signature footer) is split into 1 MiB chunks; each chunk is SHA-256'd; the
  32-byte digests are concatenated; that concatenation is SHA-256'd again. See
  src/main/extension/extension_load.cpp (ComputeFinalHash /
  IntializeAncillaryData / ComputeHashesOnSegments) — the engine hashes the
  1 MiB chunks on parallel threads, which is the whole reason for the two-level
  structure. Validated byte-for-byte against compute-extension-hash.sh and
  `openssl pkeyutl -sign -pkeyopt digest:sha256`.

Phase 1 (CPU):  sign+compress every binary in parallel, in memory, into a
                staging tree mirroring the R2 "latest" layout:
                  <stage>/<duckdb_version>/<arch>/<ext>.duckdb_extension.{gz,wasm}
Phase 2 (I/O):  one `aws s3 sync` per metadata class (gz vs wasm) ships the
                whole tree; aws's transfer engine handles upload concurrency.

Usage: haybarn_extension_upload.py <base_dir> <s3_bucket[/prefix]>
Layout under <base_dir>: <duckdb_version>/<arch>/<ext>.duckdb_extension[.wasm]

Env:
  DUCKDB_EXTENSION_SIGNING_PK        PEM private key. If unset, a 256 zero-byte
                                     placeholder footer is used (dry validation),
                                     mirroring extension-upload-single.sh.
  DUCKDB_DEPLOY_SCRIPT_MODE          'for_real' => actually upload; else --dryrun.
  EXTENSION_UPLOAD_CONCURRENCY       sign+compress worker count (default: cpus).
  EXTENSION_UPLOAD_SYNC_CONCURRENCY  aws s3 sync transfer concurrency (default 32).
  EXTENSION_UPLOAD_CACHE_CONTROL_LATEST  Cache-Control for the latest objects.
  AWS_*                              standard aws creds/endpoint for the sync.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import pathlib
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, utils

SIGNATURE_SIZE = 256
CHUNK = 1024 * 1024  # 1 MiB — must match the engine's IntializeAncillaryData


def two_level_hash(body: bytes) -> bytes:
    concat = b"".join(
        hashlib.sha256(body[i:i + CHUNK]).digest()
        for i in range(0, len(body), CHUNK)
    )
    return hashlib.sha256(concat).digest()


def sign_footer(body: bytes, pem: bytes | None) -> bytes:
    """Return the 256-byte signature footer for this body."""
    if not pem:
        return b"\x00" * SIGNATURE_SIZE  # unsigned placeholder (no key set)
    key = serialization.load_pem_private_key(pem, password=None)
    sig = key.sign(two_level_hash(body), padding.PKCS1v15(),
                   utils.Prehashed(hashes.SHA256()))
    if len(sig) != SIGNATURE_SIZE:
        raise SystemExit(
            f"signing key produced a {len(sig)}-byte signature; the extension "
            f"footer is fixed at {SIGNATURE_SIZE} bytes (expected an RSA-2048 key)")
    return sig


def process_one(ext_file: str, stage_dir: str, pem: bytes | None) -> str:
    p = pathlib.Path(ext_file)
    arch = p.parent.name
    version = p.parent.parent.name
    is_wasm = arch.startswith("wasm")

    raw = p.read_bytes()
    if len(raw) < SIGNATURE_SIZE:
        raise SystemExit(f"{p} is smaller than the {SIGNATURE_SIZE}-byte footer")
    # Strip the placeholder footer, sign the body, re-append the real signature.
    body = raw[:-SIGNATURE_SIZE]
    signed = body + sign_footer(body, pem)

    if is_wasm:
        name = p.name[:-len(".duckdb_extension.wasm")]
        out = pathlib.Path(stage_dir) / version / arch / f"{name}.duckdb_extension.wasm"
    else:
        name = p.name[:-len(".duckdb_extension")]
        out = pathlib.Path(stage_dir) / version / arch / f"{name}.duckdb_extension.gz"
    out.parent.mkdir(parents=True, exist_ok=True)

    if is_wasm:
        # brotli has no stdlib; shell out to the CLI (stdin->stdout, no temp files).
        r = subprocess.run(["brotli", "-c"], input=signed,
                           stdout=subprocess.PIPE, check=True)
        out.write_bytes(r.stdout)
    else:
        buf = io.BytesIO()
        # mtime=0 => reproducible gzip output (no wall-clock byte in the header).
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
            gz.write(signed)
        out.write_bytes(buf.getvalue())
    return str(out)


def aws_sync(stage_dir: pathlib.Path, dest: str, include: str, dry_run: bool,
             cache_control: str, extra: list[str]) -> None:
    cmd = ["aws", "s3", "sync", str(stage_dir), dest, "--no-progress",
           "--exclude", "*", "--include", include, "--cache-control", cache_control]
    if dry_run:
        cmd.append("--dryrun")
    cmd += extra
    subprocess.run(cmd, check=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("base_dir", type=pathlib.Path)
    ap.add_argument("target_bucket", help="bucket[/prefix], e.g. my-bucket/core")
    args = ap.parse_args(argv)

    pem_str = os.environ.get("DUCKDB_EXTENSION_SIGNING_PK", "")
    pem = pem_str.encode() if pem_str else None
    if not pem:
        print("::warning::DUCKDB_EXTENSION_SIGNING_PK unset — using zero-byte "
              "signature footer (extensions will NOT verify)")

    dry_run = os.environ.get("DUCKDB_DEPLOY_SCRIPT_MODE") != "for_real"
    jobs = int(os.environ.get("EXTENSION_UPLOAD_CONCURRENCY", os.cpu_count() or 4))
    sync_conc = os.environ.get("EXTENSION_UPLOAD_SYNC_CONCURRENCY", "32")
    cache_control = os.environ.get(
        "EXTENSION_UPLOAD_CACHE_CONTROL_LATEST",
        "public, max-age=10, must-revalidate")

    files = sorted(
        [str(f) for f in args.base_dir.rglob("*.duckdb_extension")] +
        [str(f) for f in args.base_dir.rglob("*.duckdb_extension.wasm")]
    )
    if not files:
        print(f"No built extensions found under {args.base_dir}", file=sys.stderr)
        return 1

    mode = "for_real" if not dry_run else "DRY RUN"
    print(f"Signing+compressing {len(files)} binaries (jobs={jobs}) [{mode}]")

    stage_dir = pathlib.Path(tempfile.mkdtemp(prefix="haybarn-ext-stage-"))

    # Phase 1: parallel sign + compress (pure in-memory per file — no shared
    # temp files, so this is race-free unlike the shell chain it replaces).
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futs = {pool.submit(process_one, f, str(stage_dir), pem): f for f in files}
        for fut in as_completed(futs):
            print(f"  staged {pathlib.Path(fut.result()).relative_to(stage_dir)}")

    # Phase 2: ship the staged tree. gz and wasm carry different metadata.
    subprocess.run(["aws", "configure", "set",
                    "default.s3.max_concurrent_requests", sync_conc], check=True)
    dest = f"s3://{args.target_bucket}"

    # gz: NO content-encoding — the loader fetches the .gz and gunzips it itself;
    # a content-encoding header would make the CDN auto-decompress and break it.
    aws_sync(stage_dir, dest, "*.duckdb_extension.gz", dry_run, cache_control, [])

    if any(f.endswith(".wasm") for f in files):
        aws_sync(stage_dir, dest, "*.duckdb_extension.wasm", dry_run, cache_control,
                 ["--content-encoding", "br", "--content-type", "application/wasm"])

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
