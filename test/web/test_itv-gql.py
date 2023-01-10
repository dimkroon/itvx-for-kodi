# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
#
# ----------------------------------------------------------------------------------------------------------------------

from support import testutils
from test.support import fixtures
fixtures.global_setup()

import time
import re
import unittest
import requests

from test.support import object_checks, testutils


setUpModule = fixtures.setup_web_test


def compress(src_str: str) -> str:
    """Remove all whitespace from the start and end of a string and
    replace all whitespace within the string for a single space.

    """
    return re.compile(r'(\s+)').sub(' ', src_str.strip())


def _gql_query(query, variables=None, operation_name=None):
    params = {
        'query': query
    }
    if variables is not None:
        params['variables'] = variables
    if operation_name is not None:
        params['operationName'] = operation_name

    resp = requests.get(
        'https://content-inventory.prd.oasvc.itv.com/discovery',
        params=params
    )
    resp.raise_for_status()
    return resp.json()


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
        result = _gql_query(compress(QUERY))
        self.assertEqual(result['errors'][0]['message'], 'Introspection is disabled')


class Categories(unittest.TestCase):
    def test_get_hub_category_names(self):
        t_s = time.time()
        result = _gql_query(
            operation_name='Categories',
            query='query Categories {genres(filter: {hubCategory: true}, sortBy: TITLE_ASC) {name id}}'
        )
        # testutils.save_json(result, 'categories/hub_categories.json')
        categories = result['data']['genres']
        t_e = time.time()
        self.assertEqual(len(categories), 8)
        print("Fetched categories in {:0.3f} sec.".format(t_e - t_s))

    def test_get_other_category_names(self):
        """Get all categories that are not visible on the website."""
        result = _gql_query(
            operation_name='Categories',
            query='query Categories { genres(filter: {hubCategory: false}, sortBy: TITLE_ASC) { __typename name id } }'
        )
        # testutils.save_json(result, 'categories/other_categories.json')
        categories = result['data']['genres']
        self.assertGreater(len(categories), 100)


class CategoryContent(unittest.TestCase):
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
        data = _gql_query(compress(self.QUERY), compress(self.VARS) % 'COMEDY')
        self.assertGreater(len(data['data']['brands']), 20)
        self.assertGreaterEqual(len(data['data']['titles']), 4)

    def test_get_all_category_children(self):
        data = _gql_query(compress(self.QUERY), compress(self.VARS) % 'CHILDREN')
        self.assertGreater(len(data['data']['brands']), 40)
        self.assertGreaterEqual(len(data['data']['titles']), 2)

    def test_get_category_drama_and_soaps(self):
        data = _gql_query(compress(self.QUERY), compress(self.VARS) % 'DRAMA_AND_SOAPS')
        # testutils.save_json(data, 'categories/drama_and_soaps.json')
        self.assertGreater(len(data['data']['brands']), 40)
        self.assertGreaterEqual(len(data['data']['titles']), 2)

    def test_get_category_drama_and_soaps(self):
        data = _gql_query(compress(self.QUERY), compress(self.VARS) % 'SPORT')
        testutils.save_json(data, 'categories/sport.json')
        self.assertGreater(len(data['data']['brands']), 40)
        self.assertGreaterEqual(len(data['data']['titles']), 2)


class Shows(unittest.TestCase):
    VARS = ('{'
            '"broadcaster":"UNKNOWN",'
            '"features":["HD","PROGRESSIVE","SINGLE_TRACK","MPEG_DASH","WIDEVINE","WIDEVINE_DOWNLOAD",'
            '"INBAND_TTML","HLS","AES","INBAND_WEBVTT", "INBAND_WEBVTT"],'
            '"tiers":["FREE"]'
            '}')

    def test_programmes(self):
        """List all programmes
        Using the legacy name programmes, which apparently are now being called 'brands'
        """
        query = """
            query Shows($broadcaster: Broadcaster, $features: [Feature!], $tiers: [Tier!]) { 
                brands(filter: {tiers: $tiers, available: "NOW", broadcaster: $broadcaster}, sortBy: TITLE_ASC) { 
                    legacyId 
                    ccid 
                    series {
                        seriesNumber
                        numberOfAvailableEpisodes
                    }
                    numberOfAvailableSeries
                    genres {
                        name
                    }
                    imageUrl(imageType: ITVX)
                    title 
                    tier 
                    synopses {
                        ninety
                        epg
                    }
                }
            }
        """
        qs = compress(query)
        print(qs)
        print(qs[255:295])
        data = _gql_query(compress(query), self.VARS)
        self.assertGreater(len(data['data']['brands']), 500)
        self.assertGreater(len(data['data']['titles']), 400)

    def test_all_shows(self):
        query = """
            query Shows($broadcaster: Broadcaster, $features: [Feature!], $tiers: [Tier!]) { 
                brands(filter: {tiers: $tiers, available: "NOW", broadcaster: $broadcaster}, sortBy: TITLE_ASC) { 
                    __typename 
                    ...BrandFields 
                }
                titles(filter: {hasBrand: false, tiers: $tiers, available: "NOW", broadcaster: $broadcaster}, sortBy: TITLE_ASC) { 
                    __typename 
                    ...TitleFields 
                } 
            } 
            fragment BrandFields on Brand { 
                __typename 
                ccid 
                legacyId 
                imageUrl(imageType: ITVX)
                title 
                tier 
                partnership
                contentOwner
                series {
                    seriesNumber
                }
            }
            fragment TitleFields on Title { 
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
        data = _gql_query(compress(query), self.VARS)
        self.assertGreater(len(data['brands']), 500)
        self.assertGreater(len(data['titles']), 400)


    def test_request_a_titles_lagacy_id(self):
        query = """
        query TitleLegacyId($broadcaster: Broadcaster, $titleLegacyId: TitleLegacyId, $features: [Feature!]) {
            titles(filter: {legacyId: $titleLegacyId, broadcaster: $broadcaster, available: "NOW", platform: MOBILE, features: $features, tiers: ["FREE", "PAID"]}) { 
                __typename 
                brandLegacyId 
            } 
        }
        """
        vars = ('{'
                '"broadcaster":"UNKNOWN",'
                '"titleLegacyId":"10/3819/0001",'
                '"features":["HD","PROGRESSIVE","SINGLE_TRACK ","MPEG_DASH","WIDEVINE","WIDEVINE_DOWNLOAD","INBAND_TTML","HLS","AES","INBAND_WEBVTT" ]'
                '}')
        operationName = 'TitleLegacyId'


    def test_get_episode_page(self):
        query = """
            'query=query EpisodePage($broadcaster: Broadcaster, $brandLegacyId: BrandLegacyId, $features: [Feature!]) { 
                brands(filter: {legacyId: $brandLegacyId, tiers: ["FREE", "PAID"]}) { 
                    __typename 
                    title 
                    tier 
                    imageUrl(imageType: ITVX) 
                    synopses { 
                        __typename 
                        ninety 
                    } 
                    earliestAvailableTitle { 
                        __typename 
                        ccid 
                    } 
                    latestAvailableTitle { 
                        __typename 
                        ccid 
                    } s
                    eries(sortBy: SEQUENCE_ASC) { 
                        __typename 
                        seriesNumber 
                    } 
                    channel { 
                        __typename 
                        name 
                    } 
                } 
                titles(filter: {brandLegacyId: $brandLegacyId, broadcaster: $broadcaster, available: "NOW", platform: MOBILE, features: $features, tiers: ["FREE", "PAID"]}, sortBy: SEQUENCE_ASC) { 
                    __typename ...TitleFields 
                } 
            } fragment TitleFields on Title { 
                __typename 
                titleType 
                ccid 
                legacyId 
                brandLegacyId 
                title 
                brand { 
                    __typename 
                    title 
                    ccid 
                    legacyId 
                    synopses { 
                        __typename 
                        ninety 
                    } 
                    tier 
                    latestAvailableEpisode { 
                        __typename 
                        ccid 
                        title 
                    } 
                    genres(filter: {hubCategory: true}) { 
                        __typename name 
                    } 
                    channel { 
                        __typename 
                        name 
                    } 
                    earliestAvailableSeries { 
                        __typename 
                        seriesNumber 
                    } 
                    latestAvailableSeries { 
                        __typename 
                        seriesNumber 
                    } 
                    numberOfAvailableSeries 
                } 
                merchandisingTags { 
                    __typename 
                    id 
                } 
                nextAvailableTitle { 
                    __typename 
                    ccid 
                    legacyId 
                    latestAvailableVersion { 
                        __typename 
                        legacyId 
                    } 
                } 
                channel { 
                    __typename 
                    name 
                    strapline 
                } 
                broadcastDateTime 
                synopses { 
                    __typename 
                    ninety 
                } 
                imageUrl(imageType: ITVX) 
                regionalisation 
                latestAvailableVersion { 
                    __typename 
                    legacyId 
                    duration 
                    playlistUrl 
                    duration 
                    compliance { 
                        __typename 
                        displayableGuidance 
                    } 
                    availability { 
                        __typename 
                        downloadable 
                        end 
                        start 
                        maxResolution 
                        adRule 
                    } .
                    ..VariantsFields 
                    linearContent 
                    visuallySigned 
                    duration 
                    scheduleEvent { 
                        __typename 
                        broadcastDateTime 
                        originalBroadcastDateTime 
                    } 
                } 
                contentOwner 
                partnership 
                ... on Episode { 
                    ...EpisodeInfo 
                } 
                ... on Film { 
                    ...FilmInfo 
                } 
                ... on Special { 
                    ...SpecialInfo 
                } 
            } f
            ragment 
            VariantsFields on Version { 
                __typename 
                variants(filter: {features: $features}) {
                    __typename 
                    features 
                    variantId 
                    platform 
                } 
            } 
            fragment 
            EpisodeInfo on Episode { 
                __typename 
                series { 
                    __typename 
                    ...SeriesInfo 
                } 
                episodeNumber 
                tier 
            } 
            fragment SeriesInfo on Series { 
                __typename 
                longRunning 
                fullSeries 
                seriesNumber 
                numberOfAvailableEpisodes 
            } 
            fragment FilmInfo on Title { 
                __typename 
                ... on Film { 
                    title 
                    tier 
                    imageUrl(imageType: ITVX) 
                    synopses { 
                        __typename 
                        ninety 
                    } 
                    categories 
                    genres { 
                        __typename 
                        id 
                        name 
                        hubCategory 
                    } 
                } 
            } 
            fragment SpecialInfo on Special { 
                __typename 
                title 
                tier 
                imageUrl(imageType: ITVX) 
                synopses { 
                    __typename 
                    ninety 
                    thousand 
                } 
                categories 
                genres { 
                `   __typename 
                    id 
                    name 
                    hubCategory 
                } 
            }
        """
        vars = ('{'
                '"broadcaster":"UNKNOWN",'
                '"brandLegacyId":"10/3819",'
                '"features":["HD","PROGRESSIVE","SINGLE_TRACK","MPEG_DASH","WIDEVINE","WIDEVINE_DOWNLOAD","INBAND_TTML","HLS","AES","INBAND_WEBVTT","OUTBAND_WEBVTT","INBAND_AUDIO_DESCRIPTION"]'
                '}')
        operationName='EpisodePage'

