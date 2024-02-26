# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
import copy
from datetime import datetime, timedelta

import requests
from requests.cookies import RequestsCookieJar
from urllib.parse import quote

from resources.lib import itv_account
from resources.lib import fetch
from resources.lib import parsex
from resources.lib import itvx
from resources.lib import utils
from resources.lib import main
from test.support import object_checks
from test.support import testutils


setUpModule = fixtures.setup_web_test


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
                self.assertTrue(program['startTime'].endswith('Z') or program['startTime'].endswith('+01:00'))     # start time is in format '2022-11-22T20:00Z'
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
        now = datetime.utcnow()
        end = now + timedelta(hours=4)
        self.check_schedule(now, end)

    # @unittest.skip("Schedules far in the past time out")
    def test_main_channels_schedules_4_days_in_the_past(self):
        """Live schedules are available to some time in the past.

        Requesting schedules takes some time, but going further in the past quickly increases
        the time the request takes to return.
        If we do the same request several times, a response that initially took 10 sec , returns
        in 150 ms after a few attempts.

        .. Note ::
            Regularly requests encounter a 504 - Gateway Timeout error, even requests that on other occasions
            complete without error, but going further in the past increases the change of a time-out.
        """
        now = datetime.utcnow()
        start = now - timedelta(days=4)
        # self.check_schedule(start, now)
        try:
            self.check_schedule(start, now + timedelta(hours=4))
        except (requests.HTTPError, requests.ReadTimeout) as err:
            if isinstance(err, requests.ReadTimeout) or err.response.status_code == 504:
                # try again
                print("schedule for 4 days in the past failed, trying again...")
                self.check_schedule(start, now + timedelta(hours=4))
            else:
                raise

    @unittest.skip("Schedules far in the future time out")
    def test_main_channels_schedules_7_days_in_the_future(self):
        """Live schedules are available up to roughly 1 week in the future. Requests for
        more will usually succeed normally, but do not contain more data.

        See the test above (week_in_the_past) for peculiarities

        """
        now = datetime.utcnow()
        end = now + timedelta(days=8)
        expected_end = now + timedelta(days=7)
        try:
            schedule = self.check_schedule(now, end)
        except (requests.HTTPError, requests.ReadTimeout) as err:
            if isinstance(err, requests.ReadTimeout) or err.response.status_code == 504:
                # try again
                print("schedule for days on the future failed, trying again...")
                schedule = self.check_schedule(now, end)
            else:
                raise
        last_programme = schedule[0]['_embedded']['slot'][-1]
        start_dt = datetime.strptime(last_programme['startTime'], '%Y-%m-%dT%H:%MZ')
        self.assertAlmostEqual(start_dt.timestamp(), expected_end.timestamp(), delta=86400)  # give or take a day

    @unittest.skip("Schedules far in the past time out")
    def test_one_day_week_ago(self):
        now = datetime.utcnow()
        end = now - timedelta(days=6)
        try:
            schedule = self.check_schedule(start_dt=now - timedelta(days=7), end_dt=end)
        except (requests.HTTPError, requests.ReadTimeout) as err:
            if isinstance(err, requests.ReadTimeout) or err.response.status_code == 504:
                # try again
                print("schedule for on week ago failed, trying again...")
                schedule = self.check_schedule(start_dt=now - timedelta(days=7), end_dt=end)
            else:
                raise
        last_programme = schedule[0]['_embedded']['slot'][-1]
        start_dt = datetime.strptime(last_programme['startTime'], '%Y-%m-%dT%H:%MZ')
        self.assertAlmostEqual(start_dt.timestamp(), end.timestamp(), delta=86400)  # give or take a day

    def test_now_next(self):
        resp = requests.get('https://nownext.oasvc.itv.com/channels?broadcaster=itv&featureSet=mpeg-dash,clearkey,'
                            'outband-webvtt,hls,aes,playready,widevine,fairplay&platformTag=dotcom')
        data = resp.json()
        # testutils.save_json(data, 'schedule/now_next.json')
        object_checks.has_keys(data, 'channels', 'images', 'ts')

        self.assertTrue(data['images']['backdrop'].startswith('https://'))
        self.assertTrue(data['images']['backdrop'].endswith('.jpeg'))

        self.assertAlmostEqual(20, len(data['channels']), delta=5)
        for chan in data['channels']:
            object_checks.has_keys(chan, 'id', 'editorialId', 'channelType', 'name', 'streamUrl', 'slots', 'images')
            for program in (chan['slots']['now'], chan['slots']['next']):
                progr_keys = ('titleId', 'prodId', 'contentEntityType', 'start', 'end', 'title',
                              'brandTitle', 'displayTitle', 'detailedDisplayTitle', 'broadcastAt', 'guidance',
                              'rating', 'episodeNumber', 'seriesNumber', 'startAgainVod',
                              'startAgainSimulcast', 'shortSynopsis')
                object_checks.has_keys(program, *progr_keys)
                if program['displayTitle'] is None:
                    # If displayTitle is None all other fields are None or False as well.
                    # Noticed 25-6-2023, only on the FAST channel named 'Unwind', which in fact
                    # does not really broadcast programmes.
                    for k in progr_keys:
                        self.assertFalse(program[k])
                    self.assertTrue(chan['name'].lower() in ('unwind', 'citv'))
                else:
                    self.assertTrue(object_checks.is_iso_utc_time(program['start']))
                    self.assertTrue(object_checks.is_iso_utc_time(program['end']))
                    if program['broadcastAt'] is not None:      # is None on fast channels
                        self.assertTrue(object_checks.is_iso_utc_time(program['broadcastAt']))


@unittest.skip("not to interfere with tests of bugfix branch")
class Search(unittest.TestCase):
    def setUp(self) -> None:
        self.search_url = 'https://textsearch.prd.oasvc.itv.com/search'
        self.search_params = {
            'broadcaster': 'itv',
            'featureSet': 'clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay,bbts,progressive,hd,rtmpe',
            'onlyFree': 'false',
            'platform': 'ctv',
        }.copy()

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
        object_checks.is_url(item_data['imageHref'])

    def check_film_item(self, item_data):
        object_checks.has_keys(item_data, 'filmCCId', 'legacyId', 'productionId', 'filmTitle',
                               'synopsis', 'imageHref', 'tier',
                               obj_name='specialItem.data')
        object_checks.is_url(item_data['imageHref'])
        self.assertTrue(object_checks.is_not_empty(item_data['legacyId']['apiEncoded'], str))
        self.assertFalse('/' in item_data['legacyId']['apiEncoded'])

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

    def test_search_without_result(self):
        """Typical itvX behaviour; response can be either HTTP status 204 - No Content,
        or status 200 - OK with empty results list."""
        self.search_params['query'] = 'xprs'
        resp = requests.get(self.search_url, params=self.search_params)
        self.assertTrue(resp.status_code in (200, 204))
        if resp.status_code == 200:
            self.assertListEqual([], resp.json()['results'])

    def test_search_foster_with_paid(self):
        """Results contains a Doctor Foster programme, which can only be watch with a premium account."""
        # Search including paid
        url = ('https://textsearch.prd.oasvc.itv.com/search?broadcaster=itv&featureSet=clearkey,outband-webvtt,'
               'hls,aes,playready,widevine,fairplay,bbts,progressive,hd,rtmpe&onlyFree=false&platform=ctv&query='
               + quote('doctor foster'))
        resp = requests.get(url,
                            headers={'accept': 'application/json'})
        data = resp.json()
        self.check_result(data)
        self.assertTrue(any('PAID' == result['data']['tier'] for result in data['results']))
        # self.assertTrue(all('FREE' == result['data']['tier'] for result in data['results']))

    def test_search_foster_only_free(self):
        # Search exclude paid
        url = ('https://textsearch.prd.oasvc.itv.com/search?broadcaster=itv&featureSet=clearkey,outband-webvtt,'
               'hls,aes,playready,widevine,fairplay,bbts,progressive,hd,rtmpe&onlyFree=true&platform=ctv&query='
               + quote('doctor foster'))
        resp = requests.get(url,
                            headers={'accept': 'application/json'})
        data = resp.json()
        self.assertGreater(len(data['results']), 0)
        self.check_result(data)
        # self.assertTrue(any('PAID' == result['data']['tier'] for result in data['results']))
        self.assertTrue(all('FREE' == result['data']['tier'] for result in data['results']))


# ----------------------------------------------------------------------------------------------------------------------

class MyList(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.token = itv_account.itv_session().access_token
        cls. userid = itv_account.itv_session().user_id

    def test_get_my_list_no_content_type(self):
        """Request My List without specifying the content-type

        """
        # Query parameters features and platform are required!!
        # NOTE:
        #   Platform dotcom may return fewer items than mobile and ctv, even when those items are
        #   presented and playable on the website.
        url = 'https://my-list.prd.user.itv.com/user/{}/mylist?features=mpeg-dash,outband-webvtt,hls,aes,playre' \
              'ady,widevine,fairplay,progressive&platform=ctv'.format(self.userid)
        headers = {'authorization': 'Bearer ' + self.token}
        # Both webbrowser and app authenticate with header, without any cookie.
        resp = requests.get(url, headers=headers)
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
        url = 'https://my-list.prd.user.itv.com/user/{}/mylist?features=mpeg-dash,outband-webvtt,hls,aes,playre' \
              'ady,widevine,fairplay,progressive&platform=ctv'.format(self.userid)
        headers = {'authorization': 'Bearer ' + self.token,
                   'accept': 'application/json'}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        # testutils.save_json(data, 'mylist/mylist_json_data.json')

        self.assertIsInstance(data, list)
        self.assertEqual(resp.headers['content-type'], 'application/json')

    def test_add_programme(self):
        """At present only programmes can be added to the list, no individual episodes.

        Itv always returns HTTP status 200 when a syntactical valid request has been made. However,
        that is no guarantee that the requested programme is in fact added to My List.

        """
        progr_id = '2_7931'
        episode_id = '2_7931_0001_001'
        url = 'https://my-list.prd.user.itv.com/user/{}/mylist/programme/{}?features=mpeg-dash,outband-webvtt,hls,aes,playre' \
              'ady,widevine,fairplay,progressive&platform=ctv'.format(self.userid, progr_id, episode_id)
        headers = {'authorization': 'Bearer ' + self.token}
        # Both webbrowser and app authenticate with header, without any cookie.
        resp = requests.post(url, headers=headers)
        data = resp.json()
        self.assertIsInstance(data, dict)


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
            self.assertTrue(item['contentType']in ('EPISODE', 'FILM', 'SPECIAL'))
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

            if item['contentType'] in ('FILM', 'SPECIAL'):
                self.assertIsNotNone(utils.iso_duration_2_seconds(item['duration']))
            else:
                self.assertIsNone(item['duration'])

    def test_get_last_watched(self):
        """Get last watch without specifying accept header returns content-type application/json,
        with exactly the same content as the original application/vnd.user.content.v1+json.
        """
        url = 'https://content.prd.user.itv.com/lastwatched/user/{}/dotcom?features=mpeg-dash,outband-webvtt,' \
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
        url = 'https://content.prd.user.itv.com/lastwatched/user/{}/dotcom?features=mpeg-dash,outband-webvtt,' \
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
        url = 'https://content.prd.user.itv.com/lastwatched/user/{}/dotcom?features=mpeg-dash,outband-webvtt,' \
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
        self.features_web = {
                'features': 'mpeg-dash,outband-webvtt,hls,aes,playready,widevine,fairplay,progressive',
                'platform': 'dotcom',
                'size': 12}
        self.features_mobile = {
                'features': 'mpeg-dash,widevine,widevine-download,inband-ttml,inband-webvtt,outband-webvtt,inband-audio-description',
                'platform': 'mobile',
                'size': 12}
        self.userid = itv_account.itv_session().user_id
        self.headers = {'accept': 'application/json'}

    def test_get_recommendations_byw(self):
        """Because You Watched - recommendations based on the (last) watched programme
        Requires userid, but no login."""
        url = 'https://recommendations.prd.user.itv.com/recommendations/byw/' + self.userid
        resp = requests.get(url, headers=self.headers, params=self.features_web, allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        self.assertEqual('application/json', resp.headers['content-type'])
        data = resp.json()
        # testutils.save_json(data, 'usercontent/byw.json')
        self.assertTrue(object_checks.is_not_empty(data['watched_programme'], str))
        self.assertTrue(12, len(data['recommendations']))
        for progr in data['recommendations']:
            object_checks.check_item_type_programme(self, progr, 'BecauseYouWatched')

        # without specifying content-type
        resp = requests.get(url, params=self.features_web, allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        self.assertEqual('application/json', resp.headers['content-type'])

        # invalid user ID
        url = 'https://recommendations.prd.user.itv.com/recommendations/byw/none'
        resp = requests.get(url, headers=self.headers, params=self.features_web, allow_redirects=False)
        self.assertEqual(204, resp.status_code)

    def test_recommendations_homepage(self):
        """Regular recommendations place on the home page."""
        self.features_web.update(tier='FREE', version='1')
        url = 'https://recommendations.prd.user.itv.com/recommendations/homepage/' + self.userid
        resp = requests.get(url, headers=self.headers, params=self.features_web, allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        self.assertEqual('application/json', resp.headers['content-type'])
        data = resp.json()
        # testutils.save_json(data, 'usercontent/recommended.json')
        self.assertTrue(12, len(data))

    def test_recommendations_homepage_with_invalid_userid(self):
        url = 'https://recommendations.prd.user.itv.com/recommendations/homepage/none'
        resp = requests.get(url, headers=self.headers, params=self.features_web, allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        self.assertTrue(12, len(data))
        for progr in data:
            object_checks.check_item_type_programme(self, progr, 'Recommended')

    def test_recommendations_homepage_without_invalid_userid(self):
        url = 'https://recommendations.prd.user.itv.com/recommendations/homepage/'
        resp = requests.get(url, headers=self.headers, params=self.features_web, allow_redirects=False)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        self.assertTrue(12, len(data))
        for progr in data:
            object_checks.check_item_type_programme(self, progr, 'Recommended')

    def test_recommendatation_homepage_more_items(self):
        # request more than 12 items
        self.features_web['size'] = 24
        url = 'https://recommendations.prd.user.itv.com/recommendations/homepage/' + self.userid
        resp = requests.get(url, headers=self.headers, params=self.features_web, allow_redirects=False)
        data = resp.json()
        self.assertTrue(24, len(data))
        for progr in data:
            object_checks.check_item_type_programme(self, progr, 'Recommended')

    def test_recommendations_homepage_mobile(self):
        """This request fails without an apikey header"""
        url = 'https://api.itv/hub/recommendations/homepage/' + self.userid
        resp = requests.get(url, headers=self.headers, params=self.features_web, allow_redirects=False)
        self.assertEqual(401, resp.status_code)

# ----------------------------------------------------------------------------------------------------------------------


stream_req_data = {
    'client': {
        'id': 'browser',
        'supportsAdPods': False,
        'version': ''
    },
    'device': {
        'manufacturer': 'Firefox',
        'model': '105',
        'os': {
            'name': 'Linux',
            'type': 'desktop',
            'version': 'x86_64'
        }
    },
    'user': {
        'entitlements': [],
        'itvUserId': '',
        'token': ''
    },
    'variantAvailability': {
        'featureset': {
            'min': ['mpeg-dash', 'widevine'],
            'max': ['mpeg-dash', 'widevine', 'hd']
        },
        'platformTag': 'dotcom'
    }
}


class Playlists(unittest.TestCase):
    manifest_headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
        'Origin': 'https://www.itv.com'}

    @staticmethod
    def create_post_data(stream_type):
        acc_data = itv_account.itv_session()
        post_data = copy.deepcopy(stream_req_data)
        post_data['user']['token'] = acc_data.access_token
        post_data['client']['supportsAdPods'] = True
        feature_set = post_data['variantAvailability']['featureset']

        # Catchup MUST have outband-webvtt in min feature set to return subtitles.
        # Live, however must have a min feature set WITHOUT outband-webvtt, or it wil return 400 - Bad Request
        if stream_type == 'vod':
            feature_set['min'].append('outband-webvtt')

        return post_data

    def get_playlist_live(self, channel):
        """Get the playlist of one of the itvx live channels

        For all channels other than the headers User Agent and Origin are required.
        And the cookie consent cookies must be present. If any of those are missing the request will time out.

        Since accessToken is provided in the body, authentication by cookie or header is not needed.
        """
        acc_data = itv_account.itv_session()
        acc_data.refresh()
        post_data = self.create_post_data('live')

        url = 'https://simulcast.itv.com/playlist/itvonline/' + channel
        resp = requests.post(
            url,
            headers={
                'Accept': 'application/vnd.itv.online.playlist.sim.v3+json',
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                'Origin': 'https://www.itv.com'},
                cookies=fetch.HttpSession().cookies,  # acc_data.cookie,
            json=post_data, timeout=10)
        strm_data = resp.json()
        return strm_data

    def test_get_playlist_simulcast(self):
        for channel in ('ITV', 'ITV2', 'ITV3', 'ITV4', 'CITV', 'ITVBe'):
            strm_data = self.get_playlist_live(channel)
            object_checks.check_live_stream_info(strm_data['Playlist'])

    def test_get_playlist_fast(self):
        for chan_id in range(1, 21):
            channel = 'FAST{}'.format(chan_id)
            strm_data = self.get_playlist_live(channel)
            object_checks.check_live_stream_info(strm_data['Playlist'])

    def test_playlist_live_cookie_requirement(self):
        """Test that consent cookies are required for a playlist request and that these are the
        only required cookies.

        """
        url = 'https://simulcast.itv.com/playlist/itvonline/ITV'
        headers = {
            'Accept': 'application/vnd.itv.online.playlist.sim.v3+json',
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
            'Origin': 'https://www.itv.com'}
        existing_cookies = fetch.HttpSession().cookies

        with self.assertRaises(requests.exceptions.ReadTimeout):
            requests.post(url, headers=headers, json=self.create_post_data('live'), timeout=2)

        jar = RequestsCookieJar()
        for cookie in existing_cookies:
            if cookie.name.startswith("Cassie"):
                jar.set_cookie(cookie)
        self.assertTrue(len(jar.items()), "No Cassie consent cookies")
        requests.post(url, headers=headers, cookies=jar, json=self.create_post_data('live'), timeout=2)

    def test_manifest_live_simulcast(self):
        strm_data = self.get_playlist_live('ITV')
        start_again_url = strm_data['Playlist']['Video']['VideoLocations'][0]['StartAgainUrl']
        start_time = datetime.utcnow() - timedelta(seconds=30)
        mpd_url = start_again_url.format(START_TIME=start_time.strftime('%Y-%m-%dT%H:%M:%S'))
        resp = requests.get(mpd_url, headers=self.manifest_headers, timeout=10)
        manifest = resp.text
        # testutils.save_doc(manifest, 'mpd/itv1.mpd')
        self.assertGreater(len(manifest), 1000)
        self.assertTrue(manifest.startswith('<?xml version='))
        if resp.history:
            self.assertTrue('hdntl' in resp.history[0].cookies)        # assert manifest response sets an hdntl cookie
        else:
            self.assertTrue('hdntl' in resp.cookies)

    def test_manifest_live_FAST(self):
        strm_data = self.get_playlist_live('FAST16')
        mpd_url = strm_data['Playlist']['Video']['VideoLocations'][0]['Url']
        resp = requests.get(mpd_url, headers=self.manifest_headers, timeout=10, allow_redirects=False)
        # Manifest of FAST channels can have several redirects. The hdntl cookie is set in the first response.
        self.assertTrue('hdntl' in resp.cookies)
        if resp.status_code == 302:
            resp = requests.get(mpd_url, headers=self.manifest_headers, timeout=10)
        manifest = resp.text
        # testutils.save_doc(manifest, 'mpd/fast16.mpd')
        self.assertGreater(len(manifest), 1000)
        self.assertTrue(manifest.startswith('<?xml version='))

    def test_manifest_live_FAST_playagain(self):
        """As of approximately 05-2023 play-again appears not to be available for fast channels"""
        strm_data = self.get_playlist_live('FAST16')
        start_time = datetime.strftime(datetime.now() - timedelta(seconds=20), '%Y-%m-%dT%H:%M:%S' )
        mpd_url = strm_data['Playlist']['Video']['VideoLocations'][0]['StartAgainUrl'].format(START_TIME=start_time)
        resp = requests.get(mpd_url, headers=self.manifest_headers, cookies=fetch.HttpSession().cookies)
        self.assertEqual(404, resp.status_code)
        # manifest = resp.text
        # # testutils.save_doc(manifest, 'mpd/fast16.mpd')
        # self.assertGreater(len(manifest), 1000)
        # self.assertTrue(manifest.startswith('<?xml version='))

    def get_playlist_catchup(self, url=None):
        """Request stream of a catchup episode (i.e. production)

        Unlike live channels, pLaylist requests for VOD don't need any cookie.
        """
        post_data = self.create_post_data('vod')

        if not url:
            # request playlist of an episode of Doc Martin
            url = 'https://magni.itv.com/playlist/itvonline/ITV/1_7665_0049.001'

        resp = requests.post(
            url,
            headers={'Accept': 'application/vnd.itv.vod.playlist.v2+json',
                     'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                     'Origin': 'https://www.itv.com',
                     },
            json=post_data,
            timeout=10)
        resp = resp.json()
        return resp

    def test_get_playlist_catchup(self):
        strm_data = self.get_playlist_catchup()
        # testutils.save_json(strm_data, 'playlists/doc_martin.json')
        object_checks.check_catchup_dash_stream_info(strm_data['Playlist'])

    def test_get_playlist_premium_catchup(self):
        """Request a premium stream without a premium account."""
        # 2Point4 Children S1E1
        resp = self.get_playlist_catchup('https://magni.itv.com/playlist/itvonline/ITV/10_0848_0006.001')
        object_checks.has_keys(resp, 'Message', 'TransactionId')
        self.assertTrue('message: User does not have entitlements' in resp['Message'])

    def test_manifest_vod(self):
        strm_data = self.get_playlist_catchup()
        base_url = strm_data['Playlist']['Video']['Base']
        path = strm_data['Playlist']['Video']['MediaFiles'][0]['Href']
        mpd_url = base_url + path
        resp = requests.get(mpd_url, headers=self.manifest_headers, timeout=10)
        manifest = resp.text
        self.assertGreater(len(manifest), 1000)
        self.assertTrue(manifest.startswith('<?xml version='))
        self.assertTrue('hdntl' in resp.cookies)    # assert manifest response sets an hdntl cookie

    def test_playlist_news_collection_items(self):
        """Short news items form the collection 'news' are all just mp4 files."""
        page_data = parsex.scrape_json(fetch.get_document('https://www.itv.com/'))
        for item in page_data['shortFormSliderContent'][0]['items']:
            is_short = True
            if 'encodedProgrammeId' in item.keys():
                # The new item is a 'normal' catchup title
                # Do not use field 'href' as it is known to have non-a-encoded program and episode Id's which doesn't work.
                url = '/'.join(('https://www.itv.com/watch',
                                item['titleSlug'],
                                item['encodedProgrammeId']['letterA'],
                                item.get('encodedEpisodeId', {}).get('letterA', ''))).rstrip('/')
                is_short = False
            else:
                # This news item is a 'short' item
                url = '/'.join(('https://www.itv.com/watch/news', item['titleSlug'], item['episodeId']))
            playlist_url = itvx.get_playlist_url_from_episode_page(url)
            strm_data = self.get_playlist_catchup(playlist_url)
            if is_short:
                object_checks.check_news_collection_stream_info(strm_data['Playlist'])
            else:
                object_checks.check_catchup_dash_stream_info(strm_data['Playlist'])