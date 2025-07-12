# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
from unittest.mock import patch
from datetime import timezone
import types
import time

from test.support.testutils import open_json, open_doc, HttpResponse
from test.support.object_checks import has_keys, is_li_compatible_dict, is_url, is_not_empty

from resources.lib import itvx, errors, main, cache, utils, itv_account


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


def check_item(testcase, item):
    has_keys(item, 'type', 'show')
    testcase.assertTrue(item['type'] in main.callb_map.keys())
    is_li_compatible_dict(testcase, item['show'])


@patch('resources.lib.cache.set_item')
@patch('resources.lib.fetch.get_document', return_value=open_doc('html/index.html')())
class GetPageData(TestCase):
    @patch('resources.lib.cache.get_item', return_value="Cached data")
    def test_get_page_data(self, p_get_item, p_get_doc, p_set_item):
        data = itvx.get_page_data('/my/url')
        self.assertIsInstance(data, dict)
        p_get_item.assert_not_called()
        p_set_item.assert_not_called()
        p_get_doc.assert_called_with('https://www.itv.com/my/url')
        # full url with protocol
        p_get_doc.reset_mock()
        itvx.get_page_data('https://www.itv.com/my/url')
        p_get_doc.assert_called_with('https://www.itv.com/my/url')
        # with trailing space
        p_get_doc.reset_mock()
        itvx.get_page_data('/my/url ')
        p_get_doc.assert_called_with('https://www.itv.com/my/url')

    @patch('resources.lib.cache.get_item', return_value="Cached data")
    def test_get_page_from_cache(self, p_get_item, _, p_set_item):
        url = 'some/url'
        data = itvx.get_page_data(url, 20)
        self.assertEqual("Cached data", data)
        full_url = "https://www.itv.com" + url
        p_get_item.assert_called_with(full_url)
        p_set_item.assert_not_called()

    @patch('resources.lib.cache.get_item', return_value=None)
    def test_get_page_from_empty_cache(self, p_get_item, _, p_set_item):
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
        self.assertAlmostEqual(17, len(now_next), delta=3)
        for channel in now_next:
            has_keys(channel, 'name', 'channelType', 'streamUrl', 'images', 'slot')
            for programme in channel['slot']:
                has_keys(programme, 'programmeTitle', 'startTime', 'orig_start')

    @patch('xbmc.getRegion', return_value='%H:%M')
    def test_now_next_in_local_time(self, _):
        local_tz = utils.ZoneInfo('America/Fort_Nelson')
        schedule = itvx.get_now_next_schedule(local_tz=timezone.utc)
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
            schedule = itvx.get_now_next_schedule(local_tz=timezone.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('23:00', start_time)
        with patch('xbmc.getRegion', return_value='%I:%M %p'):
            schedule = itvx.get_now_next_schedule(local_tz=timezone.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('11:00 pm', start_time.lower())


class FullSchedule(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('schedule/html_schedule.json'))
    def test_full_schedule(self, _):
        schedules = itvx.get_full_schedule()
        self.assertIsInstance(schedules, dict)
        channels = ('ITV1', 'ITV2', 'ITVBe', 'ITV3', 'ITV4')
        has_keys(schedules, *channels)
        for progr_list in schedules.values():
            self.assertIsInstance(progr_list, list)
            self.assertGreater(len(progr_list), 100)


class MainPageItem(TestCase):
    def test_list_main_page_items(self):
        page_data = open_json('html/index-data.json')
        with patch('resources.lib.itvx.get_page_data', return_value=page_data):
            items = list(itvx.main_page_items())
            items_count = len(items)
            self.assertEqual(7, items_count)
            for item in items:
                check_item(self, item)
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
    def setUp(self):
        cache.purge()

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('json/index-data.json'))
    def test_collection_news(self, _):
        items = list(filter(None, itvx.collection_content(slider='newsShortForm')))
        self.assertEqual(3, len(items))
        for item in items:
            check_item(self, item)
        items2 = list(filter(None, itvx.collection_content(slider='newsShortForm', hide_paid=True)))
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('json/test_collection.json'))
    def test_collection_content_shortForm(self, _):
        """The contents of a shortForm slider on a collection page."""
        items = list(filter(None, itvx.collection_content(slider='shortFormSlider')))
        self.assertEqual(2, len(items))
        for item in items:
            check_item(self, item)
        items2 = list(filter(None, itvx.collection_content(slider='shortFormSlider', hide_paid=True)))
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_collection_trending(self, _):
        items = list(filter(None, itvx.collection_content(slider='trendingSliderContent')))
        self.assertGreater(len(items), 10)
        for item in items:
            check_item(self, item)
        items2 = list(filter(None, itvx.collection_content(slider='trendingSliderContent', hide_paid=True)))
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('json/index-data.json'))
    def test_collection_from_main_page(self, _):
        items = list(itvx.collection_content(url='https://www.itv.com', slider='editorial_rail_slot1'))
        self.assertEqual(4, len(items))
        for item in items:
            check_item(self, item)
        items2 = list(filter(None, itvx.collection_content(url='https://www.itv.com', slider='editorial_rail_slot1', hide_paid=True)))
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('json/editorial_slider.json'))
    def test_collection_from_test_rail(self, _):
        """Test a specially crafted slider with all possible types of items."""
        items = list(filter(None, itvx.collection_content('https://www.itv.com', slider='test_rail')))
        self.assertEqual(10, len(items))
        for item in items:
            check_item(self, item)
        self.assertEqual('simulcastspot', items[0]['type'])
        self.assertEqual('fastchannelspot', items[1]['type'])
        self.assertEqual('collection', items[8]['type'])
        self.assertEqual('collection', items[9]['type'])
        items2 = list(filter(None, itvx.collection_content('https://www.itv.com', slider='test_rail', hide_paid=True)))
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_just-in_data.json'))
    def test_collection_content_from_collection_page(self, _):
        items = list(itvx.collection_content(url='collection_top_picks'))
        self.assertGreater(len(items), 10)
        for item in items:
            check_item(self, item)
        items2 = list(itvx.collection_content(url='collection_top_picks', hide_paid=True))
        self.assertListEqual(items, items2)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('json/test_collection.json'))
    def test_editorial_slider_from_collection(self, _):
        items = list(itvx.collection_content(url='my_test_collection', slider='editorial_rail_slot2'))
        self.assertEqual(4, len(items))
        for item in items:
            check_item(self, item)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_non_existing_collection(self, _):
        items = list(filter(None, itvx.collection_content('https://www.itv.com', slider='SomeNonExistingSlider')))
        self.assertListEqual([], items)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_itvx-kids.json'))
    def test_collection_from_collection_page_with_rails(self, _):
        items = list(itvx.collection_content(url='itvx_kids'))
        self.assertGreater(len(items), 10)
        for item in items:
            check_item(self, item)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_itvx-fast.json'))
    def test_collection_of_live_fast_channels(self, _):
        items = list(itvx.collection_content(url='itvx_fast'))
        self.assertEqual(3, len(items))
        for item in items:
            check_item(self, item)

    def test_collection_with_shortform_slider(self):
        page_data = open_json('json/test_collection.json')
        page_data['collection'] = None
        page_data['editorialSliders'] = None
        with patch('resources.lib.itvx.get_page_data', return_value=page_data):
            items = list(itvx.collection_content(url='https://www.itvx_coll'))
            # 1 folder from the shortFormSlider
            self.assertEqual(1, len(items))
            for item in items:
                self.assertEqual('collection', item['type'])
                check_item(self, item)

    @patch('resources.lib.itvx.get_page_data', side_effect=(open_json('html/collection_the-costume-collection.json'),
                                                            open_json('html/collection_the-costume-collection.json')))
    def test_collection_with_paid_items(self, _):
        # The costume collection has 18 show, 1 title, of which 3 are premium
        items = list(itvx.collection_content(url='the_costume_collection'))
        self.assertEqual(19, len(items))
        items = list(filter(None, itvx.collection_content(url='the_costume_collection', hide_paid=True)))
        self.assertEqual(16, len(items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_just-in_data.json'))
    @patch('resources.lib.parsex.parse_collection_item', return_value=None)
    def test_collection_with_invalid_items(self, _, __):
        """Items that fail to parse return None and must be filtered out in the final result."""
        items = list(itvx.collection_content(url='some/url'))
        self.assertListEqual([None] * 15, items)


class Categories(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/categories_data.json'))
    def test_get_categories(self, _):
        cat_list = list(itvx.categories())
        self.assertEqual(9, len(cat_list))

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
                if progr['type'] in ('episode', 'special', 'title', 'film'):
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
            self.assertEqual('title', progr['type'])
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
                check_item(self, item)

            if sub_cat[0] in ('heroAndLatestData', 'longformData'):
                free_items = itvx.category_news_content('my/url', *sub_cat, hide_paid=True)
                self.assertEqual(len(items), len(free_items))

        # Unknown subcategory and/or rail
        self.assertListEqual([], itvx.category_news_content('my/url', 'SomeSubCat', None))
        self.assertListEqual([], itvx.category_news_content('my/url', 'SomeSubCat', 'SomeRail'))
        self.assertListEqual([], itvx.category_news_content('my/url', 'curatedRails', 'SomeRail'))


class Episodes(TestCase):
    @patch('resources.lib.fetch.get_document', new=open_doc('html/series_miss-marple.html'))
    def test_episodes_marple(self):
        series_listing, programme_id = itvx.episodes('asd')
        self.assertIsInstance(series_listing, dict)
        self.assertEqual(len(series_listing), 6)
        self.assertTrue(is_not_empty(programme_id, str))

    @patch('resources.lib.fetch.get_document', new=open_doc('html/paid_episode_downton-abbey-s1e1.html'))
    def test_paid_episodes(self):
        series_listing, programme_id = itvx.episodes('asd')
        self.assertIsInstance(series_listing, dict)
        self.assertEqual(7, len(series_listing))
        self.assertEqual(7, len(series_listing['1']['episodes']))
        self.assertTrue(is_not_empty(programme_id, str))

    @patch('resources.lib.fetch.get_document', return_value=open_doc('html/series_miss-marple.html')())
    def test_episodes_with_cache(self, _):
        series_listing1, programme_id1 = itvx.episodes('asd', use_cache=False)
        self.assertIsInstance(series_listing1, dict)
        self.assertEqual(len(series_listing1), 6)
        self.assertTrue(is_not_empty(programme_id1, str))
        series_listing2, programme_id2 = itvx.episodes('asd', use_cache=True)
        self.assertDictEqual(series_listing1, series_listing2)
        self.assertEqual(programme_id1, programme_id2)

    def test_missing_episodes_data(self):
        data = open_json('html/series_miss-marple_data.json')
        del data['seriesList']
        with patch('resources.lib.itvx.get_page_data', return_value=data):
            series_listing, programme_id = itvx.episodes('asd')
            self.assertFalse(is_not_empty(series_listing, dict))
            self.assertIsNone(programme_id)

    def test_merge_multiple_series_with_same_series_number(self):
        data = open_json('html/series_miss-marple_data.json')
        # Check we operate on the expected object.
        series_list = data['seriesList']
        self.assertEqual(series_list[1]['seriesNumber'], '2')
        num_episodes_series_2 = len(series_list[1]['titles'])
        self.assertEqual(series_list[2]['seriesNumber'], '3')
        num_episodes_series_3 = len(series_list[2]['titles'])
        # force a duplicate series number and check result
        series_list[2]['seriesNumber'] = '2'
        with patch('resources.lib.itvx.get_page_data', return_value=data):
            series_listing, programme_id = itvx.episodes('asd')
        self.assertEqual(len(series_listing['2']['episodes']), num_episodes_series_2 + num_episodes_series_3)


class Search(TestCase):
    @patch('requests.sessions.Session.send', return_value=HttpResponse(text=open_doc('search/test_results.json')()))
    def test_simple_search(self, _):
        result = itvx.search('the_chase')
        self.assertIsInstance(result, types.GeneratorType)
        self.assertEqual(8, len(list(result)))

    def test_search_without_results(self):
        """Currently, empty results seems to consistently return HTTP status 204, but
        keep testing all empty results observed in the past."""
        with patch('requests.sessions.Session.send', return_value=HttpResponse(204)):
            result = itvx.search('xprs')
            self.assertIsNone(result)
        with patch('requests.sessions.Session.send', return_value=HttpResponse(200, content=b'{"results": []}')):
            result = itvx.search('xprs')
            self.assertListEqual([], list(result))
        with patch('requests.sessions.Session.send', return_value=HttpResponse(200, content=b'no content')):
            result = itvx.search('xprs')
            self.assertIsNone(result)

    @patch('requests.sessions.Session.send', return_value=HttpResponse(text=open_doc('search/test_results.json')()))
    def test_search_hide_paid(self, _):
        results = list(itvx.search('blbl'))
        self.assertIsInstance(results[0], dict)
        results = list(itvx.search('blbl', hide_paid=True))
        self.assertIsNone(results[0])


class LastWatched(TestCase):
    def setUp(self):
        cache.purge()
        
    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('usercontent/last_watched_all.json'))
    def test_get_last_watched(self, patched_fetch):
        results = itvx.get_last_watched()
        self.assertIsInstance(results, list)     # requirement for paginator
        self.assertGreater(len(results), 0)
        for item in results:
            self.assertIsInstance(item, dict)
        patched_fetch.assert_called_once()
        # --- check cache ---
        results_cache = itvx.get_last_watched()
        self.assertListEqual(results, results_cache)
        patched_fetch.assert_called_once()     # fetch not called for the second time

    def test_get_last_watched_no_content(self):
        """All responses below have been observed in the wild"""
        with patch('resources.lib.itv_account.fetch_authenticated', return_value=[]):
            results = itvx.get_last_watched()
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 0)
        cache.purge()
        with patch('resources.lib.itv_account.fetch_authenticated', return_value=None):
            results = itvx.get_last_watched()
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 0)
        cache.purge()
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.ParseError):
            results = itvx.get_last_watched()
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 0)
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.HttpError):
            results = itvx.get_last_watched()
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 0)

    def test_get_resume_point(self):
        with patch('resources.lib.itv_account.fetch_authenticated',
                   return_value=open_json('usercontent/resume_point.json')):
            result = itvx.get_resume_point('aa')
            self.assertGreater(result, 0)
            self.assertIsInstance(result, float)
        # --- No resume point available, e.i. next episode ---
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.HttpError(404, 'not found')):
            # ITV returns HTTP status 404 when the programme has no resume point.
            result = itvx.get_resume_point('aa')
            self.assertIsNone(result)
        # --- Other HTTP error ---
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.HttpError(500, 'server error')):
            result = itvx.get_resume_point('aa')
            self.assertIsNone(result)
        # --- Other fetch error ---
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.FetchError):
            result = itvx.get_resume_point('aa')
            self.assertIsNone(result)
        # --- Invalid resume data ---
        with patch('resources.lib.itv_account.fetch_authenticated', return_value={'some': 'invalid data'}):
            result = itvx.get_resume_point('aa')
            self.assertIsNone(result)


class GetPLaylistUrl(TestCase):
    @patch('resources.lib.fetch.get_document', new=open_doc('html/film.html'))
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

    @patch('resources.lib.fetch.get_document', new=open_doc('html/news-short_item.html'))
    def test_get_playlist_from_news_shortform_item(self):
        result = itvx.get_playlist_url_from_episode_page('page')
        self.assertTrue(is_url(result))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_stonehouse-bsl.json'))
    def test_get_playlist_from_signed_programme(self, _):
        result = itvx.get_playlist_url_from_episode_page('page')
        self.assertTrue(is_url(result))
        bsl_result = itvx.get_playlist_url_from_episode_page('page', prefer_bsl=True)
        self.assertTrue(is_url(result))
        self.assertNotEqual(result, bsl_result)


class GetMyList(TestCase):
    def setUp(self):
        cache.purge()

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    def test_get_mylist(self, p_fetch):
        result_1 = itvx.my_list('156-45xsghf75-4sf569')
        self.assertEqual(len(list(result_1)), 4)
        for item in result_1:
            is_li_compatible_dict(self, item['show'])
        p_fetch.assert_called_once()
        # second call should be fetched from cache
        result_2 = itvx.my_list('156-45xsghf75-4sf569')
        p_fetch.assert_called_once()
        self.assertListEqual(result_1, result_2)

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=None)
    def test_get_empty_mylist(self, p_fetch):
        result_1 = itvx.my_list('156-45xsghf75-4sf569')
        self.assertListEqual(result_1, [])
        p_fetch.assert_called_once()

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    @patch('resources.lib.parsex.parse_my_list_item', return_value=None)
    def test_get_mylist_with_parse_errors(self, _, __):
        """Simulate parse errors and the parser returning None"""
        result = itvx.my_list('156-45xsghf75-4sf569')
        self.assertListEqual(result, [])

    @patch('resources.lib.itv_account.fetch_authenticated', side_effect=SystemExit)
    def test_get_mylist_not_signed_in(self, _):
        self.assertRaises(SystemExit, itvx.my_list, '156-45xsghf75-4sf569')

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    def test_get_my_list_cache_not_used_after_user_change(self, p_fetch):
        itvx.my_list('156-45xsghf75-4sf569')
        p_fetch.assert_called_once()
        # Check cache is not used with another user ID
        p_fetch.reset_mock()
        itvx.my_list('xxx')
        p_fetch.assert_called_once()

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    def test_add_mylist_item(self, p_fetch):
        result = itvx.my_list('156-45xsghf75-4sf569', '10_3408', 'add')
        self.assertEqual(len(list(result)), 4)
        for item in result:
            is_li_compatible_dict(self, item['show'])
        p_fetch.assert_called_once()

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    def test_remove_mylist_item(self, p_delete):
        result = itvx.my_list('156-45xsghf75-4sf569', '10_3408', 'remove')
        self.assertEqual(len(list(result)), 4)
        for item in result:
            is_li_compatible_dict(self, item['show'])
        p_delete.assert_called_once()


class InitialiseMyList(TestCase):
    def setUp(self):
        cache.purge()

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    def test_initialise_my_list(self, _):
        itvx.initialise_my_list()

    def test_initialise_my_list_not_logged_in(self):
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.AuthenticationError):
            itvx.initialise_my_list()
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.AccessRestrictedError):
            itvx.initialise_my_list()
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.FetchError):
            itvx.initialise_my_list()
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=SystemExit):
            self.assertRaises(SystemExit, itvx.initialise_my_list)


class Recommendations(TestCase):
    @classmethod
    def setUpClass(cls):
        itv_account.itv_session()

    def setUp(self):
        cache.purge()

    @patch('resources.lib.fetch.get_json', return_value=open_json('usercontent/byw.json'))
    def test_because_you_watched(self, p_fetch):
        res1 = itvx.because_you_watched('my_user_id')
        self.assertIsInstance(res1, list)
        self.assertEqual(12, len(res1))
        p_fetch.assert_called_once()
        for item in res1:
            has_keys(item, 'programme_id', 'type', 'show')
            is_li_compatible_dict(self, item['show'])
        # test second call gets from cache
        res2 = itvx.because_you_watched('my_user_id')
        p_fetch.assert_called_once()
        self.assertListEqual(res1, res2)
        # Other user ID not from cache
        p_fetch.reset_mock()
        itvx.because_you_watched('other_user_id')
        p_fetch.assert_called_once()
        # Filter paid
        res3 = itvx.because_you_watched('my_user_id', hide_paid=True)
        self.assertEqual(11, len(res3))

        # not logged in
        res1 = itvx.because_you_watched('')
        self.assertIs(res1, None)

    @patch('resources.lib.fetch.get_json', return_value=open_json('usercontent/byw.json'))
    def test_byw_name_only(self, p_fetch):
        res1 = itvx.because_you_watched('my_user_id', name_only=True)
        p_fetch.assert_called_once()
        self.assertEqual('Van Der Valk (Original)', res1)
        # from cache
        res2 = itvx.because_you_watched('my_user_id', name_only=True)
        p_fetch.assert_called_once()
        self.assertEqual(res2, res1)
        # Other user ID not from cache
        p_fetch.reset_mock()
        itvx.because_you_watched('other_user_id', name_only=True)
        p_fetch.assert_called_once()
        # not logged in
        res1 = itvx.because_you_watched('')
        self.assertIs(res1, None)

    @patch('resources.lib.fetch.get_json', return_value=None)
    def test_byw_fetch_errors(self, p_fetch):
        res = itvx.because_you_watched('my_user_id')
        p_fetch.assert_called_once()
        self.assertIs(res, None)
        p_fetch.reset_mock()
        res = itvx.because_you_watched('my_user_id', name_only=True)
        p_fetch.assert_called_once()
        self.assertIs(res, None)

    @patch('resources.lib.fetch.get_json', return_value=open_json('usercontent/recommended.json'))
    def test_recommended(self, p_fetch):
        res1 = itvx.recommended('my_user_id')
        self.assertIsInstance(res1, list)
        self.assertEqual(12, len(res1))
        p_fetch.assert_called_once()
        for item in res1:
            has_keys(item, 'programme_id', 'type', 'show')
            is_li_compatible_dict(self, item['show'])
        # test second call gets from cache
        res2 = itvx.recommended('my_user_id')
        p_fetch.assert_called_once()
        self.assertListEqual(res1, res2)
        # Other user ID not from cache
        p_fetch.reset_mock()
        itvx.recommended('other_user_id')
        p_fetch.assert_called_once()
        # Filter paid
        res3 = itvx.recommended('my_user_id', hide_paid=True)
        self.assertEqual(1, len(res1) - len(res3))
        # not logged in - just returns data as normal.
        p_fetch.reset_mock()
        res4 = itvx.recommended('')
        p_fetch.assert_called_once()
        self.assertListEqual(res1, res4)

    @patch('resources.lib.fetch.get_json', return_value=None)
    def test_recommended_fetch_errors(self, p_fetch):
        res = itvx.recommended('my_user_id')
        p_fetch.assert_called_once()
        self.assertIs(res, None)


@patch.object(itv_account.itv_session(), 'account_data', {'refreshed': time.time(), 'itv_session': {'access_token': 'abc'}, 'cookies': {'asdfg':'defg'}})
@patch('resources.lib.fetch.post_json')
class RequestStreamData(TestCase):
    def test_request_live_default(self, p_post):
        itvx._request_stream_data('some/url')
        post_dta = p_post.call_args.kwargs['data']
        self.assertEqual('dotcom', post_dta['variantAvailability']['platformTag'])

    def test_request_live_full_hd(self, p_post):
        itvx._request_stream_data('some/url', full_hd=True)
        post_dta = p_post.call_args.kwargs['data']
        self.assertEqual('ctv', post_dta['variantAvailability']['platformTag'])

    def test_request_vod_default(self, p_post):
        itvx._request_stream_data('some/url', stream_type='vod')
        post_dta = p_post.call_args.kwargs['data']
        self.assertEqual('dotcom', post_dta['variantAvailability']['platformTag'])

    def test_request_vod_full_hd(self, p_post):
        itvx._request_stream_data('some/url', stream_type='vod', full_hd=True)
        post_dta = p_post.call_args.kwargs['data']
        self.assertEqual('ctv', post_dta['variantAvailability']['platformTag'])

    def test_request_with_auth_failure(self, _):
        with patch.object(itv_account.itv_session(), 'account_data', {}):
            with self.assertRaises(SystemExit) as cm:
                itvx._request_stream_data('some/url')
            self.assertEqual(1, cm.exception.code)