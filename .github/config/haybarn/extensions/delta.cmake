# Haybarn build-fork of delta: upstream's v2.0.0 pin (9dcfb65b) plus the
# Haybarn CI/NOTICE stack. Branch haybarn-2.0; the 1.5 line is `haybarn`.
if(NOT MINGW AND NOT ${WASM_ENABLED})
  duckdb_extension_load(delta
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-delta
            GIT_TAG 12b5ff6e04c877fadd7c7e9cb2fe9ab9708c306f
            SUBMODULES extension-ci-tools
  )
endif()
