
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.itvx
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import time
import unittest
import requests

from resources.lib import fetch, parsex, utils, errors
from support.object_checks import has_keys, misses_keys, is_url, is_iso_time
from support import testutils

setUpModule = fixtures.setup_web_test


def check_shows(self, show, parent_name):
    # Not always present: 'contentInfo'
    has_keys(show, 'contentType', 'title', 'description', 'titleSlug', 'imageTemplate', 'encodedEpisodeId',
             'encodedProgrammeId', obj_name='{}-show-{}'.format(parent_name, show['title']))
    self.assertTrue(show['contentType'] in ('series', 'brand', 'film', 'special', 'episode'), "{}: Unexpected title type '{}'.".format(
        '.'.join((parent_name, show['title'])), show['contentType']))
    is_url(show['imageTemplate'], '.png')


def check_brand(self, brand, parent_name):
    obj_name = '{}-{}'.format(parent_name, brand['title'])
    has_keys(brand, 'title', 'imageUrl', 'synopses', 'legacyId', 'availableEpisodeCount', 'guidance', 'series', 'tier',
             obj_name=obj_name)
    self.assertIsInstance(brand['series'], list)
    is_url(brand['imageUrl'])


def check_series(self, series, parent_name):
    obj_name = '{}-{}'.format(parent_name, series['title'])
    # Field 'legacyId' is not always present, but is not used anyway.
    has_keys(series, 'title', 'seriesNumber', 'seriesAvailableEpisodeCount', 'fullSeries', 'episodes',
             obj_name=obj_name)
    for episode in series['episodes']:
        check_episode(self, episode, obj_name)


def check_title(self, title, parent_name):
    obj_name = '{}-title-{}'.format(parent_name, title['episodeTitle'])
    has_keys(title, 'titleType', 'episodeTitle', 'broadcastDateTime', 'isChildrenCategory', 'legacyId', 'guidance',
             'imageUrl', 'playlistUrl', 'productionId', 'synopsis', 'tier', 'numberedEpisodeTitle',
             'isChildrenCategory', obj_name=obj_name)
    is_url(title['imageUrl'])
    is_url(title['playlistUrl'])
    self.assertIsNotNone(title['numberedEpisodeTitle'])

    if title['titleType'] in ('EPISODE', 'FILM'):
        self.assertFalse(title['duration'].startswith('P'))    # duration is not is iso format

    if title['titleType'] == 'FILM':
        has_keys(title, 'productionYear',
                 obj_name=obj_name)


def check_episode(self, episode, parent_name):
    obj_name = '{}-{}'.format(parent_name, episode['episodeTitle'])
    check_title(self, episode, parent_name)
    has_keys(episode, 'daysLeft', 'seriesNumber', 'episodeNumber', 'href', 'programmeTitle', obj_name=obj_name)


class MainPage(unittest.TestCase):
    def test_main_page(self):
        page = fetch.get_document('https://www.itv.com/')
        # testutils.save_doc(page, 'html/index.html')
        page_props = parsex.scrape_json(page)
        # testutils.save_json(page_props, 'html/index-data.json')
        has_keys(page_props, 'heroContent', 'editorialSliders', 'newsShortformSliderContent', 'trendingSliderContent')

        self.assertIsInstance(page_props['heroContent'], list)
        for item in page_props['heroContent']:
            has_keys(item, 'contentType', 'title', 'imageTemplate', 'description',
                     'contentInfo', 'tagName', obj_name=item['title'])
            self.assertTrue(item['contentType'] in ('simulcastspot', 'series', 'film', 'special'))

            if item['contentType'] != 'simulcastspot':
                has_keys(item, 'encodedProgrammeId', 'programmeId', 'genre', obj_name=item['title'])

            if item['contentType'] == 'special':
                has_keys(item, 'encodedEpisodeId', 'dateTime', 'duration', obj_name=item['title'])

            if item['contentType'] == 'series':
                has_keys(item, 'encodedEpisodeId', 'brandImageTemplate', 'series', obj_name=item['title'])

            if item['contentType'] == 'film':
                # Fields not always present:  'dateTime'
                has_keys(item, 'productionYear', 'duration', obj_name=item['title'])

        self.assertIsInstance(page_props['editorialSliders'], dict)
        for item in page_props['editorialSliders'].values():
            collection = item['collection']
            # , 'imageTreatment', 'imageAspectRatio', 'imageClass'
            has_keys(collection, 'headingTitle', 'shows',
                     obj_name='collection-' + collection['headingTitle'])
            for show in collection['shows']:
                check_shows(self, show, collection['headingTitle'])

        self.assertIsInstance(page_props['trendingSliderContent'], dict)
        self.assertTrue(page_props['trendingSliderContent']['header']['title'])
        for item in page_props['trendingSliderContent']['items']:
            has_keys(item, 'title', 'imageUrl', 'description', 'encodedProgrammeId', 'contentType',
                     'contentInfo', 'titleSlug', obj_name='trending-slider_' + item['title'])
            # Must have either an episode id when the underlying item is an episode, but there
            # is no way to check the item's type
            # has_keys(item, 'encodedEpisodeId', obj_name='trending-slider_' + item['title'])

        self.assertIsInstance(page_props['newsShortformSliderContent'], dict)
        for item in page_props['newsShortformSliderContent']['items']:
            # Field 'synopsys' may be absent occasionally.
            has_keys(item, 'episodeTitle', 'imageUrl', 'href', 'dateTime',
                     'titleSlug', obj_name='news-slider')
            self.assertFalse(is_url(item['href']))
            self.assertFalse(item['href'].startswith('/'))

    def test_get_itvx_logo(self):
        resp = requests.get('https://app.10ft.itv.com/itvstatic/assets/images/brands/itvx/itvx-logo-for-light-'
                            'backgrounds.jpg?q=80&format=jpg&w=960&h=540&bg=false&blur=0')
        self.assertEqual(200, resp.status_code)
        img = resp.content
        # testutils.save_binary(img, 'html/itvx-logo-light-bg.jpg')
        resp = requests.get('https://app.10ft.itv.com/itvstatic/assets/images/brands/itvx/itvx-logo-for-dark-'
                            'backgrounds.jpg?q=80&format=jpg&w=960&bg=false&blur=0')
        self.assertEqual(200, resp.status_code)
        img = resp.content
        # testutils.save_binary(img, 'html/itvx-logo-dark-bg.jpg')


class CollectionPage(unittest.TestCase):
    def test_collection_just_in(self):
        page = fetch.get_document('https://www.itv.com/watch/collections/just-in/2RQpkypwh3w8m6738sUHQH')
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/collection_just-in_data.json')
        shows = data['collection']['shows']
        for show in shows:
            check_shows(self, show, data['collection']['sliderName'])


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
            has_keys(progr_data, 'broadcastStartTimestamp')
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
        page = fetch.get_document('https://www.itv.com/watch?channel=itv')
        # testutils.save_doc(page, 'html/watch-itv1.html')
        data = parsex.scrape_json(page)
        channel_data = data['channelsMetaData']
        # check presence and type of backdrop image
        self.assertTrue(len(channel_data['images']), 1)     # only backdrop image is available
        self.assertTrue(is_url(channel_data['images']['backdrop'], '.jpeg'))

        for chan in channel_data['channels']:
            chan_type = chan['channelType']
            self.check_schedule_channel_info(chan)
            self.check_schedule_now_next_slot(chan['slots']['now'], chan_type,
                                              obj_name='{}-Now-on'.format(chan['name']))
            self.check_schedule_now_next_slot(chan['slots']['next'], chan_type,
                                              obj_name='{}-Next-on'.format(chan['name']))

    def test_series_page(self):
        for url in (
                'https://www.itv.com/watch/agatha-christies-marple/L1286',
                'https://www.itv.com/watch/bad-girls/7a0129',
                'https://www.itv.com/watch/midsomer-murders/Ya1096',
                ):
            page = fetch.get_document(url)
            # testutils.save_doc(page, 'html/series_bad-girls.html')
            data = parsex.scrape_json(page)
            # testutils.save_json(data, 'html/series_midsummer-murders.json')
            title_data = data['title']
            check_title(self, title_data, '')
            check_brand(self, title_data['brand'], '')
            for series in title_data['brand']['series']:
                check_series(self, series, title_data['brand']['title'])

    def test_film_details_page(self):
        page = fetch.get_document('https://www.itv.com/watch/danny-collins/10a3142')
        # testutils.save_doc(page, 'html/film_love-actually.html')
        data = parsex.scrape_json(page)
        check_title(self, data['title'], 'love-actually')


class TvGuide(unittest.TestCase):
    def test_guide_of_today(self):
        today = ''  # datetime.utcnow().strftime(('%Y-%m-%d'))
        url = 'https://www.itv.com/watch/tv-guide/' + today
        page = fetch.get_document(url)
        # testutils.save_doc(page, 'html/tv_guide.html')
        self.assertRaises(errors.ParseError,  parsex.scrape_json, page)


class Categories(unittest.TestCase):
    all_categories = ['factual', 'drama-soaps', 'children', 'films', 'sport', 'comedy', 'news', 'entertainment']

    def test_get_available_categories(self):
        """The page categories returns in fact already a full categorie page - the first page in the list
        of categories. Which categorie that is, may change.
        Maybe because of that it is much slower than requesting categories by gql.
        """
        t_s = time.time()
        page = fetch.get_document('https://www.itv.com/watch/categories')
        # testutils.save_doc(page, 'html/categories.html')
        t_1 = time.time()
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/categories_data.json')
        categories = data['subnav']['items']
        t_2 = time.time()
        for item in categories:
            has_keys(item, 'id', 'name', 'label', 'url')
            # url is the full path without domain
            self.assertTrue(item['url'].startswith('/watch/'))

        self.assertEqual(8, len(categories))        # the mobile app has an additional category AD (Audio Described)
        self.assertListEqual([cat['label'].lower().replace(' & ', '-') for cat in categories], self.all_categories)
        # print('Categorie page fetched in {:0.3f}, parsed in {:0.3f}, total: {:0.3f}'.format(
        #     t_1 - t_s, t_2 - t_1, t_2 - t_s))

    def test_all_categories(self):
        for cat in self.all_categories:
            url = 'https://www.itv.com/watch/categories/' + cat
            t_s = time.time()
            page = fetch.get_document(url)
            t_1 = time.time()
            data = parsex.scrape_json(page)
            # if cat == 'films':
            #     testutils.save_json(data, 'html/category_{}.json'.format(cat))
            programmes = data['programmes']
            t_2 = time.time()
            self.assertIsInstance(programmes, list)
            for progr in programmes:
                has_keys(progr, 'title', 'titleSlug', 'encodedProgrammeId', 'encodedEpisodeId', 'description',
                         'imageTemplate', 'contentInfo', 'contentOwner', 'tier')
                self.assertTrue(progr['encodedProgrammeId']['letterA'])
                self.assertIsNotNone(progr['encodedEpisodeId']['letterA'])
                self.assertTrue(progr['contentInfo'].lower().startswith('series') or
                                utils.duration_2_seconds(progr['contentInfo']) is not None)
            # print("Fetched categorie {} in {:0.3f} s, parsed in {:0.3f}s, total {:0.3f}s.".format(
            #     cat, t_1 - t_s, t_2 - t_1, t_2 - t_s))
