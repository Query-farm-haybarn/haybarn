# Haybarn build-fork of ducklake: upstream's v2.0.1 pin (08089b16) plus the
# Haybarn CI/NOTICE stack. Branch haybarn-2.0; the 1.5 line is `haybarn`.
# APPLY_PATCHES: upstream's .github/patches/extensions/ducklake fixes apply
# unchanged to the fork.
duckdb_extension_load(ducklake
    LOAD_TESTS
    GIT_URL https://github.com/Query-farm-haybarn/haybarn-ducklake
    GIT_TAG d3afbed5d64e5604f7d82fff6323e4e95e6a96a7
    APPLY_PATCHES
)
