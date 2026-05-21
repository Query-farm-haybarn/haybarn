#include "duckdb/main/extension_discovery.hpp"

#include "duckdb.hpp"
#include "duckdb/common/file_system.hpp"
#include "duckdb/common/string_util.hpp"
#include "duckdb/main/extension_helper.hpp"

#ifdef _WIN32
#include "duckdb/common/windows.hpp"
#include "duckdb/common/windows_util.hpp"
#elif !defined(WASM_LOADABLE_EXTENSIONS) && !defined(__EMSCRIPTEN__)
#include <dlfcn.h>
#define HAYBARN_HAVE_DLADDR 1
#endif

namespace duckdb {

// Maps DuckDB::Platform() to the npm package-name platform suffix used by the
// Haybarn extension publish pipeline. "" if the platform has no npm mapping.
static string NpmPlatformSuffix() {
	auto platform = DuckDB::Platform();
	if (platform == "linux_amd64") {
		return "linux-x64";
	}
	if (platform == "linux_arm64") {
		return "linux-arm64";
	}
	if (platform == "linux_amd64_musl") {
		return "linux-x64-musl";
	}
	if (platform == "linux_arm64_musl") {
		return "linux-arm64-musl";
	}
	if (platform == "osx_amd64") {
		return "darwin-x64";
	}
	if (platform == "osx_arm64") {
		return "darwin-arm64";
	}
	if (platform == "windows_amd64") {
		return "win32-x64";
	}
	if (platform == "windows_arm64") {
		return "win32-arm64";
	}
	return string();
}

// The Haybarn ABI suffix in the npm package name, e.g. "v1.5.3" -> "h1-5-3".
// For non-release (dev/source-id) builds this won't match any published
// package, which is fine — discovery simply finds nothing.
static string HaybarnVersionPackageSuffix() {
	auto version = ExtensionHelper::GetVersionDirectoryName();
	if (!version.empty() && (version[0] == 'v' || version[0] == 'V')) {
		version = version.substr(1);
	}
	version = StringUtil::Replace(version, ".", "-");
	return "h" + version;
}

// Parent directory by trimming the last path component. Returns "" once at the
// (POSIX or drive) root, so the upward walk terminates.
static string ParentDir(const string &path) {
	string p = path;
	while (p.size() > 1 && (p.back() == '/' || p.back() == '\\')) {
		p.pop_back();
	}
	auto pos = p.find_last_of("/\\");
	if (pos == string::npos) {
		return string();
	}
	if (pos == 0) {
		return p.substr(0, 1); // POSIX root "/"
	}
#ifdef _WIN32
	if (pos == 2 && p[1] == ':') {
		return p.substr(0, 3); // drive root "C:\"
	}
#endif
	return p.substr(0, pos);
}

// Directory of the loaded Haybarn library (the shared lib / .node addon, or the
// executable for static builds). The robust anchor for embedded use (Node
// bindings), where cwd is often not an ancestor of node_modules. "" on failure.
static string LoadedLibraryDir() {
#ifdef _WIN32
	HMODULE hmod = nullptr;
	if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
	                       reinterpret_cast<LPCWSTR>(&LoadedLibraryDir), &hmod) &&
	    hmod) {
		wchar_t buffer[4096];
		auto n = GetModuleFileNameW(hmod, buffer, 4096);
		if (n > 0 && n < 4096) {
			return ParentDir(WindowsUtil::UnicodeToUTF8(buffer));
		}
	}
	return string();
#elif defined(HAYBARN_HAVE_DLADDR)
	Dl_info info;
	if (dladdr(reinterpret_cast<void *>(&LoadedLibraryDir), &info) && info.dli_fname) {
		return ParentDir(string(info.dli_fname));
	}
	return string();
#else
	return string();
#endif
}

// Walk `start` upward; return the binary path on the first matching leaf.
// The exact @haybarn/ext-<name>-h<...>-<platsuffix> package path plus the
// <name>.duckdb_extension binary is the candidate criterion; the binary's
// RSA signature (verified at load time) is the trust gate.
static string WalkForLeaf(FileSystem &fs, const string &start, const string &leaf, const string &binary_name) {
	string dir = start;
	while (!dir.empty()) {
		auto candidate = fs.JoinPath(fs.JoinPath(fs.JoinPath(dir, "node_modules"), "@haybarn"), leaf);
		if (fs.DirectoryExists(candidate)) {
			auto binary = fs.JoinPath(fs.JoinPath(candidate, "bin"), binary_name);
			if (fs.FileExists(binary)) {
				return binary;
			}
		}
		auto parent = ParentDir(dir);
		if (parent == dir) {
			break;
		}
		dir = parent;
	}
	return string();
}

string TryDiscoverNpmExtension(DatabaseInstance &db, FileSystem &fs, const string &extension) {
	auto platsuffix = NpmPlatformSuffix();
	if (platsuffix.empty()) {
		return string();
	}
	auto name = ExtensionHelper::ApplyExtensionAlias(StringUtil::Lower(extension));
	auto leaf = "ext-" + name + "-" + HaybarnVersionPackageSuffix() + "-" + platsuffix;
	auto binary_name = name + ".duckdb_extension";

	// Anchors, in priority order: process cwd first, then the loaded library
	// directory (covers embedded use where cwd is unrelated to node_modules).
	vector<string> anchors;
	auto cwd = FileSystem::GetWorkingDirectory();
	if (!cwd.empty()) {
		anchors.push_back(cwd);
	}
	auto lib_dir = LoadedLibraryDir();
	if (!lib_dir.empty() && lib_dir != cwd) {
		anchors.push_back(lib_dir);
	}

	for (auto &anchor : anchors) {
		auto found = WalkForLeaf(fs, anchor, leaf, binary_name);
		if (!found.empty()) {
			return found;
		}
	}
	return string();
}

} // namespace duckdb
