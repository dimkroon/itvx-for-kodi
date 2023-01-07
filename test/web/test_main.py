# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import MagicMock
from typing import MutableMapping

from resources.lib import main


setUpModule = fixtures.setup_web_test


class TestMenu(unittest.TestCase):
    def test_menu_live(self):
        items = list(main.sub_menu_live(MagicMock()))
        self.assertGreaterEqual(len(items), 10)
        self.assertGreater(len(items), 10)
        # for item in items:
        #     print(item.params['url'])

    def test_menu_categories(self):
        items = main.list_categories(MagicMock())
        self.assertIsInstance(items, list)
        self.assertAlmostEqual(len(items), 8, delta=2)

    def test_menu_collections(self):
        items = main.list_collections(MagicMock())
        self.assertIsInstance(items, list)
        self.assertAlmostEqual(len(items), 20, delta=4)


class TstCategories(unittest.TestCase):
    def test_categorey_drama_and_soaps(self):
        items = main.list_category(MagicMock(), path='/watch/categories/drama-soaps')
        self.assertGreater(len(items), 10)


class TestGetProductions(unittest.TestCase):
    def test_productions_midsummer_murders(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/midsomer-murders/Ya1096')
        # for item in items:
        #     print(item)
        self.assertGreater(len(items), 1)

    def test_get_productions_midsummer_murder_folder_1(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/midsomer-murders/Ya1096', series_idx=1)
        self.assertGreater(len(items), 1)

    def test_get_productions_midsummer_murder_folder_other_episodes(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/midsomer-murders/Ya1096', series_idx='other-episodes')
        self.assertEqual(len(items), 1)

    def test_get_productions_the_professionals_folder_1(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/the-professionals/L0845', series_idx=1)
        self.assertGreater(len(items), 1)

    def test_get_productions_the_chase(self):
        """The chase had 53 items, but only one production was shown"""
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/the-chase/1a7842')
        self.assertGreater(len(items), 1)

    def test_get_productions_doctor_foster(self):
        """Productions of a paid programme"""
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/doctor-foster/2a7438')
        self.assertGreater(len(items), 1)

    def test_get_productions_bad_girls(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/bad-girls/7a0129')
        self.assertEqual(8, len(items))
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/bad-girls/7a0129', series_idx=6)
        self.assertEqual(12, len(items))


class TestPlayCatchup(unittest.TestCase):
    def test_play_itv_1(self):
        result = main.play_stream_live(MagicMock(), "itv", None)
        self.assertEqual('itv', result.label)
        self.assertIsInstance(result.params, MutableMapping)

    def test_play_vod_a_touch_of_frost(self):
        result = main.play_stream_catchup(MagicMock(),
                                          url='https://magni.itv.com/playlist/itvonline/ITV3/Y_1774_0002_Y',
                                          name='A Touch of Frost')
        self.assertEqual('A Touch of Frost', result.label)
        self.assertIsInstance(result.params, MutableMapping)

    def test_play_vod_episode_julia_bradbury(self):
        result = main.play_stream_catchup(MagicMock(),
                                          url='https://magni.itv.com/playlist/itvonline/ITV/10_0852_0001.001',
                                          name='Walks with Julia Bradbury')
        self.assertEqual('Walks with Julia Bradbury', result.label)
        self.assertIsInstance(result.params, MutableMapping)


class TestSearch(unittest.TestCase):
    def test_search_chase(self):
        items = main.do_search(MagicMock(), 'chase')
        self.assertGreater(len(items), 4)

    def test_search_mear(self):
        items = main.do_search(MagicMock(), 'mear')
        self.assertGreater(len(items), 4)

    def test_search_monday(self):
        items = main.do_search(MagicMock(), 'monday')
        self.assertGreater(len(items), 4)
