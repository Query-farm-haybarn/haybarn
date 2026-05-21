#!/bin/bash

# Haybarn: parallel sign/compress + single `aws s3 sync` replacement for the
# upstream serial extension-upload-repository.sh.
#
# The upstream script walks <version>/<arch>/<ext> in two nested loops and
# invokes extension-upload-single.sh once per file, each of which does an
# `aws s3 cp` — hundreds of serialized PUTs, every one paying a fresh `aws` CLI
# (Python/botocore) cold-start plus a round-trip to R2. That dominates the
# "Sign and publish to R2" job wall-clock.
#
# This driver splits the work along its two independent cost centers:
#   Phase 1 (CPU-bound)     sign + compress every extension IN PARALLEL into a
#                           local tree mirroring the R2 "latest" key layout.
#                           extension-upload-single.sh's EXTENSION_UPLOAD_STAGE_DIR
#                           mode does the signing/compression (no crypto dup'd here).
#   Phase 2 (latency-bound) one `aws s3 sync` per metadata class ships the whole
#                           tree; aws's own transfer engine handles upload
#                           concurrency, so we pay ONE CLI cold-start, not N.
#
# Usage: ./haybarn-extension-upload-repository.sh <base_dir> <s3_bucket[/prefix]>
# Expected layout under <base_dir>: <duckdb_version>/<architecture>/<ext>.duckdb_extension[.wasm]

set -euo pipefail

script_dir="$(dirname "$(readlink -f "$0")")"

BASE_DIR="${1:-build/release/repository}"
TARGET_BUCKET="${2:-duckdb-core-extensions}"

# CPU phase parallelism; override via env. Default to the runner's core count.
JOBS="${EXTENSION_UPLOAD_CONCURRENCY:-$(nproc)}"
# aws s3 sync's internal upload concurrency (default is 10).
SYNC_CONCURRENCY="${EXTENSION_UPLOAD_SYNC_CONCURRENCY:-32}"

CACHE_CONTROL_LATEST="${EXTENSION_UPLOAD_CACHE_CONTROL_LATEST:-public, max-age=10, must-revalidate}"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

if [ "${DUCKDB_DEPLOY_SCRIPT_MODE:-}" == "for_real" ]; then
  echo "Deploying extensions from '$BASE_DIR' to bucket '$TARGET_BUCKET' (jobs=$JOBS, sync_concurrency=$SYNC_CONCURRENCY) .."
  SYNC_DRY=""
else
  echo "Deploying extensions from '$BASE_DIR' to bucket '$TARGET_BUCKET' .. (DRY RUN)"
  SYNC_DRY="--dryrun"
fi

# ---------------------------------------------------------------------------
# Phase 1: sign + compress in parallel into $STAGE_DIR/<version>/<arch>/...
# ---------------------------------------------------------------------------
prepare_one() {
  local f="$1"
  local arch_dir arch version ext_name
  arch_dir="$(dirname "$f")"
  arch="$(basename "$arch_dir")"
  version="$(basename "$(dirname "$arch_dir")")"
  if [[ $arch == wasm* ]]; then
    ext_name="$(basename "$f" .duckdb_extension.wasm)"
  else
    ext_name="$(basename "$f" .duckdb_extension)"
  fi
  echo "Signing+compressing $ext_name ($arch, $version)"
  # args: <name> <ext_version> <duckdb_version> <arch> <bucket> <latest> <versioned> <path>
  # EXTENSION_UPLOAD_STAGE_DIR makes single.sh stage instead of upload.
  EXTENSION_UPLOAD_STAGE_DIR="$STAGE_DIR" \
    "$script_dir/extension-upload-single.sh" \
    "$ext_name" "" "$version" "$arch" "$TARGET_BUCKET" true false "$arch_dir"
}
export -f prepare_one
export script_dir STAGE_DIR TARGET_BUCKET

# Bail loudly if the build produced nothing — otherwise the sync below is a
# silent no-op and the deploy looks green without writing anything.
if [ -z "$(find "$BASE_DIR" \( -name '*.duckdb_extension' -o -name '*.duckdb_extension.wasm' \) -print -quit)" ]; then
  echo "No built extensions found to publish under '$BASE_DIR'" >&2
  exit 1
fi

# Drive the fan-out with GNU parallel when present, else fall back to xargs -P
# (always available; -0/-print0 keeps paths with spaces safe).
find "$BASE_DIR" \( -name '*.duckdb_extension' -o -name '*.duckdb_extension.wasm' \) -print0 \
  | if command -v parallel >/dev/null 2>&1; then
      parallel -0 -j"$JOBS" --halt now,fail=1 prepare_one {}
    else
      xargs -0 -P"$JOBS" -I{} bash -c 'prepare_one "$1"' _ {}
    fi

# ---------------------------------------------------------------------------
# Phase 2: ship the staged tree. gz and wasm carry different metadata, so one
# sync each. aws s3 sync uploads new/changed objects only; freshly-staged files
# are always newer than any prior remote copy, so the mutable "latest" pointers
# always refresh.
# ---------------------------------------------------------------------------
aws configure set default.s3.max_concurrent_requests "$SYNC_CONCURRENCY"

# gz: NO content-encoding — the extension loader fetches the .gz and gunzips it
# itself; a content-encoding header would make Cloudflare auto-decompress and
# break the loader. content-type is left to aws's auto-detection (matches the
# upstream `aws s3 cp` behavior).
aws s3 sync "$STAGE_DIR" "s3://$TARGET_BUCKET" $SYNC_DRY \
  --no-progress \
  --exclude '*' --include '*.duckdb_extension.gz' \
  --cache-control "$CACHE_CONTROL_LATEST"

# wasm: brotli-compressed, served as application/wasm.
if find "$STAGE_DIR" -name '*.duckdb_extension.wasm' -print -quit | grep -q .; then
  aws s3 sync "$STAGE_DIR" "s3://$TARGET_BUCKET" $SYNC_DRY \
    --no-progress \
    --exclude '*' --include '*.duckdb_extension.wasm' \
    --content-encoding br --content-type "application/wasm" \
    --cache-control "$CACHE_CONTROL_LATEST"
fi

echo "Done."
