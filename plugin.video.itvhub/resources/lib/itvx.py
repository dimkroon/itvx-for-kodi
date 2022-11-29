#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
#

import os
import string
import time
import logging

from datetime import datetime
import pytz


from codequick.support import logger_id

from . import fetch

from .itv import get_live_schedule


logger = logging.getLogger(logger_id + '.itv')

FEATURE_SET = 'hd,progressive,single-track,mpeg-dash,widevine,widevine-download,inband-ttml,hls,aes,inband-webvtt,outband-webvtt,inband-audio-description'
PLATFORM_TAG = 'mobile'


def get_live_channels():
    from tzlocal import get_localzone
    local_tz = get_localzone()
    utc_tz = pytz.utc

    live_data = fetch.get_json(
        'https://nownext.oasvc.itv.com/channels',
        params={
            'broadcaster': 'itv',
            'featureSet': FEATURE_SET,
            'platformTag': PLATFORM_TAG})

    fanart_url = live_data['images']['backdrop']

    main_schedule = get_live_schedule()

    channels = live_data['channels']

    for channel in channels:
        channel['backdrop'] = fanart_url
        slots = channel.pop('slots')

        # The itv main live channels get their schedule from the full live schedule
        if channel['channelType'] == 'simulcast':
            chan_id = channel['id']
            for main_chan in main_schedule:
                # Caution, might get broken when ITV becomes ITV1 everywhere
                if main_chan['channel']['name'] == chan_id:
                    channel['slot'] = main_chan['slot']
                    break
            if channel.get('slot'):
                # On to the next channel if adding full schedule succeeded
                continue

        programs_list = []
        for prog in (slots['now'], slots['next']):
            if prog['detailedDisplayTitle']:
                title = ': '.join((prog['displayTitle'], prog['detailedDisplayTitle']))
            else:
                title = prog['displayTitle']

            start_t = prog['start'][:19]
            # TODO: check this in DST period
            utc_start = datetime(*(time.strptime(start_t, '%Y-%m-%dT%H:%M:%S')[0:6])).replace(tzinfo=utc_tz)

            programs_list.append({
                'programmeTitle': title,
                'orig_start': None,  # fast channels do not support play from start
                'startTime': utc_start.astimezone(local_tz).strftime('%H:%M')
            })
        channel['slot'] = programs_list
    return channels


def categories():
    """Return all available categorie names."""
    result = fetch.get_json(
        'https://content-inventory.prd.oasvc.itv.com/discovery',
        params={
            'operationName': 'Categories',
            'query': 'query Categories { genres(filter: {hubCategory: true}, sortBy: TITLE_ASC) { __typename name id } }'
        })
    cat_list = result['data']['genres']
    return ({'label': cat['name'], 'params': {'id': cat['id']}} for cat in cat_list)


def category_content(cat_id: str):
    """Return all programmes in a category"""
    if cat_id == 'FILM':
        return get_category_films()

    result = fetch.get_json(
        'https://content-inventory.prd.oasvc.itv.com/discovery',
        params={
            'operationName': 'CategoryPage',
            'query': 'query CategoryPage($broadcaster: Broadcaster, $features: [Feature!], $category: Category, '
                     '$tiers: [Tier!]) { brands(filter: {category: $category, tiers: $tiers, available: "NOW", '
                     'broadcaster: $broadcaster}, sortBy: TITLE_ASC) { __typename ...CategoryPageBrandFields } '
                     'titles(filter: {hasBrand: false, category: $category, tiers: $tiers, available: "NOW", '
                     'broadcaster: $broadcaster}, sortBy: TITLE_ASC) { __typename ...CategoryPageTitleFields } } '
                     'fragment CategoryPageBrandFields on Brand { __typename ccid legacyId imageUrl(imageType: ITVX) '
                     'title latestAvailableTitle { __typename ...CategoryPageTitleFields } tier partnership '
                     'contentOwner } fragment CategoryPageTitleFields on Title { __typename ccid brandLegacyId '
                     'legacyId imageUrl(imageType: ITVX) title channel { __typename name } titleType broadcastDateTime '
                     'latestAvailableVersion { __typename legacyId duration } synopses { __typename ninety epg } '
                     'availableNow tier partnership contentOwner }',
            'variables': '{"broadcaster":"UNKNOWN",'
                         '"features":["HD","PROGRESSIVE","SINGLE_TRACK","MPEG_DASH","WIDEVINE","WIDEVINE_DOWNLOAD",'
                         '"INBAND_TTML","HLS","AES","INBAND_WEBVTT"],'
                         '"category":"%s",'
                         '"tiers":["FREE"]}' % cat_id
        })
    return result['data']['brands']


def get_category_films():
    """Return all films in the category films"""
    result = fetch.get_json(
        'https://content-inventory.prd.oasvc.itv.com/discovery',
        params={
            'operationName': 'Films',
            'query': 'query Films($broadcaster: Broadcaster, $features: [Feature!], $tiers: [Tier!]) '
                     '{ titles(filter: {titleType: FILM, available: "NOW", tiers: $tiers, broadcaster: $broadcaster}, '
                     'sortBy: TITLE_ASC) { __typename ccid legacyId brandLegacyId imageUrl(imageType: ITVX) '
                     'title tier channel { __typename name } broadcastDateTime latestAvailableVersion '
                     '{ __typename legacyId duration } availableNow synopses { __typename ninety epg } '
                     'partnership contentOwner } }',
            'variables': '{"broadcaster":"UNKNOWN",'
                         '"features":["HD","PROGRESSIVE","SINGLE_TRACK","MPEG_DASH","WIDEVINE","WIDEVINE_DOWNLOAD",'
                         '"INBAND_TTML","HLS","AES","INBAND_WEBVTT"],'
                         '"category":"%s",'
                         '"tiers":["FREE"]}'
        })
    return result['data']['titles']


cached_programs = {}
CACHE_TIME = 600


def get_playlist_url_from_episode_page(page_url):
    """Obtain the url to the episode's playlist from the episode's HTML page.
    """
    import re

    logger.info("Get playlist from episode page - url=%s", page_url)
    html_doc = fetch.get_document(page_url)
    logger.debug("successfully retrieved page %s", page_url)

    # New version - might a bit overdone as just a regex to obtain the playlist url should suffice.
    # doc_data = parse.get__next__data_from_page(html_doc)
    # player_data = doc_data['props']['pageProps']['episodeHeroWrapperProps']['playerProps']
    # name = player_data['programmeTitle']
    # play_list_url = player_data['playlistUrl']

    # Only this will fail on itvX, but is the name actually used anywhere?
    # name = re.compile('data-video-title="(.+?)"').search(html_doc)[1]
    name = ''
    play_list_url = re.compile('data-video-id="(.+?)"').search(html_doc)[1]
    return play_list_url, name



def search(search_term):
    url = 'https://textsearch.prd.oasvc.itv.com/search'
    query_params = {
        'broadcaster': 'itv',
        'featureSet': 'clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay,bbts,progressive,hd,rtmpe',
        # We can handle only free items because of the way we list production right now.
        'onlyFree': 'true',
        'platform': 'dotcom',
        'query': search_term
    }
    data = fetch.get_json(url, params=query_params)
    if data is None:
        return

    results = data.get('results')

    def parse_programme(prg_data):
        prog_name = prg_data['programmeTitle']
        img_url = prg_data['latestAvailableEpisode']['imageHref']

        return {
            'entity_type': 'programme',
            'label': prog_name,
            'art': {'thumb': img_url.format(width=960, height=540, quality=80, blur=0, bg='false')},
            'info': {'plot': prg_data.get('synopsis'),
                     'title': '[B]{}[/B] - {} episodes'.format(prog_name, prg_data.get('totalAvailableEpisodes', ''))},
            'params': {
                'url': 'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?programmeId={}&'
                       'features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,'
                       'widevine&broadcaster=itv'.format(prg_data['legacyId']['apiEncoded']),
                'name': prog_name}
        }

    def parse_special(prg_data):
        # AFAICT special is always a production, which might be a production of a programme, but
        # presented as a single episode in the search results.
        prog_name = program_data['specialTitle']
        img_url = program_data['imageHref']
        # convert productionId to a format used in the url
        api_prod_id = prg_data['productionId'].replace('/', '_').replace('#', '.')

        return {
            'entity_type': 'special',
            'label': prog_name,
            'art': {'thumb': img_url.format(width=960, height=540, quality=80, blur=0, bg='false')},
            'info': {'plot': prg_data.get('synopsis'),
                     'title': prog_name},
            'params': {'url': 'https://magni.itv.com/playlist/itvonline/ITV/' + api_prod_id,
                       'name': prog_name}
        }

    for result in results:
        program_data = result['data']
        entity_type = result['entityType']

        if entity_type == 'programme':
            yield parse_programme(program_data)
        elif entity_type == 'special':
            yield parse_special(program_data)
        else:
            logger.warning("Unknown search result item entityType %s on search term %s", entity_type, search_term)
            continue
