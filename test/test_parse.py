from __future__ import unicode_literals
import unittest

from resources.lib import parse


class ParseShowsHtml(unittest.TestCase):
    def test_parse_shows_page(self):
        """read html from file and feed it to the parser"""
        with open("http responses/shows.html", 'r') as f:
            html_page = f.read()

        result = parse.parse_shows(html_page)
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)


class ParseEpisodes(unittest.TestCase):
    def parse_test_base(self, html_page):
        result = parse.parse_episodes(html_page)
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)

    def test_parse_episodes_page(self):
        """read html from file and feed it to the parser"""
        with open("http responses/episodes-2a7942.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)

    def test_parse_episodes_page_2_invalid_page(self):
        """Parse a page that has no episode data. This a HTTP 400 error"""
        with open("http responses/episodes-ainslys food we love-10a0472.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)

    def test_parse_episodes_page_3(self):
        """Parse a page with only 1 serie"""
        with open("http responses/episodes_australia_wirh_julia_bradbury-2a5896.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)

    def test_parse_episodes_page_4_manhunt(self):
        """Parse a page with 2 series, one with 4 and another with 4 episodes"""
        with open("http responses/episodes_manhunt_2a5386.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)

    def test_parse_episodes_page_5_poirot(self):
        """Parse a page with a lot of series, each with several episodes"""
        with open("http responses/episodes_poirot_L0830.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)

    def test_parse_episodes_page_6_wrestling(self):
        """Parse a page with no series, but several episodes"""
        with open("http responses/episodes_all-elite-wrestling-dynamite_2a7855.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)

    def test_parse_episodes_page_6_midsummer_murders(self):
        """Parse a page with no series, but serveral episodes"""
        with open("http responses/episodes_midsummer-murders_Ya1096.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)


class TestParseSubmenu(unittest.TestCase):
    def parse_test_base(self, html_page):
        result = parse.parse_submenu(html_page)
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)

    def test_parse_submenu_full_shows(self):
        with open("http responses/full-series.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)

    def test_parse_submenu_categories(self):
        with open("http responses/categories.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)


class ParseFullSeries(unittest.TestCase):
    def parse_test_base(self, html_page):
        result = parse.parse_full_series(html_page)
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)

    def test_parse_full_series_drama(self):
        with open("http responses/full-series_drama.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)


class ParseCategory(unittest.TestCase):
    def parse_test_base(self, html_page):
        result = parse.parse_category(html_page)
        result = list(result)
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)

    def test_parse_category_comedy(self):
        with open("http responses/category_comedy.html", 'r') as f:
            html_page = f.read()
        self.parse_test_base(html_page)
