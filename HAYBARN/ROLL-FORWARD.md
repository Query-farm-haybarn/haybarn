# Rolling forward Haybarn's pinned toolchain

Haybarn's CI deliberately **pins every moving reference** so that re-running an
old commit produces the same wheels/binaries on the same toolchain it was
released with. This is the trade — reproducibility at the cost of needing to
roll these refs forward manually when we want newer compilers, runner images,
or library versions.

This doc lists what's pinned, where, and how to refresh each one.

## What's pinned

| Component | Where | Why |
|---|---|---|
| runner OSes (`ubuntu-24.04`, `macos-15`, `windows-2022`) | all three `haybarn-*.yml` workflows + `haybarn-python.yml` + `haybarn-node-neo.yml` + `haybarn-jdbc.yml` | GitHub silently bumps `*-latest` aliases (newer toolchains → new compiler strictness surfaces, e.g. the `pybind11` `auto&` issue) |
| manylinux image tag (`manylinux_2_28:2026.05.13-1`) and musllinux (`musllinux_1_2:2026.05.13-1`) | `haybarn-release.yml`, `pyproject.toml` (`manylinux-*-image` + `musllinux-*-image`) in haybarn-python, `haybarn-node-neo.yml`, `haybarn-jdbc.yml`, both Dockerfiles in `haybarn-extension-ci-tools/docker/` | bare `manylinux_2_28` / `musllinux_1_2` tags resolve to whatever's `latest`; pypa publishes new dated tags every few days |
| extension-ci-tools wrapper | `.github/workflows/_extension_distribution.yml` (`uses:` line + `ci_tools_version:`) — a SHA, not the `v1.5-variegata` branch ref | branch refs move; the SHA doesn't |
| pybind11 build dependency (`==2.13.6`) | `pyproject.toml` in haybarn-python — both `[build-system].requires` and the dev/test groups | open upper bound resolves to latest at pip-install time |
| cibuildwheel (`@v2.21`), setup-uv (`@v5`), setup-python (`@v5`), checkout (`@v4`) | workflows | already pinned; rev majors deliberately |

Not pinned by us (deliberately): the `external/duckdb` submodule gitlink in
`haybarn-python` is a SHA — it tracks the Haybarn core fork's `haybarn` branch
HEAD and gets bumped explicitly when we want to.

`haybarn-rust` pins the engine the same way, in two coupled places: the
`crates/libduckdb-sys/duckdb-sources` submodule gitlink (a `haybarn-v*` commit on
the core fork) **and** the committed, regenerated
`crates/libduckdb-sys/duckdb.tar.gz` amalgamation that the `bundled` build
actually compiles. On an engine roll: bump the submodule to the new
`haybarn-vX.Y.Z-rcN`, re-run `crates/libduckdb-sys/update_sources.py` to
regenerate the amalgamation (which re-embeds the Haybarn trust root), and bump
the crate's `1.10503.x-rc.N` version — full procedure in that repo's `CLAUDE.md`.
Its CI runs on `*-latest` runners (not pinned), so the runner-OS row above does
not apply to it.

The **Go client** pins the engine differently again — see
[Porting & rolling the Go client](#porting--rolling-the-go-client) below.

## Porting & rolling the Go client

The Go client is **two repos** (upstream split, mirrored):

- [`Query-farm-haybarn/haybarn-go-bindings`](https://github.com/Query-farm-haybarn/haybarn-go-bindings)
  — low-level cgo bindings; fork of `duckdb/duckdb-go-bindings`.
- [`Query-farm-haybarn/haybarn-go`](https://github.com/Query-farm-haybarn/haybarn-go)
  — the `database/sql` driver; fork of `duckdb/duckdb-go`. Depends on the bindings.

### How it pins the engine (this is the unusual part)

Unlike `haybarn-rust` (which compiles a vendored amalgamation), `haybarn-go-bindings`
**does not compile the engine at all**. It commits **pre-built static-library
archives** under `lib/<platform>/` (`libhaybarn_static.a` + the extension and
third-party `.a`s + `duckdb.h`), one set per platform (darwin-amd64/arm64,
linux-amd64/arm64, windows-amd64), ~110 MB each, no Git LFS. cgo links them
(`-lhaybarn_static`, build-tag-selected per platform in `lib/*/prebuilt.go`).

Those archives are **fetched from a Haybarn engine GitHub release** — the
`static-libs-*.zip` assets the engine's `BundleStaticLibs.yml` produces (wired
into `haybarn-release.yml` as a `workflow_call` job). The Haybarn trust root and
`haybarn-extensions.query.farm` URLs are baked **inside `libhaybarn_static.a`** at
engine-build time, so "Haybarn-ness" is inherited automatically by linking it —
no Go-side change embeds it.

**Engine-side prerequisite (must hold before rolling the client):** the target
engine release must actually carry the five `static-libs-*.zip` assets. They are
produced by the `static-libs` (`Static libraries (Go client)`) jobs in
`haybarn-release.yml` → attached to the release by `haybarn-publish.yml` (they
ride the standard `haybarn-*` artifact path). If a release predates that wiring,
re-run its `Haybarn Release` and `Haybarn Publish`.

### Versioning (does NOT follow `haybarn-v*`)

The Go module proxy **requires bare `vMAJOR.MINOR.PATCH` tags**, so the org-wide
`haybarn-v*` tag convention does not apply here. Tags mirror upstream's
engine-encoding scheme:

| Engine | bindings tag | driver tag |
|---|---|---|
| v1.5.4 | `v0.10504.x` (+ `lib/<plat>/v0.10504.x`) | `v2.10504.x` |
| v1.5.5 | `v0.10505.x` | `v2.10505.x` |

The trailing `.x` is the Haybarn patch iteration on that engine version (e.g. a
bindings-only fix that needs no engine roll bumps `v0.10504.0` → `v0.10504.1`).
There is **no registry publish step** — pushing the git tag is the release; the
module proxy resolves it.

### Per-release roll procedure

Run **after** a new engine `haybarn-vX.Y.Z-rcN` release exists with its
`static-libs-*.zip` assets (see prerequisite above). `NN` below = `Y` and `Z`
zero-padded, e.g. v1.5.5 → `0.10505` / `2.10505`.

1. **Bindings — re-vendor the binaries.** In `haybarn-go-bindings`:
   - Bump `HAYBARN_VERSION` (and `HAYBARN_REPO` if it ever moves) in the `Makefile`
     to the new engine release tag.
   - Run the **`Fetch and Push Libs`** workflow (`.github/workflows/fetch.yml`),
     or locally per platform:
     ```sh
     make fetch.static.libs PLATFORM=darwin-arm64  FILENAME=static-libs-osx-arm64 COPY_HEADER=1
     make fetch.static.libs PLATFORM=darwin-amd64  FILENAME=static-libs-osx-amd64
     make fetch.static.libs PLATFORM=linux-amd64   FILENAME=static-libs-linux-amd64
     make fetch.static.libs PLATFORM=linux-arm64   FILENAME=static-libs-linux-arm64
     make fetch.static.libs PLATFORM=windows-amd64 FILENAME=static-libs-windows-mingw
     ```
     Commit the refreshed `.a`s + `duckdb.h`. **Never carry upstream DuckDB
     binaries** — verify with
     `strings lib/<plat>/libhaybarn_static.a | grep haybarn-extensions.query.farm`.
   - If `duckdb.h` changed (new C-API surface), reflect it in the Go bindings.
2. **Bindings — tag.** `scripts/release.sh v0.105NN.0` (re-entrant; it tags the
   five `lib/<plat>/...` submodules + root, and pauses once for a `go.mod`/`go.sum`
   commit — commit it to `haybarn` directly and re-run, no PR needed since we push
   directly).
3. **Driver — bump + tag.** In `haybarn-go`:
   `go get github.com/Query-farm-haybarn/haybarn-go-bindings@v0.105NN.0`,
   `go mod tidy`, bump `HAYBARN_VERSION` in its `Makefile`, update the README
   version table, commit, then `git tag v2.105NN.0 && git push origin v2.105NN.0`.
4. **Verify.** A fresh consumer is the real test:
   ```sh
   go get github.com/Query-farm-haybarn/haybarn-go/v2@v2.105NN.0
   # sql.Open("haybarn", "") and sql.Open("duckdb", "") -> SELECT version() == vX.Y.Z
   # INSTALL inet; LOAD inet;  -> resolves from haybarn-extensions.query.farm,
   #   verified against the Haybarn trust root (a non-bundled ext = real proof).
   ```
   Plus the repos' own `Tests` matrices (5 platforms each).

### Gotchas (learned 2026-06-26, first port)

- **The two opt-in alt-lib CI jobs are the ones that bite.** The default
  *Pre-Built Libs* / *Main* jobs (what ships) just work. The *Static Lib* and
  *Dynamic Lib* jobs hardcode lib names — keep them Haybarn: `-lhaybarn_static`,
  `cgo_dynamic.go` `-lhaybarn`, and `libhaybarn-*` shared-lib download filenames
  (the dynamic job pulls the engine's `libhaybarn-<plat>.zip` shared libs).
- **The driver CI tests the *published* bindings, not the branch.** A bindings
  fix that affects linking (e.g. `cgo_dynamic.go`) won't green the driver until
  it is in a *released* bindings tag and the driver's `go.mod` is bumped to it —
  hence the `v0.10504.1` / `v2.10504.1` patch pair on first port.
- **Submodules can stay put for a root-only fix.** A change in the bindings root
  module (e.g. `cgo_dynamic.go`) only needs a new **root** tag; the five
  `lib/<plat>/...` submodule tags can stay at the prior patch.
- **Engine `BundleStaticLibs` references the renamed binary.** Its Linux "Print
  platform" step runs `./build/release/haybarn` (not `duckdb`) — same artifact-
  rename class of bug as everywhere else.

Full structural notes live in each repo's `CLAUDE.md`.

## Known un-pinned bits (drift sources we accept)

These are pinnable in principle but cost more than they're worth right now.
Worth being explicit about them so a future "why did this break" investigation
doesn't go hunting:

- **`brew install <pkg>` on macOS** (e.g. `brew install ninja ccache` in
  `haybarn-release.yml`, `brew install ccache` in `pyproject.toml`'s
  cibuildwheel `before-build`). Homebrew doesn't keep historical formula
  versions reachable from `brew install`; you get whatever the main tap has
  at install time. The runner image is pinned (`macos-15`) but the packages
  installed onto it are not. If we ever need true reproducibility here, the
  path is to download release tarballs from each tool's GitHub releases page
  and unpack them rather than `brew install`.
- **`choco install <pkg>` on Windows** (`choco install ccache` in cibuildwheel
  `before-build`). Same story — Chocolatey supports `--version=X.Y.Z` for some
  packages but not all, and historical versions aren't always retained.
- **`python-version: '3.12'`** in `setup-python` — resolves to whichever 3.12.x
  is on the runner. Patch versions are stable enough that we accept this; pin
  to `3.12.7` etc. if a specific patch ever matters.
- **GitHub Actions referenced by major version** (`@v4`, `@v5`). SHA-pinning
  every action is stricter but introduces meaningful Dependabot/manual upkeep.
  We accept major-pinning for now.

What we *do* pin on macOS/Windows: the runner image (`macos-15`,
`windows-2022`), so the toolchain (Xcode / MSVC / system libs) is fixed. That
catches the biggest class of drift; the brew/choco packages above are
secondary.

## How to roll forward

### Quick refresh of all moving refs

```sh
# Current resolved values — copy these into the configs (see exact paths above)
echo "macos-latest currently maps to:"
gh api repos/actions/runner-images/contents/images/macos --jq '.[].name' \
  | grep -E '^macos-[0-9]+-Readme\.md$' | sort -V | tail -3

echo "extension-ci-tools v1.5-variegata HEAD SHA:"
gh api repos/duckdb/extension-ci-tools/commits/v1.5-variegata --jq '.sha'

# Pick a recent manylinux_2_28 image tag (browse https://quay.io/repository/pypa/manylinux_2_28_x86_64?tab=tags)
# and confirm the same tag exists for the aarch64 variant:
curl -sSI -o /dev/null -w "%{http_code}\n" \
  "https://quay.io/v2/pypa/manylinux_2_28_aarch64/manifests/<TAG>"

# Current latest pybind11 on PyPI:
pip index versions pybind11
```

### When to roll forward

- **Security**: if the pinned manylinux/runner image is end-of-life, refresh.
- **New Python interpreter**: cibuildwheel adds CPython versions over time; a
  newer cibuildwheel + newer images unlock those builds.
- **Bug fixes in pybind11 / extension-ci-tools**: refresh to pick up fixes when
  needed.
- **Otherwise**: don't. The pipeline is reproducible and that's the point.

### Refresh procedure

1. Re-resolve each of the moving refs (commands above).
2. Update every pin in one commit titled `ci: roll forward pinned toolchain`.
3. Dispatch the release + extensions + python builds (`workflow_dispatch`).
4. Expect new compiler-strictness surprises — fix them in source, not by
   loosening the pin. The pin is the contract; the source adapts.
5. After all three pipelines pass on the new pins, tag a new `haybarn-v*-rc`
   to exercise the full release flow.

## Why pinning matters here

Haybarn was bitten by every kind of drift in its first build cycle:
- `ubuntu-latest`/`macos-latest` moved to newer GCC/Clang that rejected
  pybind11 idioms upstream had used without issue.
- `manylinux_2_28` (untagged) pulled a newer base image with GCC 14.
- `v1.5-variegata` is a moving branch on `duckdb/extension-ci-tools`; bug
  fixes there could change build behaviour mid-release.

These are all *legitimate* drift, but they break the assumption "the code that
shipped should build the same way tomorrow." Pinning makes that assumption
hold; this doc is how we break the pins on purpose.

## Roll-forward log

Record each roll-forward here so a future "why is this pin so old" investigation
has the context.

### 2026-05-15 — bump manylinux + musllinux from `2024.10.07-1` to `2026.05.13-1`

- **What**: All `manylinux_2_28_{x86_64,aarch64}` and `musllinux_1_2_{x86_64,aarch64}`
  pins moved forward ~19 months across the seven config sites. Also pinned
  musllinux explicitly for the first time (previously cibuildwheel picked its
  own default, which had drifted to the same date as our manylinux pin —
  surprising and worth eliminating).
- **Why**: The original pin was just "whatever was current the day we wrote it"
  with no specific feature/bug rationale. After ~19 months the toolchain drift
  is huge; pulling forward keeps us closer to what wheel consumers actually
  have on their hosts.
- **Surfaced**: Re-enabling `odbc_scanner` in `haybarn_extensions.cmake` at the
  same time (separate fix — unixODBC headers now present in the newer manylinux
  base; old TODO comment removed). The `mysql_scanner` GCC 12 `unique_ptr` copy
  error from the old image *may* be gone in the newer toolchain (older GCC) or
  *may* be even stricter (likely newer GCC) — first run after the bump will
  tell. We adapt the source, not the pin (see "When to roll forward" rules).
- **Also fixed**: Added a `[[tool.cibuildwheel.overrides]]` block in
  haybarn-python's `pyproject.toml` so `*-musllinux*` wheels use `apk add` instead
  of `yum install` in their before-build. The unified `[tool.cibuildwheel.linux]`
  was wrong for Alpine-based musllinux and silently broke aarch64-musl wheels.
