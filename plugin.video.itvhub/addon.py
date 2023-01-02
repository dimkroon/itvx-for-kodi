# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------


from codequick import support
from resources.lib import logging
from resources.lib import main
from resources.lib import cc_patch


cc_patch.patch_cc_route()
cc_patch.patch_label_prop()


if __name__ == '__main__':
    main.run()
    logging.shutdown_log()
