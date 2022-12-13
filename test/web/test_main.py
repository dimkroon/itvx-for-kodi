# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import MagicMock
from typing import MutableMapping

from resources.lib import main


setUpModule = fixtures.setup_web_test


class TestMenu(unittest.TestCase):
    def test_menu_live(self):
        items = list(main.sub_menu_live(MagicMock()))
        self.assertGreaterEqual(len(items), 10)
        for item in items:
            print(item.params['url'])

    def test_menu_shows(self):
        items  = list(main.list_programs(MagicMock(), url='https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay&sortBy=title'))
        for item in items:
            print(item.params['url'])


class TestGetProductions(unittest.TestCase):
    def test_productions_midsummer_murders(self):
        items = list(main.list_productions(
            MagicMock(),
            'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=Y_1096&features=aes,'
            'clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv'))
        for item in items:
            print(item)

    def test_get_productions_midsummer_murder_folder_1(self):
        items = list(main.list_productions(
            MagicMock(),
           'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=Y_1096&features=aes,'
           'clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv',
           series_idx=1))
        for item in items:
            print(item)

    def test_get_productions_the_professionals_folder_1(self):
        items = list(main.list_productions(
            MagicMock(),
           'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=L0845&features=aes,'
           'clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv',
           series_idx=1))
        for item in items:
            print(item)

    def test_get_productions_the_chase(self):
        """The chase had 53 items, but only one production was shown"""
        items = list(main.list_productions(
            MagicMock(),
           'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=1_7842&features=aes,'
           'clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv',
           name='The Chase'))
        self.assertGreater(len(items), 1)
        for item in items:
            print(item)

    def test_get_productions_doctor_foster(self):
        """Productions of a paid programme
        Fails with a non-subscription account"""
        items = main.list_productions(
            MagicMock(),
            'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=2_7438&features=aes,'
            'clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv',
            name='Doctor Foster')
        self.assertIs(False, items)


class TestPlayCatchup(unittest.TestCase):
    def test_play_itv_1(self):
        result = main.play_stream_live(MagicMock(), "itv", None)
        self.assertEqual('itv', result.label)
        self.assertIsInstance(result.params, MutableMapping)

    def test_play_vod_a_touch_of_frost(self):
        result = main.play_stream_catchup(MagicMock(),
                                          url='https://magni.itv.com/playlist/itvonline/ITV3/Y_1774_0002_Y',
                                          name='A Touch of Frost')
        self.assertEqual('A Touch of Frost', result.label)
        self.assertIsInstance(result.params, MutableMapping)

    def test_play_vod_episode_julia_bradbury(self):
        result = main.play_stream_catchup(MagicMock(),
                                          url='https://magni.itv.com/playlist/itvonline/ITV/10_0852_0001.001',
                                          name='Walks with Julia Bradbury')
        self.assertEqual('Walks with Julia Bradbury', result.label)
        self.assertIsInstance(result.params, MutableMapping)