# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import xbmcgui

import logging as py_logging

import unittest
from unittest.mock import MagicMock, patch

from resources.lib import itv_account
from resources.lib import settings
from resources.lib import addon_log
from resources.lib import errors

from support.testutils import doc_path, open_doc, SessionMock


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class Login(unittest.TestCase):
    """
    Ensure login() does not return a value. A Script's return value is treated as a redirect url by codequick.
    """
    @patch('resources.lib.itv_account.ItvSession.login')
    @patch("resources.lib.kodi_utils.ask_credentials", return_value=('my_name', 'my_passw'))
    # noinspection PyMethodMayBeStatic
    def test_login(self, p_login, _):
        # When called from settings, codequick passes a Route object login(), here simulated by a mock object.
        settings.login(MagicMock())
        p_login.assert_called_once()

    @patch("resources.lib.kodi_utils.ask_credentials", side_effect=[('', ''), ('my_name', ''), ('', 'my_passw')])
    @patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.AuthenticationError)
    def test_user_cancels_user_or_password_entry(self, p_login, _):
        """Test all situation where NOT both username and password are provided.
        The last one should practically never occur though."""
        for _ in range(3):
            self.assertIsNone(settings.login())
        p_login.assert_not_called()

    @patch("resources.lib.kodi_utils.ask_credentials", return_value=('my_name', 'my_password'))
    @patch("resources.lib.kodi_utils.ask_login_retry", return_value=False)
    def test_login_encounters_http_errors_without_retry(self, p_ask_retry, p_ask_cred):
        with patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.AuthenticationError):
            self.assertIsNone(settings.login())
            p_ask_retry.assert_called_once()
            p_ask_cred.assert_called_once()

            p_ask_retry.reset_mock()
            p_ask_cred.reset_mock()
        with patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.HttpError(404, '')):
            self.assertRaises(errors.HttpError, settings.login)
            p_ask_retry.assert_not_called()
            p_ask_cred.assert_called_once()

            p_ask_cred.reset_mock()
        with patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.GeoRestrictedError):
            self.assertRaises(errors.GeoRestrictedError, settings.login)
            p_ask_retry.assert_not_called()
            p_ask_cred.assert_called_once()

    @patch("resources.lib.kodi_utils.ask_credentials", return_value=('my_name', 'my_password'))
    @patch("resources.lib.kodi_utils.ask_login_retry", return_value=True)
    @patch('resources.lib.itv_account.ItvSession.login', side_effect=(errors.AuthenticationError, True))
    def test_login_succeeds_after_retry(self, p_login, p_ask_retry, p_ask_cred):
        self.assertIsNone(settings.login())
        self.assertEqual(2, p_login.call_count)
        self.assertEqual(2, p_ask_cred.call_count)
        p_ask_retry.assert_called_once()


@patch("resources.lib.kodi_utils.ask_login_retry", side_effect=(True, False))
# noinspection PyMethodMayBeStatic
class LoginRetryBehaviour(unittest.TestCase):
    @patch('resources.lib.itv_account.ItvSession.login', return_value=True)
    @patch("resources.lib.kodi_utils.ask_credentials", new=lambda a, b: ('my_name', 'my_password'))
    def test_login_no_retry_on_successful_login(self, _, p_ask_retry):
        settings.login()
        p_ask_retry.assert_not_called()

    @patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.AuthenticationError)
    @patch("resources.lib.kodi_utils.ask_credentials", new=lambda a, b: ('', ''))
    def test_login_no_retry_on_canceled_credentials(self, _, p_ask_retry):
        self.assertFalse(settings.login())
        p_ask_retry.assert_not_called()

    @patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.AuthenticationError)
    @patch("resources.lib.kodi_utils.ask_credentials", side_effect=(('my_name', 'my_password'), ('', '')))
    def test_login_no_second_retry_on_canceled_credentials(self, _, __, p_ask_retry):
        """The user cancels entering credentials after the first retry has been offered"""
        self.assertFalse(settings.login())
        p_ask_retry.assert_called_once()

    @patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.HttpError(404, ''))
    @patch("resources.lib.kodi_utils.ask_credentials", new=lambda a, b: ('my_name', 'my_password'))
    def test_login_no_retry_on_other_errors(self, _, p_ask_retry):
        self.assertRaises(errors.HttpError, settings.login)
        p_ask_retry.assert_not_called()

    @patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.AuthenticationError)
    @patch("resources.lib.kodi_utils.ask_credentials", new=lambda a, b: ('my_name', 'my_password'))
    def test_login_retry_on_wrong_credentials(self, p_post, p_ask_retry):
        # Login() returns false when the second request for retry is rejected (by pathed ask_login_retry).
        self.assertFalse(settings.login())
        self.assertEqual(2, p_ask_retry.call_count)
        self.assertEqual(2, p_post.call_count)  # 1 original login, 1 after first retry


@patch('resources.lib.settings.check_token_data')
class ImportAuthTokens(unittest.TestCase):
    @patch('xbmcgui.Dialog.browseSingle', return_value=doc_path('cookie-files/firefox-cookie.txt'))
    def test_import_file(self, p_dlg, p_check):
        settings.import_tokens.test()
        p_dlg.assert_called_once()
        p_check.assert_called_once()

    @patch('xbmcgui.Dialog.browseSingle', return_value='')
    def test_file_select_canceled(self, p_dlg, p_check):
        settings.import_tokens.test()
        p_dlg.assert_called_once()
        p_check.assert_not_called()


class HandleTokenData(unittest.TestCase):
    def test_handle_token_data(self):
        for fname in ('firefox-cookie.txt', 'chromium-cookie.txt', 'viwx-tokens.txt'):
            raw_data = open_doc('cookie-files/' + fname)()
            with patch("resources.lib.itv_account._itv_session_obj", SessionMock()) as p_session:
                settings.check_token_data(raw_data)
                acc_data = itv_account.itv_session().account_data
                self.assertEqual('this.isarefresh.token', acc_data['itv_session']['refresh_token'])
                p_session.refresh.assert_called_once()

    def test_handle_cripled_cookie(self):
        for fname in ('firefox-cookie.txt', 'chromium-cookie.txt'):
            raw_data = open_doc('cookie-files/' + fname)()
            with patch("resources.lib.itv_account._itv_session_obj", SessionMock()) as p_session:
                # First character missing
                settings.check_token_data(raw_data[1:])
                acc_data = itv_account.itv_session().account_data
                self.assertNotEqual('this.isarefresh.token', acc_data['itv_session']['refresh_token'])
                p_session.refresh.assert_not_called()
                # Last character missing
                settings.check_token_data(raw_data[:-1])
                acc_data = itv_account.itv_session().account_data
                self.assertNotEqual('this.isarefresh.token', acc_data['itv_session']['refresh_token'])
                p_session.refresh.assert_not_called()
                # Something in between is missing, making data invalid json
                settings.check_token_data(raw_data[:40] + raw_data[-30:])
                acc_data = itv_account.itv_session().account_data
                self.assertNotEqual('this.isarefresh.token', acc_data['itv_session']['refresh_token'])
                p_session.refresh.assert_not_called()

    @patch("resources.lib.itv_account._itv_session_obj", SessionMock())
    def test_invalid_viwx_token_data(self):
        settings.check_token_data('{"vers": 2}')
        itv_account.itv_session().refresh.assert_not_called()
        settings.check_token_data('"vers": 2')
        itv_account.itv_session().refresh.assert_not_called()

    @patch("resources.lib.itv_account._itv_session_obj", SessionMock())
    def test_handle_unknown_file(self):
        settings.check_token_data('some invalid data')
        acc_data = itv_account.itv_session().account_data
        self.assertNotEqual('this.isarefresh.token', acc_data['itv_session']['refresh_token'])
        itv_account.itv_session().refresh.assert_not_called()

    @patch("resources.lib.itv_account._itv_session_obj", SessionMock())
    def test_cookie_file_not_signed_in(self):
        settings.check_token_data('{"tokens":{"content":{}}}')
        itv_account.itv_session().refresh.assert_not_called()

    @patch("resources.lib.itv_account._itv_session_obj", SessionMock(refresh=False))
    def test_refresh_fails(self):
        settings.check_token_data(open_doc('cookie-files/firefox-cookie.txt')())


class ParseCookies(unittest.TestCase):
    def test_parse_cookie_data(self):
        tokens = settings._parse_cookie('{"tokens":{"content": "These are the tokens"}}')
        self.assertEqual(tokens, "These are the tokens")

    def test_not_signed_in_cookies(self):
        with self.assertRaises(errors.ParseError):
            settings._parse_cookie('{"tokens":{}}')

    def test_invalid_data(self):
        with self.assertRaises(errors.ParseError):
            settings._parse_cookie('{"tokens": "My token"}')


@patch('xbmcvfs.copy')
class ExportAuthTokens(unittest.TestCase):
    @patch('xbmcgui.Dialog.browseSingle', return_value='special://profile')
    def test_export(self, _, p_copy):
        # check we are signed in
        self.assertGreater(itv_account.itv_session().account_data['refreshed'], 0 )
        settings.export_tokens.test()
        p_copy.assert_called_once()

    @patch('xbmcgui.Dialog.browseSingle', return_value='special://profile')
    def test_export_failures(self, _, p_copy):
        # not signed in
        with patch.object(itv_account.itv_session(), '_user_id', ''):
            settings.export_tokens.test()
            p_copy.assert_not_called()
        # write failed
        with patch('xbmcvfs.exists', return_value=False):
            self.assertGreater(itv_account.itv_session().account_data['refreshed'], 0)
            settings.export_tokens.test()
            p_copy.assert_called_once()

    @patch('xbmcgui.Dialog.browseSingle', return_value='')
    def test_export_dialog_canceled(self, _, p_copy):
        # check we are signed in
        self.assertGreater(itv_account.itv_session().account_data['refreshed'], 0)
        settings.export_tokens.test()
        p_copy.assert_not_called()


class TestSettings(unittest.TestCase):
    @patch('resources.lib.itv_account.ItvSession.log_out')
    # noinspection PyMethodMayBeStatic
    def test_logout(self, p_logout):
        settings.logout(MagicMock())
        p_logout.assert_called_once()

    @patch("resources.lib.addon_log.set_log_handler")
    def test_change_logger(self, p_set_log):
        logger = addon_log.logger

        self.assertTrue(hasattr(settings.change_logger, 'route'))

        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(0, 'kodi log')):
            settings.change_logger(MagicMock())
            p_set_log.assert_called_with(addon_log.KodiLogHandler)

        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(1, 'file log')):
            settings.change_logger(MagicMock())
            p_set_log.assert_called_with(addon_log.CtFileHandler)

        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(2, 'no log')) as p_ask:
            with patch.object(logger, 'handlers', new=[addon_log.CtFileHandler()]):
                settings.change_logger(MagicMock())
                p_set_log.assert_called_with(addon_log.DummyHandler)
                p_ask.assert_called_with(1)

        # Test default values passed to ask_log_handler().
        # logger not properly initialised
        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(1, 'file log')) as p_ask:
            with patch.object(logger, 'handlers', new=[]):
                settings.change_logger(MagicMock())
                p_ask.assert_called_with(0)

        # Current handler is of an unknown type
        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(1, 'file log')):
            with patch.object(logger, 'handlers', new=[py_logging.Handler()]):
                settings.change_logger(MagicMock())
                p_ask.assert_called_with(0)
