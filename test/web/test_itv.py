# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viewx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import patch

import typing

from resources.lib import itv
from codequick import Route

from test.support.object_checks import has_keys

setUpModule = fixtures.setup_web_test


@Route.register()
def dummycallback():
    pass


class TestItv(unittest.TestCase):
    def test_get_live_schedule(self):
        result = itv.get_live_schedule()
        self.assertEqual(6, len(result))
        # print(json.dumps(result, indent=4))
        for item in result:
            has_keys(item['channel'], 'name', 'strapline', '_links', obj_name=item['channel']['name'])
            for programme in item['slot']:
                has_keys(programme, 'programmeTitle', 'productionId', 'startTime', 'startAgainVod', 'vodLink',
                         'onAirTimeUTC', 'orig_start',
                         obj_name='-'.join((item['channel']['name'], programme['programmeTitle'])))

    def test_get_live_urls(self):
        result = itv.get_live_urls('https://simulcast.itv.com/playlist/itvonline/itv')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        # assert live provides no subtitles
        self.assertIsNone(result[2])
        # print(result)

    def test_get_catchup_urls(self):
        urls = (
            # something else with subtitles:
            'https://magni.itv.com/playlist/itvonline/ITV/10_0852_0001.001', )
        for url in urls:
            result = itv.get_catchup_urls(url)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 4)
            # print(result)

    def test_get_vtt_subtitles(self):
        srt_file = itv.get_vtt_subtitles('https://itvpnpsubtitles.blue.content.itv.com/1-7665-0049-001/Subtitles/2/'
                                         'WebVTT-OUT-OF-BAND/1-7665-0049-001_Series1662044575_TX000000.vtt')
        self.assertIsNone(srt_file)
        with patch.object(itv.Script, 'setting', new={'subtitles_show': 'true', 'subtitles_color': 'true'}):
            srt_file = itv.get_vtt_subtitles('https://itvpnpsubtitles.blue.content.itv.com/1-7665-0049-001/Subtitles/2/'
                                             'WebVTT-OUT-OF-BAND/1-7665-0049-001_Series1662044575_TX000000.vtt')
            self.assertIsInstance(srt_file, typing.Tuple)
            self.assertIsInstance(srt_file[0], str)
