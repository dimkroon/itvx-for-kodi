# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
import time

import requests

from support.object_checks import has_keys


class WhatToWatchData(TestCase):
    def platforms(self):
        resp = requests.get('https://api.tv-guide.future.sensi.link/platforms')
        self.assertEqual(200, resp.status_code)
        platforms = resp.json()['platforms']
        region_id = None
        self.assertTrue(any(item['title'] == 'Freeview' for item in platforms))
        for platform in platforms:
            has_keys(platform, 'id', 'regions', 'title')
            self.assertTrue(any(item['title'] == 'London' for item in platform['regions']))
            for region in platform['regions']:
                self.assertTrue('id' in region)
                if platform['title'] == 'Freeview' and 'London' in region['title']:
                    region_id = region['id']
        return region_id

    def channels(self, region_id):
        resp = requests.get(f'https://api.tv-guide.future.sensi.link/channels/{region_id}')
        self.assertEqual(200, resp.status_code)
        channels = resp.json()
        self.assertIsInstance(channels, list)
        chan_names = []
        chan_id = None
        for chan in channels:
            has_keys(chan, 'categories', 'id', 'media', 'title')
            chan_names.append(chan['title'])
            if 'ITV1' in chan['title']:
                chan_id = chan['id']
        self.assertTrue('ITV1 London' in chan_names)
        self.assertTrue('ITV2' in chan_names)
        self.assertTrue('ITV3' in chan_names)
        self.assertTrue('ITV4' in chan_names)
        self.assertTrue('ITV Quiz' in chan_names)
        return chan_id

    def test_programmes(self):
        region_id = self.platforms()
        chan_id = self.channels(region_id)

        now = int(time.time())
        start_t = now - 2 * 86400
        end_t = now + 7 * 86400
        # schedule of ITV1
        url = f'https://api.tv-guide.future.sensi.link/schedules/{chan_id}/{start_t}/{end_t}'
        resp = requests.get(url)
        schedule = resp.json()
        self.assertIsInstance(schedule, list)
        first_pgm = {'timestamp': 9999999999999999}
        last_pgm = {'timestamp': 0}
        for pgm in schedule:
            title = pgm['title']
            has_keys(pgm, 'assets', 'channelId', 'channelName', 'dateTime', 'duration', 'endDateTime', 'endTimestamp',
                     'media', 'summary', 'title', obj_name=f"programme-{title}")
            has_keys(pgm['assets'],'category', 'contributor', 'number', 'summary', 'title', 'type',
                     obj_name=f"programme-{title}.assets")
            for summary in (pgm['summary'], pgm['assets']['summary']):
                self.assertIsInstance(summary, (dict, list))
                # Empty summaries are an empty list, rather than an empty dict.
                if isinstance(summary, list):
                    self.assertListEqual(summary, [])

            if 'season' in pgm['assets']:
                self.assertIsInstance(pgm['assets']['season'], int)

            if pgm['timestamp'] < first_pgm['timestamp']:
                first_pgm = pgm
            if pgm['timestamp'] > last_pgm['timestamp']:
                last_pgm = pgm
        TM_FMT = '%y-%m-%d %H:%M'
        # print(f"First programme: {time.strftime(TM_FMT, time.gmtime(first_pgm['timestamp']))} - {time.strftime(TM_FMT, time.gmtime(first_pgm['endTimestamp']))}")
        # print(f"First programme starts {(now - first_pgm['timestamp']) / 3600:0.2f} and ends {(now - first_pgm['endTimestamp']) / 3600:0.2f} hrs before now ")
        # print(f"last programme starts {(end_t - last_pgm['timestamp']) / 3600:0.2f} hrs before and ends {(last_pgm['endTimestamp'] - end_t) / 3600:0.2f} hrs after end_t")
        # The first programme played between 16 and 30 hrs before now.
        self.assertTrue(first_pgm['timestamp'] <= now - 8 * 3600)
        self.assertTrue(first_pgm['endTimestamp'] > now - 32 * 3600)
        # The last programme starts before end_t end stops after end_t
        self.assertTrue(last_pgm['timestamp'] < end_t)
        self.assertTrue(last_pgm['endTimestamp'] > end_t)
