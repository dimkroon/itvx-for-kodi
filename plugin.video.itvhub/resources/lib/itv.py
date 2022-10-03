from __future__ import unicode_literals

import os
import time
import logging

from datetime import datetime, timedelta

from codequick import Script
from codequick.support import logger_id

from . import utils
from . import fetch
from . import parse

from .errors import AuthenticationError


logger = logging.getLogger(logger_id + '.itv')


def get_live_schedule(hours=4):
    """Get the schedule of the live channels from now up to the specified number of hours.

    """
    import pytz

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
    url = 'https://scheduled.oasvc.itv.com/scheduled/itvonline/schedules?from={}&platformTag=ctv&to={}'.format(
        from_date, to_date
    )
    data = fetch.get_json(url)

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

    return schedule


stream_req_data = {
    'client': {
        'id': 'browser',
        'supportsAdPods': True,
        'version': '4.1'
    },
    'device': {
        'manufacturer': '',
        'model': '',
        'os': {
            'name': '',
            'type': 'desktop',
            'version': ''
        }
    },
    'user': {
        'entitlements': [],
        'itvUserId': '',
        'token': ''
    },
    'variantAvailability': {
        'featureset': {
            'max': ['mpeg-dash', 'widevine', 'outband-webvtt'],
            'min': ['mpeg-dash', 'widevine']
        },
        'platformTag': 'dotcom'
    }
}


def _request_stream_data(url, stream_type='live', retry_on_error=True):
    from .itv_account import itv_session

    stream_req_data['user']['token'] = itv_session().access_token
    stream_req_data['client']['supportsAdPods'] = stream_type != 'live'

    if stream_type == 'live':
        accept_type = 'application/vnd.itv.online.playlist.sim.v3+json'
    else:
        accept_type = 'application/vnd.itv.vod.playlist.v2+json'

    try:
        stream_data = fetch.post_json(
            url, stream_req_data,
            {'Accept': accept_type, 'Cookie': itv_session().cookie})

        http_status = stream_data.get('StatusCode', 0)

        if http_status == 401:
            raise AuthenticationError

        return stream_data
    except AuthenticationError:
        if retry_on_error:
            itv_session().refresh()
            return _request_stream_data(url, stream_type, retry_on_error=False)
        else:
            raise


def get_live_urls(channel, url=None):
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
    try:
        # usually stream_data['Subtitles'] is just None when no subtitles are not available
        subtitles = stream_data['Subtitles'][0]['Href']
    except (TypeError, KeyError, IndexError):
        subtitles = None
    return dash_url, key_service, subtitles


def categories():
    result = fetch.get_json(
            'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/categories?'
            'features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,playready,widevine&broadcaster=itv',
            headers={'Accept': 'application/vnd.itv.online.discovery.category.v1+hal+json'})
    cat_list = result['_embedded']['categories']
    return ({'label': cat['name'], 'params': {'url': cat['_links']['doc:programmes']['href']}} for cat in cat_list)


def programmes(url):
    """Get a listing of programmes

    A programmes data structure consist of a listing of 'programmes' (i.e. shows, or series)
    Programmes may have one or more productions (i.e. episodes), but only info about
    the latest production is included in the data structure.

    Return a list in a format that contains only relevant info that can easily be used by
    codequick Listitem.from_dict.

    If the programme has only one production we return the info of that production, so it
    can be passed as a playable item to kodi.

    """
    result = fetch.get_json(
        url,
        headers={'Accept': 'application/vnd.itv.online.discovery.programme.v1+hal+json'})
    prog_list = result['_embedded']['programmes']
    for prog in prog_list:
        productions = prog['_embedded']['productions']
        latest_episode = prog['_embedded']['latestProduction']

        episode_count = productions['count']
        if episode_count > 1:
            title = '[B]{}[/B] - {} episodes'.format(prog.get('title', ''), episode_count)
        else:
            title = prog.get('title', '')

        prog_item = {
            'episodes': episode_count,
            'show': {
                'label': title,
                'art': {'thumb': latest_episode['_links']['image']['href'].format(
                    width=960, height=540, quality=80, blur=0, bg='false')},
                'info': {
                    'plot': prog['synopses']['epg'],
                    'title': title
                },
                'params': {
                    'name': prog.get('title', ''),
                    'url': (productions['_links']['doc:productions']['href'] if episode_count > 1
                            else latest_episode['_links']['playlist']['href'])
                }
            }
        }
        if episode_count == 1:
            duration = utils.duration_2_seconds(latest_episode.get('duration'))
            if duration:
                prog_item['info']['duration'] = duration
        yield prog_item


def productions(url, show_name):
    """Get a listing of productions

    A productions data structure consist of a listing of 'productions' (i.e. episodes)
    Programmes may have one or more production (i.e. episodes), but only info about
    the latest production is included in the data structure.

    Return a list in a format that contains only relevant info in a format that can easily be
    used by  codequick Listitem.from_dict.

    """
    result = fetch.get_json(
        url,
        headers={'Accept': 'application/vnd.itv.online.discovery.production.v1+hal+json'})
    prod_list = result['_embedded']['productions']

    # create a mapping of series and their episodes. Put all episodes without a series into
    # series[0].
    item_count = result['count']
    series = {}
    for prod in prod_list:
        series_idx = prod.get('series', 0)
        # In some lists of production productions do not have a field 'episode'. Until now only seen in
        # productions list that do not contain multiple series. Like Coronation Street, which just returns
        # a (small) list of recent episodes.
        # In order to create a somewhat sensible title we create an index bases in de position in the list,
        # As listings appear to be returned in order from latest to oldest, we reverse the index.
        episode_idx = prod.get('episode')
        episode_title = prod.get('episodeTitle')
        date = prod['broadcastDateTime'].get('commissioning') or prod['broadcastDateTime'].get('original')

        if episode_title:
            title = '{}. {}'.format(episode_idx or item_count, episode_title)
        elif episode_idx:
            title = '{} episode {}'.format(show_name, episode_idx)
        else:
            title = '{} - {}'.format(show_name, utils.reformat_date(date, '%Y-%m-%dT%H:%MZ', '%a %d %b %H:%M'))

        episode = {
            'label': title,
            'art': {'thumb': prod['_links']['image']['href'].format(
                width=960, height=540, quality=80, blur=0, bg='false')},
            'info': {
                'plot': utils.reformat_date(date, '%Y-%m-%dT%H:%MZ', '%d-%m-%Y %H:%M') + '\n ' + prod['synopses']['epg'],
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

    name = re.compile('data-video-title="(.+?)"').search(html_doc)[1]
    play_list_url = re.compile('data-video-id="(.+?)"').search(html_doc)[1]
    return play_list_url, name


def get_vtt_subtitles(subtitles_url):
    if not subtitles_url or Script.setting['subtitles_show'] != 'true':
        return None

    # noinspection PyBroadException
    try:
        vtt_doc = fetch.get_document(subtitles_url)

        # vtt_file = os.path.join(utils.addon_info['profile'], 'subtitles.vtt')
        # with open(vtt_file, 'w', encoding='utf8') as f:
        #     f.write(vtt_doc)

        srt_doc = utils.vtt_to_srt(vtt_doc)
        srt_file = os.path.join(utils.addon_info['profile'], 'subitles.srt')
        with open(srt_file, 'w', encoding='utf8') as f:
            f.write(srt_doc)

        return (srt_file, )
    except:
        logger.error("Failed to get vtt subtitles from url %s", subtitles_url, exc_info=True)
        return None
