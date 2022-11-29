#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
#

from support import testutils
from test.support import fixtures
fixtures.global_setup()

import datetime
import time
import unittest
import requests

from resources.lib import itvx, fetch, errors, parse
from resources.lib import itv_account

from test.support import object_checks


setUpModule = fixtures.setup_web_test


class Search(unittest.TestCase):
    search_url = 'https://textsearch.prd.oasvc.itv.com/search'
    search_params = {
        'broadcaster': 'itv',
        'featureSet': 'clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay,bbts,progressive,hd,rtmpe',
        'onlyFree': 'false',
        'platform': 'dotcom',
    }

    def check_result(self, resp_obj):
        object_checks.has_keys(resp_obj, 'results', 'maxScore', obj_name='search_result')
        results = resp_obj['results']
        self.assertIsInstance(results, list)
        for item in results:
            object_checks.has_keys(item, 'id', 'entityType', 'streamingPlatform', 'data', 'score',
                                   obj_name='resultItem')

            if item['entityType'] == 'programme':
                self.check_programme_item(item['data'])
            elif item['entityType'] == 'special':
                self.check_special_item(item['data'])
            else:
                raise AssertionError('unknown entityType {}'.format(item['entityType']))
            self.assertTrue(item['data']['tier'] in ('PAID', 'FREE'))

    def check_programme_item(self, item_data):
        object_checks.has_keys(item_data, 'programmeCCId', 'legacyId', 'productionId', 'programmeTitle',
                               'synopsis', 'latestAvailableEpisode', 'totalAvailableEpisodes', 'tier',
                               obj_name='programItem.data')
        self.assertTrue(item_data['latestAvailableEpisode']['imageHref'].startswith('https://'))

    def check_special_item(self, item_data):
        object_checks.has_keys(item_data, 'specialCCId', 'legacyId', 'productionId', 'specialTitle',
                               'synopsis', 'imageHref', 'tier',
                               obj_name='specialItem.data')
        special_data = item_data.get('specialProgramme')
        # The field specialProgramme is not used by the addon, but if present we check it anyway
        if special_data:
            object_checks.has_keys(special_data, 'programmeCCId', 'legacyId', 'programmeTitle',
                                   obj_name='specialItem.data.specialProgramme')
        self.assertTrue(item_data['imageHref'].startswith('https://'))

    def test_search_normal(self):
        self.search_params['query'] = 'the chases'
        resp = requests.get(self.search_url, params=self.search_params).json()
        self.check_result(resp)
        self.assertGreater(len(resp['results']), 3)

    def test_search_without_result(self):
        self.search_params['query'] = 'xprs'
        resp = requests.get(self.search_url, params=self.search_params)
        self.assertEqual(204, resp.status_code)

    def test_search_with_non_free_results(self):
        """Results contain Doctor Foster programme which is can only be watch with a premium account."""
        self.search_params['query'] = 'doctor foster'
        resp = requests.get(self.search_url, params=self.search_params).json()
        self.check_result(resp)
        self.assertEqual('PAID', resp['results'][0]['data']['tier'])
