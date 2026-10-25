# Haybarn: spatial alone, for a wasm-only build (the `wasm_spatial` group in
# haybarn-extensions.yml). Publishes the wasm_eh / wasm_threads spatial
# binaries without rebuilding or republishing the rest of the search group.
include("${EXTENSION_CONFIG_BASE_DIR}/spatial.cmake")
