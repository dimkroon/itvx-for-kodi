# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------

from __future__ import annotations

from test.support import fixtures
fixtures.global_setup()


from unittest import TestCase
from unittest.mock import patch

from resources.lib import itv_gql
from support.testutils import open_json, open_doc, HttpResponse
from support.object_checks import is_url


@patch('resources.lib.fetch.get_json')
class GqlGetQuery(TestCase):
    def test_query_only(self, p_get_json):
        itv_gql._gql_query('this is a query')
        call_kwargs = p_get_json.call_args.kwargs
        self.assertEqual(call_kwargs, {'params': {'query': 'this is a query'}})

    def test_query_with_variables(self, p_get_json):
        itv_gql._gql_query('this is a query', variables={'ccid': 'abc123'})
        call_kwargs = p_get_json.call_args.kwargs
        self.assertEqual(call_kwargs, {'params': {'query': 'this is a query',
                                                  'variables': {'ccid': 'abc123'}}
                                       })

    def test_query_with_variables_and_operation(self, p_get_json):
        itv_gql._gql_query('this is a query', variables={'ccid': 'abc123'}, operation_name='op_name')
        call_kwargs = p_get_json.call_args.kwargs
        self.assertEqual(call_kwargs, {'params': {'query': 'this is a query',
                                                  'variables': {'ccid': 'abc123'},
                                                  'operationName': 'op_name'}
                                       })

@patch('resources.lib.itv_gql.requests.post', return_value=HttpResponse(text='{}'))
class GqlPostQuery(TestCase):
    def test_query_only(self, p_post):
        itv_gql._gql_post('video-ulr', 'this is a query')
        call_kwargs = p_post.call_args.kwargs['json']
        self.assertEqual(call_kwargs, {'query': 'this is a query'})

    def test_query_with_variables(self, p_post):
        itv_gql._gql_post('video-ulr', 'this is a query', variables={'ccid': 'abc123'})
        call_kwargs = p_post.call_args.kwargs['json']
        self.assertEqual(call_kwargs, {'query': 'this is a query',
                                       'variables': {'ccid': 'abc123'}})


class VodPlayList(TestCase):
    @patch('resources.lib.fetch.get_json', return_value=open_json('gql/vod-by-ccid.json'))
    def test_get_vod_playlist_url(self, _):
        vod_url, has_ad = itv_gql.get_playlist_url('asdfg')
        self.assertTrue(is_url(vod_url))
        bsl_url, has_ad = itv_gql.get_playlist_url('asdfg', prefer_bsl=True)
        self.assertTrue(is_url(bsl_url))
        self.assertNotEqual(vod_url, bsl_url)

    def test_vod_playlist_url_with_multiple_titles(self):
        """If by any change multiple titles are returned by gql, only the first
        should be taken.

        """
        json_data = open_json('gql/vod-by-ccid.json')
        json_data['data']['titles'].append({
            "title": "Dummy title",
            "latestAvailableVersion": {
                "playlistUrl": "dummy_playlist",    # intentionally not a valid url; will fail tests.
            }
        })
        with patch('resources.lib.fetch.get_json', return_value=json_data):
            vod_url, has_ad = itv_gql.get_playlist_url('asdfg')
            self.assertTrue(is_url(vod_url))


class GetShortPlaylistUrl(TestCase):
    @patch('resources.lib.itv_gql.requests.post',
           return_value=HttpResponse(text=open_doc('gql/news-clip-by-ccid.json')()))
    def test_get_news_playlist_url(self, _):
        playlist_url = itv_gql.get_short_playlist_url('dfg')
        self.assertTrue(is_url(playlist_url))

    @patch('resources.lib.itv_gql.requests.post',
           return_value=HttpResponse(text=open_doc('gql/sports-clip-by-ccid.json')()))
    def test_get_sport_playlist_url(self, _):
        playlist_url = itv_gql.get_short_playlist_url('zdfga', is_sport=True)
        self.assertTrue(is_url(playlist_url))
