# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import time

from unittest import TestCase
from unittest.mock import MagicMock, patch
from datetime import timezone

from test.support.testutils import open_json, open_doc
from test.support.object_checks import has_keys, is_url

from resources.lib import itv
from resources.lib import itv_account
from resources.lib import errors
from resources.lib.utils import ZoneInfo

setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


@patch('resources.lib.fetch.get_json', new=lambda *args: open_json('schedule/live_4hrs.json'))
class LiveSchedule(TestCase):
    def test_live_schedules(self):
        schedule = itv.get_live_schedule()
        self.assertEqual(6, len(schedule))
        for channel in schedule:
            has_keys(channel['channel'], 'name', 'strapline', '_links')
            for programme in channel['slot']:
                has_keys(programme, 'programmeTitle', 'startTime', 'orig_start')

    @patch('xbmc.getRegion', return_value='%H:%M')
    def test_live_schedules_in_local_time(self, _):
        local_tz = ZoneInfo('America/Fort_Nelson')
        schedule = itv.get_live_schedule(local_tz=timezone.utc)
        utc_times = [item['startTime'] for item in schedule[0]['slot']]
        schedule = itv.get_live_schedule(local_tz=local_tz)
        ca_times = [item['startTime'] for item in schedule[0]['slot']]
        for utc, ca in zip(utc_times, ca_times):
            time_dif = time.strptime(utc, '%H:%M').tm_hour - time.strptime(ca, '%H:%M').tm_hour
            if time_dif > 0:
                self.assertEqual(7, time_dif)
            else:
                self.assertEqual(-17, time_dif)

    def test_live_schedules_system_time_format(self):
        with patch('xbmc.getRegion', return_value='%H:%M'):
            schedule = itv.get_live_schedule(local_tz=timezone.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('14:05', start_time)
        with patch('xbmc.getRegion', return_value='%I:%M %p'):
            schedule = itv.get_live_schedule(local_tz=timezone.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('02:05 pm', start_time.lower())


class GetCatchupUrls(TestCase):
    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_doc_martin.json'))
    def test_catchup_urls(self, _):
        mpd, key, subs, video_type, prod_id = itv.get_catchup_urls('itv1/url')
        self.assertTrue(is_url(mpd))
        self.assertTrue(is_url(key))
        self.assertTrue(is_url(subs))
        self.assertEqual(video_type, 'CATCHUP')

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_news_short.json'))
    def test_shorform_urls(self, _):
        mpd, key, subs, video_type, prod_id = itv.get_catchup_urls('itv1/url')
        self.assertTrue(is_url(mpd))
        self.assertIsNone(key)
        self.assertIsNone(subs)
        self.assertEqual(video_type, 'SHORT')


class GetLiveUrls(TestCase):
    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_itv1.json'))
    def test_get_dar_urls(self, _):
        mpd, key, subs = itv.get_live_urls('itv1/url')
        self.assertTrue(is_url(mpd))
        self.assertTrue('?t=' in mpd)
        self.assertTrue(is_url(key))
        self.assertIsNone(subs)

    @patch('resources.lib.itvx._request_stream_data', return_value=open_json('playlists/pl_itv1.json'))
    def test_get_live_urls_start_again(self, _):
        mpd, key, subs = itv.get_live_urls('itv1/url', start_time='2023-05-06T17:18:32Z', play_from_start=True)
        self.assertTrue(is_url(mpd))
        self.assertTrue('?t=' in mpd)
        self.assertTrue(is_url(key))
        self.assertIsNone(subs)

    def test_get_live_urls_without_start_again_url(self):
        playlist = open_json('playlists/pl_itv1.json')
        for item in playlist['Playlist']['Video']['VideoLocations']:
            del item['StartAgainUrl']
        with patch('resources.lib.itvx._request_stream_data', return_value=playlist):
            mpd, key, subs = itv.get_live_urls('itv1/url', start_time='2023-05-06T17:18:32Z', play_from_start=True)
        self.assertTrue(is_url(mpd))
        self.assertFalse('?t=' in mpd)
        self.assertTrue(is_url(key))
        self.assertIsNone(subs)


class GetVttSubtitles(TestCase):
    @patch('xbmcaddon.Addon.getSetting', return_value='true')
    @patch('resources.lib.fetch.get_document', new=open_doc('vtt/subtitles_doc_martin.vtt'))
    def test_get_vtt_subtitles(self, _):
        subs = itv.get_vtt_subtitles('my/subs/url')
        self.assertIsInstance(subs, tuple)
        self.assertTrue(1, len(subs))
        self.assertTrue(subs[0].endswith('.en.srt'))

    @patch('xbmcaddon.Addon.getSetting', return_value='false')
    @patch('resources.lib.fetch.get_document', new=open_doc('vtt/subtitles_doc_martin.vtt'))
    def test_get_vtt_subtitles_with_setting_false(self, _):
        subs = itv.get_vtt_subtitles('my/subs/url')
        self.assertIsInstance(subs, type(None))

    @patch('xbmcaddon.Addon.getSetting', return_value='true')
    @patch('resources.lib.fetch.get_document', new=open_doc('vtt/subtitles_doc_martin.vtt'))
    def test_get_vtt_subtitles_no_subtitles_url(self, _):
        subs = itv.get_vtt_subtitles('')
        self.assertIsInstance(subs, type(None))
        subs = itv.get_vtt_subtitles(None)
        self.assertIsInstance(subs, type(None))

    @patch('xbmcaddon.Addon.getSetting', return_value='true')
    @patch('resources.lib.fetch.get_document', side_effect=errors.FetchError)
    def test_get_vtt_subtitles_errors(self, _, __):
        subs = itv.get_vtt_subtitles('my/subs/url')
        self.assertIsInstance(subs, type(None))
