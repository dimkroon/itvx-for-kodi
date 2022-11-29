#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx


from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch
import types

from test.support.testutils import open_json

from resources.lib import itvx

setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class Search(TestCase):
    @patch('resources.lib.fetch.get_json', return_value=open_json('search/the_chase.json'))
    def test_simple_search(self, _):
        result = itvx.search('the_chase')
        self.assertIsInstance(result, types.GeneratorType)
        self.assertEqual(10, len(list(result)))

    @patch('resources.lib.fetch.get_json', return_value=None)
    def test_search_without_results(self, _):
        result = itvx.search('xprs')
        self.assertIsInstance(result, types.GeneratorType)
        self.assertListEqual(list(result), [])
