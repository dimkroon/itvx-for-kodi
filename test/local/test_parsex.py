# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import pytz

from test.support import fixtures
fixtures.global_setup()

import unittest

from support.testutils import open_doc, open_json
from support.object_checks import has_keys, is_url, is_li_compatible_dict
from resources.lib import parsex
from resources.lib import errors

setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class TestScrapeJson(unittest.TestCase):
    def test_scrape_json_watch_pages(self):
        for page in ('html/index.html', 'html/watch-itv1.html'):
            get_page = open_doc(page)
            data = parsex.scrape_json(get_page())
            self.assertIsInstance(data, dict)

    def test_invalid_page(self):
        # no __NEXT_DATA___
        self.assertRaises(errors.ParseError, parsex.scrape_json, '<html></html')
        # invalid json
        self.assertRaises(errors.ParseError, parsex.scrape_json,
                          '<script id="__NEXT_DATA__" type="application/json">{data=[1,2]}</script>')


class Generic(unittest.TestCase):
    def test_build_url(self):
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921', url)
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921', None)
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921', url)
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921', '10a2921a0001')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921/10a2921a0001', url)
        url = parsex.build_url('Astrid & Lily Save the World', '10a2921', '10a2921a0001')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921/10a2921a0001', url)
        url = parsex.build_url('#50/50-heroes?', '10a1511')
        self.assertEqual('https://www.itv.com/watch/5050-heroes/10a1511', url)
        url = parsex.build_url('Paul Sinha: Shout Out To My Ex', '10a3819')
        self.assertEqual('https://www.itv.com/watch/paul-sinha-shout-out-to-my-ex/10a3819', url)
        url = parsex.build_url("Watch Thursday's ITV Evening News", '10a3819')
        self.assertEqual('https://www.itv.com/watch/watch-thursdays-itv-evening-news/10a3819', url)

    def test_sort_title(self):
        self.assertEqual('my title', parsex.sort_title('My Title'))
        self.assertEqual('title', parsex.sort_title('The Title'))
        self.assertEqual('thetitle', parsex.sort_title('TheTitle'))

    def test_parse_hero(self):
        data = open_json('html/index-data.json')
        for item_data in data['heroContent']:
            obj = parsex.parse_hero_content(item_data)
            has_keys(obj, 'type', 'show')
            is_li_compatible_dict(self, obj['show'])
        # An item of unknown type
        item = data['heroContent'][0]
        item['contentType'] = 'some new type'
        self.assertIsNone(parsex.parse_hero_content(item))
        # Invalid item
        item = {'contentType': 'special', 'title': False}
        self.assertIsNone(parsex.parse_hero_content(item))

    def test_parse_slider(self):
        data = open_json('html/index-data.json')
        for item_name, item_data in data['editorialSliders'].items():
            obj = parsex.parse_slider(item_name, item_data)
            has_keys(obj, 'type', 'show')
            is_li_compatible_dict(self, obj['show'])

    def test_parse_collection_title(self):
        data = open_json('html/collection_just-in_data.json')['collection']['shows']
        # film - Valentine's Day
        item = parsex.parse_collection_item(data[2])
        has_keys(item, 'playable', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertIs(item['playable'], True)
        # series - The Twelve
        item = parsex.parse_collection_item(data[1])
        has_keys(item, 'playable', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertIs(item['playable'], False)
        # episode - Kavos Weekender
        item = parsex.parse_collection_item(data[3])
        has_keys(item, 'playable', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertIs(item['playable'], True)
        # Brand - Jonathan Ross' Must-Watch Films
        item = parsex.parse_collection_item(data[13])
        has_keys(item, 'playable', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertIs(item['playable'], False)
        # An invalid item
        item = parsex.parse_collection_item({})
        self.assertIsNone(item)

    def test_parse_collection_title_from_main_page(self):
        data = open_json('html/index-data.json')['editorialSliders']['editorialRailSlot1']['collection']['shows']
        item = parsex.parse_collection_item(data[0])
        has_keys(item, 'playable', 'show')
        is_li_compatible_dict(self, item['show'])

    def test_parse_news_collection_item(self):
        data = open_json('html/index-data.json')['shortFormSliderContent'][0]['items']
        tz_uk = pytz.timezone('Europe/London')
        # a short new item
        item = parsex.parse_news_collection_item(data[1], tz_uk, "%H-%M-%S")
        has_keys(item, 'playable', 'show')
        is_li_compatible_dict(self, item['show'])
        # NOTE: As of 20-7-23 all news collection item appear to have the same structure
        #       Just need to test a bit longer to be sure.
        # a new item like a normal catchup episode
        # item = parsex.parse_news_collection_item(data[-1], tz_uk, "%H-%M-%S")
        # has_keys(item, 'playable', 'show')
        # is_li_compatible_dict(self, item['show'])

        # An invalid item
        item = parsex.parse_news_collection_item({}, None, None)
        self.assertIsNone(item)


    def test_parse_trending_collection_item(self):
        data = open_json('html/index-data.json')['trendingSliderContent']['items']
        item = parsex.parse_trending_collection_item(data[1])
        has_keys(item, 'playable', 'show')
        is_li_compatible_dict(self, item['show'])
        # An invalid item
        item = parsex.parse_trending_collection_item({})
        self.assertIsNone(item)

    def test_parse_episode_title(self):
        data = open_json('html/series_miss-marple_data.json')
        item = parsex.parse_episode_title(data['seriesList'][0]['titles'][0])
        is_li_compatible_dict(self, item)

        # Episodes where field episodeTitle = None
        data = open_json('html/series_bad-girls_data.json')
        title_obj = data['seriesList'][6]['titles'][0]
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)

        # Episode where field seriesNumber is not a number, but 'other episodes'.
        data = open_json('html/series_midsummer-murders.json')
        series = data['seriesList'][-1]
        self.assertEqual('Other Episodes', series['seriesLabel'])
        title_obj = series['titles'][0]
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)

        # Paid episode
        title_obj['premium'] = True
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)
        self.assertTrue('premium' in item['info']['plot'].lower())

    def test_parse_search_result(self):
        # These files contain programmes, episodes, films and specials both and without a specialProgramm field.
        for file in ('search/search_results_mear.json', 'search/search_monday.json'):
            data = open_json(file)
            for result_item in data['results']:
                item = parsex.parse_search_result(result_item)
                has_keys(item, 'playable', 'show')
                is_li_compatible_dict(self, item['show'])

        # unknown entity type
        search_result = data['results'][0]
        search_result['entityType'] = 'dfgs'
        self.assertIsNone(parsex.parse_search_result(search_result))