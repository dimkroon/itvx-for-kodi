# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import patch

from resources.lib import itv_account

import account_login
setUpModule = fixtures.setup_web_test


class TestItvSession(unittest.TestCase):
    def test_instantiate_account_class(self):
        itv_sess = itv_account.ItvSession()
        assert itv_sess is not None


class TestLogin(unittest.TestCase):
    def test_login(self):
        itv_sess = itv_account.itv_session()
        resp = itv_sess.login(account_login.UNAME, account_login.PASSW)
        self.assertTrue(resp)

    def test_refresh(self):
        tv_sess = itv_account.itv_session()
        resp = tv_sess.refresh()
        self.assertTrue(resp)
