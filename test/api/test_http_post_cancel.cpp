#include "catch.hpp"
#include "duckdb.hpp"
#include "duckdb/common/http_util.hpp"
#include "duckdb/main/database.hpp"

#include <atomic>
#include <chrono>
#include <cstring>
#include <thread>

#ifndef _WIN32
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

using namespace duckdb;

#ifndef _WIN32
namespace {

// A minimal loopback TCP server that accepts a connection, reads the request, and then
// stalls — it never sends a response. This holds the curl client in the "waiting for the
// response" phase, where the only thing that can end the request is the cancellation flag
// being observed by the progress (xferinfo) callback. The dispatcher polls at a 100ms
// ceiling, so a set flag is observed within ~100ms.
struct StallServer {
	int listen_fd = -1;
	uint16_t port = 0;
	std::atomic<bool> stop {false};
	std::thread th;

	void Start() {
		listen_fd = socket(AF_INET, SOCK_STREAM, 0);
		REQUIRE(listen_fd >= 0);
		int yes = 1;
		setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
		sockaddr_in addr {};
		addr.sin_family = AF_INET;
		addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
		addr.sin_port = 0; // ephemeral
		REQUIRE(bind(listen_fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) == 0);
		socklen_t len = sizeof(addr);
		REQUIRE(getsockname(listen_fd, reinterpret_cast<sockaddr *>(&addr), &len) == 0);
		port = ntohs(addr.sin_port);
		REQUIRE(listen(listen_fd, 8) == 0);
		th = std::thread([this] {
			while (!stop.load()) {
				int fd = accept(listen_fd, nullptr, nullptr);
				if (fd < 0) {
					break; // listen socket closed on Stop()
				}
				char buf[2048];
				recv(fd, buf, sizeof(buf), 0); // drain the request line/headers, then stall
				while (!stop.load()) {
					std::this_thread::sleep_for(std::chrono::milliseconds(50));
				}
				close(fd);
			}
		});
	}

	void Stop() {
		stop.store(true);
		if (listen_fd >= 0) {
			shutdown(listen_fd, SHUT_RDWR);
			close(listen_fd);
			listen_fd = -1;
		}
		if (th.joinable()) {
			th.join();
		}
	}

	~StallServer() {
		Stop();
	}
};

int64_t ElapsedSeconds(std::chrono::steady_clock::time_point start) {
	return std::chrono::duration_cast<std::chrono::seconds>(std::chrono::steady_clock::now() - start).count();
}

// A loopback server that reads the request and replies with a small 200 response, so a
// normal (uncancelled) POST completes — used to prove the cancellation plumbing leaves the
// happy path untouched.
struct RespondServer {
	int listen_fd = -1;
	uint16_t port = 0;
	std::atomic<bool> stop {false};
	std::thread th;

	void Start() {
		listen_fd = socket(AF_INET, SOCK_STREAM, 0);
		REQUIRE(listen_fd >= 0);
		int yes = 1;
		setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
		sockaddr_in addr {};
		addr.sin_family = AF_INET;
		addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
		addr.sin_port = 0;
		REQUIRE(bind(listen_fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) == 0);
		socklen_t len = sizeof(addr);
		REQUIRE(getsockname(listen_fd, reinterpret_cast<sockaddr *>(&addr), &len) == 0);
		port = ntohs(addr.sin_port);
		REQUIRE(listen(listen_fd, 8) == 0);
		th = std::thread([this] {
			while (!stop.load()) {
				int fd = accept(listen_fd, nullptr, nullptr);
				if (fd < 0) {
					break;
				}
				char buf[4096];
				recv(fd, buf, sizeof(buf), 0);
				const char *resp = "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok";
				send(fd, resp, strlen(resp), 0);
				close(fd);
			}
		});
	}

	void Stop() {
		stop.store(true);
		if (listen_fd >= 0) {
			shutdown(listen_fd, SHUT_RDWR);
			close(listen_fd);
			listen_fd = -1;
		}
		if (th.joinable()) {
			th.join();
		}
	}

	~RespondServer() {
		Stop();
	}
};

} // namespace

// Hidden ([.]) because it only does anything in a build with httpfs linked; invoke it by name
// or by the [httpfs] tag. It exercises the real curl backend: HTTPFSCurlUtil::Post() arming
// CURLOPT_XFERINFOFUNCTION and translating a flag-driven CURLE_ABORTED_BY_CALLBACK into a
// terminal cancelled response.
TEST_CASE("HTTP POST request honors the cancellation flag", "[httpfs][.]") {
	DuckDB db(nullptr);
	Connection con(db);
	auto load = con.Query("LOAD httpfs");
	if (load->HasError()) {
		// httpfs not linked into this build — nothing to verify here.
		return;
	}

	auto &http_util = HTTPUtil::Get(*db.instance);
	StallServer server;
	server.Start();
	const string url = "http://127.0.0.1:" + to_string(server.port) + "/cancel-test";
	const string body = "payload";

	SECTION("a flag set before the request returns immediately and is terminal") {
		auto params = http_util.InitializeParameters(*db.instance, url);
		std::atomic<bool> cancel {true};
		PostRequestInfo post(url, HTTPHeaders(), *params, const_data_ptr_cast(body.data()), body.size());
		post.cancellation = &cancel;
		post.try_request = true; // return the failure instead of throwing

		auto start = std::chrono::steady_clock::now();
		auto resp = http_util.Request(post);

		REQUIRE(resp);
		REQUIRE(resp->cancelled);
		REQUIRE_FALSE(resp->ShouldRetry()); // must not trigger the retry/backoff loop
		// Far below a connect timeout and the cumulative retry-backoff budget.
		REQUIRE(ElapsedSeconds(start) < 10);
	}

	SECTION("a flag flipped mid-flight from another thread cancels the in-flight request") {
		auto params = http_util.InitializeParameters(*db.instance, url);
		std::atomic<bool> cancel {false};
		PostRequestInfo post(url, HTTPHeaders(), *params, const_data_ptr_cast(body.data()), body.size());
		post.cancellation = &cancel;
		post.try_request = true;

		std::thread flipper([&] {
			std::this_thread::sleep_for(std::chrono::milliseconds(300));
			cancel.store(true);
		});
		auto start = std::chrono::steady_clock::now();
		auto resp = http_util.Request(post);
		flipper.join();

		REQUIRE(resp);
		REQUIRE(resp->cancelled);
		REQUIRE(ElapsedSeconds(start) < 10);
	}

	server.Stop();

	SECTION("a normal POST without a cancellation flag still succeeds") {
		RespondServer responder;
		responder.Start();
		const string ok_url = "http://127.0.0.1:" + to_string(responder.port) + "/ok";
		auto params = http_util.InitializeParameters(*db.instance, ok_url);
		PostRequestInfo post(ok_url, HTTPHeaders(), *params, const_data_ptr_cast(body.data()), body.size());
		// no cancellation flag set
		post.try_request = true;
		auto resp = http_util.Request(post);
		REQUIRE(resp);
		REQUIRE_FALSE(resp->cancelled);
		REQUIRE(resp->status == HTTPStatusCode::OK_200);
		REQUIRE(post.buffer_out == "ok");
		responder.Stop();
	}
}
#endif
