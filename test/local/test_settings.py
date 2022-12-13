# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import logging as py_logging

import unittest
from unittest.mock import MagicMock, patch

from resources.lib import settings
from resources.lib import logging


class TestSettings(unittest.TestCase):
    @patch('resources.lib.itv_account.ItvSession.login')
    # noinspection PyMethodMayBeStatic
    def test_login(self, p_login):
        settings.login(MagicMock())
        p_login.assert_called_once()

    @patch('resources.lib.itv_account.ItvSession.log_out')
    # noinspection PyMethodMayBeStatic
    def test_logout(self, p_logout):
        settings.logout(MagicMock())
        p_logout.assert_called_once()

    @patch("resources.lib.logging.set_log_handler")
    def test_change_logger(self, p_set_log):
        logger = logging.logger

        self.assertTrue(hasattr(settings.change_logger, 'route'))

        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(0, 'kodi log')):
            settings.change_logger(MagicMock())
            p_set_log.assert_called_with(logging.KodiLogHandler)

        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(1, 'file log')):
            settings.change_logger(MagicMock())
            p_set_log.assert_called_with(logging.CtFileHandler)

        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(2, 'no log')) as p_ask:
            with patch.object(logger, 'handlers', new=[logging.CtFileHandler()]):
                settings.change_logger(MagicMock())
                p_set_log.assert_called_with(logging.DummyHandler)
                p_ask.assert_called_with(1)

        # Test default values passed to ask_log_handler().
        # logger not properly initialised
        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(1, 'file log')) as p_ask:
            with patch.object(logger, 'handlers', new=[]):
                settings.change_logger(MagicMock())
                p_ask.assert_called_with(0)

        # Current handler is of an unknown type
        with patch("resources.lib.kodi_utils.ask_log_handler", return_value=(1, 'file log')):
            with patch.object(logger, 'handlers', new=[py_logging.Handler()]):
                settings.change_logger(MagicMock())
                p_ask.assert_called_with(0)
