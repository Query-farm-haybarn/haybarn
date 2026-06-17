# Haybarn — operational setup

What needs to exist for the Haybarn CI/release pipelines to work. The repos and
the signing keys are already in place; this is the remaining infrastructure +
secrets checklist.

## Signing keys (already generated)

| Key | Purpose | Where it lives |
|-----|---------|----------------|
| Extension signing key (RSA-2048) | signs `.duckdb_extension` files | private key → `HAYBARN_EXTENSION_SIGNING_PK` secret; public half embedded in `src/main/extension/extension_helper.cpp` |
| Release signing key (GPG RSA-4096, `hello@query.farm`) | signs `SHA256SUMS` on GitHub Releases | private key + passphrase → secrets / macOS Keychain; public key → `HAYBARN/haybarn_release_signing.pub` |

Fingerprint of the release key: `AC21147B0BABF6941225ECBEC41595068F3F6537`.

## Cloudflare R2 (extension hosting)

1. Create an R2 bucket (the `R2_BUCKET` value).
2. Connect the custom domain **`haybarn-extensions.query.farm`** to the bucket —
   this is the URL embedded in the binary
   (`https://haybarn-extensions.query.farm/core/v<version>/<platform>/...`).
3. Create an R2 API token → gives an Access Key ID + Secret Access Key.
4. Note the endpoint: `https://<account-id>.r2.cloudflarestorage.com`.

R2 has no S3 object ACLs — public read is via the custom domain. The upload
script handles this (`ACL_PARAM` defaults to empty;
`scripts/extension-upload-single.sh`).

## GitHub Actions secrets

Set on `Query-farm-haybarn/haybarn` (repo-level) unless you have `admin:org`
scope, in which case org-level with visibility=all is fine.

| Secret | Repo(s) | Status |
|--------|---------|--------|
| `HAYBARN_EXTENSION_SIGNING_PK` | `haybarn` | set |
| `HAYBARN_GPG_PRIVATE_KEY` | `haybarn` | set |
| `HAYBARN_GPG_PASSPHRASE` | `haybarn` | set |
| `R2_ACCESS_KEY_ID` | `haybarn` | from R2 API token |
| `R2_SECRET_ACCESS_KEY` | `haybarn` | from R2 API token |
| `R2_ENDPOINT` | `haybarn` | `https://<account-id>.r2.cloudflarestorage.com` |
| `R2_BUCKET` | `haybarn` | the bucket name |
| `PYPI_API_TOKEN` | `haybarn-python` | from PyPI, scoped to the `haybarn` project |

cosign uses keyless OIDC — no secret. Apple/Windows code-signing secrets are
deferred (binaries ship with checksums + GPG + cosign for now).

## PyPI

Register the `haybarn` project name (TestPyPI first is recommended) and create a
scoped API token → `PYPI_API_TOKEN`.

## Enable GitHub Actions

Forked repos often have Actions disabled by default — enable it on all four
repos (Settings → Actions).

## Fork tags

The `haybarn` core fork must carry the upstream `v1.5.4` tag — the extension
build (`extension-ci-tools`) runs `git checkout v1.5.4` inside the checked-out
caller repo. Push it explicitly (a branch push does not carry tags):

```sh
git push origin refs/tags/v1.5.4
```

Note: enabling GitHub Actions on a fork does not retroactively index workflows
already on the default branch — push a commit after enabling Actions to trigger
indexing.

## First run

Tag the core repo to exercise the pipelines:

```sh
git tag haybarn-v1.5.4-rc1
git push origin haybarn-v1.5.4-rc1
```

This triggers `haybarn-release.yml` (binaries), `haybarn-extensions.yml` (the
extension set → R2), and `haybarn-publish.yml` (SHA256SUMS + GPG + cosign →
GitHub Release). Expect to iterate — the full cross-platform matrix rarely
passes on the first run.

## Verifying a release (for users / docs)

```sh
sha256sum -c SHA256SUMS
gpg --import haybarn_release_signing.pub
gpg --verify SHA256SUMS.asc SHA256SUMS
```

## Updating pinned toolchain

Every moving CI reference (runner OSes, manylinux image, extension-ci-tools
SHA, pybind11) is pinned for reproducibility. To refresh them, see
[ROLL-FORWARD.md](ROLL-FORWARD.md) — it lists each pin's location and gives
the exact `gh`/`curl`/`pip` commands to resolve current values.
