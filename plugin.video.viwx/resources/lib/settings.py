
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import logging
import json

import xbmcgui
import xbmcvfs
from codequick import Script
from codequick.support import addon_data, logger_id

from resources.lib import itv_account
from resources.lib import kodi_utils
from resources.lib import addon_log
from resources.lib import errors

logger = logging.getLogger('.'.join((logger_id, __name__)))


TXT_EXPORT_NOT_SINGED_IN = 30623
TXT_EXPORT_SUCCESS = 30624
TXT_EXPORT_FAIL = 30625
TXT_IMPORT_SUCCESS = 30626
TXT_IMPORT_INVALID_DATA = 30627
TXT_IMPORT_FAILED_REFRESH = 30268


@Script.register()
def login(_=None):
    """Ask the user to enter credentials and try to sign in to ITVX.

    On failure ask to retry and continue to do so until signin succeeds,
    or the user selects cancel.
    """
    uname = None
    passw = None

    logger.debug("Starting Login...")
    while True:
        uname, passw = kodi_utils.ask_credentials(uname, passw)
        if not all((uname, passw)):
            logger.info("Entering login credentials canceled by user")
            return
        try:
            itv_account.itv_session().login(uname, passw)
            kodi_utils.show_login_result(success=True)
            from resources.lib import cache
            import xbmc
            cache.my_list_programmes = None
            xbmc.executebuiltin('Container.Refresh')
            return
        except errors.AuthenticationError as e:
            if not kodi_utils.ask_login_retry(str(e)):
                logger.info("Login retry canceled by user")
                return


@Script.register()
def logout(_):
    # just to provide a route for settings' log out
    if itv_account.itv_session().log_out():
        Script.notify(Script.localize(kodi_utils.TXT_ITV_ACCOUNT),
                      Script.localize(kodi_utils.MSG_LOGGED_OUT_SUCCESS),
                      Script.NOTIFY_INFO)
        from resources.lib import cache
        import xbmc
        cache.my_list_programmes = False
        xbmc.executebuiltin('Container.Refresh')


@Script.register()
def import_tokens(_):
    """Import authentication tokens from a web browser or an existing viwx session file."""
    session = itv_account.itv_session()

    file_path = xbmcgui.Dialog().browseSingle(1, 'Open cookie file', 'files')
    if not file_path:
        logger.info("Importing browser cookie canceled.")
        return

    logger.info("Importing browser cookie from %s.", file_path)
    with xbmcvfs.File(file_path, 'r') as f:
        data = f.read()

    data = data.strip()
    try:
        if data.startswith('Itv.Session:"{"tokens":'):
            logger.info("Found Firefox cookie data...")
            data = data[13:-1]
            session_data = json.loads(data)['tokens']['content']
        elif data.startswith('{"tokens":'):
            logger.info("Found Chromium cookie data...")
            session_data = json.loads(data)['tokens']['content']
        else:
            logger.info("Expecting viwX data...")
            session_data = json.loads(data)['itv_session']
        # Just to check its presence
        _ = session_data['refresh_token']
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.error("Invalid auth cookie data:\n", exc_info=True)
        kodi_utils.msg_dlg(TXT_IMPORT_INVALID_DATA)
        return

    logger.debug('Successfully read auth cookie file.')

    session.account_data['itv_session'] = session_data
    session.account_data['cookies'] = {}
    if session.refresh():
        kodi_utils.msg_dlg(TXT_IMPORT_SUCCESS, nickname=session.user_nickname)
    else:
        session.save_account_data()
        kodi_utils.msg_dlg(TXT_IMPORT_FAILED_REFRESH)


@Script.register()
def export_tokens(_):
    import datetime
    import os
    from resources.lib import utils

    # Check if a user is logged in
    user_id = itv_account.itv_session().user_id
    if not user_id:
        logger.info("Nothing to export, user_id = '%s'.", user_id)
        kodi_utils.msg_dlg(TXT_EXPORT_NOT_SINGED_IN)
        return

    session_file = os.path.join(utils.addon_info.profile, "itv_session")
    dest_dir = xbmcgui.Dialog().browseSingle(0, 'Choose directory', 'files')
    if not dest_dir:
        return
    filename = datetime.datetime.now().strftime('viwx_tokens_%Y-%m-%d_%H-%M-%S.txt')
    logger.info("Selected destination directory: %s", dest_dir)
    sep = '' if dest_dir[-1] in ('/', '\\') else '/'
    dest_path = sep.join((dest_dir, filename))
    logger.info("Exporting session data to '%s'.", dest_path)
    xbmcvfs.copy(session_file, dest_path)

    # Both copy() and File.write() return True when writing to an un-writable destination
    # Check if the file exists to ensure copy succeeded.
    if xbmcvfs.exists(dest_path):
        kodi_utils.msg_dlg(TXT_EXPORT_SUCCESS, file_path=dest_path)
    else:
        kodi_utils.msg_dlg(TXT_EXPORT_FAIL)
    return


@Script.register()
def change_logger(_):
    """Callback for settings->generic->log_to.
    Let the user choose between logging to kodi log, to our own file, or no logging at all.

    """
    handlers = (addon_log.KodiLogHandler, addon_log.CtFileHandler, addon_log.DummyHandler)

    try:
        curr_hndlr_idx = handlers.index(type(addon_log.logger.handlers[0]))
    except (ValueError, IndexError):
        curr_hndlr_idx = 0

    new_hndlr_idx, handler_name = kodi_utils.ask_log_handler(curr_hndlr_idx)
    handler_type = handlers[new_hndlr_idx]

    addon_log.set_log_handler(handler_type)
    addon_data.setSettingString('log-handler', handler_name)
