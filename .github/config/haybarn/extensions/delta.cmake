# Haybarn build-fork of delta: upstream's v2.0.1 pin (f41762b3) plus the
# Haybarn CI/NOTICE stack. Branch haybarn-2.0; the 1.5 line is `haybarn`.
if(NOT MINGW AND NOT ${WASM_ENABLED})
  duckdb_extension_load(delta
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-delta
            GIT_TAG 64027474c58b679e190c2b26e7faa953e35acfa0
            SUBMODULES extension-ci-tools
  )
endif()
