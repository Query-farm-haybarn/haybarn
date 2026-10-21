# Haybarn variant of .github/config/cloud.cmake: identical, except httpfs,
# iceberg and ducklake come from the Haybarn build-forks.
# Includes are CMAKE_CURRENT_LIST_DIR-relative so both CMake and
# scripts/sync_out_of_tree_extensions.py resolve them from this directory.

if (NOT DEFINED DUCKDB_MAIN_EXTENSION_CONFIG_TYPE OR DUCKDB_MAIN_EXTENSION_CONFIG_TYPE STREQUAL "IN_TREE")
    duckdb_extension_load(json)
    duckdb_extension_load(parquet)
endif()

if (NOT DEFINED DUCKDB_MAIN_EXTENSION_CONFIG_TYPE OR DUCKDB_MAIN_EXTENSION_CONFIG_TYPE STREQUAL "OUT_OF_TREE")
    include("${CMAKE_CURRENT_LIST_DIR}/../extensions/aws.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/../extensions/azure.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/extensions/ducklake.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/../extensions/glue.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/extensions/httpfs.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/extensions/iceberg.cmake")
endif()
