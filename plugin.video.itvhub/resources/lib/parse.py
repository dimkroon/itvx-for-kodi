# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
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


