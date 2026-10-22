#include "catch.hpp"
#include "duckdb.hpp"
#include "duckdb/main/client_context.hpp"
#include "duckdb/main/database.hpp"
#include "duckdb/main/http/http_util.hpp"

#include <atomic>

using namespace duckdb;

TEST_CASE("HTTP parameters carry the interrupt of the client context they were initialized for", "[api][http]") {
	DuckDB db(nullptr);
	HTTPHeaders headers;

	// database-level parameters have no client context to be interrupted by
	auto db_params = HTTPUtil::Get(*db.instance).InitializeParameters(*db.instance, "http://x/y");
	GetRequestInfo db_request("http://127.0.0.1:1/x", headers, *db_params, nullptr, nullptr);
	REQUIRE_FALSE(HTTPUtil::CancellationArmed(db_request));
	REQUIRE_FALSE(HTTPUtil::CancellationRequested(db_request));
	std::atomic<bool> flag {false};
	db_request.cancellation = &flag;
	REQUIRE(HTTPUtil::CancellationArmed(db_request));
	REQUIRE_FALSE(HTTPUtil::CancellationRequested(db_request));
	flag = true;
	REQUIRE(HTTPUtil::CancellationRequested(db_request));

	unique_ptr<HTTPParams> context_params;
	{
		Connection con(db);
		context_params = HTTPUtil::Get(*db.instance).InitializeParameters(*con.context, "http://x/y");
		GetRequestInfo request("http://127.0.0.1:1/x", headers, *context_params, nullptr, nullptr);
		REQUIRE(HTTPUtil::CancellationArmed(request));
		REQUIRE_FALSE(HTTPUtil::CancellationRequested(request));
		REQUIRE_FALSE(context_params->IsInterrupted());
		con.Interrupt();
		REQUIRE(context_params->IsInterrupted());
		REQUIRE(HTTPUtil::CancellationRequested(request));
	}
	// parameters that outlive their connection never touch the destroyed context
	GetRequestInfo request("http://127.0.0.1:1/x", headers, *context_params, nullptr, nullptr);
	REQUIRE_FALSE(HTTPUtil::CancellationArmed(request));
	REQUIRE_FALSE(HTTPUtil::CancellationRequested(request));
}

