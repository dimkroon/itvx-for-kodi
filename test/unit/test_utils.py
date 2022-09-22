
# ------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
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
# ------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from test.support.testutils import doc_path

import platform

from unittest import TestCase

import resources.lib
from resources.lib import utils


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class Generic(TestCase):
    def test_addon_info(self):
        info = utils.addon_info
        keys = {"name", "id", "addon", "version", "path", "profile"}
        self.assertEqual(set(info.keys()).intersection(keys), keys)
        info = utils.create_addon_info("my.some.plugin")
        self.assertEqual(set(info.keys()).intersection(keys), keys)

    def test_kodi_vers_major(self):
        self.assertIsInstance(utils.kodi_vers_major, int)

    def test_get_os(self):
        cur_os = utils.get_os()
        self.assertIsInstance(cur_os, str)
        self.assertGreater(len(cur_os), 2)

    def test_get_subtitles_temp_file(self):
        fname = utils.get_subtitles_temp_file()
        self.assertTrue(fname.endswith('.srt'))
        # check it is a full path
        if platform.system().startswith('Win'):
            self.assertTrue(fname[1:3], ':\\')
        else:
            self.assertTrue((fname.startswith('/')))

    def test_random_string(self):
        s = utils.random_string(8)
        self.assertIsInstance(s, str)
        self.assertEqual(len(s), 8)
        self.assertEqual(len(utils.random_string(13)), 13)

    def test_duration_2_seconds(self):
        self.assertEqual(50 * 60, utils.duration_2_seconds('50 min'))
        self.assertEqual(123 * 60, utils.duration_2_seconds('123 min'))
        self.assertEqual(62 * 60, utils.duration_2_seconds('62'))
        self.assertEqual(190, utils.duration_2_seconds('3.18'))
        self.assertEqual(90, utils.duration_2_seconds('1:30'))
        self.assertEqual(90, utils.duration_2_seconds('01:30'))
        self.assertEqual(3930, utils.duration_2_seconds('1:05:30'))

        self.assertIsNone(utils.duration_2_seconds('1.25 hrs'))
        self.assertIsNone(utils.duration_2_seconds(''))
        # noinspection PyTypeChecker
        self.assertIsNone(utils.duration_2_seconds(None))
        self.assertIsNone(utils.duration_2_seconds('1:18:43:22'))

    def test_reformat_date(self):
        self.assertEqual(utils.reformat_date('1982-05-02T14:38:32Z', '%Y-%m-%dT%H:%M:%SZ', '%d.%m.%y %H:%M'), '02.05.82 14:38')


# noinspection PyMethodMayBeStatic
class VttToSrt(TestCase):
    def test_1_cue_timestamps(self):
        # convert decimal dot to comma
        srt = utils.vtt_to_srt('01:02:03.234 --> 02:03:04.567')
        self.assertEqual('\n1\n01:02:03,234 --> 02:03:04,567\n', srt)
        # add missing hours
        srt = utils.vtt_to_srt('02:03.234 --> 03:04.567')
        self.assertEqual('\n1\n00:02:03,234 --> 00:03:04,567\n', srt)

    def test_2_add_sequence_numbers(self):
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n\n01:03:03.234 --> 01:03:04.567')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\n\n2\n01:03:03,234 --> 01:03:04,567\n', srt)

    def test_other_style_new_lines(self):
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\r\n\r\n01:03:03.234 --> 01:03:04.567')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\n\n2\n01:03:03,234 --> 01:03:04,567\n', srt)
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\r\r01:03:03.234 --> 01:03:04.567')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\n\n2\n01:03:03,234 --> 01:03:04,567\n', srt)

    def test_remove_non_cue_blocks(self):
        srt = utils.vtt_to_srt('WEBVTT\n\n01:02:03.234 --> 01:02:04.567')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\n', srt)
        # from https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API:
        vtt = """
WEBVTT

STYLE
::cue {
  background-image: linear-gradient(to bottom, dimgray, lightgray);
  color: papayawhip;
}

NOTE comment blocks can be used between style blocks.

STYLE
::cue(b) {
  color: peachpuff;
}

00:00:00.000 --> 00:00:10.000
- Hello <b>world</b>"""
        srt = utils.vtt_to_srt(vtt)
        self.assertEqual('\n1\n00:00:00,000 --> 00:00:10,000\n- Hello <b>world</b>\n', srt)

    def test_write_cue_payload(self):
        # Single line
        srt = utils.vtt_to_srt(
            '01:02:03.234 --> 02:03:04.234\n'
            'text 1\n\n'
            '04:05:06.456 --> 04:05:07.457\n'
            'text 2'
        )
        self.assertEqual(
            '\n1\n01:02:03,234 --> 02:03:04,234\n'
            'text 1\n'
            '\n2\n04:05:06,456 --> 04:05:07,457\n'
            'text 2\n', srt)
        # Multiline
        srt = utils.vtt_to_srt(
            '01:02:03.234 --> 02:03:04.234\n'
            'Text 1 line1\nline2\n\n'
            '04:05:06.456 --> 04:05:07.457\n'
            'Text 2 line1\nline2'
        )
        self.assertEqual(
            '\n1\n01:02:03,234 --> 02:03:04,234\n'
            'Text 1 line1\nline2\n'
            '\n2\n04:05:06,456 --> 04:05:07,457\n'
            'Text 2 line1\nline2\n', srt
        )

    def test_remove_cue_settings(self):
        srt = utils.vtt_to_srt('01:02:03.234 --> 02:03:04.567 line:0 position:20% size:60%')
        self.assertEqual('\n1\n01:02:03,234 --> 02:03:04,567\n', srt)

    def test_remove_vtt_identifier(self):
        srt = utils.vtt_to_srt('some id\n02:03.234 --> 02:04.567\ntext 1')
        self.assertEqual('\n1\n00:02:03,234 --> 00:02:04,567\ntext 1\n', srt)

    def test_remove_unsupported_markup_tags(self):
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<v Julie>text 1</v>')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\ntext 1\n', srt)
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<c.whispering>text 1</c>')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\ntext 1\n', srt)
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<ruby>text 1</ruby>')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\ntext 1\n', srt)
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<rt>text 1</rt>')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\ntext 1\n', srt)

    def test_keep_supported_markup_tags(self):
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<b>text 1</b>')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\n<b>text 1</b>\n', srt)
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<i>text 1</i>')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\n<i>text 1</i>\n', srt)
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<u>text 1</u>')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\n<u>text 1</u>\n', srt)

    def test_convert_colour_tags(self):
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<c.yellow>text 1</c>')
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\n<font color="yellow">text 1</font>\n', srt)

    def test_convert_whole_file(self):
        for subtitle in (
                'vtt/subtitles_1_ok.vtt',
                'vtt/subtitles_doc_martin.vtt'
                ):
            with open(doc_path(subtitle)) as f:
                vtt = f.read()
            srt = utils.vtt_to_srt(vtt)
            self.assertGreater(len(srt), 100)


class ReplaceMarkdown(TestCase):
    def test_empty_string(self):
        self.assertEqual('', resources.lib.utils.replace_markdown(''))

    def test_none_value(self):
        self.assertIsNone(resources.lib.utils.replace_markdown(None))

    def test_non_string_value(self):
        self.assertEqual('', resources.lib.utils.replace_markdown(123))

    def test_remove_italics(self):
        new_str = resources.lib.utils.replace_markdown("Dit is *een* string")
        self.assertEqual(r"Dit is [I]een[/I] string", new_str)
        new_str = resources.lib.utils.replace_markdown("Dit is _een_ string")
        self.assertEqual(r"Dit is [I]een[/I] string", new_str)
        new_str = resources.lib.utils.replace_markdown("Dit is *een_ string")
        self.assertEqual(r"Dit is *een_ string", new_str)
        new_str = resources.lib.utils.replace_markdown("Dit is _een* string")
        self.assertEqual(r"Dit is _een* string", new_str)

    def test_remove_italics_with_escaped_characters(self):
        new_str = resources.lib.utils.replace_markdown(r"\* Dit is *een \*nieuwe\** string")
        self.assertEqual(r"* Dit is [I]een *nieuwe*[/I] string", new_str)
        new_str = resources.lib.utils.replace_markdown(r"\* Dit is _een \_nieuwe\__ string en een \*_oude_")
        self.assertEqual(r"* Dit is [I]een _nieuwe_[/I] string en een *[I]oude[/I]", new_str)
        new_str = resources.lib.utils.replace_markdown(r"Dit is _een \_\_\\nieuwe\\_ string en een _oude_")
        self.assertEqual(r"Dit is [I]een __\nieuwe\[/I] string en een [I]oude[/I]", new_str)
        new_str = resources.lib.utils.replace_markdown(r"Dit is *een \*\_\\nieuwe\\* string en een *oude*")
        self.assertEqual(r"Dit is [I]een *_\nieuwe\[/I] string en een [I]oude[/I]", new_str)
        # Ensure that markdown just after escaped backslashes is handled correctly
        new_str = resources.lib.utils.replace_markdown(r"Dit is een \\*nieuwe* string en *dit* een oude")
        self.assertEqual(r"Dit is een \[I]nieuwe[/I] string en [I]dit[/I] een oude", new_str)
        # Ensure escaped backslashes at the start of a string are handled well
        new_str = resources.lib.utils.replace_markdown(r"\\*Dit* is een *nieuwe* string")
        self.assertEqual(r"\[I]Dit[/I] is een [I]nieuwe[/I] string", new_str)

    def test_remove_bold(self):
        new_str = resources.lib.utils.replace_markdown("Dit is **een** string")
        self.assertEqual(r"Dit is [B]een[/B] string", new_str)
        new_str = resources.lib.utils.replace_markdown("Dit is __een__ string")
        self.assertEqual(r"Dit is [B]een[/B] string", new_str)
        new_str = resources.lib.utils.replace_markdown("Dit is **een__ string")
        self.assertEqual(r"Dit is **een__ string", new_str)
        new_str = resources.lib.utils.replace_markdown("Dit is __een** string")
        self.assertEqual(r"Dit is __een** string", new_str)

    def test_remove_bold_with_escaped_characters(self):
        new_str = resources.lib.utils.replace_markdown(r"\* Dit is **een \*nieuwe\*** string")
        self.assertEqual(r"* Dit is [B]een *nieuwe*[/B] string", new_str)
        new_str = resources.lib.utils.replace_markdown(r"\* Dit is __een \_nieuwe\___ string en een \*__oude__")
        self.assertEqual(r"* Dit is [B]een _nieuwe_[/B] string en een *[B]oude[/B]", new_str)
        new_str = resources.lib.utils.replace_markdown(r"Dit is __een \_\_\\nieuwe\\__ string en een __oude__")
        self.assertEqual(r"Dit is [B]een __\nieuwe\[/B] string en een [B]oude[/B]", new_str)
        new_str = resources.lib.utils.replace_markdown(r"Dit is **een \*\_\\nieuwe\\** string en een **oude**")
        self.assertEqual(r"Dit is [B]een *_\nieuwe\[/B] string en een [B]oude[/B]", new_str)
        # Ensure that markdown just after an escaped backslashes is handled correctly
        new_str = resources.lib.utils.replace_markdown(r"Dit is een \\**nieuwe** string en **dit** een oude")
        self.assertEqual(r"Dit is een \[B]nieuwe[/B] string en [B]dit[/B] een oude", new_str)
        # Ensure escaped backslashes at the start of a string are handled well
        new_str = resources.lib.utils.replace_markdown(r"\\**Dit** is een **nieuwe** string")
        self.assertEqual(r"\[B]Dit[/B] is een [B]nieuwe[/B] string", new_str)

    def test_remove_bold_italics(self):
        new_str = resources.lib.utils.replace_markdown("Dit is ***een*** string")
        self.assertEqual(r"Dit is [B][I]een[/B][/I] string", new_str)
        # might not be legal markdown, but it is the intended result of the function
        new_str = resources.lib.utils.replace_markdown("Dit is ___een___ string en __nog_ een")
        self.assertEqual(r"Dit is [B][I]een[/B][/I] string en [I]_nog[/I] een", new_str)
        new_str = resources.lib.utils.replace_markdown("Dit is _**een**_ string")
        self.assertEqual(r"Dit is [I][B]een[/B][/I] string", new_str)
        new_str = resources.lib.utils.replace_markdown("Dit is **_een_** string")
        self.assertEqual(r"Dit is [B][I]een[/I][/B] string", new_str)

    def test_remove_link(self):
        old_str = 'op rij (na The Wind [I, Daniel Blake](\u002Ffilms\u002Fi-daniel-blake)) [samen] met '
        new_str = resources.lib.utils.replace_markdown(old_str)
        self.assertEqual('op rij (na The Wind I, Daniel Blake) [samen] met ', new_str)
        # backslash escapes in the link text
        old_str = 'op rij (na The Wind [I, \\[Daniel\\] Blake](\u002Ffilms\u002Fi-daniel-blake)) [samen] met '
        new_str = resources.lib.utils.replace_markdown(old_str)
        self.assertEqual('op rij (na The Wind I, [Daniel] Blake) [samen] met ', new_str)

    def test_remove_all(self):
        txt = 'op rij (na The **Wind** That Shakes the Barley *[I, Daniel Blake](\u002Ffilms\u002Fi-daniel-blake)*) samen met '
        new_str = resources.lib.utils.replace_markdown(txt)
        self.assertEqual('op rij (na The [B]Wind[/B] That Shakes the Barley [I]I, Daniel Blake[/I]) samen met ', new_str)


class RemoveMarkdownFromQuotedString(TestCase):
    def handle_saved_doc(self, filename):
        with open(doc_path(filename)) as f:
            doc = f.read()

        new_doc = resources.lib.utils.replace_markdown_from_quoted_strings(doc)
        pos = new_doc.find('*')
        while pos > -1:
            # ensure all * left over in the document are escaped
            self.assertEqual(new_doc[pos-1], '\\', f"'* character found at position {pos}: {new_doc[pos-100:pos+100]}")
            pos = new_doc.find('*', pos + 1)

    def test_remove_from_films_and_docus(self):
        self.handle_saved_doc("films_en_docus-payload.js")

    def test_remove_from_collecties_drama(self):
        self.handle_saved_doc("collecties-drama-payload.js")


class RemoveMarkdown(TestCase):
    def test_remove_markdown(self):
        result = utils.remove_markdown('some *italics* in a string')
        self.assertEqual('some italics in a string', result)
        result = utils.remove_markdown('some _italics_ in a string')
        self.assertEqual('some italics in a string', result)
        result = utils.remove_markdown('some __bold__ in a string')
        self.assertEqual('some bold in a string', result)
        result = utils.remove_markdown('some ### Header in a string')
        self.assertEqual('some  Header in a string', result)

    def test_remove_with_escapes(self):
        result = utils.remove_markdown(r'some \*italics\* *in* a string')
        self.assertEqual(r'some *italics* in a string', result)
        result = utils.remove_markdown(r'some \_italics\_ _in_ a string')
        self.assertEqual(r'some _italics_ in a string', result)
        result = utils.remove_markdown(r'\_some \_italics\_ _in_ a string')
        self.assertEqual(r'_some _italics_ in a string', result)
        result = utils.remove_markdown(r'some \__italics_\_ in a string')
        self.assertEqual('some _italics_ in a string', result)

    def test_escaped_backslashes(self):
        result = utils.remove_markdown(r'\\_some \\_italics\\_ _in_ a string')
        self.assertEqual(r'\some \italics\ in a string', result)

    def test_invalid_values(self):
        self.assertEqual('', utils.remove_markdown(''))
        self.assertIsNone(utils.remove_markdown(None))
        self.assertEqual('', utils.remove_markdown(['dfg', 1]))
