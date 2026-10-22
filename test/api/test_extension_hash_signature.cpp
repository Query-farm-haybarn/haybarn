#include "catch.hpp"
#include "duckdb/main/extension_helper.hpp"
#include "mbedtls_wrapper.hpp"
#include "test_helpers.hpp"

using namespace duckdb;

// A throwaway RSA-2048 key, and its signature of the two-level hash of TestPayload(): openssl pkeyutl -sign
// -pkeyopt digest:sha256 over the SHA-256 of the concatenated SHA-256 digests of the payload's 1 MiB chunks.
static constexpr const char *HASH_TEST_PUBLIC_KEY =
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkYpwWS5krUeWjfaGJi9jP7I750LvzmdT6i6/UyyGDwZeajvqvBtXulY7KgZqqW8ebS4Z"
    "ySS3EOgNyQqJhq7cdyNmeKJoN+KbyrTQHrrYblYtVVQ911Cfa9t6ulyxvDi2cCn+pNt45Xvos3q3BgmJ5bBV6itRCXIQQ0pgmJ1VgA+R4Uxp0WxH"
    "4E+2hgrbWHsrLzQFCnkbDxjCG2kmvHk1ht5RST16XEh5A08RF+FX+Nio3kbn7UKB8WIdmsKH5ni3qYHbmNTL62qBH33b0+f+4kOnmd68995XrsBV"
    "SSQKnS/5fhg8vYsfr8K8m9Jz1SP7WiR9VVd0QNZb8VZlitY3KQIDAQAB";

static constexpr const char *HASH_TEST_SIGNATURE_HEX =
    "8ab7dbf9f962d611454405cee8bc29e12381bc949087a5f311020c3ccc31e066ac36d044b2fd59ff88649bba851a2773cbc235bec89b1c93"
    "23c9eb7fa31c80fae2d2d0dc860f5c3cfc071e4433234172b20c8f4a4b6e69f68a9a1928578ba7fbd5a7d3fc8893fc08a057925b8e9df9a6"
    "b77c0547120a5c9919c7369a360ada6143c9ecacd2221a4b0a05246a067e6a238339ee14bdbdfff3e352cc3c6dd68dd6addc24dc35c62506"
    "e47d99167b6bf2ef9cb84f5c59081d507f71284fa2ff1f5c66e1ce1488555f62c088136585e09af4579b70b893d95b734b877e466c23299b"
    "7de3b5d3a04d16791e5bbeed647258cb1d33268c1ca17134d269e18cfaf505a3";

static constexpr idx_t HASH_TEST_PAYLOAD_SIZE = 2 * 1024 * 1024 + 1234;

static string TestPayload() {
	string payload(HASH_TEST_PAYLOAD_SIZE, '\0');
	for (idx_t i = 0; i < payload.size(); i++) {
		payload[i] = static_cast<char>((i * 131 + 7) & 0xFF);
	}
	return payload;
}

static string FromHex(const string &hex) {
	string result;
	for (idx_t i = 0; i + 1 < hex.size(); i += 2) {
		result += static_cast<char>(std::stoi(hex.substr(i, 2), nullptr, 16));
	}
	return result;
}

static string Sha256(const char *data, idx_t length) {
	char hash[duckdb_mbedtls::MbedTlsWrapper::SHA256_HASH_LENGTH_BYTES];
	duckdb_mbedtls::MbedTlsWrapper::ComputeSha256Hash(data, length, hash);
	return string(hash, sizeof(hash));
}

// What an embedder computes on its side, e.g. with WebCrypto while it downloads the extension
static string TwoLevelHash(const string &payload) {
	const idx_t chunk_size = 1024 * 1024;
	string digests;
	for (idx_t offset = 0; offset < payload.size(); offset += chunk_size) {
		digests += Sha256(payload.data() + offset, MinValue<idx_t>(chunk_size, payload.size() - offset));
	}
	return Sha256(digests.data(), digests.size());
}

TEST_CASE("Test checking an extension signature against a precomputed hash", "[api]") {
	auto repository_directory = TestCreatePath("extension_hash_signature");

	DBConfig config;
	config.SetOptionByName("extension_repository_directory", repository_directory);
	config.SetOptionByName("allow_extension_repositories", "allowed");
	DuckDB db(nullptr, &config);
	Connection con(db);
	auto &instance = *db.instance;
	REQUIRE_NO_FAIL(con.Query(StringUtil::Format(
	    "CREATE EXTENSION REPOSITORY acme WITH PREFIX 'http://acme.com' USING PUBLIC KEY '%s'", HASH_TEST_PUBLIC_KEY)));

	const auto payload = TestPayload();
	const auto signature = FromHex(HASH_TEST_SIGNATURE_HEX);
	REQUIRE(signature.size() == ParsedExtensionMetaData::SIGNATURE_SIZE);
	const auto hash = TwoLevelHash(payload);
	const auto repository = ExtensionRepositoryType::USER_PROVIDED;

	// the precomputed hash verifies exactly like the engine hashing the buffer itself
	REQUIRE(ExtensionHelper::CheckExtensionBufferSignature(instance, payload.data(), payload.size(), signature,
	                                                       repository, "acme"));
	string fingerprint;
	REQUIRE(ExtensionHelper::CheckExtensionHashSignature(instance, hash, signature, repository, "acme", &fingerprint));
	REQUIRE(!fingerprint.empty());

	// the keys trusted are still those of the origin: no other repository's key verifies it
	REQUIRE(
	    !ExtensionHelper::CheckExtensionHashSignature(instance, hash, signature, ExtensionRepositoryType::CORE, ""));
	REQUIRE(!ExtensionHelper::CheckExtensionHashSignature(instance, hash, signature, repository, "unknown_repository"));

	// a hash of anything else, or of the wrong length, does not verify
	auto tampered = payload;
	tampered[1024 * 1024 + 1] ^= 1;
	REQUIRE(
	    !ExtensionHelper::CheckExtensionHashSignature(instance, TwoLevelHash(tampered), signature, repository, "acme"));
	REQUIRE(!ExtensionHelper::CheckExtensionHashSignature(instance, Sha256(payload.data(), payload.size()), signature,
	                                                      repository, "acme"));
	REQUIRE(!ExtensionHelper::CheckExtensionHashSignature(instance, hash.substr(0, 16), signature, repository, "acme"));
	REQUIRE(!ExtensionHelper::CheckExtensionHashSignature(instance, string(), signature, repository, "acme"));
}
