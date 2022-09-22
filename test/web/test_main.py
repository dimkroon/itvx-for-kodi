import account_login
account_login.set_credentials()

import unittest
from unittest.mock import MagicMock
from typing import MutableMapping

from resources.lib import main


class TestMenu(unittest.TestCase):
    def test_menu_live(self):
        items = list(main.sub_menu_live(MagicMock()))
        self.assertEqual(6, len(items))
        for item in items:
            print(item.params['url'])

    def test_menu_shows(self):
        items  = list(main.list_programs(MagicMock(), url='https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay&sortBy=title'))
        for item in items:
            print(item.params['url'])

    def test_submenu_episodes(self):
        for item in main.sub_menu_episodes(MagicMock(), 'cheat/2a5517'):
            print(item)


class TestFullSeries(unittest.TestCase):
    def test_full_series_drama(self):
        items = list(main.sub_menu_full_series(MagicMock(), '/hub/full-series/drama'))
        for item in items:
            print(item)


class TestCategories(unittest.TestCase):
    def test_category_comedy(self):
        items = list(main.sub_menu_full_series(MagicMock(), '/hub/categories/comedy'))
        for item in items:
            print(item)


class TestGetEpisodes(unittest.TestCase):
    def test_episodes_midsummer_murders(self):
        items = list(main.sub_menu_episodes(MagicMock(), 'https://www.itv.com/hub/midsomer-murders/Ya1096'))
        for item in items:
            print(item)


class TestGetProductions(unittest.TestCase):
    def test_productions_midsummer_murders(self):
        items = list(main.list_productions(MagicMock(), 'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=Y_1096&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv'))
        for item in items:
            print(item)

    def test_get_productions_midsummer_murder_folder_1(self):
        items = list(main.list_productions(MagicMock(),
                                           'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=Y_1096&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv',
                                           series_idx=1))
        for item in items:
            print(item)

    def test_get_productions_the_professionals_folder_1(self):
        items = list(main.list_productions(MagicMock(),
                                           'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=L0845&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv',
                                           series_idx=1))
        for item in items:
            print(item)

    def test_get_productions_the_chase(self):
        """The chase had 53 items, but only one production was shown"""
        items = list(main.list_productions(MagicMock(),
                                           'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                           'programmeId=1_7842&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                           'playready,widevine&broadcaster=itv',
                                           name='The Chase'),)
        self.assertGreater(len(items), 1)
        for item in items:
            print(item)

class TestPlayShow(unittest.TestCase):
    def test_play_show_a_late_quartet(self):
        result = main.play_show(MagicMock(), url='https://magni.itv.com/playlist/itvonline/ITV/10_2597_0001.001', show_name='A Late Quartet')
        self.assertIsInstance(result.params, MutableMapping)


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