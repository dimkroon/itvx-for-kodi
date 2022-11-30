#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
#

from test.support import fixtures
fixtures.global_setup()

import unittest

from resources.lib import fetch, parsex, itv_account


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
