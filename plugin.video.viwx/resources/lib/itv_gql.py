# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------


import json
import logging
import requests

from codequick.support import logger_id

from . import fetch

logger = logging.getLogger(logger_id + '.itvx')


def _gql_query(query, variables=None, operation_name=None):
    params = {
        'query': query
    }
    if variables is not None:
        params['variables'] = variables
    if operation_name is not None:
        params['operationName'] = operation_name

    resp = fetch.get_json(
        'https://content-inventory.prd.oasvc.itv.com/discovery',
        params=params
    )
    return resp


def _gql_post(url, query, variables=None):
    data = {'query': query}
    if variables:
        data['variables'] = variables
    resp = requests.post(
            url,
            headers={
             'user-agent': fetch.USER_AGENT,
             'origin': 'https://app.10ft.itv.com',
             'referer': 'https://app.10ft.itv.com/'
            },
            json=data)
    data = json.loads(resp.content)
    return data


def get_playlist_url(ccid: str, prefer_bsl: bool = False):
    """Return the playlist url of the title specified by ccid.

    """
    query = (
        'query Title {'
            'titles(filter: {ccid: "%s"}) {'
                '__typename '
                'title '
                'ccid '
                'latestAvailableVersion {'
                    'audioDescribed '
                    'playlistUrl '
                    'bsl { playlistUrl }'
                '}'
            '}'
        '}'
    ) % ccid

    titles = _gql_query(query)['data']['titles']
    if len(titles) > 1:
        logger.warning("get_playlist_urls got multiple titles for ccid '%s': %s", ccid, titles)
    version = titles[0]['latestAvailableVersion']
    bsl = version['bsl']
    if prefer_bsl and bsl:
        playlist = bsl.get('playlistUrl') or version['playlistUrl']
    else:
        playlist = version['playlistUrl']
    return playlist, version['audioDescribed']


def get_short_playlist_url(ccid: str, is_sport: bool = False):
    query = (
        'query GetClipByCcid($ccid: ID!, $isNews: Boolean!, $isSport: Boolean!) {'
            'clip(ccid: $ccid) @include(if: $isNews) {'
                'ccid '
                'title '
                'duration '
                'playlistLink '
                'subtitles '
                'guidance '
                'syndicatedToSTV '
            '}'
            'sportsClip(ccid: $ccid) @include(if: $isSport) {'
                'ccid '
                'title '
                'duration '
                'playlistLink '
                'subtitles '
                'guidance '
                'syndicatedToSTV '
            '}'
        '}'
    )
    variables = {
        "ccid": ccid,
        "isNews": not is_sport,
        "isSport": is_sport
    }

    data = _gql_post('https://shortform.prd.shows.itv.com/graphql', query, variables)
    if is_sport:
        return data['data']['sportsClip']['playlistLink']
    else:
        return data['data']['clip']['playlistLink']
