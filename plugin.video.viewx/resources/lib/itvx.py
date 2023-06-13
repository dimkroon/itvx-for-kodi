
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viewx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import time
import logging

from datetime import datetime
import pytz
import requests
import xbmc

from codequick.support import logger_id

from . import fetch, errors
from . import parsex
from . import cache

from .itv import get_live_schedule


logger = logging.getLogger(logger_id + '.itvx')


FEATURE_SET = 'hd,progressive,single-track,mpeg-dash,widevine,widevine-download,inband-ttml,hls,aes,inband-webvtt,outband-webvtt,inband-audio-description'
PLATFORM_TAG = 'mobile'


def get_page_data(url, cache_time=None):
    """Return the json data embedded in a <script> tag on a html page.

    Return the data from cache if present and not expired, or request the page by HTTP.
    """
    if not url.startswith('https://'):
        url = 'https://www.itv.com' + url

    if cache_time:
        cached_data = cache.get_item(url)
        if cached_data:
            return cached_data

    html_doc = fetch.get_document(url)
    data = parsex.scrape_json(html_doc)
    if cache_time:
        cache.set_item(url, data, cache_time)
    return data


def get_now_next_schedule(local_tz=None):
    """Get the name and start time of the current and next programme for each live channel.

    Present start time conform Kodi's time zone setting.
    """
    if local_tz is None:
        local_tz = pytz.timezone('Europe/London')

    utc_tz = pytz.utc
    # Use local time format without seconds. Fix weird kodi formatting for 12-hour clock.
    time_format = xbmc.getRegion('time').replace(':%S', '').replace('%I%I:', '%I:')

    live_data = fetch.get_json(
        'https://nownext.oasvc.itv.com/channels',
        params={
            'broadcaster': 'itv',
            'featureSet': FEATURE_SET,
            'platformTag': PLATFORM_TAG})

    fanart_url = live_data['images']['backdrop']
    channels = live_data['channels']

    for channel in channels:
        channel['backdrop'] = fanart_url
        slots = channel.pop('slots')

        programs_list = []
        for prog in (slots['now'], slots['next']):
            if prog['detailedDisplayTitle']:
                details = ': '.join((prog['displayTitle'], prog['detailedDisplayTitle']))
            else:
                details = prog['displayTitle']

            start_t = prog['start'][:19]
            utc_start = datetime(*(time.strptime(start_t, '%Y-%m-%dT%H:%M:%S')[0:6]), tzinfo=utc_tz)

            programs_list.append({
                'programme_details': details,
                'programmeTitle': prog['displayTitle'],
                'orig_start': None,          # fast channels do not support play from start
                'startTime': utc_start.astimezone(local_tz).strftime(time_format)
            })
        channel['slot'] = programs_list
    return channels


def get_live_channels(local_tz=None):
    """Return a list of all available live channels. Include each channel's scheduled
    programmes in the channel data.

    For the stream-only FAST channels, only the current and next programme are
    available. For the regular channels a schedule from now up to 4 hours in the
    future will be returned.
    Programme start times will be presented in the user's local time zone.

    """
    cached_schedule = cache.get_item('live_schedule')
    if cached_schedule:
        return cached_schedule

    if local_tz is None:
        local_tz = pytz.timezone('Europe/London')

    schedule = get_now_next_schedule(local_tz)
    main_schedule = get_live_schedule(local_tz=local_tz)

    # Replace the schedule of the main channels with the longer one obtained from get_live_schedule().
    for channel in schedule:
        # The itv main live channels get their schedule from the full live schedule.
        if channel['channelType'] == 'simulcast':
            chan_id = channel['id']
            for main_chan in main_schedule:
                # Caution, might get broken when ITV becomes ITV1 everywhere.
                if main_chan['channel']['name'] == chan_id:
                    channel['slot'] = main_chan['slot']
                    break
    cache.set_item('live_schedule', schedule, expire_time=240)
    return schedule


def main_page_items():
    main_data = get_page_data('https://www.itv.com', cache_time=None)
    for hero_data in main_data['heroContent']:
        yield parsex.parse_hero_content(hero_data)
    if 'trendingSliderContent' in main_data.keys():
        yield {'type': 'collection',
               'show': {'label': 'Trending', 'params': {'slider': 'trendingSliderContent'}}}
    if 'newsShortformSliderContent' in main_data.keys():
        yield {'type': 'collection',
               'show': {'label': 'News', 'params': {'slider': 'newsShortformSliderContent'}}}


def collection_content(url=None, slider=None, hide_paid=False):
    if url:
        items_list = get_page_data(url, cache_time=43200)['collection']['shows']
        if hide_paid:
            progr_list = [parsex.parse_collection_item(item)
                          for item in items_list
                          if not item.get('isPaid')]
        else:
            progr_list = [parsex.parse_collection_item(item) for item in items_list]
    else:
        # A Collection that has all it's data on the main page and does not have its own page.
        page_data = get_page_data('https://www.itv.com', cache_time=3600)

        if slider == 'newsShortformSliderContent':
            uk_tz = pytz.timezone('Europe/London')
            time_fmt = ' '.join((xbmc.getRegion('dateshort'), xbmc.getRegion('time')))
            items_list = page_data['newsShortformSliderContent']['items']
            if hide_paid:
                progr_list = [parsex.parse_news_collection_item(news_item, uk_tz, time_fmt)
                              for news_item in items_list
                              if not news_item.get('isPaid')]
            else:
                progr_list = [parsex.parse_news_collection_item(news_item, uk_tz, time_fmt)
                              for news_item in items_list]

        elif slider == 'trendingSliderContent':
            items_list = page_data['trendingSliderContent']['items']
            if hide_paid:
                progr_list = [parsex.parse_trending_collection_item(trending_item)
                              for trending_item in items_list
                              if not trending_item.get('isPaid')]
            else:
                progr_list = [parsex.parse_trending_collection_item(trending_item) for trending_item in items_list]

        else:
            items_list = page_data['editorialSliders'][slider]['collection']['shows']
            if hide_paid:
                progr_list = [parsex.parse_collection_item(item) for item in items_list if not item.get('isPaid')]
            else:
                progr_list = [parsex.parse_collection_item(item) for item in items_list]
    progr_list.sort(key=lambda prog: prog['show']['info']['sorttitle'])
    return progr_list


def episodes(url, use_cache=False):
    """Get a listing of series and their episodes

    Return a list containing only relevant info in a format that can easily be
    used by codequick Listitem.from_dict().

    """
    if use_cache:
        cached_data = cache.get_item(url)
        if cached_data is not None:
            return cached_data

    brand_data = get_page_data(url, cache_time=0)['title']['brand']
    brand_title = brand_data['title']
    brand_thumb = brand_data['imageUrl'].format(**parsex.IMG_PROPS_THUMB)
    brand_fanart = brand_data['imageUrl'].format(**parsex.IMG_PROPS_FANART)
    if 'FREE' in brand_data['tier']:
        brand_description = brand_data['synopses'].get('ninety', '')
    else:
        brand_description = parsex.premium_plot(brand_data['synopses'].get('ninety', ''))
    series_data = brand_data['series']

    if not series_data:
        return {}

    # The field 'seriesNumber' is not guaranteed to be unique - and not guaranteed an integer either.
    # Midsummer murder for instance has 2 series with seriesNumber 4
    # By using this mapping, setdefault() and extend() on the episode list, series with the same
    # seriesNumber are automatically merged.
    series_map = {}
    for series in series_data:
        title = series['title']
        series_idx = series['seriesNumber']
        series_obj = series_map.setdefault(
            series_idx, {
                'series': {
                    'label': title,
                    'art': {'thumb': brand_thumb, 'fanart': brand_fanart},
                    # TODO: add more info, like series number, number of episodes
                    'info': {'title': '[B]{} - {}[/B]'.format(brand_title, series['title']),
                             'plot': '{}\n\n{} - {} episodes'.format(
                                 brand_description, title, series['seriesAvailableEpisodeCount'])},

                    'params': {'url': url, 'series_idx': series_idx}
                },
                'episodes': []
            })
        series_obj['episodes'].extend(
            [parsex.parse_episode_title(episode, brand_fanart) for episode in series['episodes']])
    cache.set_item(url, series_map, expire_time=1800)
    return series_map


def categories():
    """Return all available categorie names."""
    data = get_page_data('https://www.itv.com/watch/categories', cache_time=86400)
    cat_list = data['subnav']['items']
    return ({'label': cat['name'], 'params': {'path': cat['url']}} for cat in cat_list)


def category_content(url: str, hide_paid=False):
    """Return all programmes in a category"""
    cached_data = cache.get_item(url)
    if cached_data and cached_data['hide_paid'] == hide_paid:
        return cached_data['items_list']

    cat_data = get_page_data(url, cache_time=0)
    category = cat_data['category']['pathSegment']
    progr_list = cat_data.get('programmes')

    parse_progr = parsex.parse_category_item

    if hide_paid:
        items = [parse_progr(prog, category) for prog in progr_list if 'FREE' in prog['tier']]
    else:
        items = [parse_progr(prog, category) for prog in progr_list]
    items.sort(key=lambda prog: prog['show']['info']['sorttitle'])
    cache.set_item(url, {'items_list': items, 'hide_paid': hide_paid}, expire_time=3600)
    return items


def get_playlist_url_from_episode_page(page_url):
    """Obtain the url to the episode's playlist from the episode's HTML page.
    """
    import re

    logger.info("Get playlist from episode page - url=%s", page_url)
    html_doc = fetch.get_document(page_url)
    logger.debug("successfully retrieved page %s", page_url)
    match = re.compile('data-video-id="(.+?)"').search(html_doc)
    if match:
        return match[1]
    else:
        # Premium content does not have a 'data-video-id' property in the episode page.
        # TODO: Check if it does when the user has a premium account.
        raise errors.AccessRestrictedError


def search(search_term, hide_paid=False):
    """Make a query on `search_term`

    When no search result are found itvX returns either HTTP status 204, or
    a normal json object with an emtpy list of results.

    """
    from urllib.parse import quote
    # Include the querystring in url. If requests builds the querystring from parameters it will quote the
    # commas in argument `featureset`, and ITV's search appears to have a problem with that and sometimes returns
    # no results.
    url = 'https://textsearch.prd.oasvc.itv.com/search?broadcaster=itv&featureSet=clearkey,outband-webvtt,hls,aes,' \
          'playready,widevine,fairplay,bbts,progressive,hd,rtmpe&onlyFree=false&platform=dotcom&query=' + quote(
        search_term)
    headers = {
        'User-Agent': fetch.USER_AGENT,
        'accept': 'application/json',
        'Origin': 'https://www.itv.com',
        'Referer': 'https://www.itv.com/',
        'accept-language': 'en-GB,en;q=0.5',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }
    resp = requests.get(url, headers=headers, timeout=fetch.WEB_TIMEOUT)

    if resp.status_code != 200:
        logger.debug("Search for '%s' (hide_paid=%s) failed with HTTP status %s",
                     search_term, hide_paid, resp.status_code)
        return None

    try:
        data = resp.json()
    except:
        logger.warning("Search for '%s' (hide_paid=%s) returned non-json content: '%s'",
                       search_term, hide_paid, resp.content)
        return None

    results = data.get('results')
    if not results:
        logger.debug("Search for '%s' returned an empty list of results. (hide_paid=%s)", search_term, hide_paid)
    return (parsex.parse_search_result(result) for result in results)
