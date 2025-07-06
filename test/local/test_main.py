# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import json

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from codequick import Listitem
import xbmcgui
from xbmcgui import ListItem as XbmcListItem

from test.support.testutils import open_json, open_doc, HttpResponse, mockeddt
from test.support import object_checks

from resources.lib import main
from resources.lib import errors
from resources.lib import cache
from resources.lib import itv_account


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class Paginator(TestCase):
    def test_no_items(self):
        for items_list in ([], None, False):
            pg = main.Paginator(items_list, filter_char=None, page_nr=0)
            result = list(pg)
            self.assertListEqual([], result)

    def test_invalid_type_of_list(self):
        pg = main.Paginator(1234, filter_char=None, page_nr=0)
        self.assertRaises(errors.ParseError, list, pg)

    def test_unknown_item_type(self):
        items_list = [{'type': 'zdfhs', 'show': {}}]
        pg = main.Paginator(items_list, filter_char=None, page_nr=0)
        result = list(pg)
        self.assertListEqual([], result)


@patch('resources.lib.itvx.get_page_data', return_value=open_json('json/index-data.json'))
class MainMenu(TestCase):
    @patch('resources.lib.itvx.parsex.datetime', new=mockeddt)
    def test_main_menu(self, _):
        mockeddt.mocked_now = datetime.now(tz=timezone.utc).replace(hour=21)
        items = list(main.root.test())
        self.assertGreater(len(items), 10)
        items_with_ctx_menus = 0
        for item in items:
            self.assertIsInstance(item, Listitem)
            if len(item.context) > 0:
                items_with_ctx_menus += 1
        # Check 'My ItvX' is present
        self.assertTrue(items[0].label == 'My itvX')
        self.assertEqual(6, items_with_ctx_menus)


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
    def test_list_live_channels_no_tz_settings(self, _, __):
        cache.purge()
        chans = main.sub_menu_live.test()
        self.assertIsInstance(chans, list)


class MyItvx(TestCase):
    def setUp(self):
        cache.purge()

    def test_submenu_my_itvx(self):
        list_items = main.sub_menu_my_itvx.test()
        self.assertEqual(3, len(list_items))
        # Check 'Because You Watched' present when logged in
        with patch.object(itv_account._itv_session_obj, '_user_id', 'dzgzdfgsf'):
            with patch('resources.lib.fetch.get_json', return_value=open_json('usercontent/byw.json')):
                list_items = main.sub_menu_my_itvx.test()
                self.assertEqual(4, len(list_items))

    @patch('resources.lib.itv_account.fetch_authenticated',
           new=lambda funct, url, login=True, **kwargs: funct(url, **kwargs))
    @patch('xbmcaddon.Addon.getSettingInt', return_value=1000)
    def test_list_last_watched(self, _):
        with patch('resources.lib.fetch.web_request',
                   return_value=HttpResponse(text=open_doc('usercontent/last_watched_all.json')())) as p_fetch:
            shows = list(main.generic_list.test('watching', filter_char=None))
            self.assertEqual(7, len(shows))
            p_fetch.assert_called_once()
        # All responses below have been observed in the wild when the watched list had no items.
        cache.purge()
        with patch('resources.lib.fetch.web_request', return_value=HttpResponse(200, content=b'[]')):
            result = main.generic_list.test('watching', filter_char=None)
            self.assertIs(result, False)
        cache.purge()
        with patch('resources.lib.fetch.web_request', return_value=HttpResponse(204, reason='No Content', content=b'')):
            result = main.generic_list.test('watching', filter_char=None)
            self.assertIs(result, False)
        cache.purge()
        with patch('resources.lib.fetch.web_request', return_value=HttpResponse(404, reason='Not Found', content=b'')):
            result = main.generic_list.test('watching', filter_char=None)
            self.assertIs(result, False)
        cache.purge()
        with patch('resources.lib.fetch.web_request', return_value=HttpResponse(200, content=b'no content')):
            result = main.generic_list.test('watching', filter_char=None)
            self.assertIs(result, False)

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    def test_list_mylist(self, _):
        li_items = main.generic_list.test(filter_char=None, page_nr=None)
        self.assertIsInstance(li_items, list)
        for item in li_items:
            self.assertIsInstance(item, Listitem)

    @patch('resources.lib.cache.my_list_programmes', new=None)
    def test_my_list_context_menu_not_logged_in(self):
        main._my_list_context_mnu(Listitem(), '1234')

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    def test_add_mylist_item(self, _):
        result = main.update_mylist.test(progr_id='10_1511', operation='add')
        # Callbacks of type Script should not return data
        self.assertIsNone(result)

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    @patch('xbmc.executebuiltin')
    def test_add_mylist_item_container_refresh(self, p_exec_builtin, _):
        main.update_mylist.test('10_1511', 'add', refresh=False)
        p_exec_builtin.assert_not_called()
        main.update_mylist.test('10_1511', 'add', refresh=True)
        p_exec_builtin.assert_called_once_with('Container.Refresh')

    def test_add_mylist_item_with_auth_error(self):
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.AccessRestrictedError):
            result = main.update_mylist.test(progr_id='10_1511', operation='add')
            # Callbacks of type Script should not return data
            self.assertIsNone(result)
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=SystemExit):
            self.assertRaises(SystemExit, main.update_mylist.test, progr_id='10_1511', operation='add')

    @patch('resources.lib.itv_account.fetch_authenticated', return_value=open_json('mylist/mylist_json_data.json'))
    def test_delete_mylist_item(self, _):
        result = main.update_mylist.test(progr_id='10_1511', operation='remove')
        # Callbacks of type Script should not return data
        self.assertIsNone(result)

    def test_delete_mylist_item_with_auth_error(self):
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=errors.AccessRestrictedError):
            result = main.update_mylist.test(progr_id='10_1511', operation='remove')
            # Callbacks of type Script should not return data
            self.assertIsNone(result)
        with patch('resources.lib.itv_account.fetch_authenticated', side_effect=SystemExit):
            self.assertRaises(SystemExit, main.update_mylist.test, progr_id='10_1511', operation='remove')

    @patch('resources.lib.fetch.get_json', return_value=open_json('usercontent/byw.json'))
    def test_because_you_watched(self, p_fetch):
        # Not logged in
        itv_account.itv_session()       # Ensure a session object exists
        with patch.object(itv_account._itv_session_obj, '_user_id', ''):
            result = main.generic_list.test('byw')
            self.assertIs(result, False)
            p_fetch.assert_not_called()
        # Logged In
        with patch.object(itv_account._itv_session_obj, '_user_id', 'dzgzdfgsf'):
            result = main.generic_list.test('byw')
        p_fetch.assert_called_once()
        self.assertEqual(12, len(result))

    @patch('resources.lib.fetch.get_json', return_value=open_json('usercontent/recommended.json'))
    def test_recommended(self, p_fetch):
        # Not logged in
        itv_account.itv_session()  # Ensure a session object exists
        with patch.object(itv_account._itv_session_obj, '_user_id', ''):
            result = main.generic_list.test('recommended')
        p_fetch.assert_called_once()
        self.assertEqual(12, len(result))

        # Logged In
        p_fetch.reset_mock()
        cache.purge()
        with patch.object(itv_account._itv_session_obj, '_user_id', 'dzgzdfgsf'):
            result = main.generic_list.test('recommended')
            p_fetch.assert_called_once()
            self.assertEqual(12, len(result))

            # Hide paid
            with patch('xbmcaddon.Addon.getSetting', return_value='true'):
                result = main.generic_list.test('recommended')
            self.assertEqual(11, len(result))       # one paid item in the list.

    def test_non_existing_type_of_generic_list(self):
        self.assertRaises(ValueError, main.generic_list.test, 'non-existing-list')


class Collections(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_get_collections(self, _):
        coll = main.list_collections.test()
        self.assertEqual(20, len(coll))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_get_collection_news(self, _):
        shows = list(filter(None, main.list_collection_content.test(slider='newsShortForm')))
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

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_films.json'))
    def test_category_film(self, _):
        items = main.list_category.test('category/films')
        self.assertIsInstance(items, list)
        self.assertEqual(292, len(items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_children.json'))
    def test_get_category_children_paginated(self, _):
        """Category with 128 programmes."""
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(0, 60) * 2):  # no a-z, page length = 30
            programmes = list(filter(None, main.list_category.test('sdfg')))
            self.assertEqual(61, len(programmes))
            programmes = list(filter(None, main.list_category.test('sdfg', page_nr=2)))
            self.assertEqual(8, len(programmes))
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(0, 125)):  # no a-z, page length = 55
            # content must be more than 5 longer than page length before actual pagination is performed.
            programmes = list(filter(None, main.list_category.test('sdfg')))
            self.assertEqual(128, len(programmes))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_children.json'))
    def test_category_children_az_list(self, _):
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(20, 0)):  # a-z on 20 items, page length=0
            programmes = list(filter(None, main.list_category.test('sdfg')))
            self.assertEqual(20, len(programmes))
            self.assertEqual('A', programmes[0].label)
            self.assertEqual('A', programmes[0].params['filter_char'])

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_drama-soaps.json'))
    def test_category_drama_list_by_character(self, _):
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(20, 0) * 2):  # a-z on 20 items, page length=0
            programmes = list(filter(None, main.list_category.test('sdfg', filter_char='A')))
            self.assertEqual(19, len(programmes))
            programmes = list(filter(None, main.list_category.test('sdfg', filter_char='0-9')))
            self.assertEqual(1, len(programmes))
        # Test content of 'A' divided in sub-pages
        with patch('xbmcaddon.Addon.getSettingInt', side_effect=(20, 6)*3):  # a-z on 20 items, page length=6
            programmes = list(filter(None, main.list_category.test('sdfg', filter_char='A')))
            self.assertEqual(7, len(programmes))
            programmes = list(filter(None, main.list_category.test('sdfg', filter_char='A', page_nr=2)))
            # Categories 'A' has 19 items
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
        self.assertEqual(25, len(items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_news.json'))
    def test_sub_category_news_rails(self, _):
        """Very much the same as collection news, but divided in various sub categories."""
        items = main.list_news_sub_category.test('my/url', 'curatedRails', 'Politics')
        self.assertIsInstance(items, list)
        self.assertEqual(13, len(items))


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
        list_items = main.list_productions.test('some/url/to/marple', series_idx='4')
        self.assertIsInstance(list_items, list)
        self.assertEqual(4, len(list_items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_midsomer-murders.json'))
    def test_episodes_midsummer_murders_series_other_episodes(self, _):
        """Test listing opened at the non-integer seriesNUmber 'other episodes'."""
        list_items = main.list_productions.test('/some/url//to/midsumer', series_idx='others')
        self.assertIsInstance(list_items, list)
        self.assertEqual(1, len(list_items))      # 22 series, 1 episode

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_bad-girls_data.json'))
    def test_episodes_bad_girls_series_5(self, _):
        """Test listing opened at series 4"""
        list_items = main.list_productions.test('some/url/to/bad girls', series_idx='5')
        self.assertIsInstance(list_items, list)
        self.assertEqual(16, len(list_items))

    def test_episode_of_show_with_only_one_series(self):
        # FIXME: Not quite sure what we are actually testing here.
        data = open_json('html/series_miss-marple_data.json')
        series = data['seriesList']
        # Remove all but the first series
        while len(series) > 1:
            series.pop()
        with patch('resources.lib.itvx.get_page_data', return_value=data):
            series_listing = main.list_productions.test('asd')
            self.assertEqual(4, len(series_listing))
            # Check if all items are playable
            for episode in series_listing:
                self.assertIs(episode.path, main.play_stream_catchup.route)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/paid_episode_downton-abbey-s1e1.json'))
    def test_programme_with_series_other(self, _):
        list_items = main.list_productions.test('some/url/to/downton', series_idx='others')
        self.assertIsInstance(list_items, list)
        self.assertEqual(4, len(list_items))


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
        self.assertEqual(3, len(results))
        self.assertIs(results[0].path, main.list_productions.route)
        self.assertIs(results[2].path, main.play_title.route)           # special without field specialProgramme

    @patch('requests.sessions.Session.send',
           return_value=HttpResponse(text=open_doc('search/search_monday.json')()))
    def test_search_hide_paid(self, _):
        results = main.do_search.test('monday')
        self.assertEqual(3, len(results))
        with patch('xbmcaddon.Addon.getSetting', return_value='true'):
            results = main.do_search.test('monday')
            self.assertEqual(2, len(results))

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

    @patch('requests.sessions.Session.send',
           return_value=HttpResponse(text=open_doc('search/search_monday.json')()))
    @patch('resources.lib.main._my_list_context_mnu')
    def test_search_context_menu_does_not_refresh_container(self, p_ctx_mnu, _):
        main.do_search.test('monday')
        self.assertIs(False, p_ctx_mnu.call_args.kwargs['refresh'])


@patch('requests.get', return_value=HttpResponse())
class CreateDashStreamItem(TestCase):
    def test_create_dash_stream_item(self, _):
        result = main.create_dash_stream_item('my stream', 'manifest.url', 'key.service.url')
        self.assertIsInstance(result, xbmcgui.ListItem)

    @patch('inputstreamhelper.Helper.check_inputstream', return_value=False)
    def test_create_dash_stream_item_intputstream_adaptive_not_present(self, _, __):
        result = main.create_dash_stream_item('my stream', 'manifest.url', 'key.service.url')
        self.assertIs(result, False)


class PlayStreamLive(TestCase):
    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_itv1.json'))
    @patch('requests.get', return_value=HttpResponse())
    @patch('resources.lib.itv_account.ItvSession.refresh', return_value=True)
    @patch('resources.lib.itv_account.ItvSession.cookie', new={'Itv.Session': 'blabla'})
    def test_play_live_by_channel_name(self, _, __, p_req_strm):
        result = main.play_stream_live.test(channel='ITV', url=None)
        self.assertIsInstance(result, XbmcListItem)
        self.assertEqual('ITV', result.getLabel())
        self.assertFalse('IsPlayable' in result._props)
        self.assertFalse('inputstream.adaptive.play_timeshift_buffer' in result._props)
        # Assert channel name is converted to a full url
        self.assertEqual(1, len(p_req_strm.call_args_list))
        self.assertTrue(object_checks.is_url(p_req_strm.call_args[0][0], '/ITV'))
        # -- A FAST channel --
        p_req_strm.reset_mock()
        result = main.play_stream_live.test(channel='FAST16', url=None)
        self.assertIsInstance(result, XbmcListItem)
        self.assertEqual('FAST16', result.getLabel())
        self.assertFalse('inputstream.adaptive.play_timeshift_buffer' in result._props)
        # Assert channel name is converted to a full url
        self.assertEqual(1, len(p_req_strm.call_args_list))
        self.assertTrue(object_checks.is_url(p_req_strm.call_args[0][0], '/FAST16'))
        # -- Watch from the start --
        result = main.play_stream_live.test(channel='ITV', url=None,
                                            start_time="2024-11-03T18:00:30", play_from_start=True)
        self.assertIsInstance(result, XbmcListItem)
        self.assertTrue('inputstream.adaptive.play_timeshift_buffer' in result._props)


    @patch('resources.lib.fetch.post_json', return_value=open_json('playlists/pl_itv1.json'))
    def test_play_stream_live_without_credentials(self, _):
        with patch.object(itv_account.itv_session(), 'account_data', {}):
            with self.assertRaises(SystemExit) as cm:
                main.play_stream_live.test(channel='ITV', url=None)
            self.assertEqual(1, cm.exception.code)

    @patch('resources.lib.itv.get_live_urls', side_effect=ValueError)
    def test_play_stream_live_without_other_error(self, _):
        self.assertRaises(ValueError, main.play_stream_live.test, channel='ITV', url=None)


class PlayStreamCatchup(TestCase):
    def setUp(self) -> None:
        itv_account._itv_session_obj = None

    @classmethod
    def tearDownClass(cls) -> None:
        # Ensure to clear patched session objects
        itv_account._itv_session_obj = None

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_news_short.json'))
    def test_play_short_news_item(self, _):
        result = main.play_stream_catchup.test('some/url', 'a short news item')
        self.assertIsInstance(result, XbmcListItem)

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
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

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('requests.get', return_value=HttpResponse())
    @patch('resources.lib.itv_account.ItvSession.cookie', new={'Itv.Session': ''})
    def test_play_episode_without_title(self, _, __):
        result = main.play_stream_catchup.test('some/url', '')
        self.assertIsInstance(result, XbmcListItem)
        self.assertEqual('', result.getLabel())
        with self.assertRaises(KeyError):
            result._info['video']['title']

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('resources.lib.main.create_dash_stream_item', return_value=XbmcListItem())
    @patch('resources.lib.itv.get_vtt_subtitles', return_value=('my/subs.file', ))
    def test_play_episode_with_subtitles(self, _, __, ___):
        result = main.play_stream_catchup.test('some/url', 'my episode')
        self.assertEqual(len(result._subtitles), 1)

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('resources.lib.main.create_dash_stream_item', return_value=XbmcListItem())
    @patch('resources.lib.itv.get_vtt_subtitles', return_value=None)
    def test_play_episode_without_subtitles(self, _, __, ___):
        result = main.play_stream_catchup.test('some/url', 'my episode')
        self.assertRaises(AttributeError, getattr, result, '_subtitles')

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('resources.lib.main.create_dash_stream_item', return_value=xbmcgui.ListItem())
    @patch('resources.lib.itvx.get_resume_point', return_value=32)
    def test_play_episode_with_resume(self, _, __, ___):
        result = main.play_stream_catchup.test('some/url', 'my episode', set_resume_point=True)
        self.assertEqual('32', result._props['ResumeTime'])
        self.assertTrue('TotalTime' in result._props)

    @patch('resources.lib.itv.get_catchup_urls', side_effect=errors.AccessRestrictedError)
    def test_play_premium_episode(self, _):
        result = main.play_stream_catchup.test('url', '')
        self.assertIs(result, False)

    @patch('resources.lib.fetch.post_json', return_value=open_json('playlists/pl_doc_martin.json'))
    def test_play_catchup_without_credentials(self, _):
        # Ensure we have an empty file and session object
        with patch.object(itv_account.itv_session(), 'account_data', {}):
            with self.assertRaises(SystemExit) as cm:
                main.play_stream_catchup.test('url', '')
            self.assertEqual(1, cm.exception.code)

    @patch('resources.lib.itv.get_catchup_urls', side_effect=ValueError)
    def test_play_catchup_with_other_error(self, _):
        self.assertRaises(ValueError, main.play_stream_catchup.test, 'url', '')

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    @patch('resources.lib.main.create_dash_stream_item', return_value=False)
    def test_play_catchup_inputstream_adaptive_not_installed(self, _, __):
        result = main.play_stream_catchup.test('url', '')
        self.assertIs(result, False)


class PlayTitle(TestCase):
    @patch('resources.lib.itvx.get_playlist_url_from_episode_page', return_value='my.url')
    @patch('resources.lib.main.play_stream_catchup', return_value='play_success')
    def test_play_episode(self, _, p_get_playlist):
        result = main.play_title.test('page.url')
        p_get_playlist.assert_called_once_with('page.url', False)
        self.assertEqual('play_success', result)
        # Prefer Signed Programmes
        with patch('xbmcaddon.Addon.getSetting', new=lambda self, x: 'true' if x == 'prefer_bsl' else ''):
            p_get_playlist.reset_mock()
            result = main.play_title.test('page.url')
            p_get_playlist.assert_called_once_with('page.url', True)
            self.assertEqual('play_success', result)

    @patch('resources.lib.itvx.get_playlist_url_from_episode_page', side_effect=errors.AccessRestrictedError)
    def test_play_premium_episode(self, _):
        result = main.play_title.test('page')
        self.assertIs(result, False)


class Run(TestCase):
    @patch('sys.argv', return_value=['script', '1'])
    @patch('resources.lib.main.cc_run', return_value=ValueError())
    @patch('xbmcplugin.endOfDirectory')
    def test_run_failure(self, p_end_of_dir, _, __):
        main.run()
        p_end_of_dir.assert_called_once_with(1, False)