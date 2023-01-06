
# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
from unittest.mock import patch
import types
import time
import pytz

from test.support.testutils import open_json, open_doc
from test.support.object_checks import has_keys, is_li_compatible_dict, is_url

from resources.lib import itvx, errors

setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


@patch('resources.lib.fetch.get_json', new=lambda *a, **k: open_json('schedule/now_next.json'))
class NowNextSchedule(TestCase):
    def test_get_now_next_schedule(self):
        now_next = itvx.get_now_next_schedule()
        self.assertAlmostEqual(25, len(now_next), delta=3)
        for channel in now_next:
            has_keys(channel, 'name', 'channelType', 'streamUrl', 'images', 'slot')
            for programme in channel['slot']:
                has_keys(programme, 'programmeTitle', 'startTime', 'orig_start')

    @patch('xbmc.getRegion', return_value='%H:%M')
    def test_now_next_in_local_time(self, _):
        local_tz = pytz.timezone('America/Fort_Nelson')
        schedule = itvx.get_now_next_schedule(local_tz=pytz.utc)
        utc_times = [item['startTime'] for item in schedule[0]['slot']]
        schedule = itvx.get_now_next_schedule(local_tz=local_tz)
        ca_times = [item['startTime'] for item in schedule[0]['slot']]
        for utc, ca in zip(utc_times, ca_times):
            time_dif = time.strptime(utc, '%H:%M').tm_hour - time.strptime(ca, '%H:%M').tm_hour
            if time_dif > 0:
                self.assertEqual(7, time_dif)
            else:
                self.assertEqual(-17, time_dif)

    def test_now_next_in_system_time_format(self):
        with patch('xbmc.getRegion', return_value='%H:%M'):
            schedule = itvx.get_now_next_schedule(local_tz=pytz.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('22:30', start_time)
        with patch('xbmc.getRegion', return_value='%I:%M %p'):
            schedule = itvx.get_now_next_schedule(local_tz=pytz.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('10:30 pm', start_time.lower())


class MainPageItem(TestCase):
    @patch('resources.lib.fetch.get_document', new=open_doc('html/index.html'))
    def test_list_main_page_items(self):
        items = list(itvx.main_page_items())
        self.assertGreater(len(items), 6)
        for item in items:
            is_li_compatible_dict(self, item['show'])


class Collections(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_collection_news(self, _):
        items = list(itvx.collection_content(slider='newsShortformSliderContent'))
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_collection_trending(self, _):
        items = list(itvx.collection_content(slider='trendingSliderContent'))
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_collection_from_main_page(self, _):
        items = list(itvx.collection_content(slider='editorialRailSlot1'))
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_just-in_data.json'))
    def test_collection_from_collection_page(self, _):
        items = list(itvx.collection_content(url='collection_top_picks'))
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')

    @patch('resources.lib.itvx.get_page_data', side_effect=(open_json('html/collection_the-costume-collection.json'),
                                                            open_json('html/collection_the-costume-collection.json')))
    def test_collection_with_paid_items(self, _):
        # The costume collection has 18 show, 1 title, of which 3 are premium
        items = list(itvx.collection_content(url='the_costume_collection'))
        self.assertEqual(19, len(items))
        items = list(itvx.collection_content(url='the_costume_collection', hide_paid=True))
        self.assertEqual(16, len(items))


class Categories(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/categories_data.json'))
    def test_get_categories(self, _):
        cat_list = list(itvx.categories())
        self.assertEqual(8, len(cat_list))

    @patch('resources.lib.itvx.get_page_data', side_effect=(open_json('html/category_children.json'),
                                                            open_json('html/category_drama-soaps.json'),
                                                            open_json('html/category_factual.json')))
    def test_get_category_content(self, _):
        for _ in range(3):
            program_list = list(itvx.category_content('asdgf'))
            self.assertGreater(len(program_list), 10)
            playables = 0
            for progr in program_list:
                has_keys(progr['show'], 'label', 'info', 'art', 'params')
                if progr['playable']:
                    playables += 1
            self.assertGreater(playables, 0)
            self.assertLess(playables, len(program_list) / 2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_films.json'))
    def test_category_films(self, _):
        program_list = list(itvx.category_content('asdgf'))
        self.assertGreater(len(program_list), 10)
        for progr in program_list:
            has_keys(progr['show'], 'label', 'info', 'art', 'params')
            self.assertTrue(progr['playable'])
        free_list = list(itvx.category_content('asdgf', hide_paid=True))
        self.assertLess(len(free_list), len(program_list))


class Episodes(TestCase):
    @patch('resources.lib.fetch.get_document', new=open_doc('html/series_miss-marple.html'))
    def test_episodes_marple(self):
        series_listing = itvx.episodes('asd')
        self.assertIsInstance(series_listing, dict)
        self.assertEqual(len(series_listing), 6)


class Search(TestCase):
    @patch('resources.lib.fetch.get_json', return_value=open_json('search/the_chase.json'))
    def test_simple_search(self, _):
        result = itvx.search('the_chase')
        self.assertIsInstance(result, types.GeneratorType)
        self.assertEqual(10, len(list(result)))

    @patch('resources.lib.fetch.get_json', return_value=None)
    def test_search_without_results(self, _):
        result = itvx.search('xprs')
        self.assertIsNone(result)


class GetPLaylistUrl(TestCase):
    @patch('resources.lib.fetch.get_document', new=open_doc('html/film_love-actually.html'))
    def test_get_playlist_from_film_page(self):
        result = itvx.get_playlist_url_from_episode_page('page')
        self.assertTrue(is_url(result))

    @patch('resources.lib.fetch.get_document', new=open_doc('html/episode_marple_s6e3.html'))
    def test_get_playlist_from_episode_page(self):
        result = itvx.get_playlist_url_from_episode_page('page')
        self.assertTrue(is_url(result))

    @patch('resources.lib.fetch.get_document', new=open_doc('html/paid_episode_downton-abbey-s1e1.html'))
    def test_get_playlist_from_premium_episode(self):
        self.assertRaises(errors.AccessRestrictedError, itvx.get_playlist_url_from_episode_page, 'page')
