#include "duckdb/common/time_point.hpp"

namespace duckdb {

//! steady_clock is meant to never go backwards, but it can: a virtual machine's clock can step back across vCPUs
//! (duckdb#27790), and in the browser emscripten's pthread clock (performance.timeOrigin + performance.now()) can
//! disagree between threads by the timer resolution (Safari). Callers cast elapsed times to unsigned, so a negative
//! interval is reported as zero rather than letting one clock step fail the query with an internal error.
static steady_clock::duration NonNegative(steady_clock::duration duration) {
	return duration < steady_clock::duration::zero() ? steady_clock::duration::zero() : duration;
}

TimePoint::TimePoint() : value() {
}

TimePoint TimePoint::Tick() {
	return TimePoint(steady_clock::now());
}

int64_t TimePoint::GetTickMs() {
	return std::chrono::duration_cast<std::chrono::milliseconds>(steady_clock::now().time_since_epoch()).count();
}

double TimePoint::ElapsedSeconds(const TimePoint &start, const TimePoint &end) {
	return std::chrono::duration_cast<std::chrono::duration<double>>(NonNegative(end.value - start.value)).count();
}

int64_t TimePoint::ElapsedMillis(const TimePoint &start, const TimePoint &end) {
	return std::chrono::duration_cast<std::chrono::milliseconds>(NonNegative(end.value - start.value)).count();
}

int64_t TimePoint::ElapsedMicros(const TimePoint &start, const TimePoint &end) {
	return std::chrono::duration_cast<std::chrono::microseconds>(NonNegative(end.value - start.value)).count();
}

int64_t TimePoint::ElapsedNanos(const TimePoint &start, const TimePoint &end) {
	return std::chrono::duration_cast<std::chrono::nanoseconds>(NonNegative(end.value - start.value)).count();
}

double TimePoint::ElapsedSeconds() const {
	auto now = steady_clock::now();
	return std::chrono::duration_cast<std::chrono::duration<double>>(NonNegative(now - value)).count();
}

int64_t TimePoint::ElapsedMillis() const {
	auto now = steady_clock::now();
	return std::chrono::duration_cast<std::chrono::milliseconds>(NonNegative(now - value)).count();
}

int64_t TimePoint::ElapsedMicros() const {
	auto now = steady_clock::now();
	return std::chrono::duration_cast<std::chrono::microseconds>(NonNegative(now - value)).count();
}

int64_t TimePoint::ElapsedNanos() const {
	auto now = steady_clock::now();
	return std::chrono::duration_cast<std::chrono::nanoseconds>(NonNegative(now - value)).count();
}

TimePoint::TimePoint(time_point<steady_clock> value_p) : value(value_p) {
}

} // namespace duckdb
