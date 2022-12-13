# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

import logging
import time
from datetime import datetime

from xbmcvfs import translatePath
import xbmcaddon

from codequick.support import logger_id
from . errors import *


def create_addon_info(addon_id=None):
    if addon_id:
        addon = xbmcaddon.Addon(addon_id)
    else:
        addon = xbmcaddon.Addon()
    return {
        "name": addon.getAddonInfo("name"),
        "id": addon.getAddonInfo("id"),
        "addon": addon,
        "language": addon.getLocalizedString,
        "version": addon.getAddonInfo("version"),
        "path": addon.getAddonInfo("path"),
        "profile": translatePath(addon.getAddonInfo('profile'))
    }


addon_info = create_addon_info()
logger = logging.getLogger(logger_id + '.utils')


def get_os():
    import platform
    return platform.system(), platform.machine()


def random_string(length):
    """Return a string of random upper and lowercase charters and numbers"""
    import random
    import string

    chars = string.ascii_letters + string.digits
    result = ''.join(random.choice(chars) for _ in range(length))
    return result


def get_json_from_html(page):
    """Extract JSON data from the end of an HTML page and return it as a python object.

    Some pages provide a json data structure in an <script> tag at the end of the page,
    that contains all relevant data.

    """
    import json

    script_start_tag = '<script id="__NEXT_DATA__" type="application/json">'
    pos_start = page.find(script_start_tag) + len(script_start_tag)
    if pos_start < len(script_start_tag):
        logger.error('Failed to parse page shows: script tag not found')
        raise ParseError

    pos_end = page.find('</script>', pos_start)
    if pos_end < pos_start:
        logger.error('Failed to parse page shows: cannot find </script> tag')
        raise ParseError

    script = page[pos_start:pos_end]
    return json.loads(script)


def xml_to_srt(xml_data, outfile):
    """Convert subtitles in XML format to a format that kodi accepts"""
    from xml.etree import ElementTree
    import re

    # Get XML namespace
    match = re.search(r'xmlns="(.*?)" ', xml_data, re.DOTALL)
    if match:
        xmlns = ''.join(('{', match.group(1), '}'))
    else:
        xmlns = ''

    FONT_COL_WHITE = '<font color="white">'
    FONT_END_TAG = '</font>\n'

    root = ElementTree.fromstring(xml_data)

    dflt_styles = {}
    path = ''.join(('./', xmlns, 'head', '/', xmlns, 'styling', '/', xmlns, 'style'))
    styles = root.findall(path)
    for style_def in styles:
        style_id = style_def.get(xmlns + 'id')
        colors = [value for tag, value in style_def.items() if tag.endswith('color')]
        if colors:
            col = colors[0]
            # strip possible alpha value if color is a HTML encoded RBGA value
            if col.startswith('#'):
                col = col[:7]
            dflt_styles[style_id] = ''.join(('<font color="', col, '">'))

    body = root.find(xmlns + 'body')
    if body is None:
        return

    index = 0
    # lines = []
    color_tag = "{http://www.w3.org/ns/ttml#styling}" + 'color'

    for paragraph in body.iter(xmlns + 'p'):
        index += 1

        t_start = paragraph.get('begin')
        t_end = paragraph.get('end')
        if not (t_start and t_end):
            continue
        outfile.write(str(index) + '\n')
        # convert xml time format: begin="00:03:33:14" end="00:03:36:06"
        # to srt format: 00:03:33,140 --> 00:03:36,060
        outfile.write(''.join((t_start[0:-3], ',', t_start[-2:], '0', ' --> ', t_end[0:-3], ',', t_end[-2:], '0\n')))

        p_style = paragraph.get('style')
        p_col = dflt_styles.get(p_style, FONT_COL_WHITE)
        if paragraph.text:
            outfile.write(''.join((p_col, paragraph.text, FONT_END_TAG)))
        for el in paragraph:
            if el.tag.endswith('span') and el.text:
                col = el.get(color_tag, 'white')
                # col = [v for k, v in el.items() if k.endswith('color')]
                # if col:
                outfile.write(''.join(('<font color="', col, '">', el.text, FONT_END_TAG)))
                # else:
                #     lines.append(''.join((FONT_COL_WHITE, el.text, FONT_END_TAG)))
            if el.tail:
                outfile.write(''.join((p_col, el.tail, FONT_END_TAG)))
        outfile.write('\n')


def vtt_to_srt(vtt_doc: str, colourize=True) -> str:
    """Convert a string containing subtitles in vtt format into a format kodi accepts.

    Very simple converter that does not expect much styling, position or colours and tries
    to ignore most fancy vtt stuff. But seems to be enough for most itv subtitles.

    All styling, except bold, italic and underline defined by HTML text in the cue payload is
    removed, as well as position information.

    """
    from io import StringIO
    import re

    # Match a line that start with cue timings. Accept timings with or without hours.
    regex = re.compile(r'(\d{2})?:?(\d{2}:\d{2})\.(\d{3}) +--> +(\d{2})?:?(\d{2}:\d{2})\.(\d{3})')

    # Convert new lines conform WebVTT specs
    vtt_doc = vtt_doc.replace('\r\n', '\n')
    vtt_doc = vtt_doc.replace('\r', '\n')

    # Split the document into blocks that are separated by an empty line.
    vtt_blocks = vtt_doc.split('\n\n')
    seq_nr = 0

    with StringIO() as f:
        for block in vtt_blocks:
            lines = iter(block.split('\n'))

            # Find cue timings, ignore all cue settings.
            try:
                line = next(lines)
                timings_match = regex.match(line)
                if not timings_match:
                    # The first line may be a cue identifier
                    line = next(lines)
                    timings_match = regex.match(line)
                    if not timings_match:
                        # Also no timings in the second line: this is not a cue block
                        continue
            except StopIteration:
                # Not enough lines to find timings: this is not a cue block
                continue

            # Write newline and sequence number
            seq_nr += 1
            f.write('\n{}\n'.format(seq_nr))
            # Write cue timings, add "00" for missing hours.
            f.write('{}:{},{} --> {}:{},{}\n'.format(*timings_match.groups('00')))
            # Write out the lines of the cue payload
            for line in lines:
                f.write(line + '\n')

        srt_doc = f.getvalue()

        if colourize:
            # Remove any markup tag other than the supported bold, italic underline and colour.
            srt_doc = re.sub(r'<([^biuc]).*?>(.*)</\1.*?>', r'\2', srt_doc)

            # convert color tags, accept only simple colour names.
            def sub_color_tags(match):
                colour = match[1]
                if colour in ('white', 'yellow', 'green', 'cyan'):
                    return '<font color="{}">{}</font>'.format(colour, match[2])
                else:
                    logger.debug("Unsupported colour '%s' in vtt file", colour)
                    return match[2]

            srt_doc = re.sub(r'<c\.(.*?)>(.*)</c>', sub_color_tags, srt_doc)
        else:
            # Remove any markup tag other than the supported bold, italic underline.
            srt_doc = re.sub(r'<([^biu]).*?>(.*)</\1.*?>', r'\2', srt_doc)
    return srt_doc


def duration_2_seconds(duration: str):
    """Convert a string like '120 min' to the corresponding number of seconds

    """
    try:
        splits = duration.split()
        if len(splits) == 1:
            units = 'min'
        else:
            units = splits[1]

        if units == 'min':
            return int(splits[0]) * 60
    except (ValueError, AttributeError, IndexError):
        return None


def reformat_date(date_string, old_format, new_format):
    """Take a string containing a datetime in a particular format and
    convert it into another format.

    Usually used to convert datetime strings obtained from a website into a nice readable format.

    """
    try:
        dt = datetime.strptime(date_string, old_format)
    except TypeError:
        dt = datetime(*(time.strptime(date_string, old_format)[0:6]))
    return dt.strftime(new_format)


def strptime(dt_str, format):
    """A bug free alternative to `datetime.datetime.strptime(...)`"""
    return datetime(*(time.strptime(dt_str, format)[0:6]))