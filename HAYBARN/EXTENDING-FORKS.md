# Making Haybarn changes on top of an extension build-fork

Haybarn forks the source repos of a few extensions under `Query-farm-haybarn/`
so we can land Haybarn-specific changes on top of upstream over time. Today the
build-forks are:

| Repo | Upstream | Pinned at |
|------|----------|-----------|
| `Query-farm-haybarn/haybarn-iceberg` | `duckdb/duckdb-iceberg` | (see `haybarn_extensions.cmake`) |
| `Query-farm-haybarn/haybarn-ducklake` | `duckdb/ducklake` | ″ |
| `Query-farm-haybarn/haybarn-delta` | `duckdb/duckdb-delta` | ″ |
| `Query-farm-haybarn/haybarn-httpfs` | `duckdb/duckdb-httpfs` | ″ |

The same pattern applies to any of them.

## How the build picks up these forks

`.github/config/haybarn_extensions.cmake` in this (core) repo pins each one
explicitly:

```cmake
duckdb_extension_load(httpfs
        LOAD_TESTS
        GIT_URL https://github.com/Query-farm-haybarn/haybarn-httpfs
        GIT_TAG <40-char SHA>
)
```

The pin is by **SHA**, not a branch — to roll forward, you bump the SHA. That
keeps every build reproducible and explicit about what got built.

## Working on a fork

Each fork is a small, curated commit stack on top of an upstream tag:

- `upstream` remote → `duckdb/<repo>`
- `haybarn` branch (the default) → upstream pin + Haybarn commits

Working directory layout on your machine (matches what's in this Mac):

```
~/Development/haybarn/
  haybarn/             ← core fork (this repo)
  haybarn-httpfs/      ← extension build-fork
  haybarn-iceberg/
  haybarn-ducklake/
  haybarn-delta/
```

### Adding a Haybarn change to a fork

```sh
cd ~/Development/haybarn/haybarn-httpfs

# Confirm you're on the haybarn branch (default).
git status

# Make changes, commit as normal. One commit = one concern (just like the
# core fork's stack — see HAYBARN/REBASE.md). Keep the stack small.
git commit -am "..."

# Push to the Haybarn fork.
git push origin haybarn

# Note the new haybarn-branch HEAD SHA — you'll pin to it in the core repo.
git rev-parse haybarn
```

### Bumping the pin in the core repo

```sh
NEW_SHA=$(git -C ~/Development/haybarn/haybarn-httpfs rev-parse haybarn)
cd ~/Development/haybarn/haybarn

# Edit .github/config/haybarn_extensions.cmake — replace the existing
# GIT_TAG for httpfs with $NEW_SHA. (Or whichever fork you bumped.)
$EDITOR .github/config/haybarn_extensions.cmake

git commit -am "config: bump haybarn-httpfs to $NEW_SHA"
git push origin haybarn

# Trigger an extension build with the new pin.
gh workflow run haybarn-extensions.yml \
  --repo Query-farm-haybarn/haybarn --ref haybarn \
  -f deploy=true
```

When the build deploys to R2, `INSTALL httpfs;` on a Haybarn CLI picks up the
new build immediately (same extension name; Haybarn's signing key verifies it).

### Pulling in newer upstream code (rebase on a new upstream release)

Same as the core repo's procedure — see [REBASE.md](REBASE.md). One-line summary:

```sh
cd ~/Development/haybarn/haybarn-<ext>
git fetch upstream
git rebase --onto <new-upstream-tag-or-SHA> <old-base> haybarn
# resolve conflicts; one commit at a time; rerere replays prior fixes.
git push --force-with-lease origin haybarn
# then bump the pin in haybarn_extensions.cmake as above.
```

## Why pin by SHA, not branch?

Because pin-by-branch (`GIT_TAG haybarn`) silently shifts behaviour every time
*anyone* pushes to the fork. Pin-by-SHA makes every Haybarn build
[reproducible](ROLL-FORWARD.md) — the source of truth for what got built lives
in the commit history of *this* repo.

## Hard rules (same as everywhere in Haybarn)

- The extension **name** stays `httpfs` / `iceberg` / `ducklake` / `delta`. Do
  not rename what users type in `INSTALL …`. Build-fork ≠ rebrand. See
  [memory/haybarn-project.md](../../HAYBARN/) decisions.
- Keep the fork's `duckdb::` namespace and ABI intact (do not change symbol
  names or the `.duckdb_extension` format). Build-fork changes should be
  *additive* or *bug-fix*-shaped, not ABI-breaking.
- Preserve the upstream `LICENSE` and `NOTICE`; document modifications in
  `NOTICE` on the fork (each fork has one).

## When to start a new build-fork

You only need a new build-fork when:
1. You intend to land Haybarn-specific patches *now or soon* on top of upstream
   for that extension, AND
2. The extension matters enough to Haybarn to maintain the rebase burden each
   upstream release.

If you just want to rebuild an upstream extension against Haybarn DuckDB +
Haybarn signing (no source changes), **don't fork** — just `include` the
upstream `.cmake` in `haybarn_extensions.cmake`. That's how most of the ~25
extensions are wired today; only `iceberg`, `ducklake`, `delta`, and `httpfs`
are forked.
