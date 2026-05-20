# Haybarn

**Haybarn is an independent derived distribution of [DuckDB](https://duckdb.org), powered by DuckDB.**

Haybarn builds the DuckDB source into its own branded binaries, libraries, and a
signed extension ecosystem, with an independent release cadence. It is published
by Query Farm LLC.

> Haybarn is **not** affiliated with, sponsored by, or endorsed by the DuckDB
> Foundation or DuckDB Labs. DuckDB is a trademark of the DuckDB Foundation.
> See [NOTICE](NOTICE) for details.

> [!IMPORTANT]
> **Haybarn 1.5.3 is in release-candidate phase.** The current tag is
> `haybarn-v1.5.3-rc1`. Final `1.5.3` will arrive once the extension catalog
> has stabilised. Until then, install snippets below pin the `rc` channel
> explicitly. APIs and on-disk formats are inherited from upstream DuckDB
> v1.5.3 and will not change between rcs.
>
> Live build + release status across all Haybarn repos:
> **<https://haybarn-status.query.farm>**.

This Haybarn release line is built from **DuckDB v1.5.3**.

## What Haybarn ships

| Artifact | Name | Where |
|---|---|---|
| CLI | `haybarn` | [GitHub Releases](https://github.com/Query-farm-haybarn/haybarn/releases), npm (`@haybarn/cli-*`), PyPI (`haybarn-cli`) |
| Shared library | `libhaybarn.{so,dylib,dll}` | [GitHub Releases](https://github.com/Query-farm-haybarn/haybarn/releases) |
| Static library | `libhaybarn_static.a` | [GitHub Releases](https://github.com/Query-farm-haybarn/haybarn/releases) |
| Python bindings | `haybarn` | [`Query-farm-haybarn/haybarn-python`](https://github.com/Query-farm-haybarn/haybarn-python) (PyPI publish wiring in progress) |
| Node bindings | `@haybarn/node-neo` (planned) | [`Query-farm-haybarn/haybarn-node-neo`](https://github.com/Query-farm-haybarn/haybarn-node-neo) |
| JDBC driver | `haybarn-jdbc` (planned) | [`Query-farm-haybarn/haybarn-jdbc`](https://github.com/Query-farm-haybarn/haybarn-jdbc) |
| Core extensions | Haybarn-signed | `https://haybarn-extensions.query.farm/core` |
| Community extensions | Haybarn-signed, rebuilt against the Haybarn engine | `https://haybarn-extensions.query.farm/community` |

The C/C++ API, the `duckdb::` namespace, public headers (`duckdb.h`/`.hpp`), the
`DUCKDB_VERSION` macro, the extension platform string, the `.duckdb_extension`
file suffix, and the on-disk database format are **unchanged** from upstream
DuckDB — Haybarn is ABI- and file-format-compatible. What differs is the
branding, the artifact names, the extension trust root, the extension cache
directory, and the release/distribution pipeline.

## Installing the CLI

```sh
# npm (no install)
npx haybarn@rc

# PyPI (no install)
uvx haybarn-cli==1.5.3rc1          # or `pipx run haybarn-cli==1.5.3rc1`

# GitHub Releases — pick the zip for your OS/arch
https://github.com/Query-farm-haybarn/haybarn/releases
```

All three channels ship the same `haybarn` binary built from the same engine
commit. Once `1.5.3` final lands, `npx haybarn` and `uvx haybarn-cli` will work
without the `@rc` / `==…` suffixes.

## Python

The Python package and import name are both `haybarn`. Because the API surface
is identical to DuckDB's, migrating existing code is a one-line change:

```python
import haybarn as duckdb
```

For third-party code you cannot edit, an opt-in compatibility shim is available:

```python
import haybarn.compat   # registers `haybarn` as the `duckdb` module
import duckdb           # now resolves to Haybarn
```

> The `haybarn` library wheels are built green on a 20-leg
> (OS × Python version) matrix in `Query-farm-haybarn/haybarn-python`; the
> first `pip install haybarn` publish to PyPI is gated on a workflow_dispatch
> and is not yet live. The `haybarn-cli` PyPI project (a packaged CLI) is
> separate and already live.

## Extensions

Haybarn extensions install the same way as DuckDB's:

```sql
INSTALL iceberg;
LOAD iceberg;
```

They're served from `haybarn-extensions.query.farm` (core under `/core`,
community under `/community`) and signed with a single Haybarn RSA key.
**DuckDB-signed extensions will not load** against a Haybarn engine — the
trust roots are deliberately disjoint.

Extension binaries are cached under `~/.haybarn/extensions/` (not
`~/.duckdb/extensions/`).

## Distribution & supply chain

- **Binaries** are published on GitHub Releases with `SHA256SUMS` and a
  detached GPG signature (`HAYBARN/haybarn_release_signing.pub`).
- **SLSA build provenance attestations** are attached to every release artifact
  via `actions/attest-build-provenance`. Verify with:

  ```sh
  gh attestation verify haybarn_cli-linux-amd64.zip \
    --repo Query-farm-haybarn/haybarn
  ```

- **Extensions** are hosted on Cloudflare R2 behind
  `haybarn-extensions.query.farm`, fronted per-asset (every deployed artifact
  lives at an immutable URL keyed by version + git sha).
- OS-native code signing (Apple Developer ID + Windows Authenticode) is not yet
  wired up.

## Building from source

```sh
make release
```

This produces `build/release/haybarn` and `build/release/src/libhaybarn.*`.
See the upstream [DuckDB build documentation](https://duckdb.org/docs/dev/building/overview)
for prerequisites and build options — they apply unchanged.

## Repository layout

Haybarn is maintained as a **hard fork** of `duckdb/duckdb`. All Haybarn-specific
changes are kept as a small, curated commit stack on top of an upstream release
tag, so the delta from DuckDB is auditable and easy to forward-port. The rebase
procedure for adopting a new upstream release is documented in
[HAYBARN/REBASE.md](HAYBARN/REBASE.md).

Related repos under the [`Query-farm-haybarn`](https://github.com/Query-farm-haybarn)
org:

| Repo | Purpose |
|---|---|
| `haybarn` (this) | Engine fork, core extensions config, in-tree extensions |
| `haybarn-python` | Python bindings — fork of `duckdb-python` |
| `haybarn-node-neo` | Node bindings — fork of `duckdb-node-neo` |
| `haybarn-jdbc` | JDBC driver — fork of `duckdb-java` |
| `haybarn-iceberg`, `haybarn-ducklake`, `haybarn-delta`, `haybarn-httpfs` | Build-forks for those core extensions |
| `haybarn-community-extensions` | Mirror of `duckdb/community-extensions` rebuilt against the Haybarn engine |
| `haybarn-extension-ci-tools` | Fork of `duckdb/extension-ci-tools` with vcpkg + GHCR + ccache patches |

## License

Haybarn is distributed under the MIT License, the same license as DuckDB. The
upstream license is preserved verbatim in [LICENSE](LICENSE). See [NOTICE](NOTICE)
for the list of modifications Haybarn makes and the trademark attribution.
