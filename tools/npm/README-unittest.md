# `haybarn-unittest` on npm

The [Haybarn](https://github.com/Query-farm-haybarn/haybarn) test runner —
DuckDB's `unittest` binary, rebranded — runnable directly from npm:

```sh
npx haybarn-unittest --test-dir . --list-tests
npx haybarn-unittest --test-dir path/to/extension test/sql/my_test.test
```

## What this is

`haybarn-unittest` is a meta-package that depends on per-platform native
binaries:

- `@haybarn/unittest-linux-x64`
- `@haybarn/unittest-linux-arm64`
- `@haybarn/unittest-linux-x64-musl`
- `@haybarn/unittest-linux-arm64-musl`
- `@haybarn/unittest-darwin-x64`
- `@haybarn/unittest-darwin-arm64`
- `@haybarn/unittest-win32-x64`

Each leaf carries one `haybarn-unittest` binary. npm installs only the leaf
matching your platform (via the `os` / `cpu` / `libc` fields). The
meta-package's shim resolves to that leaf and execs the binary with your
arguments.

It runs SQL logic (`.test`) files against the Haybarn engine — point it at
your own test directory with `--test-dir`. The binary is built so it launches
from any working directory; pass `--test-dir <dir>` to tell it where your
tests live.

No postinstall scripts. No network calls after `npm install`. Works behind
corporate proxies and in sandboxed CI.

## Versions

- `npx haybarn-unittest` — latest stable release.
- `npx haybarn-unittest@rc` — most recent release candidate.
- `npx haybarn-unittest@1.5.4` — pin a specific version.

## Trademark

Haybarn is an independent derived distribution of DuckDB published by
[Query Farm LLC](https://query.farm). Not affiliated with or endorsed by
the DuckDB Foundation. DuckDB is a trademark of the DuckDB Foundation.
