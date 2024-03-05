
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import xbmc
from codequick.script import Script


@Script.register
def channels(_, port):
    try:
        pass
    except Exception as err:
        # Catch all errors to prevent codequick showing an error message
        xbmc.log("[viwX] Error in iptvmanager.channels: {!r}.".format(err))


@Script.register
def epg(_, port):
    try:
        pass
    except Exception as err:
        # Catch all errors to prevent codequick showing an error message
        xbmc.log("[viwX] Error in iptvmanager.channels: {!r}.".format(err))
