
# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022 Dimitri Kroon.
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------


from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch
import types

from test.support.testutils import open_json

from resources.lib import itv

setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests

