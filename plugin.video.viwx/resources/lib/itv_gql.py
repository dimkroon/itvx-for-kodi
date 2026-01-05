# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------


import json
import logging
import requests

from codequick.support import logger_id

from . import fetch

logger = logging.getLogger(logger_id + '.itvx')


def _gql_query(query, variables=None, operation_name=None):
    params = {
        'query': query
    }
    if variables is not None:
        params['variables'] = json.dumps(variables)
    if operation_name is not None:
        params['operationName'] = operation_name

    resp = fetch.get_json(
        'https://content-inventory.prd.oasvc.itv.com/discovery',
        params=params
    )
    return resp


def _gql_post(url, query, variables=None):
    data = {'query': query}
    if variables:
        data['variables'] = variables
    resp = requests.post(
            url,
            headers={
             'user-agent': fetch.USER_AGENT,
             'origin': 'https://app.10ft.itv.com',
             'referer': 'https://app.10ft.itv.com/'
            },
            json=data)
    data = json.loads(resp.content)
    return data


def get_playlist_url(ccid: str, prefer_bsl: bool = False):
    """Return the playlist url of the title specified by ccid.

    """
    query = (
        'query Title {'
            'titles(filter: {ccid: "%s"}) {'
                '__typename '
                'title '
                'ccid '
                'latestAvailableVersion {'
                    'audioDescribed '
                    'playlistUrl '
                    'bsl { playlistUrl }'
                '}'
            '}'
        '}'
    ) % ccid

    titles = _gql_query(query)['data']['titles']
    if len(titles) > 1:
        logger.warning("get_playlist_urls got multiple titles for ccid '%s': %s", ccid, titles)
    version = titles[0]['latestAvailableVersion']
    bsl = version['bsl']
    if prefer_bsl and bsl:
        return bsl.get('playlistUrl') or version['playlistUrl']
    else:
        return version['playlistUrl']


def get_short_playlist_url(ccid: str, is_sport: bool = False):
    query = (
        'query GetClipByCcid($ccid: ID!, $isNews: Boolean!, $isSport: Boolean!) {'
            'clip(ccid: $ccid) @include(if: $isNews) {'
                'ccid '
                'title '
                'duration '
                'playlistLink '
                'subtitles '
                'guidance '
                'syndicatedToSTV '
            '}'
            'sportsClip(ccid: $ccid) @include(if: $isSport) {'
                'ccid '
                'title '
                'duration '
                'playlistLink '
                'subtitles '
                'guidance '
                'syndicatedToSTV '
            '}'
        '}'
    )
    variables = {
        "ccid": ccid,
        "isNews": not is_sport,
        "isSport": is_sport
    }

    data = _gql_post('https://shortform.prd.shows.itv.com/graphql', query, variables)
    if is_sport:
        return data['data']['sportsClip']['playlistLink']
    else:
        return data['data']['clip']['playlistLink']


def get_category(category: str):
    query = (
        'query GetPage( $pagesFilter: PageFilter! '
                        '$itemsFilter: CollectionItemFilter! '
                        '$collectionLimit: Int '
                        '$platform: Platform! '
                        '$withUpsell: Boolean! '
                        '$withSimulcast: Boolean! '
                        '$withFastChannels: Boolean! '
                        '$withNewContentTags: Boolean! ) { '
            'pages(filter: $pagesFilter) { '
                'id '
                'name '
                'subtitle '
                'imageUrl '
                'category '
                'adServed '
                'items { '
                    'name '
                    'targetedContainer { '
                        'id '
                        'name '
                        'destination '
                        'priority '
                        'containerType '
                        'displayType '
                        'content {'
                            '__typename '
                            '... on CollectionSpot { '
                                'collection { '
                                    '__typename '
                                    'id '
                                    'itemCount '
                                    'title '
                                    'subtitle '
                                    'subsequentJourney { '
                                        'name '
                                        'label '
                                        'destinationUrl(platform: $platform) '
                                        'imageUrl '
                                    '} '
                                    'imageTreatment '
                                    'imageAspectRatio '
                                    'imageClass '
                                    # 'adServed '
                                    'excludeTimeDependentTags @include(if: $withNewContentTags) '
                                    'items(filter: $itemsFilter limit: $collectionLimit) { '
                                        'itemType '
                                        '__typename '
                                        '... on SeriesCollectionItem { '
                                            'imageUrl '
                                            'seriesItem { '
                                                'tier '
                                                'imageUrl(imageType: ITVX) '
                                                '__typename '
                                                'seriesNumber '
                                                'numberOfEpisodes '
                                                'ccid '
                                                'synopses { ninety epg } '
                                                'visuallySigned '
                                                'subtitled ' 
                                                'audioDescribed '
                                                'strapline '
                                                'brand { '
                                                    # 'legacyId '
                                                    'title '
                                                    # 'channel { name } '
                                                    'ccid '
                                                    # 'imageUrl(imageType: ITVX) '
                                                    # 'partnership '
                                                    # 'contentOwner '
                                                    'synopses { epg } '
                                                    'series { seriesNumber } '
                                                    'genres { id name } '
                                                    'subgenres { id name } '
                                                '}' 
                                                # 'earliestAvailableEpisode { '
                                                #     'legacyId '
                                                #     'imageUrl(imageType: ITVX) '
                                                #     'broadcastDateTime '
                                                #     'brandLegacyId '
                                                #     'availableNow '
                                                #     'ccid '
                                                # '}'
                                                'timeDependentTags @include(if: $withNewContentTags) { '
                                                    'key '
                                                    'label '
                                                '}' 
                                                # 'attribution { '
                                                #     'partnership { '
                                                #         'name '
                                                #         'imageUrls { ctvBrowser } '
                                                #     '}'
                                                #     'contentOwner { '   
                                                #         'name '
                                                #         'imageUrls { ctvBrowser } '
                                                #     '} '
                                                # '} '
                                            '} '
                                        '} '
                                        '... on TitleCollectionItem { '
                                            'imageUrl '
                                            'titleItem { '
                                                'titleType '
                                                'tier '
                                                'partnership '
                                                'contentOwner '
                                                'title '
                                                'brandLegacyId '
                                                'legacyId '
                                                'broadcastDateTime '
                                                '__typename '
                                                'visuallySigned '
                                                'subtitled '
                                                'audioDescribed '
                                                'synopses { epg ninety } '
                                                'strapline '
                                                'attribution { '
                                                    'partnership { '
                                                        'name '
                                                        'imageUrls { ctvBrowser } '
                                                    '} '
                                                    'contentOwner { '
                                                        'name '
                                                        'imageUrls { ctvBrowser } '
                                                    '} '
                                                '} '
                                                '... on Special { '
                                                    'ccid '
                                                    'broadcastDateTime '
                                                    'title '
                                                    'timeDependentTags @include(if: $withNewContentTags) { '
                                                        'key '
                                                        'label '
                                                    '} '
                                                    'latestAvailableVersion { duration } '
                                                    'brand { '
                                                        'imageUrl(imageType: ITVX) '
                                                        'synopses { epg } '
                                                    '} '
                                                    'genres { id name } '
                                                    'subgenres { id name } '
                                                '} '
                                                '... on Film { '
                                                    'title '
                                                    'timeDependentTags @include(if: $withNewContentTags) { key label } '
                                                    'latestAvailableVersion { duration } '
                                                    'brand { '
                                                        'imageUrl(imageType: ITVX) '
                                                        'synopses { epg } '
                                                    '} '
                                                    'productionYear '
                                                    'genres { id name } '
                                                    'subgenres { id name } '
                                                    'ccid '
                                                '} '
                                                '... on Episode { '
                                                    'ccid '
                                                    'episodeNumber '
                                                    'seriesNumber '
                                                    'broadcastDateTime '
                                                    'timeDependentTags @include(if: $withNewContentTags) { key label } '
                                                    'brand { '
                                                        'title '
                                                        'imageUrl(imageType: ITVX) '
                                                        'partnership '
                                                        'contentOwner '
                                                        'synopses { epg } '
                                                        'genres { id name } '
                                                        'subgenres { id name } '
                                                    '} '
                                                    'versions { duration } '
                                                '} '
                                                '... on Title { '
                                                    'titleType '
                                                    'imageUrl(imageType: ITVX) '
                                                    'legacyId '
                                                    'brandLegacyId '
                                                    'brand { '
                                                        'title '
                                                        'legacyId '
                                                        'imageUrl(imageType: ITVX) '
                                                        'partnership '
                                                        'contentOwner '
                                                        'genres { id name } '
                                                        'subgenres { id name } '
                                                        'synopses { epg ninety } '
                                                        'ccid '
                                                    '} '
                                                    'broadcastDateTime '
                                                    'channel { name } ' 
                                                    'series { seriesNumber longRunning } '
                                                    'availableNow '
                                                    'synopses { epg ninety } '
                                                '} '
                                            '} '
                                        '} '
                                        '... on BrandCollectionItem { '
                                            'imageUrl '
                                            'brandItem { '  
                                                'ccid '
                                                '__typename '
                                                'tier '
                                                'title '
                                                'numberOfAvailableSeries '
                                                'synopses { ninety epg } '
                                                'imageUrl(imageType: ITVX) '
                                                'legacyId '
                                                'genres { id name } '
                                                'subgenres { id name } '
                                                'channel { name } '
                                                'series { seriesNumber } '
                                                'latestAvailableTitle { '   
                                                    'imageUrl(imageType: ITVX) '
                                                    'broadcastDateTime '
                                                    'availableNow '
                                                '} '
                                                'partnership '
                                                'contentOwner '
                                                'visuallySigned '
                                                'subtitled '
                                                'audioDescribed '
                                                'strapline '
                                                'timeDependentTags @include(if: $withNewContentTags) { key label } '
                                                'attribution { '
                                                    'partnership { '
                                                        'name '
                                                        'imageUrls { ctvBrowser } '
                                                    '} '
                                                    'contentOwner { '
                                                        'name '
                                                        'imageUrls { ctvBrowser } '
                                                    '} '
                                                '} '
                                            '} '
                                        '} '
                                        '...on PageCollectionItem { '
                                            'imageUrl '
                                            'strapline '
                                            'title '
                                            'subtitle '
                                            'pageItem { '
                                                'id '
                                                'name '
                                                'category '
                                                'subtitle '
                                                'adServed '
                                            '} '
                                        '} '
                                        '... on CollectionCollectionItem { '
                                            'title '
                                            'imageUrl '
                                            'strapline '
                                            'subtitle '
                                            'collectionItem { '
                                                'id '
                                                'itemCount '
                                                'adServed '
                                            '} '
                                        '} '
                                        '... on UrlSpotCollectionItem { '
                                            'title '
                                            'subtitle '
                                            'imageUrl '
                                            'url '
                                        '} '
                                        '... on UpsellSpotCollectionItem @include(if: $withUpsell) { '
                                            'title '
                                            'subtitle '
                                            'strapline '
                                            'imageUrl '
                                        '} '
                                        '... on SimulcastSpotCollectionItem @include(if: $withSimulcast) { '
                                            'title '
                                            'subtitle '
                                            'startDateTime '
                                            'endDateTime '
                                            'channel { name } '
                                            'genre { name } '
                                            'imageUrl '
                                            'strapline '
                                            'startDateTime '
                                            'endDateTime '
                                        '} '
                                        '... on FastChannelSpotCollectionItem @include(if: $withFastChannels) { '
                                            'title '
                                            'subtitle '
                                            'fastChannel '
                                            'imageUrl '
                                            'strapline '
                                            'startDateTime '
                                            'endDateTime '
                                        '} '
                                        '... on NewsCategoryPageSpotItem { '
                                            'title '
                                            'subtitle '
                                            'imageUrl '
                                            'strapline '
                                        '} ... on ShortformCollectionItem { '
                                            'title '
                                            'subtitle '
                                            'strapline '
                                            'ccid '
                                            'slug '
                                            'imageUrl '
                                        '} '
                                    '} '
                                '} '
                            '} '
                        '} '
                    '} '
                '} '
            '}'
        '}'
    )

    variables = {
        "pagesFilter": {
            "category": category.upper(),
            "tiers": ["FREE"],
            "available": "NOW"
        },
        "collectionLimit": 12,
        "platform": "CTV",
        "itemsFilter": {
            "itemTypes": ["BRAND", "SERIES", "TITLE", "COLLECTION", "PAGE", "URLSPOT",
                          "NEWSCATEGORYPAGESPOT", "SHORTFORM", "UPSELLSPOT", "SIMULCASTSPOT",
                          "FASTCHANNELSPOT"],
            "features": ["OUTBAND_WEBVTT", "MPEG_DASH", "WIDEVINE", "HD", "SINGLE_TRACK", "INBAND_AUDIO_DESCRIPTION"],
            "broadcaster": "ITV",
            "platform": "CTV"
        },
        "withUpsell": True,
        "withSimulcast": True,
        "withFastChannels": True,
        "withNewContentTags": True
    }
    return _gql_query(query, variables)


def category_az(cat):
    query = (
        'query GetCategoryContent( $brandFilter: BrandFilter $titleFilter: TitleFilter $limit: Int $isFilm: Boolean! $isBsl: Boolean! $withNewContentTags: Boolean! ) {'
            'brands(sortBy: TITLE_ASC filter: $brandFilter limit: $limit) @skip(if: $isFilm) { '
                '__typename '
                'ccid '
                'tier '
                'title '
                # 'legacyId '
                # 'channel { name } '
                'latestAvailableTitle {'
                    'broadcastDateTime '
                    # 'legacyId '
                    'latestAvailableVersion { duration } '
                '} '
                'imageUrl(imageType: ITVX) '
                'synopses { ninety, epg } '
                'series { '
                    '__typename '
                    # 'seriesNumber '
                    # 'fullSeries '
                    'numberOfAvailableEpisodes '
                '} '
                # 'partnership '
                # 'contentOwner '
                'genres(filter: { hubCategory: true }) { id name }'
                'timeDependentTags @include(if: $withNewContentTags) { key label } '
                # 'attribution { '
                #     'partnership { name } '
                #     'contentOwner { name } '
                # '}' 
            '} '
            'titles(sortBy: TITLE_ASC filter: $titleFilter limit: $limit) @include(if: $isBsl){ '
                '__typename '
                'ccid '
                'tier '
                # 'partnership '
                # 'contentOwner '
                'title '
                # 'legacyId '
                'imageUrl(imageType: ITVX) '
                # 'brandLegacyId '
                # 'channel { name } '
                'broadcastDateTime '
                'synopses { ninety, epg } '
                'latestAvailableVersion { duration } '
                'timeDependentTags @include(if: $withNewContentTags) { key label } '
                # 'attribution { '
                #     'partnership { name } '
                #     'contentOwner { name } '
                # '} '
            '} '
            'titles(sortBy: TITLE_ASC filter: $titleFilter limit: $limit) @skip(if: $isBsl) { '
                '... on Film @include(if: $isFilm) { '
                    '__typename '
                    'ccid '
                    'tier '
                    # 'partnership '
                    # 'contentOwner '
                    'title '
                    # 'legacyId '
                    'imageUrl(imageType: ITVX) '
                    # 'brandLegacyId '
                    # 'channel { name } '
                    'broadcastDateTime '
                    'synopses { ninety, epg } '
                    'latestAvailableVersion { duration } '
                    # 'attribution { '
                    #     'partnership { name } ' 
                    #     'contentOwner { name } '
                    # '} ' 
                    'timeDependentTags @include(if: $withNewContentTags) { key label } '
                '} ' 
                '... on Special @skip(if: $isFilm) {'
                    '__typename '
                    'ccid '
                    'tier '
                    # 'partnership '
                    # 'contentOwner '
                    'title '
                    # 'legacyId '
                    'imageUrl(imageType: ITVX) '
                    # 'brandLegacyId '
                    # 'channel { name } '
                    'broadcastDateTime '
                    'synopses { ninety , epg} '  
                    'latestAvailableVersion { duration } '  
                    # 'attribution {'
                    #     'partnership { name } '
                    #     'contentOwner { name } '
                    # '} '
                    'timeDependentTags @include(if: $withNewContentTags) { key label } '
                '} '
            '} '
        '}'
    )

    variables = {
        "brandFilter": {
            "available": "NOW",
            "features": ["OUTBAND_WEBVTT","MPEG_DASH","WIDEVINE","HD","SINGLE_TRACK","INBAND_AUDIO_DESCRIPTION"],
            "broadcaster": "ITV",
            "platform": "CTV",
            "tiers": ["FREE"],
            "visuallySigned": None,
            "genreId": cat.upper()
        },
        "titleFilter": {
            "available": "NOW",
            "features": ["OUTBAND_WEBVTT","MPEG_DASH","WIDEVINE","HD","SINGLE_TRACK","INBAND_AUDIO_DESCRIPTION"],
            "broadcaster": "ITV",
            "platform": "CTV",
            "tiers": ["FREE"],
            "visuallySigned": None,
            "genreId": cat.upper(),
            "titleTypes": None,
            "titleType": "SPECIAL",
            "hasBrand": False
        },
        "limit": None,
        "isFilm":False,
        "isBsl": False,
        "withNewContentTags":True
    }
    return _gql_query(query, variables)