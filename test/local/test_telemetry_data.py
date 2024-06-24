# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------


from unittest import TestCase
from unittest.mock import patch, MagicMock

from test.support.object_checks import is_not_empty

from resources.lib import telemetry_data


class TestTelemetryFactory(TestCase):
    def test_telemetry_factory(self):
        data = []
        fact = telemetry_data._TelemetryFactory()
        for i in range (len(telemetry_data.telemetry_data)):
            t_data = fact.get_data()
            self.assertTrue(is_not_empty(t_data, str))
            data.append(t_data)
        # Assert all data has only been returned once
        self.assertEqual(len(data), len(set(data)))
        # The next call should return data that has already been returned before
        new_data = fact.get_data()
        self.assertTrue(is_not_empty(new_data, str))
        self.assertTrue(new_data in data)
