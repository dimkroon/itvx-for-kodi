
import logging
import os


import xbmcplugin

from codequick import Route, Resolver, Listitem, Script, run
from codequick.utils import urljoin_partial as urljoin
from codequick.support import logger_id

from resources.lib import itv, itv_account
from resources.lib import utils
from resources.lib import parse
from resources.lib import fetch
from resources.lib.errors import *


logger = logging.getLogger(logger_id + '.main')
logger.critical('-------------------------------------')


build_url = urljoin('https://www.itv.com/hub/')


@Route.register
def root(_):
    yield Listitem.from_dict(sub_menu_live, 'Live', params={'_cache_to_disc_': False})
    yield Listitem.from_dict(
            list_programs,
            'Shows',
            params={'url': 'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?broadcaster=itv&'
                           'features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,widevine,'
                           'fairplay&sortBy=title'})
    yield Listitem.from_dict(
            sub_menu_from_page,
            'Full series',
            params={'url': 'https://www.itv.com/hub/full-series', 'callback': sub_menu_full_series})
    yield Listitem.from_dict(list_categories, 'categories')


# In order to ensure that epg data is refreshed when a live stream is stopped, kodi is
# directed not to return to it's cached listing, but call the addon to supply the list.
# To prevent rather long waiting times when a user kind of quickly zaps between channels, the
# listing is cached for a period short enough to not totally invalidate EPG data.

@Route.register(cache_ttl=4)
def sub_menu_live(_):
    tv_schedule = itv.get_live_schedule()
    addon_path = utils.addon_info['path']

    for item in tv_schedule:
        channel_info = item['channel']
        chan_name = channel_info['name']
        now_on = item['slot'][0]['programmeTitle']
        programs = ('{} - {}'.format(program['startTime'], program['programmeTitle']) for program in item['slot'])
        thumbfile = os.path.join(addon_path, 'resources/media/{}-colour.png'.format(chan_name.lower()))
        label = '{}    [COLOR orange]{}[/COLOR]'.format(chan_name, now_on)
        li = Listitem.from_dict(
            play_stream_live,
            label=label,
            art={
                'fanart': channel_info['_links']['backgroundImage']['href'].format(
                        width=1280, height=720, quality=80, blur=0, bg='false'),
                'thumb': thumbfile},
            info={
                'title': label,
                'plot': '\n'.join(programs)},
            params={
                'channel': chan_name,
                'url': channel_info['_links']['playlist']['href']
            }
        )
        yield li


@Route.register(cache_ttl=24 * 60)
def list_categories(_):
    logger.debug("List categories.")
    categories = itv.categories()
    items = list(Listitem.from_dict(list_programs, **cat) for cat in categories)
    return items


@Route.register(cache_ttl=60)
def list_programs(_, url):
    logger.debug("list programs for url '%s'", url)
    shows_list = itv.programmes(url)
    for show in shows_list:
        if show['episodes'] > 1:
            yield Listitem.from_dict(list_productions, **show['show'])
        else:
            yield Listitem.from_dict(play_stream_catchup, **show['show'])


@Route.register(cache_ttl=60)
def list_productions(plugin, url, name='', series_idx=0):

    logger.info('Getting productions for series %s of %s', series_idx, url)
    plugin.add_sort_methods(xbmcplugin.SORT_METHOD_UNSORTED,
                            xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE,
                            xbmcplugin.SORT_METHOD_DATE,
                            disable_autosort=True)

    series_list = itv.productions(url, name)

    # First create folders for series
    for i in range(len(series_list)):
        # skip the folder of the series that is opened
        if i == series_idx:
            continue

        series = series_list[i]
        episode_list = series['episodes']
        label = '[B]{}[/B]  -  {} episodes'.format(series['name'], len(episode_list))
        # TODO: Maybe better not to provide plot and art of the first episode. It is only of
        #       of use when the series is one continuous story, which is only rarely the case.
        li = Listitem.from_dict(
            list_productions,
            label=label,
            art=episode_list[0]['art'],
            info={'title': label,
                  'plot': episode_list[0]['info']['plot'],
                  },
            params={'url': url, 'name': name, 'series_idx': i}
        )
        yield li

    # Now create episode items for the opened series folder
    episodes = series_list[series_idx]['episodes']
    for episode in episodes:
        li = Listitem.from_dict(play_stream_catchup, **episode)
        date = episode['info'].get('date')
        if date:
            li.info.date(date, '%Y-%m-%dT%H:%MZ')
        yield li


@Route.register(cache_ttl=120, autosort=False)
def sub_menu_episodes(plugin, url, show_name='', series_idx=0):
    """Show the list of episodes for the specified series and show folders for
    all other series, if present.

    """
    logger.info('Getting episodes for series %s of %s', series_idx, url)
    plugin.add_sort_methods(xbmcplugin.SORT_METHOD_UNSORTED,
                            xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE,
                            xbmcplugin.SORT_METHOD_DATE,
                            disable_autosort=True)

    series_list = itv.get_episodes(build_url(url), show_name)

    # First create folders for series
    for i in range(len(series_list)):
        if i == series_idx:
            continue

        series = series_list[i]
        episode_list = series['episodes']
        label = '[B]{}[/B]  -  {} episodes'.format(series['name'], len(episode_list))
        # TODO: Maybe better not to provide plot and art of the first episode. It is only of
        #       of use when the series is one continuous story, which is only rarely the case.
        li = Listitem.from_dict(
            sub_menu_episodes,
            label=label,
            art=episode_list[0]['art'],
            info={'title': label, 'plot': episode_list[0]['info']['plot']},
            params={'url': url, 'show_name': show_name, 'series_idx': i}
        )
        yield li

    # Now create episode items for the opened series
    episodes = series_list[series_idx]['episodes']
    for episode in episodes:
        li = Listitem.from_dict(play_episode, **episode)
        date = episode['info'].get('date')
        if date:
            li.info.date(date, '%Y-%m-%dT%H:%MZ')
        yield li


@Route.register(cache_ttl=480, autosort=False)
def sub_menu_from_page(_, url, callback):
    """Return the submenu items present a page. Like the categories from page categories"""
    logger.info('sub_menu_from_page for url %s, handler = %s', url, callback)
    submenu_items = parse.parse_submenu(fetch.get_document(url))
    for item in submenu_items:
        yield Listitem.from_dict(callback, **item)


@Route.register(cache_ttl=480)
def sub_menu_full_series(_, url):
    """Return a listing of programmes from a full series' category"""
    url = build_url(url)
    logger.info('sub_menu_full_series for url %s', url)
    submenu_items = parse.parse_full_series(fetch.get_document(url))
    for item in submenu_items:
        yield Listitem.from_dict(sub_menu_episodes, **item)


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
        return

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

    cookiestr = itv_session().cookie + '; hdntl=' + hdntl_cookie
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
def play_stream_live(_, channel, url):
    logger.info('play live stream - channel=%s, url=%s', channel, url)
    try:
        manifest_url, key_service_url, subtitle_url = itv.get_live_urls(channel, url)
    except FetchError as err:
        logger.error('Error retrieving live stream urls: %r' % err)
        Script.notify('ITV', str(err), Script.NOTIFY_ERROR)
        return False
    except Exception as e:
        logger.error('Error retrieving live stream urls: %r' % e)
        return

    list_item = create_dash_stream_item(channel, manifest_url, key_service_url, resume_time='43200')
    if list_item:
        list_item.property['inputstream.adaptive.manifest_update_parameter'] = 'full'
    return list_item


@Resolver.register
def play_stream_catchup(_, url, name):

    logger.info('play catchup stream -%s  url=%s', name, url)
    try:
        manifest_url, key_service_url, subtitle_url = itv.get_catchup_urls(url)
        logger.debug('dash subtitles url: %s', subtitle_url)
    except FetchError as err:
        logger.error('Error retrieving episode stream urls: %r' % err)
        Script.notify('ITV', str(err), Script.NOTIFY_ERROR)
        return False
    except Exception as e:
        logger.error('Error retrieving episode stream urls: %r' % e)
        return False

    list_item = create_dash_stream_item(name, manifest_url, key_service_url)
    if list_item:
        list_item.subtitles = itv.get_vtt_subtitles(subtitle_url)
    return list_item


@Resolver.register
def play_episode(plugin, url, name=None):
    """PLay an episode from an url to the episode's html page.

    While episodes obtain from list_productions() have urls to stream info,
    episodes from listings obtained by parsing html pages have url to the
    respective episode's details html page.

    """
    url, title = itv.get_playlist_url_from_episode_page(url)
    if name is None:
        name = title
    return play_stream_catchup(plugin, url, name)
