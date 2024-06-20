# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import uuid
import unittest
from unittest.mock import MagicMock, patch
from typing import MutableMapping

from xbmcgui import ListItem as XbmcListItem

from resources.lib import main, itvx, itv, itv_account, errors, cache
from support import object_checks

setUpModule = fixtures.setup_web_test


class TestMenu(unittest.TestCase):
    def test_main_menu(self):
        items = list(main.root(MagicMock()))
        self.assertGreaterEqual(len(items), 6)

    def test_menu_my_itvx(self):
        items = list(main.sub_menu_my_itvx.route.unittest_caller())
        self.assertGreater(len(items), 0)

    @patch('resources.lib.kodi_utils.get_system_setting', return_value='America/Regina')
    def test_menu_live(self, _):
        items = list(main.sub_menu_live(MagicMock()))
        self.assertGreaterEqual(len(items), 10)
        # for item in items:
        #     print(item.params['url'])

    def test_menu_categories(self):
        items = main.list_categories(MagicMock())
        self.assertIsInstance(items, list)
        self.assertAlmostEqual(len(items), 8, delta=2)

    def test_menu_collections(self):
        items = main.list_collections.test()
        self.assertIsInstance(items, list)
        self.assertAlmostEqual(len(items), 20, delta=4)


class TestMyItvx(unittest.TestCase):
    def setUp(self):
        cache.purge()

    def test_mylist(self):
        items = main.generic_list(MagicMock(), filter_char=None)
        self.assertGreater(len(items), 1)

    def test_mylist_wrong_user_id(self):
        with patch.object(itv_account._itv_session_obj, '_user_id', new=str(uuid.uuid4())):
            self.assertRaises(errors.AccessRestrictedError, main.generic_list.test, filter_char=None)

    def test_my_list_not_signed_in(self):
        with patch.object(itv_account._itv_session_obj, 'account_data', new={}):
            self.assertRaises(SystemExit, main.generic_list.test, filter_char=None)

    @patch('xbmcaddon.Addon.getSettingInt', side_effect=(1000, 50))
    def test_continue_watching(self, _):
        items = main.generic_list.test('watching', filter_char=None)
        self.assertGreater(len(items), 1)

    def test_continue_watching_with_wrong_userid(self):
        with patch.object(itv_account._itv_session_obj, '_user_id', new=str(uuid.uuid4())):
            self.assertRaises(errors.AccessRestrictedError, main.generic_list.test, 'watching', filter_char=None)

    def test_continue_watching_not_signed_in(self):
        with patch.object(itv_account._itv_session_obj, 'account_data', new={}):
            self.assertRaises(SystemExit, main.generic_list.test, 'watching', filter_char=None)

    def test_byw(self):
        items = main.generic_list.test('byw')
        self.assertEqual(12, len(items))

    def test_byw_wrong_userid(self):
        with patch.object(itv_account._itv_session_obj, '_user_id', new=str(uuid.uuid4())):
            items = main.generic_list.test('byw')
            self.assertIs(items, False)

    def test_recommended(self):
        items = main.generic_list.test('recommended')
        self.assertGreater(len(items), 12)


class TstCategories(unittest.TestCase):
    def test_category_drama_and_soaps(self):
        items = main.list_category(MagicMock(), path='/watch/categories/drama-soaps')
        self.assertGreater(len(items), 10)

    def test_news_subcategory_latest_stories(self):
        items = main.list_news_sub_category(MagicMock(), '/watch/categories/news', 'heroAndLatestData')
        self.assertGreater(len(items), 5)


class TestGetProductions(unittest.TestCase):
    def test_productions_midsummer_murders(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/midsomer-murders/Ya1096')
        # for item in items:
        #     print(item)
        self.assertGreater(len(items), 1)

    def test_get_productions_midsummer_murder_folder_1(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/midsomer-murders/Ya1096', series_idx='1')
        self.assertGreater(len(items), 1)

    def test_get_productions_midsummer_murder_folder_other_episodes(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/midsomer-murders/Ya1096', series_idx='others')
        self.assertEqual(len(items), 1)

    def test_get_productions_above_suspicion_folder_1(self):
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/above-suspicion/35460', series_idx='1')
        self.assertEqual(len(items), 2)

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
        items = main.list_productions(MagicMock(), 'https://www.itv.com/watch/bad-girls/7a0129', series_idx='6')
        self.assertEqual(12, len(items))

    def test_get_production_with_bsl(self):
        # Stonehouse, a series with versions that include British Sign Language
        items = main.list_productions.test('https://www.itv.com/watch/stonehouse/10a1973')
        self.assertEqual(3, len(items))

class TestPlayCatchup(unittest.TestCase):
    def test_play_itv_1(self):
        result = main.play_stream_live(MagicMock(), "itv", 'https://simulcast.itv.com/playlist/itvonline/itv', None)
        self.assertEqual('itv', result.getLabel())
        self.assertIsInstance(result, XbmcListItem)

    def test_play_vod_a_touch_of_frost(self):
        result = main.play_stream_catchup(MagicMock(),
                                          url='https://magni.itv.com/playlist/itvonline/ITV3/Y_1774_0002_Y',
                                          name='A Touch of Frost')
        self.assertEqual('A Touch of Frost', result.getLabel())
        self.assertRaises(AttributeError, getattr, result, '_subtitles')
        self.assertIsInstance(result, XbmcListItem)

    def test_play_vod_frost_with_subtitles(self):
        with patch.object(itv.Script, 'setting', new={'subtitles_show': 'true', 'subtitles_color': 'true'}):
            result = main.play_stream_catchup(MagicMock(),
                                              url='https://magni.itv.com/playlist/itvonline/ITV3/Y_1774_0002_Y',
                                              name='A Touch of Frost')
        self.assertEqual('A Touch of Frost', result.getLabel())
        self.assertEqual(1, len(result._subtitles))
        self.assertIsInstance(result, XbmcListItem)

    def test_play_vod_episode_julia_bradbury(self):
        result = main.play_stream_catchup(MagicMock(),
                                          url='https://magni.itv.com/playlist/itvonline/ITV/10_0852_0001.001',
                                          name='Walks with Julia Bradbury')
        self.assertEqual('Walks with Julia Bradbury', result.getLabel())
        self.assertIsInstance(result, XbmcListItem)
        self.assertTrue(object_checks.is_url(result.getPath(), '.mpd'))

    def test_play_short_news_item(self):
        # get the first news item from the main page
        page_data = itvx.get_page_data('https://www.itv.com/')
        news_item = page_data['shortFormSliderContent'][0]['items'][0]
        item_url = '/'.join(('https://www.itv.com/watch/news', news_item['titleSlug'], news_item['episodeId']))
        # play the item
        result = main.play_title.test(item_url, 'news item')
        self.assertIsInstance(result, XbmcListItem)
        self.assertTrue(object_checks.is_url(result.getPath(), '.mp4'))


@unittest.skip("not to interfere with tests of bugfix branch")
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
