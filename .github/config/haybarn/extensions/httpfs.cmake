# Haybarn build-fork of httpfs: upstream's v2.0.0 pin (77392a72) plus Haybarn's
# HTTP work re-expressed against upstream's 2.0 src/http + src/s3 layout:
# HTTP/2 via ALPN with curl_multi stream multiplexing, lowercase response header
# names, response compression for API requests and whole-file GETs (text pages
# under http_compressed_download_threshold read with one compressed GET; range
# GETs and HEAD stay identity), If-Unmodified-Since for files without a strong
# ETag, and cancellation of in-flight requests through the engine's HTTPParams
# interrupt context. Branch haybarn-2.0; the 1.5 line is `haybarn`.
duckdb_extension_load(httpfs
    LOAD_TESTS
    GIT_URL https://github.com/Query-farm-haybarn/haybarn-httpfs
    GIT_TAG 9c5025d463fd80faa748a923a59d09cfb8b06dfe
)
