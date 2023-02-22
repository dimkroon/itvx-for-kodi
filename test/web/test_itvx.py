
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest

from typing import Generator

from codequick import Route

from resources.lib import itvx, errors, itv_account
from test.support.object_checks import is_url, has_keys, is_li_compatible_dict

setUpModule = fixtures.setup_web_test


@Route.register()
def dummycallback():
    pass


class TestItvX(unittest.TestCase):
    def test_get_now_next_schedule(self):
        result = itvx.get_now_next_schedule()
        for item in result:
            has_keys(item, 'name', 'channelType', 'streamUrl', 'images', 'slot')
        # print(json.dumps(result, indent=4))

    def test_get_live_channels(self):
        chan_list = list(itvx.get_live_channels())
        for item in chan_list:
            has_keys(item, 'name', 'channelType', 'streamUrl', 'images', 'slot')

    def test_get_categories(self):
        result = itvx.categories()
        self.assertIsInstance(result, Generator)
        for item in result:
            is_li_compatible_dict(self, item)

    def test_all_categories_content(self):
        categories = itvx.categories()
        for cat in categories:
            if cat['label'] == 'News':
                # Category news has a different structure
                continue
            result = list(itvx.category_content(cat['params']['path']))
            self.assertGreater(len(result), 1)      # News has only a few items
            for item in result:
                self.assertTrue(item['type'] in ('series', 'brand', 'programme', 'episode', 'special', 'film', 'title'))
                is_li_compatible_dict(self, item['show'])

    def test_category_news(self):
        sub_cat_list = list(itvx.category_news('/watch/categories/news'))
        self.assertGreater(len(sub_cat_list), 4)
        for item in sub_cat_list:
            is_li_compatible_dict(self, item)


    def test_search(self):
        items = itvx.search('the chase')
        self.assertGreater(len(list(items)), 2)
        items = itvx.search('xprgs')     # should return None or empty results, depending on how ITV responds.
        if items is not None:
            self.assertEqual(len(list(items)), 0)

    def test_get_playlist_url_from_episode_page(self):
        # legacy episode page, redirects to itvx https://www.itv.com/watch/holding/7a0203/7a0203a0002
        episode_url = 'https://www.itv.com/hub/holding/7a0203a0002'
        url = itvx.get_playlist_url_from_episode_page(episode_url)
        self.assertTrue(is_url(url))

        # itvx episode page - Nightwatch Series1 episode 2
        episode_url = "https://www.itv.com/watch/nightwatch/10a3249/10a3249a0002"
        url = itvx.get_playlist_url_from_episode_page(episode_url)
        self.assertTrue(is_url(url))

        # Premium episode Downton-abbey S1E1
        episode_url = "https://www.itv.com/watch/downton-abbey/1a8697/1a8697a0001"
        url = itvx.get_playlist_url_from_episode_page(episode_url)
        self.assertTrue(is_url(url))

    def test_get_mylist(self):
        uid = itv_account.itv_session().user_id
        items = itvx.my_list(uid)
        self.assertGreater(len(items), 1)
