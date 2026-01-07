# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase

from resources.lib import itv_gql

from support.object_checks import is_url


setUpModule = fixtures.setup_web_test



class GetPlaylistUrl(TestCase):
    def test_get_vod_playlist_url(self):
        ccid = 'hcnxs56'  # an episode of 'a spy among friends', has BSL and AD
        playlist_url = itv_gql.get_playlist_url(ccid)
        self.assertTrue(is_url(playlist_url))
        bsl_playlist_url = itv_gql.get_playlist_url(ccid, prefer_bsl=True)
        self.assertTrue(is_url(bsl_playlist_url))
        self.assertNotEqual(playlist_url, bsl_playlist_url)


class GetShortPlaylistUrl(TestCase):
    def test_get_news_playlist_url(self):
        ccid = 'bkqljr6'  # a short news clip: https://www.itv.com/watch/news/snow-and-ice-expected-to-bring-travel-disruption-ahead-of-amber-weather-warning/bkqljr6
        playlist_url = itv_gql.get_short_playlist_url(ccid)
        self.assertTrue(is_url(playlist_url))

    def test_get_sport_playlist_url(self):
        ccid = 'yvr02ml'  # https://app.10ft.itv.com/3.672.1/freeview/sport/yvr02ml
        playlist_url = itv_gql.get_short_playlist_url(ccid, is_sport=True)
        self.assertTrue(is_url(playlist_url))