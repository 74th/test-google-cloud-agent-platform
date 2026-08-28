import json
import unittest

from gateway_probe import sanitize


class ProbeSanitizationTest(unittest.TestCase):
    def test_redacts_secret_keys_and_values(self):
        raw = {
            "Authorization": "Bearer do-not-record",
            "access_token": "do-not-record",
            "certificate": "-----BEGIN CERTIFICATE-----secret-----END CERTIFICATE-----",
            "nested": {"private_key": "do-not-record", "message": "Bearer still-do-not-record"},
            "safe": "registry_discovery",
        }
        sanitized = sanitize(raw)
        encoded = json.dumps(sanitized)
        self.assertNotIn("do-not-record", encoded)
        self.assertNotIn("BEGIN CERTIFICATE", encoded)
        self.assertEqual(sanitized["safe"], "registry_discovery")

    def test_secret_key_is_not_emitted(self):
        self.assertNotIn("Authorization", json.dumps(sanitize({"authorization": "x"})))


if __name__ == "__main__":
    unittest.main()
