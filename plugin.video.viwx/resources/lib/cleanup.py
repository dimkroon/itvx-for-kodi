# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
import xbmcvfs
import os
import logging
from xml.etree.ElementTree import ElementTree

from codequick.support import logger_id


logger = logging.getLogger(logger_id + '.cleanup')


def remove_setting_value(profile_dir, *setting_ids: str):
    """Remove one or more setting values from the user's profile.

    Intended to be able to remove the value of a setting that is no longer
    available in de add-on's settings.

    """
    fname = profile_dir
    try:
        fname = xbmcvfs.translatePath(os.path.join(profile_dir, 'settings.xml'))
        with open(fname, 'r') as f:
            tree = ElementTree(file=f)
        root = tree.getroot()
        removed = 0
        for elem in root.findall('setting'):
            s_id = elem.attrib.get('id')
            if s_id in setting_ids:
                root.remove(elem)
                removed += 1
                logger.info("Setting '%s' removed from '%s'", s_id, fname)
        if removed:
            tree.write(fname, xml_declaration=False)
        return removed == len(setting_ids)
    except Exception:
        logger.error("Error removing settings '%s' from '%s':", setting_ids, fname, exc_info=True)
    return False