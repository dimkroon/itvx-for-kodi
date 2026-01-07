# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase

from ..gql_utils import gql_get, compress

setUpModule = fixtures.setup_web_test


# noinspection PyMethodMayBeStatic
class Titles(TestCase):

    def test_request_a_title_by_legacy_id(self):
        query = """
        query TitleLegacyId($broadcaster: Broadcaster, $titleLegacyId: TitleLegacyId, $features: [Feature!]) {
            titles(filter: {legacyId: $titleLegacyId, broadcaster: $broadcaster, available: "NOW", platform: MOBILE, 
                            features: $features, tiers: ["FREE", "PAID"]}) { 
                __typename 
                brandLegacyId 
            } 
        }
        """
        variables = (
            '{'
            '"broadcaster":"UNKNOWN",'
            '"titleLegacyId":"10/3819/0001",'
            '"features":["HD","PROGRESSIVE","SINGLE_TRACK","MPEG_DASH","WIDEVINE","WIDEVINE_DOWNLOAD",'
            '            "INBAND_TTML","HLS","AES","INBAND_WEBVTT" ]'
            '}')
        operationName = 'TitleLegacyId'
        resp = gql_get(compress(query), variables, operationName)
        pass

    def test_request_a_title_from_ccid(self):
        query = (
            'query Title {'
                'titles(filter: {ccid: "%s"}) {' 
                    '__typename '
                    'title '
                    'ccid '
                    'brandLegacyId '
                    'latestAvailableVersion {' 
                        'audioDescribed '
                        'playlistUrl '
                        'bsl { playlistUrl }'
                    '}'
                '}' 
            '}'
        ) % "9r8cx9g"
        resp = gql_get(compress(query))
        pass

    def test_get_episode_page(self):
        query = """
            'query EpisodePage($broadcaster: Broadcaster, $brandLegacyId: BrandLegacyId, $features: [Feature!]) { 
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
                titles(filter: {brandLegacyId: $brandLegacyId, broadcaster: $broadcaster, available: "NOW", 
                       platform: MOBILE, features: $features, tiers: ["FREE", "PAID"]}, sortBy: SEQUENCE_ASC) { 
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
            } 
            fragment VariantsFields on Version { 
                __typename 
                variants(filter: {features: $features}) {
                    __typename 
                    features 
                    variantId 
                    platform 
                } 
            } 
            fragment EpisodeInfo on Episode { 
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
        variables = (
            '{'
            '"broadcaster":"UNKNOWN",'
            '"brandLegacyId":"10/3819",'
            '"features":["HD","PROGRESSIVE","SINGLE_TRACK","MPEG_DASH","WIDEVINE","WIDEVINE_DOWNLOAD",'
            '"INBAND_TTML","HLS","AES","INBAND_WEBVTT","OUTBAND_WEBVTT","INBAND_AUDIO_DESCRIPTION"]'
            '}')
        operationName = 'EpisodePage'
        resp = gql_get(compress(query), variables, operationName)
        pass
