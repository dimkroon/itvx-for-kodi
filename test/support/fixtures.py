# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viewx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import os

from unittest.mock import patch


patch_g = None


def global_setup():
    """Fixture required for all test.
    Ensure this is imported and called in every test module first thing. At least before
    importing any other module from the project or other kodi related module.

    As it is global for all tests there is no need to tear down.

    """
    global patch_g
    if patch_g is None:
        # Ensure that kodi's special://profile refers to a predefined folder. Just in case
        # some code want to write, whether intentional or not.
        profile_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'addon_profile_dir'))
        patch_g = patch('xbmcaddon.Addon.getAddonInfo',
                         new=lambda self, item: profile_dir if item == 'profile' else '')
        patch_g.start()

        # Enable logging to file during tests with a new file each test run.
        try:
            os.remove(os.path.join(profile_dir, '.log'))
        except FileNotFoundError:
            pass
        patch('xbmcaddon.Addon.getSettingString',
              new=lambda self, item: 'file' if item == 'log-handler' else '').start()


patch_1 = None


class RealWebRequestMadeError(Exception):
    pass


def setup_local_tests():
    """Module level fixture for all local tests. Ensures that no unintentional real
    web requests can occur.

    """
    global patch_1
    patch_1 = patch('requests.sessions.Session.send', side_effect=RealWebRequestMadeError)
    patch_1.start()


def tear_down_local_tests():
    global patch_1

    if patch_1:
        patch_1.stop()
        patch_1 = None


credentials_set = False

def set_credentials(session=None) -> None:
    # IMPORTANT: import here, after global setup has been executed and paths to addon profile_dir are set!!
    from resources.lib import itv_account
    try:
        from test import account_login
    except ImportError:
        raise RuntimeError("Missing ITV account credentials.")

    global credentials_set
    s = session if session is not None else itv_account.itv_session()
    if s.refresh() is False:
        with patch("resources.lib.kodi_utils.ask_credentials", new=lambda x, y: (x,y)):
            credentials_set = s.login(account_login.UNAME, account_login.PASSW)


def setup_web_test(*args):
    # Sign in once per test run.
    if not credentials_set:
        set_credentials()
