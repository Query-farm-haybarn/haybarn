#include "duckdb/parser/statement/load_statement.hpp"
#include "duckdb/planner/binder.hpp"
#include "duckdb/planner/operator/logical_load.hpp"
#include "duckdb/main/database.hpp"
#include "duckdb/main/extension_install_info.hpp"
#include "duckdb/main/extension_repository_manager.hpp"
#include "duckdb/common/string_util.hpp"
#include <algorithm>

namespace duckdb {

BoundStatement Binder::Bind(LoadStatement &stmt) {
	BoundStatement result;
	result.types = LoadInfo::GetResultTypes(stmt.info->load_type);
	result.names = LoadInfo::GetResultNames(stmt.info->load_type);

	// Haybarn: the VERSION clause becomes a path segment in the download URL with no escaping,
	// so reject anything that could reshape that URL rather than name a build.
	if (!stmt.info->version.empty()) {
		for (auto c : stmt.info->version) {
			if (c == '/' || c == '\\' || StringUtil::CharacterIsSpace(c)) {
				throw BinderException("Invalid extension version '%s': must not contain path separators or whitespace",
				                      stmt.info->version);
			}
		}
		if (StringUtil::Contains(stmt.info->version, "..")) {
			throw BinderException("Invalid extension version '%s': must not contain '..'", stmt.info->version);
		}
	}

	// Ensure the repository exists if it's an alias
	if (!stmt.info->repository.empty() && stmt.info->repo_is_alias) {
		auto &db = DatabaseInstance::GetDatabase(context);
		auto &fs = FileSystem::GetLocal(db);
		ExtensionRepository repository;
		auto repository_url = ExtensionRepository::TryGetRepositoryUrl(stmt.info->repository);
		if (repository_url.empty() &&
		    !ExtensionRepositoryManager::TryGetRepository(db, fs, stmt.info->repository, repository)) {
			throw BinderException("'%s' is not a known repository name. Are you trying to query from a repository by "
			                      "path? Use single quotes: `FROM '%s'`",
			                      stmt.info->repository, stmt.info->repository);
		}
	}

	auto load_type = stmt.info->load_type;
	result.plan = make_uniq<LogicalLoad>(std::move(stmt.info));

	auto &properties = GetStatementProperties();
	properties.output_type = QueryResultOutputType::FORCE_MATERIALIZED;
	properties.return_type =
	    load_type == LoadType::CREATE_REPOSITORY ? StatementReturnType::QUERY_RESULT : StatementReturnType::NOTHING;
	return result;
}

} // namespace duckdb
