# CLAUDE.md — Haybarn

Guidance for Claude Code (and humans) working in this repository.

## What this repo is

**Haybarn** is an independent derived distribution of DuckDB ("Haybarn, powered
by DuckDB"), published by Query Farm LLC. This repo is a **hard fork** of
`duckdb/duckdb`, currently based on the upstream **`v1.5.2`** tag.

All Haybarn-specific changes are a small, curated **commit stack** on top of the
upstream tag — not scattered edits. Keep it that way: the stack must stay easy to
rebase onto future DuckDB releases. See `HAYBARN/REBASE.md`.

## Hard rules

- **Never rename the `duckdb::` C++ namespace, exported symbols, public header
  names (`duckdb.h`/`.hpp`), the `.duckdb_extension` suffix, the extension
  platform string, or the `DUCKDB_VERSION` macro.** Haybarn is deliberately
  ABI-compatible with upstream DuckDB. Only *artifacts* are renamed
  (`haybarn` CLI, `libhaybarn*` libraries) and *branding* is changed.
- **Trademark compliance is mandatory.** Product name is always "Haybarn", never
  "DuckDB Haybarn". DuckDB only appears descriptively ("powered by DuckDB"). No
  DuckDB logo or duck-derived marks. Keep the MIT `LICENSE` verbatim; keep
  `NOTICE` accurate. Full rules: the trademark guidelines at
  https://duckdb.org/trademark_guidelines.
- **One commit = one concern.** Prefer adding new files over editing upstream
  files. When you must edit an upstream file, keep it surgical.
- **The extension trust root is a single Haybarn key.** DuckDB-signed extensions
  must not load. Don't re-add upstream signing keys.

## The Haybarn commit stack (on top of `v1.5.2`)

| Concern | Key files |
|---|---|
| branding: artifact names | `src/CMakeLists.txt`, `tools/shell/CMakeLists.txt`, `tools/shell/rc/duckdb.rc`, `src/version.rc` |
| branding: CLI banner + user-agent | `tools/shell/shell.cpp`, `src/main/config.cpp` |
| signing: embedded extension keys | `src/main/extension/extension_helper.cpp` |
| signing: repository URLs | `src/include/duckdb/main/extension_install_info.hpp`, `src/main/extension_install_info.cpp` |
| ci: Haybarn workflows | `.github/workflows/haybarn-*.yml` (new files) |
| ci: neuter upstream triggers | upstream `.github/workflows/*.yml` |
| packaging: bundle outputs | `Makefile` |
| docs | `README.md`, `NOTICE`, `HAYBARN/`, this file |

## Building

```sh
make release          # -> build/release/haybarn, build/release/src/libhaybarn.*
```

For a build whose `version()` reports the release version (not a `git describe`
dev string), pin it the way CI does:

```sh
OVERRIDE_GIT_DESCRIBE=v1.5.2 make release
```

## Distribution

- **Binaries:** GitHub Releases under `Query-farm-haybarn/haybarn`, with
  `SHA256SUMS` + GPG + cosign signatures. OS-native code signing (Apple/Windows)
  is not wired up yet — TODOs are marked in `.github/workflows/haybarn-*.yml`.
- **Extensions:** Cloudflare R2, split across two buckets:
  - Core: `https://haybarn-extensions.query.farm/core` (this repo, via
    `haybarn-extensions.yml`).
  - Community: `https://haybarn-community-extensions.query.farm` (separate repo
    `Query-farm-haybarn/haybarn-community-extensions`, mirror of upstream's
    ~150 community extensions rebuilt against the Haybarn engine).
  Both signed with the SAME Haybarn extension key (`HAYBARN_EXTENSION_SIGNING_PK`
  secret; public half embedded in `extension_helper.cpp` as
  `HAYBARN_TRUST_ROOT`, referenced by both `public_keys[]` and
  `community_public_keys[]`). One trust root, two distribution channels.
- Release tags are `haybarn-v<version>`; the `haybarn-*.yml` workflows trigger on
  them. The upstream `OnTag.yml` (matches `v*.*.*`) is intentionally left alone —
  it never matches Haybarn tags.

## Pinning + rolling forward

Every drifting CI reference is **pinned** — runner OS, manylinux image, the
`duckdb/extension-ci-tools` SHA, pybind11. The pipeline is meant to be
reproducible; do not loosen pins to make a build green, adapt the *source* and
roll the pin forward deliberately. The where/why/how is in
[`HAYBARN/ROLL-FORWARD.md`](HAYBARN/ROLL-FORWARD.md).

## Extending the build-fork extensions

`iceberg`, `ducklake`, `delta`, and `httpfs` are Haybarn build-forks at
`Query-farm-haybarn/haybarn-<ext>`, so Haybarn-specific changes can land on top
of upstream over time. Procedure for adding a change to a fork and rolling the
core build to pick it up: [`HAYBARN/EXTENDING-FORKS.md`](HAYBARN/EXTENDING-FORKS.md).

## Related repos (Query-farm-haybarn org)

Haybarn is multi-repo. The Python client and the out-of-tree extensions live in
their own hard forks of the corresponding `duckdb/*` repos, each rebranded and
re-signed with the Haybarn key. See the project plan for the current list and
status.

## Local layout

- `/Users/rusty/Development/haybarn/haybarn` — this repo (the core fork).
- `/Users/rusty/Development/haybarn/duckdb-v1.5.2` — pristine upstream reference.
- `/Users/rusty/Development/haybarn/keys` — signing keys, **never committed**.
