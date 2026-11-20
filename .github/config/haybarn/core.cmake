# Haybarn's core group: upstream's .github/config/core.cmake without sirius (v2.0.1).
# sirius (GPU, Linux glibc) needs extension-ci-tools changes from upstream's
# v2.0-cyanoptera (subdirectory builds, a vcpkg manifest workaround, libclang) that
# Haybarn's ci-tools fork does not carry yet. Keep the rest in step with upstream's file.
if (NOT DEFINED DUCKDB_MAIN_EXTENSION_CONFIG_TYPE OR DUCKDB_MAIN_EXTENSION_CONFIG_TYPE STREQUAL "IN_TREE")
    duckdb_extension_load(autocomplete)
    duckdb_extension_load(core_functions)
    duckdb_extension_load(icu)
    duckdb_extension_load(tpcds)
    duckdb_extension_load(tpch)

    # Test extension for the upcoming C CAPI extensions
    duckdb_extension_load(demo_capi)
endif()

if (NOT DEFINED DUCKDB_MAIN_EXTENSION_CONFIG_TYPE OR DUCKDB_MAIN_EXTENSION_CONFIG_TYPE STREQUAL "OUT_OF_TREE")
    include("${EXTENSION_CONFIG_BASE_DIR}/avro.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/excel.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/inet.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/legacy_parser.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/quack.cmake")
    include("${EXTENSION_CONFIG_BASE_DIR}/sqlsmith.cmake")
endif()
