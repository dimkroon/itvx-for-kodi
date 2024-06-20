# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import unittest
import datetime


from test.support import testutils


class TestMockedDateTime(unittest.TestCase):
    def test_mocked_datetime_instantiation(self):
        dt = testutils.mockeddt(2014, 5, 16, 13, 24, 36)
        self.assertIsInstance(dt, datetime.datetime)

    def test_mocked_dt_now_naive(self):
        testutils.mockeddt.mocked_now = mocked_now = datetime.datetime(2024, 12, 11, 10, 9 ,8)
        now = testutils.mockeddt.now()
        self.assertEqual(mocked_now, now)
        self.assertIsNone(now.tzinfo)

        testutils.mockeddt.mocked_now = mocked_now = datetime.datetime(2024, 12, 11, 10, 9, 8, tzinfo=datetime.timezone.utc)
        now = testutils.mockeddt.now()
        self.assertNotEqual(mocked_now, now)
        self.assertIsNone(now.tzinfo)

    def test_mocked_dt_now_aware(self):
        bst = datetime.timezone(datetime.timedelta(hours=1), 'BST')
        testutils.mockeddt.mocked_now = mocked_now = datetime.datetime(2024, 12, 11, 10, 9 ,8)
        now = testutils.mockeddt.now(tz=bst)
        self.assertIs(now.tzinfo, bst)
        self.assertNotEqual(mocked_now, now)       # One is naive and the other is aware
        self.assertEqual(mocked_now.strftime('%H:%M'), now.strftime('%H:%M'))

        testutils.mockeddt.mocked_now = mocked_now = datetime.datetime(2024, 12, 11, 10, 9, 8, tzinfo=datetime.timezone.utc)
        now = testutils.mockeddt.now(tz=bst)
        self.assertEqual(mocked_now, now)           # both are aware, base dot the same time
        self.assertEqual('11:09', now.strftime('%H:%M'))
        self.assertEqual('10:09', mocked_now.strftime('%H:%M'))
        self.assertIs(now.tzinfo, bst)

