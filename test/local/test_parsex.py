# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import MagicMock, patch

from support.testutils import open_doc, open_json
from resources.lib import parsex


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class TestGet__Next__DataFromPage(unittest.TestCase):
    def test_parse_watch_pages(self):
        for page in ('html/index.html', 'html/watch-itv1.html'):
            get_page = open_doc(page)
            data = parsex.scrape_json(get_page())
            self.assertIsInstance(data, dict)



class Generic(unittest.TestCase):
    def test_build_url(self):
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921', url)
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921', None)
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921', url)
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921', '10a2921a0001')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921/10a2921a0001', url)

    def test_parse_title(self):
        data = open_json('html/series_miss-marple_data.json')
        item = parsex.parse_title(data['title'])
        self.assertTrue(item)
        self.assertIsInstance(item, dict)

        # Episodes where field episodeTitle = None
        data = open_json('html/series_bad-girls_data.json')
        title_obj = data['title']['brand']['series'][6]['episodes'][0]
        item = parsex.parse_title(title_obj)
        self.assertTrue(item)
        self.assertIsInstance(item, dict)