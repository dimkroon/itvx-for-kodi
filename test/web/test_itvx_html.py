
# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import time
import unittest
import requests

from resources.lib import fetch, parsex, itv_account
from support import testutils
from support.object_checks import has_keys, misses_keys, is_url, is_iso_time


setUpModule = fixtures.setup_web_test


class MainPage(unittest.TestCase):
    def test_main_page(self):
        page = fetch.get_document('https://www.itv.com/')
        # testutils.save_doc(page, 'html/index.html')
        page_data = parsex.get__next__data_from_page(page)
        # testutils.save_json(page_data, 'html/index-data.json')
        page_props = page_data['props']['pageProps']
        has_keys(page_props, 'heroContent', 'editorialSliders', 'newsShortformSliderContent', 'trendingSliderContent')

        self.assertIsInstance(page_props['heroContent'], list)
        for item in page_props['heroContent']:
            has_keys(item, 'type', 'title', 'imageTemplate', 'programmeId', 'encodedEpisodeId',
                     'description', 'genre', 'contentInfo')
        pass

    def test_get_itvx_logo(self):
        resp = requests.get('https://app.10ft.itv.com/itvstatic/assets/images/brands/itvx/itvx-logo-for-light-backgrounds.jpg?q=80&format=jpg&w=960&h=540&bg=false&blur=0')
        self.assertEqual(200, resp.status_code)
        img = resp.content
        # testutils.save_binary(img, 'html/itvx-logo-light-bg.jpg')
        resp = requests.get('https://app.10ft.itv.com/itvstatic/assets/images/brands/itvx/itvx-logo-for-dark-backgrounds.jpg?q=80&format=jpg&w=960&bg=false&blur=0')
        self.assertEqual(200, resp.status_code)
        img = resp.content
        # testutils.save_binary(img, 'html/itvx-logo-dark-bg.jpg')


class WatchPages(unittest.TestCase):
    def check_schedule_now_next_slot(self, progr_data, chan_type, obj_name=None):
        """Check the now/next schedule data returned from an HTML page.
        It is very simular to the data returned by `nownext.oasvc.itv.com`, but not quite the same."""
        has_keys(progr_data, 'titleId', 'title', 'prodId', 'brandTitle', 'broadcastAt', 'guidance', 'rating',
                 'contentEntityType', 'episodeNumber', 'seriesNumber', 'startAgainPlaylistUrl', 'shortSynopsis',
                 'displayTitle', 'detailedDisplayTitle', 'timestamp',
                 'broadcastEndTimestamp', 'productionId', obj_name=obj_name)
        # These times are in a format like '2022-11-22T20:00Z'
        self.assertTrue(is_iso_time(progr_data['start']))
        self.assertTrue(is_iso_time(progr_data['end']))

        if chan_type == 'fast':
            misses_keys(progr_data, 'broadcastStartTimestamp')
            self.assertIsNone(progr_data['broadcastAt'])
            self.assertIsNone(progr_data['broadcastEndTimestamp'])

        if chan_type != 'fast':
            has_keys(progr_data, 'broadcastStartTimestamp' )
            self.assertTrue(is_iso_time(progr_data['broadcastAt']))
            # check timestamps are integers
            self.assertGreater(int(progr_data['broadcastStartTimestamp']), 0)
            self.assertGreater(int(progr_data['broadcastEndTimestamp']), 0)
        self.assertTrue(progr_data['startAgainPlaylistUrl'] is None or is_url(progr_data['startAgainPlaylistUrl']))

    def check_schedule_channel_info(self, channel_info):
        has_keys(channel_info, 'id', 'name', 'slug', 'slots', 'images', 'playlistUrl')
        self.assertTrue(is_url(channel_info['images']['logo'], '.png'))
        self.assertTrue(is_url(channel_info['playlistUrl']))
        self.assertTrue(channel_info['channelType'] in ('fast', 'simulcast'))

    def test_watch_live_itv1(self):
        """The jsonp data primarily contains now/next schedule of all live channels"""
        page = fetch.get_document("https://www.itv.com/watch?channel=itv")
        # testutils.save_doc(page, 'html/watch-itv1.html')
        data = parsex.get__next__data_from_page(page)
        channel_data = data['props']['pageProps']['channelsMetaData']
        # check presence and type of backdrop image
        self.assertTrue(len(channel_data['images']), 1)     # only backdrop image is available
        self.assertTrue(is_url(channel_data['images']['backdrop'], '.jpeg'))

        for chan in channel_data['channels']:
            chan_type = chan['channelType']
            self.check_schedule_channel_info(chan)
            self.check_schedule_now_next_slot(chan['slots']['now'], chan_type, obj_name='{}-Now-on'.format(chan['name']))
            self.check_schedule_now_next_slot(chan['slots']['next'], chan_type, obj_name='{}-Next-on'.format(chan['name']))


class TvGuide(unittest.TestCase):
    def test_guide_of_today(self):
        today = ''  # datetime.utcnow().strftime(('%Y-%m-%d'))
        url = 'https://www.itv.com/watch/tv-guide/' + today
        page = fetch.get_document(url)
        # testutils.save_doc(page, 'html/tv_guide.html')
        print(page)


class Categories(unittest.TestCase):
    all_categories = ['factual', 'drama-soaps', 'children', 'films', 'sport', 'comedy', 'news', 'entertainment']

    def test_get_available_gategories(self):
        """The page categories returns in fact already a full categorie page - the first page in the list
        of categories. Which categorie that is, may change.
        Maybe because of that it is much slower than requesting categories by gql.
        """
        t_s = time.time()
        page = fetch.get_document('https://www.itv.com/watch/categories')
        # testutils.save_doc(page, 'categories/categories.html')
        t_1 = time.time()
        data = parsex.get__next__data_from_page(page)
        categories = data['props']['pageProps']['subnav']['items']
        t_2 = time.time()
        for item in categories:
            has_keys(item, 'id', 'name', 'label', 'url')
            # url is the full path without domain
            self.assertTrue(item['url'].startswith('/watch/'))

        self.assertEqual(8, len(categories))        # the mobile app has an additional category AD (Audio Described)
        self.assertListEqual([cat['label'].lower().replace(' & ', '-') for cat in categories], self.all_categories)
        print('Categorie page fetched in {:0.3f}, parsed in {:0.3f}, total: {:0.3f}'.format(
            t_1 - t_s, t_2 - t_1, t_2 - t_s))

    def test_all_categories(self):
        for cat in self.all_categories:
            url = 'https://www.itv.com/watch/categories/children/' + cat
            t_s = time.time()
            page = fetch.get_document(url)
            t_1 = time.time()
            data = parsex.get__next__data_from_page(page)
            programmes = data['props']['pageProps']['programmes']
            t_2 = time.time()
            self.assertIsInstance(programmes, list)
            print("Fetched categorie {} in {:0.3f} s, parsed in {:0.3f}s, total {:0.3f}s.".format(
                cat, t_1 - t_s, t_2 - t_1, t_2 - t_s))
