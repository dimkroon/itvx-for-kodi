# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
from test.support import fixtures
fixtures.global_setup()

import pytz
import unittest

from datetime import datetime, timezone, timedelta
from copy import deepcopy

from support.testutils import open_doc, open_json
from support.object_checks import has_keys, is_li_compatible_dict
from resources.lib import parsex
from resources.lib import errors
from resources.lib import main


setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests


class TestScrapeJson(unittest.TestCase):
    def test_scrape_json_watch_pages(self):
        for page in ('html/index.html', 'html/watch-itv1.html'):
            get_page = open_doc(page)
            data = parsex.scrape_json(get_page())
            self.assertIsInstance(data, dict)

    def test_invalid_page(self):
        # no __NEXT_DATA___
        self.assertRaises(errors.ParseError, parsex.scrape_json, '<html></html')
        # invalid json
        self.assertRaises(errors.ParseError, parsex.scrape_json,
                          '<script id="__NEXT_DATA__" type="application/json">{data=[1,2]}</script>')


class Generic(unittest.TestCase):
    def test_build_url(self):
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921', url)
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921', None)
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921', url)
        url = parsex.build_url('Astrid and Lily Save the World', '10a2921', '10a2921a0001')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921/10a2921a0001', url)
        url = parsex.build_url('Astrid & Lily Save the World', '10a2921', '10a2921a0001')
        self.assertEqual('https://www.itv.com/watch/astrid-and-lily-save-the-world/10a2921/10a2921a0001', url)
        url = parsex.build_url('#50/50-heroes?', '10a1511')
        self.assertEqual('https://www.itv.com/watch/5050-heroes/10a1511', url)
        url = parsex.build_url('Paul Sinha: Shout Out To My Ex', '10a3819')
        self.assertEqual('https://www.itv.com/watch/paul-sinha-shout-out-to-my-ex/10a3819', url)
        url = parsex.build_url("Watch Thursday's ITV Evening News", '10a3819')
        self.assertEqual('https://www.itv.com/watch/watch-thursdays-itv-evening-news/10a3819', url)

    def test_sort_title(self):
        self.assertEqual('my title', parsex.sort_title('My Title'))
        self.assertEqual('title', parsex.sort_title('The Title'))
        self.assertEqual('thetitle', parsex.sort_title('TheTitle'))

    def test_parse_hero(self):
        data = open_json('html/index-data.json')
        for item_data in data['heroContent']:
            obj = parsex.parse_hero_content(item_data)
            has_keys(obj, 'type', 'show')
            self.assertTrue(obj['type'] in main.callb_map.keys())
            is_li_compatible_dict(self, obj['show'])
        # An item of unknown type
        item = data['heroContent'][0]
        item['contentType'] = 'some new type'
        self.assertIsNone(parsex.parse_hero_content(item))
        # Invalid item
        item = {'contentType': 'special', 'title': False}
        self.assertIsNone(parsex.parse_hero_content(item))

    def test_parse_main_page_short_form_slider(self):
        data = open_json('html/index-data.json')
        for slider in data['shortFormSliderContent']:
            obj = parsex.parse_short_form_slider(slider)
            has_keys(obj, 'type', 'show')
            is_li_compatible_dict(self, obj['show'])
            self.assertTrue('slider' in obj['show']['params'])
        # Return None on parse errors
        self.assertIsNone(parsex.parse_short_form_slider([]))
        # Return None when a 'view all items' link to collection page is absent from the header
        self.assertIsNone(parsex.parse_short_form_slider({'header': {}}))

    def test_parse_collection_short_form_slider(self):
        data = open_json('json/test_collection.json')
        obj = parsex.parse_short_form_slider(data['shortFormSlider'], url='https://mypage')
        has_keys(obj, 'type', 'show')
        is_li_compatible_dict(self, obj['show'])
        self.assertEqual('shortFormSlider', obj['show']['params']['slider'])

    def test_parse_editorial_slider_items(self):
        # Sliders on the main page
        data = open_json('json/index-data.json')
        for item_data in data['editorialSliders'].values():
            obj = parsex.parse_editorial_slider('https://www.itv.com', item_data)
            has_keys(obj, 'type', 'show')
            is_li_compatible_dict(self, obj['show'])
        # Sliders on a collection page
        slider_list = open_json('json/test_collection.json')['editorialSliders']
        for i in range(2):
            obj = parsex.parse_editorial_slider('https://www.itv.com', slider_list[i])
            has_keys(obj, 'type', 'show')
            is_li_compatible_dict(self, obj['show'])
        # A Slider without shows - should return None
        obj = parsex.parse_editorial_slider('https://www.itv.com', slider_list[-1])
        self.assertIsNone(obj)
        # Return None on parse errors
        self.assertIsNone(parsex.parse_editorial_slider('', ''))

    def test_parse_collection_title(self):
        data = open_json('json/test_collection.json')['editorialSliders'][0]['collection']['shows']
        # film
        item = parsex.parse_collection_item(data[6])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertEqual('film', item['type'])
        # series
        item = parsex.parse_collection_item(data[2])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertEqual('series', item['type'])
        # episode
        item = parsex.parse_collection_item(data[3])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertEqual('episode', item['type'])
        # Brand
        item = parsex.parse_collection_item(data[4])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertEqual('brand', item['type'])
        # fastchannelspot
        item = parsex.parse_collection_item(data[1])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertEqual('fastchannelspot', item['type'])
        # simulcastspot
        item = parsex.parse_collection_item(data[0])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertEqual('simulcastspot', item['type'])
        # page
        item = parsex.parse_collection_item(data[7])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])
        self.assertEqual('collection', item['type'])
        # An invalid item
        item = parsex.parse_collection_item({})
        self.assertIsNone(item)

    def test_parse_collection_title_from_main_page(self):
        data = open_json('html/index-data.json')['editorialSliders']['editorialRailSlot1']['collection']['shows']
        item = parsex.parse_collection_item(data[0])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])

    def test_parse_shortform_item(self):
        tz_uk = pytz.timezone('Europe/London')

        # ShortForm from collection
        data = open_json('json/test_collection.json')
        sf_item = data['shortFormSlider']['items'][0]
        obj = parsex.parse_shortform_item(sf_item, tz_uk, "%H-%M-%S")
        self.assertEqual('title', obj['type'])
        is_li_compatible_dict(self, obj['show'])

        # an item like a normal catchup episode
        item = parsex.parse_shortform_item(data['shortFormSlider']['items'][0], tz_uk, "%H-%M-%S")
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])

        # shortForm news item from the main page
        data = open_json('html/index-data.json')['shortFormSliderContent'][0]['items']
        item = parsex.parse_shortform_item(data[1], tz_uk, "%H-%M-%S")
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])

        # An invalid item
        item = parsex.parse_shortform_item({}, None, None)
        self.assertIsNone(item)

    def test_parse_trending_collection_item(self):
        data = open_json('html/index-data.json')['trendingSliderContent']['items']
        item = parsex.parse_trending_collection_item(data[1])
        has_keys(item, 'type', 'show')
        is_li_compatible_dict(self, item['show'])
        # An invalid item
        item = parsex.parse_trending_collection_item({})
        self.assertIsNone(item)

    def test_parse_episode_title(self):
        title_obj = open_json('json/episodes.json')[0]['episode']
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)

        # Episodes where field episodeTitle = None
        title_obj = open_json('json/episodes.json')[1]['episode']
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)

        # Paid episode
        title_obj = open_json('json/episodes.json')[2]['episode']
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)
        self.assertTrue('premium' in item['info']['plot'].lower())

        # Episode where field seriesNumber is not a number, but 'other episodes'.
        title_obj = open_json('json/episodes.json')[3]['episode']
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)

        # An Episode lacking field 'guidance'.
        title_obj = open_json('json/episodes.json')[4]['episode']
        item = parsex.parse_episode_title(title_obj)
        is_li_compatible_dict(self, item)

    def test_parse_search_result(self):
        # These files contain programmes, episodes, films and specials both and without a specialProgramm field.
        for file in ('search/search_results_mear.json', 'search/search_monday.json'):
            data = open_json(file)
            for result_item in data['results']:
                item = parsex.parse_search_result(result_item)
                has_keys(item, 'type', 'show')
                is_li_compatible_dict(self, item['show'])

        # unknown entity type
        search_result = data['results'][0]
        search_result['entityType'] = 'dfgs'
        self.assertIsNone(parsex.parse_search_result(search_result))

    def test_parse_mylist(self):
        data = open_json('mylist/mylist_data.json')['items']
        for mylist_item in data:
            item = parsex.parse_my_list_item(mylist_item)
            has_keys(item, 'type', 'show')
            is_li_compatible_dict(self, item['show'])

    def test_parse_last_watched(self):
        data = open_json('usercontent/last_watched_all.json')
        utc_now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        for item in data:
            show = parsex.parse_last_watched_item(item, utc_now)
            has_keys(show, 'type', 'show')
            self.assertEqual('vodstream', show['type'])
            is_li_compatible_dict(self, show['show'])

    def test_parse_last_watched_availability(self):
        data = open_json('usercontent/last_watched_all.json')[0]
        utc_now = datetime.now(tz=timezone.utc).replace(tzinfo=None)

        some_years = (datetime.utcnow() + timedelta(days=370)).replace(microsecond=0)
        data['availabilityEnd'] = some_years.isoformat() + 'Z'
        item = parsex.parse_last_watched_item(data, utc_now)
        self.assertTrue('over a year' in item['show']['info']['plot'])

        some_months = (datetime.utcnow() + timedelta(days=62)).replace(microsecond=0)
        data['availabilityEnd'] = some_months.isoformat() + 'Z'
        item = parsex.parse_last_watched_item(data, utc_now)
        self.assertTrue('2 months' in item['show']['info']['plot'])

        one_months = (datetime.utcnow() + timedelta(days=32)).replace(microsecond=0)
        data['availabilityEnd'] = one_months.isoformat() + 'Z'
        item = parsex.parse_last_watched_item(data, utc_now)
        self.assertTrue('1 month' in item['show']['info']['plot'])

        some_days = (datetime.utcnow() + timedelta(days=4, minutes=1)).replace(microsecond=0)
        data['availabilityEnd'] = some_days.isoformat() + 'Z'
        item = parsex.parse_last_watched_item(data, utc_now)
        self.assertTrue('4 days available' in item['show']['info']['plot'])

        one_day = (datetime.utcnow() + timedelta(days=1, minutes=1)).replace(microsecond=0)
        data['availabilityEnd'] = one_day.isoformat() + 'Z'
        item = parsex.parse_last_watched_item(data, utc_now)
        self.assertTrue('1 day available' in item['show']['info']['plot'])

        some_hours = (datetime.utcnow() + timedelta(hours=4, minutes=1)).replace(microsecond=0)
        data['availabilityEnd'] = some_hours.isoformat() + 'Z'
        item = parsex.parse_last_watched_item(data, utc_now)
        self.assertTrue('4 hours available' in item['show']['info']['plot'])

        one_hours = (datetime.utcnow() + timedelta(hours=1, minutes=1)).replace(microsecond=0)
        data['availabilityEnd'] = one_hours.isoformat() + 'Z'
        item = parsex.parse_last_watched_item(data, utc_now)
        self.assertTrue('1 hour available' in item['show']['info']['plot'])

        zero_hours = (datetime.utcnow() + timedelta(minutes=1)).replace(microsecond=0)
        data['availabilityEnd'] = zero_hours.isoformat() + 'Z'
        item = parsex.parse_last_watched_item(data, utc_now)
        self.assertTrue('0 hours available' in item['show']['info']['plot'])

    def test_parse_schedule(self):
        data = open_json('json/schedule_data.json')['tvGuideData']

        # episodeNr present, but seriesNr is None
        item = parsex.parse_schedule_item(data['ITV'][0])
        self.assertEqual('S00E41', item['episode'])
        # Both episodeNr and seriesNr present
        item = parsex.parse_schedule_item(data['ITV'][1])
        self.assertEqual('S07E10', item['episode'])
        # Both episodeNr and seriesNr absent
        item = parsex.parse_schedule_item(data['ITV'][2])
        self.assertTrue('episode' not in item.keys())

        # Formatting direct episode url
        item = parsex.parse_schedule_item(data['ITV'][1])
        self.assertTrue(item['stream'].startswith("plugin://plugin.video.viwx/resources/lib"))
        self.assertTrue(item['stream'].endswith(data['ITV'][1]['episodeLink'][-4:]))

        # Check all test items
        for chan_data in data.values():
            for item in chan_data:
                self.assertIsNotNone(parsex.parse_schedule_item(item))

        # Invalid data
        self.assertIsNone(parsex.parse_schedule_item({}))

    def test_parse_viewall(self):
        slider_data = {
            'header': {
                'linkHref': '/watch/collections/some_collection.html',
                'linkText': "My Test Link"
            }
        }
        item = parsex.parse_view_all(deepcopy(slider_data))
        self.assertEqual('collection', item['type'])
        self.assertTrue('url' in item['show']['params'])
        self.assertEqual('My Test Link', item['show']['label'])

        data = deepcopy(slider_data)
        data['header']['linkHref'] = '/watch/categories/some_category.html'
        item = parsex.parse_view_all(deepcopy(data))
        self.assertEqual('category', item['type'])
        self.assertTrue('path' in item['show']['params'])
        self.assertEqual('My Test Link', item['show']['label'])

        # Invalid and non-existing links
        data = deepcopy(slider_data)
        data['header']['linkHref'] = '/watch/some_programme.html'
        item = parsex.parse_view_all(deepcopy(data))
        self.assertIsNone(item)
        data['header']['linkHref'] = ''
        item = parsex.parse_view_all(deepcopy(data))
        self.assertIsNone(item)
        data['header']['linkHref'] = None
        item = parsex.parse_view_all(deepcopy(data))
        self.assertIsNone(item)
        del data['header']['linkHref']
        item = parsex.parse_view_all(deepcopy(data))
        self.assertIsNone(item)

        # Missing and empty linkText
        data = deepcopy(slider_data)
        data['header']['linkText'] = ''
        item = parsex.parse_view_all(deepcopy(data))
        self.assertEqual('View All', item['show']['label'])
        data['header']['linkText'] = None
        item = parsex.parse_view_all(deepcopy(data))
        self.assertEqual('View All', item['show']['label'])
        del data['header']['linkText']
        item = parsex.parse_view_all(deepcopy(data))
        self.assertEqual('View All', item['show']['label'])