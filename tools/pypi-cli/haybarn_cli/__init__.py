"""haybarn-cli — Python wheel that bundles the haybarn native binary.

The `console_scripts` entry point `haybarn = haybarn_cli:main` becomes a
small launcher script that, when invoked, locates the bundled binary
inside this package and re-exec's into it. Same end-user UX as the npm
meta-package: `uvx haybarn-cli -c "PRAGMA version;"`.

The actual binary lives at `haybarn_cli/_bin/haybarn` (or `haybarn.exe`
on Windows) and is platform-specific — each PyPI wheel ships only the
binary for its `manylinux` / `musllinux` / `macosx` / `win` tag, so pip
and uv install the right one automatically.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _binary_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    binname = "haybarn.exe" if sys.platform == "win32" else "haybarn"
    return os.path.join(here, "_bin", binname)


def main() -> None:
    binpath = _binary_path()
    if not os.path.exists(binpath):
        sys.stderr.write(
            f"haybarn-cli: bundled binary missing at {binpath}.\n"
            "This usually means the wheel was built without a binary "
            "(e.g. from sdist) or installed with --no-binary. Reinstall "
            "with a binary wheel:\n"
            "  pip install --only-binary=:all: haybarn-cli\n"
            "or run via uvx/pipx instead:\n"
            "  uvx haybarn-cli -- <args>\n"
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
                f"haybarn-cli: binary at {binpath} is not executable and "
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
