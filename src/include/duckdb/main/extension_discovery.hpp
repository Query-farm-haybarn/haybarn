//===----------------------------------------------------------------------===//
//                         Haybarn
//
// duckdb/main/extension_discovery.hpp
//
// Haybarn addition: discover extensions installed via npm into node_modules.
// See HAYBARN/ and ideas/extensions-from-npm-pypi.md (Model B / Phase 3).
//
//===----------------------------------------------------------------------===//

#pragma once

#include "duckdb/common/common.hpp"

namespace duckdb {
class DatabaseInstance;
class FileSystem;

//! Try to locate an npm-installed extension binary for `extension` (a bare
//! name, e.g. "avro"). Walks node_modules upward from the process working
//! directory and from the directory of the loaded Haybarn library, looking for
//! `@haybarn/ext-<name>-h<M>-<m>-<p>-<platsuffix>/bin/<name>.duckdb_extension`
//! gated on the leaf's package.json containing a top-level "haybarn" object.
//! Returns the absolute path to the uncompressed `.duckdb_extension` on the
//! first (nearest) match, or an empty string if none is found. Never throws.
//! The returned file is loaded in place and still subject to the normal
//! Haybarn RSA signature verification at load time.
string TryDiscoverNpmExtension(DatabaseInstance &db, FileSystem &fs, const string &extension);

} // namespace duckdb
