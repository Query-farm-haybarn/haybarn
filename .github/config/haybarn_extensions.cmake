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
# changes can land on top of upstream over time. Pinned by explicit SHA — bump it
# when you want to roll forward (or pick up new Haybarn commits on the fork's
# haybarn branch). Now at 151fb49: the Haybarn stack rebased onto upstream's
# v1.5.6 httpfs pin (4bc690d, +15 commits over v1.5.5's 827222f: S3 multipart
# and expired-token fixes). The one non-mechanical spot: upstream stopped
# throwing from the GET response handlers and now raises get_error after
# send_request returns, capturing the >= 400 body in the client instead. The
# Haybarn cancellation commit was merged with that in RunGetRequest and the
# httplib streaming GET (cancellation check + upstream's error-body capture);
# conditional reads, HTTP/2 multiplex and the 412 translation carried forward
# unchanged. APPLY_PATCHES mirrors upstream's v1.5.6 config, which skips the
# glob_s3_recursive slow test via .github/patches/extensions/httpfs/.
duckdb_extension_load(httpfs
        LOAD_TESTS
        GIT_URL https://github.com/Query-farm-haybarn/haybarn-httpfs
        GIT_TAG 151fb49d9b490a8db15a4b87a1fa1caa21850525
        APPLY_PATCHES
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
# fork's `haybarn` branch is the exact commit DuckDB v1.5.6 CI pinned (iceberg
# 890b78a9, ducklake ac7595b0, delta 6059958c) plus the Haybarn CI/NOTICE
# stack, rebased forward for v1.5.6 — pinned here by explicit SHA so the build
# is reproducible and unambiguously the 1.5.6 build, never `main`.
if(NOT MINGW AND NOT ${WASM_ENABLED})
    duckdb_extension_load(delta
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-delta
            GIT_TAG b364355817c281e182124702005e2949cc1c1a0f
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
            GIT_TAG e03af7b2ab79aded649fe2188059cbf227a28a12
            )
endif()

# haybarn-ducklake@haybarn tracks upstream/v1.5-variegata (the 1.5 release line)
# plus the Haybarn CI/NOTICE stack. Bump this SHA to the branch tip after syncing
# the fork from v1.5-variegata. 028d623 = the 9-commit Haybarn CI stack rebased
# onto upstream's v1.5.6 ducklake pin (ac7595b0) + a .github/duckdb-version bump
# to v1.5.6.
duckdb_extension_load(ducklake
    GIT_URL https://github.com/Query-farm-haybarn/haybarn-ducklake
    GIT_TAG 028d623356f817971ff58be9e301134ac47082fe
)
