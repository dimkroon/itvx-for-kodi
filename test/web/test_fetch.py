# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
import os

from resources.lib import utils
from resources.lib import fetch

setUpModule = fixtures.setup_web_test


class TestFetch(unittest.TestCase):
    def test_set_cookie_consent(self):
        cookie_file = os.path.join(utils.addon_info['profile'], 'cookies')
        cj = fetch.set_default_cookies(fetch.PersistentCookieJar(cookie_file))
        self.assertGreater(len(cj), 5)
        self.assertIsInstance(cj, fetch.PersistentCookieJar)
