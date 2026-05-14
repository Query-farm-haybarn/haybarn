# Haybarn

**Haybarn is an independent derived distribution of [DuckDB](https://duckdb.org), powered by DuckDB.**

Haybarn builds the DuckDB source into its own branded binaries, libraries, and a
signed extension ecosystem, with an independent release cadence. It is published
by Query Farm LLC.

> Haybarn is **not** affiliated with, sponsored by, or endorsed by the DuckDB
> Foundation or DuckDB Labs. DuckDB is a trademark of the DuckDB Foundation.
> See [NOTICE](NOTICE) for details.

This first Haybarn release is built from **DuckDB v1.5.2**.

## What Haybarn ships

| Artifact            | Name                                             |
|---------------------|--------------------------------------------------|
| CLI                 | `haybarn`                                        |
| Shared library      | `libhaybarn.{so,dylib,dll}`                      |
| Static library      | `libhaybarn_static.a`                            |
| Python package      | `haybarn` (on PyPI)                              |
| Core extensions     | Haybarn-signed, served from `haybarn.query.farm` |

The C/C++ API, the `duckdb::` namespace, public headers (`duckdb.h`/`.hpp`), and
the on-disk database and extension formats are **unchanged** from upstream
DuckDB — Haybarn is ABI-compatible. What differs is the branding, the artifact
names, the extension trust root, and the release/distribution pipeline.

## How Haybarn differs from DuckDB

- **Branding** — the CLI is `haybarn`, the libraries are `libhaybarn`, and the
  shell banner reads `Haybarn <version> — powered by DuckDB v<version>`.
- **Extension signing** — Haybarn embeds its own extension-signing public key
  and trusts *only* that key. DuckDB-signed extensions will not load; every
  Haybarn extension is signed with the Haybarn key and served from the Haybarn
  extension repository (`https://haybarn.query.farm/core`).
- **Distribution** — binaries are published on GitHub Releases with
  `SHA256SUMS`, detached GPG signatures, and cosign signatures. Extensions are
  hosted on Cloudflare R2.

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

## License

Haybarn is distributed under the MIT License, the same license as DuckDB. The
upstream license is preserved verbatim in [LICENSE](LICENSE). See [NOTICE](NOTICE)
for the list of modifications Haybarn makes and the trademark attribution.
