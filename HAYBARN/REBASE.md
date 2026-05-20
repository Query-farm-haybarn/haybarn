# Rebasing Haybarn onto a new DuckDB release

Haybarn is a **hard fork** of `duckdb/duckdb`. Every Haybarn-specific change
lives in a small, curated commit stack on top of an upstream DuckDB release tag.
Adopting a new upstream release means rebasing that stack onto the new tag.

## Principles

- **One commit = one concern.** Keep the stack small and each commit focused, so
  conflicts are localized and self-documenting.
- **Prefer additive files over edits to upstream files.** New files never
  conflict. The Haybarn CI lives in new `.github/workflows/haybarn-*.yml` files;
  Haybarn docs live in `HAYBARN/`, `NOTICE`, and a rewritten `README.md`.
- **Keep edits to upstream files surgical** — version banner, artifact names,
  embedded signing key, repository URLs, Makefile bundle targets, and the
  neutered upstream workflow triggers. That is the entire upstream-file delta.

## One-time setup

```sh
git remote add upstream https://github.com/duckdb/duckdb.git
git config rerere.enabled true   # replay previous conflict resolutions
```

## Per-release procedure

Assume the current Haybarn branch is based on `v1.5.3` and we are moving to
`vX.Y.Z`.

```sh
git fetch upstream --tags

# Rebase the Haybarn commit stack onto the new upstream tag.
git checkout haybarn
git rebase --onto vX.Y.Z v1.5.3 haybarn
```

Resolve conflicts commit-by-commit. Likely conflict sites, by Haybarn commit:

| Haybarn commit                          | Files to watch |
|-----------------------------------------|----------------|
| branding: rename artifacts              | `src/CMakeLists.txt`, `tools/shell/CMakeLists.txt`, `tools/shell/rc/duckdb.rc`, `src/version.rc` |
| branding: CLI banner and user-agent     | `tools/shell/shell.cpp`, `src/main/config.cpp` |
| signing: replace embedded keys          | `src/main/extension/extension_helper.cpp` |
| signing: repoint repositories           | `src/include/duckdb/main/extension_install_info.hpp`, `src/main/extension_install_info.cpp` |
| ci: neuter upstream triggers            | upstream `.github/workflows/*.yml` (re-run the neutering if upstream added workflows) |
| packaging: rename bundle outputs        | `Makefile` |

`git rerere` will auto-replay resolutions it has seen before.

## After the rebase

1. Update the embedded version references that mention the previous base (`1.5.3`):
   - the `OVERRIDE_GIT_DESCRIBE` default in the `haybarn-*.yml` workflows
   - the CLI banner literal in `tools/shell/shell.cpp` (if hard-coded)
   - `README.md` ("built from DuckDB vX.Y.Z")
   - `NOTICE` (modification list, if it changed)
2. Build and run the verification steps (see the project plan's *Verification*
   section): `make release`, check the banner and `SELECT version()`, confirm
   the extension trust root.
3. Check whether upstream added any new `.github/workflows/*.yml` with `push` /
   `pull_request` triggers and neuter them too.
4. Tag the result `haybarn-vX.Y.Z` to trigger the Haybarn release CI.

## Why a hard fork (not a submodule overlay)

The hard fork lets Haybarn inherit DuckDB's battle-tested build matrix and tree
structure directly, and run its own CI in parallel. The cost — forward-porting
the stack each release — is kept low by the small, disciplined commit stack
described above.
