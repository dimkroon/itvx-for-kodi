# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import json
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

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
        epg_data = {'ITV1': [{'start': "23:23", 'end': '12:43', 'title': 'my title', 'description': ''}],
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


class TestChannelSchedule(unittest.TestCase):
    def setUp(self):
        self.json_epg_1 = [
            {'start': '2025-06-01T04:04:04Z', 'stop': '2025-06-01T05:05:05Z',
             'description': 'progr 2'},
            {'start': '2025-06-01T03:03:03Z', 'stop': '2025-06-01T04:04:04Z',
             'description': 'progr 1'},
            {'start': '2025-06-01T05:05:05Z', 'stop': '2025-06-01T06:06:06Z',
             'description': 'progr 3'},
            {'start': '2025-06-01T02:02:02Z', 'stop': '2025-06-01T03:03:03Z',
             'description': 'progr 0'}
        ]

        self.json_epg_2 = [
            {'start': '2025-06-01T03:03:03Z', 'stop': '2025-06-01T04:04:04Z',
             'description': 'news', 'vod': 'link.to.news'},
            {'start': '2025-06-01T04:04:04Z', 'stop': '2025-06-01T05:99:99Z',     # different end time!
             'description': None, 'vod': None},
            {'start': '2025-06-01T06:06:06Z', 'stop': '2025-06-01T07:07:07Z',
             'description': 'some programme'},
            {'start': '2025-06-01T07:07:07Z', 'stop': '2025-06-01T08:08:08Z',
             'description': 'other programme'},
            {'start': '2025-06-01T08:08:08Z', 'stop': '2025-06-01T09:09:09Z'}
        ]

    def test_instance(self):
        s = iptvmanager.ChannelSchedule('My Chan', self.json_epg_1)
        self.assertEqual(4, len(s))
        self.assertEqual(s.channel, "My Chan")
        self.assertEqual(s.programme_list, sorted(self.json_epg_1, key=lambda x: x['start']))
        s = iptvmanager.ChannelSchedule('My Chan', [])
        self.assertEqual(0, len(s))
        self.assertListEqual(s.programme_list, [])
        # schedule list is not JSON-EPG
        self.assertRaises(TypeError, iptvmanager.ChannelSchedule, 'MyChan', [1, 2, 3])

    def test_item_access(self):
        # Items are sorted on start time.
        s = iptvmanager.ChannelSchedule('My Chan', self.json_epg_1)
        self.assertDictEqual(s[0], {'start': '2025-06-01T02:02:02Z', 'stop': '2025-06-01T03:03:03Z',
                                    'description': 'progr 0'})
        self.assertDictEqual(s[-1], {'start': '2025-06-01T05:05:05Z', 'stop': '2025-06-01T06:06:06Z',
                                     'description': 'progr 3'})

    def test_slicing(self):
        s = iptvmanager.ChannelSchedule('My Chan', self.json_epg_1)
        sliced_s = s[1:3]
        self.assertIsInstance(sliced_s, iptvmanager.ChannelSchedule)
        self.assertEqual(sliced_s.channel, "My Chan")
        self.assertDictEqual(sliced_s[0], s[1])
        self.assertDictEqual(sliced_s[-1], s[2])

    def test_iterator(self):
        s = iptvmanager.ChannelSchedule('My Chan', self.json_epg_1)
        count = 0
        for item in s:
            self.assertEqual(item, s[count])
            count += 1

    def test_update_programme_info(self):
        s1 = iptvmanager.ChannelSchedule('My Chan', self.json_epg_1)
        s2 = iptvmanager.ChannelSchedule('My Chan', self.json_epg_2)
        s1.update_programme_info(s2)
        # Length has not changed
        self.assertEqual(len(s1), len(self.json_epg_1))
        # Values are updated
        self.assertEqual(s1[1]['start'], '2025-06-01T03:03:03Z')
        self.assertEqual(s1[1]['description'], 'news')
        self.assertEqual(s1[1]['vod'], self.json_epg_2[0]['vod'])
        # None values are not copied
        self.assertEqual(s1[2]['start'], '2025-06-01T04:04:04Z')
        self.assertEqual(s1[2]['description'], 'progr 2')
        self.assertRaises(KeyError, lambda: s1[2]['vod'])
        # End time is not copied
        self.assertEqual(s1[2]['stop'], '2025-06-01T05:05:05Z')
        # Other items remain unchanged
        self.assertEqual(s1[0], self.json_epg_1[3])
        self.assertEqual(s1[3], self.json_epg_1[2])

    def test_filter(self):
        s = iptvmanager.ChannelSchedule('My chan', self.json_epg_2)
        self.assertEqual(5, len(s))
        # filter on exact start times
        new_s = s.filter(datetime(2025, 6, 1, 4, 4, 4), datetime(2025, 6, 1, 8, 8, 8))
        self.assertEqual(new_s.channel, 'My chan')
        self.assertEqual(3, len(new_s))
        self.assertEqual(new_s[0]['start'], '2025-06-01T04:04:04Z')
        self.assertEqual(new_s[-1]['start'], '2025-06-01T07:07:07Z')
        # `to_time` is larger than present in new_epg
        new_s = s.filter(datetime(2025, 6, 1, 6, 6, 6), datetime(2025, 6, 1, 11, 11, 11))
        self.assertEqual(new_s.channel, 'My chan')
        self.assertEqual(3, len(new_s))
        self.assertEqual(new_s[0]['start'], '2025-06-01T06:06:06Z')
        self.assertEqual(new_s[-1]['start'], '2025-06-01T08:08:08Z')
        # `from_time` is smaller than present in new_epg
        new_s = s.filter(datetime(2025, 6, 1, 1, 1, 1), datetime(2025, 6, 1, 5, 5, 5))
        self.assertEqual(new_s.channel, 'My chan')
        self.assertEqual(len(new_s), 2)
        self.assertEqual(new_s[0]['start'], '2025-06-01T03:03:03Z')
        self.assertEqual(new_s[-1]['start'], '2025-06-01T04:04:04Z')
        # End time is None should include everything from `from_time` up to `to_time`
        new_s = s.filter(datetime(2025, 6, 1, 4, 4, 4))
        self.assertEqual(4, len(new_s))
        self.assertEqual(new_s[0]['start'], '2025-06-01T04:04:04Z')
        self.assertEqual(new_s[-1]['start'], '2025-06-01T08:08:08Z')
        # Start time is None should include everything up to `to_time`
        new_s = s.filter(to_time=datetime(2025, 6, 1, 7, 7, 7))
        self.assertEqual(3, len(new_s))
        self.assertEqual(new_s[0]['start'], '2025-06-01T03:03:03Z')
        self.assertEqual(new_s[-1]['start'], '2025-06-01T06:06:06Z')
        # Not exact date-time - filter should the take the first item following start time.
        new_s = s.filter(datetime(2025, 6, 1, 3, 50, 50), datetime(2025, 6, 1, 8, 0, 0))
        self.assertEqual(3, len(new_s))
        self.assertEqual(new_s[0]['start'], '2025-06-01T04:04:04Z')
        self.assertEqual(new_s[-1]['start'], '2025-06-01T07:07:07Z')

    def test_extend(self):
        """Extend should only add programmes following those already in the list."""
        # Last programme start does not overlap with first programmes to extend.
        s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_1)
        other_s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_2)
        s.extend(other_s)
        self.assertEqual(7, len(s))
        self.assertEqual(s[0]['start'], '2025-06-01T02:02:02Z')  # from s
        self.assertEqual(s[3]['start'], '2025-06-01T05:05:05Z')  # from s
        self.assertEqual(s[4]['start'], '2025-06-01T06:06:06Z')  # from other_s
        self.assertEqual(s[-1]['start'], '2025-06-01T08:08:08Z')  # from other_s

        # Last programme start is the as first programmes to extend.
        self.setUp()
        new_epg = [
            {'start': '2025-06-01T05:05:05Z', 'stop': '2025-06-01T01:01:01Z'},
            {'start': '2025-06-01T05:05:05Z', 'stop': '2025-06-01T06:06:06Z'},
            {'start': '2025-06-01T06:06:06Z', 'stop': '2025-06-01T07:07:07Z'},
        ]
        s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_1)
        other_s = iptvmanager.ChannelSchedule('My Channel', new_epg)
        s.extend(other_s)
        # earlier programmes from other_s are disregarded.
        self.assertEqual(s[0]['start'], '2025-06-01T02:02:02Z')  # from s
        self.assertEqual(s[3]['start'], '2025-06-01T05:05:05Z')  # from s
        self.assertEqual(s[3]['description'], 'progr 3')  # from s
        self.assertEqual(s[4]['start'], '2025-06-01T06:06:06Z')  # from other_s

        # Extend to an empty schedule
        self.setUp()
        s = iptvmanager.ChannelSchedule('My Channel', [])
        other_s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_1)
        s.extend(other_s)
        self.assertListEqual(s._pgm_list, other_s._pgm_list)
        self.assertFalse(s._pgm_list is other_s._pgm_list)

        # Extend a list object
        self.setUp()
        s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_1)
        s.extend(self.json_epg_2)
        self.assertEqual(7, len(s))

        # Not a valid object
        self.setUp()
        s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_1)
        self.assertRaises(TypeError, s.extend, {})

    def test_comparison(self):
        s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_1)
        other_s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_1)
        self.assertEqual(s, other_s)
        other_s = iptvmanager.ChannelSchedule('Other Channel', self.json_epg_1)
        self.assertNotEqual(s, other_s)
        other_s = iptvmanager.ChannelSchedule('My Channel', self.json_epg_2)
        self.assertNotEqual(s, other_s)


class TestEpgSchedule(unittest.TestCase):
    def setUp(self):
        self.epg = iptvmanager.Epg()
        self.s1 = MagicMock(spec=iptvmanager.ChannelSchedule)
        self.s1.channel = "Chan1"
        self.s2 = MagicMock(spec=iptvmanager.ChannelSchedule)
        self.s2.channel = "Chan2"
        self.epg.add_schedule(self.s1)
        self.epg.add_schedule(self.s2)

    def test_add_channel(self):
        s1 = MagicMock(spec=iptvmanager.ChannelSchedule)
        s1.channel = "Chan3"
        self.epg.add_schedule(s1)

        # Not a ChannelSchedule object
        self.assertRaises(AttributeError, self.epg.add_schedule, [])

    def test_filter(self):
        from_t = datetime(2025, 6, 1, 5, 5, 5)
        to_t = datetime(2025, 6, 1, 6, 6, 6)
        self.epg.filter(from_t, to_t)
        # filter is called on all schedules
        self.s1.filter.assert_called_with(from_t, to_t)
        self.s2.filter.assert_called_with(from_t, to_t)

    def test_update_programme_info(self):
        other_epg = iptvmanager.Epg()
        for chan_name in ('Chan1', 'Chan3'):
            sched = MagicMock(spec=iptvmanager.ChannelSchedule)
            sched.channel = chan_name
            sched.__len__.return_value = 1       # otherwise bool(sched) is False.
            other_epg.add_schedule(sched)

        self.epg.update_programme_info(other_epg)
        # Update is called on each schedule that has a corresponding schedule in other_epg
        self.s1.update_programme_info.assert_called_once_with(other_epg['Chan1'])
        self.s2.update_programme_info.assert_not_called()
        # Schedule of 'Chan3' is not added
        self.assertEqual(list(self.epg.keys()), ['Chan1', 'Chan2'])

    def test_extend(self):
        epg2 = iptvmanager.Epg()
        s2_1 = MagicMock(spec=iptvmanager.ChannelSchedule)
        s2_1.channel = "Chan1"
        epg2.add_schedule(s2_1)
        s2_3 = MagicMock(spec=iptvmanager.ChannelSchedule)
        s2_3.channel = "Chan3"
        epg2.add_schedule(s2_3)

        # All ChannelSchedules are extended with their corresponding channel in epg2
        self.epg.extend(epg2)
        self.s1.extend.assert_called_with(s2_1)
        self.s2.extend.assert_not_called()
        # New channel from epg2 is added.
        self.assertTrue('Chan3' in epg2._chan_schedules)

        # Not an Epg object
        self.assertRaises(TypeError, epg2.extend, [])

    def test_json_epg(self):
        pgm_list = [
            {'start': '2025-06-01T05:05:05Z', 'stop': '2025-06-01T01:01:01Z'},
            {'start': '2025-06-01T05:05:05Z', 'stop': '2025-06-01T06:06:06Z'}
        ]
        epg = iptvmanager.Epg()
        s1 = iptvmanager.ChannelSchedule('Chan1', pgm_list)
        epg.add_schedule(s1)
        json_epg = epg.json_epg
        self.assertEqual(1, len(epg))
        self.assertListEqual(json_epg['Chan1'], pgm_list)

        new_epg = iptvmanager.Epg.from_json_epg(json_epg)
        self.assertIsInstance(new_epg, iptvmanager.Epg)
        self.assertDictEqual(new_epg.json_epg, json_epg)

        # Fails silently on errors.
        # noinspection PyTypeChecker
        invalid_epg = iptvmanager.Epg.from_json_epg(12345)
        self.assertIsInstance(new_epg, iptvmanager.Epg)
        self.assertEqual(invalid_epg.json_epg, {})

    def test_item_access(self):
        self.assertIsInstance(self.epg['Chan1'], iptvmanager.ChannelSchedule)
        self.epg['Chan3'] = self.s1
        self.assertListEqual(list(self.epg.keys()), ['Chan1', 'Chan2', 'Chan3'])
        del self.epg['Chan2']
        self.assertListEqual(list(self.epg.keys()), ['Chan1', 'Chan3'])
        with self.assertRaises(TypeError):
            self.epg['Chan4'] = []
