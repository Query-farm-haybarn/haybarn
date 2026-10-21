# Haybarn build-fork of iceberg: upstream's v2.0.0 pin (4c0c0874) plus the
# Haybarn CI/NOTICE stack. Branch haybarn-2.0; the 1.5 line is `haybarn`.
if (NOT MINGW)
  duckdb_extension_load(iceberg
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-iceberg
            GIT_TAG fa86ad24928da0f4be1ed3fec76cf73e22daed3e
            )
endif()
