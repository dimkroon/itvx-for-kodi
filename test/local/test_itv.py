# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import time

# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------


from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch
import pytz

from test.support.testutils import open_json
from test.support.object_checks import has_keys

from resources.lib import itv
from resources.lib import itv_account
from resources.lib import errors

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
        local_tz = pytz.timezone('America/Fort_Nelson')
        schedule = itv.get_live_schedule(local_tz=pytz.utc)
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
            schedule = itv.get_live_schedule(local_tz=pytz.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('19:30', start_time)
        with patch('xbmc.getRegion', return_value='%I:%M %p'):
            schedule = itv.get_live_schedule(local_tz=pytz.utc)
            start_time = schedule[0]['slot'][0]['startTime']
            self.assertEqual('07:30 pm', start_time.lower())


class RequestStreamData(TestCase):
    def test_request_with_auth_failure(self):
        itv_account.itv_session().log_out()
        self.assertRaises(errors.AuthenticationError, itv._request_stream_data, 'some/url')