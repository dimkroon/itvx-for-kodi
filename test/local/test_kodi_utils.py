# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import patch

from resources.lib import kodi_utils
from resources.lib import utils


class TestKodiUtils(unittest.TestCase):
    def test_ask_credentials(self):
        resp = kodi_utils.ask_credentials('name', 'pw')
        self.assertIsInstance(resp, tuple)
        self.assertEqual(2, len(resp))
        with patch('codequick.utils.keyboard', side_effect=('new_user', 'new_password')):
            self.assertTupleEqual(('new_user', 'new_password'), kodi_utils.ask_credentials('name', 'pw'))

    def test_show_msg_not_logged_in(self):
        self.assertTrue(kodi_utils.show_msg_not_logged_in())
        with patch('xbmcgui.Dialog.yesno', return_value=False):
            self.assertFalse(kodi_utils.show_msg_not_logged_in())

    # noinspection PyMethodMayBeStatic
    def test_ask_login_retry(self):
        self.assertTrue(kodi_utils.ask_login_retry('some_reason'))
        self.assertTrue(kodi_utils.ask_login_retry('Invalid username'))
        self.assertTrue(kodi_utils.ask_login_retry('Invalid password'))
        with patch('xbmcgui.Dialog.yesno', return_value=False):
            self.assertFalse(kodi_utils.ask_login_retry('Invalid password'))

    def test_ask_log_handler(self):
        with patch('xbmcgui.Dialog.contextmenu', return_value=1):
            # return user selection
            result, name = kodi_utils.ask_log_handler(2)
            self.assertEqual(1, result)
            self.assertIsInstance(name, str)
        with patch('xbmcgui.Dialog.contextmenu', return_value=-1):
            # return default value when the user cancels the dialog
            result, _ = kodi_utils.ask_log_handler(2)
            self.assertEqual(2, result)
        with patch('xbmcgui.Dialog.contextmenu', return_value=-1):
            # default value cannot be mapped to a name
            result, name = kodi_utils.ask_log_handler(5)
            self.assertEqual(5, result)
            self.assertEqual('', name)

    def test_ask_play_from_start(self):
        kodi_utils.ask_play_from_start()
        kodi_utils.ask_play_from_start('Title')
        self.assertRaises(ValueError, kodi_utils.ask_play_from_start, 1235)

    def test_get_system_setting(self):
        with patch("xbmc.executeJSONRPC",
                   return_value='{"id": 1, "jsonrpc": "2.0", "result": {"value": "Europe/Amsterdam"}}') as p_rpc:
            self.assertEqual('Europe/Amsterdam', kodi_utils.get_system_setting("my.setting"))
            p_rpc.assert_called_once_with(
                '{"jsonrpc": "2.0", "method": "Settings.GetSettingValue", "params": ["my.setting"], "id": 1}')

        with patch("xbmc.executeJSONRPC",
                   return_value='{"error":{"code":-32602,"message":"Invalid params."},"id": 1,"jsonrpc": "2.0"}'):
            self.assertRaises(ValueError, kodi_utils.get_system_setting, "my.setting")

    def test_local_time_zone(self):
        tz = kodi_utils.local_timezone()
        self.assertIsInstance(tz, utils.ZoneInfo)
        with patch('resources.lib.kodi_utils.get_system_setting', side_effect=ValueError):
            tz = kodi_utils.local_timezone()
            self.assertIsInstance(tz, utils.ZoneInfo)


@patch('xbmcgui.Dialog.ok')
class MessageDialog(unittest.TestCase):
    def test_open_with_text(self, p_ok):
        kodi_utils.msg_dlg('Message')
        p_ok.assert_called_once_with('viwX', 'Message')
        p_ok.reset_mock()
        kodi_utils.msg_dlg('Message', 'Title')
        p_ok.assert_called_once_with('Title', 'Message')
        self.assertRaises(TypeError, kodi_utils.msg_dlg, title='Title')

    def test_open_with_string_id(self, p_ok):
        kodi_utils.msg_dlg(30101)
        p_ok.assert_called_once_with('viwX', 'Catchup programs')
        p_ok.reset_mock()
        kodi_utils.msg_dlg(30101, 30100)
        p_ok.assert_called_once_with('General', 'Catchup programs')

    def test_open_with_formattable_string(self, p_ok):
        kodi_utils.msg_dlg('value = {number}', number=102)
        p_ok.assert_called_once_with('viwX', 'value = 102')
        p_ok.reset_mock()
        # No formatting when no keyword arguments are passed
        kodi_utils.msg_dlg('value = {number}', title='Title')
        p_ok.assert_called_once_with('Title', 'value = {number}')