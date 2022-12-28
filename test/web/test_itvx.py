
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

from codequick import Listitem, Route, Script

from resources.lib import itvx
from test.support.object_checks import is_url, has_keys, is_li_compatible_dict

setUpModule = fixtures.setup_web_test


@Route.register()
def dummycallback():
    pass


class TestItvX(unittest.TestCase):
    def test_get_categories(self):
        result = itvx.categories()
        self.assertIsInstance(result, Generator)
        for item in result:
            is_li_compatible_dict(self, item)

    def test_all_categories_content(self):
        categories = itvx.categories()
        for cat in categories:
            result = list(itvx.category_content(cat['params']['path']))
            self.assertGreater(len(result), 1)      # News has only a few items
            for item in result:
                self.assertIsInstance(item['playable'], bool)
                is_li_compatible_dict(self, item['show'])

    def test_get_now_next_schedule(self):
        result = itvx.get_live_schedule()
        # TODO: check result
        print(json.dumps(result, indent=4))

    def test_search(self):
        items = itvx.search('the chase')
        self.assertGreater(len(list(items)), 2)
        items = itvx.search('xprgs')     # should return None or empty results, depending on how ITV responds.
        if items is not None:
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
