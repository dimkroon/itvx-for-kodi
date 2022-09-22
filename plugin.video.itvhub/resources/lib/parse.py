import itertools
import json
import time
import logging

from codequick.support import logger_id

from . import utils
from .errors import ParseError
from .utils import reformat_date


logger = logging.getLogger(logger_id + '.parse')


def parse_shows(page: str):
    """Parse the page 'shows' and return a generator of al items.

    """
    t_start = time.monotonic()

    try:
        page_data = utils.get_json_from_html(page)
        data_list = page_data['props']['pageProps']['showGroups']
        shows_iter = itertools.chain.from_iterable(group['shows'] for group in data_list)
        shows_data = (_show_2_item_dict(show_data) for show_data in shows_iter)
        logger.debug('Parsed all shows in %f seconds', time.monotonic() - t_start)
        return shows_data
    except (json.JSONDecodeError, KeyError, ParseError) as err:
        logger.error('Failed parse page shows: %r', err)
        raise ParseError


def _show_2_item_dict(show_data):
    """Covert a dictionary containing info about a show to a format that is compatible with a codequick ListItem"""
    episode_count = show_data.get('episodeCount', 0)
    if episode_count > 1:
        title = '[B]{}[/B] - {} episodes'.format(show_data.get('title', ''), episode_count)
    else:
        title = show_data.get('title', '')
    show_info = {
        'label': title,
        'art': {'thumb': show_data['imageUrl'].format(width=960, height=540, quality=80, blur=0, bg='false')},
        'info': {'plot': show_data.get('synopsis'), 'title': title},
        'params': {'url': show_data.get('href'), 'show_name': show_data.get('title', '')}
    }
    if episode_count == 1:
        duration = utils.duration_2_seconds(show_data.get('duration'))
        if duration:
            show_info['info']['duration'] = duration

    return {'episodes': episode_count, 'show': show_info}


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


def _parse_item_data(soup, fallback_name=''):
    """Extract info from an anchor item, like url, label, plot, etc.

    """
    episode = {'art': {}, 'info': {}, 'params': {}}
    episode['params']['url'] = soup['href']

    img_link = soup.find('img')['src'].split('?')[0]
    episode['art']['thumb'] = img_link + '?w=960&h=540&q=80&blur=0&bg=false&image_format=jpg'
    title_tag = soup.find(class_='tout__title')
    # sometimes the tag has no text content
    episode['label'] = title_tag.get_text(strip=True) or fallback_name

    summary_tag = soup.find(class_='tout__summary')
    if summary_tag:
        summary = summary_tag.get_text(strip=True)
    else:
        summary = ''

    time_tag = soup.find('time')
    if time_tag is not None:
        date_str = soup.find('time')['datetime']
        episode['info']['date'] = date_str
        summary = reformat_date(date_str, '%Y-%m-%dT%H:%MZ', '%d-%m-%Y %H:%M') + '\n ' + summary
    else:
        episode['info']['date'] = None

    episode['info']['plot'] = summary
    return episode


def parse_episodes(page: str, show_name=''):
    """Parse the page 'episodes' of a particular show.

    To ensure every episode has a title the original name of the show is used if
    the title on the web page is missing or empty.

    Returns a list of series where each series contains a list of episodes.

    """
    t_start = time.monotonic()

    from bs4 import BeautifulSoup, SoupStrainer

    section_filter = SoupStrainer('section')
    soup = BeautifulSoup(page, "html.parser", parse_only=section_filter)

    series_list = []
    for section in soup.find_all('section', class_='module', recursive=False):
        episodes_list = []
        serie = {'episodes': episodes_list}

        serie_header = section.find('h2')
        serie['name'] = serie_header.stripped_string or tuple(serie_header.stripped_strings)[-1]

        # Index used to create unique episode names when the website does not provide one
        idx = 1
        for episode_tag in section.find_all('a'):
            try:
                episode = _parse_item_data(episode_tag, '{}. {}'.format(idx, show_name))
            except TypeError:
                # Occasionally there are sections of class module that do not contain episode data.
                # Just disregard the section and continue
                continue
            episodes_list.append(episode)
            idx += 1

        # Sometimes ITV presents the order from newest to oldest, i.e. episode 1 is last in the list,
        # but is it not quite clear when. Also, sometimes episodes are marked with their number, like
        # '1. The third girl', but on other shows it is just the plain episode's title.
        # There is as such no standard way to order the list. We just keep ITV's order end let
        # Kodi make the best of it.
        if episodes_list:
            series_list.append(serie)

    # ITV seems to present series in order from newest to oldest, i.e. series 1 is last in the list
    series_list.reverse()
    logger.debug('Parsed episodes %s in %f', show_name, time.monotonic() - t_start)
    return series_list


def parse_full_series(page: str):
    """Parse a category page of full series.
    Like www.itv.com/hub/full-series/drama

    """
    t_start = time.monotonic()
    from bs4 import BeautifulSoup, SoupStrainer

    section_filter = SoupStrainer('a', {'data-content-type': 'programme'})
    soup = BeautifulSoup(page, "html.parser", parse_only=section_filter)
    series_list = []
    for anchor_tag in soup.find_all('a', recursive=False):
        series_item = _parse_item_data(anchor_tag)
        series_list.append(series_item)

    logger.debug('Parsed full series in %f', time.monotonic() - t_start)
    return series_list


def _category_item_2_dict(show_data):
    """Covert a dictionary containing info about a show to a format that is compatible with a codequick ListItem

    Unfortunately the structure of data obtained from a categories page differs to that retrieved from shows.

    """
    episode_count = show_data.get('episodeCount', 0)
    if episode_count > 1:
        title = '[B]{}[/B] - {} episodes'.format(show_data.get('title', ''), episode_count)
    else:
        title = show_data.get('title', '')
    show_info = {
        'label': title,
        'art': {'thumb': show_data['image'].format(width=960, height=540, quality=80, blur=0, bg='false')},
        'info': {'plot': show_data.get('longDescription'), 'title': title},
        # The url to the show is not available in the json data, but encoded in html
        # As the url's are very predictable it is pretty safe to build it from show data.
        'params': {'url': '/'.join((show_data['titleSlug'], show_data['encodedProgrammeId']['letterA'])),
                   'show_name': show_data.get('title', '')}
    }
    if episode_count == 1:
        duration = utils.duration_2_seconds(show_data.get('duration'))
        if duration:
            show_info['info']['duration'] = duration

    return {'episodes': episode_count, 'show': show_info}


def parse_category(page: str):
    """Parse a category page of categories.

    Like https://www.itv.com/hub/categories/comedy
    Unfortunately, the page's structure differs from full_series on several vital points.

    """
    t_start = time.monotonic()

    try:
        page_data = utils.get_json_from_html(page)
        data_list = page_data['props']['pageProps']['programmes']
        shows_data = (_category_item_2_dict(show_data) for show_data in data_list)
        logger.debug('Parsed all shows in %f seconds', time.monotonic() - t_start)
        return shows_data
    except (json.JSONDecodeError, KeyError, ParseError) as err:
        logger.error('Failed parse page shows: %r', err)
        raise ParseError
