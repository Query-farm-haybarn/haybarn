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
# haybarn branch). Now at 94d8fee: the Haybarn stack rebased onto upstream's
# v1.5.5 httpfs pin (827222f, +63 commits over v1.5.4's c3f215a). That roll
# rewrote the request path into thin public wrappers over shared Run*Request
# runners parameterised by send/error callbacks, so the Haybarn HTTP work was
# re-expressed against it: conditional reads (If-Match / If-Unmodified-Since)
# now live entirely in the public wrappers and turn the server's 412 into the
# "remote file changed" error via the get_error callback, leaving the shared
# runners byte-identical to upstream. Cancellation moved into the runners, which
# extends it to every method. HTTP/2 multiplex carried forward unchanged; the
# URL-ownership/%n submodule bump dropped as already-upstream.
duckdb_extension_load(httpfs
        LOAD_TESTS
        GIT_URL https://github.com/Query-farm-haybarn/haybarn-httpfs
        GIT_TAG 94d8fee6ea02ce952bab164e22689afe8f0cd8ed
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
# fork's `haybarn` branch is the exact commit DuckDB v1.5.5 CI pinned (iceberg
# 45163a28, ducklake d8a1881e, delta 45c40878 — unchanged from v1.5.4) plus the
# Haybarn CI/NOTICE stack, rebased forward for v1.5.5 — pinned here by explicit
# SHA so the build is reproducible and unambiguously the 1.5.5 build, never
# `main`.
if(NOT MINGW AND NOT ${WASM_ENABLED})
    duckdb_extension_load(delta
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-delta
            GIT_TAG f2dbbb0b2adeea2fb05159f0d920d0b43f807a56
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
            GIT_TAG 501a36825e83ee7952d58d22f32890eeedaf1724
            )
endif()

# haybarn-ducklake@haybarn tracks upstream/v1.5-variegata (the 1.5 release line)
# plus the Haybarn CI/NOTICE stack. Bump this SHA to the branch tip after syncing
# the fork from v1.5-variegata. 7f29519 = the 9-commit Haybarn CI stack rebased
# onto upstream's v1.5.5 ducklake pin (d8a1881e) + a .github/duckdb-version bump
# to v1.5.5. The previously carried `fix relassert` (5947ea32, murmur3
# constant-vector) is now upstream and was dropped by the rebase.
duckdb_extension_load(ducklake
    GIT_URL https://github.com/Query-farm-haybarn/haybarn-ducklake
    GIT_TAG 7f29519075dae75b2e636ce31f7ef6d3d545c5dd
)
