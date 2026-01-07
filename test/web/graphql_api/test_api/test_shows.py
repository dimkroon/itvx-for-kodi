# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import json

from unittest import TestCase

from ..gql_utils import gql_get, compress

setUpModule = fixtures.setup_web_test


class Shows(TestCase):
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
        data = gql_get(compress(query), self.VARS)
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
        data = gql_get(compress(query), self.VARS)
        self.assertGreater(len(data['brands']), 500)
        self.assertGreater(len(data['titles']), 400)
