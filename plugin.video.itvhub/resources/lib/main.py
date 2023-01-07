# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

import logging
import typing

import xbmcplugin

from codequick import Route, Resolver, Listitem, Script, run
from codequick.support import logger_id, build_path

from resources.lib import itv, itv_account, itvx
from resources.lib import utils
from resources.lib import parsex
from resources.lib import fetch
from resources.lib import kodi_utils
from resources.lib import cache
from resources.lib.errors import *


logger = logging.getLogger(logger_id + '.main')
logger.critical('-------------------------------------')


TXT_SEARCH = 30807
TXT_NO_ITEMS_FOUND = 30608
TXT_PLAY_FROM_START = 30620
TXT_PREMIUM_CONTENT = 30622


def empty_folder():
    kodi_utils.msg_dlg(Script.localize(TXT_NO_ITEMS_FOUND))
    # Script.notify('ITV hub', Script.localize(TXT_NO_ITEMS_FOUND), icon=Script.NOTIFY_INFO, display_time=6000)
    return False


def dynamic_listing(func=None):
    """Decorator that adds some default behaviour to callback functions that provide
    a listing of items where the content depends on parameters passes to the function.

    Typically, these callbacks are not guaranteed to return items - a directory may be empty, or
    a search may not return anything.
    Also, when the directory has been added to favourites and has been opened from there, the
    'directory up' ('..') entry in the list will cause the callback to be invoked without any arguments.

    This decorator provides default behaviour for these cases.

    """
    def wrapper(*args, **kwargs):
        # Codequick will always pass a Router object as 1st positional argument and all other parameters
        # as keyword arguments, but others, like tests, may use position arguments.
        if not kwargs and len(args) < 2:
            logger.debug("Function called without kwargs; return False ")
            # Just return false, which results in Kodi returning to the main menu.
            return False
        else:
            args[0].register_delayed(cache.clean)
            logger.debug("wrapper diverts route to: %s", func.__name__)
            result = func(*args, **kwargs)
            if isinstance(result, typing.Generator):
                result = list(result)
            if result:
                return result
            else:
                # Anything that evaluates to False is 'no items found'.
                return empty_folder()
    if func is None:
        return wrapper()
    else:
        wrapper.__name__ = 'wrapper.' + func.__name__
        return wrapper


@Route.register
def root(_):
    yield Listitem.from_dict(sub_menu_live, 'Live', params={'_cache_to_disc_': False})
    # yield Listitem.from_dict(sub_menu_shows, 'Shows')
    callb_map = {
        'collection': list_collection_content,
        'series': list_productions,
        'simulcastspot': play_stream_live
    }
    for item in itvx.main_page_items():
        callback = callb_map.get(item['type'], play_title)
        yield Listitem.from_dict(callback, **item['show'])
    yield Listitem.from_dict(list_collections, 'Collections')
    yield Listitem.from_dict(list_categories, 'Categories')
    yield Listitem.search(do_search, Script.localize(TXT_SEARCH))


# In order to ensure that epg data is refreshed when a live stream is stopped, kodi is
# directed not to return to it's cached listing, but call the addon to supply the list.
# To prevent rather long waiting times when a user kind of quickly zaps between channels, the
# listing is cached for a period short enough to not totally invalidate EPG data.

@Route.register(cache_ttl=4, content_type='videos')
def sub_menu_live(_):
    tv_schedule = itvx.get_live_channels()

    for item in tv_schedule:
        chan_name = item['name']
        now_on = item['slot'][0]
        programs = ('{} - {}'.format(program['startTime'],
                                     program.get('programme_details') or program['programmeTitle'])
                    for program in item['slot'])
        label = '{}    [COLOR orange]{}[/COLOR]'.format(chan_name, now_on['programmeTitle'])
        program_start_time = now_on['orig_start']
        callback_kwargs = {
                'channel': chan_name,
                'url': item['streamUrl'],
                'title': now_on['programmeTitle'],
                'start_time': program_start_time
                }

        # noinspection SpellCheckingInspection
        li = Listitem.from_dict(
            play_stream_live,
            label=label,
            art={
                'fanart': item['backdrop'],
                'thumb': item['images']['logo']},
            info={
                'title': label,
                'plot': '\n'.join(programs),
                },
            params=callback_kwargs,
            properties={
                # This causes Kodi not to offer the standard resume dialog
                'resumetime': '0',
                'totaltime': 3600
            }
        )

        # add 'play from the start' context menu item for channels that support this feature
        if program_start_time:
            cmd = 'PlayMedia({}, noresume)'.format(
                build_path(play_stream_live, play_from_start=True, **callback_kwargs))
            li.context.append((Script.localize(TXT_PLAY_FROM_START), cmd))
        yield li


@Route.register(content_type='videos')
def list_collections(_):
    slider_data = itvx.get_page_data('https://www.itv.com', cache_time=3600)['editorialSliders']
    return [Listitem.from_dict(list_collection_content, **parsex.parse_slider(*slider)['show'])
            for slider in slider_data.items()]


@Route.register(cache_ttl=-1, content_type='videos')
@dynamic_listing
def list_collection_content(addon, url=None, slider=None):
    shows_list = itvx.collection_content(url, slider, addon.setting.get_boolean('hide_paid'))
    return [
        Listitem.from_dict(play_title, **show['show'])
        if show['playable'] else
        Listitem.from_dict(list_productions, **show['show'])
        for show in shows_list
    ]


@Route.register(content_type='videos')  # 24 * 60)
def list_categories(_):
    logger.debug("List categories.")
    categories = itvx.categories()
    items = [Listitem.from_dict(list_category, **cat) for cat in categories]
    return items


@Route.register(content_type='videos')
@dynamic_listing
def list_category(addon, path, filter_char=None):
    addon.add_sort_methods(xbmcplugin.SORT_METHOD_UNSORTED,
                           xbmcplugin.SORT_METHOD_TITLE,
                           xbmcplugin.SORT_METHOD_DATE,
                           xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE,
                           disable_autosort=True)
    if path.endswith('/films'):
        addon.content_type = 'movies'

    shows_list = itvx.category_content(path, addon.setting.get_boolean('hide_paid'))
    return [
        Listitem.from_dict(play_title, **show['show'])
        if show['playable'] else
        Listitem.from_dict(list_productions, **show['show'])
        for show in shows_list
    ]



@Route.register(content_type='videos')
@dynamic_listing
def list_productions(plugin, url, series_idx=None):

    logger.info("Getting productions for series '%s' of '%s'", series_idx, url)

    plugin.add_sort_methods(xbmcplugin.SORT_METHOD_UNSORTED,
                            xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE,
                            xbmcplugin.SORT_METHOD_DATE,
                            disable_autosort=True)

    series_map = itvx.episodes(url, use_cache=True)
    if not series_map:
        return

    if len(series_map) == 1:
        # List the episodes if there is only 1 series
        opened_series = list(series_map.values())[0]
    else:
        opened_series = series_map.get(series_idx, None)

    if opened_series:
        # list episodes of a series
        episodes = opened_series['episodes']
        for episode in episodes:
            li = Listitem.from_dict(play_stream_catchup, **episode)
            date = episode['info'].get('date')
            if date:
                li.info.date(date, '%Y-%m-%dT%H:%M:%SZ')
            yield li
    else:
        # List folders of all series
        for series in series_map.values():
            li = Listitem.from_dict(list_productions, **series['series'])
            yield li


@Route.register(content_type='videos')
@dynamic_listing
def do_search(addon, search_query):
    search_results = itvx.search(search_term=search_query, hide_paid=addon.setting.get_boolean('hide_paid'))
    if not search_results:
        return

    items = [
        Listitem.from_dict(play_title, **result['show'])
        if result['playable']
        else Listitem.from_dict(list_productions, **result['show'])
        for result in search_results if result is not None
    ]
    return items


def create_dash_stream_item(name, manifest_url, key_service_url, resume_time=None):
    # noinspection PyImport,PyUnresolvedReferences
    import inputstreamhelper
    from resources.lib.itv_account import itv_session

    logger.debug('dash manifest url: %s', manifest_url)
    logger.debug('dash key service url: %s', key_service_url)

    try:
        # Usually the first request to the manifest is being redirected several times, but at the first
        # response a hdntl cookie is set that is required for all subsequent requests to media data.
        # Since we loose that cookie using the proxy, we make a single request to obtain the cookie
        # before handling it over to inputstream helper.
        resp = itv_account.fetch_authenticated(fetch.web_request, manifest_url, method='GET', allow_redirects=False)
        hdntl_cookie = resp.cookies.get('hdntl', '')
    except FetchError as err:
        logger.error('Error retrieving dash manifest - url: %r' % err)
        Script.notify('ITV', str(err), Script.NOTIFY_ERROR)
        return False

    PROTOCOL = 'mpd'
    DRM = 'com.widevine.alpha'

    is_helper = inputstreamhelper.Helper(PROTOCOL, drm=DRM)
    if not is_helper.check_inputstream():
        return False

    play_item = Listitem()
    play_item.label = name
    play_item.set_path(manifest_url, is_playable=True)

    play_item.listitem.setContentLookup(False)
    play_item.listitem.setMimeType('application/dash+xml')

    play_item.property['inputstream'] = is_helper.inputstream_addon
    play_item.property['inputstream.adaptive.manifest_type'] = PROTOCOL
    play_item.property['inputstream.adaptive.license_type'] = DRM
    # Ensure to clear the Content-Type header to force curl to make the right request.
    play_item.property['inputstream.adaptive.license_key'] = ''.join((
            key_service_url,
            '|User-Agent=',
            fetch.USER_AGENT,
            '&Content-Type=&Origin=https://www.itv.com&Referer=https://www.itv.com/&|R{SSM}|'))

    cookiestr = ''.join(('Itv.Session: ', itv_session().cookie['Itv.Session'], '; hdntl=', hdntl_cookie))
    play_item.property['inputstream.adaptive.stream_headers'] = ''.join((
            'User-Agent=',
            fetch.USER_AGENT,
            '&Referer=https://www.itv.com/&'
            'Origin=https://www.itv.com&'
            'Sec-Fetch-Dest=empty&'
            'Sec-Fetch-Mode=cors&'
            
            'Sec-Fetch-Site=same-site&'
            'Cookie=',
            cookiestr))

    if resume_time:
        play_item.property['ResumeTime'] = resume_time
        play_item.property['TotalTime'] = '1'

    return play_item


@Resolver.register
def play_stream_live(addon, channel, url, title=None, start_time=None, play_from_start=False):
    logger.info('play live stream - channel=%s, url=%s', channel, url)

    if addon.setting['live_play_from_start'] != 'true' and not play_from_start:
        start_time = None

    try:
        manifest_url, key_service_url, subtitle_url = itv.get_live_urls(channel,
                                                                        url,
                                                                        title,
                                                                        start_time,
                                                                        play_from_start)
    except FetchError as err:
        logger.error('Error retrieving live stream urls: %r' % err)
        Script.notify('ITV', str(err), Script.NOTIFY_ERROR)
        return False
    except Exception as e:
        logger.error('Error retrieving live stream urls: %r' % e)
        return

    list_item = create_dash_stream_item(channel, manifest_url, key_service_url)  # , resume_time='43200')
    if list_item:
        # list_item.property['inputstream.adaptive.manifest_update_parameter'] = 'full'
        if start_time and start_time in manifest_url:
            # cut the first few seconds of video without audio
            list_item.property['ResumeTime'] = '8'
            list_item.property['inputstream.adaptive.play_timeshift_buffer'] = 'true'
            logger.debug("play live stream - timeshift_buffer enabled")
        else:
            # compensate for the 20 sec back used to get the time shift stream of a live channel
            list_item.property['ResumeTime'] = '20'
        list_item.property['TotalTime'] = '1'
    return list_item


@Resolver.register
def play_stream_catchup(_, url, name):

    logger.info('play catchup stream - %s  url=%s', name, url)
    try:
        manifest_url, key_service_url, subtitle_url = itv.get_catchup_urls(url)
        logger.debug('dash subtitles url: %s', subtitle_url)
    except AccessRestrictedError:
        logger.info('Stream only available with premium account')
        kodi_utils.msg_dlg(Script.localize(TXT_PREMIUM_CONTENT))
        return False
    except FetchError as err:
        logger.error('Error retrieving episode stream urls: %r' % err)
        Script.notify(utils.addon_info.name, str(err), Script.NOTIFY_ERROR)
        return False
    except Exception:
        logger.error('Error retrieving catchup stream urls:', exc_info=True)
        return False

    list_item = create_dash_stream_item(name, manifest_url, key_service_url)
    if list_item:
        list_item.subtitles = itv.get_vtt_subtitles(subtitle_url)
    return list_item


@Resolver.register
def play_title(plugin, url, name=''):
    """Play an episode from an url to the episode's html page.

    While episodes obtained from list_productions() have direct urls to stream's
    playlist, episodes from listings obtained by parsing html pages have an url
    to the respective episode's details html page.

    """
    try:
        url = itvx.get_playlist_url_from_episode_page(url)
    except AccessRestrictedError:
        kodi_utils.msg_dlg(Script.localize(TXT_PREMIUM_CONTENT))
        return False
    return play_stream_catchup(plugin, url, name)
