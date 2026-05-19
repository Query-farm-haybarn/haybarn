#
# Haybarn extension build configuration.
#
# This is the full set of extensions Haybarn builds, signs with the Haybarn
# extension-signing key, and serves from https://haybarn-extensions.query.farm/core.
#
# It is the set DuckDB's own CI builds, MINUS the extensions Haybarn does not
# ship: vortex, lance, motherduck.
#
# To build with this configuration:
#   EXTENSION_CONFIGS=.github/config/haybarn_extensions.cmake \
#   USE_MERGED_VCPKG_MANIFEST=1 BUILD_COMPLETE_EXTENSION_SET=1 make
#
# Extension *names* are deliberately unchanged from upstream — `INSTALL iceberg`
# etc. work exactly as with DuckDB. What makes these "Haybarn" extensions is
# that they are built against the Haybarn build of DuckDB and signed with the
# Haybarn key.

# --- In-tree extensions (built from this repo) -------------------------------
duckdb_extension_load(autocomplete)
duckdb_extension_load(core_functions)
duckdb_extension_load(icu)
duckdb_extension_load(json)
duckdb_extension_load(parquet)
duckdb_extension_load(tpcds)
duckdb_extension_load(tpch)

# --- Out-of-tree extensions, rebuilt from upstream ---------------------------
# These reuse the upstream GIT_URL + pinned GIT_TAG from the per-extension
# config files; only the build target (Haybarn DuckDB) and the signing key
# differ from upstream.
include("${EXTENSION_CONFIG_BASE_DIR}/avro.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/aws.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/azure.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/encodings.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/excel.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/fts.cmake")
# httpfs is a Haybarn build-fork (Query-farm-haybarn/haybarn-httpfs) so Haybarn
# changes can land on top of upstream over time. Same source as duckdb-httpfs
# v1.5.2 pin (13e18b3c) plus a NOTICE commit; pinned by explicit SHA — bump it
# when you want to roll forward (or pick up new Haybarn commits on the fork's
# haybarn branch).
duckdb_extension_load(httpfs
        LOAD_TESTS
        GIT_URL https://github.com/Query-farm-haybarn/haybarn-httpfs
        GIT_TAG cbfcb2e650593ff48f4a490e3599721f204a0eb4
)
include("${EXTENSION_CONFIG_BASE_DIR}/inet.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/mysql_scanner.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/odbc_scanner.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/postgres_scanner.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/spatial.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/sqlite_scanner.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/sqlsmith.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/vss.cmake")

# --- Rust-based out-of-tree extensions, rebuilt from upstream ----------------
# (require a Rust toolchain in CI)
include("${EXTENSION_CONFIG_BASE_DIR}/unity_catalog.cmake")

# --- Out-of-tree extensions, built from the Haybarn build-forks --------------
# iceberg, ducklake and delta are forked under Query-farm-haybarn for source/tag
# control. The extension names stay `iceberg` / `ducklake` / `delta`. Each
# fork's `haybarn` branch is the exact commit DuckDB v1.5.2 CI pinned (iceberg
# 11fea8ed, ducklake 415a9ebd, delta 776be7ac) plus a single NOTICE commit —
# pinned here by explicit SHA so the build is reproducible and unambiguously
# the 1.5.2 build, never `main`.
if(NOT MINGW AND NOT ${WASM_ENABLED})
    duckdb_extension_load(delta
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-delta
            GIT_TAG 9ef3645f4610a0e7877095f4de3887075eebdb07
            SUBMODULES extension-ci-tools
    )
endif()
if (NOT MINGW)
    # DONT_LINK: iceberg ships Unity-Catalog support and defines
    # duckdb::GetUCCreateView, which collides with the unity_catalog extension
    # when both are statically linked into one binary (DuckDB builds them in
    # separate configs; Haybarn's merged config does not). Built loadable-only,
    # which is exactly what the extension repository needs.
    duckdb_extension_load(iceberg
            DONT_LINK
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-iceberg
            GIT_TAG 9ed58be8cb2361c66b63bbfd46657c3fad954175
            )
endif()

duckdb_extension_load(ducklake
    GIT_URL https://github.com/Query-farm-haybarn/haybarn-ducklake
    GIT_TAG 45e2b4ba5ae6de1fc0f1c78802638eed672d9a99
)
