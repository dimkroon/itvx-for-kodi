# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import unittest
import json

from unittest import TestCase


from support.object_checks import is_url
from support import object_checks, testutils

from ..gql_utils import gql_get, compress

setUpModule = fixtures.setup_web_test


class Introspection(unittest.TestCase):
    def test_inspect_brand(self):
        QUERY = """
        query BrandFields {
            __type(name:"brands") {
                fields {
                    name
                    description
                }  
            }
        }"""
        result = gql_get(compress(QUERY))
        self.assertEqual(result['errors'][0]['message'], 'Introspection is disabled')
