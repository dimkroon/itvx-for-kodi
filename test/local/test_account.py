# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import json
import time
import unittest
import uuid
import binascii
import requests

from copy import deepcopy
from unittest.mock import patch, mock_open, MagicMock

from resources.lib import errors
from resources.lib import itv_account
from resources.lib import fetch
from resources.lib import utils

from test.support.object_checks import has_keys
from test.support.testutils import is_uuid
from test.support.testutils import HttpResponse

# noinspection PyPep8Naming
setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


ACCESS_TKN_FIELDS = ('iss', 'sub', 'exp', 'iat', 'broadcastErrorMsg', 'broadcastResponseCode', 'broadcaster',
                     'isActive', 'nonce', 'name', 'scope', 'entitlements', 'paymentSource', 'showPrivacyNotice',
                     'under18', 'accountProfileIdInUse')
REFRESH_TKN_FIELDS = ('iss', 'sub', 'exp', 'iat', 'nonce', 'scope', 'auth_time', 'accountProfileIdInUse')
PROFILE_TKN_FIELDS = ('iss', 'sub', 'exp', 'iat', 'nonce', 'name', 'under18', 'scope')


def build_test_tokens(user_nick, account_id=None, exp_time=None):
    now = int(time.time())
    tkn_type = {'typ': 'JWT',
                'alg': 'RS256'}
    gen_data = {"iss": "https://auth.itv.com",
                "sub": account_id or str(uuid.uuid4()),
                "exp": exp_time or now + 90000,
                "iat": now,
                'auth_time': now,
                "broadcastErrorMsg": "",
                "broadcastResponseCode": "200",
                "broadcaster": "ITV",
                "isActive": True,
                "nonce": utils.random_string(20),
                "name": user_nick,
                "scope": "content",
                "entitlements": [],
                "paymentSource": "",
                "showPrivacyNotice": False,
                "under18": False,
                "accountProfileIdInUse": None}

    def create_token(tkn_data, key):
        return '.'.join((
            binascii.b2a_base64(json.dumps(tkn_type).encode('ASCII')).decode('ascii'),
            binascii.b2a_base64(json.dumps(tkn_data).encode('ASCII')).decode('ascii'),
            key))

    access_data = {k: v for k, v in gen_data.items() if k in ACCESS_TKN_FIELDS}
    refresh_data = {k: v for k, v in gen_data.items()  if k in REFRESH_TKN_FIELDS}
    profile_data = {k: v for k, v in gen_data.items()  if k in PROFILE_TKN_FIELDS}

    return (create_token(access_data, utils.random_string(342)),
            create_token(refresh_data, utils.random_string(342)),
            create_token(profile_data, utils.random_string(342))
            )


test_user_nick_name = 'My username'
test_access_token, test_refresh_token, test_profile_token = build_test_tokens(test_user_nick_name)


session_dta = {'itv_session': {
    'entitlement': {
        'purchased': [],
        'failed_availability_checks': [],
        'source': ''
    },
    'email_verified': True,
    'missingUserData': ['NoPlanSelected'],
    'access_token': test_access_token,
    'token_type': 'bearer',
    'refresh_token': test_refresh_token,
    'profile_token': test_profile_token}
}


account_data_v0 = {'uname': 'my_uname', 'passw': 'my_passw',
                   "refreshed": time.time(),
                   'itv_session': {'access_token': 'my-token',
                                   'refresh_token': 'my-refresh-token'},
                   'cookies': {'Itv.Cid': 'xxxxxxxxxxxx'}
                   }

account_data_v2 = {
                   'refreshed': account_data_v0['refreshed'],
                   'itv_session': {'access_token': 'my-token',
                                   'refresh_token': 'my-refresh-token'},
                   'cookies': {'Itv.Session': '{"sticky": true, "tokens": {"content": {"access_token": "my-token", '
                                              '"refresh_token": "my-refresh-token"}}}'},
                   'vers': 2
                   }


class TestSession(unittest.TestCase):
    # noinspection PyMethodMayBeStatic
    def test_instantiate_session_class(self):
        sess = itv_account.ItvSession()
        self.assertIsInstance(sess, itv_account.ItvSession)

    @patch('resources.lib.itv_account.open', side_effect=OSError)
    def test_instantiate_session_class_with_missing_data_file(self, _):
        sess = itv_account.ItvSession()
        self.assertIsInstance(sess, itv_account.ItvSession)

    def test_session(self):
        itv_account._session_obj = None
        sess_1 = itv_account.itv_session()
        self.assertIsInstance(sess_1, itv_account.ItvSession)
        sess_2 = itv_account.itv_session()
        self.assertIs(sess_1, sess_2)


@patch("resources.lib.itv_account.ItvSession.save_account_data")
class TestLogin(unittest.TestCase):
    @patch('requests.post', return_value=HttpResponse(content=b'{"access_token": "new_token", "refresh_token": "new_refresh"}'))
    def test_login_requires_both_uname_and_password(self, _, __):
        ct_sess = itv_account.ItvSession()
        self.assertRaises(TypeError, ct_sess.login)
        self.assertRaises(TypeError, ct_sess.login, uname="my name")
        self.assertRaises(TypeError, ct_sess.login, passw="my password")
        self.assertTrue(ct_sess.login(uname="my name", passw="my password"))

    @patch('requests.post', return_value=HttpResponse(content=b'{"access_token": "new_token", "refresh_token": "new_refresh"}'))
    def test_login_with_credentials(self, p_post, _):
        ct_sess = itv_account.ItvSession()
        self.assertTrue(ct_sess.login('my_name', 'my_passw'))
        post_kwargs = p_post.call_args.kwargs['json']
        has_keys(post_kwargs, 'username', 'password', 'nonce', 'grant_type', obj_name='post_json kwargs')
        self.assertEqual('my_name', post_kwargs['username'])
        self.assertEqual('my_passw', post_kwargs['password'])
        self.assertEqual(itv_account.SESS_DATA_VERS, ct_sess.account_data['vers'])
        headers = p_post.call_args.kwargs['headers']
        has_keys(headers, 'user-agent', 'accept', 'accept-language', 'accept-encoding', 'content-type',
                 'akamai-bm-telemetry', 'origin', 'referer', 'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site',
                 'priority', 'te')

    def test_login_encounters_http_errors(self, p_save):
        # with patch('requests.post', side_effect=errors.AuthenticationError):
        #     ct_sess = itv_account.ItvSession()
        #     p_save.reset_mock()
        #     self.assertRaises(errors.AuthenticationError, ct_sess.login, 'my name', 'my password')
        #     p_save.assert_not_called()

        with patch('requests.post', return_value=HttpResponse(status_code=400)):
            ct_sess = itv_account.ItvSession()
            p_save.reset_mock()
            self.assertRaises(errors.AuthenticationError, ct_sess.login, 'my name', 'my password')
            p_save.assert_not_called()

        with patch('requests.post', return_value=HttpResponse(status_code=401)):
            ct_sess = itv_account.ItvSession()
            p_save.reset_mock()
            self.assertRaises(requests.HTTPError, ct_sess.login, 'my name', 'my password')
            p_save.assert_not_called()

        with patch('requests.post', return_value=HttpResponse(status_code=403)):
            ct_sess = itv_account.ItvSession()
            p_save.reset_mock()
            self.assertRaises(errors.AuthenticationError, ct_sess.login, 'my name', 'my password')
            p_save.assert_not_called()

        with patch('requests.post', return_value=HttpResponse(status_code=404)):
            ct_sess = itv_account.ItvSession()
            p_save.reset_mock()
            self.assertRaises(requests.HTTPError, ct_sess.login, 'my name', 'my password')
            p_save.assert_not_called()
        #
        # with patch('requests.post', side_effect=errors.GeoRestrictedError):
        #     ct_sess = itv_account.ItvSession()
        #     p_save.reset_mock()
        #     self.assertRaises(errors.GeoRestrictedError, ct_sess.login, 'my name', 'my password')
        #     p_save.assert_not_called()


@patch("resources.lib.itv_account.ItvSession.save_account_data")
class Refresh(unittest.TestCase):
    def setUp(self) -> None:
        self.ct_sess = itv_account.ItvSession()
        self.ct_sess.account_data = {'itv_session': {'access_token': '1st_token', 'refresh_token': '1st_refresh'},
                                     'cookies': {'Itv.Cid': 'aaaa-bbbb-11'}
                                     }

    @patch('resources.lib.fetch.get_json', return_value={'access_token': '2nd_token', 'refresh_token': '2nd_refresh'})
    def test_refresh(self, _, p_save):
        self.assertTrue(self.ct_sess.refresh())
        self.assertTrue(p_save.called_once())
        self.assertEqual(self.ct_sess.account_data['itv_session'],
                         {'access_token': '2nd_token', 'refresh_token': '2nd_refresh'})

    def test_refresh_with_request_errors(self, p_save):
        with patch('resources.lib.fetch.get_json', side_effect=errors.AuthenticationError()):
            self.assertFalse(self.ct_sess.refresh())
        with patch('resources.lib.fetch.get_json', side_effect=errors.HttpError(400, 'Bad request')):
            self.assertRaises(errors.HttpError, self.ct_sess.refresh)
        with patch('resources.lib.fetch.get_json', side_effect=errors.GeoRestrictedError()):
            self.assertRaises(errors.GeoRestrictedError, self.ct_sess.refresh)
        with patch('resources.lib.fetch.get_json', side_effect=errors.FetchError()):
            self.assertRaises(errors.FetchError, self.ct_sess.refresh)
        p_save.assert_not_called()

    @patch('resources.lib.fetch.get_json', return_value={'token': '2nd_token', 'refreshToken': '2nd_refresh'})
    def test_refresh_without_account_data(self, p_post, p_save):
        ct_sess = itv_account.ItvSession()
        p_save.reset_mock()
        ct_sess.account_data = None
        self.assertFalse(ct_sess.refresh())
        p_post.assert_not_called()
        p_save.assert_not_called()


@patch('resources.lib.itv_account.ItvSession.login')
@patch('resources.lib.itv_account.ItvSession.refresh', return_value=True)
class PropAccessToken(unittest.TestCase):
    def test_prop_access_token(self, p_refresh, p_login):
        ct_sess = itv_account.ItvSession()
        ct_sess.account_data = account_data_v2
        self.assertEqual(account_data_v2['itv_session']['access_token'], ct_sess.access_token)
        p_refresh.assert_not_called()
        p_login.assert_not_called()

    def test_prop_access_token_raises_auth_error_on_no_account_data(self, p_refresh, p_login):
        ct_sess = itv_account.ItvSession()
        ct_sess.account_data = None
        self.assertEqual('', ct_sess.access_token)
        p_login.assert_not_called()
        p_refresh.assert_not_called()

    def test_prop_access_token_with_expired_tokens(self, p_refresh, p_login):
        ct_sess = itv_account.ItvSession()
        ct_sess.account_data = deepcopy(account_data_v2)
        ct_sess.account_data['refreshed'] = time.time() - 48 * 3600     # force a timeout
        self.assertEqual(account_data_v2['itv_session']['access_token'], ct_sess.access_token)
        p_login.assert_not_called()
        p_refresh.assert_not_called()


@patch('resources.lib.itv_account.ItvSession.login')
@patch('resources.lib.itv_account.ItvSession.refresh')
class PropCookie(unittest.TestCase):
    def test_prop_cookie(self, p_refresh, p_login):
        ct_sess = itv_account.ItvSession()
        ct_sess.account_data = account_data_v2
        self.assertEqual(account_data_v2['cookies'], ct_sess.cookie)
        p_refresh.assert_not_called()
        p_login.assert_not_called()

    def test_prop_cookie_auth_error_on_no_account_data(self, p_refresh, p_login):
        ct_sess = itv_account.ItvSession()
        ct_sess.account_data = None
        self.assertEqual({}, ct_sess.cookie)
        p_login.assert_not_called()
        p_refresh.assert_not_called()

    def test_prop_cookie_with_cache_timed_out_invokes_refresh(self, p_refresh, p_login):
        ct_sess = itv_account.ItvSession()
        ct_sess.account_data = deepcopy(account_data_v2)
        ct_sess.account_data['refreshed'] = time.time() - 48 * 3600     # force a timeout
        self.assertEqual(account_data_v2['cookies'], ct_sess.cookie)
        p_login.assert_not_called()
        p_refresh.assert_not_called()


@patch('resources.lib.itv_account.ItvSession.login')
@patch('resources.lib.itv_account.ItvSession.refresh')
class PropUserId(unittest.TestCase):
    def test_prop_user_id_logged_in(self, p_refresh, p_login):
        acc_data = deepcopy(account_data_v2)
        acc_data['itv_session'] = session_dta['itv_session']
        with patch('resources.lib.itv_account.open', mock_open(read_data=json.dumps(acc_data))):
            sess = itv_account.ItvSession()
        userid = sess.user_id
        p_login.assert_not_called()
        p_refresh.assert_not_called()
        self.assertTrue(is_uuid(userid))

    def test_prop_user_id_not_logged_in(self, p_refresh, p_login):
        with patch('resources.lib.itv_account.open', side_effect=IOError):
            ct_sess = itv_account.ItvSession()
        self.assertEqual('', ct_sess.user_id)
        p_login.assert_not_called()
        p_refresh.assert_not_called()

    def test_user_id_after_logout(self, _, __):
        acc_data = deepcopy(account_data_v2)
        acc_data['itv_session'] = session_dta['itv_session']
        with patch('resources.lib.itv_account.open', mock_open(read_data=json.dumps(acc_data))):
            sess = itv_account.ItvSession()
        sess.log_out()
        self.assertEqual('', sess.user_id)


@patch('resources.lib.itv_account.ItvSession.login')
@patch('resources.lib.itv_account.ItvSession.refresh')
class PropUserNickName(unittest.TestCase):
    def test_prop_user_nickname(self, p_refresh, p_login):
        acc_data = deepcopy(account_data_v2)
        acc_data['itv_session'] = session_dta['itv_session']
        with patch('resources.lib.itv_account.open', mock_open(read_data=json.dumps(acc_data))):
            sess = itv_account.ItvSession()
        username = sess.user_nickname
        p_login.assert_not_called()
        p_refresh.assert_not_called()
        self.assertIsInstance(username, str)

    def test_prop_user_nickname_not_logged_in(self, p_refresh, p_login):
        with patch('resources.lib.itv_account.open', side_effect=IOError):
            sess = itv_account.ItvSession()
        self.assertEqual('', sess.user_nickname)
        p_login.assert_not_called()
        p_refresh.assert_not_called()

    def test_user_id_after_logout(self, _, __):
        acc_data = deepcopy(account_data_v2)
        acc_data['itv_session'] = session_dta['itv_session']
        with patch('resources.lib.itv_account.open', mock_open(read_data=json.dumps(acc_data))):
            sess = itv_account.ItvSession()
        sess.log_out()
        self.assertEqual('', sess.user_nickname)


class Misc(unittest.TestCase):
    def test_read_account_data(self):
        with patch('resources.lib.itv_account.open', mock_open(read_data=json.dumps(account_data_v2))):
            # test data is being read at class instantiation
            ct_sess = itv_account.ItvSession()
            has_keys(ct_sess.account_data, 'itv_session', 'cookies', 'refreshed', 'vers')
            self.assertEqual(account_data_v2, ct_sess.account_data)
            ct_sess.account_data = None
            # test manual read
            ct_sess.read_account_data()
            self.assertEqual(account_data_v2, ct_sess.account_data)
        # Account data file not presents
        with patch('resources.lib.itv_account.open', side_effect=OSError):
            ct_sess.read_account_data()
            self.assertEqual({}, ct_sess.account_data)
        # Account data file is an empty dict, e.g. after logout
        with patch('resources.lib.itv_account.open', mock_open(read_data=json.dumps({})), create=True) as patched_open:
            ct_sess.read_account_data()
            self.assertTrue('vers' in ct_sess.account_data.keys())
            self.assertTrue('cookies' in ct_sess.account_data.keys())
            self.assertFalse('itv_session' in ct_sess.account_data.keys())
            # Check if converted account data has been saved correctly
            data_str = patched_open.return_value.write.call_args[0][0]
            data_written = json.loads(data_str)
            self.assertEqual(itv_account.SESS_DATA_VERS, data_written['vers'])

    def test_read_account_converts_to_new_format(self):
        with patch('resources.lib.itv_account.open', mock_open(read_data=json.dumps(account_data_v0))):
            ct_sess = itv_account.ItvSession()
            has_keys(ct_sess.account_data, 'itv_session', 'cookies', 'refreshed', 'vers')
            self.assertEqual(account_data_v2, ct_sess.account_data)

    def test_save_account_data(self):
        ct_sess = itv_account.ItvSession()
        with patch("resources.lib.itv_account.open") as p_open:
            ct_sess.save_account_data()
            p_open.assert_called_once()
            self.assertGreater(len(p_open.mock_calls), 2)   # at least calls to __enter__, write , __exit__

    @patch("resources.lib.itv_account.ItvSession.save_account_data")
    def test_logout(self, p_save):
        ct_sess = itv_account.ItvSession()
        p_save.reset_mock()
        ct_sess.account_data = {"some data"}
        ct_sess._user_id = 'myuserid'
        ct_sess._user_nickname = 'my-nick'
        ct_sess.log_out()
        self.assertEqual(ct_sess.account_data, {})
        p_save.assert_called_once()
        self.assertEqual('', ct_sess.user_id)
        self.assertEqual('', ct_sess.user_nickname)

    def test_parse_token(self):
        access_tkn, _, __ = build_test_tokens('My username')
        a_user_id, a_user_nick, a_exp_time = itv_account.parse_token(access_tkn)
        self.assertTrue(is_uuid(a_user_id))
        self.assertIsInstance(a_exp_time, int)
        self.assertEqual('My username', a_user_nick)

        invalid_token = access_tkn[:60] + access_tkn[90:]
        a_user_id, a_user_nick, a_exp_time = itv_account.parse_token(invalid_token)
        self.assertIsNone(a_user_id)
        self.assertIsNone(a_user_nick)
        # on parse errors expire time is set to now(), to force a refresh on the next call
        self.assertIsInstance(a_exp_time, int)
        self.assertAlmostEqual(a_exp_time, time.time() + time.timezone, delta=1)


class AccountMock:
    access_token = '123abc'

    def __init__(self):
        self.refresh = MagicMock()
        self.login = MagicMock()
        self.cookie = MagicMock()
        self.account_data = {'refreshed': time.time()}
    def alt_refresh(self):
        self.account_data['refreshed'] = time.time()


URL = 'https://mydoc'


class GetAuthenticated(unittest.TestCase):
    @patch("resources.lib.itv_account.itv_session", return_value=AccountMock())
    @patch("resources.lib.fetch.get_json", return_value={'a': 1})
    def test_authenticated_fetch(self, mocked_get, _):
        resp = itv_account.fetch_authenticated(fetch.get_json, URL)
        self.assertEqual({'a': 1}, resp)
        mocked_get.assert_called_once_with(url=URL, cookies={}, headers={'authorization': 'Bearer 123abc'})

    @patch('resources.lib.fetch.get_json', return_value={'a': 1})
    @patch('xbmc.executebuiltin')
    @patch('resources.lib.kodi_utils.show_msg_not_logged_in', return_value=True)
    def test_authenticated_fetch_not_logged_in(self, mocked_dialog, mocked_exec_buildin, mocked_get):
        account = AccountMock()
        account.account_data = ''
        account.refresh = MagicMock(return_value=False)
        with patch("resources.lib.itv_account.itv_session", return_value=account):
            with self.assertRaises(SystemExit) as cm:
                itv_account.fetch_authenticated(fetch.get_json, URL)
        self.assertEqual(1, cm.exception.code)      # MUST have a non-sero exit status
        mocked_dialog.assert_called_once()
        mocked_exec_buildin.assert_called_once()
        mocked_get.assert_not_called()

    @patch('resources.lib.fetch.get_json', return_value={'a': 1})
    @patch('xbmc.executebuiltin')
    @patch('resources.lib.kodi_utils.show_msg_not_logged_in', return_value=True)
    def test_authenticated_fetch_not_logged_in_without_sign_in_dialog(self, mocked_dialog, mocked_exec_buildin, mocked_get):
        account = AccountMock()
        account.account_data = ''
        account.refresh = MagicMock(return_value=False)
        with patch("resources.lib.itv_account.itv_session", return_value=account):
            with self.assertRaises(errors.AuthenticationError) as cm:
                itv_account.fetch_authenticated(fetch.get_json, URL, login=False)
        mocked_dialog.assert_not_called()
        mocked_exec_buildin.assert_not_called()
        mocked_get.assert_not_called()

    @patch('resources.lib.fetch.get_json', return_value={'a': 1})
    @patch('xbmc.executebuiltin')
    @patch('resources.lib.kodi_utils.show_msg_not_logged_in', return_value=True)
    def test_authenticated_fetch_missing_cookies(self, mocked_dialog, mocked_exec_buildin, mocked_get):
        """Test cookies absent. Basically the same as not logged in"""
        account = AccountMock()
        account.cookie = {}
        account.refresh = MagicMock(return_value=False)
        with patch("resources.lib.itv_account.itv_session", return_value=account):
            with self.assertRaises(SystemExit) as cm:
                itv_account.fetch_authenticated(fetch.get_json, URL)
        self.assertEqual(1, cm.exception.code)      # MUST have a non-sero exit status

    @patch("resources.lib.fetch.get_json", return_value={'a': 1})
    def test_authenticated_fetch_get_with_expired_tokens(self, mocked_get):
        account = AccountMock()
        account.account_data['refreshed'] = time.time() - 48 * 3600
        account.refresh = account.alt_refresh       # ensure a call to refresh() resets refresh time.
        with patch("resources.lib.itv_account.itv_session", return_value=account):
            resp = itv_account.fetch_authenticated(fetch.get_json, URL)
        self.assertEqual({'a': 1}, resp)
        mocked_get.assert_called_once_with(url=URL, cookies={}, headers={'authorization': 'Bearer 123abc'})

    @patch('resources.lib.settings.login')
    @patch('resources.lib.kodi_utils.show_msg_not_logged_in')
    @patch("resources.lib.itv_account.itv_session", return_value=AccountMock())
    @patch("resources.lib.fetch.get_json", side_effect=[errors.AuthenticationError, {'a': 1}])
    def test_authenticated_fetch_meets_auth_error_response(self, mocked_get, mocked_session, mocked_dialog, mocked_login):
        """Refresh tokens on authentication error and try again"""
        resp = itv_account.fetch_authenticated(fetch.get_json, URL)
        mocked_session.return_value.refresh.assert_called_once()
        mocked_dialog.assert_not_called()
        mocked_login.assert_not_called()
        self.assertEqual(2, mocked_get.call_count)
        self.assertEqual({'a': 1}, resp)

    @patch('resources.lib.settings.login')
    @patch('resources.lib.kodi_utils.show_msg_not_logged_in')
    @patch("resources.lib.itv_account.itv_session", return_value=AccountMock())
    @patch('resources.lib.fetch.HttpSession.request',
           return_value=HttpResponse(status_code=403,
                                     content=b'{"Message": "UserTokenValidationFailed for user: Some(92a3bfde-bfe1-'
                                             b'40ea-ad43-09b8b522b7cb) message: User does not have entitlements"}'))
    def test_authenticated_fetch_meets_auth_error_no_subscription(self, mocked_get, mocked_account, mocked_dialog, mocked_login):
        """Caused by trying to play a premium stream without a premium account
        Should raise a AccessRestrictedError without attempts to refresh or login.
        """
        self.assertRaises(errors.AccessRestrictedError, itv_account.fetch_authenticated, fetch.get_json, URL)
        mocked_account.return_value.refresh.assert_not_called()
        mocked_dialog.assert_not_called()
        mocked_login.login.assert_not_called()
        self.assertEqual(1, mocked_get.call_count)

    @patch('resources.lib.settings.login')
    @patch('resources.lib.kodi_utils.show_msg_not_logged_in')
    @patch("resources.lib.itv_account.itv_session", return_value=AccountMock())
    @patch("resources.lib.fetch.get_json", side_effect=[errors.AuthenticationError, {'a': 1}])
    def test_authenticated_fetch_refresh_fails_(self, mocked_get, mocked_account, mocked_dialog, mocked_login):
        """Refresh tokens on authentication error and show a dialog to go to settings if refresh fails"""
        mocked_account.return_value.refresh.return_value = False
        with self.assertRaises(SystemExit) as cm:
            itv_account.fetch_authenticated(fetch.get_json, URL)
        self.assertEqual(1, cm.exception.code)
        mocked_account.return_value.refresh.assert_called_once()
        mocked_login.assert_not_called()       # Fetch_authenticated does NOT login automatically
        mocked_get.assert_called_once()
        mocked_dialog.assert_called_once()

    @patch("resources.lib.itv_account.itv_session", return_value=AccountMock())
    @patch("resources.lib.fetch.get_json", side_effect=errors.AuthenticationError)
    def test_authenticated_not_authenticated_even_after_successful_refresh(self, mocked_get, mocked_account):
        self.assertRaises(errors.AccessRestrictedError, itv_account.fetch_authenticated, fetch.get_json, URL)
        mocked_account.return_value.refresh.assert_called_once()
        self.assertEqual(2, mocked_get.call_count)
