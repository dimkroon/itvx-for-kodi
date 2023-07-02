# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from unittest import TestCase

from test.support import object_checks


class TestObjectChecks(TestCase):
    def test_is_url(self):
        self.assertTrue(object_checks.is_url('https://adskj'))
        self.assertFalse(object_checks.is_url('http://adskj'))     # unsecure fails
        self.assertTrue(object_checks.is_url('https://adskj/jbhnkjn.jpg', '.jpg'))
        self.assertFalse(object_checks.is_url('https://adskj/jbhnkjn.png', '.jpg'))
        self.assertTrue(object_checks.is_url('https://adskj/jbhnkjn.jpg?some=query&string=', '.jpg'))
        self.assertFalse(object_checks.is_url('https://adskj/jbhnkjn.jpg?some=query&string=', '.png'))

    def test_is_iso_time(self):
        self.assertTrue(object_checks.is_iso_utc_time("2019-05-26T23:10:32Z"))
        self.assertFalse(object_checks.is_iso_utc_time("19-05-26T23:10:32Z"))
        self.assertFalse(object_checks.is_iso_utc_time("2019-05-26 23:10:32Z"))
        self.assertFalse(object_checks.is_iso_utc_time("2019-05-26T23:10:32"))

        self.assertTrue(object_checks.is_iso_utc_time("2019-05-26T23:10:32.003Z"))
        self.assertTrue(object_checks.is_iso_utc_time("2019-05-26T23:10:32.3Z"))
        self.assertFalse(object_checks.is_iso_utc_time("2019-05-26T23:10:32.Z"))

    def test_misses_keys(self):
        d = {'a': 1, 'b': 2, 'c': 3}
        self.assertTrue(object_checks.misses_keys(d, 'z'))
        self.assertTrue(object_checks.misses_keys(d, 'z', 'x', 'y'))
        self.assertRaises(AssertionError, object_checks.misses_keys, d, 'b')
        self.assertRaises(AssertionError, object_checks.misses_keys, d, 'z', 'b')

    def test_expect_misses_keys(self):
        d = {'a': 1, 'b': 2, 'c': 3}
        self.assertTrue(object_checks.expect_misses_keys(d, 'z'))
        self.assertTrue(object_checks.expect_misses_keys(d, 'z', 'x', 'y'))
        self.assertFalse(object_checks.expect_misses_keys(d, 'b'))
        self.assertFalse(object_checks.expect_misses_keys(d, 'z', 'b'))
