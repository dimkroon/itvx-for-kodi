
from test.support import fixtures
fixtures.global_setup()

import unittest

from resources.lib import fetch

setUpModule = fixtures.setup_web_test


class TestFetch(unittest.TestCase):
    def test_set_cookie_consent(self):
        cj = fetch.set_default_cookies(fetch.PersistentCookieJar(fetch.cookie_file))
        self.assertGreater(len(cj), 5)
        self.assertIsInstance(cj, fetch.PersistentCookieJar)
