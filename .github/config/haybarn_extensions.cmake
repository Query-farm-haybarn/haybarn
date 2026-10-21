#
# Haybarn extension build configuration.
#
# This is the full set of extensions Haybarn builds, signs with the Haybarn
# extension-signing key, and serves from https://haybarn-extensions.query.farm/core.
#
# It is the set DuckDB's own CI builds, MINUS the extensions Haybarn does not
# ship: vortex, lance.
#
# CI builds these as upstream's groups instead (core, haybarn/cloud, search,
# scanner, haybarn/rust_based_extensions); this merged file is for local builds.
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
# config files (.github/config/extensions/, DuckDB v2.0.0 pins); only the build
# target (Haybarn DuckDB) and the signing key differ from upstream. This is
# upstream's core + cloud + search + scanner + rust sets (out_of_tree_extensions
# + rust_based_extensions), minus the build-forks below.
include("${EXTENSION_CONFIG_BASE_DIR}/avro.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/aws.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/azure.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/encodings.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/excel.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/fts.cmake")
# New in 2.0. glue: AWS Glue Data Catalog (experimental). legacy_parser: the 1.5
# SQL parser as an extension, autoinstalled by `SET enable_legacy_parser`.
# quack: client/server protocol (experimental), autoinstalled on first use.
include("${EXTENSION_CONFIG_BASE_DIR}/glue.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/inet.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/legacy_parser.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/mysql_scanner.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/odbc_scanner.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/postgres_scanner.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/quack.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/spatial.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/sqlite_scanner.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/sqlsmith.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/vss.cmake")

# --- Rust-based out-of-tree extensions, rebuilt from upstream ----------------
# (require a Rust toolchain in CI)
include("${EXTENSION_CONFIG_BASE_DIR}/unity_catalog.cmake")

# --- Out-of-tree extensions, built from the Haybarn build-forks --------------
# httpfs, iceberg, ducklake and delta come from the Query-farm-haybarn
# build-forks; their pins live in haybarn/extensions/ (shared with the CI group
# configs haybarn/cloud.cmake and haybarn/rust_based_extensions.cmake).
include("${EXTENSION_CONFIG_BASE_DIR}/../haybarn/extensions/httpfs.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/../haybarn/extensions/delta.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/../haybarn/extensions/ducklake.cmake")
# iceberg ships Unity-Catalog support and defines duckdb::GetUCCreateView,
# which collides with unity_catalog when both are statically linked into one
# binary. CI builds them in separate groups; this merged local config builds
# iceberg loadable-only via DONT_LINK. Keep GIT_TAG in sync with
# haybarn/extensions/iceberg.cmake.
if (NOT MINGW)
    duckdb_extension_load(iceberg
            DONT_LINK
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-iceberg
            GIT_TAG fa86ad24928da0f4be1ed3fec76cf73e22daed3e
            )
endif()
