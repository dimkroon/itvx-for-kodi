# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase

from support.object_checks import is_not_empty

from resources.lib import iptvmanager


setUpModule = fixtures.setup_web_test


class WhatToWatchEpg(TestCase):
    def test_what_to_watch_region_id(self):
        reg_id = iptvmanager.what_to_watch_region_id()
        self.assertTrue(is_not_empty(reg_id, str))

    def test_what_to_watch_channel_ids(self):
        region_id = iptvmanager.what_to_watch_region_id()
        channel_ids = iptvmanager.what_to_watch_channel_ids(region_id)
        self.assertEqual(len(channel_ids), 5)
        for chan_id in channel_ids:
            self.assertTrue(is_not_empty(chan_id, str))

    def test_what_to_watch_epg(self):
        epg = iptvmanager.what_to_watch_schedule()
        self.assertEqual(list(epg.keys()), ['ITV1', 'ITV2', 'ITV3', 'ITV4', 'ITVBe'])
        for schedule in epg.values():
            self.assertGreater(len(schedule), 5)
            for pgm in schedule:
                self.assertIsInstance(pgm, dict)

