# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
import xbmcgui

from test.support import fixtures
fixtures.global_setup()

import types
import json

from unittest import TestCase
from unittest.mock import patch

from codequick import Listitem
from xbmcgui import ListItem as XbmcListItem

from test.support.testutils import open_json, open_doc, HttpResponse
from test.support import object_checks

from resources.lib import main
from resources.lib import errors
from resources.lib import cache
from resources.lib import itv_account


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class Paginator(TestCase):
    def test_paginate_empty_list(self):
        pg = main.Paginator([], filter_char=None, page_nr=0)
        result = list(pg)
        self.assertListEqual([], result)


@patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
class MainMenu(TestCase):
    def test_main_menu(self, _):
        items = list(main.root.test())
        self.assertGreater(len(items), 10)
        for item in items:
            self.assertIsInstance(item, Listitem)


class LiveChannels(TestCase):
    @patch('resources.lib.fetch.get_json', side_effect=(open_json('schedule/now_next.json'),
                                                        open_json('schedule/live_4hrs.json')))
    @patch('resources.lib.kodi_utils.get_system_setting', return_value='America/Regina')
    def test_list_live_channels(self, _, mocked_get_json):
        cache.purge()
        chans = main.sub_menu_live.test()
        self.assertIsInstance(chans, list)
        chan_list = list(chans)
        self.assertGreaterEqual(len(chan_list), 10)
        self.assertEqual(2, mocked_get_json.call_count)
        # Next call is from cache
        main.sub_menu_live.test()
        self.assertEqual(2, mocked_get_json.call_count)

    @patch('resources.lib.fetch.get_json', side_effect=(open_json('schedule/now_next.json'),
                                                        open_json('schedule/live_4hrs.json')))
    @patch('resources.lib.kodi_utils.get_system_setting', side_effect=ValueError)
    def test_list_live_channels_no_tz_settings(self, _, mocked_get_json):
        cache.purge()
        chans = main.sub_menu_live.test()
        self.assertIsInstance(chans, list)


class Collections(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_get_collections(self, _):
        coll = main.list_collections.test()
        self.assertAlmostEqual(20, len(coll), delta=5)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_get_collection_news(self, _):
        shows = list(filter(None, main.list_collection_content.test(slider='shortFormSliderContent')))
        self.assertGreater(len(shows), 10)
        for item in shows:
            self.assertIsInstance(item, Listitem)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_get_collection_trending(self, _):
        shows = list(filter(None, main.list_collection_content.test(slider='trendingSliderContent')))
        self.assertGreater(len(shows), 10)
        for item in shows:
            self.assertIsInstance(item, Listitem)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_just-in_data.json'))
    def test_get_collection_from_collection_page(self, _):
        shows = list(filter(None, main.list_collection_content.test(url='top-picks')))
        self.assertGreater(len(shows), 10)
        for item in shows:
            self.assertIsInstance(item, Listitem)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_itvx-kids.json'))
    def test_get_collection_from_collection_page_with_rails(self, _):
        shows = list(filter(None, main.list_collection_content.test(url='itvs-kids')))
        self.assertGreater(len(shows), 10)
        for item in shows:
            self.assertIsInstance(item, Listitem)


class Categories(TestCase):
    def tearDown(self) -> None:
        cache.purge()

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/categories_data.json'))
    def test_get_categories(self, _):
        cats = main.list_categories.test()
        self.assertAlmostEqual(len(cats), 8, delta=2)
        for cat in cats:
            self.assertIsInstance(cat, Listitem)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_drama-soaps.json'))
    def test_get_category_drama(self, _):
        programmes = main.list_category.test('sdfg')
        self.assertGreater(len(programmes), 100)
        for prog in programmes:
            self.assertIsInstance(prog, (Listitem, type(None)))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_children.json'))
    def test_get_category_children_paginated(self, _):
        """Category with 65 programmes."""
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(0, 35) * 2):  # no a-z, page length = 30
            programmes = list(filter(None, main.list_category.test('sdfg')))
            self.assertEqual(36, len(programmes))
            programmes = list(filter(None, main.list_category.test('sdfg', page_nr=1)))
            self.assertEqual(30, len(programmes))
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(0, 60)):  # no a-z, page length = 55
            # content must be more than 5 longer than page length before actual pagination is performed.
            programmes = list(filter(None, main.list_category.test('sdfg')))
            self.assertEqual(65, len(programmes))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_children.json'))
    def test_category_children_az_list(self, _):
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(20, 0)):  # a-z on 20 items, page length=0
            programmes = list(filter(None, main.list_category.test('sdfg')))
            self.assertEqual(21, len(programmes))
            self.assertEqual('A', programmes[0].label)
            self.assertEqual('A', programmes[0].params['filter_char'])

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_drama-soaps.json'))
    def test_category_drama_list_by_character(self, _):
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(20, 0) * 2):  # a-z on 20 items, page length=0
            programmes = list(filter(None, main.list_category.test('sdfg', filter_char='A')))
            self.assertEqual(31, len(programmes))
            programmes = list(filter(None, main.list_category.test('sdfg', filter_char='0-9')))
            self.assertEqual(2, len(programmes))
        # Test content of 'A' divided in sub-pages
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(20, 6)*3):  # a-z on 20 items, page length=6
            programmes = list(filter(None, main.list_category.test('sdfg', filter_char='A')))
            self.assertEqual(7, len(programmes))
            programmes = list(filter(None, main.list_category.test('sdfg', filter_char='A', page_nr=4)))
            # Categories 'A' has 31 items
            self.assertEqual(7, len(programmes))  # The remaining item of the last page is added to this one.

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_news.json'))
    def test_category_news(self, _):
        """News now returns a list of sub categories."""
        items = main.list_category.test('category/news')
        self.assertIsInstance(items, list)
        self.assertEqual(7, len(items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_news.json'))
    def test_sub_category_news_hero_items(self, _):
        items = main.list_news_sub_category.test('my/url', 'heroAndLatestData', None)
        self.assertIsInstance(items, list)
        self.assertEqual(13, len(items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_news.json'))
    def test_sub_category_news_long_format_items(self, _):
        """These are in fact the tv shows in the category news."""
        items = main.list_news_sub_category.test('my/url', 'longformData', None)
        self.assertIsInstance(items, list)
        self.assertEqual(10, len(items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_news.json'))
    def test_sub_category_news_rails(self, _):
        """Very much the same as collection news, but divided in various sub categories."""
        items = main.list_news_sub_category.test('my/url', 'curatedRails', 'Politics')
        self.assertIsInstance(items, list)
        self.assertEqual(12, len(items))


@patch("resources.lib.cache.get_item", new=lambda *a, **k: None)     # disable cache
class Productions(TestCase):
    @patch("resources.lib.itvx.episodes", return_value=[])
    def test_empty_productions_list(self, _):
        result = main.list_productions.test('/some/url')
        self.assertIs(result, False)

    def test_no_url_passed(self):
        result = main.list_productions.test()
        self.assertIs(False, result)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_miss-marple_data.json'))
    def test_episodes_marple(self, _):
        list_items = main.list_productions.test('some/url/to/marple')
        self.assertIsInstance(list_items, list)
        self.assertEqual(6, len(list_items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_miss-marple_data.json'))
    def test_episodes_marple_series_4(self, _):
        """Test listing opened at series 4"""
        list_items = main.list_productions.test('some/url/to/marple', series_idx=4)
        self.assertIsInstance(list_items, list)
        self.assertEqual(4, len(list_items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_midsummer-murders.json'))
    def test_episodes_midsummer_murders_series_other_episodes(self, _):
        """Test listing opened at the non-integer seriesNUmber 'other episodes'."""
        list_items = main.list_productions.test('/some/url//to/midsumer', series_idx='other-episodes')
        self.assertIsInstance(list_items, list)
        self.assertEqual(1, len(list_items))      # 22 series, 1 episode

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_midsummer-murders.json'))
    def test_episodes_midsummer_murders_series_4(self, _):
        """Midsummer murder has 2 different series numbered series-4. These should be merged into one"""
        list_items = main.list_productions.test('some/url/to/midsumer', series_idx=4)
        self.assertIsInstance(list_items, list)
        self.assertEqual(6, len(list_items))      # 22 series, 5 episode in series 4-1, 1 episode in series 4-2

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_bad-girls_data.json'))
    def test_episodes_bad_girls_series_5(self, _):
        """Test listing opened at series 4"""
        list_items = main.list_productions.test('some/url/to/bad girls', series_idx=5)
        self.assertIsInstance(list_items, list)
        self.assertEqual(16, len(list_items))

    def test_episode_of_show_with_only_one_series(self):
        data = open_json('html/series_miss-marple_data.json')
        series = data['title']['brand']['series']
        # Remove all but the first series
        while len(series) > 1:
            series.pop()
        with patch('resources.lib.itvx.get_page_data', return_value=data):
            series_listing = main.list_productions.test('asd')
            self.assertEqual(4, len(series_listing))
            # Check if all items are playable
            for episode in series_listing:
                self.assertIs(episode.path, main.play_stream_catchup.route)


class Search(TestCase):
    @patch('requests.sessions.Session.send',
           return_value=HttpResponse(text=open_doc('search/the_chase.json')()))
    def test_search_the_chase(self, _):
        results = main.do_search.test('the chase')
        self.assertEqual(10, len(results))
        self.assertIs(results[0].path, main.list_productions.route)     # programme
        self.assertIs(results[4].path, main.play_title.route)           # special with field specialProgramme

    @patch('requests.sessions.Session.send',
           return_value=HttpResponse(text=open_doc('search/search_results_mear.json')()))
    def test_search_mear(self, _):
        results = main.do_search.test('mear')
        self.assertEqual(10, len(results))
        self.assertIs(results[0].path, main.list_productions.route)     # programme
        self.assertIs(results[4].path, main.play_title.route)           # film

    @patch('requests.sessions.Session.send',
           return_value=HttpResponse(text=open_doc('search/search_monday.json')()))
    def test_search_monday(self, _):
        results = main.do_search.test('monday')
        self.assertEqual(7, len(results))
        self.assertIs(results[0].path, main.list_productions.route)
        self.assertIs(results[6].path, main.play_title.route)           # special without field specialProgramme

    def test_search_result_with_unknown_entitytype(self):
        search_data = open_json('search/search_results_mear.json')
        with patch('requests.sessions.Session.send', return_value=HttpResponse(text=json.dumps(search_data))):
            results_1 = main.do_search.test('kjhbn')
            self.assertEqual(10, len(results_1))
        # check again with one item having an unknown entity type
        search_data['results'][3]['entityType'] = 'video'
        with patch('requests.sessions.Session.send', return_value=HttpResponse(text=json.dumps(search_data))):
            results_2 = main.do_search.test('kjhbn')
            self.assertEqual(9, len(results_2))

    @patch('requests.sessions.Session.send', return_value=HttpResponse(204))
    def test_search_with_no_results(self, _):
        results = main.do_search.test('the chase')
        self.assertIs(results, False)


class PlayStreamLive(TestCase):
    @patch('resources.lib.itv._request_stream_data', return_value=open_json('playlists/pl_itv1.json'))
    @patch('requests.get', return_value=HttpResponse())
    @patch('resources.lib.itv_account.ItvSession.refresh', return_value=True)
    @patch('resources.lib.itv_account.ItvSession.cookie', new={'Itv.Session': 'blabla'})
    def test_play_live_by_channel_name(self, _, __, p_req_strm):
        result = main.play_stream_live.test(channel='ITV', url=None)
        self.assertIsInstance(result, XbmcListItem)
        self.assertEqual('ITV', result.getLabel())
        self.assertFalse('IsPlayable' in result._props)
        # Assert channel name is converted to a full url
        self.assertEqual(1, len(p_req_strm.call_args_list))
        self.assertTrue(object_checks.is_url(p_req_strm.call_args_list[0], '/ITV'))

    @patch('resources.lib.fetch.post_json', return_value=open_json('playlists/pl_itv1.json'))
    def test_play_stream_live_without_credentials(self, _):
        itv_account.itv_session().log_out()
        itv_account._itv_session_obj = None
        result = main.play_stream_live.test(channel='ITV', url=None)
        self.assertFalse(result)


class PlayStreamCatchup(TestCase):
    def setUp(self) -> None:
        itv_account._itv_session_obj = None

    @classmethod
    def tearDownClass(cls) -> None:
        # Ensure to clear patched session objects
        itv_account._itv_session_obj = None

    @patch('resources.lib.itv._request_stream_data', return_value=open_json('playlists/pl_news_short.json'))
    def test_play_short_news_item(self, _):
        result = main.play_stream_catchup.test('some/url', 'a short news item')
        self.assertIsInstance(result, XbmcListItem)

    @patch('resources.lib.itv._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('requests.get', return_value=HttpResponse())
    @patch('resources.lib.itv_account.ItvSession.cookie', new={'Itv.Session': ''})
    def test_play_episode(self, _, __):
        result = main.play_stream_catchup.test('some/url', 'my episode')
        self.assertIsInstance(result, XbmcListItem)
        self.assertEqual('my episode', result.getLabel())
        self.assertEqual('my episode', result._info['video']['title'])
        with self.assertRaises(KeyError):
            result._info['video']['plot']
        self.assertFalse('IsPlayable' in result._props)
        self.assertRaises(AttributeError, getattr, result, '_subtitles')

    @patch('resources.lib.itv._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('requests.get', return_value=HttpResponse())
    @patch('resources.lib.itv_account.ItvSession.cookie', new={'Itv.Session': ''})
    def test_play_episode_without_title(self, _, __):
        result = main.play_stream_catchup.test('some/url', '')
        self.assertIsInstance(result, XbmcListItem)
        self.assertEqual('', result.getLabel())
        with self.assertRaises(KeyError):
            result._info['video']['title']

    @patch('resources.lib.itv._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('resources.lib.main.create_dash_stream_item', return_value=xbmcgui.ListItem())
    @patch('resources.lib.itv.get_vtt_subtitles', return_value=('my/subs.file', ))
    def test_play_episode_with_subtitles(self, _, __, ___):
        result = main.play_stream_catchup.test('some/url', 'my episode')
        self.assertEqual(len(result._subtitles), 1)

    @patch('resources.lib.itv._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('resources.lib.main.create_dash_stream_item', return_value=xbmcgui.ListItem())
    @patch('resources.lib.itv.get_vtt_subtitles', return_value=None)
    def test_play_episode_without_subtitles(self, _, __, ___):
        result = main.play_stream_catchup.test('some/url', 'my episode')
        self.assertRaises(AttributeError, getattr, result, '_subtitles')

    @patch('resources.lib.itv.get_catchup_urls', side_effect=errors.AccessRestrictedError)
    def test_play_premium_episode(self, _):
        result = main.play_stream_catchup.test('url', '')
        self.assertIs(result, False)

    @patch('resources.lib.fetch.post_json', return_value=open_json('playlists/pl_doc_martin.json'))
    def test_play_catchup_without_credentials(self, _):
        # Ensure we have an empty file and session object
        itv_account.itv_session().log_out()
        result = main.play_stream_catchup.test('url', '')
        self.assertFalse(result)


class PlayTitle(TestCase):
    @patch('resources.lib.itvx.get_playlist_url_from_episode_page', side_effect=errors.AccessRestrictedError)
    def test_play_premium_episode(self, _):
        result = main.play_title.test('page')
        self.assertIs(result, False)
