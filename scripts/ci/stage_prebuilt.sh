#!/usr/bin/env bash
set -euo pipefail

commit10="$(echo "$GITHUB_SHA" | cut -c1-10 | tr 'A-F' 'a-f')"
version="$OVERRIDE_GIT_DESCRIBE"
[[ "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-(alpha|rc|dev)[0-9]+)?$ ]] || { echo "::error::unstageable version $version"; exit 1; }
prefix="s3://$R2_BUCKET/staging/$commit10"

# Require every supported platform before uploading anything.
platforms=(linux-amd64 linux-arm64 linux-amd64-musl linux-arm64-musl osx-arm64 windows-amd64 windows-amd64-mingw)
for platform in "${platforms[@]}"; do
    archive="artifacts/duckdb-static-libs-$platform.tar.gz"
    [[ -s "$archive" ]] || { echo "::error::missing or empty static-libs archive: $archive"; exit 1; }
done

for platform in "${platforms[@]}"; do
    archive="artifacts/duckdb-static-libs-$platform.tar.gz"
    # Extension CI's MinGW staging name differs from the public release asset.
    staged_platform="$platform"
    if [[ "$platform" == windows-amd64-mingw ]]; then
        staged_platform=windows-mingw
    fi
    aws s3 cp --no-progress "$archive" "$prefix/$version/duckdb/duckdb/github_release/duckdb-static-libs-$staged_platform.tar.gz"
done

# Written last, so a reader that finds the pointer finds every platform.
printf '%s\n' "$version" > latest_alpha_version.txt
aws s3 cp --no-progress --content-type text/plain latest_alpha_version.txt "$prefix/latest_alpha_version.txt"
echo "Staged ${#platforms[@]} archives under https://haybarn-extensions.query.farm/staging/$commit10/$version/"
