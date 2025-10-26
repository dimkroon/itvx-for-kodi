# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------

import os
import sys
import re
from typing import Dict, List, Tuple

from unittest.mock import patch

import xbmcvfs
import xbmcaddon


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
        info_map = {'profile': profile_dir,
                    'id': 'plugin.video.viwx',
                    'name': 'viwX'}
        patch_g = patch('xbmcaddon.Addon.getAddonInfo',
                         new=lambda self, item: info_map.get(item, ''))
        patch_g.start()

        # Translate path with special:// protocol to a path in the kodifs directory on the
        # top of out test folder.
        xbmcvfs.translatePath = translate_path_mock
        xbmcvfs.File = FileMock
        xbmcaddon.Addon.getLocalizedString = localise_mock

        # prevent requesting MyList items at the import of main.
        patch("resources.lib.cache.my_list_programmes", new=list()).start()

        # Enable logging to file during tests with a new file each test run.
        try:
            os.remove(os.path.join(profile_dir, info_map['name'] + '.log'))
        except FileNotFoundError:
            pass
        patch('xbmcaddon.Addon.getSettingString',
              new=lambda self, item: 'file' if item == 'log-handler' else '').start()
        # Import module to setup logging
        from resources.lib import addon_log

        # Use an xbmcgui.ListItem that stores the values which have been set.
        patch_listitem()

        # Apply codequick patches
        from resources.lib.cc_patch import patch_label_prop
        patch_label_prop()


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

    if session is not None:
        s = session
    else:
        # Ensure web tests do not use a session object that could have been messed up by local tests.
        itv_account._itv_session_obj = None
        s = itv_account.itv_session()

    global credentials_set
    credentials_set = s.refresh()
    if credentials_set is False:
        credentials_set = s.login(account_login.UNAME, account_login.PASSW)
        if not credentials_set:
            import traceback
            traceback.print_exc()
            sys.exit(1)


def setup_web_test(*args):
    # Sign in once per test run.
    if not credentials_set:
        # Ensure web tests start with a new HttpSession object to prevent ill effects from local tests.
        from resources.lib import fetch
        fetch.HttpSession.instance = None
        set_credentials()


def patch_listitem():
    import xbmcgui

    class LI(xbmcgui.ListItem):
        def __init__(self, label: str = "",
                     label2: str = "",
                     path: str = "",
                     offscreen: bool = False) -> None:
            super().__init__()
            assert isinstance(label, str)
            assert isinstance(label2, str)
            assert isinstance(path, str)
            assert isinstance(offscreen, bool)
            self._label = label
            self._label2 = label2
            self._path = path
            self._offscreen = offscreen
            self._is_folder = False
            self._art = {}
            self._info = {}
            self._props = {}

        def getLabel(self) -> str:
            return self._label

        def getLabel2(self) -> str:
            return self._label2

        def setLabel(self, label: str) -> None:
            assert isinstance(label, str), "Argument 'label' must be a string."
            self._label = label

        def setLabel2(self, label: str) -> None:
            assert isinstance(label, str), "Argument 'label' must be a string."
            self._label2 = label

        def setArt(self, dictionary: Dict[str, str]) -> None:
            assert isinstance(dictionary, dict), "Argument 'dictionary' must be a dict."
            self._art.update(dictionary)

        def setIsFolder(self, isFolder: bool) -> None:
            assert isinstance(isFolder, bool), "Argument 'isFolder' must be a boolean."
            self._is_folder = isFolder

        def setInfo(self, type: str, infoLabels: Dict[str, str]) -> None:
            assert isinstance(type, str), "Argument 'type' must be a string."
            assert isinstance(infoLabels, dict), "Argument 'infoLabels' must be a dict."
            assert type in ('video', 'music', 'pictures', 'game')
            info_dict = self._info.setdefault(type, {})
            info_dict.update(infoLabels)

        def setProperty(self, key: str, value: str) -> None:
            assert isinstance(key, str), "Argument 'key' must be a string."
            assert isinstance(value, str), "Argument 'value' must be a string."
            self._props[key] = value

        def setProperties(self, dictionary: Dict[str, str]) -> None:
            assert isinstance(dictionary, dict), "Argument 'dictionary' must be a dict."
            self._props.update(dictionary)

        def getProperty(self, key: str) -> str:
            assert isinstance(key, str), "Argument 'key' must be a string."
            return self._props['key']

        def setPath(self, path: str) -> None:
            assert isinstance(path, str), "Argument 'path' must be a string."
            self._path = path

        def setMimeType(self, mimetype: str) -> None:
            assert isinstance(mimetype, str), "Argument 'mimetype' must be a string."
            self._mimetype = mimetype

        def setContentLookup(self, enable: bool) -> None:
            assert isinstance(enable, bool), "Argument 'enable' must be a boolean."
            self._content_lookup = enable

        def setSubtitles(self, subtitleFiles: List[str]) -> None:
            assert isinstance(subtitleFiles, (list, tuple)), "Argument 'subtitleFiles' must be a tuple or a list."
            self._subtitles = subtitleFiles

        def getPath(self) -> str:
            return self._path

    xbmcgui.ListItem = LI


def translate_path_mock(path: str):
    """Translate 'special://' paths to folders in a directory named 'kodifs' in the top
    test directory, assuming this file is in a folder directly under test/.

    It is not accurate enough to reliably translate every possible special path, but it's
    enough to suit our needs right now.
    """
    if not path.startswith('special://'):
        return path
    special_path = path[10:]
    test_base = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'kodifs'))
    special_base_dir = special_path.split('/', 1)[0]
    os.makedirs(os.path.join(test_base, special_base_dir), exist_ok=True)
    local_dir = os.path.join(test_base, special_path)
    return local_dir


# noinspection PyUnusedLocal
def localise_mock(self, str_id):
    """Return the text corresponding to str_id in the original language file.
    Returns only the text of the first line in the file.

    """
    if 30000 <= str_id <= 30999:
        pattern = f'msgctxt "#{str_id}"\nmsgid "([^"]*)"'
        test_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '../'))
        lang_file = os.path.join(
            test_dir,
            '../plugin.video.viwx/resources/language/resource.language.en_gb/strings.po')
        with open(lang_file) as f:
            lang_texts = f.read()
        match = re.search(pattern, lang_texts)
        if match:
            return match[1]
        return ''
    else:
        return 'UNKNOWN_SYS_STRING'


class FileMock(xbmcvfs.File):
    def __init__(self, filepath: str, mode: str | None = None) -> None:
        super().__init__(filepath, mode)    # doesn't do anything, but keeps pycharm happy.
        if mode is None:
            mode = 'r'
        self._file = open(translate_path_mock(filepath), mode)

    def read(self, numBytes: int = 0) -> str:
        # For some reason Kodi's default numBytes == 0, while Python requires -1 to read all content.
        if numBytes == 0:
            numBytes = -1
        return self._file.read(numBytes)

    def write(self, buffer: str | bytes | bytearray) -> bool:
        return bool(self._file.write(buffer))

    def close(self) -> None:
        self._file.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
