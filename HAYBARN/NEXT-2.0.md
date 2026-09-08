# Haybarn on DuckDB 2.0

This branch is the development base for Haybarn AI work. It is not a release
branch and must not replace the stable DuckDB 1.5.5-based Haybarn distribution
until DuckDB 2.0 is released and the deferred distribution work below is done.

## Current base

- Branch: `next-2.0`
- Upstream: `upstream/v2.0-cyanoptera`
- Upstream base: `a86336cd55` (2026-09-08)
- Haybarn patch stack: rebased on top of that base
- Local debug build: passing on macOS arm64

The stable `haybarn` branch and worktree remain on DuckDB 1.5.5.

## Extension CI

The `next-2.0` branch of `haybarn-extension-ci-tools` is based on current
upstream `main` and uses its reusable `build.yml` workflow. Haybarn's writable
vcpkg, asset, and ccache configuration and its R2/npm/PyPI publication scripts
are carried on top.

`haybarn-extensions.yml` uses that workflow to build and test a deliberately
small 2.0 smoke set containing parquet. Add `ask` to
`haybarn_extensions_next_2_0.cmake` after the extension repository exists.
Keep the old full extension list separate until all of its 1.5-specific fork
commits have been rebased and pinned for 2.0.

The CI-tools branch must be pushed before this engine branch because GitHub
must resolve the external reusable-workflow ref first. Pin the caller to a
commit SHA after the development workflow has passed remotely.

## AI shell integration

The first implementation should be a one-shot `.ask` command, not a second
interactive REPL. Port the catalog-command discovery and dispatch mechanism
from DuckDB PR #24793 onto this branch as an isolated commit, retaining its
shell tests. That mechanism keeps command registration in SQL-visible catalog
functions and avoids exposing the shell's internal `ShellState` as extension
ABI.

The initial `ask` extension can run its agent/tool loop through its existing
DuckDB `ClientContext` and return action rows for the shell to render. Start
with the existing `print` action. Add narrowly specified actions such as
`print_error` or `render_result` only when the MVP demonstrates a need for
them.

Do not port the full `ShellContext` interface from PR #22079 for the MVP. Its
terminal, renderer, interrupt, history, and nested-input methods create a much
larger shell ABI. Revisit a small input capability only if a later `.chat`
sub-REPL requires it.

Keep AI syntax out of the PEG SQL grammar. The PEG parser is useful to the
extension for validating or classifying generated SQL, but `.ask` is shell
command dispatch rather than SQL grammar.

Use `ask` as the extension/artifact name. `ai` is already used by a DuckDB
community extension and would create installation and catalog ambiguity.

## Validation completed

- Full debug build of the engine, shell, core functions, parquet, and unit-test
  binary.
- Haybarn CLI branding and DuckDB 2.0 version reporting.
- Extension install-version validation.
- Haybarn extension repository routing and trust behavior.
- User-agent branding.
- PEG parsing of extension load statements.
- PostgreSQL catalog compatibility functions.
- Serialization generation produces no additional changes.
- Changed files pass formatter and diff checks. The full-tree formatter reports
  success but currently emits an upstream `format.py` path-handling traceback.

## Deferred before a 2.0 release

- Adapt Haybarn's static-library artifact packaging to DuckDB 2.0's consolidated
  `Main.yml`; the old `BundleStaticLibs.yml` no longer exists.
- Update the release, extension-publish, PyPI, npm, image, and documentation
  defaults that intentionally still pin the stable v1.5.5 distribution.
- Re-pin and validate every out-of-tree extension against the final DuckDB 2.0
  release commit and ABI.
