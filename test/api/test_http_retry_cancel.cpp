#include "catch.hpp"
#include "duckdb.hpp"
#include "duckdb/common/http_util.hpp"
#include "duckdb/main/database.hpp"

#include <atomic>
#include <chrono>
#include <thread>

using namespace duckdb;

// RunRequestWithRetry must honour BaseRequest::cancellation between attempts, not
// only inside a backend's transfer: a 503 with Retry-After makes the backoff a
// long sleep, and a cancelled query used to sit it out before failing.
namespace {

struct RetryFixture {
	DuckDB db {nullptr};
	HTTPParams params {HTTPUtil::Get(*db.instance)};
	HTTPHeaders headers;
	std::atomic<bool> cancel {false};
	idx_t attempts = 0;

	RetryFixture() {
		params.retries = 5;
		// Long enough that finishing the backoff would blow every bound below.
		params.retry_wait_ms = 30000;
		params.retry_backoff = 1;
	}

	idx_t retry_callbacks = 0;
	// When set, the request's transfer is "aborted" by the backend: it flips the flag
	// and reports the response cancelled, as the curl backend does.
	bool cancel_during_transfer = false;

	unique_ptr<HTTPResponse> Run(GetRequestInfo &request) {
		request.cancellation = &cancel;
		return HTTPUtil::RunRequestWithRetry(
		    [&]() {
			    attempts++;
			    auto response = make_uniq<HTTPResponse>(HTTPStatusCode::ServiceUnavailable_503);
			    if (cancel_during_transfer) {
				    cancel = true;
				    response->cancelled = true;
			    }
			    return response;
		    },
		    request, [&]() { retry_callbacks++; });
	}
};

} // namespace

TEST_CASE("Cancelling a request ends its retry backoff", "[api][http]") {
	RetryFixture fixture;
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, fixture.params, nullptr, nullptr);
	request.try_request = true;

	auto started = std::chrono::steady_clock::now();
	std::thread canceller([&]() {
		std::this_thread::sleep_for(std::chrono::milliseconds(300));
		fixture.cancel = true;
	});
	auto response = fixture.Run(request);
	canceller.join();
	auto elapsed = std::chrono::steady_clock::now() - started;

	REQUIRE(response->IsCancelled());
	REQUIRE_FALSE(response->Success());
	// The first retry is immediate; the second waits the backoff, during which the cancel lands.
	REQUIRE(fixture.attempts == 2);
	REQUIRE(elapsed < std::chrono::seconds(2));
	// The retry callback ran before the second attempt, not after the cut-short backoff.
	REQUIRE(fixture.retry_callbacks == 1);
}

TEST_CASE("A request cancelled before it starts is not attempted", "[api][http]") {
	RetryFixture fixture;
	fixture.cancel = true;
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, fixture.params, nullptr, nullptr);
	request.try_request = true;
	auto response = fixture.Run(request);
	REQUIRE(response->IsCancelled());
	REQUIRE(fixture.attempts == 0);
}

TEST_CASE("Cancelling a non-try request throws an interrupt", "[api][http]") {
	RetryFixture fixture;
	fixture.cancel = true;
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, fixture.params, nullptr, nullptr);
	REQUIRE_THROWS_AS(fixture.Run(request), InterruptException);
	REQUIRE(fixture.attempts == 0);
}

TEST_CASE("A transfer the backend aborts on the flag throws an interrupt for non-try requests", "[api][http]") {
	RetryFixture fixture;
	fixture.cancel_during_transfer = true;
	GetRequestInfo request("http://127.0.0.1:1/retry", fixture.headers, fixture.params, nullptr, nullptr);
	REQUIRE_THROWS_AS(fixture.Run(request), InterruptException);
	REQUIRE(fixture.attempts == 1);
}
