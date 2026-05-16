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
- **When you change a user-facing engine string, update the tests that assert it.**
  We have learned this the hard way more than once. Engine error wording in
  `src/main/...`, banner text, CLI prompt — there are matching asserts in
  `test/sql/**/*.test`, `test/api/test_api.cpp`, and `tools/shell/tests/*.py`
  that must move together. Sample failures we've hit: `test_shell_basics.py::
  test_open_non_database` asserting `"not a valid DuckDB database file"` and
  `test/api/test_api.cpp:569,576` asserting `ex.what()` contains `"DuckDB"`.
  Branding sweeps have multi-language test surface.

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
  `SHA256SUMS` + detached GPG signature + GitHub SLSA build-provenance
  attestations (each artifact bound to its commit/workflow/run; verified via
  `gh attestation verify <file> --repo Query-farm-haybarn/haybarn`).
  OS-native code signing (Apple/Windows) is not wired up yet — TODOs are marked
  in `.github/workflows/haybarn-*.yml`.
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

## CI infrastructure

The Linux build environment is centrally maintained:

- **Pre-built images on GHCR** at `ghcr.io/query-farm-haybarn/haybarn-linux_<arch>-{base,rust,full}:v1.5.2`.
  Built from `Query-farm-haybarn/haybarn-extension-ci-tools/docker/<arch>/Dockerfile`
  by `.github/workflows/publish-build-images.yml` in that repo. 12 images
  (4 archs × 3 toolchain variants). Public packages.
- Consumers — `haybarn-release.yml` here, `haybarn-extensions.yml` here, and
  `haybarn-community-extensions/build.yml` — `docker pull` these instead of
  `docker build`-ing inline. Saves ~5–8 min × 4 Linux archs per build.
- Variant selection: `base` (no toolchains), `-rust` (Rust toolchain),
  `-full` (rust + go + fortran + parser_tools + unixodbc + multimedia).
  Engine release uses `base`; core extensions use `full` (delta/ducklake
  need Rust; odbc_scanner needs unixodbc).
- macOS / Windows / wasm jobs still run native on GH runners — no Docker.

ccache is wired through R2 (`http://haybarn-vcpkg-cache.rusty-bb6.workers.dev/ccache`)
for cross-leg and cross-repo hits:

- **Linux**: ccache 4.13.6 baked into the Phase A images (musl-static binary
  from upstream GitHub release).
- **macOS**: Homebrew ships 4.13+, works as-is.
- **Windows + wasm**: `hendrikmuhs/ccache-action` installs 4.9.1 from
  chocolatey/apt, whose HTTP backend silently fails bearer-auth PUTs. The
  reusable workflow drops a 4.13.6 binary over the installed copy after
  the action runs.

The R2 bucket holds both vcpkg binaries and ccache objects under different
key prefixes. The bearer token is `HAYBARN_VCPKG_TOKEN` (org-level secret).

## Distribution / release flow

- Release tag pattern: `haybarn-v<version>` (e.g. `haybarn-v1.5.2-rc6`). Fires
  `haybarn-release.yml` (engine binaries) and `haybarn-extensions.yml` (core
  extensions), and the same tag on each downstream client repo fires their
  workflows.
- Engine release artifacts: `release/` directory uploaded to GH Releases by
  `haybarn-release.yml`, which also attaches a SLSA build-provenance
  attestation (`actions/attest-build-provenance`) to every artifact at build
  time. The `Haybarn Publish` workflow runs on `workflow_run` after Release
  succeeds, doing `SHA256SUMS` + GPG-detach-sign and creating the GitHub
  Release. (cosign `sign-blob` was dropped in rc7 — the attestation supersedes
  it and is verifiable against this repo specifically, whereas the cosign
  recipe had an unpinnable `.*` identity regex.)
- **GPG key gotcha**: the `HAYBARN_GPG_PRIVATE_KEY` org secret is stored
  hex-encoded (`gpg --export-secret-keys ... | xxd -p`), NOT ASCII-armored.
  The publish workflow probes 6 shapes (armored, armored-with-`\n`-escapes,
  base64-of-binary, base64-of-armored, hex, raw) and imports the first that
  works. Don't re-store the secret unless rotating.
- **R2 secret name oddity**: the actual access-key-secret is stored under
  `R2_SECRET_KEY_ID` (the `_ID` suffix is a misnomer; the value is the SECRET
  half of the access pair). `R2_ACCESS_KEY_ID` is the ID. Both at org level.
- Tag-triggered runs of `haybarn-extensions.yml` are in `dry_run` mode by
  default — actual R2 deploys only happen on `workflow_dispatch` with
  `deploy=true`. (haybarn-community-extensions deploys-on-every-push.)

## Extending the build-fork extensions

`iceberg`, `ducklake`, `delta`, and `httpfs` are Haybarn build-forks at
`Query-farm-haybarn/haybarn-<ext>`, so Haybarn-specific changes can land on top
of upstream over time. Procedure for adding a change to a fork and rolling the
core build to pick it up: [`HAYBARN/EXTENDING-FORKS.md`](HAYBARN/EXTENDING-FORKS.md).

## Related repos (Query-farm-haybarn org)

Haybarn is multi-repo. Each is pinned by SHA where another consumes it.

| Repo | Purpose | Tag-trigger |
|---|---|---|
| `haybarn` (this) | Engine fork, core extensions config, in-tree extensions | `haybarn-v*` |
| `haybarn-extension-ci-tools` | Fork of `duckdb/extension-ci-tools` with vcpkg-token + GHCR + ccache 4.13.6 patches | none (consumed by SHA pin) |
| `haybarn-community-extensions` | Mirror of `duckdb/community-extensions` rebuilt against this engine | push to `main` (build), workflow_dispatch (deploy) |
| `haybarn-python` | Python wheels — fork of `duckdb-python` | `haybarn-v*` |
| `haybarn-jdbc` | JDBC jar — fork of `duckdb-java` | `haybarn-v*` |
| `haybarn-node-neo` | Node bindings — fork of `duckdb-node-neo` | `haybarn-v*` |
| `haybarn-iceberg`, `haybarn-ducklake`, `haybarn-delta`, `haybarn-httpfs` | Build-forks for the listed core extensions | consumed by core extension build via SHA pin |
| `haybarn-vcpkg-worker` | Cloudflare Worker fronting R2 for vcpkg + ccache caches | manual deploy |
| `haybarn-org-profile` | Org-level docs / landing | n/a |

## Recent state (as of 2026-05-16)

Current rc series: **`haybarn-v1.5.2-rc7`**. Major work this cycle:

- SLSA build-provenance attestations added to `haybarn-release.yml` (all 4 jobs)
  via `actions/attest-build-provenance@v2`; cosign `sign-blob` dropped from
  `haybarn-publish.yml` along with the misleading `.*` identity-regex recipe
  in the release notes. GPG signature retained for the traditional audience.

Earlier (rc6) work this series:

- Two-bucket distribution split: core (`/core` path on `haybarn-extensions.query.farm`)
  vs community (own subdomain `haybarn-community-extensions.query.farm`).
- Pre-built GHCR build-environment images for all Linux platforms (3 toolchain variants × 4 archs).
- Community-extensions repo bootstrapped with `waddle` smoke extension; first
  end-to-end validation deployed 9 platform binaries to R2 and verified
  anonymous HTTP fetch.
- ccache HTTP backend bearer-auth fixed across all platforms (wasm + Windows
  were on broken 4.9.1; now 4.13.6 everywhere).
- Publish workflow's GPG key import made resilient to whatever shape the
  secret was stored in (it turned out to be hex).
- Engine release flow now also pulls Phase A images instead of inline
  `docker build` + runtime tool installs.

What's known broken / not yet done: see `~/.claude/projects/.../memory/haybarn-status.md`
for the latest "pending" list. Engine client repos (`haybarn-jdbc`,
`haybarn-node-neo`) need their submodule bumps + first tag pushes; PyPI/NPM
publishing for haybarn-python is gated on a workflow_dispatch with
`publish=pypi`.

## Local layout

- `/Users/rusty/Development/haybarn/haybarn` — this repo (the core fork).
- `/Users/rusty/Development/haybarn/duckdb-v1.5.2` — pristine upstream reference.
- `/Users/rusty/Development/haybarn/keys` — signing keys, **never committed**.
