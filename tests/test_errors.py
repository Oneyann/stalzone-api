import unittest
from types import SimpleNamespace

from stalzone_api.errors import NotFound, ServerError, error_from_response


def fake_response(status, payload, reason="Reason"):
    return SimpleNamespace(
        status_code=status,
        reason_phrase=reason,
        json=lambda: payload,
        request=SimpleNamespace(url="https://example.com/api"),
    )


class ErrorFromResponseTest(unittest.TestCase):
    def test_maps_404_to_not_found(self):
        error = error_from_response(fake_response(404, {"title": "Missing"}))
        self.assertIsInstance(error, NotFound)
        self.assertEqual(error.title, "Missing")
        self.assertEqual(str(error), "404 Missing (https://example.com/api)")

    def test_maps_5xx_to_server_error(self):
        error = error_from_response(fake_response(503, None, reason="Unavailable"))
        self.assertIsInstance(error, ServerError)
        self.assertEqual(error.title, "Unavailable")


if __name__ == "__main__":
    unittest.main()
