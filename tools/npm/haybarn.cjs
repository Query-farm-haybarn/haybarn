#!/usr/bin/env node
// Haybarn npm shim.
//
// `haybarn` on npm is a meta-package that depends on per-platform leaves
// (`@haybarn/cli-<os>-<arch>[-musl]`) as optionalDependencies. npm installs
// only the leaf matching the current runtime. This shim locates that
// leaf's bundled binary and execs it with the user's arguments.
//
// Same pattern esbuild / swc / biome use. Deliberately no postinstall
// script — installs work in corporate npm proxies and sandboxed environments
// (Snyk, npm audit, restrictive CI runners) where postinstall execution is
// blocked.

'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

function detectMuslLinux() {
  try {
    // process.report.getReport() exposes the runtime libc. On glibc Linux
    // header.glibcVersionRuntime is a version string; on Alpine/musl it's
    // absent. This is the same probe used by esbuild's npm shim.
    const report = process.report.getReport();
    return !report.header.glibcVersionRuntime;
  } catch (_) {
    // Older Node, or report API unavailable — fall back to a filesystem
    // probe. /usr/bin/ldd dispatching to musl emits "musl" in its banner,
    // but reading /etc/os-release is faster and doesn't spawn a subprocess.
    try {
      return /alpine|musl/i.test(fs.readFileSync('/etc/os-release', 'utf8'));
    } catch (_) {
      return false;
    }
  }
}

function platformPackageName() {
  const platform = process.platform;
  const arch = process.arch;

  if (platform === 'linux') {
    if (arch !== 'x64' && arch !== 'arm64') return null;
    const suffix = detectMuslLinux() ? '-musl' : '';
    return `@haybarn/cli-linux-${arch}${suffix}`;
  }
  if (platform === 'darwin') {
    if (arch !== 'x64' && arch !== 'arm64') return null;
    return `@haybarn/cli-darwin-${arch}`;
  }
  if (platform === 'win32') {
    if (arch !== 'x64') return null;
    return '@haybarn/cli-win32-x64';
  }
  return null;
}

function binaryFilename() {
  return process.platform === 'win32' ? 'haybarn.exe' : 'haybarn';
}

const pkg = platformPackageName();
if (!pkg) {
  console.error(
    `haybarn: no prebuilt binary for ${process.platform}/${process.arch}.\n` +
    `Supported: linux x64/arm64 (glibc + musl), darwin x64/arm64, win32 x64.\n` +
    `Build from source: https://github.com/Query-farm-haybarn/haybarn`
  );
  process.exit(1);
}

let binPath;
try {
  binPath = require.resolve(`${pkg}/bin/${binaryFilename()}`);
} catch (_) {
  // The optional dep didn't install — most common cause is `npm install
  // --no-optional` or the user's lockfile predates this binary's platform.
  // Emit an actionable message rather than a stack trace.
  console.error(
    `haybarn: platform package ${pkg} is not installed.\n` +
    `Reinstall haybarn without --no-optional, or install the leaf directly:\n` +
    `  npm install ${pkg}`
  );
  process.exit(1);
}

// On POSIX we'd ideally exec() to replace this Node process; Node has no
// direct execve. spawnSync with stdio:'inherit' is the next best thing:
// signals propagate, the child's exit status becomes ours.
const result = spawnSync(binPath, process.argv.slice(2), { stdio: 'inherit' });

if (result.error) {
  if (result.error.code === 'ENOENT') {
    console.error(`haybarn: binary missing at ${binPath}`);
    process.exit(127);
  }
  console.error(`haybarn: ${result.error.message}`);
  process.exit(1);
}

if (typeof result.status === 'number') {
  process.exit(result.status);
}

if (result.signal) {
  // Re-raise the signal so the parent shell sees what really happened.
  process.kill(process.pid, result.signal);
}

process.exit(0);
