# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
import copy
import time

from datetime import datetime, timedelta, timezone

import requests

from resources.lib import itv_account
from resources.lib import fetch
from resources.lib import parsex
from resources.lib import itvx
from resources.lib import utils
from resources.lib import main
from test.support import object_checks
from test.support import testutils
from local.test_account import build_test_tokens


setUpModule = fixtures.setup_web_test

dftl_headers = {'User-Agent': fetch.USER_AGENT,
                'Origin': 'https://www.itv.com'}


class LiveSchedules(unittest.TestCase):
    """Request the live schedule
    No cookies or authentication required. Web browser doesn't either.

    """
    def check_schedule(self, start_dt, end_dt):
        t_fmt = '%Y%m%d%H%M'
        resp = requests.get(
                'https://scheduled.oasvc.itv.com/scheduled/itvonline/schedules?',
                params={'from': start_dt.strftime(t_fmt),
                        'to': end_dt.strftime(t_fmt),
                        # was 'ctv' until recently, maybe changed since itvX, doesn't seem to matter.
                        'platformTag': 'dotcom',
                        'featureSet': 'mpeg-dash,widevine'},
                headers={'Accept': 'application/vnd.itv.hubsvc.schedule.v2+vnd.itv.hubsvc.channel.v2+hal+json',
                         'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0',
                         'Origin': 'https://www.itv.com',
                         },
                timeout=60)     # Usually a 504 - Gateway Timeout is returned before that.
        resp.raise_for_status()
        data = resp.json()
        # testutils.save_json(data, 'schedule/live_4hrs.json')

        schedule = data['_embedded']['schedule']
        self.assertEqual(6, len(schedule))      # only the 6 main channels are present in the schedule
        for channel_data in schedule:
            programs = channel_data['_embedded']['slot']
            for program in programs:
                object_checks.has_keys(program, 'programmeTitle', 'startTime', 'onAirTimeUTC', 'productionId')
                # start time is in a format like '2022-11-22T20:00Z'
                self.assertTrue(program['startTime'].endswith('Z') or program['startTime'].endswith('+01:00'))
                # Ascertain startTime has no seconds
                if program['startTime'].endswith('Z'):
                    self.assertEqual(17, len(program['startTime']))
                else:
                    self.assertEqual(22, len(program['startTime']))
            channel_info = channel_data['_embedded']['channel']
            object_checks.has_keys(channel_info, 'name', 'strapline', '_links')
            self.assertTrue(channel_info['_links']['playlist']['href'].startswith('https'))
        return schedule

    def test_main_channels_schedules_4hrs(self):
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=4)
        self.check_schedule(now, end)

    def test_now_next(self):
        resp = requests.get('https://nownext.oasvc.itv.com/channels')
        data = resp.json()
        # testutils.save_json(data, 'schedule/now_next.json')
        object_checks.has_keys(data, 'channels', 'images', 'ts')

        self.assertTrue(data['images']['backdrop'].startswith('https://'))
        self.assertTrue(data['images']['backdrop'].endswith('.jpeg'))

        self.assertAlmostEqual(20, len(data['channels']), delta=5)
        for chan in data['channels']:
            item_name = "now-next.{}".format(chan.get('name', "unknown channel"))
            object_checks.has_keys(chan, 'id', 'editorialId', 'channelType', 'name', 'streamUrl', 'slots', 'images',
                                   'slug', 'isKidsChannel', obj_name=item_name)
            self.assertTrue(chan['channelType'] in ('simulcast', 'fast'))
            if chan['channelType'] == 'fast':
                object_checks.has_keys(chan, 'channelDescription', 'channelTitle', obj_name=item_name)

            for program in (chan['slots']['now'], chan['slots']['next']):
                progr_keys = ('titleId', 'prodId', 'contentEntityType', 'start', 'end', 'title',
                              'brandTitle', 'displayTitle', 'detailedDisplayTitle', 'broadcastAt', 'guidance',
                              'rating', 'episodeNumber', 'seriesNumber', 'startAgainVod',
                              'startAgainSimulcast', 'shortSynopsis')
                object_checks.has_keys(program, *progr_keys)
                if program['displayTitle'] is None:
                    # If displayTitle is None all other fields are None or False as well.
                    # Noticed first 25-6-2023, on the FAST channels that were no longer available
                    # Since May 2024 a channel name 'ITV Sport' has empty data.
                    for k in progr_keys:
                        self.assertFalse(program[k])
                    self.assertTrue(chan['name'].lower() in ('itv sport', ))
                else:
                    self.assertTrue(object_checks.is_iso_utc_time(program['start']))
                    self.assertTrue(object_checks.is_iso_utc_time(program['end']))
                    if program['broadcastAt'] is not None:      # is None on fast channels
                        self.assertTrue(object_checks.is_iso_utc_time(program['broadcastAt']))


class Search(unittest.TestCase):
    def setUp(self) -> None:
        self.search_url = 'https://textsearch.prd.oasvc.itv.com/search'
        self.search_params = {
            'broadcaster': 'itv',
            'channelType': 'simulcast',
            'featureSet': 'clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay,bbts,progressive,hd,rtmpe',
            'onlyFree': 'false',
            'platform': 'dotcom',
            'pretx': 'true',
            'size': '24'
        }.copy()

    def check_result(self, resp_obj):
        object_checks.has_keys(resp_obj, 'results', 'maxScore', obj_name='search_result')
        results = resp_obj['results']
        self.assertIsInstance(results, list)
        for item in results:
            object_checks.has_keys(item, 'id', 'contentType', 'streamingPlatform', 'data', 'score',
                                   obj_name='resultItem')
            if item['contentType'] == 'live':
                self.assertEqual('simulcast', item['channelType'])  # Flag if other types like fast turn up.
                object_checks.misses_keys(item, 'entityType', obj_name='resultItem')
                self.check_simulcast_item(item['data'])
            else:
                self.assertEqual('vod', item['contentType'])
                if item['entityType'] == 'programme':
                    self.check_programme_item(item['data'])
                elif item['entityType'] == 'special':
                    self.check_special_item(item['data'])
                elif item['entityType'] == 'film':
                    self.check_film_item(item['data'])
                else:
                    raise AssertionError('unknown entityType {}'.format(item['entityType']))
                self.assertTrue(item['data']['tier'] in ('PAID', 'FREE'))

    def check_programme_item(self, item_data):
        object_checks.has_keys(item_data, 'programmeCCId', 'legacyId', 'productionId', 'programmeTitle',
                               'synopsis', 'latestAvailableEpisode', 'totalAvailableEpisodes', 'tier',
                               obj_name='programItem.data')
        object_checks.is_url(item_data['latestAvailableEpisode']['imageHref'])
        self.assertTrue(object_checks.is_not_empty(item_data['legacyId']['apiEncoded'], str))
        self.assertFalse('/' in item_data['legacyId']['apiEncoded'])

    def check_special_item(self, item_data):
        object_checks.has_keys(item_data, 'specialCCId', 'legacyId', 'productionId', 'specialTitle',
                               'synopsis', 'imageHref', 'tier',
                               obj_name='specialItem.data')

        # The field specialProgramme is not always present
        special_data = item_data.get('specialProgramme')
        if special_data:
            object_checks.has_keys(special_data, 'programmeCCId', 'legacyId', 'programmeTitle',
                                   obj_name='specialItem.data.specialProgramme')
            self.assertTrue(object_checks.is_not_empty(special_data['legacyId']['apiEncoded'], str))
            self.assertFalse('/' in special_data['legacyId']['apiEncoded'])
        else:
            self.assertTrue(object_checks.is_not_empty(item_data['legacyId']['apiEncoded'], str))
            # Check this programmeId has 2 underscores, since it is in fact more like an episodeId.
            self.assertEqual(2, item_data['legacyId']['apiEncoded'].count('_'))
        self.assertTrue(object_checks.is_url(item_data['imageHref']))

    def check_film_item(self, item_data):
        object_checks.has_keys(item_data, 'filmCCId', 'legacyId', 'productionId', 'filmTitle',
                               'synopsis', 'imageHref', 'tier',
                               obj_name='specialItem.data')
        self.assertTrue(object_checks.is_url(item_data['imageHref']))
        self.assertTrue(object_checks.is_not_empty(item_data['legacyId']['apiEncoded'], str))
        self.assertFalse('/' in item_data['legacyId']['apiEncoded'])

    def check_simulcast_item(self, item_data):
        object_checks.has_keys(item_data, 'startDateAndTime', 'endDateAndTime', 'channelId', 'channelName',
                               'channelType', 'titleCCId', 'brandTitle', 'imageHref', 'tileImageHref', 'isLive',
                               'synopsis', obj_name='simulcast.data')
        self.assertTrue(object_checks.is_url(item_data['imageHref']))
        self.assertTrue(object_checks.is_not_empty(item_data['channelName'], str))
        self.assertTrue(object_checks.is_not_empty(item_data['channelId'], str))
        self.assertTrue(object_checks.is_not_empty(item_data['synopsis'], str))
        self.assertTrue(object_checks.is_iso_utc_time(item_data['startDateAndTime']))   # Note 'And' in the field name
        self.assertTrue(object_checks.is_iso_utc_time(item_data['endDateAndTime']))

    def test_search_normal_chase(self):
        self.search_params['query'] = 'the chase'
        resp = requests.get(self.search_url, params=self.search_params)
        data = resp.json()
        self.check_result(data)
        self.assertGreater(len(data['results']), 3)

    def test_search_normal_monday(self):
        self.search_params['query'] = 'monday'
        resp = requests.get(self.search_url, params=self.search_params).json()
        # testutils.save_json(resp, 'search/search_monday.json')
        self.check_result(resp)
        self.assertGreater(len(resp['results']), 3)

    def test_search_with_simulcast_result(self):
        self.search_params['query'] = 'itv1'
        resp = requests.get(self.search_url, params=self.search_params).json()
        self.check_result(resp)
        self.assertGreater(len(resp['results']), 3)

    def test_search_without_result(self):
        """Typical itvX behaviour; response can be either HTTP status 204 - No Content,
        or status 200 - OK with empty results list."""
        self.search_params['query'] = 'xprs'
        resp = requests.get(self.search_url, params=self.search_params)
        self.assertTrue(resp.status_code in (200, 204))
        if resp.status_code == 200:
            self.assertListEqual([], resp.json()['results'])

    def test_search_foster_with_paid_results(self):
        """Results contains a Doctor Foster programme, which can only be watched with a premium account."""
        # Search including paid
        self.search_params['query'] = 'doctor foster'
        resp = requests.get(self.search_url, self.search_params, headers={'accept': 'application/json'})
        data = resp.json()
        self.check_result(data)
        # Ensure premium result are present.
        self.assertTrue(any('PAID' == result['data']['tier'] for result in data['results']))

        # Check if the (now legacy) parameter 'onlyFree' filters premium content from the resutls
        self.search_params['onlyFree'] = 'true'
        resp = requests.get(self.search_url, self.search_params, headers={'accept': 'application/json'})
        data = resp.json()
        self.check_result(data)
        # Ensure premium result are still present.
        self.assertTrue(any('PAID' == result['data']['tier'] for result in data['results']))


class MyList(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.token = itv_account.itv_session().access_token
        cls.userid = itv_account.itv_session().user_id
        # Query parameters features and platform are required!!
        # NOTE:
        #   Platform dotcom may return fewer items than mobile and ctv.
        #   The website now uses platform dotcom,but has been using ctv for quite some time.
        cls.mylist_url = ('https://my-list.prd.user.itv.com/user/{}/mylist?features=mpeg-dash,outband-webvtt,'
                          'hls,aes,playready,widevine,fairplay,progressive&platform=ctv&size=52').format(cls.userid)
        # Both webbrowser and app authenticate with a header, no cookies required.
        cls.headers = {'authorization': 'Bearer ' + cls.token}

    def test_get_my_list_no_content_type(self):
        """Request My List without specifying the content-type

        """
        resp = requests.get(self.mylist_url, headers=self.headers)
        data = resp.json()
        # testutils.save_json(data, 'mylist/mylist_data.json')

        # When no particular type of content is requested a dict is returned
        self.assertIsInstance(data, dict)
        self.assertEqual(resp.headers['content-type'], 'application/vnd.itv.online.perso.my-list.v1+json')

        watched = data['items']
        self.assertEqual(data['availableSlots'], 52 - len(watched))
        if len(watched) == 0:
            print("WARNING - No LastWatched items")
        for item in watched:
            object_checks.has_keys(item, 'categories', 'contentType', 'contentOwner', 'dateAdded', 'duration',
                                   'imageLink', 'itvxImageLink', 'longRunning', 'numberOfAvailableSeries',
                                   'numberOfEpisodes', 'partnership', 'programmeId', 'programmeTitle', 'synopsis',
                                   'tier', obj_name=item['programmeTitle'])
            self.assertTrue(item['contentType'].lower() in main.callb_map.keys())
            self.assertIsInstance(item['numberOfAvailableSeries'], list)
            self.assertIsInstance(item['numberOfEpisodes'], (int, type(None)))
            self.assertTrue(item['tier'] in ('FREE', 'PAID'))

    def test_get_my_list_content_type_json(self):
        """Request My List with content-type = application/json"""
        headers = self.headers.copy()
        headers['accept'] = 'application/json'
        resp = requests.get(self.mylist_url, headers=headers)
        data = resp.json()
        # testutils.save_json(data, 'usercontent/mylist_json_data.json')

        self.assertIsInstance(data, list)
        self.assertEqual(resp.headers['content-type'], 'application/json')

    def test_add_and_remove_programme(self):
        """At present only programmes can be added to the list, no individual episodes.

        Itv always returns HTTP status 200 when a syntactical valid request has been made. However,
        that is no guarantee that the requested programme is in fact added to My List.

        .. note ::
            ITV now accepts ccid's as well as legacy programme ID's

        """
        progr_id = '2_7931'            # a spy among friends
        episode_id = '2_7931_0001_001'
        qs = '?features=mpeg-dash,outband-webvtt,hls,aes,playready,widevine,fairplay,progressive&platform=ctv&size=52'
        url = 'https://my-list.prd.user.itv.com/user/{}/mylist/programme/{}'.format(self.userid, progr_id, episode_id)

        # Without querystring the response is 201-Created without content
        # Note: The presence of query argument 'size' does not affect the response.
        resp = requests.post(url, headers=self.headers)
        self.assertEqual(201, resp.status_code)
        self.assertEqual(b'', resp.content)

        # With querystring the response is 200-OK with the new list in the body,
        # but it takes a bit longer to complete.
        url = url + qs
        resp = requests.post(url, headers=self.headers)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        pgm_ids = [item['programmeId'].replace('/', '_') for item in data['items']]
        self.assertTrue(progr_id in pgm_ids)

        # Add an already added programme again
        resp = requests.post(url, headers=self.headers)
        self.assertEqual(200, resp.status_code)

        # Delete a programme
        resp = requests.delete(url, headers=self.headers)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        pgm_ids = [item['programmeId'].replace('/', '_') for item in data['items']]
        self.assertFalse(progr_id in pgm_ids)

        # Delete a programme that is not on the list
        resp = requests.delete(url, headers=self.headers)
        self.assertEqual(200, resp.status_code)


class LastWatched(unittest.TestCase):
    def check_vnd_user_content_v1_json(self, data):
        """Check the data returned by lastwatched
        - EpisodeNumber and ProgrammeNumber can be None, even in data of type EPISODE
        - tier is of type string, instead of the usual list
        """
        self.assertIsInstance(data, list)
        for item in data:
            object_checks.has_keys(
                item, 'availabilityEnd', "broadcastDatetime", "contentType", "duration",
                "episodeNumber", "episodeTitle", "isNextEpisode", "itvxImageLink", "percentageWatched",
                "productionId", "programmeTitle", "seriesNumber", "synopsis", "tier", "viewedOn", "programmeId",
                obj_name=item['programmeTitle'])

            object_checks.expect_keys(item, 'categories', "channel", "channelLink", "contentOwner", "imageLink",
                                      "episodeId", "longRunning", "partnership",
                                      obj_name='Watching: {}'.format(item['programmeTitle']))
            self.assertTrue(item['contentType'] in ('EPISODE', 'FILM', 'SPECIAL'))
            self.assertTrue(object_checks.is_iso_utc_time(item['availabilityEnd']))
            self.assertTrue(object_checks.is_iso_utc_time(item['broadcastDatetime']))
            self.assertTrue(object_checks.is_not_empty(item['episodeId'], str))
            self.assertTrue(object_checks.is_not_empty(item['isNextEpisode'], bool))
            self.assertTrue(object_checks.is_url(item['itvxImageLink']))
            self.assertTrue(object_checks.is_url(item['itvxImageLink']))
            self.assertTrue(object_checks.is_not_empty(item['percentageWatched'], float))
            self.assertLessEqual(item['percentageWatched'], 1.0)
            self.assertTrue(object_checks.is_not_empty(item['productionId'], str))
            self.assertTrue(object_checks.is_not_empty(item['programmeTitle'], str))
            self.assertTrue(object_checks.is_not_empty(item['synopsis'], str))
            # Tier is usually of type list, but is string here. The parser accepts both
            self.assertTrue(object_checks.is_not_empty(item['tier'], str))
            self.assertTrue(object_checks.is_iso_utc_time(item['viewedOn']))
            self.assertTrue(object_checks.is_iso_utc_time(item['availabilityEnd']))
            self.assertTrue(object_checks.is_not_empty(item['programmeId'], str))

            if item['contentType'] == 'EPISODE':
                # Some episodes' series and/or episode number are None, e.g. episodes of The Chase
                object_checks.has_keys(item, 'seriesNumber', 'episodeNumber')

            if item['contentType'] == 'FILM':
                self.assertIsNotNone(utils.iso_duration_2_seconds(item['duration']))
            elif item['contentType'] == 'SPECIAL':
                self.assertTrue(utils.iso_duration_2_seconds(item['duration']) or item['duration'] is None)
            else:
                self.assertIsNone(item['duration'])

    def test_get_last_watched(self):
        """Get last watch without specifying accept header returns content-type application/json,
        with exactly the same content as the original application/vnd.user.content.v1+json.
        """
        url = 'https://content.prd.user.itv.com/lastwatched/user/{}/ctv?features=mpeg-dash,outband-webvtt,' \
              'hls,aes,playready,widevine,fairplay,progressive'.format(itv_account.itv_session().user_id)
        headers = {'authorization': 'Bearer ' + itv_account.itv_session().access_token,
                   'accept': 'application/vnd.user.content.v1+json'}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        # testutils.save_json(data, 'usercontent/last_watched.json')
        self.assertEqual('application/vnd.user.content.v1+json', resp.headers['content-type'])
        self.check_vnd_user_content_v1_json(data)

    def test_get_last_watched_without_accept_type(self):
        """Get last watch without specifying accept header returns content-type application/json,
        with exactly the same content as the original application/vnd.user.content.v1+json.
        """
        url = 'https://content.prd.user.itv.com/lastwatched/user/{}/ctv?features=mpeg-dash,outband-webvtt,' \
              'hls,aes,playready,widevine,fairplay,progressive'.format(itv_account.itv_session().user_id)
        headers = {'authorization': 'Bearer ' + itv_account.itv_session().access_token}
        resp = requests.get(url, headers=headers)
        self.assertEqual('application/json', resp.headers['content-type'])
        data = resp.json()
        self.check_vnd_user_content_v1_json(data)

    def test_get_resume_time_of_production(self):
        """Get the resume point if a production

        NOTE:
            The content type returned by ITV is the same type as returned by last watched,
            though the content is quite different.

        """
        # Get the productionId of the first last-watched programme
        url = 'https://content.prd.user.itv.com/lastwatched/user/{}/ctv?features=mpeg-dash,outband-webvtt,' \
              'hls,aes,playready,widevine,fairplay,progressive'.format(itv_account.itv_session().user_id)
        last_watched = itv_account.fetch_authenticated(fetch.get_json, url)
        prod_id = None
        for item in last_watched:
            # Find the first programme that has a resume point
            if not item['isNextEpisode']:
                prod_id = item['productionId'].replace('/', '_').replace('#', '.')
                break
        self.assertIsNotNone(prod_id, "No Last watched programme available that can be resumed")

        url = 'https://content.prd.user.itv.com/resume/user/{}/productionid/{}'.format(
            itv_account.itv_session().user_id,
            prod_id)
        headers = {'authorization': 'Bearer ' + itv_account.itv_session().access_token,
                   'accept': 'application/vnd.user.content.v1+json'}
        resp = requests.get(url, headers=headers)
        self.assertEqual('application/vnd.user.content.v1+json', resp.headers['content-type'])
        data = resp.json()
        # testutils.save_json(data, 'usercontent/resume_point.json')

        object_checks.has_keys(data, 'progress', 'tier', 'timestamp')
        self.assertIsInstance(data['progress']['percentage'], float)
        self.assertIsInstance(data['progress']['time'], str)
        # Ascertain that time is in a format HH:MM:SS.ms - with seconds as float, rather than the
        # unusual format HH:MM:SS:ms returned by playlists.
        self.assertEqual(3, len(data['progress']['time'].split(':')))

        # Request without specifying accept content type return type application/json, but the data is the same.
        del headers['accept']
        resp = requests.get(url, headers=headers)
        self.assertEqual('application/json', resp.headers['content-type'])
        self.assertDictEqual(data, resp.json())


class Recommended(unittest.TestCase):
    def setUp(self) -> None:
        self.userid = itv_account.itv_session().user_id
        self.headers = {'accept': 'application/json'}

    def get_features(self, **kwargs):
        base_features = {
            'features': 'mpeg-dash,outband-webvtt,hls,aes,playready,widevine,fairplay,progressive',
            'platform': 'dotcom',
            'size': 12,
            'broadcaster': 'ITV'}
        features = base_features.copy()
        if kwargs.get('platform') == 'web':
            del kwargs['platform']
        features.update({k: v for k, v in kwargs.items()})
        return features

    def test_get_recommendations_byw(self):
        """Because You Watched - recommendations based on the (last) watched programme
        Requires userid, but no login."""
        url = 'https://recommendations.prd.user.itv.com/recommendations/byw/' + self.userid
        resp = requests.get(url, headers=self.headers, params=self.get_features(version=2), allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        self.assertEqual('application/json', resp.headers['content-type'])
        data = resp.json()
        # testutils.save_json(data, 'usercontent/byw.json')
        self.assertTrue(object_checks.is_not_empty(data['watched_programme'], str))
        recommendations_1 = data['recommendations']
        self.assertTrue(12, len(recommendations_1))
        for progr in recommendations_1:
            object_checks.check_item_type_programme(self, progr, 'BecauseYouWatched')

        # tier=PAID
        resp = requests.get(url, headers=self.headers,
                            params=self.get_features(version=2, tier='PAID'), allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(recommendations_1, data['recommendations'])

        # without specifying content-type
        resp = requests.get(url, params=self.get_features(version=2), allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        self.assertEqual('application/json', resp.headers['content-type'])

        # invalid user ID
        url = 'https://recommendations.prd.user.itv.com/recommendations/byw/none'
        resp = requests.get(url, headers=self.headers, params=self.get_features(version=2), allow_redirects=False)
        self.assertEqual(204, resp.status_code)

    def test_recommendations_homepage(self):
        """Regular recommendations place on the home page."""
        url = 'https://recommendations.prd.user.itv.com/recommendations/homepage/' + self.userid
        resp = requests.get(url, headers=self.headers, params=self.get_features(version=3), allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        self.assertEqual('application/json', resp.headers['content-type'])
        data = resp.json()
        for progr in data:
            object_checks.check_item_type_programme(self, progr, 'Recommended')
        # testutils.save_json(data, 'usercontent/recommended.json')
        self.assertTrue(12, len(data))

        # tier=PAID
        resp = requests.get(url, headers=self.headers,
                            params=self.get_features(version=2, tier='PAID'), allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        paid_data = resp.json()
        self.assertEqual(data, paid_data)

    def test_recommendations_homepage_with_invalid_userid(self):
        url = 'https://recommendations.prd.user.itv.com/recommendations/homepage/none'
        resp = requests.get(url, headers=self.headers, params=self.get_features(version=3), allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        self.assertTrue(12, len(data))
        for progr in data:
            object_checks.check_item_type_programme(self, progr, 'Recommended')

    def test_recommendations_homepage_without_invalid_userid(self):
        url = 'https://recommendations.prd.user.itv.com/recommendations/homepage/'
        resp = requests.get(url, headers=self.headers, params=self.get_features(version=3), allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        self.assertTrue(12, len(data))
        for progr in data:
            object_checks.check_item_type_programme(self, progr, 'Recommended')

    def test_recommendatation_homepage_more_items(self):
        # request more than 12 items
        url = 'https://recommendations.prd.user.itv.com/recommendations/homepage/' + self.userid
        resp = requests.get(url, headers=self.headers,
                            params=self.get_features(version=3, size=24),
                            allow_redirects=False)
        data = resp.json()
        self.assertTrue(24, len(data))
        for progr in data:
            object_checks.check_item_type_programme(self, progr, 'Recommended')

    def test_recommendations_homepage_mobile(self):
        """This request fails without an apikey header"""
        url = 'https://api.itv/hub/recommendations/homepage/' + self.userid
        resp = requests.get(url, headers=self.headers,
                            params=self.get_features(platform='mobile', version=3),
                            allow_redirects=False)
        self.assertEqual(401, resp.status_code)

# ----------------------------------------------------------------------------------------------------------------------


web_req_data = {
    'client': {
        'id': 'browser',
        'supportsAdPods': False,
        'version': ''
    },
    'device': {
        'manufacturer': 'Firefox',
        'model': '1127',
        'os': {
            'name': 'Linux',
            'type': 'desktop',
            'version': 'x86_64'
        }
    },
    'user': {
        'token': ''
    },
    'variantAvailability': {
        'drm': {
            'maxSupported': 'L3',
            'system': 'widevine'
        },
        'featureset': ['mpeg-dash', 'widevine', 'outband-webvtt', 'hd', 'single-track'],
        'platformTag': 'dotcom',
        'player': 'dash'
    }
}

mobile_req_data = {
  "client": {
    "id": "android",
    "service": "itv.x",
    "supportsAdPods": False,
    "version": "0.6.0"
  },
  "device": {
    "advertisingIdentifier": "00000000-0000-0000-0000-000000000000",
    "firmware": "22",
    "id": "xplayer",
    "manufacturer": "",
    "model": "",
    "os": {
      "name": "android",
      "type": "android",
      "version": "12.0"
    }
  },
  "preview": False,
  "user": {
    "entitlements": [],
    "itvUserId": "",
    "status": "reg",
    "subscribed": "false",
    "token": ""
  },
  "variantAvailability": {
    "featureset": {},
    "platformTag": "ctv"
  }
}

freeview_req_data = {
    "client": {
        "id": "freeview",
        "isp": {},
        "supportsAdPods": True,
        "appVersion": "3.564.0",
        "version": "3.564.0",
        "service": "itv.x",
        "thirdPartyPaymentModel": "free",
        "ssaiClientSdkVersion": "3"
    },
    "device": {
        "manufacturer": "LG",
        "model": "oled77g36la",
        "os": {"name": "oled77g36la"}
    },
    "user": {"token": ""},
    "variantAvailability": {
        "featureset": {},
        "platformTag": "ctv",
        "drm": {"system": "widevine", "maxSupported": "L3"}
    }
}

features_live = {
    "min": [
        "mpeg-dash",
        "widevine",
      ],
    "max": [
        "hd",
        "mpeg-dash",
        "widevine",
        "inband-webvtt"
    ]
}

features_catchup = ['mpeg-dash', 'widevine', 'outband-webvtt', 'hd', 'single-track']


class Playlists(unittest.TestCase):
    manifest_headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
        'Origin': 'https://www.itv.com'}

    @classmethod
    def setUpClass(cls):
        cls.acc_data = itv_account.itv_session()
        cls.acc_data.refresh()

    def create_post_data(self, stream_type, platform='freeview'):
        req_data = {
            'web': web_req_data,
            'mobile': mobile_req_data,
            'freeview': freeview_req_data
        }.get(platform)
        post_data = copy.deepcopy(req_data)
        post_data['user']['token'] = self.acc_data.access_token
        post_data['client']['supportsAdPods'] = True

        if stream_type == 'live':
            post_data['variantAvailability']['featureset'] = features_live
        else:
            post_data['variantAvailability']['featureset'] = features_catchup
        return post_data

    def get_playlist_live(self, channel, platform='freeview', query_str=''):
        """Get the playlist of one of the itvx live channels

        For all channels no other headers than User Agent and Origin are required.
        If any of those are missing the request will time out.

        Since accessToken is provided in the body, authentication by cookie or header is not needed.
        """
        post_data = self.create_post_data('live', platform)

        url = 'https://simulcast.itv.com/playlist/itvonline/' + channel + query_str
        resp = requests.post(
            url,
            headers={
                'Accept': 'application/vnd.itv.online.playlist.sim.v3+json',
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                'Origin': 'https://www.itv.com'},
            json=post_data, timeout=10)
        strm_data = resp.json()
        return strm_data

    def get_manifest_live(self, channel, platform):
        """Get the manifest from the start-again url"""
        playlist = self.get_playlist_live(channel, platform)
        start_again_url = playlist['Playlist']['Video']['VideoLocations'][0]['StartAgainUrl']
        start_time = datetime.now(timezone.utc) - timedelta(seconds=3600)
        mpd_url = start_again_url.format(START_TIME=start_time.strftime('%Y-%m-%dT%H:%M:%S'))
        resp = requests.get(mpd_url, headers=self.manifest_headers, timeout=10)
        manifest = resp.text
        return manifest

    def test_get_playlist_simulcast_web(self):
        for channel in ('ITV', 'ITV2', 'ITV3', 'ITV4', 'ITVBe'):
            strm_data = self.get_playlist_live(channel, 'web')
            # testutils.save_json(strm_data, 'playlists/pl_itv1.json')
            object_checks.check_live_stream_info(strm_data['Playlist'], full_hd=False)

    def test_get_playlist_simulcast_freeview(self):
        for channel in ('ITV', 'ITV2', 'ITV4'):
            strm_data = self.get_playlist_live(channel, 'freeview')
            # testutils.save_json(strm_data, 'playlists/pl_itv1.json')
            object_checks.check_live_stream_info(strm_data['Playlist'], full_hd=True)
        for channel in ('ITV3', 'ITVBe'):
            strm_data = self.get_playlist_live(channel, 'freeview')
            object_checks.check_live_stream_info(strm_data['Playlist'], full_hd=False)
            self.assertFalse(strm_data['Playlist']['Video']['VideoLocations'][0]['IsDar'])

    def test_playlist_live_regional_freeview(self):
        strm_data = self.get_playlist_live('ITV', 'freeview')
        url = strm_data['Playlist']['Video']['VideoLocations'][0]['StartAgainUrl']
        self.assertTrue('/itv1/' in url)
        strm_data = self.get_playlist_live('ITV', 'freeview', '?region=granada')
        url = strm_data['Playlist']['Video']['VideoLocations'][0]['StartAgainUrl']
        self.assertTrue('/itv1-gran/' in url)

    def test_playlist_live_regional_web(self):
        strm_data = self.get_playlist_live('ITV', 'web')
        url = strm_data['Playlist']['Video']['VideoLocations'][0]['StartAgainUrl']
        self.assertTrue('/itv1/' in url)
        strm_data = self.get_playlist_live('ITV', 'web', '?region=granada')
        url = strm_data['Playlist']['Video']['VideoLocations'][0]['StartAgainUrl']
        # Region has no effect on web streams
        self.assertFalse('/itv1-gran/' in url)
        self.assertTrue('/itv1/' in url)

    def test_get_playlist_fast_web(self):
        for chan_id in (5, 20):
            channel = 'FAST{}'.format(chan_id)
            strm_data = self.get_playlist_live(channel, 'web')
            # if chan_id == 20:
            #     testutils.save_json(strm_data, 'playlists/pl_fast_non_dar.json')
            object_checks.check_live_stream_info(strm_data['Playlist'], full_hd=False)
            if chan_id == 20:
                # FAST20 - GoUSA TV is always non-dar
                self.assertFalse(strm_data['Playlist']['Video']['VideoLocations'][0]['IsDar'])
            else:
                self.assertTrue(strm_data['Playlist']['Video']['VideoLocations'][0]['IsDar'])

    def test_get_playlist_fast_freeview(self):
        """Freeview fast channels are 720p by default"""
        for chan_id in (5, 20):
            channel = 'FAST{}'.format(chan_id)
            strm_data = self.get_playlist_live(channel, 'freeview')
            object_checks.check_live_stream_info(strm_data['Playlist'], full_hd=False)
            # All freeview live streams are non-dar
            self.assertFalse(strm_data['Playlist']['Video']['VideoLocations'][0]['IsDar'])

    def test_manifest_live_simulcast_web(self):
        manifest = self.get_manifest_live('ITV', 'web')
        # testutils.save_doc(manifest, 'mpd/itv1.mpd')
        max_res = object_checks.check_dash_manifest(self, manifest)
        self.assertEqual(720, max_res)

    def test_manifest_live_simulcast_freeview(self):
        manifest = self.get_manifest_live('ITV', 'freeview')
        max_res = object_checks.check_dash_manifest(self, manifest)
        self.assertEqual(1080, max_res)

    def test_manifest_live_FAST(self):
        """NOTE: FAST channels change frequently, some channels may not return a valid manifest."""
        for chan in ('5', '16', '20'):
            manifest = self.get_manifest_live('FAST' + chan, 'web')
            max_res = object_checks.check_dash_manifest(self, manifest)
            self.assertEqual(720, max_res)
            manifest = self.get_manifest_live('FAST' + chan, 'freeview')
            max_res = object_checks.check_dash_manifest(self, manifest)
            self.assertEqual(720, max_res)

    def test_force_freeview_full_hd(self):
        """On freeview only the ITV1, ITV2 and ITV4 are in full HD by default.
        Test if we can obtain the other channels in 1080P as well by replacing
        'ctv_low' with 'ctv' in the manifest url.

        .. note ::
            Fast channels change often and some might not be available any more.
        """
        for channel in ('ITV3', 'FAST5', 'FAST20'):
            playlist = self.get_playlist_live(channel, 'freeview')
            start_again_url = playlist['Playlist']['Video']['VideoLocations'][0]['StartAgainUrl']
            self.assertTrue('ctv-low.mpd' in start_again_url)
            start_time = datetime.now(timezone.utc) - timedelta(seconds=3600)
            mpd_url = (start_again_url.replace('ctv-low', 'ctv').
                       format(START_TIME=start_time.strftime('%Y-%m-%dT%H:%M:%S')))
            resp = requests.get(mpd_url, headers=self.manifest_headers, timeout=10)
            max_res = object_checks.check_dash_manifest(self, resp.text)
            self.assertEqual(1080, max_res)

    # -----------------------
    #       VOD
    # -----------------------

    def get_playlist_catchup(self, url=None, platform='freeview'):
        """Request stream of a catchup episode (i.e. production)

        """
        post_data = self.create_post_data('vod', platform)

        if not url:
            # request playlist of an episode of Doc Martin
            url = 'https://magni.itv.com/playlist/itvonline/ITV/1_7665_0049.001'

        resp = requests.post(
            url,
            headers={'Accept': 'application/vnd.itv.vod.playlist.v4+json',
                     'User-Agent': 'X-Player',
                     # 'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                     # 'Origin': 'https://www.itv.com',
                     },
            # headers={'Accept': 'application/vnd.itv.vod.playlist.v4+json',
            #          'User-Agent': 'ITV_Player_(Android)',
            #          'Origin': 'https://www.itv.com',
            #          },
            json=post_data,
            timeout=10)
        resp = resp.json()
        return resp

    def test_get_playlist_catchup(self):
        strm_data = self.get_playlist_catchup(platform='web')
        # testutils.save_json(strm_data, 'playlists/pl_doc_martin.json')
        object_checks.check_catchup_dash_stream_info(strm_data['Playlist'], full_hd=False)
        strm_data = self.get_playlist_catchup(platform='freeview')
        object_checks.check_catchup_dash_stream_info(strm_data['Playlist'], full_hd=True)

    def test_get_playlist_premium_catchup(self):
        """Request a premium stream _without_ a premium account."""
        # Judge John Deed S1E1
        resp = self.get_playlist_catchup('https://magni.itv.com/playlist/itvonline/ITV/10_5323_0001.001')
        object_checks.has_keys(resp, 'Message', 'TransactionId')
        self.assertTrue('message: User does not have entitlements' in resp['Message'])

    def test_manifest_vod(self):
        for platform in ('web', 'freeview'):
            strm_data = self.get_playlist_catchup(platform=platform)
            mpd_url = strm_data['Playlist']['Video']['MediaFiles'][0]['Href']
            resp = requests.get(mpd_url, headers=self.manifest_headers, timeout=10)
            max_res = object_checks.check_dash_manifest(self, resp.text)
            if platform == 'web':
                self.assertEqual(720, max_res)
            else:
                self.assertEqual(1080, max_res)

    def test_playlist_news_collection_items(self):
        """Short news items form the collection 'news' are all just mp4 files."""
        page_data = parsex.scrape_json(fetch.get_document('https://www.itv.com/'))
        for slider in page_data['shortFormSliderContent']:
            checked_types = set()
            for item in slider['items']:
                content_type = item['contentType']
                if content_type in checked_types:
                    continue
                checked_types.add(content_type)
                if content_type == 'shortform':
                    url = '/'.join(('https://www.itv.com/watch', item['genre'], item['titleSlug'], item['episodeId']))
                elif 'encodedProgrammeId' in item.keys():
                    # The new item is a 'normal' catchup title
                    # Do not use field 'href' as it has non-a-encoded program and episode IDs which won't work.
                    url = '/'.join(('https://www.itv.com/watch',
                                    item['titleSlug'],
                                    item['encodedProgrammeId']['letterA'],
                                    item.get('encodedEpisodeId', {}).get('letterA', ''))).rstrip('/')
                else:
                    raise AssertionError("Unknown news item type '{}'.".format(content_type))

                playlist_url = itvx.get_playlist_url_from_episode_page(url)
                for platform in ('web', 'freeview'):
                    strm_data = self.get_playlist_catchup(playlist_url, platform)
                    # testutils.save_json(strm_data, 'playlists/pl_news_short.json')
                    if content_type == 'shortform':
                        object_checks.check_news_collection_stream_info(strm_data['Playlist'])
                    else:
                        object_checks.check_catchup_dash_stream_info(strm_data['Playlist'], full_hd=platform == 'freeview')


class ChannelLogos(unittest.TestCase):
    """These urls are obtained from the now/next schedule and are hardcoded for use
    in iptvmanager integration.
    """
    logo_urls = [
        'https://images.ctfassets.net/bd5zurrrnk1g/54OefyIkbiHPMJUYApbuUX/7dfe2176762fd8ec10f77cd61a318b07/itv1.png',
        'https://images.ctfassets.net/bd5zurrrnk1g/aV9MOsYOMEXHx3iw0p4tk/57b35173231c4290ff199ef8573367ad/itv2.png',
        'https://images.ctfassets.net/bd5zurrrnk1g/6Mul5JVrb06pRu8bNDgIAe/b5309fa32322cc3db398d25e523e2b2e/itvBe.png',
        'https://images.ctfassets.net/bd5zurrrnk1g/39fJAu9LbUJptatyAs8HkL/80ac6eb141104854b209da946ae7a02f/itv3.png',
        'https://images.ctfassets.net/bd5zurrrnk1g/6Dv76O9mtWd6m7DzIavtsf/b3d491289679b8030eae7b4a7db58f2d/itv4.png'
    ]

    def test_channel_log_urls(self):
        """Test if logo images used in IPTV Manager integration are available.

        """
        for url in self.logo_urls:
            response = requests.get(url, headers=dftl_headers, timeout=5)
            self.assertEqual(response.status_code, 200)

    def test_check_scaled_logos(self):
        """Check if resized images can be obtained as per API specs at:
        https://www.contentful.com/developers/docs/references/images-api/#/reference/resizing-&-cropping

        """
        import struct
        import imghdr

        # A modified version of https://stackoverflow.com/questions/8032642/how-can-i-obtain-the-image-size-using-a
        # -standard-python-class-without-using-an
        def get_image_size(imgdata):
            """Determine the image type of fhandle and return its size.
            from draco"""
            head = imgdata[:24]
            if len(head) != 24:
                return None
            if imghdr.what(None, h=imgdata) == 'png':
                check = struct.unpack('>i', head[4:8])[0]
                if check != 0x0d0a1a0a:
                    return None
                w, h = struct.unpack('>ii', head[16:24])
            else:
                return None
            return w, h

        for url in self.logo_urls:
            url += '?w=512'
            response = requests.get(url, headers=dftl_headers, timeout=5)
            self.assertEqual(response.status_code, 200)
            width, height = get_image_size(response.content)
            self.assertEqual(512, width)
            self.assertAlmostEqual(512, height, delta=2)


class SignIn(unittest.TestCase):
    def test_refresh_with_invalid_tokens(self):
        refresh_tkn = build_test_tokens('Peter')[1]
        resp = requests.get(
            url='https://auth.prd.user.itv.com/token',
            params={'refresh': refresh_tkn},
            headers={'user-agent': fetch.USER_AGENT,
                     'accept': 'application/vnd.user.auth.v2+json',
                     'accept-language':  'en-GB,en;q=0.5',
                     'accept-encoding':  'gzip, deflate, br, zstd',
                     'origin':           'https://www.itv.com',
                     'referer':          'https://www.itv.com/',
                     'sec-fetch-dest':   'empty',
                     'sec-fetch-mode':   'cors',
                     'sec-fetch-site':   'same-site',
                     'te':               'trailers'}
        )
        self.assertEqual(400, resp.status_code)
        data = resp.json()
        self.assertEqual('invalid_grant', data['error'])
        self.assertEqual('The token is not a valid JWT token', data['error_description'])
        self.assertIsNone(data['validation_errors'])


class Region(unittest.TestCase):
    def test_available_regions(self):
        resp = requests.get('https://config.fe.itv.com/3.564.0/freeview')
        self.assertEqual(200, resp.status_code)
        config = resp.json()
        new_regions = config['regions']
        # testutils.save_json(new_regions, 'json/regions.json')
        regions = testutils.open_json('json/regions.json')
        self.assertDictEqual(regions, new_regions)

    @unittest.skip("Run manually when regions have changed.")
    def test_region_to_settings(self):
        """Print out all regions in a format that can be used in the addon's settings."""
        regions = testutils.open_json('json/regions.json')
        for k, v in regions.items():
            if v['broadcaster'] == 'STV':
                continue
            label = k.replace("_", " ").title()
            print(f'<option label="{label}">{v["region"]}</option>')
        time.sleep(1)
