#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
#

import os
import string
import time
import logging

from datetime import datetime, timedelta
import pytz

from codequick import Script
from codequick.support import logger_id

from . import utils
from . import fetch
from . import parse
from . import kodi_utils

from .errors import AuthenticationError

logger = logging.getLogger(logger_id + '.itv')

FEATURE_SET = 'hd,progressive,single-track,mpeg-dash,widevine,widevine-download,inband-ttml,hls,aes,inband-webvtt,outband-webvtt,inband-audio-description'
PLATFORM_TAG = 'mobile'


def get_live_schedule(hours=4):
    """Get the full schedule of the itv's main live channels from now up to the specified number of hours.

    """
    # Calculate current british time and the difference between that and local time
    btz = pytz.timezone('Europe/London')
    british_now = datetime.now(btz)
    local_offset = datetime.now() - datetime.utcnow()
    time_dif = local_offset - british_now.utcoffset()
    # in the above calculation we lose a few nanoseconds, so we need to convert the difference to round seconds again
    time_dif = timedelta(time_dif.days, time_dif.seconds + 1)

    # Request TV schedules for the specified number of hours from now, in british time
    from_date = british_now.strftime('%Y%m%d%H%M')
    to_date = (british_now + timedelta(hours=hours)).strftime('%Y%m%d%H%M')
    # Note: platformTag=ctv is exactly what a webbrowser sends
    data = fetch.get_json(
        'https://scheduled.oasvc.itv.com/scheduled/itvonline/schedules',
        params={
            'from': from_date,
            'to': to_date,
            'platformTag': PLATFORM_TAG,
            'featureSet': FEATURE_SET})

    schedules_list = data.get('_embedded', {}).get('schedule', [])
    schedule = [element['_embedded'] for element in schedules_list]

    # convert British start time to local time
    for channel in schedule:
        for program in channel['slot']:
            time_str = program['startTime'][:16]
            # datetime.datetime.strptime has a bug in python3 used in kodi 19: https://bugs.python.org/issue27400
            brit_time = datetime(*(time.strptime(time_str, '%Y-%m-%dT%H:%M')[0:6]))
            loc_time = brit_time + time_dif
            program['startTime'] = loc_time.strftime('%H:%M')
            program['orig_start'] = program['onAirTimeUTC'][:19]

    return schedule


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


stream_req_data = {
    'client': {
        'id': 'browser',
        'supportsAdPods': False,
        'version': '4.1'
    },
    'device': {
        'manufacturer': 'Firefox',
        'model': '105',
        'os': {
            'name': 'Linux',
            'type': 'desktop',
            'version': 'x86_64'
        }
    },
    'user': {
        'entitlements': [],
        'itvUserId': '',
        'token': ''
    },
    'variantAvailability': {
        'featureset': {
            'max': ['HD', 'mpeg-dash', 'widevine', 'outband-webvtt'],
            'min': ['HD', 'mpeg-dash', 'widevine', 'outband-webvtt']
        },
        'platformTag': PLATFORM_TAG
    }
}


def _request_stream_data(url, stream_type='live', retry_on_error=True):
    from .itv_account import itv_session
    session = itv_session()

    try:
        stream_req_data['user']['token'] = session.access_token
        stream_req_data['client']['supportsAdPods'] = stream_type != 'live'

        if stream_type == 'live':
            accept_type = 'application/vnd.itv.online.playlist.sim.v3+json'
            # Live MUST have a featureset containing an item without outband-webvtt, or a bad request is returned.
            min_features = ['mpeg-dash', 'widevine']
        else:
            accept_type = 'application/vnd.itv.vod.playlist.v2+json'
            #  ITV appears now to use the min feature for catchup streams, causing subtitles
            #  to go missing if not specfied here. Min and max both specifying webvtt appears to
            # be no problem for catchup streams that don't have subtitles.
            min_features = ['mpeg-dash', 'widevine', 'outband-webvtt']

        stream_req_data['variantAvailability']['featureset']['min'] = min_features

        stream_data = fetch.post_json(
            url, stream_req_data,
            headers={'Accept': accept_type},
            cookies=session.cookie)

        http_status = stream_data.get('StatusCode', 0)
        if http_status == 401:
            raise AuthenticationError

        return stream_data
    except AuthenticationError:
        if retry_on_error:
            if session.refresh():
                return _request_stream_data(url, stream_type, retry_on_error=False)
            else:
                if kodi_utils.show_msg_not_logged_in():
                    from xbmc import executebuiltin
                    executebuiltin('Addon.OpenSettings({})'.format(utils.addon_info['id']))
                return False
        else:
            raise


def get_live_urls(channel, url=None, title=None, start_time=None):
    """Return the urls to the dash stream, key service and subtitles for a particular live channel.

    .. Note::
        Subtitles are usually not available on live streams, but in order to be compatible with
        data returned by get_catchup_urls(...) None is returned

    """
    # import web_pdb; web_pdb.set_trace()

    if url is None:
        url = 'https://simulcast.itv.com/playlist/itvonline/' + channel

    stream_data = _request_stream_data(url)
    video_locations = stream_data['Playlist']['Video']['VideoLocations'][0]
    dash_url = video_locations['Url']
    start_again_url = video_locations.get('StartAgainUrl')

    if start_again_url:
        if start_time and kodi_utils.ask_play_from_start(title):
            dash_url = start_again_url.format(START_TIME=start_time)
            logger.debug('get_live_urls - selected play from start at %s', start_time)
        else:
            # Go 20 sec back to ensure we get the timeshift stream
            start_time = datetime.utcnow() - timedelta(seconds=20)
            dash_url = start_again_url.format(START_TIME=start_time.strftime('%Y-%m-%dT%H:%M:%S'))

    key_service = video_locations['KeyServiceUrl']
    return dash_url, key_service, None


def get_catchup_urls(episode_url):
    """Return the urls to the dash stream, key service and subtitles for a particular catchup episode.
    """
    # import web_pdb; web_pdb.set_trace()
    stream_data = _request_stream_data(episode_url, 'catchup')['Playlist']['Video']
    url_base = stream_data['Base']
    video_locations = stream_data['MediaFiles'][0]
    dash_url = url_base + video_locations['Href']
    key_service = video_locations['KeyServiceUrl']

    # dash_url = dash_url.replace('26%26DisplayHeight%3C%3D576', '26%26DisplayHeight%3C%3D1080')

    try:
        # usually stream_data['Subtitles'] is just None when no subtitles are not available
        subtitles = stream_data['Subtitles'][0]['Href']
    except (TypeError, KeyError, IndexError):
        subtitles = None
    return dash_url, key_service, subtitles


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


def _create_program_item(item_data):
    productions = item_data['_embedded']['productions']
    latest_episode = item_data['_embedded']['latestProduction']

    episode_count = productions['count']
    orig_title = item_data.get('title', '')
    if episode_count > 1:
        title = '[B]{}[/B] - {} episodes'.format(orig_title, episode_count)
    else:
        title = orig_title

    orig_title = orig_title.lower()

    prog_item = {
        'episodes': episode_count,
        'show': {
            'label': title,
            'art': {'thumb': latest_episode['_links']['image']['href'].format(
                width=960, height=540, quality=80, blur=0, bg='false')},
            'info': {
                'plot': item_data['synopses']['epg'],
                'title': title,
                'sorttitle': orig_title[4:] if orig_title.startswith('the ') else orig_title
            },
            'params': {
                'name': item_data.get('title', ''),
                'url': (productions['_links']['doc:productions']['href'] if episode_count > 1
                        else latest_episode['_links']['playlist']['href'])
            }
        }
    }
    if episode_count == 1:
        duration = utils.duration_2_seconds(latest_episode.get('duration'))
        if duration:
            prog_item['info']['duration'] = duration
    return prog_item


cached_programs = {}
CACHE_TIME = 600


def _get_programs(url):
    """Return the cached list of programs if present in the cache and not expired, or
    create a new list from data from itv hub.
    Cache the list in memory for the lifetime of the addon, to a maximum of CACHE_TIME in seconds

    """
    progs = cached_programs.get(url)
    if progs and progs['expires'] < time.monotonic():
        logger.debug("Programs list cache hit")
        return progs['progs_list']
    else:
        logger.debug("Programs list cache miss")
        result = fetch.get_json(
            url,
            headers={'Accept': 'application/vnd.itv.online.discovery.programme.v1+hal+json'})

        prog_data_list = result['_embedded']['programmes']
        progr_list = [_create_program_item(prog) for prog in prog_data_list]
        cached_programs[url] = {'progs_list': progr_list, 'expires': time.monotonic() + CACHE_TIME}
        return progr_list


def programmes(url, filter_char=None):
    """Get a listing of programmes

    A programmes data structure consist of a listing of 'programmes' (i.e. shows, or series)
    Programmes may have one or more productions (i.e. episodes), but only info about
    the latest production is included in the data structure.

    Return a list in a format that contains only relevant info that can easily be used by
    codequick Listitem.from_dict.

    If the programme has only one production the info of that production is returned, so it
    can be passed as a playable item to kodi.

    """
    t_start = time.monotonic()
    progr_list = _get_programs(url)

    if filter_char is None:
        result = progr_list
    elif len(filter_char) == 1:
        # filter on a single character
        filter_char = filter_char.lower()
        result = [prog for prog in progr_list if prog['show']['info']['sorttitle'][0] == filter_char]
    else:
        # like '0-9'. Return anything not a character
        filter_char = string.ascii_lowercase
        result = [prog for prog in progr_list if prog['show']['info']['sorttitle'][0] not in filter_char]

    logger.debug("Created programs list in %s sec.", time.monotonic() - t_start)
    return result


def productions(url, show_name):
    """Get a listing of productions

    A productions data structure consist of a listing of 'productions' (i.e. episodes)
    Programmes may have one or more production (i.e. episodes), but only info about
    the latest production is included in the data structure.

    Return a list containing only relevant info in a format that can easily be
    used by codequick Listitem.from_dict.

    """
    result = fetch.get_json(
        url,
        headers={'Accept': 'application/vnd.itv.online.discovery.production.v1+hal+json'})
    prod_list = result['_embedded']['productions']
    if not prod_list:
        return []

    # create a mapping of series and their episodes. Put all episodes without a series into
    # series[0].
    item_count = result['count']
    series = {}
    for prod in prod_list:
        series_idx = prod.get('series', 0)
        # In some lists of production productions do not have a field 'episode'. Until now only seen in
        # productions list that do not contain multiple series. Like Coronation Street, which just returns
        # a (small) list of recent episodes.
        # In order to create a somewhat sensible title we create an index based on de position in the list.
        # As listings appear to be returned in order from latest to oldest, the index (`item_count`) is in
        # reversed order.
        episode_idx = prod.get('episode')
        episode_title = prod.get('episodeTitle')
        date = prod['broadcastDateTime'].get('original') or prod['broadcastDateTime'].get('commissioning')

        if episode_title:
            title = '{}. {}'.format(episode_idx or item_count, episode_title)
        elif episode_idx:
            title = '{} episode {}'.format(show_name, episode_idx)
        else:
            # TODO: convert to the local date format
            title = '{} - {}'.format(show_name, utils.reformat_date(date, '%Y-%m-%dT%H:%MZ', '%a %d %b %Y %H:%M'))

        episode = {
            'label': title,
            'art': {'thumb': prod['_links']['image']['href'].format(
                width=960, height=540, quality=80, blur=0, bg='false')},
            'info': {
                'plot': prod['synopses']['epg'],
                'title': title,
                'tagline': prod['synopses']['ninety'],
                'duration': utils.duration_2_seconds(prod['duration']['display']),
                'date': date,
                'episode': episode_idx,
                'season': series_idx if series_idx != 0 else None
            },
            'params': {
                'url': prod['_links']['playlist']['href'],
                'name': title
            }
        }
        item_count -= 1
        episode_map = series.setdefault(series_idx, {})
        episode_map[episode_idx or item_count] = episode

    # turn the mappings in a list of series
    series_list = [
        {'name': 'Series {}'.format(k) if k != 0 else 'Other episodes',
         'episodes': [v[item_idx] for item_idx in sorted(v.keys())]}
        for k, v in sorted(series.items(), key=lambda x: x[0])
    ]
    return series_list


def get_episodes(url, show_name):
    t_start = time.time()
    page_episodes = fetch.get_document(url)
    logger.debug('fetched episodes in %f', time.time() - t_start)
    t_start = time.time()
    episodes_data = parse.parse_episodes(page_episodes, show_name)
    logger.debug('parsed episodes in %f', time.time() - t_start)
    return episodes_data


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


def get_vtt_subtitles(subtitles_url):
    show_subtitles = Script.setting['subtitles_show'] == 'true'
    if show_subtitles is False:
        logger.info('Ignored subtitles by entry in settings')
        return None

    if not subtitles_url:
        logger.info('No subtitles available for this stream')
        return None

    # noinspection PyBroadException
    try:
        vtt_doc = fetch.get_document(subtitles_url)

        # vtt_file = os.path.join(utils.addon_info['profile'], 'subtitles.vtt')
        # with open(vtt_file, 'w', encoding='utf8') as f:
        #     f.write(vtt_doc)

        srt_doc = utils.vtt_to_srt(vtt_doc, colourize=Script.setting['subtitles_color'] != 'false')
        srt_file = os.path.join(utils.addon_info['profile'], 'subitles.srt')
        with open(srt_file, 'w', encoding='utf8') as f:
            f.write(srt_doc)

        return (srt_file,)
    except:
        logger.error("Failed to get vtt subtitles from url %s", subtitles_url, exc_info=True)
        return None


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

