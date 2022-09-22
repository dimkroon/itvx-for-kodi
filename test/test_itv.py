
from test.support import fixtures
fixtures.global_setup()

import os
import json
import unittest

from typing import Generator

from resources.lib import itv, fetch, itv_account
from codequick import Listitem, Route, Script


setUpModule = fixtures.setup_web_test


@Route.register()
def dummycallback():
    pass


class TestItv(unittest.TestCase):
    def test_get_categories(self):
        result = itv.categories()
        self.assertIsInstance(result, Generator)
        for item in result:
            assert('label' in item.keys())
            assert('params') in item.keys()
            assert('url') in item['params'].keys()

    def test_get_shows(self):
        result = itv.get_shows()
        self.assertIsInstance(result, Generator)

    def test_get_live_schedule(self):
        result = itv.get_live_schedule()
        print(json.dumps(result, indent=4))

    def test_get_programmes(self):
        # get all shows
        result = itv.programmes('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay&sortBy=title')
        self.assertIsInstance(result, Generator)
        for item in result:
            self.assertIsInstance(item, dict)
            self.assertTrue(tuple(item.keys()) == ('episodes', 'show'))
            self.assertIsInstance(item['episodes'], int)
            self.assertIsInstance(item['show'], dict)

    def test_get_productions(self):
        """Get episodes of a show"""
        for show in (
            ('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=1_0694&features=aes,'
             'clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv', 'Coronation Street'),
            ('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId=Y_1096&features=aes,'
             'clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv', "Midsomer Murders")
        ):
            result = itv.productions(*show)
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            for item in result:
                self.assertIsInstance(item, dict)
                self.assertTrue(tuple(item.keys()) == ('name', 'episodes'))
                self.assertIsInstance(item['name'], str)
                self.assertIsInstance(item['episodes'], list)
                for episode in item['episodes']:
                    self.assertIsInstance(episode, dict)
                    Listitem.from_dict(dummycallback, **episode)

    def test_get_playlist_url_from_episode_page(self):
        episode_url = 'https://www.itv.com/hub/holding/7a0203a0002'
        url, name = itv.get_playlist_url_from_episode_page(episode_url)
        self.assertEqual('Holding', name)
        self.assertTrue(url.startswith('https://'))

    def test_get_live_urls(self):
        result = itv.get_live_urls('itv')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        # assert live provides no subtitles
        self.assertIsNone(result[2])
        print(result)

    def test_get_catchup_urls(self):
        result = itv.get_catchup_urls('https://magni.itv.com/playlist/itvonline/ITV/10_0852_0001.001')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        print(result)

    def test_get_vtt_subtitles(self):
        # result = itv.get_catchup_urls('https://magni.itv.com/playlist/itvonline/ITV/10_0591_0001.002')
        # subtitles_url = result[2]
        # srt_file = itv.get_vtt_subtitles('https://itvpnpsubtitles.blue.content.itv.com/1-7665-0049-001/Subtitles/2/WebVTT-OUT-OF-BAND/1-7665-0049-001_Series1662044575_TX000000.vtt')
        # self.assertIsInstance(srt_file, str)
        # Doc Martin episode 1
        srt_file = itv.get_vtt_subtitles('https://itvpnpsubtitles.blue.content.itv.com/1-7665-0049-001/Subtitles/2/WebVTT-OUT-OF-BAND/1-7665-0049-001_Series1662044575_TX000000.vtt')
        self.assertIsInstance(srt_file, str)