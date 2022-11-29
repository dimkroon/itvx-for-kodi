
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#
#  This file is part of plugin.video.itvhub
#
#  Plugin.video.itvhub is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or (at your
#  option) any later version.
#
#  Plugin.video.itvhub is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#  or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  plugin.video.itvhub. If not, see <https://www.gnu.org/licenses/>.

from test.support import fixtures
fixtures.global_setup()

import os
import json
import unittest
from unittest.mock import patch

import typing

from resources.lib import itv, fetch, itv_account
from codequick import Listitem, Route, Script


setUpModule = fixtures.setup_web_test


@Route.register()
def dummycallback():
    pass


class TestItv(unittest.TestCase):
    def test_get_categories(self):
        result = itv.categories()
        self.assertIsInstance(result, typing.Generator)
        for item in result:
            assert('label' in item.keys())
            assert('params') in item.keys()
            assert('id') in item['params'].keys()

    def test_get_category_films(self):
        result = itv.get_category_films()
        print(result)

    def test_category_content(self):
        result = itv.category_content('SPORT')
        self.assertIsInstance(result, list)

    def test_all_categories_content(self):
        categories = itv.categories()
        for cat in categories:
            result = itv.category_content(cat['params']['id'])
            print(result)

    def test_get_live_schedule(self):
        result = itv.get_live_schedule()
        print(json.dumps(result, indent=4))

    def test_get_live_channels(self):
        chan_list = list(itv.get_live_channels())
        for item in chan_list:
            self.assertIsInstance(item, dict)

    def test_get_programmes(self):
        # get all shows
        result = itv.programmes('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay&sortBy=title')
        self.assertIsInstance(result, list)
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
        self.assertEqual('', name)
        self.assertTrue(url.startswith('https://'))

    def test_get_live_urls(self):
        result = itv.get_live_urls('itv')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        # assert live provides no subtitles
        self.assertIsNone(result[2])
        print(result)

    def test_get_catchup_urls(self):
        urls = (
            # something else with subtitles:
            'https://magni.itv.com/playlist/itvonline/ITV/10_0852_0001.001', )
        for url in urls:
            result = itv.get_catchup_urls(url)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)
            # print(result)

    def test_get_vtt_subtitles(self):
        # result = itv.get_catchup_urls('https://magni.itv.com/playlist/itvonline/ITV/10_0591_0001.002')
        # subtitles_url = result[2]
        # srt_file = itv.get_vtt_subtitles('https://itvpnpsubtitles.blue.content.itv.com/1-7665-0049-001/Subtitles/2/WebVTT-OUT-OF-BAND/1-7665-0049-001_Series1662044575_TX000000.vtt')
        # self.assertIsInstance(srt_file, str)
        # Doc Martin episode 1
        srt_file = itv.get_vtt_subtitles('https://itvpnpsubtitles.blue.content.itv.com/1-7665-0049-001/Subtitles/2/WebVTT-OUT-OF-BAND/1-7665-0049-001_Series1662044575_TX000000.vtt')
        self.assertIsNone(srt_file)
        with patch.object(itv.Script, 'setting', new={'subtitles_show': 'true', 'subtitles_color': 'true'}):
            srt_file = itv.get_vtt_subtitles('https://itvpnpsubtitles.blue.content.itv.com/1-7665-0049-001/Subtitles/2/WebVTT-OUT-OF-BAND/1-7665-0049-001_Series1662044575_TX000000.vtt')
            self.assertIsInstance(srt_file, typing.Tuple)
            self.assertIsInstance(srt_file[0], str)
