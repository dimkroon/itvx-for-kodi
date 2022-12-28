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
from support.object_checks import has_keys, is_url, is_li_compatible_dict
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
        url = parsex.build_url('Astrid & Lily Save the World', '10a2921', '10a2921a0001')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921/10a2921a0001', url)
        url = parsex.build_url('#50/50-heroes?', '10a1511')
        self.assertEqual('https://www.itv.com/watch/5050-heroes/10a1511', url)

    def test_parse_title(self):
        data = open_json('html/series_miss-marple_data.json')
        item = parsex.parse_episode_title(data['title'])
        is_li_compatible_dict(self, item)

        # Episodes where field episodeTitle = None
        data = open_json('html/series_bad-girls_data.json')
        title_obj = data['title']['brand']['series'][6]['episodes'][0]
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)

    def test_parse_search_result(self):
        data = open_json('search/search_results_mear.json')
        for result_item in data['results']:
            item = parsex.parse_search_result(result_item)
            has_keys(item, 'playable', 'show')
            is_li_compatible_dict(self, item['show'])
        search_result = data['results'][0]
        # unknown entity type
        search_result['entityType'] = 'dfgs'
        self.assertIsNone(parsex.parse_search_result(search_result))