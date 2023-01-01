# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from support import testutils
from test.support import fixtures
fixtures.global_setup()

from datetime import datetime, timedelta
import time
import unittest
import requests
import copy

from resources.lib import itv, fetch, errors, parse
from resources.lib import itv_account

from test.support import object_checks


setUpModule = fixtures.setup_web_test




# ----------------------------------------------------------------------------------------------------------------------
#           JSON API
# ----------------------------------------------------------------------------------------------------------------------

class Programmes(unittest.TestCase):
    def get_json(self, url):
        resp = requests.get(
                url,
                headers={'Accept': 'application/vnd.itv.online.discovery.programme.v1+hal+json; charset=UTF-8'}
        )
        return resp.json()

    def _validate_strcuture(self, programs_data):
        self.assertTrue('_embedded' in programs_data.keys())
        self.assertTrue('programmes' in programs_data['_embedded'].keys())
        prog_list = programs_data['_embedded']['programmes']
        self.assertIsInstance(prog_list, list)
        for item in prog_list:
            self.assertTrue('id' in item.keys())
            self.assertTrue('title' in item.keys())
            self.assertTrue('epg' in item['synopses'].keys())
            productions = item['_embedded']['productions']
            self.assertTrue('count' in productions.keys())
            self.assertTrue('_links' in productions.keys())
            self.assertTrue(productions['_links']['doc:productions']['href'].startswith('https://'))
            latest = item['_embedded']['latestProduction']
            self.assertTrue('productionType' in latest.keys())
            self.assertTrue(latest['productionType'] in ('programme', 'PROGRAMME'))

            # series and episodes are not always present, event of there are more than 1 episodes.
            # assertTrue('episode' in latest.keys())

            # EpisodeTitle is not always present, even if there are multiple episodes availble.
            # self.assertTrue('episodeTitle' in latest.keys(),
            #                 msg="No key episodeTitle in production {}".format(latest))

            self.assertTrue('commissioning' in latest['broadcastDateTime'].keys())
            self.assertTrue('iso8601', latest['duration'].keys())
            self.assertTrue('display', latest['duration'].keys())
            self.assertTrue(latest['_links']['image']['href'].startswith('https://'))
            self.assertTrue(latest['_links']['playlist']['href'].startswith('https://'))

    def test_programmes_all(self):
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?'
                                  'broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,'
                                  'widevine,fairplay&sortBy=title')
        self._validate_strcuture(json_resp)
# ---------------------------------------------------------------------------------------------------------------------
