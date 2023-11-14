# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
import json
import time

from support import testutils
from test.support import fixtures
fixtures.global_setup()

import binascii
import unittest
from unittest.mock import patch

from resources.lib import itv_account
from test.support import object_checks
from test.local.test_account import ACCESS_TKN_FIELDS, REFRESH_TKN_FIELDS, PROFILE_TKN_FIELDS

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


class TestTokens(unittest.TestCase):
    @classmethod
    @patch("resources.lib.kodi_utils.ask_credentials", new=lambda x, y: (x, y))
    def setUpClass(cls) -> None:
        cls.itv_sess = sess = itv_account.itv_session()
        # Fetch the tokens
        sess.refresh() or sess.login(account_login.UNAME, account_login.PASSW)
        cls.now = int(time.time())

    def parse_token(self, token):
        str_parts = token.split('.')
        print(f'len(token) = {len(str_parts[2])}')
        token_parts = []
        for part in str_parts:
            try:
                data_str = binascii.a2b_base64(part + '==')
                data = json.loads(data_str)
                token_parts.append(data)
            except Exception as err:
                token_parts.append(None)
        self.assertEqual(3, len(token_parts))
        self.assertIsNone(token_parts[2])
        self.assertEqual(342, len(str_parts[2]), "Unexpected token length of {}".format(len(str_parts[2])))
        return token_parts

    def _check_token_type(self, type_data):
        object_checks.has_keys(type_data, 'typ', 'alg')
        self.assertEqual('JWT', type_data['typ'])
        self.assertEqual('RS256', type_data['alg'])

    def test_access_token(self):
        acc_token = self.itv_sess.account_data['itv_session']['access_token']
        token_data = self.parse_token(acc_token)
        self._check_token_type(token_data[0])
        user_data = token_data[1]
        object_checks.has_keys(user_data, *ACCESS_TKN_FIELDS)
        self.assertTrue(user_data['isActive'])
        self.assertEqual('https://auth.itv.com', user_data['iss'])  # issuer
        self.assertTrue(testutils.is_uuid(user_data['sub']))
        self.assertAlmostEqual(self.now, user_data['iat'], delta=5)
        self.assertEqual(user_data['exp'], user_data['iat'] + 90000)
        self.assertEqual('ITV', user_data['broadcaster'])
        self.assertEqual('content', user_data['scope'])

    def test_refresh_token(self):
        refresh_token = self.itv_sess.account_data['itv_session']['refresh_token']
        token_data = self.parse_token(refresh_token)
        self._check_token_type(token_data[0])
        user_data = token_data[1]
        object_checks.has_keys(user_data, *REFRESH_TKN_FIELDS)
        self.assertEqual('https://auth.itv.com', user_data['iss'])  # issuer
        self.assertTrue(testutils.is_uuid(user_data['sub']))
        self.assertAlmostEqual(self.now, user_data['iat'], delta=5)
        # refresh token expires after 100 years (3155673600 sec.), allow a difference of a leap day
        self.assertAlmostEqual(user_data['exp'], self.now + 36524 * 86400, delta=86400)
        self.assertEqual('content', user_data['scope'])
        self.assertAlmostEqual(self.now, user_data['auth_time'], delta=5)  # timestamp of moment of authentication

    def test_profile_token(self):
        refresh_token = self.itv_sess.account_data['itv_session']['refresh_token']
        profile_token = self.itv_sess.account_data['itv_session']['profile_token']
        self.assertNotEqual(refresh_token, profile_token)       # refresh and profiel token are different
        token_data = self.parse_token(profile_token)
        self._check_token_type(token_data[0])
        profile_data = token_data[1]
        object_checks.has_keys(profile_data, *PROFILE_TKN_FIELDS)
        self.assertEqual('https://auth.itv.com', profile_data['iss'])  # issuer
        self.assertLessEqual(profile_data['iat'], self.now)
        self.assertLessEqual(profile_data['exp'], profile_data['iat'] + 3600)   # expires 1 hour after iat
        self.assertTrue(testutils.is_uuid(profile_data['sub']))
