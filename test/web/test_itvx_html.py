
# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import time
import unittest

from resources.lib import fetch, parsex, itv_account
from support import testutils, object_checks


setUpModule = fixtures.setup_web_test


class WatchPages(unittest.TestCase):
    def test_watch_live_itv1(self):
        page = fetch.get_document("https://www.itv.com/watch?channel=itv")
        # testutils.save_doc(page, 'html/watch-itv1.html')
        data = parsex.get__next__data_from_page(page)
        print(data)


class TvGuide(unittest.TestCase):
    def test_guide_of_today(self):
        today = ''  # datetime.utcnow().strftime(('%Y-%m-%d'))
        url = 'https://www.itv.com/watch/tv-guide/' + today
        page = fetch.get_document(url)
        # testutils.save_doc(page, 'html/tv_guide.html')
        print(page)


class Categories(unittest.TestCase):
    all_categories = ['factual', 'drama-soaps', 'children', 'films', 'sport', 'comedy', 'news', 'entertainment']

    def test_get_available_gategories(self):
        """The page categories returns in fact already a full categorie page - the first page in the list
        of categories. Which categorie that is, may change.
        Maybe because of that it is much slower than requesting categories by gql.
        """
        t_s = time.time()
        page = fetch.get_document('https://www.itv.com/watch/categories')
        # testutils.save_doc(page, 'categories/categories.html')
        t_1 = time.time()
        data = parsex.get__next__data_from_page(page)
        categories = data['props']['pageProps']['subnav']['items']
        t_2 = time.time()
        for item in categories:
            object_checks.has_keys(item, 'id', 'name', 'label', 'url')
            # url is the full path without domain
            self.assertTrue(item['url'].startswith('/watch/'))

        self.assertEqual(8, len(categories))        # the mobile app has an additional category AD (Audio Described)
        self.assertListEqual([cat['label'].lower().replace(' & ', '-') for cat in categories], self.all_categories)
        print('Categorie page fetched in {:0.3f}, parsed in {:0.3f}, total: {:0.3f}'.format(
            t_1 - t_s, t_2 - t_1, t_2 - t_s))

    def test_all_categories(self):
        for cat in self.all_categories:
            url = 'https://www.itv.com/watch/categories/children/' + cat
            t_s = time.time()
            page = fetch.get_document(url)
            t_1 = time.time()
            data = parsex.get__next__data_from_page(page)
            programmes = data['props']['pageProps']['programmes']
            t_2 = time.time()
            self.assertIsInstance(programmes, list)
            print("Fetched categorie {} in {:0.3f} s, parsed in {:0.3f}s, total {:0.3f}s.".format(
                cat, t_1 - t_s, t_2 - t_1, t_2 - t_s))
