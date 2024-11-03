# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from __future__ import annotations
import time
import unittest

from resources.lib import  utils


def has_keys(dict_obj, *keys, obj_name='dictionary'):
    """Checks if all keys are present in the dictionary"""
    keys_set = set(keys)
    present_keys = set(dict_obj.keys()).intersection(keys_set)
    if present_keys != keys_set:
        absent = keys_set.difference(present_keys)
        raise AssertionError("Key{} {} {} not present in '{}'".format(
            's' if len(absent) > 1 else '',
            absent,
            'is' if len(absent) == 1 else 'are',
            obj_name)
        )


def misses_keys(dict_obj: str, *keys: str, obj_name: str = 'dictionary') -> None:
    """Checks if all keys are NOT present in the dictionary

    :param dict_obj: The dictionary to check
    :param obj_name: Optional name of the object, only used to add a meaningful message to an AssertionError
    :raises AssertionError:

    """
    keys_set = set(keys)
    present_keys = set(dict_obj.keys()).intersection(keys_set)
    if present_keys:
        raise AssertionError("Key{} {} {} unexpectedly present in '{}'".format(
            's' if len(present_keys) > 1 else '',
            present_keys,
            'is' if len(present_keys) == 1 else 'are',
            obj_name)
        )
    return True


def expect_keys(dict_obj: dict, *keys: str, obj_name: str ='dictionary'):
    """Print a warning if a key is not present, but do not fail a test.
    """
    try:
        has_keys(dict_obj, *keys, obj_name=obj_name)
    except AssertionError as err:
        print('Expected', err)


def expect_misses_keys(dict_obj, *keys, obj_name='dictionary'):
    """Print a warning if a key is unexpectedly present, but do not fail a test.
    """
    try:
        return misses_keys(dict_obj, *keys, obj_name=obj_name)
    except AssertionError as err:
        print(err)
        return False


def is_url(url: str, ext: str| list | tuple | None = None) -> bool:
    """Short and simple check if the string `url` is indeed a URL.
    This is in no way intended to completely validate the URL - it is just to check
    that the string is not just a path without protocol specification, or just some
    other string that is not a URL at all.

    :param url: str: String to check.
    :param ext: Optional file extension(s) (including preceding dot) of the document requested in the URL.

    """
    if not isinstance(url, str):
        return False
    result = url.startswith('https://')
    result = result and url.find('//', 7) == -1
    if ext is not None:
        if isinstance(ext, (tuple, list)):
            result = result and any(url.endswith(extension) or extension + '?' in url for extension in ext)
        else:
            result = result and (url.endswith(ext) or ext + '?' in url)
    return result


def is_iso_utc_time(time_str):
    """check if the time string is in a format like yyyy-mm-ddThh:mm:ssZ which is
    often used by itv's web services.
    Accept times with or without milliseconds
    """
    try:
        if '.' in time_str:
            time.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        else:
            time.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')
        return True
    except (ValueError, TypeError):
        return False


def is_encoded_programme_or_episode_id(item: dict) -> bool:
    try:
        if len(item) != 2:
            return False
        la = item['letterA']
        us = item['underscore']
        if la == '' and us == '':
            return True
        if not(isinstance(la, str) and la):
            return False
        for char in '_/':
            if char in la:
                return False
        if not(isinstance(us, str) and us):
            return False
        for char in 'a/':
            if char in us:
                return False
        return True
    except (KeyError, ValueError):
        return False


def is_encoded_programme_id(item):
    return is_encoded_programme_or_episode_id(item)


def is_encoded_episode_id(item):
    return is_encoded_programme_or_episode_id(item)


def is_li_compatible_dict(testcase: unittest.TestCase, dict_obj: dict):
    """Check if `dict_obj` is a dict that can be passed to codequick's Listitem.from_dict()

    """
    testcase.assertIsInstance(dict_obj, dict)
    has_keys(dict_obj, 'label', 'params')
    for item_key, item_value in dict_obj.items():
        testcase.assertTrue(item_key in ('label', 'art', 'info', 'params', 'properties'))
        if item_key == 'label':
            testcase.assertIsInstance(dict_obj['label'], str)
            testcase.assertTrue(dict_obj['label'])
            continue

        testcase.assertIsInstance(item_value, dict)
        # all sub items must be strings or integers.
        # Is not a requirement for Listitem, but I like to keep it that way.
        for item_val in item_value.values():
            testcase.assertIsInstance(item_val, (str, int, type(None)))

        if item_key == 'art':
            for art_type, art_link in item_value.items():
                testcase.assertTrue(art_type in ('thumb', 'fanart', 'poster'),
                                    'Unexpected artType: {}'.format(art_type))
                testcase.assertTrue(not art_link or is_url(art_link))
        if item_key == 'info':
            for param, param_val in item_value.items():
                if param in ('episode', 'season'):
                    testcase.assertIsInstance(param_val, (int, type(None)))
        elif item_key == 'params':
            for param, param_val in item_value.items():
                if param == 'url' and param_val:
                    testcase.assertTrue(is_url(param_val))
        elif item_key == 'properties':
            for param, param_val in item_value.items():
                if param == 'resumetime':
                    testcase.assertIsInstance(param_val, str)
                    testcase.assertGreaterEqual(int(param_val), 0)
                if param == 'totaltime':
                    testcase.assertIsInstance(param_val, int)
    return True


def is_tier_info(item) -> bool:
    if not isinstance( item, list):
        return False
    return 'FREE' in item or 'PAID' in item


def is_not_empty(item, type):
    if not isinstance(item, type):
        return False
    if type in (int, float, bool):
        return True
    else:
        return bool(item)


def check_live_stream_info(playlist):
    """Check the structure of a dictionary containing urls to playlist and subtitles, etc.
    This checks a playlist of type application/vnd.itv.online.playlist.sim.v3+json, which is
    returned for live channels
    """
    mandatory_keys = ['Video', 'ProductionId', 'VideoType', 'ContentBreaks', 'Cdn']
    has_keys(playlist, *mandatory_keys, obj_name='Playlist')

    video_inf = playlist['Video']
    has_keys(video_inf, 'Duration', 'Subtitles', 'VideoLocations', obj_name="Playlist['Video']")
    # Field token has always been None and was removed in 2023-09
    misses_keys(video_inf, 'token', obj_name="Playlist['Video']")

    assert isinstance(video_inf['Duration'], str)
    assert isinstance(video_inf['Subtitles'], (type(None), str))

    strm_inf = video_inf['VideoLocations']
    assert isinstance(strm_inf, list), 'VideoLocations is not a list but {}'.format(type(strm_inf))
    for strm in strm_inf:
        assert isinstance(strm['IsDar'], bool)
        assert is_url(strm['Url'], '.mpd')
        assert is_url(strm['StartAgainUrl'], '.mpd')
        assert is_url(strm['KeyServiceUrl'])
        assert '{START_TIME}' in strm['StartAgainUrl']


def has_adverts(playlist):
    breaks = playlist['ContentBreaks']
    has_breaks = len(breaks) > 1
    if len(breaks) == 1:
        # If there  are no content breaks the list of breaks has a single item with an empty actions list.
        assert len(breaks[0]['Actions']) == 0
    for stream in playlist['Video']['VideoLocations']:
        assert stream['IsDar'] == has_breaks
    return has_breaks


def check_catchup_dash_stream_info(playlist):
    """Check the structure of a dictionary containing urls to playlist and subtitles, etc.
    This checks a playlist of type application/vnd.itv.vod.playlist.v2+json, which is
    returned for catchup productions
    """
    has_keys(playlist, 'Video', 'ProductionId', 'VideoType', 'ContentBreaks', obj_name='Playlist')

    video_inf = playlist['Video']
    has_keys(video_inf, 'Duration', 'Timecodes', 'Base', 'MediaFiles', 'Subtitles', 'Token',
             obj_name="Playlist['Video']")

    assert isinstance(video_inf['Duration'], str)
    assert isinstance(video_inf['Token'], (type(None), str))
    assert video_inf['Base'].startswith('https://') and video_inf['Base'].endswith('/')

    strm_inf = video_inf['MediaFiles']
    assert isinstance(strm_inf, list), 'MediaFiles is not a list but {}'.format(type(strm_inf))
    for strm in strm_inf:
        assert (not strm['Href'].startswith('https://')) and '.mpd?' in strm['Href'], \
            "Unexpected playlist url: <{}>".format(strm['Href'])
        assert is_url(strm['KeyServiceUrl']), "Unexpected KeyServiceUrl url: <{}>".format(strm['KeyServiceUrl'])

    subtitles = video_inf['Subtitles']
    assert isinstance(subtitles, (type(None), list)), 'MediaFiles is not a list but {}'.format(type(strm_inf))
    if subtitles is not None:
        for subt in subtitles:
            assert is_url(subt['Href'], '.vtt')
        # Of little value right now, because only a few streams are checked.
        assert len(subtitles) == 1


def check_news_collection_stream_info(playlist):
    """Check the structure of a dictionary containing urls to the mp4 file
    This checks a playlist of type application/vnd.itv.vod.playlist.v2+json, which is
    returned for short news items.

    """
    has_keys(playlist, 'Video', 'ProductionId', 'VideoType', 'ContentBreaks', obj_name='Playlist')
    assert playlist['VideoType'] == 'SHORT'

    video_inf = playlist['Video']
    has_keys(video_inf, 'Duration', 'MediaFiles', obj_name="Playlist['Video']")
    # If these are present it is a 'normal' catchup item
    misses_keys(video_inf, 'Timecodes', 'Subtitles', 'Token', 'Base', obj_name="Playlist['Video']")

    assert isinstance(video_inf['Duration'], str)

    strm_inf = video_inf['MediaFiles']
    assert isinstance(strm_inf, list), 'MediaFiles is not a list but {}'.format(type(strm_inf))
    assert len(strm_inf) == 1
    assert is_url(strm_inf[0]['Href'], '.mp4')


def check_short_form_slider(testcase, slider, name=''):
    has_keys(slider, 'header', 'items', 'key', obj_name=name)
    expect_keys(slider, 'genre', 'isRail', 'dataTestId', 'titleType')
    testcase.assertTrue(slider['key'] in ('newsShortForm', 'sportShortForm'))
    testcase.assertEqual(slider['tileType'], 'news')  # also for slider sport, flag if it changes.
    header = slider['header']
    if not header['title']:
        # News's title is empty, but has a field iconTitle instead
        testcase.assertTrue(is_not_empty(header['iconTitle'], str))
    has_keys(header, 'linkHref', 'linkText', obj_name=slider['key'] + '.header')
    for item in slider['items']:
        check_short_form_item(item)


def check_short_form_item(item):
    """Check the content of a shortForm item from a collection or from category 'News'

    In both news and collections shortForm items are mostly short mp4 files, but a few are
    normal programmes, like a full news programme, or a full sports match.

    Items from collection or from Hero of category have an extra field `posterImage`, but it's not used in the addon.

    """
    objname = "shortform item '{}'".format(item.get('episodeTitle', 'unknown title'))
    has_keys(item, 'episodeTitle', 'imageUrl', 'contentType', obj_name=objname)
    misses_keys(item, 'isPaid', 'tier', 'imagePresets')

    assert(item['contentType'] in ('shortform', 'episode', 'fastchannelspot'))

    if item['contentType'] == 'fastchannelspot':
        assert(item['channel'].startswith('fast'))
        misses_keys(item, 'description, synopsis', obj_name=objname)
    else:
        has_keys(item, 'episodeId', 'titleSlug', 'dateTime', obj_name=objname)
        assert is_not_empty(item['episodeId'], str)
        assert is_not_empty(item['titleSlug'], str)
        assert is_iso_utc_time(item['dateTime'])
        assert isinstance(item.get('duration'), (int, type(None)))

    if item['contentType'] == 'shortform':
        # items like news and sport clips
        has_keys(item, 'duration', 'synopsis')
        misses_keys(item, 'programmeTitle', 'encodedProgrammeId', 'encodedEpisodeId')
        assert isinstance(item['synopsis'], str, ) and item['synopsis']
        assert isinstance(item.get('duration'), int)
        # episodeId on real clips does not require letterA encoding
        assert '/' not in item['episodeId']
    elif item['contentType'] == 'episode':
        # 'Normal' programmes
        has_keys(item, 'programmeTitle', 'encodedEpisodeId')
        misses_keys(item, 'duration', 'synopsis')
        expect_keys(item, 'programmeTitle')  # not used by the parser.
        assert is_not_empty(item['encodedEpisodeId'], dict)
        # episodeId on regular programmes DO require letterA encoding
        assert '/' in item['episodeId']

    assert is_not_empty(item['episodeTitle'], str)
    assert is_url(item['imageUrl'], ('.jpg', '.jpeg', '.png', '.bmp')), \
           "item '{}' has not a valid imageUrl".format(item['episodeTitle'])
    # True shortform items have a field 'href', but items produced by heroAndLatest and curatedRails
    # on the news category page don't.
    if 'href' in item:
        assert item['href'].startswith('/')
        assert item['href'].endswith('undefined')


def check_category_item(item):
    """Check a news item from the section 'longformData' which contains full episodes from itv news
    and other news related programmes.

    """
    title = item['title']
    # TODO: Check if this is the same as a normal episode
    has_keys(
        item,
        'title', 'titleSlug', 'encodedProgrammeId', 'channel', 'description', 'imageTemplate',
        'contentInfo', 'partnership', 'contentOwner', 'tier', 'broadcastDateTime', 'programmeId', 'contentType',
        obj_name=f'categoryItem-{title}'
    )

    assert is_not_empty(item['title'], str)
    # Only the contentType from items in category news vary, normal category items are all of type 'brand'.
    assert item['contentType'] in ('series', 'special', 'film', 'episode', 'brand')
    assert isinstance(item['titleSlug'], str) and item['titleSlug'], "Invalid titleSlug in '{}'.".format(title)
    assert is_encoded_programme_id(item['encodedProgrammeId']), "Invalid encodedProgrammeId in '{}'.".format(title)
    if 'encodedEpisodeId' in item:
        assert is_encoded_episode_id(item['encodedEpisodeId']), "Invalid encodedEpisodeId in {}".format(title)
        assert item['encodedEpisodeId']['letterA'] != '', "Legacy use of empty encodedEpisodeId"
            # As of may 2024 payable items in categories -> new -> Latest Programmes do have
            # the same programme and episode ID, which is a bug, and they won't play on the web either.
            # So commented out for now to pass web tests.
            #assert item['encodedProgrammeId'] != item['encodedEpisodeId']
    else:
        # Check that items lacking an encodedEpisodeId are playable. Brands can be both.
        assert 'series' not in item['contentInfo'].lower()
    assert isinstance(item['description'], str) and item['description'], "Invalid description in '{}'.".format(title)
    assert is_url(item['imageTemplate']), "Invalid imageTemple in '{}'.".format(title)
    # ContentInfo is at this moment what is being shown on the web, but can be empty, or have
    # info like 'series 1'.
    assert isinstance(item['contentInfo'], str), "Invalid type of contentInfo in '{}'.".format(title)
    assert (item['contentInfo'].lower().startswith('series')
            or utils.duration_2_seconds(item['contentInfo']) is not None
            or item['contentInfo'] == ''), \
            "invalid contentInfo '{}' for item '{}'.".format(item['contentInfo'], item['title'])
    assert is_tier_info(item['tier']), "Invalid tier in '{}'.".format(title)
    # Broadcast datetime can be None occasionally.
    assert item['broadcastDateTime'] is None or is_iso_utc_time(item['broadcastDateTime']), \
        "Invalid broadcastDateTime in '{}'.".format(title)
    assert isinstance(item['programmeId'], str) and item['programmeId'], "Invalid programmeId in '{}'.".format(title)


def check_item_type_programme(testcase, progr_data, parent):
    """Check an item of type `programme` as return in lists of recommendations.
    Not to be confused with the programme info in category items.

    Very similar to MyList items, but with fewer fields and some field names are slightly different.

    """
    obj_name = '{}.{}'.format(parent, progr_data['title'])
    has_keys(progr_data, 'contentType', 'duration', 'imageUrl', 'itvxImageUrl', 'programmeId',
             'synopsis', 'tier', 'title', obj_name=obj_name)
    expect_keys(progr_data, 'coldStart', 'contentOwner', 'latestProduction', 'longRunning', obj_name=obj_name)

    misses_keys(progr_data, 'encodedProgrammeId', 'categories', 'longRunningimagePresets')

    testcase.assertTrue(progr_data['contentType'] in ('PROGRAMME', 'SPECIAL', 'FILM'))
    testcase.assertTrue(is_not_empty(progr_data['title'], str))
    testcase.assertTrue(is_not_empty(progr_data['synopsis'], str))
    testcase.assertTrue(is_url(progr_data['imageUrl']))
    testcase.assertTrue(is_url(progr_data['itvxImageUrl']))
    testcase.assertFalse(is_encoded_programme_id(progr_data['programmeId']))
    testcase.assertTrue(is_not_empty(progr_data['programmeId'], str))
    testcase.assertTrue(progr_data['tier'] in('FREE', 'PAID'))

    testcase.assertIsInstance(progr_data['numberOfAvailableSeries'], list)
    testcase.assertIsInstance(progr_data['numberOfEpisodes'], (int, type(None)))


def check_genres(testcase, genre_item, item_name='unknown'):
    """Check that `genre_item` is a list of dicts.

    :param unittest.TestCase testcase: Instanceof unittest.TestCase to run the tests in.
    :param list genre_item: The value of a field named 'genres' in data returned by ITVX.

    """
    for genre in genre_item:
        has_keys(genre, 'id', 'name', obj_name=item_name)
        # testcase.assertTrue({'id', 'name'} == set(genre.keys()), f'Unexpected fields in genre of item {item_name}')
        testcase.assertTrue(
            genre['id'] in
            ['FACTUAL', 'DRAMA_AND_SOAPS', 'CHILDREN', 'FILM', 'SPORT', 'COMEDY', 'NEWS', 'ENTERTAINMENT'],
            f"Unexpected genre '{genre['id']}' in item f{item_name}")

