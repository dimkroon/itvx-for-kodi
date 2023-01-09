
# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------


from test.support import fixtures
fixtures.global_setup()

import string
from datetime import datetime
from unittest import TestCase

from resources.lib import utils

from test.support.testutils import doc_path


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class Generic(TestCase):
    def test_addon_info(self):
        info = utils.addon_info
        info.initialise()
        for attr_name in ('addon', 'name', 'id', 'localise', 'profile'):
            self.assertTrue(hasattr(info, attr_name))

    def test_get_os(self):
        cur_os = utils.get_os()
        self.assertIsInstance(cur_os, tuple)
        self.assertEqual(2, len(cur_os))

    def test_random_string(self):
        s = utils.random_string(8)
        self.assertIsInstance(s, str)
        self.assertEqual(len(s), 8)
        self.assertEqual(len(utils.random_string(13)), 13)

    def test_duration_2_seconds(self):
        self.assertEqual(50 * 60, utils.duration_2_seconds('50 min'))
        self.assertEqual(123 * 60, utils.duration_2_seconds('123 min'))
        self.assertEqual(62 * 60, utils.duration_2_seconds('62'))
        self.assertEqual(4500, utils.duration_2_seconds('1.25 hrs'))
        self.assertEqual(4500, utils.duration_2_seconds('1h 15m'))
        self.assertEqual(7200, utils.duration_2_seconds('2h'))
        self.assertEqual(52 * 60, utils.duration_2_seconds('52m'))

        self.assertIsNone(utils.duration_2_seconds(''))
        # noinspection PyTypeChecker
        self.assertIsNone(utils.duration_2_seconds(None))
        self.assertIsNone(utils.duration_2_seconds('1:18:43:22'))

    def test_reformat_date(self):
        self.assertEqual(utils.reformat_date('1982-05-02T14:38:32Z', '%Y-%m-%dT%H:%M:%SZ', '%d.%m.%y %H:%M'),
                         '02.05.82 14:38')

    def test_strptime(self):
        self.assertEqual(datetime(2012, 9, 14, 18, 32, 45),
                         utils.strptime('2012-09-14T18:32:45Z', '%Y-%m-%dT%H:%M:%SZ'))

    def test_paginate(self):
        letters = list(string.ascii_letters)
        lower, next_page_nr = utils.paginate(letters, page_nr=0, page_len=26)
        self.assertEqual(lower, list(string.ascii_lowercase))
        self.assertEqual(1, next_page_nr)
        upper, next_page_nr = utils.paginate(letters, 1, 26)
        self.assertEqual(upper, list(string.ascii_uppercase))
        self.assertIs(next_page_nr, None)
        # merge the remaining 10 of the second page into the first
        all_letters, next_page_nr = utils.paginate(letters, 0, 42, 10)
        self.assertEqual(all_letters, letters)
        self.assertIs(next_page_nr, None)
        # a small page
        self.assertListEqual([1,2,3,4], utils.paginate([1,2,3,4], page_nr=0, page_len=10)[0])
        # invalid page nr
        self.assertListEqual([], utils.paginate([1, 2, 3, 4], page_nr=2, page_len=10)[0])


    def test_list_start_chars(self):
        items = [
            {'show': {'info': {'sorttitle': 'asgf'}}},
            {'show': {'info': {'sorttitle': 'bhfl'}}},
            {'show': {'info': {'sorttitle': 'krinj'}}},
            {'show': {'info': {'sorttitle': 'xhkjh khjkh'}}},
            {'show': {'info': {'sorttitle': 'ujjm'}}},
        ]
        char_list  = utils.list_start_chars(items)
        self.assertListEqual(char_list, ['A', 'B', 'K', 'U', 'X'])
        items.extend([{'show': {'info': {'sorttitle': '#maf '}}}, {'show': {'info': {'sorttitle': '1 ffrk'}}}])
        char_list = utils.list_start_chars(items)
        self.assertListEqual(char_list, ['A', 'B', 'K', 'U', 'X', '0-9'])
        items = [{'show': {'info': {'sorttitle': '#maf '}}}]
        char_list = utils.list_start_chars(items)
        self.assertListEqual(char_list, ['0-9'])


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
        srt = utils.vtt_to_srt('01:02:03.234 --> 01:02:04.567\n<c.yellow>text 1</c>', False)
        self.assertEqual('\n1\n01:02:03,234 --> 01:02:04,567\ntext 1\n', srt)

    def test_convert_whole_file(self):
        for subtitle in (
                'vtt/subtitles_1_ok.vtt',
                'vtt/subtitles_doc_martin.vtt'
                ):
            with open(doc_path(subtitle)) as f:
                vtt = f.read()
            srt = utils.vtt_to_srt(vtt)
            self.assertGreater(len(srt), 100)

