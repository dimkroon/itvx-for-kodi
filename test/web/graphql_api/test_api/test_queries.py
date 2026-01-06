# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2026 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------
"""
Module to test whether the queries currently in use by the add-on are still the
same as those used by itv apps.

Current queries are stored in files like test_docs/gql/queries_pages.json
This particular file contains all known queries of type page.

To test the latest queries, a new file must be created by queries obtained from
the web. The filename must be the same as the current with '_new' appended to the
name.

If tests fail and the add-on has been adjusted to accommodate for the changes, the
current file should be replaced by the new file. As such defining the current query
as used by the add-on.

"""
import re
import time

from test.support import fixtures
fixtures.global_setup()

from unittest import TestCase

from resources.lib.itv_gql import _gql_query
from support.testutils import open_json, save_doc


def pretty_gql(gql_string: str, quote_lines=True, merge_fields=0) -> str:
    """Pretty print a graphql document.

    Parse `gql_string` and return a new pretty formatted string with proper
    indentation. Intended to create a nicely readable documents from queries
    obtained from web requests.

    If `quote_lines` is True, the text on each line is quoted, not including
    the indentations. A text as used can be used in the addon where python's
    implied line continuation will turn it into a single line of valid graphql.

    """
    parts = ['']
    TAB = ' ' * 4
    indent = 0

    # Regular expression to match GraphQL components
    regex = (r'(?P<BEGIN>\{)|'
             r'(?P<END>\})|'
             r'(?P<operation>query|mutation|subscription|fragment)|'
             r'(?P<fragment_spread>\.\.\.\w+)|'
             r'(?P<inline_fragment>\.\.\.)|'
             r'(?P<type_condition> on \w+)|'
             r'(?P<field_with_params>\w+\(.*?\))|'
             r'(?P<include>@include\([^)]+\))|'
             r'(?P<field>\w+)')

    def append_to_last(text):
        parts[-1] = ' '.join((parts[-1], text))

    def new_line(text):
        if quote_lines:
            parts.append("'".join((TAB * indent, text)))
        else:
            parts.append(TAB * indent + text)

    add_to_current = False

    for match in re.finditer(regex, gql_string):
        data = match.groupdict()
        if data['BEGIN']:
            append_to_last("{")
            indent += 1
        elif data['END']:
            indent -= 1
            new_line("}")

        elif data['type_condition']:
            # This match already includes a leading space. So, do not use append_to_last()
            parts[-1] += data['type_condition']

        elif data['fragment_spread']:
            new_line(data['fragment_spread'])

        elif data['inline_fragment']:
            new_line(data['inline_fragment'])

        elif data['field_with_params']:
            if add_to_current:
                append_to_last(data['field_with_params'])
            else:
                new_line(data['field_with_params'])

        elif data['field']:
            if add_to_current:
                append_to_last(data['field'])
            else:
                new_line(data['field'])

        elif data['include']:
            append_to_last(data['include'])

        if data['operation']:
            indent = 0
            parts.append(data['operation'])
            add_to_current = True
        else:
            add_to_current = False

    if merge_fields:
        start_pos = 0
        end_pos = 0

        def find_start(start_idx):
            for idx in range(start_idx, len(parts)):
                if parts[idx].endswith('{'):
                    return idx
            return None

        def find_end(start_idx):
            for idx in range(start_idx +1, len(parts)):
                part = parts[idx]
                if part.endswith('{'):
                    return None
                if part.endswith('}'):
                    return idx
            return None

        def merge(start, end):
            to_be_merged = (p.lstrip("' ") for p in parts[start + 1:end + 1])
            parts[start] = ' '.join((parts[start], *to_be_merged))
            del parts[start + 1:end + 1]
            return start + 1

        while start_pos < len(parts):
            start_pos = find_start(start_pos)
            if not start_pos:
                break
            end_pos = find_end(start_pos)
            if end_pos:
                num_fields = end_pos - start_pos - 1
                if num_fields <= merge_fields:
                    start_pos = merge(start_pos, end_pos)
                else:
                    start_pos = end_pos + 1
            else:
                start_pos += 1

    if quote_lines:
        for i in range(len(parts)):
            parts[i]  += " '"
    # Print the formatted query
    pretty_str = ('\n'.join(parts))
    return pretty_str


class CheckPageRequests(TestCase):
    def test_new_page_queries(self):
        """Check that the queries of all categories are the same."""
        query_data = open_json('gql/queries_cat_news.json')
        gql_query = query_data['FACTUAL']['query']
        for query in query_data.values():
            self.assertEqual(query['query'], gql_query)

    def test_new_page_variables(self):
        """Check that the queries of all categories are the same."""
        query_data = open_json('gql/queries_pages_new.json')

        def dict_equal(d1, d2, path):
            for k, v in d1.items():
                if k in ('category', 'id', 'tiers'):
                    continue
                self.assertTrue(k in d2, f"Key {path}/{k} not present.")
                v2 = d2[k]
                self.assertIsInstance(d2[k], type(v), f"Value of {path}/{k} not a {type(v)}, but {type(v2)}.")
                if isinstance(v, dict):
                    dict_equal(v, v2, f"{path}/{k}")
                else:
                    self.assertEqual(v, v2, f"Value of {path}/{k} not equal\n\texpected {v}, got {v2}.")

        gql_vars = query_data['FACTUAL']['variables']
        for key, query in query_data.items():
            if key in ('FACTUAL', ):
                continue
            dict_equal(gql_vars, query['variables'], f'{key}/variables')

    def test_pretty_print(self):
        query_data = open_json('gql/queries_pages_new.json')
        qd = query_data['FACTUAL']
        try:
            save_doc(pretty_gql(qd['query'], quote_lines=True, merge_fields=2),
                     'gql/page_query.txt')
        except Exception as err:
            pass
        return

    def test_compare_old_new_category_queries(self):
        """Compare the new query with the current."""
        cur_query_data = open_json('gql/queries_pages.json')
        new_query_data = open_json('gql/queries_pages_new.json')
        self.assertEqual(cur_query_data['FACTUAL']['query'], new_query_data['FACTUAL']['query'])


class RunQueries(TestCase):
    """Class to run several stored queries"""
    def test_run_categorie_page(self):
        queries = open_json('gql/queries_pages.json')
        for cat in ('DRAMA_AND_SOAPS', 'COMEDY'):
            cat_page_query = queries.get(cat)
            ts = time.monotonic()
            data = _gql_query(cat_page_query['query'], cat_page_query['variables'])
            tt = time.monotonic() - ts
            self.assertIsInstance(data, dict)
            self.assertIsInstance(data['data']['pages'], list)
            self.assertEqual(len(data['data']['pages']), 1)