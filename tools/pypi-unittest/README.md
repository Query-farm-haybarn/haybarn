# `haybarn-unittest` on PyPI

The [Haybarn](https://github.com/Query-farm-haybarn/haybarn) test runner —
DuckDB's `unittest` binary, rebranded — runnable directly from PyPI:

```sh
uvx haybarn-unittest --test-dir . --list
# or
pipx run haybarn-unittest --test-dir path/to/extension test/sql/my_test.test
```

## What this is

`haybarn-unittest` is a binary-distribution package. Each PyPI wheel embeds
the pre-built `haybarn-unittest` binary for one platform, tagged so `pip` /
`uv` auto-select the correct one:

- `manylinux_2_28_x86_64` — glibc-based Linux on x86_64
- `manylinux_2_28_aarch64` — glibc-based Linux on aarch64
- `musllinux_1_2_x86_64` — Alpine / musl Linux on x86_64
- `musllinux_1_2_aarch64` — Alpine / musl Linux on aarch64
- `macosx_11_0_x86_64` — macOS 11+ on Intel
- `macosx_11_0_arm64` — macOS 11+ on Apple Silicon
- `win_amd64` — 64-bit Windows

The Python shim (`haybarn_unittest:main`) `os.execv`s into the bundled
binary, so signals and exit codes propagate naturally.

It runs SQL logic (`.test`) files against the Haybarn engine — point it at
your own test directory with `--test-dir`. The binary launches from any
working directory; `--test-dir <dir>` tells it where your tests live.

## Versions

- `uvx haybarn-unittest` — latest stable.
- `uvx haybarn-unittest@1.5.3rc1` — pin to a specific release candidate.
  (PEP 440 normalizes `1.5.3-rc1` → `1.5.3rc1`.)

## Related

- **`haybarn-unittest`** (npm) — same binary, run via `npx haybarn-unittest`.
- **`haybarn-cli`** (PyPI) — the Haybarn CLI, run via `uvx haybarn-cli`.

## Trademark

Haybarn is an independent derived distribution of DuckDB published by
[Query Farm LLC](https://query.farm). Not affiliated with or endorsed
by the DuckDB Foundation. DuckDB is a trademark of the DuckDB Foundation.
