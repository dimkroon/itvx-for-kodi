# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from resources.lib import cc_patch
from resources.lib import addon_log
from resources.lib import main
from resources.lib import utils


if __name__ == '__main__':
    utils.addon_info.initialise()
    main.run()
    addon_log.shutdown_log()
