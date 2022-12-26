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

from test.support.testutils import open_json

from resources.lib import main


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


@patch('resources.lib.fetch.get_json', side_effect=(open_json('schedule/now_next.json'),
                                                    open_json('schedule/live_4hrs.json')))
class LiveChannels(TestCase):
    def test_liste_live_channels(self, _):
        chans = main.sub_menu_live(MagicMock())
        self.assertIsInstance(chans, types.GeneratorType)
        chan_list = list(chans)
        self.assertGreaterEqual(len(chan_list), 10)


@patch('resources.lib.fetch.get_json', return_value=open_json('programs_legacy/all_shows.json'))
class Shows(TestCase):
    def assert_all_items_start_with(self, chars, items_list):
        """Check if the first character of all items is one of `chars`."""
        for item in items_list:
            self.assertTrue(item.info['sorttitle'][0] in chars)

    def test_shows_all(self, _):
        all_shows = main.list_programs(MagicMock(), "shows_url")
        self.assertIsInstance(all_shows, list)
        self.assertGreater(len(all_shows), 300)

    def test_shows_without_kwargs(self, _):
        """Test calling list_programs without keyword arguments. Is what happens when a programme
        has been added to favourites and the user clicks on the '...' after entering the listing from
        favourites.
        """
        all_shows = main.list_programs(MagicMock())
        self.assertIs(all_shows, False)

    def test_shows_filtered(self, _):
        shows_a = main.list_programs(MagicMock(), "shows_url", 'A')
        self.assert_all_items_start_with('a', shows_a)
        shows_l = main.list_programs(MagicMock(), "shows_url", 'L')
        self.assert_all_items_start_with('l', shows_l)
        shows_num = main.list_programs(MagicMock(), "shows_url", '0-9')
        self.assert_all_items_start_with('0123456789#', shows_num)

    def test_shows_filter_is_case_insensitive(self, _):
        shows_A = main.list_programs(MagicMock(), "shows_url", 'A')
        shows_a = main.list_programs(MagicMock(), "shows_url", 'a')
        self.assertEqual(len(shows_A), len(shows_a))
        for i in range(len(shows_A)):
            self.assertEqual(shows_A[i].info['sorttitle'], shows_a[i].info['sorttitle'])

    def test_return_value_of_empty_sub_folder(self, _):
        """Folder 'X' does not have any items"""
        shows_x = main.list_programs(MagicMock(), "shows_url", 'X')
        self.assertFalse(shows_x)


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
        self.assertEqual(9, len(list_items))

    @patch('resources.lib.itvx.get_page_data', return_value=open_json('html/series_bad-girls_data.json'))
    def test_episodes_bad_girls_series_5(self, _):
        """Test listing opened at series 4"""
        list_items = main.list_productions(MagicMock(), 'bad girls', series_idx=5)
        self.assertIsInstance(list_items, list)
        self.assertEqual(23, len(list_items))


class Search(TestCase):
    @patch('resources.lib.fetch.get_json', return_value=open_json('search/the_chase.json'))
    def test_search_the_chase(self, _):
        results = main.do_search(MagicMock(), 'the chase')
        self.assertEqual(10, len(results))

    @patch('resources.lib.fetch.get_json', return_value=None)
    def test_search_with_no_results(self, _):
        results = main.do_search(MagicMock(), 'the chase')
        self.assertFalse(results)