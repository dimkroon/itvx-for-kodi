
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


def get__next__data_from_page(html_page):
    import re
    result = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html_page)
    if result:
        json_str = result[1]
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("__NEXT_DATA__ in HTML page is not valid JSON: %r", e)
            raise ParseError
        return data