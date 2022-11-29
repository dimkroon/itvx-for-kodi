#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx

from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import MagicMock, patch

from support.testutils import open_doc
from resources.lib import parsex


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class TestGet__Next__DataFromPage(unittest.TestCase):
    def test_parse_watch_pages(self):
        for page in ('html/watch-itv1.html', ):
            get_page = open_doc(page)
            data = parsex.get__next__data_from_page(get_page())
            self.assertIsInstance(data, dict)