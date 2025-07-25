
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from codequick.support import logger_id
from codequick import Script

from . import utils
from . import kodi_utils
from .errors import ParseError

TXT_PLAY_FROM_START = 30620
TXT_VIEW_ALL_EPISODES = 30803

logger = logging.getLogger(logger_id + '.parse')

# NOTE: The resolutions below are those specified by Kodi for their respective usage. There is no guarantee that
#       the image returned by itvX is of that exact resolution.
IMG_PROPS_THUMB = {'treatment': 'title', 'aspect_ratio': '16x9', 'class': '04_DesktopCTV_RailTileLandscape',
                   'distributionPartner': '', 'fallback': 'default', 'width': '960', 'height': '540',
                   'quality': '80', 'blur': 0, 'bg': 'false', 'image_format': 'jpg'}
IMG_PROPS_POSTER = {'treatment': 'title', 'aspect_ratio': '2x3', 'class': '07_RailTilePortrait',
                    'distributionPartner': '', 'fallback': 'standard', 'width': '1000', 'height': '1500',
                    'quality': '80', 'blur': 0, 'bg': 'false', 'image_format': 'jpg'}
IMG_PROPS_FANART = {'treatment': '', 'aspect_ratio': '16x9', 'class': '01_Hero_DesktopCTV',
                    'distributionPartner': '', 'fallback': 'standard', 'width': '1920', 'height': '1080',
                    'quality': '80', 'blur': 0, 'bg': 'false', 'image_format': 'jpg'}


url_trans_table = str.maketrans(' ', '-', '#/?:\'')


def build_url(programme, programme_id, episode_id=None):
    progr_slug = (programme.lower()
                           .replace('&', 'and')
                           .replace(' - ', '-')
                           .translate(url_trans_table))
    base_url = ('https://www.itv.com/watch/' + progr_slug)
    if episode_id:
        return '/'.join((base_url, programme_id, episode_id))
    else:
        return '/'.join((base_url, programme_id))


def premium_plot(plot: str):
    """Add a notice of paid or premium content tot the plot."""
    return '\n'.join(('[COLOR yellow]itvX premium[/COLOR]', plot))


def sort_title(title: str):
    """Return a string te be used as sort title of `title`

    The returned sort title is lowercase and stripped of a possible leading 'The'
    """
    l_title = title.lower()
    return l_title[4:] if l_title.startswith('the ') else l_title


def ctx_mnu_all_episodes(programme_id: str, programme_name: str = 'undefined'):
    callback_qs = urlencode({'url': ''.join(('/watch/', programme_name, '/', programme_id))})
    return (utils.addon_info.localise(TXT_VIEW_ALL_EPISODES),
            ''.join(('Container.Update(plugin://',
                     utils.addon_info.id,
                     '/resources/lib/main/wrapper.list_productions?',
                     callback_qs,
                     ')'))
            )


def ctx_mnu_watch_from_start(chan_id, start_time):
    cmd = ''.join((
        'PlayMedia(plugin://', utils.addon_info.id,
        '/resources/lib/main/play_stream_live/?channel=', chan_id,
        '&start_time=', start_time[:19],
        '&play_from_start=True, noresume)'))
    return utils.addon_info.localise(TXT_PLAY_FROM_START), cmd


def scrape_json(html_page):
    # noinspection GrazieInspection
    """Return the json data embedded in a script tag on an html page"""
    result = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html_page, flags=re.DOTALL)
    if result:
        json_str = result[1]
        try:
            data = json.loads(json_str)
            return data['props']['pageProps']
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("__NEXT_DATA__ in HTML page has unexpected format: %r", e)
            raise ParseError('Invalid data received')
    raise ParseError('No data available')


def parse_simulcast_item(sim_dta: dict) -> dict:
    """Parse simulcast items from various sources like hero, search, etc"""

    plain_title = title = sim_dta.get('title') or sim_dta['brandTitle']
    channel = sim_dta.get('channel') or sim_dta['channelName']
    description = sim_dta.get('description') or sim_dta.get('synopsis', '')
    img_link = sim_dta.get('imageTemplate') or sim_dta.get('imageHref')
    start_t = sim_dta.get('startDateTime') or sim_dta.get('startDateAndTime')
    end_t = sim_dta.get('endDateTime') or sim_dta.get('endDateAndTime')
    utc_now = datetime.now(tz=timezone.utc)
    tz_local = kodi_utils.local_timezone()
    tz_utc = timezone.utc
    ctx_mnu = []

    if start_t and end_t:
        try:
            utc_start = utils.strptime(start_t, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=tz_utc)
            utc_end = utils.strptime(end_t, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=tz_utc)
        except ValueError:
            # Simulcast hero items have a start and end as British local time in hh:mm format.
            start_hrs, start_mins = start_t.split(':')
            end_hrs, end_mins = end_t.split(':')
            btz = utils.ZoneInfo('Europe/London')
            # Add today's date. This goes wrong when it's just past midnight and the live item started
            # the day before. Since simulcast items can have a start time in the future as well as in
            # the past, there's no way to determine the real date. However, it's unlikely live hero
            # items will be presented at such a time.

            brit_start = datetime.now(tz=btz).replace(hour=int(start_hrs), minute=int(start_mins))
            brit_end = datetime.now(tz=btz).replace(hour=int(end_hrs), minute=int(end_mins))
            utc_start = brit_start.astimezone(tz_utc)
            utc_end = brit_end.astimezone(tz_utc)
            # Title in the colour used for all hero items.
            title = ''.join(('[COLOR orange]', plain_title, '[/COLOR]'))

        if utc_start < utc_now:
            title = title + '   [B][I][COLOR yellow]on now[/COLOR][/I][/B]'
            ctx_mnu = [ctx_mnu_watch_from_start(channel, utc_start.strftime('%Y-%m-%dT%H:%M:%S'))]

        plot = ''. join(('Live on ', channel, ' ',
                         utc_start.astimezone(tz_local).strftime('%H:%M'),
                         ' - ',
                         utc_end.astimezone(tz_local).strftime('%H:%M'),
                         '\n',
                         description))
    else:
        plot = ''. join(('Live on ', channel, '\n', description))

    return {
        'type': 'simulcastspot',
        'programme_id': None,
        'show': {
            'label': plain_title,
            'art': {'thumb': img_link.format(**IMG_PROPS_THUMB)},
            'info': {'plot': plot,
                     'title': title},
            'params': {'channel': channel},
        },
        'ctx_mnu': ctx_mnu
    }


# noinspection PyTypedDict
def parse_hero_content(hero_data):
    # noinspection PyBroadException
    try:
        item_type = hero_data['contentType']
        title = hero_data['title']

        if item_type in ('collection', 'page'):
            item = parse_item_type_collection(hero_data)
            info = item['show']['info']
            info['title'] = ''.join(('[COLOR orange]', info['title'], '[/COLOR]'))
            return item

        if item_type == 'simulcastspot':
            return parse_simulcast_item(hero_data)

        context_mnu = []

        item = {
            'label': title,
            'art': {'thumb': hero_data['imageTemplate'].format(**IMG_PROPS_THUMB),
                    'fanart': hero_data['imageTemplate'].format(**IMG_PROPS_FANART)},
            'info': {'title': ''.join(('[B][COLOR orange]', title, '[/COLOR][/B]'))}
        }

        brand_img = hero_data.get('brandImageTemplate')
        if brand_img:
            item['art']['fanart'] = brand_img.format(**IMG_PROPS_FANART)

        if item_type == 'fastchannelspot':
            item['params'] = {'channel': hero_data['channel'], 'url': None}
            item['info'].update(plot='[B]Watch Live[/B]\n' + hero_data.get('description', ''))

        elif item_type in ('series', 'brand'):
            series_idx = hero_data.get('series', '')
            item['info'].update(plot=''.join((hero_data.get('ariaLabel', ''), '\n\n', hero_data.get('description'))))
            item['params'] = {'url': build_url(title, hero_data['encodedProgrammeId']['letterA']),
                              'series_idx': str(series_idx)}
            if series_idx:
                context_mnu.append(ctx_mnu_all_episodes(hero_data['encodedProgrammeId']['letterA']))

        elif item_type in ('special', 'film', 'episode'):
            item['info'].update(plot=''.join(('[B]Watch ',
                                              'FILM' if item_type == 'film' else 'NOW',
                                              '[/B]\n',
                                              hero_data.get('description'))),
                                duration=utils.duration_2_seconds(hero_data.get('duration')))
            item['params'] = {'url': build_url(title,
                                               hero_data['encodedProgrammeId']['letterA'],
                                               hero_data.get('encodedEpisodeId', {}).get('letterA')),
                              'name': title}
            if item_type == 'episode':
                context_mnu.append(ctx_mnu_all_episodes(hero_data['encodedProgrammeId']['letterA']))

        else:
            logger.warning("Hero item %s is of unknown type: %s", hero_data['title'], item_type)
            return None
        return {'type': item_type,
                'programme_id': hero_data.get('encodedProgrammeId', {}).get('underscore'),
                'show': item,
                'ctx_mnu': context_mnu}
    except:
        logger.warning("Failed to parse hero item '%s':\n", hero_data.get('title', 'unknown title'), exc_info=True)
        return None


def parse_short_form_slider(slider_data, url=None):
    """Parse a shortFormSlider from the main page or a collection page.

    Returns the link to the collection page associated with the shortFormSlider.

    """
    # noinspection PyBroadException
    try:
        header = slider_data['header']
        link = header.get('linkHref')
        title = header.get('title') or header.get('iconTitle', '')
        if url:
            # A shortFormSlider from a collection page.
            params = {'url': url, 'slider': 'shortFormSlider'}
        elif link:
            # A shortFormSlider from the main page
            params = {'url': 'https://www.itv.com', 'slider': slider_data.get('key')}
        else:
            return None

        return {'type': 'collection',
                'show': {'label': title,
                         'params': params,
                         'info': {'sorttitle': sort_title(title)}
                         }
                }
    except:
        logger.error("Unexpected error parsing shorFormSlider.", exc_info=True)
        return None


def parse_view_all(slider_data):
    """Return listitem data with a behaviour similar to the 'View All' button of a
    slider on the web page.

    """
    header = slider_data['header']
    link = header.get('linkHref')
    if not link:
        return None
    url = 'https://www.itv.com' + link

    if link.startswith('/watch/categories'):
        item_type = 'category'
        params = {'path': url}
    elif link.startswith('/watch/collections'):
        item_type = 'collection'
        params = {'url': url}
    else:
        logger.warning("Unknown linkHref on %s: '%s", slider_data.get('key'), link)
        return None

    return {'type': item_type,
            'show': {'label': header.get('linkText') or 'View All',
                     'params': params,
                     'info': {'sorttitle': sort_title('zzzz')}
                     }
            }


def parse_editorial_slider(url, slider_data):
    """Parse editorialSliders from the main page or from a collection."""
    # noinspection PyBroadException
    try:
        coll_data = slider_data['collection']
        if not coll_data.get('shows'):
            # Has happened. Items without field `shows` have an invalid headingLink
            return None
        page_link = coll_data.get('headingLink')
        base_url = 'https://www.itv.com/watch'
        if page_link:
            # Link to the collection's page if available
            params = {'url': base_url + page_link['href']}
        else:
            # Provide the slider name when the collection contents are the
            # items in the slider on the original page.
            slider_name = slider_data['collection']['sliderName']
            params = {'url': url, 'slider': slider_name}

        return {'type': 'collection',
                'show': {'label': coll_data['headingTitle'],
                         'params': params,
                         'info': {'sorttitle': sort_title(coll_data['headingTitle'])}}}
    except:
        logger.error("Unexpected error parsing editorialSlider from %s", url, exc_info=True)
        return None


def parse_collection_item(show_data, hide_paid=False):
    """Parse a show item from a collection page

    Very much like category content, but just not quite.

    """
    # noinspection PyBroadException
    try:
        content_type = show_data.get('contentType') or show_data['type']
        is_playable = content_type in ('episode', 'film', 'special', 'title', 'fastchannelspot', 'simulcastspot')
        title = show_data['title']
        content_info = show_data.get('contentInfo', '')

        if content_type in ('collection', 'page'):
            return parse_item_type_collection(show_data)
        if content_type == 'simulcastspot':
            return parse_simulcast_item(show_data)

        if show_data.get('isPaid'):
            if hide_paid:
                return None
            plot = premium_plot(show_data['description'])
        else:
            plot = show_data['description']

        img = show_data.get('imageTemplate') or show_data.get('imageUrl', '')
        programme_item = {
            'label': title,
            'art': {'thumb': img.format(**IMG_PROPS_THUMB),
                    'fanart': img.format(**IMG_PROPS_FANART)},
            'info': {'title': title if is_playable else '[B]{}[/B] {}'.format(title, content_info),
                     'plot': plot,
                     'sorttitle': sort_title(title)},
        }

        if content_type == 'fastchannelspot':
            programme_item['params'] = {'channel': show_data['channel'], 'url': None}

        else:
            programme_item['params'] = {'url': build_url(show_data['titleSlug'],
                                        show_data['encodedProgrammeId']['letterA'],
                                        show_data.get('encodedEpisodeId', {}).get('letterA'))}

        if 'FILMS' in show_data.get('categories', ''):
            programme_item['art']['poster'] = show_data['imageTemplate'].format(**IMG_PROPS_POSTER)

        if is_playable:
            programme_item['info']['duration'] = utils.duration_2_seconds(content_info)
        return {'type': content_type,
                'programme_id': show_data.get('encodedProgrammeId', {}).get('underscore'),
                'show': programme_item}
    except Exception as err:
        logger.warning("Failed to parse collection_item: %r\n%s", err, json.dumps(show_data, indent=4))
        return None


# noinspection GrazieInspection
def parse_shortform_item(item_data, time_zone, time_fmt, hide_paid=False):
    """Parse an item from a shortFormSlider.

    ShortFormSliders are found on the main page. Some collection pages used to have
    shortFromSliders, but this field has not been seen on collection for quite some time.
    Items from heroAndLatest and curatedRails in category news also have a shortForm-like
    content and are handled by this parser.

    """
    try:
        content_type = item_data['contentType']

        if content_type == 'shortform':
            # This item is a 'short item', aka 'news clip' or 'sport clip'.
            # hero and curated rails from the news category lack a field 'genre'.
            # Since sportShortFrom is only ever present on the main page, it's safe
            # to assume genry is news.
            url = '/'.join(('https://www.itv.com/watch',
                            item_data.get('genre', 'news'),
                            item_data['titleSlug'],
                            item_data['episodeId']))

        elif content_type == 'episode':
            # The news item is a 'normal' catchup title. Is usually just the latest ITV news,
            # or a full sports programme.
            # Do not use field 'href' as it is known to have non-a-encoded program and episode Id's which doesn't work.
            url = '/'.join(('https://www.itv.com/watch',
                            item_data['titleSlug'],
                            item_data['encodedProgrammeId']['letterA'],
                            item_data.get('encodedEpisodeId', {}).get('letterA', ''))).rstrip('/')
        else:
            logger.info("Disregarding shortform item of type '%s'", content_type)
            return None

        # dateTime field occasionally has milliseconds. Strip these when present.
        item_time = utils.strptime(item_data['dateTime'][:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
        loc_time = item_time.astimezone(time_zone)
        title = item_data.get('episodeTitle')
        plot = '\n'.join((loc_time.strftime(time_fmt), item_data.get('synopsis', title)))

        # Does paid news exists?
        if item_data.get('isPaid'):
            if hide_paid:
                return None
            plot = premium_plot(plot)

        # TODO: consider adding poster image, but it is not always present.
        #       Add date.
        return {
            'type': 'title',
            'show': {
                'label': title,
                'art': {'thumb': item_data['imageUrl'].format(**IMG_PROPS_THUMB)},
                'info': {'plot': plot, 'sorttitle': sort_title(title), 'duration': item_data.get('duration')},
                'params': {'url': url}
            }
        }
    except Exception as err:
        logger.error("Unexpected error parsing a shortForm item: %r\n%s", err, json.dumps(item_data, indent=4))
        return None


def parse_category_item(prog, category_id):
    # At least all items without an encodedEpisodeId are playable.
    # Unfortunately there are items that do have an episodeId, but are in fact single
    # episodes, and thus playable, but there is no reliable way of detecting these,
    # since category items lack a field like `contentType`.
    # The previous method of detecting the presence of 'series' in contentInfo proved
    # to be very unreliable.
    #
    # All items with episodeId are returned as series folder, with the odd change some
    # contain only one item.

    # TODO: Both regular and news category items now have a field contentType

    is_playable = prog.get('encodedEpisodeId') is None
    playtime = utils.duration_2_seconds(prog['contentInfo'])
    title = prog['title']

    if 'FREE' in prog['tier']:
        plot = prog['description']
    else:
        plot = premium_plot(prog['description'])

    programme_item = {
        'label': title,
        'art': {'thumb': prog['imageTemplate'].format(**IMG_PROPS_THUMB),
                'fanart': prog['imageTemplate'].format(**IMG_PROPS_FANART)},
        'info': {'title': title if is_playable
                          else '[B]{}[/B] {}'.format(title, prog['contentInfo'] if not playtime else ''),
                 'plot': plot,
                 'sorttitle': sort_title(title)},
    }

    # Currently the films category has id 'FILM' while in other data the plural 'FILMS' is used.
    # Ensure a future change to 'FILMS' will not break the add-on again.
    if category_id and 'FILM' in category_id:
        programme_item['art']['poster'] = prog['imageTemplate'].format(**IMG_PROPS_POSTER)

    if is_playable:
        programme_item['info']['duration'] = playtime
        programme_item['params'] = {'url': build_url(title, prog['encodedProgrammeId']['letterA'])}
    else:
        # A Workaround for an issue at ITVX where news programmes' programmeId already contain an
        # episodeId and programme and episode IDs are the same. On the website these programmes
        # end up at page saying "Oops something went wrong".
        prog_id = prog['encodedProgrammeId']['letterA']
        episode_id = prog['encodedEpisodeId']['letterA']
        programme_item['params'] = {'url': build_url(title,
                                                     prog_id,
                                                     episode_id if prog_id != episode_id else None)}
    return {'type': 'title' if is_playable else 'series',
            'programme_id': prog['encodedProgrammeId']['underscore'],
            'show': programme_item}


def parse_item_type_collection(item_data):
    """Parse an item of type 'collection' or type 'page' found in heroContent or
    a collection.
    The collection items refer to another collection.

    .. note::
        Only items from heroContent seem to have a field `ctaLabel`.

    """
    url = '/'.join(('https://www.itv.com/watch/collections',
                   item_data.get('titleSlug', ''),
                   item_data.get('collectionId') or item_data['pageId']))
    if item_data['contentType'] == 'page':
        # This querystring is required for page items
        url += '?ind'

    title = item_data['title']
    descr = '\n\n'.join(txt for txt in (item_data.get('ctaLabel', 'Collection'), item_data.get('description')) if txt)
    item = {
        'label': title,
        'art': {'thumb': item_data['imageTemplate'].format(**IMG_PROPS_THUMB),
                'fanart': item_data['imageTemplate'].format(**IMG_PROPS_FANART)},
        'info': {'title': '[B]{}[/B]'.format(title),
                 'plot': descr,
                 'sorttitle': sort_title(title)},
        'params': {'url': url}
    }
    return {'type': 'collection', 'show': item}


def _get_hero_cta_label(hero_cta: dict) -> str:
    """Return the episode title obtained from heroCtaLabel.

    episodeLabel is usually like "S1:E3 - Episode 3, but not always..."
    Can also be an empy string in which case field 'label' is returned.
    """
    try:
        label = hero_cta['episodeLabel'] or hero_cta['label']
        match = re.match(r'S\d{1,2}: ?E\d{1,3} - (.*)', label)
        if match:
            label = match[1]
        return label
    except:
        logger.error("Failed to parse heroCtaLabel '%s'\n", hero_cta, exc_info=True)
        return ''


def parse_episode_title(title_data, brand_fanart=None, prefer_bsl=False):
    """Parse a title from episodes listing"""

    # Note: episodeTitle may be None, so prefer title from heroCtaLabel, but even that
    # may not always have the required fields.

    title = _get_hero_cta_label(title_data['heroCtaLabel']) or title_data.get('episodeTitle') or ''
    img_url = title_data['image']
    plot = '\n\n'.join(t for t in (title_data['longDescription'], title_data.get('guidance')) if t)
    if title_data['premium']:
        plot = premium_plot(plot)

    episode_nr = title_data.get('episode')
    if episode_nr is not None:
        info_title = '{}. {}'.format(episode_nr, title)
    else:
        info_title = title

    series_nr = title_data.get('series')
    if not isinstance(series_nr, int):
        series_nr = None

    if prefer_bsl:
        playlist_url = title_data.get('bslPlaylistUrl') or title_data['playlistUrl']
    else:
        playlist_url = title_data['playlistUrl']

    title_obj = {
        'label': title,
        'art': {'thumb': img_url.format(**IMG_PROPS_THUMB),
                'fanart': brand_fanart,
                # 'poster': img_url.format(**IMG_PROPS_POSTER)
                },
        'info': {'title': info_title,
                 'plot': plot,
                 'duration': utils.iso_duration_2_seconds(title_data['notFormattedDuration']),
                 'date': title_data['dateTime'],
                 'episode': episode_nr,
                 'season': series_nr,
                 'year': title_data.get('productionYear')},
        'params': {'url': playlist_url, 'name': title}
    }

    return title_obj


def parse_search_result(search_data, hide_paid=False):
    entity_type = search_data.get('entityType') or search_data.get('channelType')
    result_data = search_data['data']
    api_episode_id = ''

    if entity_type == 'simulcast':
        return parse_simulcast_item(result_data)

    if 'PAID' in result_data['tier']:
        if hide_paid:
            return None
        plot = premium_plot(result_data['synopsis'])
    else:
        plot = result_data['synopsis']

    if entity_type == 'programme':
        prog_name = result_data['programmeTitle']
        title = '[B]{}[/B] - {} episodes'.format(prog_name, result_data.get('totalAvailableEpisodes', ''))
        img_url = result_data['latestAvailableEpisode']['imageHref']
        api_prod_id = result_data['legacyId']['apiEncoded']

    elif entity_type == 'special':
        # A single programme without episodes
        title = result_data['specialTitle']
        img_url = result_data['imageHref']

        programme = result_data.get('specialProgramme')
        if programme:
            prog_name = programme['programmeTitle']
            api_prod_id = programme['legacyId']['apiEncoded']
            api_episode_id = result_data['legacyId']['officialFormat']
        else:
            prog_name = title
            api_prod_id = result_data['legacyId']['apiEncoded']
            if api_prod_id.count('_') > 1:
                api_prod_id = api_prod_id.rpartition('_')[0]

    elif entity_type == 'film':
        prog_name = result_data['filmTitle']
        title = '[B]Film[/B] - ' + result_data['filmTitle']
        img_url = result_data['imageHref']
        api_prod_id = result_data['legacyId']['apiEncoded']
        if api_prod_id.count('_') > 1:
            api_prod_id = api_prod_id.rpartition('_')[0]

    else:
        logger.warning("Unknown search result item entityType %s", entity_type)
        return None

    return {
        'type': entity_type,
        'programme_id': api_prod_id,
        'show': {
            'label': prog_name,
            'art': {'thumb': img_url.format(**IMG_PROPS_THUMB)},
            'info': {'plot': plot,
                     'title': title},
            'params': {'url': build_url(prog_name, api_prod_id.replace('_', 'a'), api_episode_id.replace('/', 'a'))}
        }
    }


def parse_my_list_item(item, hide_paid=False):
    """Parser for items from My List, Recommended and Because You Watched."""
    # noinspection PyBroadException
    try:
        if 'PAID' in item['tier']:
            if hide_paid:
                return None
            description = premium_plot(item['synopsis'])
        else:
            description = item['synopsis']
        progr_name = item.get('programmeTitle') or item['title']
        progr_id = item['programmeId'].replace('/', '_')
        num_episodes = item['numberOfEpisodes']
        content_info = ' - {} episodes'.format(num_episodes) if num_episodes is not None else ''
        img_link = item.get('itvxImageLink') or item.get('itvxImageUrl')
        is_playable = item['contentType'].lower() != 'programme'

        item_dict = {
            'type': item['contentType'].lower(),
            'programme_id': progr_id,
            'show': {
                'label': progr_name,
                'art': {'thumb': img_link.format(**IMG_PROPS_THUMB),
                        'fanart': img_link.format(**IMG_PROPS_FANART)},
                'info': {'title': progr_name if is_playable else '[B]{}[/B]{}'.format(progr_name, content_info),
                         'plot':  description,
                         'duration': utils.iso_duration_2_seconds(item.get('duration')),
                         'sorttitle': sort_title(progr_name),
                         'date': item.get('dateAdded')},
                'params': {'url': build_url(progr_name, progr_id.replace('/', 'a'))}
            }
        }
        if item['contentType'] == 'FILM':
            item_dict['show']['art']['poster'] = img_link.format(**IMG_PROPS_POSTER)
        return item_dict
    except:
        logger.warning("Unexpected error parsing MyList item:\n", exc_info=True)
        return None


def parse_last_watched_item(item, utc_now):
    progr_name = item.get('programmeTitle', '')
    progr_id = item.get('programmeId', '').replace('/', '_')
    episode_name = item.get('episodeTitle')
    series_nr = item.get('seriesNumber')
    episode_nr = item.get('episodeNumber')
    img_link = item.get('itvxImageLink', '')
    available_td = utils.strptime(item['availabilityEnd'], "%Y-%m-%dT%H:%M:%SZ") - utc_now
    days_available = int(available_td.days + 0.99)

    if days_available > 365:
        availability = '\nAvailable for over a year.'
    elif days_available > 30:
        months = int(days_available//30)
        availability = '\nAvailable for {} month{}.'.format(months, 's' if months > 1 else '')
    elif days_available >= 1:
        availability = '\n[COLOR orange]Only {} day{} available.[/COLOR]'.format(
            days_available, 's' if days_available > 1 else '')
    else:
        hours_available = int(available_td.seconds / 3600)
        availability = '\n[COLOR orange]Only {} hour{} available.[/COLOR]'.format(
            hours_available, 's' if hours_available != 1 else '')

    info = ''.join((
        item['synopsis'] if 'FREE' in item['tier'] else premium_plot(item['synopsis']),
        '\n\n',
        episode_name or '',
        ' - ' if episode_name and series_nr else '',
        'series {} episode {}'.format(series_nr, episode_nr) if series_nr else '',
        availability
    ))

    if item.get('isNextEpisode'):
        title = progr_name + ' - [I]next episode[/I]'
    else:
        title = '{} - [I]{}% watched[/I]'.format(progr_name, int(item['percentageWatched'] * 100))

    item_dict = {
        'type': 'vodstream',
        'programme_id': progr_id,
        'show': {
            'label': episode_name or progr_name,
            'art': {'thumb': img_link.format(**IMG_PROPS_THUMB),
                    'fanart': img_link.format(**IMG_PROPS_FANART)},
            'info': {'title': title,
                     'plot': info,
                     'sorttitle': sort_title(title),
                     'date': utils.reformat_date(item['viewedOn'], "%Y-%m-%dT%H:%M:%SZ", "%d.%m.%Y"),
                     'duration': utils.duration_2_seconds(item['duration']),
                     'season': series_nr,
                     'episode': episode_nr},
            'params': {'url': ('https://magni.itv.com/playlist/itvonline/ITV/' +
                               item['productionId'].replace('/', '_').replace('#', '.')),
                       'name': progr_name,
                       'set_resume_point': True},
            'properties': {
                # This causes Kodi not to offer the standard resume dialog, so we can obtain
                # resume time at the time of resolving the video url and play from there, or show
                # a 'resume from' dialog.
                'resumetime': '0',
                'totaltime': 60
            }
        }
    }
    if item['contentType'] == 'FILM':
        item_dict['show']['art']['poster'] = img_link.format(**IMG_PROPS_POSTER)
    elif item['contentType'] == 'EPISODE' and progr_id:
        item_dict['ctx_mnu'] = [ctx_mnu_all_episodes(progr_id)]
    return item_dict


def parse_schedule_item(data):
    """Parse and item from the html page /watch/guide.

    Used to create EPG data for IPTV manager.
    """
    from urllib.parse import quote

    plugin_id = utils.addon_info.id
    genres = data.get('genres')
    try:
        item = {
            'start': data['start'],
            'stop': data['end'],
            'title': data['title'],
            'description': '\n\n'.join(t for t in (data.get('description'), data.get('guidance')) if t),
            'genre': genres[0].get('name') if genres else None,
        }

        episode_nr = data.get('episodeNumber')
        if episode_nr:
            # It is not uncommon for seriesNumber to be None while episodeNumber does have a value.
            series_nr = data.get('seriesNumber') or 0
            item['episode'] = 'S{:02d}E{:02d}'.format(series_nr, episode_nr)

        episode_link = data.get('episodeLink')
        if episode_link:
            episode_url = '/watch' + episode_link
            item['stream'] = ''.join(('plugin://',
                                      plugin_id,
                                      '/resources/lib/main/play_title/?url=',
                                      quote(episode_url, safe='')))
        return item
    except:
        logger.error("Failed to parse html schedule item", exc_info=True)
        return None
