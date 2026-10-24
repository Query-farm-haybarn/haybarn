#include "catch.hpp"

// POSIX only: on Windows httplib.hpp pulls windows.h into this unity-built object library
#if (defined(__linux__) || defined(__APPLE__)) && !defined(__EMSCRIPTEN__)
#include "httplib.hpp"

#include <string>
#include <thread>

namespace {

// GitHub's release-asset redirect sends one content-security-policy line of 9,243 bytes
const size_t GITHUB_LIKE_HEADER_LINE = 9300;

struct LargeHeaderServer {
	explicit LargeHeaderServer(size_t header_value_length) : header_value(header_value_length, 'a') {
		server.Get("/redirect", [this](const duckdb_httplib::Request &, duckdb_httplib::Response &response) {
			response.set_header("Content-Security-Policy", header_value);
			response.set_redirect("/target");
		});
		server.Get("/target", [this](const duckdb_httplib::Request &, duckdb_httplib::Response &response) {
			response.set_header("X-Large", header_value);
			response.set_content("payload", "text/plain");
		});
		port = server.bind_to_any_port("127.0.0.1");
		REQUIRE(port > 0);
		listener = std::thread([this]() { server.listen_after_bind(); });
		server.wait_until_ready();
	}
	~LargeHeaderServer() {
		server.stop();
		if (listener.joinable()) {
			listener.join();
		}
	}

	std::string header_value;
	duckdb_httplib::Server server;
	std::thread listener;
	int port = -1;
};

} // namespace

TEST_CASE("Responses with header lines longer than 8 KiB are read", "[httplib]") {
	LargeHeaderServer server(GITHUB_LIKE_HEADER_LINE);
	duckdb_httplib::Client client("127.0.0.1", server.port);
	client.set_follow_location(true);

	auto head = client.Head("/redirect");
	REQUIRE(head);
	REQUIRE(head->status == 200);
	REQUIRE(head->get_header_value("X-Large").size() == GITHUB_LIKE_HEADER_LINE);

	auto get = client.Get("/redirect");
	REQUIRE(get);
	REQUIRE(get->status == 200);
	REQUIRE(get->body == "payload");
}

TEST_CASE("Header lines over CPPHTTPLIB_HEADER_MAX_LENGTH are still rejected", "[httplib]") {
	LargeHeaderServer server(CPPHTTPLIB_HEADER_MAX_LENGTH);
	duckdb_httplib::Client client("127.0.0.1", server.port);
	auto get = client.Get("/target");
	REQUIRE(!get);
}
#endif
