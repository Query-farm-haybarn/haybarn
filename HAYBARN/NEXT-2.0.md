# Haybarn on DuckDB 2.0

This branch is the development base for Haybarn AI work. It is not a release
branch and must not replace the stable DuckDB 1.5.5-based Haybarn distribution
until DuckDB 2.0 is released and the deferred distribution work below is done.

## Current base

- Branch: `next-2.0`
- Upstream: `upstream/v2.0-cyanoptera`
- Upstream base: `c65ca930b9fe39b2e8d8ed8821018dca650965f4` (2026-10-12)
- Haybarn patch stack: preserved through an upstream merge; 3,107 incoming
  commits since the previous `dee7ed975e` merge
- Local qualification: see the October refresh results below

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

The first `ask` implementation should be a one-shot `.ask` command. The
catalog-command discovery and dispatch mechanism from DuckDB PR #24793 is
already carried on this branch, with shell tests. That mechanism keeps command
registration in SQL-visible catalog functions and avoids exposing the shell's
internal `ShellState` as extension ABI.

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

## September validation

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

## October upstream refresh

The refresh merges upstream `v2.0-cyanoptera` at `c65ca930b9fe` into
`next-2.0`, starting from Haybarn `70c7bf7a0644`. The stable `haybarn` branch
and VGI's 1.5.5 submodule remain separate.

The merge preserves the Haybarn shell, library names, trust root, repository
layout, npm extension discovery, HTTP cancellation/retry changes, and INSTALL
version pins. Upstream moved dynamic installation into
`extension_install_dynamic.cpp`; pin persistence and conflict checks now live
there. Haybarn's repositories do not fall back to upstream mirrors, which serve
different binaries and signatures.

Inline named options for table-in/out now go through upstream's signature and
keyword-option validation after the input-column overload is chosen. Regression
tests cover lateral input, boolean option casting, duplicate/unknown options,
and rejection of correlated option values. Managed HTTP and local installation
tests cover pin persistence, conflicts, HTTP 304, and FORCE INSTALL unpinning.

Upstream's obsolete bundle/gather Make targets were removed with its static
library refactor. The engine now builds consolidated static archives and a
separate loadable-extensions component. Release packaging still needs the
Haybarn adaptation below.

### Local qualification (October 13)

Validated on macOS arm64 with AppleClang 17, Ninja, and the debug build's
assertions and sanitizers. `cmake --build build/debug --parallel 4` succeeds.
The local build includes core_functions, parquet, json, icu, and autocomplete.
The published extension smoke configuration remains separate.

- Focused C++ suite: 21 cases / 647 assertions pass, covering table functions,
  HTTP retry budgets/transports, installation pins, and user-agent branding.
- Named-argument/keyword-option and PostgreSQL catalog SQL: 3 cases /
  258 assertions pass. Install-version SQL: 2 cases / 9 assertions pass.
- The PEG load-statement SQL case skips because this build enables extension
  autoloading; it still needs a build with autoloading disabled.
- Shell basics and catalog dot commands: 158 passed and 1 skipped initially;
  all 8 `.schema` failures passed on rerun after adding autocomplete, which
  supplies upstream's `format_sql`. No shell code change was needed.
- Both ordinary and explicit-registration static-link smoke binaries pass.
- `make extension-patch-check` passes for all 18 configured extensions.
- Formatting and whitespace checks pass for the merge-resolution files.
  Extension entries were re-emitted from the generator while retaining the
  upstream extension metadata; no external-extension metadata was requalified.

Reproduce the targeted engine checks with `BUILD_DIR=build/debug` and
`LOCAL_EXTENSION_REPO="$PWD/build/debug/repository"` set:

```sh
./build/debug/test/unittest '[tablefunction],[http_retry_budget],[http_transport_manager],Test user_agent'
./build/debug/test/unittest 'test/extension/test_function_named_args.test,test/extension/test_function_args_kwargs.test,test/sql/pg_catalog/sqlalchemy.test'
./build/debug/test/unittest 'test/extension/install_version.test,test/extension/install_version_validation.test'
./build/debug/test/static_link_smoke
./build/debug/test/static_link_explicit_smoke
.cache/prepare-venv/bin/python -m pytest tools/shell/tests/test_shell_dot_command.py tools/shell/tests/test_shell_basics.py --shell-binary build/debug/haybarn -q
make extension-patch-check
```

This qualifies the local merge and affected Haybarn behaviors. The full upstream
test suite, other platforms, release artifacts, and external extension builds
remain unqualified. The separate extension-CI-tools branch was inspected but
was not refreshed or remotely exercised in this pass.

## Deferred before a 2.0 release

- Adapt the new release/artifact scripts to Haybarn CLI and library names,
  consolidated static archives, and explicit loader/extension registration.
  The old `BundleStaticLibs.yml` and bundle/gather Make targets no longer exist.
- Update the release, extension-publish, PyPI, npm, image, and documentation
  defaults that intentionally still pin the stable v1.5.5 distribution.
- Re-pin and validate every out-of-tree extension against the final DuckDB 2.0
  release commit and ABI.
