# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
#
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest

from resources.lib import cache

# noinspection PyPep8Naming
setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class TestCache(unittest.TestCase):
    my_str = '1234'
    my_list = [1, 2, 3, 4]
    my_dict = {1: '1', '2': 2}

    def test_cache_set_get(self):
        cache.purge()
        cache.set_item('1', self.my_str,  10)
        cache.set_item('2', self.my_list, 10)
        cache.set_item('3', self.my_dict,  10)
        self.assertEqual(self.my_str, cache.get_item('1'))
        self.assertListEqual(self.my_list, cache.get_item('2'))
        self.assertDictEqual(self.my_dict, cache.get_item('3'))

    def test_expire_time(self):
        cache.purge()
        cache.set_item('1', self.my_str, 10)
        cache.set_item('2', self.my_list, -10)
        cache.set_item('3', self.my_dict, 10)
        self.assertEqual(3, cache.size())
        self.assertIsNone(cache.get_item('2'))
        cache.clean()
        self.assertEqual(2, cache.size())

    def test_purge(self):
        cache.purge()
        cache.set_item('1', self.my_str, 10)
        cache.set_item('2', self.my_list, -10)
        self.assertEqual(self.my_str, cache.get_item('1'))
        self.assertEqual(2, cache.size())
        cache.purge()
        self.assertEqual(0, cache.size())
        self.assertIsNone(cache.get_item('1'))

    def test_changing_data_does_not_alter_cache(self):
        """Test that changing an object after it has been cached, or after it has been
        retrieved from cache does not affect the cached object.

        """
        new_list = self.my_list.copy()
        cache.set_item('n', new_list)
        new_list.pop()
        self.assertListEqual(cache.get_item('n'), self.my_list)

        cache.set_item('1', {'value': 123}, 10)
        item1 = cache.get_item('1')
        item2 = cache.get_item('1')
        self.assertIsNot(item1, item2)
