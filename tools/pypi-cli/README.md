# `haybarn-cli` on PyPI

Run [Haybarn](https://github.com/Query-farm-haybarn/haybarn) — an
independent derived distribution of [DuckDB](https://duckdb.org) —
directly from PyPI:

```sh
uvx haybarn-cli -c "SELECT 'powered by DuckDB' AS haybarn;"
# or
pipx run haybarn-cli -c "SELECT 'powered by DuckDB' AS haybarn;"
```

## What this is

`haybarn-cli` is a binary-distribution package. Each PyPI wheel embeds
the pre-built `haybarn` binary for one platform, tagged so `pip` / `uv`
auto-select the correct one:

- `manylinux_2_28_x86_64` — glibc-based Linux on x86_64
- `manylinux_2_28_aarch64` — glibc-based Linux on aarch64
- `musllinux_1_2_x86_64` — Alpine / musl Linux on x86_64
- `musllinux_1_2_aarch64` — Alpine / musl Linux on aarch64
- `macosx_11_0_x86_64` — macOS 11+ on Intel
- `macosx_11_0_arm64` — macOS 11+ on Apple Silicon
- `win_amd64` — 64-bit Windows

The Python shim (`haybarn_cli:main`) `os.execv`s into the bundled
binary, so signals and exit codes propagate naturally.

## Versions

- `uvx haybarn-cli` — latest stable.
- `uvx haybarn-cli@1.5.2rc7` — pin to a specific release candidate.
  (PEP 440 normalizes `1.5.2-rc7` → `1.5.2rc7`.)

## Related

- **`haybarn`** (npm) — same binary, run via `npx haybarn`.
- **`haybarn-python`** (PyPI, future) — Python *library* with native
  bindings (`import haybarn as duckdb`). Different package; this one
  is just the CLI.

## Trademark

Haybarn is an independent derived distribution of DuckDB published by
[Query Farm LLC](https://query.farm). Not affiliated with or endorsed
by the DuckDB Foundation. DuckDB is a trademark of the DuckDB Foundation.
