#
# This is the DuckDB in-tree extension config as it will run on the CI
#
# to build duckdb with this configuration run:
#   EXTENSION_CONFIGS=.github/config/in_tree_extensions.cmake make
#

duckdb_extension_load(autocomplete)
duckdb_extension_load(core_functions)
duckdb_extension_load(icu)
duckdb_extension_load(json)
duckdb_extension_load(parquet)
duckdb_extension_load(tpcds)
duckdb_extension_load(tpch)
# Haybarn: statically link httpfs so the engine can fetch other
# extensions over HTTPS without needing to bootstrap httpfs first.
# extension_install.cpp's HTTPUtil::IsHTTPProtocol only matches http://
# (not https://), so for the default https://haybarn-extensions.query.farm
# repository the install falls through to DirectInstallExtension →
# fs.FileExists(<https URL>) which requires httpfs to already be loaded
# — circular dependency for the bootstrap install of httpfs itself.
# Upstream DuckDB releases include httpfs the same way for the same reason.
#
# httpfs lives out-of-tree. Use the Haybarn build-fork
# (Query-farm-haybarn/haybarn-httpfs, default branch 'haybarn') so any
# Haybarn-specific patches travel with the engine.
duckdb_extension_load(httpfs
    LOAD_TESTS
    GIT_URL https://github.com/Query-farm-haybarn/haybarn-httpfs
    GIT_TAG 4bb6eb5801
)

# Test extension for the upcoming C CAPI extensions
duckdb_extension_load(demo_capi DONT_LINK)
