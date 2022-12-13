
# ---------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  This file is part of plugin.video.itvx
# ---------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

from test.support.testutils import HttpResponse
from test.support.object_checks import has_keys

from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests

from resources.lib import fetch
from resources.lib import errors


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests

URL = 'https://mydoc'
STD_HEADERS = ['User-Agent', 'Referer', 'Origin', 'Sec-Fetch-Dest', 'Sec-Fetch-Mode',
               'Sec-Fetch-Site', 'Cache-Control', 'Pragma']


class HttpSession(TestCase):
    @patch('resources.lib.fetch._create_cookiejar')
    def test_http_session_is_singleton(self, p_create):
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


class AccountMock:
    access_token = '123abc'

    def __init__(self):
        self.refresh = MagicMock()
        self.login = MagicMock()


# class GetAuthenticated(TestCase):
#     @patch("resources.lib.ctree.ct_account.session", return_value=AccountMock())
#     @patch("resources.lib.fetch.get_json", return_value={'a': 1})
#     def test_authenticated_get(self, mocked_get, _):
#         resp = fetch.fetch_authenticated(fetch.get_json, URL)
#         self.assertEqual({'a': 1}, resp)
#         mocked_get.assert_called_once_with(URL, headers={'Authorization': 'Bearer ' + AccountMock.access_token})
#         mocked_get.reset_mock()
#         # check authorization is added to headers passed in.
#         fetch.fetch_authenticated(fetch.get_json, URL, headers={'MyHeader': 'myval'})
#         mocked_get.assert_called_once_with(URL, headers={'MyHeader': 'myval', 'Authorization': 'Bearer ' + AccountMock.access_token})
#
#     @patch("resources.lib.ctree.ct_account.session", return_value=AccountMock())
#     @patch("resources.lib.fetch.get_json", side_effect=[errors.AuthenticationError, {'a': 1}])
#     def test_authenticated_meets_auth_error_response(self, mocked_get, mocked_account):
#         """Refresh tokens on authentication error and try again"""
#         resp = fetch.fetch_authenticated(fetch.get_json, URL)
#         mocked_account.return_value.refresh.assert_called_once()
#         mocked_account.return_value.login.assert_not_called()
#         self.assertEqual(2, mocked_get.call_count)
#         self.assertEqual({'a': 1}, resp)
#
#     @patch("resources.lib.ctree.ct_account.session", return_value=AccountMock())
#     @patch('requests.request', return_value=HttpResponse(status_code=401, content=b'{"status":401,"message":"User has no subscription"}'))
#     def test_authenticated_meets_auth_error_no_subscription(self, mocked_get, mocked_account):
#         """Caused by trying to play a film from the monthly subscription while logged in
#         with a rental only account.
#         Should raise a AccessRestrictedError without attempts to refresh or login.
#         """
#         self.assertRaises(errors.AccessRestrictedError, fetch.fetch_authenticated, fetch.get_json, URL)
#         mocked_account.return_value.refresh.assert_not_called()
#         mocked_account.return_value.login.assert_not_called()
#         self.assertEqual(1, mocked_get.call_count)
#
#     @patch("resources.lib.ctree.ct_account.session", return_value=AccountMock())
#     @patch('requests.request', return_value=HttpResponse(status_code=401, content=b'{"status":401,"message":"User has no transaction"}'))
#     def test_authenticated_meets_auth_error_no_transaction(self, mocked_get, mocked_account):
#         """Caused by trying to play a rental film without having paid for it.
#         Should raise a AccessRestrictedError without attempts to refresh or login.
#         """
#         self.assertRaises(errors.AccessRestrictedError, fetch.fetch_authenticated, fetch.get_json, URL)
#         mocked_account.return_value.refresh.assert_not_called()
#         mocked_account.return_value.login.assert_not_called()
#         self.assertEqual(1, mocked_get.call_count)
#
#     @patch("resources.lib.ctree.ct_account.session", return_value=AccountMock())
#     @patch("resources.lib.fetch.get_json", side_effect=[errors.AuthenticationError, {'a': 1}])
#     def test_authenticated_refresh_fails_login_succeeds(self, mocked_get, mocked_account):
#         """Refresh tokens on authentication error and try again"""
#         mocked_account.return_value.refresh.return_value = False
#
#         resp = fetch.fetch_authenticated(fetch.get_json, URL)
#         mocked_account.return_value.refresh.assert_called_once()
#         mocked_account.return_value.login.assert_called_once()
#         self.assertEqual(2, mocked_get.call_count)
#         self.assertEqual({'a': 1}, resp)
#
#     @patch("resources.lib.ctree.ct_account.session", return_value=AccountMock())
#     @patch("resources.lib.fetch.get_json", side_effect=[errors.AuthenticationError, {'a': 1}])
#     def test_authenticated_refresh_fails_login_rejectd(self, mocked_get, mocked_account):
#         """Refresh tokens failed and the user canceled the request to log in."""
#         mocked_account.return_value.refresh.return_value = False
#         with patch("resources.lib.kodi_utils.show_msg_not_logged_in", return_value=False):
#             self.assertRaises(errors.AuthenticationError, fetch.fetch_authenticated, fetch.get_json, URL)
#         mocked_account.return_value.refresh.assert_called_once()
#         mocked_account.return_value.login.assert_not_called()
#         self.assertEqual(1, mocked_get.call_count)
#
#     @patch("resources.lib.ctree.ct_account.session", return_value=AccountMock())
#     @patch("resources.lib.fetch.get_json", side_effect=[errors.AuthenticationError, {'a': 1}])
#     def test_authenticated_login_fails(self, mocked_get, mocked_account):
#         """If refresh and login fail, do not try again"""
#         mocked_account.return_value.refresh.return_value = False
#         mocked_account.return_value.login.side_effect = errors.AuthenticationError
#
#         self.assertRaises(errors.AuthenticationError, fetch.fetch_authenticated, fetch.get_json, URL)
#         mocked_account.return_value.refresh.assert_called_once()
#         mocked_account.return_value.login.assert_called_once()
#         mocked_get.assert_called_once()
#
#     @patch("resources.lib.ctree.ct_account.session", return_value=AccountMock())
#     @patch("resources.lib.fetch.get_json", side_effect=errors.AuthenticationError)
#     def test_authenticated_not_authenticated_even_after_successful_refresh(self, mocked_get, mocked_account):
#         self.assertRaises(errors.AccessRestrictedError, fetch.fetch_authenticated, fetch.get_json, URL)
#         mocked_account.return_value.refresh.assert_called_once()
#         self.assertEqual(2, mocked_get.call_count)
