# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

import types

from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch

from codequick import Listitem

from test.support.testutils import open_json

from resources.lib import main
from resources.lib import errors

setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


@patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
class MainMenu(TestCase):
    def test_main_menu(self, _):
        items = list(main.root(MagicMock()))
        self.assertGreater(len(items), 10)
        for item in items:
            self.assertIsInstance(item, Listitem)


@patch('resources.lib.fetch.get_json', side_effect=(open_json('schedule/now_next.json'),
                                                    open_json('schedule/live_4hrs.json')))
class LiveChannels(TestCase):
    def test_list_live_channels(self, _):
        chans = main.sub_menu_live(MagicMock())
        self.assertIsInstance(chans, types.GeneratorType)
        chan_list = list(chans)
        self.assertGreaterEqual(len(chan_list), 10)


class Collections(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_get_collections(self, _):
        coll = main.list_collections(MagicMock())
        self.assertAlmostEqual(20, len(coll), delta=5)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_get_collection_news(self, _):
        shows = main.list_collection_content(MagicMock(), slider='newsShortformSliderContent')
        self.assertGreater(len(shows), 10)
        for item in shows:
            self.assertIsInstance(item, Listitem)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/index-data.json'))
    def test_get_collection_trending(self, _):
        shows = main.list_collection_content(MagicMock(), slider='trendingSliderContent')
        self.assertGreater(len(shows), 10)
        for item in shows:
            self.assertIsInstance(item, Listitem)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/collection_just-in_data.json'))
    def test_get_collection_from_collection_page(self, _):
        shows = main.list_collection_content(MagicMock(), url='top-picks')
        self.assertGreater(len(shows), 10)
        for item in shows:
            self.assertIsInstance(item, Listitem)


class Categories(TestCase):
    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/categories_data.json'))
    def test_get_categories(self, _):
        cats = main.list_categories(MagicMock())
        self.assertAlmostEqual(len(cats), 8, delta=2)
        for cat in cats:
            self.assertIsInstance(cat, Listitem)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/category_drama-soaps.json'))
    def test_get_category_drama(self, _):
        programmes = main.list_category(MagicMock(), 'sdfg')
        self.assertGreater(len(programmes), 100)
        for prog in programmes:
            self.assertIsInstance(prog, Listitem)


@patch("resources.lib.cache.get_item", new=lambda *a, **k: None)     # disable cache
class Productions(TestCase):
    @patch("resources.lib.itvx.episodes", return_value=[])
    def test_empty_productions_list(self, _):
        result = main.list_productions(MagicMock(), '')
        self.assertIs(result, False)

    def test_no_url_passed(self):
        result = main.list_productions(MagicMock())
        self.assertIs(False, result)

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_miss-marple_data.json'))
    def test_episodes_marple(self, _):
        list_items = main.list_productions(MagicMock(), 'marple')
        self.assertIsInstance(list_items, list)
        self.assertEqual(6, len(list_items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_miss-marple_data.json'))
    def test_episodes_marple_series_4(self, _):
        """Test listing opened at series 4"""
        list_items = main.list_productions(MagicMock(), 'marple', series_idx=4)
        self.assertIsInstance(list_items, list)
        self.assertEqual(4, len(list_items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_midsummer-murders.json'))
    def test_episodes_midsummer_murders_series_other_episodes(self, _):
        """Test listing opened at the non-integer seriesNUmber 'other episodes'."""
        list_items = main.list_productions(MagicMock(), 'midsumer', series_idx='other-episodes')
        self.assertIsInstance(list_items, list)
        self.assertEqual(1, len(list_items))      # 22 series, 1 episode

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_midsummer-murders.json'))
    def test_episodes_midsummer_murders_series_4(self, _):
        """Midsummer murder has 2 different series numbered series-4. These should be merged into one"""
        list_items = main.list_productions(MagicMock(), 'midsumer', series_idx=4)
        self.assertIsInstance(list_items, list)
        self.assertEqual(6, len(list_items))      # 22 series, 5 episode in series 4-1, 1 episode in series 4-2

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_bad-girls_data.json'))
    def test_episodes_bad_girls_series_5(self, _):
        """Test listing opened at series 4"""
        list_items = main.list_productions(MagicMock(), 'bad girls', series_idx=5)
        self.assertIsInstance(list_items, list)
        self.assertEqual(16, len(list_items))

    def test_episode_of_show_with_only_one_series(self):
        data = open_json('html/series_miss-marple_data.json')
        series = data['title']['brand']['series']
        # Remove all but the first series
        while len(series) > 1:
            series.pop()
        with patch('resources.lib.itvx.get_page_data', return_value=data):
            series_listing = main.list_productions(MagicMock(), 'asd')
            self.assertEqual(4, len(series_listing))
            # Check if all items are playable
            for episode in series_listing:
                self.assertIs(episode.path, main.play_stream_catchup.route)


class Search(TestCase):
    @patch('resources.lib.fetch.get_json', return_value=open_json('search/the_chase.json'))
    def test_search_the_chase(self, _):
        results = main.do_search(MagicMock(), 'the chase')
        self.assertEqual(10, len(results))
        self.assertIs(results[0].path, main.list_productions.route)     # programme
        self.assertIs(results[4].path, main.play_title.route)           # special with field specialProgramme

    @patch('resources.lib.fetch.get_json', return_value=open_json('search/search_results_mear.json'))
    def test_search_mear(self, _):
        results = main.do_search(MagicMock(), 'mear')
        self.assertEqual(10, len(results))
        self.assertIs(results[0].path, main.list_productions.route)     # programme
        self.assertIs(results[4].path, main.play_title.route)           # film

    @patch('resources.lib.fetch.get_json', return_value=open_json('search/search_monday.json'))
    def test_search_monday(self, _):
        results = main.do_search(MagicMock(), 'monday')
        self.assertEqual(7, len(results))
        self.assertIs(results[0].path, main.list_productions.route)
        self.assertIs(results[6].path, main.play_title.route)           # special without field specialProgramme

    def test_search_result_with_unknown_entitytype(self):
        search_data = open_json('search/search_results_mear.json')
        with patch('resources.lib.fetch.get_json', return_value=search_data):
            results_1 = main.do_search(MagicMock(), 'kjhbn')
            self.assertEqual(10, len(results_1))
        # check again with one item having an unknown entity type
        search_data['results'][3]['entityType'] = 'video'
        with patch('resources.lib.fetch.get_json', return_value=search_data):
            results_2 = main.do_search(MagicMock(), 'kjhbn')
            self.assertEqual(9, len(results_2))

    @patch('resources.lib.fetch.get_json', return_value=None)
    def test_search_with_no_results(self, _):
        results = main.do_search(MagicMock(), 'the chase')
        self.assertIs(results, False)


class PlayStreamCatchup(TestCase):
    @patch('resources.lib.itv.get_catchup_urls', side_effect=errors.AccessRestrictedError)
    def test_play_premium_episode(self, _):
        result = main.play_stream_catchup(MagicMock(), 'url', '')
        self.assertIs(result, False)


class PlayTitle(TestCase):
    @patch('resources.lib.itvx.get_playlist_url_from_episode_page', side_effect=errors.AccessRestrictedError)
    def test_play_premium_episode(self, _):
        result = main.play_title(MagicMock(), 'page')
        self.assertIs(result, False)
