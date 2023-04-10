# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viewx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import logging as py_logging

import unittest
from unittest.mock import MagicMock, patch

from resources.lib import settings
from resources.lib import addon_log
from resources.lib import errors


class Login(unittest.TestCase):
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
            self.assertFalse(settings.login())
        p_login.assert_not_called()

    @patch("resources.lib.kodi_utils.ask_credentials", return_value=('my_name', 'my_password'))
    @patch("resources.lib.kodi_utils.ask_login_retry", return_value=False)
    def test_login_encounters_http_errors_without_retry(self, p_ask_retry, p_ask_cred):
        with patch('resources.lib.itv_account.ItvSession.login', side_effect=errors.AuthenticationError):
            self.assertFalse(settings.login())
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
        self.assertTrue(settings.login())
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
