
import unittest

from test.support import fixtures
fixtures.global_setup()

from resources.lib import itv_account

setUpModule = fixtures.setup_web_test


class TestItvSession(unittest.TestCase):
    def test_instantiate_account_class(self):
        itv_sess = itv_account.ItvSession()
        assert itv_sess is not None


class TestLogin(unittest.TestCase):
    def test_login(self):
        itv_sess = itv_account.itv_session()
        resp = itv_sess.login()
        self.assertTrue(resp)

    def test_refresh(self):
        tv_sess = itv_account.itv_session()
        resp = tv_sess.refresh()
        self.assertTrue(resp)
