# Haybarn variant of .github/config/rust_based_extensions.cmake: identical,
# except delta comes from the Haybarn build-fork.
# CI inlines this file into the extension's extension_config.cmake, so includes
# resolve from EXTENSION_CONFIG_BASE_DIR (duckdb/.github/config/extensions),
# never from this file's location. To parse it with
# scripts/sync_out_of_tree_extensions.py, pass that directory explicitly.
include("${EXTENSION_CONFIG_BASE_DIR}/../haybarn/extensions/delta.cmake")
include("${EXTENSION_CONFIG_BASE_DIR}/unity_catalog.cmake")
