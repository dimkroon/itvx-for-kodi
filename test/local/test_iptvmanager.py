# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import json
import unittest
from unittest.mock import MagicMock, patch

from test.support.object_checks import is_not_empty
from test.support.testutils import open_json
from resources.lib import iptvmanager


class TestIptvmanager(unittest.TestCase):
    def test_send_channels(self):
        mocked_socket = MagicMock()
        mocked_socket.sendall = MagicMock()
        with patch('socket.socket', return_value=mocked_socket):
            iptvm = iptvmanager.IPTVManager(port=10)
            iptvm.send_channels()
        mocked_socket.sendall.assert_called_once()
        call_dta = json.loads(mocked_socket.sendall.call_args[0][0])
        self.assertEqual(1, call_dta['version'])
        chan_list = call_dta['streams']
        for chan in chan_list:
            for key in ('id', 'name', 'logo', 'stream'):
                self.assertTrue(is_not_empty(chan[key], str))

    def test_send_epg(self):
        epg_data = {'ITV': [{'start': "23:23", 'end': '12:43', 'title': 'my title', 'description': ''}],
                    'ITV2': [{'start': "23:23", 'end': '12:43', 'title': 'his title', 'description': ''}],
                    'ITV3': [{'start': "23:23", 'end': '12:43', 'title': 'm title', 'description': ''}]}
        mocked_socket = MagicMock()
        mocked_socket.sendall = MagicMock()
        with patch('socket.socket', return_value=mocked_socket):
            with patch('resources.lib.itvx.get_full_schedule', return_value=epg_data):
                iptvm = iptvmanager.IPTVManager(port=10)
                iptvm.send_epg()

        mocked_socket.sendall.assert_called_once()
        call_dta = json.loads(mocked_socket.sendall.call_args[0][0])
        self.assertEqual(1, call_dta['version'])
        self.assertListEqual(list(epg_data.values()), list(call_dta['epg'].values()))

    @patch('json.dumps', side_effect=ValueError)
    def test_send_with_error(self, _):
        mocked_socket = MagicMock()
        mocked_socket.sendall = MagicMock()
        mocked_socket.close = MagicMock()
        with patch('socket.socket', return_value=mocked_socket):
            iptvm = iptvmanager.IPTVManager(port=10)
            self.assertRaises(ValueError, iptvm.send_channels)
        mocked_socket.sendall.assert_not_called()
        mocked_socket.close.assert_called()


class TestEntryFunctions(unittest.TestCase):
    @patch('resources.lib.iptvmanager.IPTVManager.send_channels')
    def test_channels(self, mocked_send_channels):
        iptvmanager.channels.test(port=1234)
        mocked_send_channels.assert_called_once()

    @patch('resources.lib.iptvmanager.IPTVManager.send_channels', side_effect=ValueError)
    def test_channels_with_error(self, _):
        """Errors should be ignored silently"""
        iptvmanager.channels.test(port=1234)

    @patch('resources.lib.iptvmanager.IPTVManager.send_epg')
    def test_epg(self, mocked_send_epg):
        iptvmanager.epg.test(port=1234)
        mocked_send_epg.assert_called_once()

    @patch('resources.lib.iptvmanager.IPTVManager.send_epg', side_effect=ValueError)
    def test_epg_with_error(self, _):
        """Errors should be ignored silently"""
        iptvmanager.epg.test(port=1234)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('schedule/html_schedule.json'))
    def test_egp_integration(self, _):
        mocked_socket = MagicMock()
        mocked_socket.sendall = MagicMock()
        with patch('socket.socket', return_value=mocked_socket):
            iptvmanager.epg.test(port=1234)
        send_data = json.loads(mocked_socket.sendall.call_args[0][0])
        self.assertEqual(len(send_data['epg']), 5)

