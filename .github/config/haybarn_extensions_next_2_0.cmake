# Minimal extension set used to validate the Haybarn DuckDB 2.0 build path.
#
# Keep this deliberately small until the out-of-tree Haybarn extension forks
# are rebased and pinned to DuckDB 2.0. The `ask` extension should be added here
# as the next target once its repository exists.

duckdb_extension_load(parquet)
