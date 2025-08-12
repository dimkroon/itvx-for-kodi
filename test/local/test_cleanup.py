# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from io import StringIO
from unittest import TestCase
from unittest.mock import MagicMock, patch, mock_open


from resources.lib import utils
from resources.lib import cleanup


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class RemoveSettingValue(TestCase):
    settings_xml = (
        '<settings version="2">\n'
        '    <setting id="current">true</setting>\n'
        '    <setting id="old_setting" default="true">true</setting>\n'
        '    <setting id="existing">true</setting>\n'
        '</settings>'
    )

    def test_remove_setting(self):
        buffer = StringIO()
        with patch('builtins.open', mock_open(read_data=self.settings_xml)) as m_open:
            m_open.return_value.write = buffer.write
            result = cleanup.remove_setting_value(utils.addon_info.profile, 'old_setting')
        self.assertIs(result, True)
        new_xml = buffer.getvalue()
        self.assertEqual('<settings version="2">\n'
                         '    <setting id="current">true</setting>\n'
                         '    <setting id="existing">true</setting>\n'
                         '</settings>',
                         new_xml)

    def test_remove_multiple_setting(self):
        buffer = StringIO()
        with patch('builtins.open', mock_open(read_data=self.settings_xml)) as m_open:
            m_open.return_value.write = buffer.write
            result = cleanup.remove_setting_value(utils.addon_info.profile, 'old_setting', 'current')
        self.assertIs(result, True)
        new_xml = buffer.getvalue()
        self.assertEqual('<settings version="2">\n'
                         '    <setting id="existing">true</setting>\n'
                         '</settings>',
                         new_xml)

    def test_setting_not_exists(self):
        with patch('builtins.open', mock_open(read_data=self.settings_xml)) as m_open:
            result = cleanup.remove_setting_value(utils.addon_info.profile, 'not_existing')
        self.assertIs(result, False)
        m_open.return_value.write.assert_not_called()

    def test_file_not_exists(self):
        with patch('builtins.open', side_effect=OSError):
            result = cleanup.remove_setting_value(utils.addon_info.profile, 'old_setting')
        self.assertIs(result, False)
