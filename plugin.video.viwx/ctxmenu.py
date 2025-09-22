# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import sys
from urllib.parse import parse_qsl, urlencode

from xbmc import log, executebuiltin


def ctxmnu_live_play_from(addon_id, startpoint=None):
    from datetime import datetime, timedelta, timezone
    # noinspection PyUnresolvedReferences
    li = sys.listitem
    channel = li.getProperty('viwx.live_channel')
    start_t = datetime.now(timezone.utc) - timedelta(hours=float(startpoint))
    querystring = urlencode({
        'channel': channel,
        'url': li.getProperty('viwx.live_url'),
        'start_time': start_t.strftime('%Y-%m-%dT%H:%M:%SZ')
    })
    command = ''.join((
        'PlayMedia(plugin://',
        addon_id,
        '/resources/lib/main/play_stream_live?',
        querystring,
        ', noresume)'
    ))
    executebuiltin(command)


def route(argv):
    try:
        addon_id, kwargs = sys.argv
        kwargs = dict(parse_qsl(argv[1], keep_blank_values=True))

        func = kwargs.pop('function')
        if func == 'ctxmnu_live_play_from':
            ctxmnu_live_play_from(addon_id, **kwargs)
    except:
        import traceback
        from xbmcgui import Dialog
        # TODO: Translatable text
        Dialog().ok('viwX Error', "Error invoking context menu")
        log(f'[viwX.ctxmenu] Error invoking context menu: {sys.argv} \n' + traceback.format_exc())


if __name__ == '__main__':
    route(sys.argv)