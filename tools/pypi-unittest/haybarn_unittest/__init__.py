"""haybarn-unittest — Python wheel that bundles the haybarn-unittest binary.

The `console_scripts` entry point `haybarn-unittest = haybarn_unittest:main`
becomes a small launcher script that, when invoked, locates the bundled binary
inside this package and re-exec's into it. Same end-user UX as the npm
meta-package: `uvx haybarn-unittest --test-dir . --list-tests`.

The binary is DuckDB's `unittest` test runner, rebranded `haybarn-unittest`,
built with `-DUNITTEST_ROOT_DIRECTORY=.` so it launches from any working
directory. Point it at your own `.test` files with `--test-dir <dir>`.

The actual binary lives at `haybarn_unittest/_bin/haybarn-unittest` (or
`haybarn-unittest.exe` on Windows) and is platform-specific — each PyPI wheel
ships only the binary for its `manylinux` / `musllinux` / `macosx` / `win` tag,
so pip and uv install the right one automatically.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _binary_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    binname = "haybarn-unittest.exe" if sys.platform == "win32" else "haybarn-unittest"
    return os.path.join(here, "_bin", binname)


def main() -> None:
    binpath = _binary_path()
    if not os.path.exists(binpath):
        sys.stderr.write(
            f"haybarn-unittest: bundled binary missing at {binpath}.\n"
            "This usually means the wheel was built without a binary "
            "(e.g. from sdist) or installed with --no-binary. Reinstall "
            "with a binary wheel:\n"
            "  pip install --only-binary=:all: haybarn-unittest\n"
            "or run via uvx/pipx instead:\n"
            "  uvx haybarn-unittest -- <args>\n"
        )
        sys.exit(127)

    # pip/installer doesn't always preserve the +x bit on files inside the
    # package directory (the wheel's zip stores it via external_attr but
    # some installer backends strip it during unpack). Chmod defensively on
    # POSIX; the operation is a no-op if the bit is already set, and the
    # try/except handles read-only filesystems / shared installs where the
    # user can't change permissions.
    if sys.platform != "win32" and not os.access(binpath, os.X_OK):
        try:
            os.chmod(binpath, 0o755)
        except OSError:
            sys.stderr.write(
                f"haybarn-unittest: binary at {binpath} is not executable and "
                f"chmod failed (read-only install?). Try: chmod +x {binpath}\n"
            )
            sys.exit(126)

    args = [binpath, *sys.argv[1:]]

    if sys.platform == "win32":
        # On Windows, os.execv replaces the current process but the
        # entry-point launcher (.exe) doesn't propagate that cleanly.
        # subprocess.run with stdio inherit is the right primitive.
        result = subprocess.run(args)
        sys.exit(result.returncode)

    # POSIX: replace this process so signals + exit codes pass through.
    os.execv(binpath, args)
