
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
from unittest.mock import patch
import types
import time
import pytz

from test.support.testutils import open_json, open_doc, HttpResponse
from test.support.object_checks import has_keys, is_li_compatible_dict, is_url

from resources.lib import itvx, errors, cache

setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests



@patch('resources.lib.cache.set_item')
@patch('resources.lib.fetch.get_document', new=open_doc('html/index.html'))
class GetPageData(TestCase):
    @patch('resources.lib.cache.get_item', return_value="Cached data")
    def test_get_page_data(self, p_get_item, p_set_item):
        data = itvx.get_page_data('my/url')
        self.assertIsInstance(data, dict)
        p_get_item.assert_not_called()
        p_set_item.assert_not_called()

    @patch('resources.lib.cache.get_item', return_value="Cached data")
    def test_get_page_from_cache(self, p_get_item, p_set_item):
        url = 'some/url'
        data = itvx.get_page_data(url, 20)
        self.assertEqual("Cached data", data)
        full_url = "https://www.itv.com" + url
        p_get_item.assert_called_with(full_url)
        p_set_item.assert_not_called()

    @patch('resources.lib.cache.get_item', return_value=None)
    def test_get_page_from_empty_cache(self, p_get_item, p_set_item):
        url = 'some/url'
        data = itvx.get_page_data(url, 20)
        self.assertIsInstance(data, dict)
        full_url = "https://www.itv.com" + url
        p_get_item.assert_called_with(full_url)
        p_set_item.assert_called_with(full_url, data, 20)


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
            self.assertEqual('21:20', start_time)
        with patch('xbmc.getRegion', return_value='%I:%M %p'):
            schedule = itvx.get_now_next_schedule(local_tz=pytz.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('09:20 pm', start_time.lower())


class MainPageItem(TestCase):
    def test_list_main_page_items(self):
        page_data = open_json('html/index-data.json')
        with patch('resources.lib.itvx.get_page_data', return_value=page_data):
            items = list(itvx.main_page_items())
            items_count = len(items)
            self.assertEqual(9, items_count)
            for item in items:
                is_li_compatible_dict(self, item['show'])
        # Hero item of unknown type is disregarded.
        page_data['heroContent'][1]['contentType'] = 'someNewType'
        with patch('resources.lib.itvx.get_page_data', return_value=page_data):
            items = list(itvx.main_page_items())
            self.assertEqual(items_count - 1, len(items))

    def test_missing_or_empty_herocontent_field(self):
        with patch('resources.lib.itvx.get_page_data', return_value={}):
            items = list(itvx.main_page_items())
            self.assertListEqual([], items)

        with patch('resources.lib.itvx.get_page_data', return_value={'heroContent': None}):
            items = list(itvx.main_page_items())
            self.assertListEqual([], items)

        with patch('resources.lib.itvx.get_page_data', return_value={'heroContent': []}):
            items = list(itvx.main_page_items())
            self.assertListEqual([], items)


class Collections(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_collection_news(self, _):
        items = itvx.collection_content(slider='shortFormSliderContent')
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')
        items2 = itvx.collection_content(slider='shortFormSliderContent', hide_paid=True)
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_collection_trending(self, _):
        items = itvx.collection_content(slider='trendingSliderContent')
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')
        items2 = itvx.collection_content(slider='trendingSliderContent', hide_paid=True)
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_collection_from_main_page(self, _):
        items = itvx.collection_content(slider='editorialRailSlot1')
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')
        items2 = itvx.collection_content(slider='editorialRailSlot1', hide_paid=True)
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('json/editorial_slider.json'))
    def test_collection_from_test_rail(self, _):
        """Test a specially crafted slider with all possible types of items."""
        items = itvx.collection_content(slider='testRailSlot1')
        self.assertEqual(len(items), 8)
        for item in items:
            has_keys(item, 'playable', 'show')
        self.assertTrue(items[7]['type'] == 'collection')
        items2 = itvx.collection_content(slider='testRailSlot1', hide_paid=True)
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_non_existing_collection_from_main_page(self, _):
        items = itvx.collection_content(slider='SomeNonExistingSlider')
        self.assertListEqual([], items)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_just-in_data.json'))
    def test_collection_from_collection_page(self, _):
        items = itvx.collection_content(url='collection_top_picks')
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')
        items2 = list(itvx.collection_content(url='collection_top_picks', hide_paid=True))
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_itvx-kids.json'))
    def test_collection_from_collection_page_with_rails(self, _):
        items = itvx.collection_content(url='itvx_kids')
        self.assertGreater(len(items), 10)
        for item in items:
            has_keys(item, 'playable', 'show')

    @patch('resources.lib.itvx.get_page_data', side_effect=(open_json('html/collection_the-costume-collection.json'),
                                                            open_json('html/collection_the-costume-collection.json')))
    def test_collection_with_paid_items(self, _):
        # The costume collection has 18 show, 1 title, of which 3 are premium
        items = list(itvx.collection_content(url='the_costume_collection'))
        self.assertEqual(19, len(items))
        items = itvx.collection_content(url='the_costume_collection', hide_paid=True)
        self.assertEqual(16, len(items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_just-in_data.json'))
    @patch('resources.lib.parsex.parse_collection_item', return_value=None)
    def test_collection_with_invalid_items(self, _, __):
        """Items that fail to parse return None and must be filtered out in the final result."""
        items = itvx.collection_content(url='some/url')
        self.assertListEqual([], items)

class Categories(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/categories_data.json'))
    def test_get_categories(self, _):
        cat_list = list(itvx.categories())
        self.assertEqual(8, len(cat_list))

    @patch('resources.lib.itvx.get_page_data', side_effect=(open_json('html/category_children.json'),
                                                            open_json('html/category_drama-soaps.json'),
                                                            open_json('html/category_factual.json'),
                                                            open_json('html/category_sport.json')))
    def test_get_category_content(self, _):
        for idx in range(3):
            cache.purge()
            program_list = list(itvx.category_content('asdgf'))
            self.assertGreater(len(program_list), 10)
            playables = 0
            for progr in program_list:
                has_keys(progr['show'], 'label', 'info', 'art', 'params')
                if progr['playable']:
                    playables += 1

            if idx == 1 or idx == 3:
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

    def test_category_news(self):
        with patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_news.json')):
            sub_cat_list = list(itvx.category_news('zdfd'))
            self.assertGreater(len(sub_cat_list), 4)
            for item in sub_cat_list:
                is_li_compatible_dict(self, item)
        # THe object returned has no field newsData
        with patch('resources.lib.itvx.get_page_data', return_value={}):
            sub_cat_list = list(itvx.category_news('zdfd'))
            self.assertListEqual([], sub_cat_list)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_news.json'))
    def test_news_sub_categories(self, _):
        # Known subcategategories
        for sub_cat in (('heroAndLatestData', None), ('longformData', None),
                        ('curatedRails', 'Politics'), ('curatedRails', 'World'),
                        ('curatedRails', 'Special Reports'), ('curatedRails', 'News Explained')):
            items = itvx.category_news_content('my/url', *sub_cat)
            self.assertGreater(len(items), 4)
            for item in items:
                self.assertIsInstance(item['playable'], bool)
                is_li_compatible_dict(self, item['show'])

            if sub_cat[0] in ('heroAndLatestData','longformData'):
                free_items = itvx.category_news_content('my/url', *sub_cat, hide_paid=True)
                self.assertEqual(len(items), len(free_items))

        # Unknown subcategory and/or rail
        self.assertListEqual( [], itvx.category_news_content('my/url', 'SomeSubCat', None))
        self.assertListEqual( [], itvx.category_news_content('my/url', 'SomeSubCat', 'SomeRail'))
        self.assertListEqual( [], itvx.category_news_content('my/url', 'curatedRails', 'SomeRail'))


class Episodes(TestCase):
    @patch('resources.lib.fetch.get_document', new=open_doc('html/series_miss-marple.html'))
    def test_episodes_marple(self):
        series_listing = itvx.episodes('asd')
        self.assertIsInstance(series_listing, dict)
        self.assertEqual(len(series_listing), 6)

    @patch('resources.lib.fetch.get_document', return_value=open_doc('html/series_miss-marple.html')())
    def test_episodes_with_cache(self, p_fetch):
        series_listing = itvx.episodes('asd', use_cache=False)
        self.assertIsInstance(series_listing, dict)
        self.assertEqual(len(series_listing), 6)
        series_listing = itvx.episodes('asd', use_cache=True)
        self.assertIsInstance(series_listing, dict)
        self.assertEqual(len(series_listing), 6)
        p_fetch.assert_called_once()


class Search(TestCase):
    @patch('requests.sessions.Session.send', return_value=HttpResponse(text=open_doc('search/the_chase.json')()))
    def test_simple_search(self, _):
        result = itvx.search('the_chase')
        self.assertIsInstance(result, types.GeneratorType)
        self.assertEqual(10, len(list(result)))

    @patch('requests.sessions.Session.send', return_value=HttpResponse(204))
    def test_search_without_results(self, _):
        result = itvx.search('xprs')
        self.assertIsNone(result)


class GetPLaylistUrl(TestCase):
    @patch('resources.lib.fetch.get_document', new=open_doc('html/film_danny-collins.html'))
    def test_get_playlist_from_film_page(self):
        result = itvx.get_playlist_url_from_episode_page('page')
        self.assertTrue(is_url(result))

    @patch('resources.lib.fetch.get_document', new=open_doc('html/paid_episode_downton-abbey-s1e1.html'))
    def test_get_playlist_from_premium_episode(self):
        result = itvx.get_playlist_url_from_episode_page('page')
        self.assertTrue(is_url(result))

    @patch('resources.lib.itvx.get_page_data',
           return_value=open_json('html/special_how-to-catch-a-cat-killer_data.json'))
    def test_get_playlist_from_special_item(self, _):
        result = itvx.get_playlist_url_from_episode_page('page')
        self.assertTrue(is_url(result))