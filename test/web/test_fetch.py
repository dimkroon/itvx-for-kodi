# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import patch
import os

from resources.lib import utils
from resources.lib import fetch
from resources.lib import itv_account
import account_login


setUpModule = fixtures.setup_web_test


class TestFetch(unittest.TestCase):
    def test_set_cookie_consent(self):
        cookie_file = os.path.join(utils.addon_info.profile, 'cookies')
        cj = fetch.set_default_cookies(fetch.PersistentCookieJar(cookie_file))
        self.assertGreater(len(cj), 6)
        self.assertIsInstance(cj, fetch.PersistentCookieJar)

        # Without passing a cookiejar
        cj = fetch.set_default_cookies()
        self.assertGreater(len(cj), 5)
