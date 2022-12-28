
# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

import itertools
import json
import time
import logging

from codequick.support import logger_id

from . import utils
from .errors import ParseError


logger = logging.getLogger(logger_id + '.parse')

# NOTE: The resolutions below are those specified by Kodi for their respective usage. There is no guarantee that
#       the image returned by itvX is of that exact resolution.
IMG_PROPS_THUMB = {'treatment': 'title', 'aspect_ratio': '16x9', 'class': '04_DesktopCTV_RailTileLandscape',
                   'distributionPartner': '', 'fallback': 'standard', 'width': '960', 'height': '540',
                   'quality': '80', 'blur': 0, 'bg': 'false'}
IMG_PROPS_POSTER = {'treatment': 'title', 'aspect_ratio': '2x3', 'class': '07_RailTilePortrait',
                   'distributionPartner': '', 'fallback': 'standard', 'width': '1000', 'height': '1500',
                    'quality': '80', 'blur': 0, 'bg': 'false'}
IMG_PROPS_FANART = {'treatment': '', 'aspect_ratio': '16x9', 'class': '01_Hero_DesktopCTV',
                   'distributionPartner': '', 'fallback': 'standard', 'width': '1920', 'height': '1080',
                    'quality': '80', 'blur': 0, 'bg': 'false'}


def build_url(programme, programme_id, episode_id=None):
    base_url = ('https://www.itv.com/watch/' + programme.lower()
                .replace(' ', '-')
                .replace('&', 'and')
                .replace('#', '')
                .replace('/', '')
                .replace('?', ''))
    if episode_id:
        return '/'.join((base_url, programme_id, episode_id))
    else:
        return '/'.join((base_url, programme_id))


def premium_plot(plot: str):
    """Add notice of paid or premium content tot the plot."""
    return '\n\n'.join((plot, '[COLOR yellow]X premium[/COLOR]'))


def parse_submenu(page: str, ):
    """Parse the submenu of a page which usually contains categories

    """
    from bs4 import BeautifulSoup, SoupStrainer

    header_filter = SoupStrainer('header')
    soup = BeautifulSoup(page, "html.parser", parse_only=header_filter)
    soup = soup.find('ul', class_=['nav-secondary__items', 'cp_sub-nav__list'])
    submenu = []
    for anchor in soup.find_all('a'):
        submenu_item = {
            # The selected item may have the text '(selected') in a separate <span>
            'label': anchor.get_text(separator='|', strip=True).split('|')[0],
            'params': {'url': anchor['href']}
        }
        submenu.append(submenu_item)
    return submenu


def scrape_json(html_page):
    import re
    result = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html_page, flags=re.DOTALL)
    if result:
        json_str = result[1]
        try:
            data = json.loads(json_str)
            return data['props']['pageProps']
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("__NEXT_DATA__ in HTML page has unexpected format: %r", e)
            raise ParseError('Invalid data received')


def parse_hero_content(hero_data):
    item_type = hero_data['type']
    item = {
        'type': item_type,
        'label': hero_data['title'],
        'art': {'thumb': hero_data['imageTemplate'].format(**IMG_PROPS_THUMB),
                'fanart': hero_data['imageTemplate'].format(**IMG_PROPS_FANART)},
        'info': {'title': '[B]{}[/B]'.format(hero_data['title'])}

    }
    brand_img = item.get('brandImageTemplate')

    if brand_img:
        item['art']['fanart'] = brand_img.format(**IMG_PROPS_FANART)

    if item_type == 'simulcastspot':
        item['params'] = {'channel': hero_data['channel'], 'url': None }
        item['info'].update(plot='[B]Watch Live[/B]\n' + hero_data.get('description', ''))

    elif item_type == 'series':
        item['info'].update(plot='[B]Series {}[/B]\n{}'.format(hero_data.get('series', '?'),
                                                              hero_data.get('description')))
        item['params'] = {'url': build_url(hero_data['title'], hero_data['encodedProgrammeId']['letterA']),
                          'series_idx': hero_data.get('series')}

    elif item_type == 'film':
        item['info'].update(plot='[B]Watch Now[/B]\n' + hero_data.get('description'),
                            duration=utils.duration_2_seconds(hero_data['duration']))
        item['params'] = {'url': build_url(hero_data['title'], hero_data['encodedProgrammeId']['letterA'])}
    return item


def parse_title(title_data, brand_fanart=None):
    # Note: episodeTitle may be None
    title = title_data['episodeTitle'] or title_data['numberedEpisodeTitle']
    img_url = title_data['imageUrl']
    title_obj = {
        'label': title,
        'art': {'thumb': img_url.format(**IMG_PROPS_THUMB),
                'fanart': brand_fanart,
                # 'poster': img_url.format(**IMG_PROPS_POSTER)
                },
        'info': {'title': title_data['numberedEpisodeTitle'],
                 'plot': '\n\n'.join((title_data['synopsis'], title_data['guidance'] or '')),
                 'duration': utils.duration_2_seconds(title_data['duration']),
                 'date': title_data['broadcastDateTime']},
        'params': {'url': title_data['playlistUrl'], 'name': title}
    }
    if title_data['titleType'] == 'EPISODE':
        title_obj['info'].update(episode=title_data['episodeNumber'], season=title_data['seriesNumber'])
    return title_obj


def parse_search_result(search_data):
    entity_type = search_data['entityType']
    result_data = search_data['data']
    api_episode_id = ''
    if 'FREE' in result_data['tier']:
        plot = result_data['synopsis']
    else:
        plot = premium_plot(result_data['synopsis'])

    if entity_type == 'programme':
        prog_name = result_data['programmeTitle']
        title = '[B]{}[/B] - {} episodes'.format(prog_name, result_data.get('totalAvailableEpisodes', ''))
        img_url = result_data['latestAvailableEpisode']['imageHref']
        api_prod_id = result_data['legacyId']['officialFormat']

    elif entity_type == 'special':
        # A single programme without episodes
        title = result_data['specialTitle']
        prog_name = result_data['specialProgramme']['programmeTitle']
        img_url = result_data['imageHref']
        api_episode_id = result_data['legacyId']['officialFormat']
        api_prod_id = result_data['specialProgramme']['legacyId']['officialFormat']

    elif entity_type == 'film':
        prog_name = result_data['filmTitle']
        title = '[B]Film[/B] - ' +  result_data['filmTitle']
        img_url = result_data['imageHref']
        api_prod_id = result_data['legacyId']['officialFormat']

    else:
        logger.warning("Unknown search result item entityType %s", entity_type)
        return None

    return {
        'playable': entity_type != 'programme',
        'show':{
            'label': prog_name,
            'art': {'thumb': img_url.format(**IMG_PROPS_THUMB)},
            'info': {'plot': plot,
                     'title': title},
            'params': {'url': build_url(prog_name, api_prod_id.replace('/', 'a'), api_episode_id.replace('/', 'a'))}
        }
    }
