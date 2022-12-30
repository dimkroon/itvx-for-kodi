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


class TestCookies(unittest.TestCase):
    def test_cookie_consent(self):
        r = requests.Session()


# ----------------------------------------------------------------------------------------------------------------------
#           JSON API
# ----------------------------------------------------------------------------------------------------------------------


class Categories(unittest.TestCase):
    cat_req_kwargs = {
        'url': 'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/categories',
        'headers': {'Accept': 'application/vnd.itv.online.discovery.category.v1+hal+json; charset=UTF-8'}
    }

    def test_categories(self):
        json_resp = requests.get(**self.cat_req_kwargs).json()
        self.assertTrue('_embedded' in json_resp.keys())
        self.assertTrue('categories' in json_resp['_embedded'].keys())
        cat_list = json_resp['_embedded']['categories']
        self.assertIsInstance(cat_list, list)
        for item in cat_list:
            self.assertTrue('name' in item.keys())
            self.assertTrue('_links' in item.keys())
            self.assertTrue(item['_links']['doc:programmes']['href'].startswith('https://'))


class Collections(unittest.TestCase):
    cat_req_kwargs = {
        'url': 'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/collections',
        'headers': {'Accept': 'application/vnd.itv.online.discovery.collection.v1+hal+json; charset=UTF-8'}
    }

    def test_collection(self):
        resp = requests.get(**self.cat_req_kwargs)
        self.assertEqual(404, resp.status_code)


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

    def test_programs_category_factual(self):
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?'
                                  'category=Factual&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                  'playready,widevine&broadcaster=itv')
        self._validate_strcuture(json_resp)

    def test_programs_are_same_for_different_platforms(self):
        """Test if the number of programs differ for different platforms

        Initially they did not, but now dotcom returns a significant larger number (> 400) of programs than ctv.
        """
        dotcom_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?'
                                    'broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,'
                                    'widevine,fairplay&sortBy=title')
        ctv_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/ctv/programmes?'
                                 'broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,'
                                 'widevine,fairplay&sortBy=title')
        dot_com_programs = dotcom_resp['_embedded']['programmes']
        ctv_programs = ctv_resp['_embedded']['programmes']
        self.assertGreater(len(dot_com_programs), len(ctv_programs))


class Productions(unittest.TestCase):
    def get_json(self, url):
        resp = requests.get(
                url,
                headers={'Accept': 'application/vnd.itv.online.discovery.production.v1+hal+json; charset=UTF-8'}
        )
        return resp.json()

    def _validate_structure(self, productions_data):
        self.assertIsInstance(productions_data['count'], int)
        self.assertTrue('_embedded' in productions_data.keys())
        prod_list = productions_data['_embedded']['productions']
        self.assertIsInstance(prod_list, list)
        for prod in prod_list:
            self.assertTrue('productionId' in prod.keys())
            self.assertEqual(prod['productionType'], 'PROGRAMME')
            self.assertTrue('episodeId' in prod.keys())
            self.assertTrue('iso8601' in prod['duration'].keys())
            self.assertTrue('display' in prod['duration'].keys())
            self.assertTrue('commissioning' in prod['broadcastDateTime'].keys())
            self.assertTrue('epg' in prod['synopses'].keys())
            self.assertTrue('image' in prod['_links'].keys())
            self.assertTrue(prod['_links']['image']['templated'])
            self.assertTrue('href' in prod['_links']['image'].keys())
            self.assertTrue('href' in prod['_links']['playlist'].keys())
            self.assertTrue('playlist' in prod['_links'].keys())
            self.assertTrue('title' in prod['_embedded']['programme'])
            # The following key are optional, thus may not be present at all times
            # self.assertTrue('episodeTitle' in prod.keys())
            # self.assertTrue('series' in prod.keys(),
            #                 msg="key 'series' not present in production '{}'".format(prod['productionId']))
            # self.assertTrue('episode' in prod.keys())
            # self.assertTrue('guidance' in prod.keys())
            # self.assertTrue('original' in prod['broadcastDateTime'].keys())

    def test_productions_midsummer_murders(self):
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                  'programmeId=Y_1096&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                  'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

    def test_productions_2020_the_story_of_us(self):
        """The long call - 4 episodes

        A programme where individual production do not have an episodeTitle
        """
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                  'programmeId=2_6931&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                  'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

    def test_productions_the_thief_his_wife_and_the_canoe(self):
        """The thief, his wife and the canoe - 4 episodes

        A programme where individual production do not have an episodeTitle
        """
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                  'programmeId=10_1187&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                  'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

    def test_productions_coronation_street(self):
        """Coronation Street, several episodes

        A programme where individual episodes do not have keys 'series' and 'episode'
        """
        json_resp =  self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                   'programmeId=1_0694&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                   'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

    def test_productions_the_chase(self):
        """The program item showed 52 episodes, but the productions listing only showed 1 item

        """
        json_resp =  self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                   'programmeId=1_7842&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                   'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

# ----------------------------------------------------------------------------------------------------------------------
