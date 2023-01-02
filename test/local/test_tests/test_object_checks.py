# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
#
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
        self.assertTrue(object_checks.is_iso_time("2019-05-26T23:10:32Z"))
        self.assertFalse(object_checks.is_iso_time("19-05-26T23:10:32Z"))
        self.assertFalse(object_checks.is_iso_time("2019-05-26 23:10:32Z"))
        self.assertFalse(object_checks.is_iso_time("2019-05-26T23:10:32"))

        self.assertTrue(object_checks.is_iso_time("2019-05-26T23:10:32.003Z"))
        self.assertTrue(object_checks.is_iso_time("2019-05-26T23:10:32.3Z"))
        self.assertFalse(object_checks.is_iso_time("2019-05-26T23:10:32.Z"))


