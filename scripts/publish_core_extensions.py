#!/usr/bin/env python3
"""Publish core extensions: iterate the assembled extension repository at
/tmp/haybarn-repository, apply the per-commit immutable R2 layout (signed
binary + signed manifest + signed current.json pointer), and stage pip
wheel + npm leaf + npm meta artifacts for the publish_pypi / publish_npm
jobs to upload.

Mirrors what haybarn-community-extensions/.github/workflows/_extension_deploy.yml
does for a single (extension, arch) tuple, but loops over the full
core matrix in one process — there are ~17 extensions × ~10 platforms
so a single workflow job is plenty.

Per the design call we made: all core extensions share ext_commit =
engine_commit. That's accurate for in-tree extensions and an
approximation for the build-fork extensions (iceberg/ducklake/delta/
httpfs which have their own SHAs). Refining the build-fork attribution
is a follow-up.

Inputs (all required):
  --repo-dir          assembled repo, e.g. /tmp/haybarn-repository
  --engine-commit     40-char engine SHA
  --engine-commit-ts  engine commit unix timestamp (UTC)
  --haybarn-version   e.g. 1.5.2  (drives package-name suffix + peer pin)
  --duckdb-version    e.g. v1.5.2 (path segment)
  --r2-bucket         R2 bucket name
  --r2-prefix         e.g. core
  --license           path to LICENSE file (embedded in wheels)
  --dist-dir          staging dir for pip wheels + npm package dirs
  --signed-by         identity name (forward hook for trust-store)
  --channels          comma-separated, e.g. r2-core,pypi,npm
  --deploy            when 'true', actually upload to R2; otherwise dry-run

Env (required when --deploy true):
  DUCKDB_EXTENSION_SIGNING_PK   PEM private key for binary RSA sign
  HAYBARN_GPG_PRIVATE_KEY       GPG key for manifest signing
  HAYBARN_GPG_PASSPHRASE
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_ENDPOINT_URL /
    AWS_DEFAULT_REGION / AWS_REQUEST_CHECKSUM_CALCULATION /
    AWS_RESPONSE_CHECKSUM_VALIDATION

Staging output (always written):
  <dist-dir>/pypi/<wheel-name>.whl
  <dist-dir>/npm-leaves/<leaf-pkg-name>/        (package.json + bin/ + metadata)
  <dist-dir>/npm-metas/<meta-pkg-name>/         (package.json + metadata)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()

# duckdb_arch → (PyPI platform tag, npm os, npm cpu, npm libc, leaf suffix)
PLATMAP: dict[str, tuple[str, str, str, str, str]] = {
    "linux_amd64":       ("manylinux_2_28_x86_64",  "linux",  "x64",   "glibc", "linux-x64"),
    "linux_arm64":       ("manylinux_2_28_aarch64", "linux",  "arm64", "glibc", "linux-arm64"),
    "linux_amd64_musl":  ("musllinux_1_2_x86_64",   "linux",  "x64",   "musl",  "linux-x64-musl"),
    "linux_arm64_musl":  ("musllinux_1_2_aarch64",  "linux",  "arm64", "musl",  "linux-arm64-musl"),
    "osx_amd64":         ("macosx_11_0_x86_64",     "darwin", "x64",   "-",     "darwin-x64"),
    "osx_arm64":         ("macosx_11_0_arm64",      "darwin", "arm64", "-",     "darwin-arm64"),
    "windows_amd64":     ("win_amd64",              "win32",  "x64",   "-",     "win32-x64"),
    "windows_arm64":     ("win_arm64",              "win32",  "arm64", "-",     "win32-arm64"),
    # wasm and windows_amd64_mingw deliberately not mapped — they skip
    # the pip/npm publish path (same as community workflow).
}


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """subprocess.run with check=True and minimal output by default."""
    return subprocess.run(cmd, check=True, **kw)


def sign_and_compress_binary(ext_path: pathlib.Path, arch: str, signing_pk: str,
                             work_dir: pathlib.Path) -> pathlib.Path:
    """Mirror of extension-upload-single.sh's sign+compress dance, isolated
    so we can do it for each binary while keeping the original artifact
    intact. Returns the compressed output path."""
    is_wasm = arch.startswith("wasm")
    suffix = "wasm" if is_wasm else "gz"
    dest = work_dir / f"{ext_path.stem}.duckdb_extension.{suffix}"

    # Copy → truncate last 256 bytes (placeholder signature footer)
    append = work_dir / "work.append"
    shutil.copy(ext_path, append)
    with append.open("r+b") as f:
        f.seek(-256, 2)
        f.truncate()

    # Hash the truncated body, RSA-sign with the embedded extension key
    sign_file = work_dir / "work.sign"
    key_file = work_dir / "private.pem"
    hash_file = work_dir / "work.hash"
    try:
        key_file.write_text(signing_pk)
        # compute-extension-hash.sh ships in scripts/ — use it for parity
        # with extension-upload-single.sh's hash format.
        with hash_file.open("wb") as h:
            run([str(SCRIPT_DIR / "compute-extension-hash.sh"), str(append)], stdout=h)
        run(["openssl", "pkeyutl", "-sign", "-in", str(hash_file),
             "-inkey", str(key_file), "-pkeyopt", "digest:sha256",
             "-out", str(sign_file)])
    finally:
        if key_file.exists():
            key_file.unlink()

    # Append signature, then compress
    with append.open("ab") as a, sign_file.open("rb") as s:
        a.write(s.read())
    sign_file.unlink()

    if is_wasm:
        with append.open("rb") as src, dest.open("wb") as dst:
            run(["brotli"], stdin=src, stdout=dst)
    else:
        with append.open("rb") as src, dest.open("wb") as dst:
            run(["gzip"], stdin=src, stdout=dst)
    append.unlink()
    hash_file.unlink()
    return dest


def sha256_hex(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gpg_sign(path: pathlib.Path, passphrase: str, key_id: str) -> pathlib.Path:
    asc = pathlib.Path(str(path) + ".asc")
    run(["gpg", "--batch", "--yes", "--pinentry-mode", "loopback",
         "--passphrase", passphrase, "--local-user", key_id,
         "--detach-sign", "--armor", "--output", str(asc), str(path)])
    return asc


def gpg_import_and_get_keyid(armored_or_hex_key: str, passphrase: str) -> str:
    """Import HAYBARN_GPG_PRIVATE_KEY (any of 6 shapes the engine repo's
    haybarn-publish.yml accepts) and return the long key id of the
    Haybarn signing identity."""
    import base64

    raw = armored_or_hex_key
    candidates: list[bytes] = []
    # 1. armored direct
    candidates.append(raw.encode())
    # 2. armored with literal \n escapes
    candidates.append(raw.replace("\\n", "\n").encode())
    # 3. base64-of-binary
    try:
        candidates.append(base64.b64decode("".join(raw.split())))
    except Exception:
        pass
    # 4. hex-decoded binary
    try:
        candidates.append(bytes.fromhex("".join(raw.split())))
    except ValueError:
        pass
    # 5. raw bytes
    candidates.append(raw.encode("latin-1", errors="replace"))

    for cand in candidates:
        with tempfile.NamedTemporaryFile(delete=False) as kf:
            kf.write(cand)
            kf_path = kf.name
        try:
            r = subprocess.run(
                ["gpg", "--batch", "--pinentry-mode", "loopback",
                 "--passphrase", passphrase, "--import", kf_path],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                break
        finally:
            os.unlink(kf_path)
    else:
        raise SystemExit("publish_core_extensions: could not import HAYBARN_GPG_PRIVATE_KEY")

    # Now find the secret key for our uid
    r = subprocess.run(["gpg", "--list-secret-keys", "--keyid-format", "LONG"],
                       capture_output=True, text=True, check=True)
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("sec"):
            # e.g.  "sec   rsa4096/C41595068F3F6537 ..."
            return line.split("/", 1)[1].split()[0]
    raise SystemExit("publish_core_extensions: imported GPG key but no sec line found")


def compute_calver(ts: int) -> str:
    when = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
    return f"{when.year*100+when.month}.{when.day}.{when.hour*10000+when.minute*100+when.second}"


def haybarn_suffix(hv: str) -> str:
    a, b, c = hv.split(".")
    return f"h{a}-{b}-{c}"


def npm_leaf_pkg_name(extension: str, hv: str, leaf_suffix: str) -> str:
    return f"@haybarn/ext-{extension}-{haybarn_suffix(hv)}-{leaf_suffix}"


def npm_meta_pkg_name(extension: str, hv: str) -> str:
    return f"@haybarn/ext-{extension}-{haybarn_suffix(hv)}"


def call_helper(name: str, *args: str) -> None:
    run(["python3", str(SCRIPT_DIR / name), *args])


def aws_cp(local: pathlib.Path, s3_url: str, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY: aws s3 cp {local} {s3_url}")
        return
    run(["aws", "s3", "cp", str(local), s3_url])


def maybe_read_previous(s3_pointer: str, dry_run: bool) -> str:
    """Fetch previous current.json's 'latest' if it exists, else ''."""
    if dry_run:
        return ""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        r = subprocess.run(["aws", "s3", "cp", s3_pointer, path],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return ""
        try:
            return json.load(open(path)).get("latest", "")
        except Exception:
            return ""
    finally:
        if os.path.exists(path):
            os.unlink(path)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-dir",          required=True, type=pathlib.Path)
    ap.add_argument("--engine-commit",     required=True)
    ap.add_argument("--engine-commit-ts",  required=True, type=int)
    ap.add_argument("--haybarn-version",   required=True)
    ap.add_argument("--duckdb-version",    required=True)
    ap.add_argument("--r2-bucket",         required=True)
    ap.add_argument("--r2-prefix",         required=True)
    ap.add_argument("--license",           required=True, type=pathlib.Path)
    ap.add_argument("--dist-dir",          required=True, type=pathlib.Path)
    ap.add_argument("--signed-by",         required=True)
    ap.add_argument("--channels",          required=True)
    ap.add_argument("--deploy",            default="false")
    args = ap.parse_args(argv)

    dry_run = args.deploy.lower() != "true"
    print(f"::notice::publish_core_extensions: dry_run={dry_run}, "
          f"engine={args.engine_commit[:8]}, hv={args.haybarn_version}")

    signing_pk = os.environ.get("DUCKDB_EXTENSION_SIGNING_PK")
    if not signing_pk:
        raise SystemExit("DUCKDB_EXTENSION_SIGNING_PK is required")
    gpg_pk   = os.environ.get("HAYBARN_GPG_PRIVATE_KEY", "")
    gpg_pass = os.environ.get("HAYBARN_GPG_PASSPHRASE", "")

    gpg_key_id = ""
    if gpg_pk and gpg_pass:
        gpg_key_id = gpg_import_and_get_keyid(gpg_pk, gpg_pass)
        print(f"::notice::GPG signing key {gpg_key_id}")
    else:
        print("::warning::HAYBARN_GPG_* not set — manifests will be unsigned (no .asc)")

    calver = compute_calver(args.engine_commit_ts)
    ext_short = args.engine_commit[:10]
    built_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Stage dirs
    dist = args.dist_dir
    pypi_dir = dist / "pypi"
    npm_leaves_dir = dist / "npm-leaves"
    npm_metas_dir = dist / "npm-metas"
    for d in (pypi_dir, npm_leaves_dir, npm_metas_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Track which leaves succeeded per extension for the meta packages
    leaves_by_ext: dict[str, list[str]] = {}

    work_root = pathlib.Path(tempfile.mkdtemp(prefix="publish-core-"))

    try:
        # Layout: <repo-dir>/<duckdb_version>/<arch>/<ext>.duckdb_extension(.wasm)
        for version_dir in sorted(args.repo_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            dv = version_dir.name
            for arch_dir in sorted(version_dir.iterdir()):
                if not arch_dir.is_dir():
                    continue
                arch = arch_dir.name
                is_wasm = arch.startswith("wasm")
                pat = "*.duckdb_extension.wasm" if is_wasm else "*.duckdb_extension"
                for ext_file in sorted(arch_dir.glob(pat)):
                    ext = ext_file.name.replace(".duckdb_extension.wasm", "") \
                                       .replace(".duckdb_extension", "")
                    print(f"\n=== {ext} on {arch} ({dv}) ===")
                    work = work_root / arch / ext
                    work.mkdir(parents=True, exist_ok=True)

                    compressed = sign_and_compress_binary(ext_file, arch, signing_pk, work)
                    sha = sha256_hex(compressed)
                    print(f"  sha256: {sha}")

                    # 1. haybarn-metadata.json (small blob, also used by wheel/leaf)
                    meta_path = work / "haybarn-metadata.json"
                    call_helper("generate_haybarn_metadata.py",
                                "--extension", ext,
                                "--ext-commit", args.engine_commit,
                                "--haybarn-version", args.haybarn_version,
                                "--ext-version-label", "",   # core has no per-ext semver
                                "--sha256", sha,
                                "--built-at", built_at,
                                "--out", str(meta_path))

                    # 2. R2 manifest.json (superset)
                    prev = maybe_read_previous(
                        f"s3://{args.r2_bucket}/{args.r2_prefix}/{dv}/{arch}/{ext}/current.json",
                        dry_run)
                    manifest_path = work / "manifest.json"
                    call_helper("r2_build_manifest.py",
                                "--extension", ext,
                                "--duckdb-version", dv,
                                "--platform", arch,
                                "--ext-commit", args.engine_commit,
                                "--ext-version-label", "",
                                "--sha256", sha,
                                "--object", compressed.name,
                                "--built-at", built_at,
                                "--haybarn-engine-commit", args.engine_commit,
                                "--signed-by", args.signed_by,
                                "--channels", args.channels,
                                "--previous-commit", prev,
                                "--out", str(manifest_path))

                    # 3. GPG sign (manifest + current.json), if key available
                    manifest_asc = None
                    current_path = work / "current.json"
                    current_asc = None
                    current_path.write_text(json.dumps({
                        "latest": args.engine_commit,
                        "updated_at": built_at,
                    }, indent=2, sort_keys=True) + "\n")
                    if gpg_key_id:
                        manifest_asc = gpg_sign(manifest_path, gpg_pass, gpg_key_id)
                        current_asc  = gpg_sign(current_path,  gpg_pass, gpg_key_id)

                    # 4. Upload to per-commit immutable R2 path
                    pfx = f"s3://{args.r2_bucket}/{args.r2_prefix}/{dv}/{arch}/{ext}/{ext_short}"
                    aws_cp(compressed,    f"{pfx}/{compressed.name}",       dry_run)
                    aws_cp(manifest_path, f"{pfx}/manifest.json",           dry_run)
                    if manifest_asc:
                        aws_cp(manifest_asc, f"{pfx}/manifest.json.asc",     dry_run)

                    # 5. Update current.json pointer
                    ptr = f"s3://{args.r2_bucket}/{args.r2_prefix}/{dv}/{arch}/{ext}/current.json"
                    aws_cp(current_path, ptr, dry_run)
                    if current_asc:
                        aws_cp(current_asc, f"{ptr}.asc", dry_run)

                    # 6. pip wheel + npm leaf (skip wasm + windows_amd64_mingw)
                    plat = PLATMAP.get(arch)
                    if plat is None:
                        print(f"  (no pypi/npm platform mapping for {arch} — skipping)")
                        continue
                    py_tag, npm_os, npm_cpu, npm_libc, leaf_suffix = plat

                    call_helper("pypi_build_wheel.py",
                                "--extension", ext,
                                "--haybarn-version", args.haybarn_version,
                                "--version", calver,
                                "--platform-tag", py_tag,
                                "--binary", str(compressed),
                                "--haybarn-metadata", str(meta_path),
                                "--license", str(args.license),
                                "--out-dir", str(pypi_dir))

                    # npm leaf — emit a directory ready for `cd && npm publish`
                    leaf_pkg = npm_leaf_pkg_name(ext, args.haybarn_version, leaf_suffix)
                    # npm rejects '/' in directory names of npm pkg paths
                    leaf_stage = npm_leaves_dir / leaf_pkg.replace("/", "_")
                    (leaf_stage / "bin").mkdir(parents=True, exist_ok=True)
                    shutil.copy(compressed, leaf_stage / "bin" / compressed.name)
                    shutil.copy(meta_path,  leaf_stage / "haybarn-metadata.json")
                    env = dict(os.environ,
                               STAGE=str(leaf_stage), PKG=leaf_pkg,
                               VERSION=calver, EXTENSION=ext,
                               HAYBARN_VERSION=args.haybarn_version,
                               OS=npm_os, CPU=npm_cpu, LIBC=npm_libc,
                               HAYBARN_METADATA=str(leaf_stage / "haybarn-metadata.json"))
                    run(["python3", str(SCRIPT_DIR / "npm_build_leaf.py")], env=env)

                    leaves_by_ext.setdefault(ext, []).append(leaf_suffix)

        # 7. Per-extension npm meta packages — must run after all leaves are known
        for ext, suffixes in leaves_by_ext.items():
            meta_pkg = npm_meta_pkg_name(ext, args.haybarn_version)
            meta_stage = npm_metas_dir / meta_pkg.replace("/", "_")
            meta_stage.mkdir(parents=True, exist_ok=True)
            # The meta's haybarn-metadata.json carries an aggregate blob (no
            # per-platform sha256 since the meta has no binary).
            agg_meta = meta_stage / "haybarn-metadata.json"
            call_helper("generate_haybarn_metadata.py",
                        "--extension", ext,
                        "--ext-commit", args.engine_commit,
                        "--haybarn-version", args.haybarn_version,
                        "--ext-version-label", "",
                        "--sha256", "see-leaf-packages-for-per-platform-sha256",
                        "--built-at", built_at,
                        "--out", str(agg_meta))
            env = dict(os.environ,
                       STAGE=str(meta_stage), PKG=meta_pkg,
                       VERSION=calver, EXTENSION=ext,
                       HAYBARN_VERSION=args.haybarn_version,
                       HAYBARN_METADATA=str(agg_meta),
                       PRESENT_LEAVES=",".join(sorted(suffixes)))
            run(["python3", str(SCRIPT_DIR / "npm_build_meta.py")], env=env)

        # Summary
        n_wheels = sum(1 for _ in pypi_dir.glob("*.whl"))
        n_leaves = sum(1 for d in npm_leaves_dir.iterdir() if d.is_dir())
        n_metas  = sum(1 for d in npm_metas_dir.iterdir()  if d.is_dir())
        print(f"\n=== summary ===")
        print(f"  extensions processed: {len(leaves_by_ext)}")
        print(f"  wheels staged:        {n_wheels}")
        print(f"  npm leaves staged:    {n_leaves}")
        print(f"  npm metas staged:     {n_metas}")
        print(f"  calver:               {calver}")
        print(f"  ext_commit short:     {ext_short}")
        return 0
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
