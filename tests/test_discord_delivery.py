import unittest
from unittest.mock import patch

import check_new_issues as bot


class FakeResponse:
    def __init__(self, status):
        self.status = status

    def read(self):
        return b""


class FakeConnection:
    status = 204
    requests = []

    def __init__(self, host, timeout):
        self.host = host
        self.timeout = timeout

    def request(self, method, path, body, headers):
        self.requests.append((method, path, body, headers))

    def getresponse(self):
        return FakeResponse(self.status)

    def close(self):
        pass


class DiscordDeliveryTests(unittest.TestCase):
    issue = {
        "number": 7,
        "title": "Test issue",
        "html_url": "https://example.invalid/issues/7",
        "labels": [],
    }

    def setUp(self):
        FakeConnection.requests = []
        FakeConnection.status = 204
        self.webhook = patch.object(
            bot, "DISCORD_WEBHOOK_URL", "https://example.invalid/webhook"
        )
        self.connection = patch.object(bot.http.client, "HTTPSConnection", FakeConnection)
        self.sleep = patch.object(bot.time, "sleep")
        self.webhook.start()
        self.connection.start()
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()
        self.connection.stop()
        self.webhook.stop()

    def test_204_is_success(self):
        self.assertTrue(bot.post_to_discord("owner/repo", self.issue))
        method, _, _, headers = FakeConnection.requests[0]
        self.assertEqual(method, "POST")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_403_is_failure(self):
        FakeConnection.status = 403
        self.assertFalse(bot.post_to_discord("owner/repo", self.issue))

    def test_failed_posts_are_not_saved(self):
        issues = [
            {"number": 2, "title": "Second", "html_url": "https://example.invalid/2", "labels": []},
            {"number": 1, "title": "First", "html_url": "https://example.invalid/1", "labels": []},
        ]
        saved_state = {}
        with (
            patch.object(bot, "REPOS", ["owner/repo"]),
            patch.object(bot, "load_state", return_value={}),
            patch.object(bot, "fetch_open_issues", return_value=issues),
            patch.object(bot, "post_to_discord", side_effect=lambda _, issue: issue["number"] == 2),
            patch.object(bot, "save_state", side_effect=saved_state.update),
        ):
            bot.main()

        self.assertEqual(saved_state, {"owner/repo": [2]})


if __name__ == "__main__":
    unittest.main()
