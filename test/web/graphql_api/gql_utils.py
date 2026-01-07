# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------

import re
import json
import requests


def compress(src_str: str) -> str:
    """Remove all whitespace from the start and end of a string and
    replace all whitespace within the string for a single space.

    """
    return re.compile(r'(\s+)').sub(' ', src_str.strip())



def gql_get(query, variables=None, operation_name=None):
    params = {
        'query': query
    }
    if variables is not None:
        if isinstance(variables, str):
            params['variables'] = variables
        else:
            params['variables'] = json.dumps(variables)
    if operation_name is not None:
        params['operationName'] = operation_name

    resp = requests.get(
        'https://content-inventory.prd.oasvc.itv.com/discovery',
        params=params
    )
    resp.raise_for_status()
    return resp.json()