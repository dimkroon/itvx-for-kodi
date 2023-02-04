
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
#
# ----------------------------------------------------------------------------------------------------------------------
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx

# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
import requests
import copy
from datetime import datetime, timedelta

from resources.lib import itv_account
from resources.lib import fetch
from resources.lib import parsex
from resources.lib import itvx
from test.support import object_checks

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
                self.assertTrue(program['startTime'].endswith('Z'))     # start time is in format '2022-11-22T20:00Z'
                self.assertEqual(17, len(program['startTime']))         # has no seconds
            channel_info = channel_data['_embedded']['channel']
            object_checks.has_keys(channel_info, 'name', 'strapline', '_links')
            self.assertTrue(channel_info['_links']['playlist']['href'].startswith('https'))
            return schedule

    def test_main_channels_schedules_4hrs(self):
        now = datetime.utcnow()
        end = now + timedelta(hours=4)
        self.check_schedule(now, end)

    @unittest.skip("Schedules far in the past time out")
    def test_main_channels_schedules_week_in_the_past(self):
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
            self.check_schedule(start, now)
        except (requests.HTTPError, requests.ReadTimeout) as err:
            if isinstance(err, requests.ReadTimeout) or err.response.status_code == 504:
                # try again
                print("schedule for days on the future failed, trying again...")
                self.check_schedule(start, now)
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

        self.assertAlmostEqual(25, len(data['channels']), delta=2)
        for chan in data['channels']:
            object_checks.has_keys(chan, 'id', 'editorialId', 'channelType', 'name', 'streamUrl', 'slots', 'images')
            for program in (chan['slots']['now'], chan['slots']['next']):
                object_checks.has_keys(program, 'titleId', 'prodId', 'contentEntityType', 'start', 'end', 'title',
                                       'brandTitle', 'displayTitle', 'detailedDisplayTitle', 'broadcastAt', 'guidance',
                                       'rating', 'episodeNumber', 'seriesNumber', 'startAgainVod',
                                       'startAgainSimulcast', 'shortSynopsis')
                self.assertIsNotNone(program['displayTitle'])
                self.assertTrue(object_checks.is_iso_time(program['start']))
                self.assertTrue(object_checks.is_iso_time(program['end']))
                if program['broadcastAt'] is not None:      # is None on fast channels
                    self.assertTrue(program['broadcastAt'].endswith('Z'))
                    self.assertTrue(20, len(program['broadcastAt']))


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
        self.assertTrue(item_data['legacyId']['officialFormat'])

    def check_special_item(self, item_data):
        object_checks.has_keys(item_data, 'specialCCId', 'legacyId', 'productionId', 'specialTitle',
                               'synopsis', 'imageHref', 'tier',
                               obj_name='specialItem.data')

        # The field specialProgramme is not always present
        special_data = item_data.get('specialProgramme')
        if special_data:
            object_checks.has_keys(special_data, 'programmeCCId', 'legacyId', 'programmeTitle',
                                   obj_name='specialItem.data.specialProgramme')
        object_checks.is_url(item_data['imageHref'])
        self.assertTrue(item_data['legacyId']['officialFormat'])

    def check_film_item(self, item_data):
        object_checks.has_keys(item_data, 'filmCCId', 'legacyId', 'productionId', 'filmTitle',
                               'synopsis', 'imageHref', 'tier',
                               obj_name='specialItem.data')
        object_checks.is_url(item_data['imageHref'])
        self.assertTrue(item_data['legacyId']['officialFormat'])

    def test_search_normal_chase(self):
        self.search_params['query'] = 'the chases'
        resp = requests.get(self.search_url, params=self.search_params).json()
        self.check_result(resp)
        self.assertGreater(len(resp['results']), 3)

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

    def test_search_with_non_free_results(self):
        """Results contain Doctor Foster programme which is can only be watch with a premium account."""
        self.search_params['query'] = 'doctor foster'
        resp = requests.get(self.search_url, params=self.search_params).json()
        self.check_result(resp)
        self.assertEqual('PAID', resp['results'][0]['data']['tier'])

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
        'platformTag': 'ctv'
    }
}


class Playlists(unittest.TestCase):
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
        """Get the playlists of the main live channels

        For all channels other than ITV the headers User Agent and Origin are required.
        And the cookie consent cookies must present. If any of those are missing the request will time out.
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
                    'Origin':           'https://www.itv.com',
                },
                cookies=fetch.HttpSession().cookies,  # acc_data.cookie,
                json=post_data,
                timeout=10
        )
        # strm_data = fetch.post_json(
        #     url, data=post_data,
        #     headers={'Accept': 'application/vnd.itv.online.playlist.sim.v3+json'},
        #     cookies=acc_data.cookie)
        # self.assertEqual(200, resp.status_code)
        strm_data = resp.json()
        return strm_data

    def test_get_playlist_live(self):
        for channel in ('ITV', 'ITV2', 'ITV3', 'ITV4', 'CITV', 'ITVBe'):
            strm_data = self.get_playlist_live(channel)
            object_checks.check_live_stream_info(strm_data['Playlist'])

    def test_manifest_live(self):
        strm_data = self.get_playlist_live('ITV')
        mpd_url = strm_data['Playlist']['Video']['VideoLocations'][0]['Url']
        resp = requests.get(
                mpd_url,
                headers={
                    'Accept': 'application/vnd.itv.online.playlist.sim.v3+json',
                    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                    'Origin':           'https://www.itv.com',
                },
                # cookies=fetch.HttpSession().cookies,  #acc_data.cookie,
                timeout=10
        )
        manifest = resp.text
        self.assertGreater(len(manifest), 1000)
        self.assertTrue(manifest.startswith('<?xml version='))

    def get_playlist_catchup(self, url=None):
        """Request stream of a catchup episode (i.e. production)

        Webbrowsers send several cookies in one single Cookie header:
            - Itv.Session
            - Itv.Cid
            - mid
            - All Syrenisxxx concerning cookie consent
            - _ga_D6PQ6YDTQK
            - _ga
            - Itv.Region

        However, we test with only Itv.Session cookie set and that seems to work fine.

        """
        post_data = self.create_post_data('vod')

        if not url:
            # request playlist of an episode of Doc Martin
            url = 'https://magni.itv.com/playlist/itvonline/ITV/1_7665_0049.001'

            # The bigger trip - episode 1
            # url = 'https://magni.itv.com/playlist/itvonline/ITV/10_2772_0001.001'

            # url = 'https://magni.itv.com/playlist/itvonline/ITV/CFD0332_0001.001'

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
        resp = self.get_playlist_catchup()
        strm_data = resp
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
        resp = requests.get(
            mpd_url,
            headers={'Accept': 'application/vnd.itv.online.playlist.sim.v3+json',
                     'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                     'Origin': 'https://www.itv.com',
                     },
            # cookies=fetch.HttpSession().cookies,  #acc_data.cookie,
            timeout=10
        )
        manifest = resp.text
        self.assertGreater(len(manifest), 1000)
        self.assertTrue(manifest.startswith('<?xml version='))

    def test_playlist_news_collection_items(self):
        """Short news items form the collection 'news' are all just mp4 files."""
        page_data = parsex.scrape_json(fetch.get_document('https://www.itv.com/'))
        for item in page_data['newsShortformSliderContent']['items']:
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
                url = 'https://www.itv.com/watch/news/' + item['href']
            playlist_url = itvx.get_playlist_url_from_episode_page(url)
            strm_data = self.get_playlist_catchup(playlist_url)
            if is_short:
                object_checks.check_news_stream_info(strm_data['Playlist'])
            else:
                object_checks.check_catchup_dash_stream_info(strm_data['Playlist'])