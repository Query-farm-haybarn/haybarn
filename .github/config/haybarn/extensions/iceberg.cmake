# Haybarn build-fork of iceberg: upstream's v2.0.1 pin (f979b5b2) plus the
# Haybarn CI/NOTICE stack. Branch haybarn-2.0; the 1.5 line is `haybarn`.
# Windows tests for iceberg currently not working (as upstream)
IF (NOT WIN32)
  set(LOAD_ICEBERG_TESTS "LOAD_TESTS")
else ()
  set(LOAD_ICEBERG_TESTS "")
endif()
if (NOT MINGW)
  duckdb_extension_load(iceberg
            ${LOAD_ICEBERG_TESTS}
            GIT_URL https://github.com/Query-farm-haybarn/haybarn-iceberg
            GIT_TAG e6e133be5a944c8316badde2be695562c9bc3a0d
            )
endif()
