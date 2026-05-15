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
| runner OSes (`ubuntu-24.04`, `macos-15`, `windows-2022`) | all three `haybarn-*.yml` workflows + `haybarn-python.yml` | GitHub silently bumps `*-latest` aliases (newer toolchains → new compiler strictness surfaces, e.g. the `pybind11` `auto&` issue) |
| manylinux image tag (`manylinux_2_28:2024.10.07-1`) | `haybarn-release.yml` (the `docker run` line) and `pyproject.toml` `[tool.cibuildwheel]` (`manylinux-*-image`) in haybarn-python | the bare `manylinux_2_28` tag resolves to whatever's `latest` |
| extension-ci-tools wrapper | `.github/workflows/_extension_distribution.yml` (`uses:` line + `ci_tools_version:`) — a SHA, not the `v1.5-variegata` branch ref | branch refs move; the SHA doesn't |
| pybind11 build dependency (`==2.13.6`) | `pyproject.toml` in haybarn-python — both `[build-system].requires` and the dev/test groups | open upper bound resolves to latest at pip-install time |
| cibuildwheel (`@v2.21`), setup-uv (`@v5`), setup-python (`@v5`), checkout (`@v4`) | workflows | already pinned; rev majors deliberately |

Not pinned by us (deliberately): the `external/duckdb` submodule gitlink in
`haybarn-python` is a SHA — it tracks the Haybarn core fork's `haybarn` branch
HEAD and gets bumped explicitly when we want to.

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
