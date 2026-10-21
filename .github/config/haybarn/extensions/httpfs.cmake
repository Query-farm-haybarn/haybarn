# Haybarn build-fork of httpfs: upstream's v2.0.0 pin (77392a72) plus Haybarn's
# HTTP work (HTTP/2 multiplexing, request cancellation, compression and
# conditional reads, header handling) re-expressed against upstream's 2.0
# src/http + src/s3 layout. Branch haybarn-2.0; the 1.5 line is `haybarn`.
#
# TEMPORARY (2026-10-21): upstream httpfs at DuckDB's v2.0.0 pin, so the other
# 2.0 groups can be validated while the haybarn-2.0 port is in progress.
# Must point at Query-farm-haybarn/haybarn-httpfs before any 2.0 publish.
duckdb_extension_load(httpfs
    LOAD_TESTS
    GIT_URL https://github.com/duckdb/duckdb-httpfs
    GIT_TAG 77392a72077a85897db2519fae11e2c0da972b8a
)
