#!/usr/bin/env python3
"""Compute the CalVer package version string for an extension build.

Used by the pip/npm publish steps to derive the registry version field.
Scheme (per ideas/extension-version-pinning.md, Phase 5):

    <YYYYMM>.<DD>.<HHMMSS>     — derived from the extension source commit
                                  time in UTC, e.g. 202605.17.122351

Both PEP 440 and semver accept three integer release components with no
leading zeros, so a single string crosses both registries unchanged.

If the extension descriptor declares a semver (waddle has version: 0.0.2),
that wins — `--semver` short-circuits the CalVer derivation. Pass it
through unmodified so legible `==0.0.2` pins keep working.

Usage:
    python3 compute_calver.py --commit-ts 1747445031
    python3 compute_calver.py --semver 0.0.2
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys


def calver_from_ts(commit_unix_ts: int) -> str:
    # Commit time is authoritative — gives idempotent rebuilds (same commit
    # → same version → PyPI's immutability rule just confirms equality
    # rather than producing a conflict).
    when = dt.datetime.fromtimestamp(commit_unix_ts, tz=dt.timezone.utc)
    major = when.year * 100 + when.month        # 2026 * 100 + 5 = 202605
    minor = when.day                            # 17
    patch = when.hour * 10000 + when.minute * 100 + when.second  # 12*10000 + 23*100 + 51 = 122351
    return f"{major}.{minor}.{patch}"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit-ts", type=int,
                    help="extension source commit Unix timestamp (UTC seconds)")
    ap.add_argument("--semver",
                    help="if the descriptor carries a real semver, "
                         "use it verbatim and skip CalVer derivation")
    args = ap.parse_args(argv)

    if args.semver:
        # Trust the descriptor — the version pinning doc says semver wins
        # when present. No validation here; the publish tooling will reject
        # malformed semver downstream.
        print(args.semver)
        return 0

    if args.commit_ts is None:
        print("compute_calver: one of --semver or --commit-ts is required",
              file=sys.stderr)
        return 2

    print(calver_from_ts(args.commit_ts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
