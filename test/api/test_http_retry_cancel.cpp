#include "catch.hpp"
#include "duckdb.hpp"
#include "duckdb/main/client_context.hpp"
#include "duckdb/main/database.hpp"
#include "duckdb/main/http/http_util.hpp"

#include <atomic>
#include <chrono>
#include <cstring>
#include <thread>

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

// The retry loop honours cancellation between attempts and during the back-off, not only inside a backend's
// transfer: a 503 with Retry-After makes the back-off a long sleep, which an interrupted query used to sit out.
// Cancellation comes from the request's own flag or from the interrupt of the client context its parameters were
// initialized for.
namespace {

using std::chrono::milliseconds;
using std::chrono::steady_clock;

struct RetryFixture {
	DuckDB db {nullptr};
	Connection con {db};
	HTTPHeaders headers;
	std::atomic<bool> cancel {false};
	idx_t attempts = 0;
	idx_t retry_callbacks = 0;
	//! The backend aborts the transfer: it flips the flag and reports the response cancelled, as httpfs does.
	bool cancel_during_transfer = false;

	unique_ptr<HTTPParams> Params(bool with_context) {
		const string url = "http://127.0.0.1:1/retry";
		auto params = with_context ? HTTPUtil::Get(*db.instance).InitializeParameters(*con.context, url)
		                           : HTTPUtil::Get(*db.instance).InitializeParameters(*db.instance, url);
		params->retries = 5;
		params->retry_wait_ms = 100;
		params->retry_backoff = 1;
		return params;
	}

	unique_ptr<HTTPResponse> Run(GetRequestInfo &request, bool use_flag = true) {
		if (use_flag) {
			request.cancellation = &cancel;
		}
		return HTTPUtil::RunRequestWithRetry(
		    [&]() {
			    attempts++;
			    // The server asks for 10 s between attempts, far beyond every bound below.
			    auto response = make_uniq<HTTPResponse>(HTTPStatusCode::ServiceUnavailable_503);
			    response->headers.Insert("Retry-After", "10");
			    if (cancel_during_transfer) {
				    cancel = true;
				    response->cancelled = true;
			    }
			    return response;
		    },
		    request, [&]() { retry_callbacks++; });
	}
};

std::thread CancelAfter(milliseconds delay, const std::function<void()> &cancel) {
	return std::thread([delay, cancel]() {
		std::this_thread::sleep_for(delay);
		cancel();
	});
}

} // namespace

TEST_CASE("Cancelling a request ends its retry back-off", "[api][http]") {
	RetryFixture fixture;
	auto params = fixture.Params(false);
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, *params, nullptr, nullptr);
	request.try_request = true;

	auto canceller = CancelAfter(milliseconds(300), [&]() { fixture.cancel = true; });
	auto started = steady_clock::now();
	auto response = fixture.Run(request);
	canceller.join();
	auto elapsed = steady_clock::now() - started;

	REQUIRE(response->IsCancelled());
	REQUIRE_FALSE(response->Success());
	REQUIRE(fixture.attempts == 1);
	REQUIRE(elapsed < std::chrono::seconds(3));
	// The retry callback prepares an attempt that never happens
	REQUIRE(fixture.retry_callbacks == 0);
}

TEST_CASE("A request cancelled before it starts is not attempted", "[api][http]") {
	RetryFixture fixture;
	fixture.cancel = true;
	auto params = fixture.Params(false);
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, *params, nullptr, nullptr);
	request.try_request = true;
	auto response = fixture.Run(request);
	REQUIRE(response->IsCancelled());
	REQUIRE(fixture.attempts == 0);
}

TEST_CASE("Cancelling a non-try request throws an interrupt", "[api][http]") {
	RetryFixture fixture;
	fixture.cancel = true;
	auto params = fixture.Params(false);
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, *params, nullptr, nullptr);
	REQUIRE_THROWS_AS(fixture.Run(request), InterruptException);
	REQUIRE(fixture.attempts == 0);
}

TEST_CASE("A transfer the backend aborts on cancellation throws an interrupt for non-try requests", "[api][http]") {
	RetryFixture fixture;
	fixture.cancel_during_transfer = true;
	auto params = fixture.Params(false);
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, *params, nullptr, nullptr);
	REQUIRE_THROWS_AS(fixture.Run(request), InterruptException);
	REQUIRE(fixture.attempts == 1);
}

TEST_CASE("Interrupting the query of the opening client context ends the retry back-off", "[api][http]") {
	RetryFixture fixture;
	auto params = fixture.Params(true);
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, *params, nullptr, nullptr);

	auto canceller = CancelAfter(milliseconds(300), [&]() { fixture.con.Interrupt(); });
	auto started = steady_clock::now();
	REQUIRE_THROWS_AS(fixture.Run(request, false), InterruptException);
	canceller.join();
	REQUIRE(fixture.attempts == 1);
	REQUIRE(steady_clock::now() - started < std::chrono::seconds(3));
}

TEST_CASE("A coordinator's retry budget stops waiting once its client context is interrupted", "[api][http]") {
	RetryFixture fixture;
	auto params = fixture.Params(true);
	params->retry_wait_ms = 30000;
	HTTPRetryBudget budget(*params, HTTPRetryOutcomeOwner::COORDINATOR);

	auto canceller = CancelAfter(milliseconds(300), [&]() { fixture.con.Interrupt(); });
	auto started = steady_clock::now();
	idx_t attempts = 0;
	budget.Run([&]() {
		attempts++;
		return HTTPRetryDecision::Throttled("10");
	});
	canceller.join();
	REQUIRE(steady_clock::now() - started < std::chrono::seconds(3));
	REQUIRE(attempts == 1);
	REQUIRE(budget.CancellationRequested());
	// a cancelled operation admits no further retry and is not charged for one
	REQUIRE(budget.RetriesUsed() == 1);
	idx_t more_attempts = 0;
	budget.Run([&]() {
		more_attempts++;
		return HTTPRetryDecision::Retry();
	});
	REQUIRE(more_attempts == 1);
	REQUIRE(budget.RetriesUsed() == 1);
}
