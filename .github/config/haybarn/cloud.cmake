# Haybarn variant of .github/config/cloud.cmake: identical, except httpfs,
# iceberg and ducklake come from the Haybarn build-forks.
# CI inlines this file into the extension's extension_config.cmake, so includes
# resolve from EXTENSION_CONFIG_BASE_DIR (duckdb/.github/config/extensions),
# never from this file's location. To parse it with
# scripts/sync_out_of_tree_extensions.py, pass that directory explicitly.

if (NOT DEFINED DUCKDB_MAIN_EXTENSION_CONFIG_TYPE OR DUCKDB_MAIN_EXTENSION_CONFIG_TYPE STREQUAL "IN_TREE")
    duckdb_extension_load(json)
    duckdb_extension_load(parquet)
endif()

if (NOT DEFINED DUCKDB_MAIN_EXTENSION_CONFIG_TYPE OR DUCKDB_MAIN_EXTENSION_CONFIG_TYPE STREQUAL "OUT_OF_TREE")
    include("${EXTENSION_CONFIG_BASE_DIR}/aws.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/azure.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/../haybarn/extensions/ducklake.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/glue.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/../haybarn/extensions/httpfs.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/../haybarn/extensions/iceberg.cmake")
endif()
