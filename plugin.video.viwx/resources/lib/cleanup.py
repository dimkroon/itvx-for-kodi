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


def remove_setting_value(profile_dir, setting_id: str):
    """Remove a setting value from the user's profile.

    Intended to be able to remove the value of a setting that is no longer
    available in de add-on's settings.

    """
    fname = profile_dir
    try:
        fname = xbmcvfs.translatePath(os.path.join(profile_dir, 'settings.xml'))
        with open(fname, 'r') as f:
            tree = ElementTree(file=f)
        root = tree.getroot()
        for elem in root.findall('setting'):
            if elem.attrib.get('id') == setting_id:
                root.remove(elem)
                tree.write(fname, xml_declaration=False)
                logger.info("Setting '%s' removed from '%s'", setting_id, fname)
                return True
        logger.warning("Failed to remove setting '%s': not found in file %s.", setting_id, fname)
    except Exception:
        logger.error("Error removing setting '%s' from '%s':", setting_id, fname, exc_info=True)
    return False