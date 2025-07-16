# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------


import json
import logging


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
        'query GetVersionByProductionId($versionsFilter: VersionFilter!) {'
            'versions(filter: $versionsFilter) {'
                '__typename '
                'legacyId '
                'ccid '
                'playlistUrl '
                'visuallySigned '
                'audioDescribed '
                'bsl { playlistUrl } '
                'variants { features } '
            '}'
        '}'
    )

    variables = (
       '{'
           '"versionsFilter":{'
               '"ccid":"%s",'
               '"tiers":["FREE","PAID"],'
               '"features":["OUTBAND_WEBVTT","MPEG_DASH","WIDEVINE", "INBAND_AUDIO_DESCRIPTION"],'
               '"broadcaster":"ITV",'
               '"platform":"%s"'
           '}'
       '}'
    ) % (ccid, itvx.PLATFORM_TAG)

    data = _gql_query(query, variables)
    if prefer_bsl:
        return data['bsl'].get('playlistUrl') or data['playlistUrl']
    else:
        return data['playlistUrl']