# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2023 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch, mock_open

import json
import requests
from requests.cookies import RequestsCookieJar

from resources.lib import fetch
from resources.lib import errors
from resources.lib import utils

from test.support.testutils import HttpResponse
from test.support.object_checks import has_keys


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests

URL = 'https://mydoc'
STD_HEADERS = ['User-Agent', 'Referer', 'Origin', 'Sec-Fetch-Dest', 'Sec-Fetch-Mode',
               'Sec-Fetch-Site', 'Cache-Control', 'Pragma']


class TestPersistentCookieJar(TestCase):
    def test_persistent_jar(self):
        jar = fetch.PersistentCookieJar('my/fle')

    def test_save(self):
        jar = fetch.PersistentCookieJar('my/file')
        with patch('builtins.open', mock_open()) as m:
            jar.save()
            m.assert_not_called()
            jar._has_changed = True
            jar.save()
            m.assert_called_once()

    def test_set_cookie(self):
        jar = fetch.PersistentCookieJar('my/file')
        self.assertIs(jar._has_changed, False)
        cookie = MagicMock()
        cookie.name='hdntl'
        jar.set_cookie(cookie)
        self.assertIs(jar._has_changed, False)
        jar.set_cookie(MagicMock())
        self.assertIs(jar._has_changed, True)

    def test_clear(self):
        jar = fetch.PersistentCookieJar('my/file')
        cookie = MagicMock()
        cookie.domain = 'itv.com'
        jar.set_cookie(cookie)
        jar._has_changed = False
        jar.clear(domain='bbc.com')
        self.assertIs(jar._has_changed, False)
        jar.clear(domain='itv.com')
        self.assertIs(jar._has_changed, True)


class TestHttpSession(TestCase):
    @patch('resources.lib.fetch._create_cookiejar')
    def test_http_session_is_singleton(self, p_create):
        fetch.HttpSession.instance = None   # remove a possible existing instance
        s = fetch.HttpSession()
        ss = fetch.HttpSession()
        self.assertTrue(s is ss)

        s_id = id(s)
        del s
        del ss
        new_s = fetch.HttpSession()
        self.assertEqual(s_id, id(new_s))
        # The session's __init__() creates a cookiejar, assert that it has happend only once.
        p_create.assert_called_once()
        # Remove the created instance so subsequent (web) requests don't end up with a
        # session with a patched cookiejar.
        fetch.HttpSession.instance = None

    def test_http_session_non_existing_cookie_file(self):
        fetch.HttpSession.instance = None  # remove a possible existing instance
        with patch.object(utils.addon_info, 'profile', new='my/non/existing/path/'):
            s = fetch.HttpSession()
        jar = s.cookies
        self.assertIsInstance(jar, fetch.PersistentCookieJar)
        self.assertEqual('my/non/existing/path/cookies', jar.filename)


class SetDefaultCookies(TestCase):
    @patch('requests.Session.get', return_value=HttpResponse(content=b'{"CassieConsent": "{\\"my_cookie\\": \\"my_value\\"}"}'))
    def test_get_default_cookies(self, _):
        jar = RequestsCookieJar()
        resp = fetch.set_default_cookies(jar)
        self.assertIs(resp, jar)
        self.assertTrue('my_cookie' in jar)
        # without initial cookiejar, returns requests.Session's cookiejar
        resp = fetch.set_default_cookies()
        self.assertIsInstance(resp, RequestsCookieJar)
        self.assertTrue('my_cookie' in resp)

    def test_get_default_cookies_invalid_cookiejar(self):
        self.assertRaises(ValueError, fetch.set_default_cookies, {})

    @patch('requests.Session.get', side_effect=errors.HttpError)
    def test_unexpected_response(self, _):
        resp = fetch.set_default_cookies()
        self.assertIs(resp, None)


class WebRequest(TestCase):
    @patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=200))
    def test_web_request_get_plain(self, mocked_req):
        fetch.web_request('get', URL)
        mocked_req.assert_called_once()
        self.assertEqual(('get', URL), mocked_req.call_args[0][:2])
        has_keys(mocked_req.call_args[1], 'headers', 'json', 'timeout')
        # without data json must be None
        self.assertIsNone(mocked_req.call_args[1]['json'])

    @patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=200))
    # noinspection PyMethodMayBeStatic
    def test_web_request_adds_extra_headers(self, mocked_req):
        fetch.web_request('get', URL, headers={'NewHeader': 'newval'})
        has_keys(mocked_req.call_args[1], 'headers', 'json', 'timeout')
        has_keys(mocked_req.call_args[1]['headers'], 'NewHeader')

    @patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=200))
    def test_web_request_replaces_std_headers(self, mocked_req):
        """If a header passed to webrequest is the same a default header it should overwrite the default."""
        fetch.web_request('get', URL, headers={'Referer': 'mysite', 'NewHeader': 'newval'})
        has_keys(mocked_req.call_args[1], 'headers', 'json', 'timeout')
        has_keys(mocked_req.call_args[1]['headers'], 'NewHeader')
        self.assertEqual(mocked_req.call_args[1]['headers']['Referer'], 'mysite')

    @patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=200))
    def test_web_request_data_is_json(self, mocked_req):
        fetch.web_request('get', URL,  data=[1, 2, 3, 4])
        self.assertListEqual([1, 2, 3, 4], mocked_req.call_args[1]['json'])

    @patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=200))
    def test_web_request_extra_kwargs_are_passed_through(self, mocked_req):
        fetch.web_request('get', URL, proxies='some_value')
        self.assertEqual('some_value', mocked_req.call_args[1]['proxies'])

    def test_web_request_http_errors(self):
        with patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=400)):
            self.assertRaises(errors.HttpError, fetch.web_request, 'get', URL)

        with patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=401)):
            self.assertRaises(errors.AuthenticationError, fetch.web_request, 'get', URL)

        with patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=403)):
            self.assertRaises(errors.HttpError, fetch.web_request, 'get', URL)

        with patch('requests.sessions.Session.request', return_value=HttpResponse(
                status_code=403, text=json.dumps({'error': 'invalid_grant'}))):
            with self.assertRaises(errors.AuthenticationError) as cr:
                fetch.web_request('get', URL)
            self.assertEqual('Login failed', str(cr.exception))

        with patch('requests.sessions.Session.request', return_value=HttpResponse(
                status_code=403, text=json.dumps({'error': 'invalid_request'}))):
            with self.assertRaises(errors.AuthenticationError) as cr:
                fetch.web_request('get', URL)
            self.assertEqual('Login failed', str(cr.exception))

        with patch('requests.sessions.Session.request', return_value=HttpResponse(
                status_code=403, text=json.dumps({'Message': 'User does not have entitlements'}))):
            self.assertRaises(errors.AccessRestrictedError, fetch.web_request, 'get', URL)

        with patch('requests.sessions.Session.request', return_value=HttpResponse(
                status_code=403, text=json.dumps({'Message': 'Outside Of Allowed Geographic Region'}))):
            self.assertRaises(errors.GeoRestrictedError, fetch.web_request, 'get', URL)

        with patch('requests.sessions.Session.request', return_value=HttpResponse(status_code=500, reason='server error')):
            with self.assertRaises(errors.HttpError) as err:
                fetch.web_request('get', URL)
            self.assertEqual(500, err.exception.code)
            self.assertEqual('server error', err.exception.reason)

    @patch('requests.sessions.Session.request', side_effect=requests.RequestException)
    def test_web_request_other_request_errors(self, _):
        self.assertRaises(errors.FetchError, fetch.web_request, 'get', URL)


class PostJson(TestCase):
    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    def test_post_json_plain_with_response(self, mocked_req):
        resp = fetch.post_json(URL, {'x': 'y'})
        mocked_req.assert_called_once_with('POST', URL, {'Accept': 'application/json'}, {'x': 'y'})
        self.assertEqual({'a': 1}, resp)

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    # noinspection PyMethodMayBeStatic
    def test_post_json_adds_extra_headers(self, mocked_req):
        fetch.post_json(URL, {'x': 'y'}, {'MyHeader': 'myval'})
        has_keys(mocked_req.call_args[0][2], 'Accept', 'MyHeader')

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    def test_post_json_replaces_existing_header(self, mocked_req):
        fetch.post_json(URL, {'x': 'y'}, {'Accept': 'text/plain'})
        self.assertEqual('text/plain', mocked_req.call_args[0][2]['Accept'])

    def test_post_json_invalid_response(self):
        """Post_json expects a json response."""
        with patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'')):
            self.assertRaises(errors.FetchError, fetch.post_json, URL, {'x': 'y'})
        with patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'some text')):
            self.assertRaises(errors.FetchError, fetch.post_json, URL, {'x': 'y'})


class GetJson(TestCase):
    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    def test_get_json_plain_with_response(self, mocked_req):
        resp = fetch.get_json(URL)
        mocked_req.assert_called_once_with('GET', URL, {'Accept': 'application/json'})
        self.assertEqual({'a': 1}, resp)

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(status_code=204))
    def test_get_json_returns_no_content(self, mocked_req):
        resp = fetch.get_json(URL)
        mocked_req.assert_called_once_with('GET', URL, {'Accept': 'application/json'})
        self.assertIsNone(resp)

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    # noinspection PyMethodMayBeStatic
    def test_get_json_adds_extra_headers(self, mocked_req):
        fetch.get_json(URL, {'MyHeader': 'myval'})
        has_keys(mocked_req.call_args[0][2], 'Accept', 'MyHeader')

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    def test_get_json_replaces_existing_header(self, mocked_req):
        fetch.get_json(URL, {'Accept': 'text/plain'})
        self.assertEqual('text/plain', mocked_req.call_args[0][2]['Accept'])

    def test_get_json_invalid_response(self):
        """Get_json expects a json response."""
        with patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'')):
            self.assertRaises(errors.FetchError, fetch.get_json, URL)
        with patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'some text')):
            self.assertRaises(errors.FetchError, fetch.get_json, URL)


class PutJson(TestCase):
    """Put_json makes a put request and does not expect data back. The return value is the HTTP response"""
    @ patch("resources.lib.fetch.web_request", return_value=HttpResponse(status_code=200))
    def test_put_json_plain(self, mocked_req):
        resp = fetch.put_json(URL, {'a': 1})
        self.assertIsInstance(resp, requests.models.Response)
        mocked_req.assert_called_once_with('PUT', URL, None, {'a': 1})

    @ patch("resources.lib.fetch.web_request", return_value=HttpResponse(status_code=200))
    def test_put_json_adds_extra_headers(self, mocked_req):
        resp = fetch.put_json(URL, {'a': 1}, {'MyHeader': 'myval'})
        self.assertIsInstance(resp, requests.models.Response)
        mocked_req.assert_called_once_with('PUT', URL, {'MyHeader': 'myval'}, {'a': 1})

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'some content'))
    def test_put_json_returns_data(self, _):
        """Response content is totally ignored, but can be obtained from the response object."""
        resp = fetch.put_json(URL, {'a': 1})
        self.assertEqual('some content', resp.text)


class DeleteJson(TestCase):
    """Delete_json makes a delete request and may get data back. The return value is
    the as get_json; data as object when the response contained data, or None"""

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    def test_delete_json_plain_with_response(self, mocked_req):
        resp = fetch.delete_json(URL, {'id': 1})
        mocked_req.assert_called_once_with('DELETE', URL, {'Accept': 'application/json'}, {'id': 1})
        self.assertEqual({'a': 1}, resp)

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(status_code=204))
    def test_delete_json_returns_no_content(self, mocked_req):
        resp = fetch.delete_json(URL, {'id': 1})
        mocked_req.assert_called_once_with('DELETE', URL, {'Accept': 'application/json'}, {'id': 1})
        self.assertIsNone(resp)

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    # noinspection PyMethodMayBeStatic
    def test_delete_json_adds_extra_headers(self, mocked_req):
        fetch.delete_json(URL, {'id': 1}, headers={'MyHeader': 'myval'})
        has_keys(mocked_req.call_args[0][2], 'Accept', 'MyHeader')

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'{"a": 1}'))
    def test_delete_json_replaces_existing_header(self, mocked_req):
        fetch.delete_json(URL, {'id': 1}, headers={'Accept': 'text/plain'})
        self.assertEqual('text/plain', mocked_req.call_args[0][2]['Accept'])

    def test_delete_json_invalid_response(self):
        """delete_json() expects a json response."""
        with patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'')):
            self.assertRaises(errors.FetchError, fetch.delete_json, URL, {'id': 1})
        with patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'some text')):
            self.assertRaises(errors.FetchError, fetch.delete_json, URL, {'id': 1})


class GetDocument(TestCase):
    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'blabla'))
    def test_document_plain_with_response(self, mocked_req):
        resp = fetch.get_document(URL)
        mocked_req.assert_called_once_with('GET', URL, None)
        self.assertEqual('blabla', resp)

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(content=b'blabla'))
    def test_get_document_adds_extra_headers(self, mocked_req):
        fetch.get_document(URL, {'MyHeader': 'myval'})
        has_keys(mocked_req.call_args[0][2], 'MyHeader')

    @patch("resources.lib.fetch.web_request", return_value=HttpResponse(status_code=204, content=b''))
    def test_get_document_no_response(self, _):
        resp = fetch.get_document(URL)
        self.assertEqual('', resp)
