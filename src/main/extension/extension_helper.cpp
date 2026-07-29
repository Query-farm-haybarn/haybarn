#include "duckdb/main/extension_helper.hpp"

#include "duckdb/common/file_system.hpp"
#include "duckdb/common/local_file_system.hpp"
#include "duckdb/common/serializer/binary_deserializer.hpp"
#include "duckdb/common/serializer/buffered_file_reader.hpp"
#include "duckdb/common/string_util.hpp"
#include "duckdb/common/windows.hpp"
#include "duckdb/logging/logger.hpp"
#include "duckdb/main/client_context.hpp"
#include "duckdb/main/database.hpp"
#include "duckdb/main/database_file_opener.hpp"
#include "duckdb/main/extension.hpp"
#include "duckdb/main/extension_install_info.hpp"
#include "duckdb/main/settings.hpp"

// Note that c++ preprocessor doesn't have a nice way to clean this up so we need to set the defines we use to false
// explicitly when they are undefined
#ifndef DUCKDB_EXTENSION_CORE_FUNCTIONS_LINKED
#define DUCKDB_EXTENSION_CORE_FUNCTIONS_LINKED false
#endif

#ifndef DUCKDB_EXTENSION_ICU_LINKED
#define DUCKDB_EXTENSION_ICU_LINKED false
#endif

#ifndef DUCKDB_EXTENSION_EXCEL_LINKED
#define DUCKDB_EXTENSION_EXCEL_LINKED false
#endif

#ifndef DUCKDB_EXTENSION_PARQUET_LINKED
#define DUCKDB_EXTENSION_PARQUET_LINKED false
#endif

#ifndef DUCKDB_EXTENSION_TPCH_LINKED
#define DUCKDB_EXTENSION_TPCH_LINKED false
#endif

#ifndef DUCKDB_EXTENSION_TPCDS_LINKED
#define DUCKDB_EXTENSION_TPCDS_LINKED false
#endif

#ifndef DUCKDB_EXTENSION_HTTPFS_LINKED
#define DUCKDB_EXTENSION_HTTPFS_LINKED false
#endif

#ifndef DUCKDB_EXTENSION_JSON_LINKED
#define DUCKDB_EXTENSION_JSON_LINKED false
#endif

#ifndef DUCKDB_EXTENSION_AUTOCOMPLETE_LINKED
#define DUCKDB_EXTENSION_AUTOCOMPLETE_LINKED false
#endif

// Load the generated header file containing our list of extension headers
#if defined(GENERATED_EXTENSION_HEADERS) && GENERATED_EXTENSION_HEADERS && !defined(DUCKDB_AMALGAMATION)
#include "duckdb/main/extension/generated_extension_loader.hpp"
#else
// TODO: rewrite package_build.py to allow also loading out-of-tree extensions in non-cmake builds, after that
//		 these can be removed
#if DUCKDB_EXTENSION_CORE_FUNCTIONS_LINKED
#include "core_functions_extension.hpp"
#endif

#if DUCKDB_EXTENSION_ICU_LINKED
#include "icu_extension.hpp"
#endif

#if DUCKDB_EXTENSION_PARQUET_LINKED
#include "parquet_extension.hpp"
#endif

#if DUCKDB_EXTENSION_TPCH_LINKED
#include "tpch_extension.hpp"
#endif

#if DUCKDB_EXTENSION_TPCDS_LINKED
#include "tpcds_extension.hpp"
#endif

#if DUCKDB_EXTENSION_JSON_LINKED
#include "json_extension.hpp"
#endif

#if DUCKDB_EXTENSION_AUTOCOMPLETE_LINKED
#include "autocomplete_extension.hpp"
#endif

#endif

namespace duckdb {

//===--------------------------------------------------------------------===//
// Default Extensions
//===--------------------------------------------------------------------===//
static const DefaultExtension internal_extensions[] = {
    {"core_functions", "Core function library", DUCKDB_EXTENSION_CORE_FUNCTIONS_LINKED},
    {"icu", "Adds support for time zones and collations using the ICU library", DUCKDB_EXTENSION_ICU_LINKED},
    {"excel", "Adds support for Excel-like format strings", DUCKDB_EXTENSION_EXCEL_LINKED},
    {"parquet", "Adds support for reading and writing parquet files", DUCKDB_EXTENSION_PARQUET_LINKED},
    {"tpch", "Adds TPC-H data generation and query support", DUCKDB_EXTENSION_TPCH_LINKED},
    {"tpcds", "Adds TPC-DS data generation and query support", DUCKDB_EXTENSION_TPCDS_LINKED},
    {"httpfs", "Adds support for reading and writing files over a HTTP(S) connection", DUCKDB_EXTENSION_HTTPFS_LINKED},
    {"json", "Adds support for JSON operations", DUCKDB_EXTENSION_JSON_LINKED},
    {"autocomplete", "Adds support for autocomplete in the shell", DUCKDB_EXTENSION_AUTOCOMPLETE_LINKED},
    // Haybarn: motherduck removed — it's a proprietary cloud product specific
    // to MotherDuck Inc., not appropriate to advertise as a Haybarn extension.
    // Users who need it can manually INSTALL/LOAD against the DuckDB upstream
    // repository.
    {"mysql_scanner", "Adds support for connecting to a MySQL database", false},
    {"odbc_scanner", "Adds support for connecting to remote databases over ODBC", false},
    {"sqlite_scanner", "Adds support for reading and writing SQLite database files", false},
    {"postgres_scanner", "Adds support for connecting to a Postgres database", false},
    {"inet", "Adds support for IP-related data types and functions", false},
    {"spatial", "Geospatial extension that adds support for working with spatial data and functions", false},
    {"aws", "Provides features that depend on the AWS SDK", false},
    {"azure", "Adds a filesystem abstraction for Azure blob storage to DuckDB", false},
    {"encodings", "All unicode encodings to UTF-8", false},
    {"iceberg", "Adds support for Apache Iceberg", false},
    {"vss", "Adds indexing support to accelerate Vector Similarity Search", false},
    {"delta", "Adds support for Delta Lake", false},
    {"fts", "Adds support for Full-Text Search Indexes", false},
    {"ui", "Adds local UI for DuckDB", false},
    {"ducklake", "Adds support for DuckLake, SQL as a Lakehouse Format", false},
    {"quack", "The DuckDB 'Quack' Client/Server Protocol", false},
    // Haybarn: vortex + lance removed — both are commercial products with
    // upstream packages that wouldn't verify against the Haybarn trust root.
    // Users who need them can manually INSTALL/LOAD against the upstream
    // DuckDB repository.
    {"avro", "Adds support for reading Avro files", false},
    {"unity_catalog", "Adds support for connecting to Unity Catalog", false},
    {nullptr, nullptr, false}};

idx_t ExtensionHelper::DefaultExtensionCount() {
	idx_t index;
	for (index = 0; internal_extensions[index].name != nullptr; index++) {
	}
	return index;
}

DefaultExtension ExtensionHelper::GetDefaultExtension(idx_t index) {
	D_ASSERT(index < DefaultExtensionCount());
	return internal_extensions[index];
}

//===--------------------------------------------------------------------===//
// Allow Auto-Install Extensions
//===--------------------------------------------------------------------===//
// Haybarn: motherduck dropped from the auto-install allow list (see comment
// in internal_extensions above). The rest mirror upstream.
static const char *const auto_install[] = {
    "postgres_scanner", "mysql_scanner", "odbc_scanner", "sqlite_scanner",
    "delta",            "iceberg",       "unity_catalog", "ui",       "ducklake",
    nullptr};

// TODO: unify with new autoload mechanism
bool ExtensionHelper::AllowAutoInstall(const string &extension) {
	auto extension_name = ApplyExtensionAlias(extension);
	for (idx_t i = 0; auto_install[i]; i++) {
		if (extension_name == auto_install[i]) {
			return true;
		}
	}
	return false;
}

bool ExtensionHelper::CanAutoloadExtension(const string &ext_name) {
#ifdef DUCKDB_DISABLE_EXTENSION_LOAD
	return false;
#endif

	if (ext_name.empty()) {
		return false;
	}
	for (const auto &ext : AUTOLOADABLE_EXTENSIONS) {
		if (ext_name == ext) {
			return true;
		}
	}
	return false;
}

string ExtensionHelper::AddExtensionInstallHintToErrorMsg(ClientContext &context, const string &base_error,
                                                          const string &extension_name) {
	return AddExtensionInstallHintToErrorMsg(DatabaseInstance::GetDatabase(context), base_error, extension_name);
}
string ExtensionHelper::AddExtensionInstallHintToErrorMsg(DatabaseInstance &db, const string &base_error,
                                                          const string &extension_name) {
	string install_hint;

	if (!ExtensionHelper::CanAutoloadExtension(extension_name)) {
		install_hint = "Please try installing and loading the " + extension_name + " extension:\nINSTALL " +
		               extension_name + ";\nLOAD " + extension_name + ";\n\n";
	} else if (!Settings::Get<AutoloadKnownExtensionsSetting>(db)) {
		install_hint =
		    "Please try installing and loading the " + extension_name + " extension by running:\nINSTALL " +
		    extension_name + ";\nLOAD " + extension_name +
		    ";\n\nAlternatively, consider enabling auto-install "
		    "and auto-load by running:\nSET autoinstall_known_extensions=1;\nSET autoload_known_extensions=1;";
	} else if (!Settings::Get<AutoinstallKnownExtensionsSetting>(db)) {
		install_hint =
		    "Please try installing the " + extension_name + " extension by running:\nINSTALL " + extension_name +
		    ";\n\nAlternatively, consider enabling autoinstall by running:\nSET autoinstall_known_extensions=1;";
	}

	if (!install_hint.empty()) {
		return base_error + "\n\n" + install_hint;
	}

	return base_error;
}

bool ExtensionHelper::TryAutoLoadExtension(ClientContext &context, const string &extension_name) noexcept {
	if (context.db->ExtensionIsLoaded(extension_name)) {
		return true;
	}
	try {
		if (Settings::Get<AutoinstallKnownExtensionsSetting>(context)) {
			auto autoinstall_repo_setting = Settings::Get<AutoinstallExtensionRepositorySetting>(context);
			auto autoinstall_repo = ExtensionRepository::GetRepositoryByUrl(autoinstall_repo_setting);
			ExtensionInstallOptions options;
			options.repository = autoinstall_repo;
			ExtensionHelper::InstallExtension(context, extension_name, options);
		}
		ExtensionHelper::LoadExternalExtension(context, extension_name);
		return true;
	} catch (...) {
		return false;
	}
}

static string GetAutoInstallExtensionsRepository(const DBConfig &config) {
	string repository_url = Settings::Get<AutoinstallExtensionRepositorySetting>(config);
	if (repository_url.empty()) {
		repository_url = Settings::Get<CustomExtensionRepositorySetting>(config);
	}
	return repository_url;
}

bool ExtensionHelper::TryAutoLoadExtension(DatabaseInstance &instance, const string &extension_name) noexcept {
	if (instance.ExtensionIsLoaded(extension_name)) {
		return true;
	}
	auto &dbconfig = DBConfig::GetConfig(instance);
	try {
		auto &fs = FileSystem::GetFileSystem(instance);
		if (Settings::Get<AutoinstallKnownExtensionsSetting>(instance)) {
			auto repository_url = GetAutoInstallExtensionsRepository(dbconfig);
			auto autoinstall_repo = ExtensionRepository::GetRepositoryByUrl(repository_url);
			ExtensionInstallOptions options;
			options.repository = autoinstall_repo;
			ExtensionHelper::InstallExtension(instance, fs, extension_name, options);
		}
		if (Settings::Get<AutoloadKnownExtensionsSetting>(instance)) {
			ExtensionHelper::LoadExternalExtension(instance, fs, extension_name);
			return true;
		}
		return false;
	} catch (...) {
		return false;
	}
}

bool ExtensionHelper::TryAutoLoadAvailableExtension(DatabaseInstance &instance, const string &extension_name) noexcept {
	if (instance.ExtensionIsLoaded(extension_name)) {
		return true;
	}
	try {
		auto &fs = FileSystem::GetFileSystem(instance);
		ExtensionHelper::LoadExternalExtension(instance, fs, extension_name);
		return true;
	} catch (...) {
		return false;
	}
}

static ExtensionUpdateResult UpdateExtensionInternal(ClientContext &context, DatabaseInstance &db, FileSystem &fs,
                                                     const string &full_extension_path, const string &extension_name) {
	ExtensionUpdateResult result;
	result.extension_name = extension_name;

	if (!fs.FileExists(full_extension_path)) {
		result.tag = ExtensionUpdateResultTag::NOT_INSTALLED;
		return result;
	}

	// Extension exists, check for .info file
	const string info_file_path = full_extension_path + ".info";
	if (!fs.FileExists(info_file_path)) {
		result.tag = ExtensionUpdateResultTag::MISSING_INSTALL_INFO;
		return result;
	}

	// Parse the version of the extension before updating
	auto ext_binary_handle = fs.OpenFile(full_extension_path, FileOpenFlags::FILE_FLAGS_READ);
	auto parsed_metadata = ExtensionHelper::ParseExtensionMetaData(*ext_binary_handle);
	if (!parsed_metadata.AppearsValid() && !Settings::Get<AllowExtensionsMetadataMismatchSetting>(context)) {
		throw IOException(
		    "Failed to update extension: '%s', the metadata of the extension appears invalid! To resolve this, either "
		    "reinstall the extension using 'FORCE INSTALL %s', manually remove the file '%s', or enable '"
		    "SET allow_extensions_metadata_mismatch=true'",
		    extension_name, extension_name, full_extension_path);
	}

	result.prev_version = parsed_metadata.AppearsValid() ? parsed_metadata.extension_version : "";

	auto extension_install_info = ExtensionInstallInfo::TryReadInfoFile(fs, info_file_path, extension_name);

	// Early out: no info file found
	if (extension_install_info->mode == ExtensionInstallMode::UNKNOWN) {
		result.tag = ExtensionUpdateResultTag::MISSING_INSTALL_INFO;
		return result;
	}

	// Early out: we can only update extensions from repositories
	if (extension_install_info->mode != ExtensionInstallMode::REPOSITORY) {
		result.tag = ExtensionUpdateResultTag::NOT_A_REPOSITORY;
		result.installed_version = result.prev_version;
		return result;
	}

	auto repository_from_info = ExtensionRepository::GetRepositoryByUrl(extension_install_info->repository_url);
	result.repository = repository_from_info.ToReadableString();

	// Haybarn early out: a pinned extension is pinned on purpose. The install below is a force
	// install with no version, which would resolve to the repository's mutable "latest" slot and
	// quietly move the extension off its pin. Report it and leave it where it is.
	if (!extension_install_info->pinned_version.empty()) {
		result.tag = ExtensionUpdateResultTag::PINNED;
		result.installed_version = result.prev_version;
		return result;
	}

	// Force install the full url found in this file, enabling etags to ensure efficient updating
	ExtensionInstallOptions options;
	options.repository = repository_from_info;
	options.force_install = true;
	options.use_etags = true;

	unique_ptr<ExtensionInstallInfo> install_result;
	try {
		install_result = ExtensionHelper::InstallExtension(context, extension_name, options);
	} catch (std::exception &e) {
		ErrorData error(e);
		error.Throw("Extension updating failed when trying to install '" + extension_name + "', original error: ");
	}

	result.installed_version = install_result->version;

	if (result.installed_version.empty()) {
		result.tag = ExtensionUpdateResultTag::REDOWNLOADED;
	} else if (result.installed_version != result.prev_version) {
		result.tag = ExtensionUpdateResultTag::UPDATED;
	} else {
		result.tag = ExtensionUpdateResultTag::NO_UPDATE_AVAILABLE;
	}

	return result;
}

vector<ExtensionUpdateResult> ExtensionHelper::UpdateExtensions(ClientContext &context) {
	auto &fs = FileSystem::GetFileSystem(context);

	vector<ExtensionUpdateResult> result;
	DatabaseInstance &db = DatabaseInstance::GetDatabase(context);

#ifndef WASM_LOADABLE_EXTENSIONS
	case_insensitive_set_t seen_extensions;

	// scan the install directory for installed extensions
	auto ext_directory = ExtensionHelper::ExtensionDirectory(db, fs);
	fs.ListFiles(ext_directory, [&](const string &path, bool is_directory) {
		if (!StringUtil::EndsWith(path, ".duckdb_extension")) {
			return;
		}

		auto extension_file_name = StringUtil::GetFileName(path);
		auto extension_name = StringUtil::Split(extension_file_name, ".")[0];

		seen_extensions.insert(extension_name);

		result.push_back(UpdateExtensionInternal(context, db, fs, fs.JoinPath(ext_directory, path), extension_name));
	});
#endif

	return result;
}

ExtensionUpdateResult ExtensionHelper::UpdateExtension(ClientContext &context, const string &extension_name) {
	auto &fs = FileSystem::GetFileSystem(context);
	DatabaseInstance &db = DatabaseInstance::GetDatabase(context);
	auto ext_directory = ExtensionHelper::ExtensionDirectory(db, fs);

	auto full_extension_path = fs.JoinPath(ext_directory, extension_name + ".duckdb_extension");

	auto update_result = UpdateExtensionInternal(context, db, fs, full_extension_path, extension_name);

	if (update_result.tag == ExtensionUpdateResultTag::NOT_INSTALLED) {
		throw InvalidInputException("Failed to update the extension '%s', the extension is not installed!",
		                            extension_name);
	} else if (update_result.tag == ExtensionUpdateResultTag::UNKNOWN) {
		throw InternalException("Failed to update extension '%s', an unknown error occurred", extension_name);
	}
	return update_result;
}

void ExtensionHelper::AutoLoadExtension(ClientContext &context, const string &extension_name) {
	return ExtensionHelper::AutoLoadExtension(*context.db, extension_name);
}

void ExtensionHelper::AutoLoadExtension(DatabaseInstance &db, const string &extension_name) {
	if (db.ExtensionIsLoaded(extension_name)) {
		// Avoid downloading again
		return;
	}
	auto &dbconfig = DBConfig::GetConfig(db);
	try {
		auto &fs = FileSystem::GetLocal(db);
#ifndef DUCKDB_WASM
		if (Settings::Get<AutoinstallKnownExtensionsSetting>(db)) {
			auto repository_url = GetAutoInstallExtensionsRepository(dbconfig);
			auto autoinstall_repo = ExtensionRepository::GetRepositoryByUrl(repository_url);
			ExtensionInstallOptions options;
			options.repository = autoinstall_repo;
			ExtensionHelper::InstallExtension(db, fs, extension_name, options);
		}
#endif
		ExtensionHelper::LoadExternalExtension(db, fs, extension_name);
		DUCKDB_LOG_INFO(db, "Loaded extension '%s'", extension_name);
	} catch (std::exception &e) {
		ErrorData error(e);
		throw AutoloadException(extension_name, error.RawMessage());
	}
}

// Haybarn: the single RSA trust root used for both core and community
// extensions. Upstream DuckDB carries 21 core keys + 19 community keys; we
// replace the lot with one Haybarn-controlled key. Every extension Haybarn
// loads — core OR community — must be signed by the matching Haybarn private
// key (HAYBARN_EXTENSION_SIGNING_PK), served from one of the Haybarn-operated
// repository URLs. DuckDB-signed extensions intentionally will not verify.
static const char *const HAYBARN_TRUST_ROOT = R"(
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsaa0V5d4IEKBv7UX7uwj
KXrn42rNYS7AHBiQJ5bXyHO+0JZGQL/lvByDIa3zuGpo/M89AAl8ziCoBhOHJTyr
7X0tNDTGfBT+8Kk+QeLuWJmkvRCf1A5TNmmQUm4elYs7KRbks8YqG2rIKOVl8heG
3JHbcqgSXjcp+PCLSVDGh/1S1nQeYa+vfooEqL+myVKy2FQXxziYmjbhT69cx7xx
K9zepc3vGC7rJMCUOrBoFkJHrFJ6f24ag2/nFaHCuHKWDgLrZ6bbgjopUE6504Uv
zkL8UKYc42Qa+zR0qd5d6QC3E+2EnYmg0GPE7u0xGEAANdU2KuwXrM8IfNpIVKBK
iQIDAQAB
-----END PUBLIC KEY-----
)";

static const char *const public_keys[] = {HAYBARN_TRUST_ROOT, nullptr};

// Same trust root as `public_keys` — Haybarn deliberately uses ONE key to sign
// both core and community extensions. Two distribution channels (core and
// community-extensions buckets) but one cryptographic identity. The arrays stay
// separate (rather than collapsing into one) so the upstream-shaped
// `allow_community_extensions` gating still works: a user can disallow
// community-installed extensions and the verification loop in GetPublicKeys()
// below will skip this array — even though the keys are identical, the *flag*
// is the gate, not the key list.
static const char *const community_public_keys[] = {HAYBARN_TRUST_ROOT, nullptr};

const vector<string> ExtensionHelper::GetPublicKeys(bool allow_community_extensions) {
	vector<string> keys;
	for (idx_t i = 0; public_keys[i]; i++) {
		keys.emplace_back(public_keys[i]);
	}
	if (allow_community_extensions) {
		for (idx_t i = 0; community_public_keys[i]; i++) {
			keys.emplace_back(community_public_keys[i]);
		}
	}
	return keys;
}

} // namespace duckdb
