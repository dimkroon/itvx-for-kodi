
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#
#  This file is part of plugin.video.itvhub
#
#  Plugin.video.itvhub is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or (at your
#  option) any later version.
#
#  Plugin.video.itvhub is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#  or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  plugin.video.itvhub. If not, see <https://www.gnu.org/licenses/>.

from codequick import support
from resources.lib import logging
from resources.lib import main
from resources.lib import cc_patch


cc_patch.patch_cc_route()
cc_patch.patch_label_prop()


if __name__ == '__main__':
    main.run()
    logging.shutdown_log()
