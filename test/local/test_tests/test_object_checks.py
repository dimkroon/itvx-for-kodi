# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from unittest import TestCase

from test.support import object_checks as oc


class TestObjectChecks(TestCase):
    def test_is_url(self):
        self.assertTrue(oc.is_url('https://adskj'))
        self.assertFalse(oc.is_url('http://adskj'))     # unsecure fails
        self.assertTrue(oc.is_url('https://adskj/jbhnkjn.jpg', '.jpg'))
        self.assertFalse(oc.is_url('https://adskj/jbhnkjn.png', '.jpg'))
        self.assertTrue(oc.is_url('https://adskj/jbhnkjn.jpg?some=query&string=', '.jpg'))
        self.assertFalse(oc.is_url('https://adskj/jbhnkjn.jpg?some=query&string=', '.png'))
        self.assertTrue(oc.is_url('https://adskj/jbhnkjn.jpg', ('.bmp', '.jpg', '.png')))
        self.assertFalse(oc.is_url('https://adskj/jbhnkjn.jpg', ('.bmp', '.gif', '.png')))

    def test_is_iso_time(self):
        self.assertTrue(oc.is_iso_utc_time("2019-05-26T23:10:32Z"))
        self.assertFalse(oc.is_iso_utc_time("19-05-26T23:10:32Z"))
        self.assertFalse(oc.is_iso_utc_time("2019-05-26 23:10:32Z"))
        self.assertFalse(oc.is_iso_utc_time("2019-05-26T23:10:32"))

        self.assertTrue(oc.is_iso_utc_time("2019-05-26T23:10:32.003Z"))
        self.assertTrue(oc.is_iso_utc_time("2019-05-26T23:10:32.3Z"))
        self.assertFalse(oc.is_iso_utc_time("2019-05-26T23:10:32.Z"))

    def test_misses_keys(self):
        d = {'a': 1, 'b': 2, 'c': 3}
        self.assertTrue(oc.misses_keys(d, 'z'))
        self.assertTrue(oc.misses_keys(d, 'z', 'x', 'y'))
        self.assertRaises(AssertionError, oc.misses_keys, d, 'b')
        self.assertRaises(AssertionError, oc.misses_keys, d, 'z', 'b')

    def test_expect_misses_keys(self):
        d = {'a': 1, 'b': 2, 'c': 3}
        self.assertTrue(oc.expect_misses_keys(d, 'z'))
        self.assertTrue(oc.expect_misses_keys(d, 'z', 'x', 'y'))
        self.assertFalse(oc.expect_misses_keys(d, 'b'))
        self.assertFalse(oc.expect_misses_keys(d, 'z', 'b'))


class IsNotEmpy(TestCase):
    def test_is_not_empty_string(self):
        self.assertTrue(oc.is_not_empty('dfsd', str))
        self.assertFalse(oc.is_not_empty('', str))
        self.assertFalse(oc.is_not_empty(124, str))
        self.assertFalse(oc.is_not_empty(None, str))

    def test_is_not_empty_int(self):
        self.assertTrue(oc.is_not_empty(124, int))
        self.assertTrue(oc.is_not_empty(0, int))
        self.assertFalse(oc.is_not_empty(12.56, int))
        self.assertFalse(oc.is_not_empty('124', int))
        self.assertFalse(oc.is_not_empty(None, int))

    def test_is_not_empty_float(self):
        self.assertTrue(oc.is_not_empty(124.45, float))
        self.assertTrue(oc.is_not_empty(0.0, float))
        self.assertFalse(oc.is_not_empty(12, float))
        self.assertFalse(oc.is_not_empty('124.25', float))
        self.assertFalse(oc.is_not_empty(None, float))

    def test_is_not_empty_bool(self):
        self.assertTrue(oc.is_not_empty(True, bool))
        self.assertTrue(oc.is_not_empty(False, bool))
        self.assertFalse(oc.is_not_empty(None, bool))
        self.assertFalse(oc.is_not_empty(1, bool))

