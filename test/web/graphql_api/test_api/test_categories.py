# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import time

from unittest import TestCase

from support.object_checks import is_url
from support import object_checks, testutils

from ..gql_utils import gql_get, compress

setUpModule = fixtures.setup_web_test



class AvailableCategories(TestCase):
    def test_get_hub_category_names(self):
        t_s = time.monotonic()
        result = gql_get(
            operation_name='Categories',
            query='query Categories {genres(filter: {hubCategory: true}, sortBy: TITLE_ASC) {name id}}'
        )
        # testutils.save_json(result, 'categories/hub_categories.json')
        categories = result['data']['genres']
        t_e = time.monotonic()
        self.assertEqual(len(categories), 8)
        print("Fetched categories in {:0.3f} sec.".format(t_e - t_s))

    def test_get_other_category_names(self):
        """Get all categories that are not visible on the website."""
        result = gql_get(
            operation_name='Categories',
            query='query Categories { genres(filter: {hubCategory: false}, sortBy: TITLE_ASC) { __typename name id } }'
        )
        # testutils.save_json(result, 'categories/other_categories.json')
        categories = result['data']['genres']
        self.assertGreater(len(categories), 100)



class CategoryContent(TestCase):
    QUERY = """
query CategoryPage($broadcaster: Broadcaster, $features: [Feature!], $category: Category, $tiers: [Tier!]) { 
    brands(filter: {category: $category, tiers: $tiers, available: "NOW", broadcaster: $broadcaster}, sortBy: TITLE_ASC) { 
        __typename 
        ...CategoryPageBrandFields 
    }
    titles(filter: {hasBrand: false, category: $category, tiers: $tiers, available: "NOW", broadcaster: $broadcaster}, sortBy: TITLE_ASC) { 
        __typename 
        ...CategoryPageTitleFields 
    } 
} 
fragment CategoryPageBrandFields on Brand { 
    __typename 
    ccid 
    legacyId 
    imageUrl(imageType: ITVX)
    title 
    latestAvailableTitle { __typename ...CategoryPageTitleFields } 
    tier 
    partnership
    contentOwner
}
fragment CategoryPageTitleFields on Title { 
    __typename 
    ccid 
    brandLegacyId
    legacyId 
    imageUrl(imageType: ITVX) 
    title 
    channel { 
        __typename 
        name 
    } 
    titleType 
    broadcastDateTime
    latestAvailableVersion { 
        __typename 
        legacyId 
        duration 
    } 
    synopses { 
        __typename 
        ninety 
        epg 
    } 
    availableNow 
    tier 
    partnership 
    contentOwner
}"""

    VARS = (
        '{'
        '"broadcaster":"UNKNOWN",'
        '"features":["HD","PROGRESSIVE","SINGLE_TRACK","MPEG_DASH","WIDEVINE","WIDEVINE_DOWNLOAD",'
        '"INBAND_TTML","HLS","AES","INBAND_WEBVTT"],'
        '"category":"%s",'
        '"tiers":["FREE"]'
        '}')

    def test_get_category_comedy(self):
        data = gql_get(compress(self.QUERY), compress(self.VARS) % 'COMEDY')
        self.assertGreater(len(data['data']['brands']), 20)
        self.assertGreaterEqual(len(data['data']['titles']), 4)

    def test_get_all_category_children(self):
        data = gql_get(compress(self.QUERY), compress(self.VARS) % 'CHILDREN')
        self.assertGreater(len(data['data']['brands']), 40)
        self.assertGreaterEqual(len(data['data']['titles']), 2)

    def test_get_category_drama_and_soaps(self):
        data = gql_get(compress(self.QUERY), compress(self.VARS) % 'DRAMA_AND_SOAPS')
        # testutils.save_json(data, 'categories/drama_and_soaps.json')
        self.assertGreater(len(data['data']['brands']), 40)
        self.assertGreaterEqual(len(data['data']['titles']), 2)

    def test_get_category_sport(self):
        data = gql_get(compress(self.QUERY), compress(self.VARS) % 'SPORT')
        testutils.save_json(data, 'categories/sport.json')
        self.assertGreater(len(data['data']['brands']), 40)
        self.assertGreaterEqual(len(data['data']['titles']), 2)

    def test_get_category_news(self):
        data = gql_get(compress(self.QUERY), compress(self.VARS) % 'NEWS')
        testutils.save_json(data, 'categories/sport.json')
        self.assertGreater(len(data['data']['brands']), 40)
        self.assertGreaterEqual(len(data['data']['titles']), 2)
