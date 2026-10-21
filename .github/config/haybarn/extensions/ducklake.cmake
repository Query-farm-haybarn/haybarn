# Haybarn build-fork of ducklake: upstream's v2.0.0 pin (417a9117) plus the
# Haybarn CI/NOTICE stack. Branch haybarn-2.0; the 1.5 line is `haybarn`.
# APPLY_PATCHES: upstream's .github/patches/extensions/ducklake fixes apply
# unchanged to the fork.
duckdb_extension_load(ducklake
    LOAD_TESTS
    GIT_URL https://github.com/Query-farm-haybarn/haybarn-ducklake
    GIT_TAG 76c5055876130db070397604675f0fb98cfa5777
    APPLY_PATCHES
)
