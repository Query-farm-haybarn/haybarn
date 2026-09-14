#include "duckdb/main/http/http_retry_budget.hpp"

#include "duckdb/common/limits.hpp"
#include "duckdb/common/random_engine.hpp"
#include "duckdb/common/string_util.hpp"
#include "duckdb/main/http/http_util.hpp"

#ifndef DUCKDB_NO_THREADS
#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <thread>
#endif

namespace duckdb {

#ifndef DUCKDB_NO_THREADS
namespace {

// Upper bound on a honored Retry-After — a hostile/misconfigured server must not
// be able to stall a request for an unbounded time (60s).
constexpr uint64_t MAX_HONORED_RETRY_AFTER_MS = 60000;

// Days since 1970-01-01 for a proleptic-Gregorian y/m/d (Howard Hinnant's
// days-from-civil). Portable — avoids the non-standard timegm().
int64_t DaysFromCivil(int64_t y, uint32_t m, uint32_t d) {
	y -= m <= 2;
	const int64_t era = (y >= 0 ? y : y - 399) / 400;
	const uint32_t yoe = static_cast<uint32_t>(y - era * 400);
	const uint32_t doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
	const uint32_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
	return era * 146097 + static_cast<int64_t>(doe) - 719468;
}

uint32_t MonthFromAbbrev(const char *mon) {
	static const char *kMonths[12] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
	                                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
	for (uint32_t i = 0; i < 12; i++) {
		if (std::strncmp(mon, kMonths[i], 3) == 0) {
			return i + 1;
		}
	}
	return 0;
}

// Parse an RFC 7231 / 9110 IMF-fixdate ("Wed, 21 Oct 2015 07:28:00 GMT") to epoch
// seconds (UTC). Returns false if it does not match. DuckDB's own timestamp
// parser does not accept the weekday/month-name HTTP-date form, hence this.
bool ParseHttpDateEpoch(const string &s, int64_t &out_epoch) {
	char wday[8] = {0};
	char mon[8] = {0};
	int day = 0, year = 0, hh = 0, mm = 0, ss = 0;
	int n = std::sscanf(s.c_str(), "%3s %d %3s %d %d:%d:%d", wday, &day, mon, &year, &hh, &mm, &ss);
	if (n != 7) {
		n = std::sscanf(s.c_str(), "%*[^,], %d %3s %d %d:%d:%d", &day, mon, &year, &hh, &mm, &ss);
		if (n != 6) {
			return false;
		}
	}
	uint32_t month = MonthFromAbbrev(mon);
	if (month == 0 || day < 1 || day > 31 || hh < 0 || hh > 23 || mm < 0 || mm > 59 || ss < 0 || ss > 60) {
		return false;
	}
	out_epoch = DaysFromCivil(year, month, static_cast<uint32_t>(day)) * 86400 + static_cast<int64_t>(hh) * 3600 +
	            static_cast<int64_t>(mm) * 60 + ss;
	return true;
}

// Parse a Retry-After response header (RFC 9110 §10.2.3): delta-seconds or an
// HTTP-date. On success sets out_ms (>= 0) and returns true.
bool TryParseRetryAfterMs(string v, uint64_t &out_ms) {
	StringUtil::Trim(v); // in-place (void return)
	if (v.empty()) {
		return false;
	}
	if (std::all_of(v.begin(), v.end(), [](unsigned char c) { return std::isdigit(c) != 0; })) {
		try {
			auto seconds = std::stoull(v);
			out_ms = seconds >= MAX_HONORED_RETRY_AFTER_MS / 1000 ? MAX_HONORED_RETRY_AFTER_MS : seconds * 1000;
			return true;
		} catch (...) {
			return false;
		}
	}
	int64_t when_epoch;
	if (!ParseHttpDateEpoch(v, when_epoch)) {
		return false;
	}
	auto now_epoch =
	    std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();
	int64_t delta = when_epoch - static_cast<int64_t>(now_epoch);
	out_ms = delta > 0 ? static_cast<uint64_t>(delta) * 1000ull : 0;
	return true;
}

} // namespace
#endif

HTTPRetryDecision HTTPRetryDecision::Finish() {
	return HTTPRetryDecision(Type::FINISH);
}

HTTPRetryDecision HTTPRetryDecision::Retry() {
	return HTTPRetryDecision(Type::RETRY);
}

HTTPRetryDecision HTTPRetryDecision::Throttled(const string &retry_after) {
	return HTTPRetryDecision(Type::THROTTLED, retry_after);
}

HTTPRetryBudget::HTTPRetryBudget(const HTTPParams &params)
    : retries(params.retries), retry_wait_ms(params.retry_wait_ms), retry_backoff(params.retry_backoff) {
}

void HTTPRetryBudget::Run(const std::function<HTTPRetryDecision()> &attempt) {
	Run(attempt, {});
}

void HTTPRetryBudget::Run(const std::function<HTTPRetryDecision()> &attempt,
                          const std::function<void()> &before_retry) {
	if (!attempt) {
		throw InternalException("HTTP retry loop requires an attempt callback");
	}
	for (;;) {
		auto decision = attempt();
		if (decision.type == HTTPRetryDecision::Type::FINISH || !ConsumeAndWait(decision)) {
			return;
		}
		if (before_retry) {
			before_retry();
		}
	}
}

bool HTTPRetryBudget::ConsumeAndWait(const HTTPRetryDecision &decision) {
	D_ASSERT(decision.type != HTTPRetryDecision::Type::FINISH);
	const bool throttled = decision.type == HTTPRetryDecision::Type::THROTTLED;
#ifndef DUCKDB_NO_THREADS
	static constexpr uint64_t THROTTLE_EXTRA_RETRIES = 5;
#else
	// Without threads we cannot sleep between retries, so do not add zero-delay retries.
	static constexpr uint64_t THROTTLE_EXTRA_RETRIES = 0;
#endif
	const auto extra_retries = throttled ? THROTTLE_EXTRA_RETRIES : 0;
	if (retries_used >= retries && retries_used - retries >= extra_retries) {
		return false;
	}
	retries_used++;
#ifndef DUCKDB_NO_THREADS
	if (retries_used > 1 || throttled) {
		static constexpr uint64_t THROTTLE_MAX_BACKOFF_MS = 10000;
		const auto backoff_exp = static_cast<double>(throttled ? retries_used - 1 : retries_used - 2);
		const auto backoff_ms = (double)retry_wait_ms * pow(retry_backoff, backoff_exp);
		// Cap in the double domain to avoid overflow in the cast.
		uint64_t sleep_amount = (uint64_t)MinValue<double>(backoff_ms, (double)NumericLimits<int64_t>::Maximum());
		if (throttled) {
			sleep_amount = MinValue<uint64_t>(sleep_amount, THROTTLE_MAX_BACKOFF_MS);
			// Jitter the backoff before applying the server's requested delay as a floor.
			RandomEngine random;
			sleep_amount -= random.NextRandomInteger64() % (sleep_amount / 2 + 1);
			uint64_t retry_after_ms;
			if (TryParseRetryAfterMs(decision.retry_after, retry_after_ms)) {
				sleep_amount =
				    MaxValue<uint64_t>(sleep_amount, MinValue<uint64_t>(retry_after_ms, MAX_HONORED_RETRY_AFTER_MS));
			}
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(sleep_amount));
	}
#else
	(void)retry_wait_ms;
	(void)retry_backoff;
#endif
	return true;
}

} // namespace duckdb
