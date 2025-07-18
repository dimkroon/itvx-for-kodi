# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import logging
import requests
import json

from codequick.support import logger_id

from . import itvx
from . import errors
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
        return bsl.get('playlistUrl') or version['playlistUrl']
    else:
        return version['playlistUrl']


def get_short_playlist_url(ccid: str, is_sport: bool = False):
    query = {
        'query': (
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
        ),
        'variables': {
            "ccid": ccid,
            "isNews": not is_sport,
            "isSport": is_sport
        }
    }

    resp = requests.post(
        url='https://shortform.prd.shows.itv.com/graphql',
        json=query
    )
    data = json.loads(resp.content)
    return data['playlistUrl']
