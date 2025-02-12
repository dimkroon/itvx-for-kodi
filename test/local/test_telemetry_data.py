# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import re
from unittest import TestCase

from support.object_checks import is_not_empty
from support.testutils import doc_path


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


class TestaDate(TestCase):
    def test_missing_commas(self):
        """Ensure each line of data in the list must end with a comma, or python will
        automatically concatenate both lines to one single string.

        """
        tm_file = doc_path('../../plugin.video.viwx/resources/lib/telemetry_data.py')
        with open(tm_file, 'r') as f:
            match = re.search(r'telemetry_data = \[([^]]+)]', f.read())
        self.assertTrue(match)
        i = 0
        filtered_lines = 0
        for line in match[1].splitlines():
            i += 1
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            self.assertTrue(line.endswith(','), f'Line {i} does not end with a comma.')
            filtered_lines += 1
        self.assertEqual(filtered_lines, len(telemetry_data.telemetry_data))
