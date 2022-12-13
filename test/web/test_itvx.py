
# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------


from test.support import fixtures
fixtures.global_setup()

import os
import json
import unittest

from typing import Generator

from resources.lib import itvx
from codequick import Listitem, Route, Script


setUpModule = fixtures.setup_web_test


@Route.register()
def dummycallback():
    pass


class TestItvX(unittest.TestCase):
    def test_get_categories(self):
        result = itvx.categories()
        self.assertIsInstance(result, Generator)
        for item in result:
            self.assertTrue('label' in item.keys())
            self.assertTrue('params' in item.keys())
            self.assertTrue('id' in item['params'].keys())

    def test_get_category_films(self):
        result = itvx.get_category_films()
        print(result)

    def test_category_content(self):
        result = itvx.category_content('SPORT')
        self.assertIsInstance(result, list)

    def test_all_categories_content(self):
        categories = itvx.categories()
        for cat in categories:
            result = itvx.category_content(cat['params']['id'])
            print(result)

    def test_get_now_next_schedule(self):
        result = itvx.get_live_schedule()
        # TODO: check result
        print(json.dumps(result, indent=4))

    def test_search(self):
        items = itvx.search('the chase')
        self.assertGreater(len(list(items)), 2)
        items = itvx.search('xprgs')     # should return no results
        self.assertEqual(len(list(items)), 0)

    def test_get_playlist_url_from_episode_page(self):
        # legacy episode page, redirects to itvx https://www.itv.com/watch/holding/7a0203/7a0203a0002
        episode_url = 'https://www.itv.com/hub/holding/7a0203a0002'
        url, name = itvx.get_playlist_url_from_episode_page(episode_url)
        self.assertEqual('', name)
        self.assertTrue(url.startswith('https://'))
        # itvx episode page - Nightwatch Series1 episode 2
        episode_url = "https://www.itv.com/watch/nightwatch/10a3249/10a3249a0002"
        rl, name = itvx.get_playlist_url_from_episode_page(episode_url)
        self.assertEqual('', name)
        self.assertTrue(url.startswith('https://'))
