# `haybarn` on npm

Run [Haybarn](https://github.com/Query-farm-haybarn/haybarn) — an
independent derived distribution of [DuckDB](https://duckdb.org) — directly
from npm:

```sh
npx haybarn -c "SELECT 'powered by DuckDB' AS haybarn;"
```

## What this is

`haybarn` is a meta-package that depends on per-platform native binaries:

- `@haybarn/cli-linux-x64`
- `@haybarn/cli-linux-arm64`
- `@haybarn/cli-linux-x64-musl`
- `@haybarn/cli-linux-arm64-musl`
- `@haybarn/cli-darwin-x64`
- `@haybarn/cli-darwin-arm64`
- `@haybarn/cli-win32-x64`

Each leaf carries one `haybarn` binary. npm installs only the leaf matching
your platform (via the `os` / `cpu` / `libc` fields). The meta-package's
shim resolves to that leaf and execs the binary with your arguments.

No postinstall scripts. No network calls after `npm install`. Works behind
corporate proxies and in sandboxed CI.

## Versions

- `npx haybarn` — latest stable release.
- `npx haybarn@rc` — most recent release candidate.
- `npx haybarn@1.5.2` — pin a specific version.

## Trademark

Haybarn is an independent derived distribution of DuckDB published by
[Query Farm LLC](https://query.farm). Not affiliated with or endorsed by
the DuckDB Foundation. DuckDB is a trademark of the DuckDB Foundation.
