# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()


from unittest import TestCase

from resources.lib import interval


class TestInterval(TestCase):
    def test_instantiation(self):
        ival = interval.Interval(1, 2)

    def test_attributes(self):
        ival = interval.Interval(1, 3)
        self.assertEqual(1, ival.start)
        self.assertEqual(3, ival.end)
        self.assertEqual(2, ival.interval)

    def test_bool(self):
        b = bool(interval.Interval(1, 2))
        self.assertIs(bool(interval.Interval(1, 2)), True)

    def test_eq_comparison(self):
        self.assertTrue(interval.Interval(2.0, 2.0) == interval.Interval(2, 2))
        self.assertFalse(interval.Interval(1.0, 2.0) == interval.Interval(1.0, 2.5))
        self.assertFalse(interval.Interval(1.0, 2.0) == interval.Interval(1.5, 2.0))

    def test_less_comparison(self):
        self.assertTrue(interval.Interval(1, 2) < interval.Interval(1, 2.5))
        self.assertTrue(interval.Interval(1, 3) < interval.Interval(2, 2.5))
        self.assertFalse(interval.Interval(2.5, 3) < interval.Interval(1, 2))
        self.assertFalse(interval.Interval(2, 3) < interval.Interval(2, 2.5))
        self.assertFalse(interval.Interval(2, 2) < interval.Interval(2, 2))

    def test_less_or_equal_comparison(self):
        self.assertTrue(interval.Interval(1, 2) <= interval.Interval(1, 2.5))
        self.assertTrue(interval.Interval(1, 3) <= interval.Interval(2, 2.5))
        self.assertFalse(interval.Interval(2.5, 3) <= interval.Interval(1, 2))
        self.assertFalse(interval.Interval(2, 3) <= interval.Interval(2, 2.5))
        self.assertTrue(interval.Interval(2, 2) <= interval.Interval(2, 2))

    def test_greater_comparison(self):
        self.assertFalse(interval.Interval(1, 2) > interval.Interval(1, 2.5))
        self.assertFalse(interval.Interval(1, 3) > interval.Interval(2, 2.5))
        self.assertTrue(interval.Interval(2.5, 3) > interval.Interval(1, 2))
        self.assertTrue(interval.Interval(2, 3) > interval.Interval(2, 2.5))
        self.assertFalse(interval.Interval(2, 2) > interval.Interval(2, 2))

    def test_greater_or_equal_comparison(self):
        self.assertFalse(interval.Interval(1, 2) >= interval.Interval(1, 2.5))
        self.assertFalse(interval.Interval(1, 3) >= interval.Interval(2, 2.5))
        self.assertTrue(interval.Interval(2.5, 3) >= interval.Interval(1, 2))
        self.assertTrue(interval.Interval(2, 3) >= interval.Interval(2, 2.5))
        self.assertTrue(interval.Interval(2, 2) >= interval.Interval(2, 2))


class SkipIntervalTests(TestCase):
    @staticmethod
    def create_item():
        return interval.SkipIntervals(
                {'StartTime': '00:00:00:000', 'EndTime': '00:02:01:500'},
                {'StartTime': '00:05:06:000', 'EndTime': '00:06:07:050'},
                {'StartTime': '00:07:08:000', 'EndTime': '00:08:09:005'}
        )


    def test_instantiation(self):
        si = interval.SkipIntervals()
        si = interval.SkipIntervals({'StartTime': '00:00:00:000', 'EndTime': '00:02:01:500'})
        si = interval.SkipIntervals({'StartTime': '00:00:00:000', 'EndTime': '00:02:01:500'},
                                    {'StartTime': '00:05:06:000', 'EndTime': '00:06:07:050'})
        self.assertEqual(2, len(si))
        si = interval.SkipIntervals({'StartTime': '00:00:00:000', 'EndTime': '00:02:01:500'},
                                    {'StartTime': '00:01:06:000', 'EndTime': '00:02:30:050'})
        self.assertEqual(1, len(si))
        si = interval.SkipIntervals({'StartTime': '00:00:00:000', 'EndTime': '00:02:01:500'},
                                    {'StartTime': '00:01:06:000', 'EndTime': '00:02:30:050'},
                                    {'StartTime': '00:00:00:000', 'EndTime': '00:02:01:500'})
        self.assertEqual(1, len(si))

    def test_skip_from_start(self):
        si = interval.SkipIntervals({'StartTime': '00:00:00:000', 'EndTime': '00:02:01:500'})
        self.assertIs(si.skip_from_start, True)
        si = interval.SkipIntervals({'StartTime': '00:01:00:000', 'EndTime': '00:02:01:500'})
        self.assertIs(si.skip_from_start, False)
        # StartTime within min gap of start of the video
        si = interval.SkipIntervals({'StartTime': '00:00:04:000', 'EndTime': '00:02:01:500'})
        self.assertIs(si.skip_from_start, True)

    def test_get_item(self):
        si = self.create_item()
        ival = si[0]
        ival = si[1]
        ival = si[2]
        self.assertEqual(float('inf'), si[3].start)
        with self.assertRaises(IndexError):
            si[4]

    def test_set_item(self):
        si = self.create_item()
        si[2] = {'StartTime': '00:10:10:000', 'EndTime': '00:11:12:000'}

    def test_pop_item(self):
        si = self.create_item()
        l = len(si)
        ival = si.pop()
        self.assertIsInstance(ival, dict)
        self.assertEqual(l - 1, len(si))

    def test_add(self):
        si = self.create_item()
        si.add({'StartTime': '00:10:10:000', 'EndTime': '00:11:12:000'})
        si.add(interval.Interval(125, 160))

    def test_iterator(self):
        si = interval.SkipIntervals({'StartTime': '00:00:00:000', 'EndTime': '00:02:01:500'},
                                    {'StartTime': '00:05:06:000', 'EndTime': '00:06:07:050'})
        ival = next(si)
        self.assertEqual(0.0, ival['start'])
        self.assertEqual(121.5, ival['end'])
        ival = next(si)
        self.assertEqual(306, ival['start'])
        self.assertEqual(367.05, ival['end'])
        ival = next(si)
        self.assertEqual(float('inf'), ival['start'])
        self.assertEqual(float('inf'), ival['end'])
        self.assertRaises(StopIteration, next, si)