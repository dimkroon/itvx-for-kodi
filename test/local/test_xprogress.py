# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import time
import itertools

from unittest import TestCase
from unittest.mock import patch, Mock

from resources.lib import xprogress, errors

from support.testutils import HttpResponse


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class TestPLayTimeMonitor(TestCase):
    def test_property_playtime(self):
        mon = xprogress.PlayTimeMonitor('')
        mon._playtime = 32.2568
        self.assertEqual(32256, mon.playtime)

    @patch('resources.lib.xprogress.PlayTimeMonitor.getPlayingFile', return_value='my_playing_file')
    @patch('resources.lib.xprogress.PlayTimeMonitor._handle_event')
    def test_on_av_started(self, p_evt, _):
        mon = xprogress.PlayTimeMonitor('')
        mon.onAVStarted()
        self.assertIs(mon._status, xprogress.PlayState.PLAYING)
        p_evt.assert_called_once()
        self.assertTrue('startUpComplete' in p_evt.call_args.args)

        # Error getting play time, i.e. not playing
        p_evt.reset_mock()
        mon = xprogress.PlayTimeMonitor('')
        mon.getTime = Mock(side_effect=RuntimeError)
        mon.onAVStarted()
        self.assertIs(mon._status, xprogress.PlayState.STOPPED)
        p_evt.assert_not_called()

        # Already playing
        p_evt.reset_mock()
        mon = xprogress.PlayTimeMonitor('')
        mon._status = xprogress.PlayState.STOPPED
        mon.onAVStarted()
        self.assertIs(mon._status, xprogress.PlayState.STOPPED)
        p_evt.assert_not_called()

    @patch('resources.lib.xprogress.PlayTimeMonitor._handle_event')
    def test_on_av_change(self, p_event):
        # Change to a new file
        mon = xprogress.PlayTimeMonitor('')
        mon._cur_file = 'already_playing_file'
        mon._status = xprogress.PlayState.PLAYING
        with patch.object(mon, 'getPlayingFile', return_value='new file'):
            mon.onAVChange()
            self.assertIs(mon._status, xprogress.PlayState.STOPPED)
            p_event.assert_called_once()
            self.assertTrue('heartbeat' in p_event.call_args.args)

        # Same File
        p_event.reset_mock()
        mon = xprogress.PlayTimeMonitor('')
        mon._cur_file = 'already_playing_file'
        mon._status = xprogress.PlayState.PLAYING
        with patch.object(mon, 'getPlayingFile', return_value='already_playing_file'):
            mon.onAVChange()
            self.assertIs(mon._status, xprogress.PlayState.PLAYING)
            p_event.assert_not_called()

    @patch('resources.lib.xprogress.PlayTimeMonitor._handle_event')
    def test_on_play_back_stopped(self, p_event):
        # While playing
        mon = xprogress.PlayTimeMonitor('')
        mon._status = xprogress.PlayState.PLAYING
        mon.onPlayBackStopped()
        self.assertIs(mon._status, xprogress.PlayState.STOPPED)
        p_event.assert_called_once()
        self.assertTrue('heartbeat' in p_event.call_args.args)

        # While stopped
        p_event.reset_mock()
        mon = xprogress.PlayTimeMonitor('')
        mon._status = xprogress.PlayState.STOPPED
        mon.onPlayBackStopped()
        self.assertIs(mon._status, xprogress.PlayState.STOPPED)
        p_event.assert_not_called()

        # Uninitialised
        p_event.reset_mock()
        mon = xprogress.PlayTimeMonitor('')
        mon._status = xprogress.PlayState.UNDEFINED
        mon.onPlayBackStopped()
        self.assertIs(mon._status, xprogress.PlayState.STOPPED)
        p_event.assert_not_called()

    @patch('resources.lib.xprogress.PlayTimeMonitor.onPlayBackStopped')
    def test_other_stop_callbacks(self, p_onstopped):
        mon = xprogress.PlayTimeMonitor('')
        mon._status = xprogress.PlayState.PLAYING
        mon.onPlayBackEnded()
        p_onstopped.assert_called_once()

        p_onstopped.reset_mock()
        mon.onPlayBackError()
        p_onstopped.assert_called_once()

    def test_wait_unit_playing(self):
        # playing has started
        mon = xprogress.PlayTimeMonitor('')
        mon._status = xprogress.PlayState.PLAYING
        result = mon.wait_until_playing(0.003)
        self.assertIs(result, True)

        # playing has stopped
        mon = xprogress.PlayTimeMonitor('')
        mon._status = xprogress.PlayState.STOPPED
        result = mon.wait_until_playing(0.003)
        self.assertIs(result, False)

        # Playing times out
        with patch('xbmc.Monitor.waitForAbort', new=lambda a, b: time.sleep(0.001)):
            mon = xprogress.PlayTimeMonitor('')
            result = mon.wait_until_playing(0.003)
            self.assertIs(result, False)

        # Abort Requested
        with patch('xbmc.Monitor.waitForAbort', side_effect=(False, True)):
            mon = xprogress.PlayTimeMonitor('')
            result = mon.wait_until_playing(15)
            self.assertIs(result, False)

    def test_monitor_progress(self):
        # While not intialised
        with patch('xbmc.Monitor.waitForAbort') as p_wait:
            mon = xprogress.PlayTimeMonitor('')
            mon.monitor_progress()
            p_wait.assert_not_called()

        # While playing
        with patch('xbmc.Monitor.waitForAbort', return_value=False) as p_wait:
            mon = xprogress.PlayTimeMonitor('')
            mon._status = xprogress.PlayState.STOPPED
            mon.monitor_progress()
            p_wait.assert_called_once()

        # times out
        with patch('xbmc.Monitor.waitForAbort', side_effect=(False, False, True)) as p_wait:
            mon = xprogress.PlayTimeMonitor('')
            mon._status = xprogress.PlayState.PLAYING
            mon.monitor_progress()
            self.assertEqual(3, p_wait.call_count)

        # Has stopped undetected
        with patch('xbmc.Monitor.waitForAbort', return_value=False) as p_wait:
            mon = xprogress.PlayTimeMonitor('')
            mon.getTime = Mock(side_effect=(1,2,3, RuntimeError))
            mon.onPlayBackStopped = Mock()
            mon._status = xprogress.PlayState.PLAYING
            mon.monitor_progress()
            self.assertEqual(4, p_wait.call_count)
            mon.onPlayBackStopped.assert_called_once()

        # posts heartbeat events
        with patch('xbmc.Monitor.waitForAbort', new=lambda a, b: time.sleep(0.001)):
            mon = xprogress.PlayTimeMonitor('')
            mon.getTime = Mock(side_effect=(1, 2, 3, 4, RuntimeError))
            mon.onPlayBackStopped = Mock()
            mon._post_event_heartbeat = Mock()
            mon._status = xprogress.PlayState.PLAYING
            mon.REPORT_PERIOD = 0.003
            mon.monitor_progress()
            mon.onPlayBackStopped.assert_called_once()
            mon._post_event_heartbeat.assert_called_once()
            self.assertEqual(5, mon.getTime.call_count)     # broke the loop because getTime raised RuntimeError

        # Exception while posting events
        with patch('xbmc.Monitor.waitForAbort', new=lambda a, b: time.sleep(0.001)):
            mon = xprogress.PlayTimeMonitor('')
            mon.getTime = Mock(side_effect=(1, 2, 3, 4, RuntimeError))
            mon.onPlayBackStopped = Mock()
            mon._post_event_heartbeat = Mock(side_effect=IOError)
            mon._status = xprogress.PlayState.PLAYING
            mon.REPORT_PERIOD = 0.003
            self.assertRaises(IOError, mon.monitor_progress)


    def test_initialise(self):
        # Request with normal response
        with patch('resources.lib.fetch.web_request', return_value=HttpResponse(content=b'ok')) as p_fetch:
            mon = xprogress.PlayTimeMonitor('')
            mon.initialise()
            p_fetch.assert_called_once()
            self.assertTrue('post' in p_fetch.call_args.args)
            self.assertIsInstance(p_fetch.call_args.kwargs['data'], dict)
            self.assertIs(mon._status, xprogress.PlayState.UNDEFINED)

        # Abnormal response from ITV
        with patch('resources.lib.fetch.web_request', return_value=HttpResponse(content=b'not vailable')) as p_fetch:
            mon = xprogress.PlayTimeMonitor('')
            mon.initialise()
            p_fetch.assert_called_once()
            self.assertIs(mon._status, xprogress.PlayState.STOPPED)

    def test_event_posting(self):
        mon = xprogress.PlayTimeMonitor('')
        mon._handle_event = p_hndl_evt = Mock()
        mon._post_event_startup_complete()
        p_hndl_evt.assert_called_once()
        self.assertTrue('startUpComplete' in p_hndl_evt.call_args.args)

        p_hndl_evt.reset_mock()
        mon._post_event_heartbeat()
        p_hndl_evt.assert_called_once()
        self.assertTrue('heartbeat' in p_hndl_evt.call_args.args)

        p_hndl_evt.reset_mock()
        mon._post_event_seek(23.15)
        p_hndl_evt.assert_called_once()
        self.assertTrue('seek' in p_hndl_evt.call_args.args)

        with patch('resources.lib.fetch.web_request') as p_fetch:
            mon._post_event_stop()
            p_fetch.assert_called_once()
            self.assertTrue('post' in p_fetch.call_args.args)

    def test_handle_event(self):
        # posting event is successful
        with patch('resources.lib.fetch.web_request', return_value=HttpResponse(content=b'ok')) as p_fetch:
            mon = xprogress.PlayTimeMonitor('')
            mon._status = xprogress.PlayState.PLAYING
            mon._handle_event({}, 'heartbeat')
            p_fetch.assert_called_once()
            self.assertIs(mon._status, xprogress.PlayState.PLAYING)

        # posting event keeps failing
        with patch('resources.lib.fetch.web_request', return_value=HttpResponse(content=b'not allowed')):
            mon = xprogress.PlayTimeMonitor('')
            mon._status = xprogress.PlayState.PLAYING
            mon._handle_event({}, 'heartbeat')
            self.assertIs(mon._status, xprogress.PlayState.PLAYING)
            mon._handle_event({}, 'heartbeat')
            self.assertIs(mon._status, xprogress.PlayState.PLAYING)
            mon._handle_event({}, 'heartbeat')
            self.assertIs(mon._status, xprogress.PlayState.PLAYING)
            mon._handle_event({}, 'heartbeat')
            self.assertIs(mon._status, xprogress.PlayState.STOPPED)

        # posting event fails, but recovers
        with patch('resources.lib.fetch.web_request', side_effect=itertools.chain(
                itertools.repeat(HttpResponse(content=b'not allowed'), 3),
                itertools.repeat(HttpResponse(content=b'ok')))) as p_fetch:
            mon = xprogress.PlayTimeMonitor('')
            mon._status = xprogress.PlayState.PLAYING
            for _ in range(8):
                mon._handle_event({}, 'heartbeat')
                self.assertIs(mon._status, xprogress.PlayState.PLAYING)
            self.assertEqual(8, p_fetch.call_count)


class TestFuncPLayTimeMonitor(TestCase):
    @patch('resources.lib.fetch.web_request', return_value=HttpResponse(content=b'not allowed'))
    @patch('resources.lib.xprogress.PlayTimeMonitor.monitor_progress')
    @patch('resources.lib.xprogress.PlayTimeMonitor.wait_until_playing')
    def test_playtime_monitor(self, p_wait, p_mon_progress, p_fetch):
        xprogress.playtime_monitor('sdgsd')
        p_wait.assert_called_once()
        p_mon_progress.assert_called_once()
        p_fetch.assert_called_once()       # only initialisation

    @patch('resources.lib.fetch.web_request', side_effect=errors.AuthenticationError)
    def test_playtime_monitor_exits_silently_on_error(self, p_fetch):
        xprogress.playtime_monitor('sdgsd')
        p_fetch.assert_called_once()



