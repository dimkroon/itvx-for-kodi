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


class TestEntryFunctions(unittest.TestCase):
    @patch('resources.lib.iptvmanager.IPTVManager.send_channels')
    def test_channels(self, mocked_send_channels):
        iptvmanager.channels.test(port=1234)
        mocked_send_channels.assert_called_once()

    @patch('resources.lib.iptvmanager.IPTVManager.send_channels', side_effect=ValueError)
    def test_channels_with_error(self, _):
        """Errors should be ignored silently"""
        iptvmanager.channels.test(port=1234)
