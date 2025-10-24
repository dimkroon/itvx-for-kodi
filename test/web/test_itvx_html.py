
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import os
import time
import unittest
import requests
from datetime import datetime, timedelta, timezone

from resources.lib import fetch, parsex, main, itv_account, errors
from support.object_checks import (
    has_keys,
    expect_keys,
    misses_keys,
    expect_misses_keys,
    is_url,
    is_iso_utc_time,
    is_tier_info,
    is_not_empty,
    is_encoded_programme_id,
    is_encoded_episode_id,
    check_short_form_slider,
    check_short_form_item,
    check_category_item,
    check_genres
)
from support import testutils

setUpModule = fixtures.setup_web_test

NONE_T = type(None)
now_dt = datetime.now()
now_str = now_dt.strftime('%Y-%m-%d %H:%M')

# A list of all pages that have been checked. Prevents loops and checking the same page
# over again when it appears in multiple collections.
checked_urls = []


# A list of already saved types of collection items.
# Used to save one item of each type, to be used in test documents.
saved_col_item_types = set(os.path.splitext(fname)[0] for fname in os.listdir(testutils.doc_path('col_items')))
saved_hero_item_types = set(os.path.splitext(fname)[0] for fname in os.listdir(testutils.doc_path('hero_items')))

def save_item(item, source):
    """Save one of the variations of each collection item type."""

    cfg = {
        'collection': {'base_folder': 'col_items/', 'saved': saved_col_item_types},
        'hero': {'base_folder': 'hero_items/', 'saved': saved_hero_item_types}
    }[source]

    content_type = item.get('contentType')
    if content_type in ('simulcastspot', 'fastchannelspot'):
        if item['startDateTime'] is None:
            content_type = content_type + '_none'
        else:
            content_type = content_type + '_date'
    if content_type in ('brand', 'series', 'episode', 'special', 'film'):
        if item.get('isPaid'):
            content_type = content_type + '_paid'
        else:
            content_type = content_type + '_free'

    if content_type not in cfg['saved']:
        cfg['saved'].add(content_type)
        save_item = {'Dev_Comment': ' '.join((content_type.replace('_', ' - ').title(), now_str))}
        save_item.update(item)
        fname = os.path.join(cfg['base_folder'], content_type + '.json')
        testutils.save_json(save_item, fname)


def check_editorial_slider(testcase, slider_data, parent_name):
    """Check an editorial slider from the main page, or a (sub) collection page

    Some sliders have a 'view all' link to another (sub) collection page.
    Others do not and the content in `['collections']['shows']` is all they have.
    This is primarily found in collections that are already sub-collections, in
    particular in collections of type `page`.

    Returns either a tuple of (url, parent_name), where url is a link to the page with
    the full collection, or None, when all available shows are in the slider.

    """
    collection_data = slider_data['collection']
    has_keys(collection_data, 'headingTitle', 'sliderName')
    obj_name = parent_name + '.' + collection_data['headingTitle']
    if 'shows' in collection_data:
        testcase.assertTrue(is_not_empty(collection_data['shows'], list))
        testcase.assertTrue(is_not_empty(collection_data['itemCount'], int))
    else:
        # Item is invalid. Has been observed in a sub-collection of a sub-collection.
        # These items did have a headingLink, but that link was invalid.
        # The entry was also not shown on the website.
        testcase.assertFalse('itemCount' in collection_data)
        print('NOTICE: No shows in Slider ' + obj_name)
        return None
    href = collection_data.get('headingLink')
    if href:
        page_ref = 'https://www.itv.com/watch' + href
        return page_ref, obj_name
    else:
        for show in collection_data['shows']:
            check_shows(testcase, show, obj_name)
        return None


def check_shows(testcase, show, parent_name):
    """Check an item of a collection page or in a rail on the main page."""
    testcase.assertTrue(show.get('contentType') in
                        ('series', 'brand', 'film', 'special', 'episode', 'collection', 'fastchannelspot',
                        'simulcastspot', 'page', None),
                        "{}: Unexpected title type '{}'.".format('.'.join((parent_name, show['title'])),
                                                                 show.get('contentType', '')))
    content_type = show.get('contentType')
    if content_type is None:
        # This type is not actually a show
        return True

    save_item(show, 'collection')

    if content_type == 'collection':
        return check_rail_item_type_collection(testcase, show, parent_name)
    if content_type == 'fastchannelspot':
        return check_collection_item_type_fastchannelspot(testcase, show, parent_name)
    if content_type == 'simulcastspot':
        return check_item_type_simulcastspot(testcase, show, parent_name)
    if content_type == 'page':
        return check_item_type_page(testcase, show, parent_name)
    if content_type == 'brand':
        return check_item_type_brand(testcase, show, parent_name)
    # Not always present: 'contentInfo'
    has_keys(show, 'contentType', 'title', 'description', 'titleSlug', 'imageTemplate',
             'encodedProgrammeId', obj_name='{}-show-{}'.format(parent_name, show['title']))
    if content_type in ('series', 'episode', 'film', 'special'):
        has_keys(show, 'encodedEpisodeId', obj_name='{}-show-{}'.format(parent_name, show['title']))
    else:
        raise AssertionError("A non-playable should already have been checked by it's dedicated checker.")
    testcase.assertTrue(is_url(show['imageTemplate']))


def check_programme(self, progr_data):
    """Formerly known as 'Brand'"""
    obj_name = progr_data['title']
    has_keys(progr_data, 'title', 'image', 'longDescription', 'description',
             'encodedProgrammeId', 'titleSlug', 'tier', 'visuallySigned',
             obj_name=obj_name)
    expect_keys(progr_data, 'programmeId')
    misses_keys(progr_data, 'categories')
    # Only programme details pages (like episodes, specials, films) still have this field.
    # Its presence is specifically checked in their tests.
    expect_misses_keys(progr_data, 'imagePresets')
    self.assertTrue(is_encoded_programme_id(progr_data['encodedProgrammeId']))
    self.assertTrue(is_not_empty(progr_data['title'], str))
    self.assertTrue(is_not_empty(progr_data['longDescription'], str))
    self.assertTrue(is_not_empty(progr_data['description'], str))
    self.assertTrue(is_url(progr_data['image']))
    self.assertTrue(is_not_empty(progr_data['genres'], list))
    has_keys(progr_data['genres'][0], 'id', 'name')
    self.assertTrue(is_not_empty(progr_data['titleSlug'], str))
    self.assertTrue(is_tier_info(progr_data['tier']))
    if 'numberOfAvailableSeries' in progr_data:
        self.assertTrue(is_not_empty(progr_data['numberOfAvailableSeries'], int))


def check_series(self, series, parent_name):
    obj_name = '{}-{}'.format(parent_name, series['seriesLabel'])
    has_keys(series, 'seriesLabel', 'seriesNumber', 'numberOfAvailableEpisodes', 'titles',
             obj_name=obj_name)
    expect_keys(series, 'seriesType', 'legacyId', 'fullSeries', 'seriesType', 'longRunning')
    self.assertTrue(is_not_empty(series['seriesNumber'], str))
    self.assertTrue(is_not_empty(series['seriesLabel'], str))
    # A programme can have single episodes not belonging to a series, like the Christmas special.
    # These are of type 'EPISODE'.
    self.assertTrue(series.get('seriesType') in ('SERIES', 'FILM', 'EPISODE', None))
    self.assertTrue(is_not_empty(series['numberOfAvailableEpisodes'], int))
    for episode in series['titles']:
        check_title(self, episode, obj_name)


def check_title(self, title, parent_name):
    obj_name = '{}-title-{}'.format(parent_name, title['episodeTitle'])
    has_keys(title, 'accessibilityTags', 'audioDescribed', 'availabilityFrom', 'availabilityUntil', 'broadcastDateTime',
             'genres', 'contentInfo', 'dateTime', 'description',
             'duration', 'encodedEpisodeId', 'episodeTitle', 'genres', 'guidance', 'image', 'longDescription',
             'notFormattedDuration', 'playlistUrl', 'productionType', 'premium', 'tier', 'series', 'visuallySigned',
             'subtitled', 'audioDescribed', 'heroCtaLabel',
             obj_name=obj_name)

    expect_keys(title, 'availabilityFeatures', 'ccid', 'channel', 'episodeId',
                'fullSeriesRange', 'linearContent', 'longRunning', 'partnership',
                'productionId', 'programmeId', 'subtitled', 'visuallySigned', 'regionalisation', obj_name=obj_name)

    self.assertIsInstance(title['accessibilityTags'], list)
    self.assertIsInstance(title['audioDescribed'], bool)
    self.assertTrue(is_iso_utc_time(title['availabilityFrom']))
    self.assertTrue(is_iso_utc_time(title['availabilityUntil']))
    self.assertTrue(is_iso_utc_time(title['broadcastDateTime']) or title['broadcastDateTime'] is None)
    self.assertTrue(is_not_empty(title['genres'], list))
    has_keys(title['genres'][0], 'id', 'name')
    self.assertIsInstance(title['contentInfo'], str)        # can be empty in films, specials, or episodes in sections like 'latest episodes'.
    self.assertTrue(is_iso_utc_time(title['dateTime']) or title['dateTime'] is None)
    self.assertTrue(is_not_empty(title['description'], str))
    self.assertTrue(is_not_empty(title['duration'], str) or title['duration'] is None)
    if title['duration'] is not None:
        self.assertFalse(title['duration'].startswith('P'))  # duration is not in iso format
    if title['notFormattedDuration'] is None:
        self.assertIsNone(title['duration'])
    else:
        self.assertTrue(title['notFormattedDuration'].startswith('PT'))
    self.assertTrue(is_encoded_episode_id(title['encodedEpisodeId']))
    self.assertTrue(is_not_empty(title['episodeTitle'], str) or title['episodeTitle'] is None)
    check_genres(self, title['genres'])
    self.assertTrue(is_not_empty(title['longDescription'], str))
    self.assertTrue(is_url(title['image']))
    self.assertTrue(is_url(title['playlistUrl']))
    self.assertIsInstance(title['premium'], bool)
    self.assertTrue(title['productionType'] in ('EPISODE', 'FILM', 'SPECIAL'))
    self.assertIsInstance(title['subtitled'], bool)
    if title['premium']:
        self.assertListEqual(['PAID'], title['tier'])
    else:
        self.assertListEqual(['FREE'], title['tier'])
    if title['visuallySigned']:
        self.assertTrue(is_url(title['bslPlaylistUrl']))

    if title['productionType'] == 'EPISODE':
        # Field 'nextProductionId' is only present when there actually is a next episode.
        # The very lat episode does not have this field, as well as episodes in listings
        # like 'other' and 'latest'
        expect_keys(title, 'isFullSeries', 'nextProductionId', obj_name=obj_name)
        self.assertTrue(is_not_empty(title['episode'], int))
        # Some episodes do not belong to a series, like the Christmas special
        self.assertTrue(is_not_empty(title['series'], int) or title['series'] is None)
        # We use this a a fallback when title is None, but even this can be an empty string
        self.assertTrue(isinstance(title['heroCtaLabel']['episodeLabel'], str))
        self.assertTrue(is_not_empty(title['heroCtaLabel']['label'], str))

    if title['productionType'] == 'SPECIAL':
        self.assertIsNone(title['episode'])
        self.assertEqual('others', title['series'])
        self.assertGreater(title['productionYear'], 1900)
        # Specials have been observed with a title['dataTime'] of 1-1-1970, but also real dates occur.

    if title['productionType'] in ('EPISODE', 'FILM', 'SPECIAL'):
        pass

    if title['productionType'] == 'FILM':
        self.assertGreater(title['productionYear'], 1900)
        self.assertIsNone(title['episode'])
        self.assertIsNone(title['series'])


def check_episode(self, episode, parent_name):
    obj_name = '{}-{}'.format(parent_name, episode['episodeTitle'])
    check_title(self, episode, parent_name)
    has_keys(episode, 'daysLeft', 'seriesNumber', 'episodeNumber', 'href', 'programmeTitle', obj_name=obj_name)


def check_rail_item_type_collection(testcase, item, parent_name):
    """Check items of type collection found on heroContent and editorialSliders."""
    item_name = '{}.{}'.format(parent_name, item.get('title', 'unknown'))
    has_keys(item, 'contentType', 'title', 'titleSlug', 'collectionId', 'imageTemplate',
             obj_name=item_name)
    misses_keys(item, 'imagePresets', 'channel', obj_name=item_name)
    testcase.assertIsInstance(item['description'], (str, type(None)))
    testcase.assertTrue(is_url(item['imageTemplate']))
    testcase.assertTrue(is_not_empty(item['title'], str))
    testcase.assertTrue(is_not_empty(item['titleSlug'], str))
    testcase.assertTrue(is_not_empty(item['collectionId'], str))


def check_item_type_page(testcase, item, parent_name):
    """Check items of type page.
    Items of type page have been found in heroContent on the main page and as a
    show in a collection. In the latter, page items are disregarded, so this
    function currently only checks hero items.

    Page items are very similar to items of type collection. The only difference
    is the use of field 'pageId' instead of 'collectionId'.
    Furthermore, the urls of page appear to require a querystring to return without error.

    """
    item_name = '{}.{}'.format(parent_name, item.get('title', 'unknown'))
    has_keys(item, 'contentType', 'title', 'titleSlug', 'pageId', 'imageTemplate',
             obj_name=item_name)
    # ctalable and arialabel seem to be specific to Hero items
    expect_keys(item, 'ctaLabel', 'ariaLabel',
                obj_name=item_name)
    misses_keys(item, 'imagePresets', obj_name=item_name)
    testcase.assertTrue(is_url(item['imageTemplate']))
    testcase.assertTrue(is_not_empty(item['title'], str))
    testcase.assertTrue(is_not_empty(item['titleSlug'], str))
    testcase.assertTrue(is_not_empty(item['pageId'], str))
    if 'ariaLabel' in item:
        testcase.assertTrue(is_not_empty(item['ariaLabel'], str))
        testcase.assertTrue(is_not_empty(item['ctaLabel'], str))
    # Currently items of type page require a querystring added to the url
    # The only instance of a page item found so far, referred to the collection 'funny-favourites'
    # and returned HTTP error 404 unless query string ?ind was added to the url.

    url = 'https://www.itv.com/watch/collections/' + item['titleSlug'] + '/' + item['pageId']
    headers = {
        # Without these headers the requests will time out.
        'user-agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/110.0',
        'Origin': 'https: /www.itv.com',
    }
    # Check url without query string fails
    # Since june 2025 requests without query time out, instead of returning not found.
    testcase.assertRaises(requests.Timeout, requests.get, url, headers=headers, timeout=3)
    # testcase.assertEqual(404, resp.status_code)
    # Check the contents of the collection page with querystring added to url
    CollectionPages.check_page(testcase, url + '?ind', parent_name)


def check_collection_item_type_fastchannelspot(self, item, parent_name):
    name = '{}.{}'.format(parent_name, item.get('title', 'unknown'))
    has_keys(item, 'contentType', 'title', 'channel', 'description', 'imageTemplate',
             'startDateTime', 'endDateTime', 'progress',
             obj_name=name)
    expect_keys(item, 'contentInfo', 'tagNames', obj_name=name)
    # Keys available in simulcastspot, but not found in fastchannelspots. Flag any changes
    misses_keys(item, 'genre', obj_name=name)
    # Items assumed to be no longer present
    misses_keys(item, 'imagePresets', obj_name=name)
    self.assertTrue(is_url(item['imageTemplate']))
    self.assertTrue(is_not_empty(item['title'], str))
    self.assertTrue(is_not_empty(item['channel'], str))


def check_mylist_item(testcase, item, parent_name):
    obj_name = '.'.join((parent_name, item['programmeTitle']))
    has_keys(item, 'categories', 'contentType', 'contentOwner', 'dateAdded', 'duration',
             'imageLink', 'itvxImageLink', 'longRunning', 'numberOfAvailableSeries',
             'numberOfEpisodes', 'partnership', 'programmeId', 'programmeTitle', 'synopsis',
             'tier', obj_name=obj_name)
    testcase.assertTrue(item['contentType'].lower() in main.callb_map.keys())
    testcase.assertIsInstance(item['numberOfAvailableSeries'], list)
    testcase.assertIsInstance(item['numberOfEpisodes'], (int, type(None)))
    testcase.assertTrue(item['tier'] in ('FREE', 'PAID'))
    testcase.assertTrue(is_iso_utc_time(item['dateAdded']))
    testcase.assertTrue(is_url(item['itvxImageLink']))
    testcase.assertTrue(is_not_empty(item['programmeId'], str))
    testcase.assertFalse(is_encoded_programme_id(item['programmeId']))  # Programme ID in My List is NOT encoded.


def check_item_type_simulcastspot(self, item, parent_name):
    """Simulcastspots are very similar to fastchannelspots, but have a few additional fields.

    """
    name = '{}.{}'.format(parent_name, item.get('title', 'unknown'))
    has_keys(item, 'contentType', 'title', 'channel', 'description', 'imageTemplate',
             'genre', 'startDateTime', 'endDateTime',
             obj_name=name)
    expect_keys(item, 'contentInfo', 'tagName' 'ctaLabel', 'ariaLabel', obj_name=name)
    misses_keys(item, 'imagePresets', obj_name=name)
    self.assertTrue(is_url(item['imageTemplate']))
    self.assertTrue(is_not_empty(item['title'], str))
    self.assertTrue(is_not_empty(item['channel'], str))
    self.assertTrue(is_url(item['imageTemplate']))
    # Generic check on start and end time. Items from hero use a different format than those from collection.
    # Hero and collection will each perform additional checks on the format.
    # TODO: Review
    #       Noticed one simulcastspot from a collection where both values are None, but
    #       is there still any value in testing it like this?
    self.assertTrue(is_not_empty(item['startDateTime'], str) or item['startDateTime'] is None)
    self.assertTrue(is_not_empty(item['endDateTime'], str) or item['endDateTime'] is None)
    # We see a move to ID based genres at ITVX, but this has still the old single value genre
    # Just to detect a change
    self.assertTrue(is_not_empty(item['genre'], str))


def check_item_type_brand(testcase, item, parent_name):
    name = '{}.{}'.format(parent_name, item.get('title', 'unknown'))
    has_keys(item, 'title', 'contentType', 'titleSlug', 'description', 'genres', 'dateTime', 'imageTemplate',
             'numberOfAvailableSeries', 'series', 'programmeId', 'encodedProgrammeId', 'contentInfo', 'isPaid',
             obj_name=name)
    expect_keys(item, 'partnership', 'contentOwner', 'channel', 'ccid', obj_name=name)
    misses_keys(item, 'categories')
    testcase.assertTrue(is_not_empty(item['title'], str))
    testcase.assertTrue(is_not_empty(item['titleSlug'], str))
    testcase.assertTrue(is_not_empty(item['description'], str))
    check_genres(testcase, item['genres'], name)
    testcase.assertTrue(item['dateTime'] is None or is_iso_utc_time(item['dateTime']))
    testcase.assertTrue(is_url(item['imageTemplate']))
    testcase.assertTrue(is_not_empty(item['numberOfAvailableSeries'], int))
    testcase.assertTrue(is_encoded_programme_id(item['encodedProgrammeId']))
    testcase.assertIsInstance(item['isPaid'], bool)
    testcase.assertIsInstance(item['series'], list)
    for series in item['series']:
        # This data is not used by the parse. Series and episode data is obtained from the programme's page.
        expect_keys(series, 'numberOfEpisodes', 'numberOfAvailableEpisodes', 'fullSeries', 'legacyId', 'seriesNumber',
                    'longRunning', obj_name='{}.series-{}'.format(name, series['seriesNumber']))
        # Just flag when other keys are added.
        testcase.assertLessEqual(len(list(series.keys())), 6)


class MainPage(unittest.TestCase):
    def test_main_page(self):
        page = fetch.get_document('https://www.itv.com/')
        # testutils.save_doc(page, 'html/index.html')
        page_props = parsex.scrape_json(page)
        # testutils.save_json(page_props, 'html/index-data_new.json')
        has_keys(page_props, 'heroContent', 'editorialSliders', 'shortFormSliderContent', 'trendingSliderContent')

        self.assertIsInstance(page_props['heroContent'], list)
        for item in page_props['heroContent']:
            content_type = item['contentType']
            self.assertTrue(content_type in
                            ('simulcastspot', 'fastchannelspot', 'series', 'film', 'special', 'episode', 'brand',
                             'collection', 'page', 'upsellspot'))
            if content_type == 'upsellspot':
                continue
            save_item(item, 'hero')
            obj_name = 'Hero-items.' + item['title']
            if content_type == 'simulcastspot':
                check_item_type_simulcastspot(self, item, parent_name='hero-items')
                # Flag if key normally only present in collections become available in hero items as well
                misses_keys(item, 'contentinfo', 'progress', obj_name=obj_name)
                # Start and end times in Simulcastspots in hero are normally not in iso format.
                # Flag if this changes.
                self.assertFalse(is_iso_utc_time(item['startDateTime']))
                self.assertFalse(is_iso_utc_time(item['endDateTime']))
                # Basic check that start and end times are in HH:MM format in British local time
                self.assertTrue(t.isdecimal for t in item['startDateTime'].split(':'))
                self.assertTrue(t.isdecimal for t in item['endDateTime'].split(':'))
            #  TODO: Merge check with similar items from shortFormatSliders and collections
            # elif content_type == 'fastchannelspot':
            #     check_collection_item_type_fastchannelspot(self, item, parent_name='hero-item')
            elif content_type == 'collection':
                check_rail_item_type_collection(self, item, 'heroContent')
                # ariaLabel seems only present on heroContent, not on collection items in editorialSliders.
                has_keys(item, 'ariaLabel')
            elif content_type == 'page':
                check_item_type_page(self, item, 'mainpage.hero')
            else:
                has_keys(item, 'contentType', 'title', 'imageTemplate', 'description', 'ctaLabel', 'ariaLabel',
                         'contentInfo', obj_name=obj_name)
                self.assertIsInstance(item['contentInfo'], list)

                if item['contentType'] in ('simulcastspot', 'fastchannelspot'):
                    has_keys(item, 'channel', obj_name=obj_name)
                else:
                    has_keys(item, 'genres', 'encodedProgrammeId', 'programmeId', obj_name=obj_name)
                    self.assertTrue(is_encoded_programme_id(item['encodedProgrammeId']))
                    check_genres(self, item['genres'])

                if item['contentType'] == 'special':
                    # Field 'dateTime' not always present in special title
                    has_keys(item, 'encodedEpisodeId', 'duration', obj_name=obj_name)
                    self.assertTrue(is_encoded_episode_id(item['encodedEpisodeId']))

                if item['contentType'] == 'episode':
                    self.assertTrue(is_encoded_episode_id(item['encodedEpisodeId']))
                    misses_keys(item, 'duration', obj_name=obj_name)

                if item['contentType'] == 'series':
                    has_keys(item, 'encodedEpisodeId', 'brandImageTemplate', 'series', obj_name=obj_name)
                    self.assertTrue(is_encoded_episode_id(item['encodedEpisodeId']))

                if item['contentType'] == 'film':
                    # Fields not always present:  'dateTime'
                    has_keys(item, 'productionYear', 'duration', obj_name=obj_name)

                if item['contentType'] == 'brand':
                    # Just to check over time if this is always true
                    self.assertTrue(any(inf.startswith('Series') for inf in item['contentInfo']))

        self.assertIsInstance(page_props['editorialSliders'], dict)
        for item in page_props['editorialSliders'].values():
            collection = item['collection']
            if collection.get('headingLink'):
                # These collections have their own page and their data on the main page is not used.
                continue
            # , 'imageTreatment', 'imageAspectRatio', 'imageClass'
            has_keys(collection, 'headingTitle', 'shows',
                     obj_name='collection-' + collection['headingTitle'])
            for show in collection['shows']:
                check_shows(self, show, 'MainPage.ES[' + collection['headingTitle'] + ']')

        self.assertIsInstance(page_props['trendingSliderContent'], dict)
        self.assertTrue(page_props['trendingSliderContent']['header']['title'])
        for item in page_props['trendingSliderContent']['items']:
            has_keys(item, 'title', 'imageUrl', 'description', 'encodedProgrammeId', 'contentType',
                     'contentInfo', 'titleSlug', obj_name='trending.' + item['title'])
            # Must have either an episode id when the underlying item is an episode, but there
            # is no way to check the item's type
            # has_keys(item, 'encodedEpisodeId', obj_name='trending-slider_' + item['title'])
            # Trending is probably always FREE, but it has no fields indicating whether it is.
            misses_keys(item, 'tier', 'isPaid', obj_name='trending.' + item['title'])

        self.assertIsInstance(page_props['shortFormSliderContent'], list)
        # Currently the list contains only the news rail and possibly a sport rail.
        self.assertTrue(len(page_props['shortFormSliderContent']) in (1, 2))
        for slider in page_props['shortFormSliderContent']:
            check_short_form_slider(self, slider, name='mainpage.shortform')
            header = slider['header']
            # ShortFromSlider on the main page should have a reference to a collection or category page.
            self.assertFalse(is_url(header['linkHref']))                # is a relative link
            self.assertTrue(header['linkHref'].startswith('/watch'))    # starts with '/watch', unlike editorialSliders

    def test_get_itvx_logo(self):
        resp = requests.get('https://app.10ft.itv.com/itvstatic/assets/images/brands/itvx/itvx-logo-for-light-'
                            'backgrounds.jpg?q=80&format=jpg&w=960&h=540&bg=false&blur=0')
        self.assertEqual(200, resp.status_code)
        img = resp.content
        # testutils.save_binary(img, 'html/itvx-logo-light-bg.jpg')
        resp = requests.get('https://app.10ft.itv.com/itvstatic/assets/images/brands/itvx/itvx-logo-for-dark-'
                            'backgrounds.jpg?q=80&format=jpg&w=960&bg=false&blur=0')
        self.assertEqual(200, resp.status_code)
        img = resp.content
        # testutils.save_binary(img, 'html/itvx-logo-dark-bg.jpg')


class CollectionPages(unittest.TestCase):
    @staticmethod
    def check_page(testcase, url, parent_name=''):
        """Check a collection page.

        """
        if url in checked_urls:
            return

        try:
            page_data = parsex.scrape_json(fetch.get_document(url))
        except errors.HttpError as err:
            if err.code == 404:
                # Happens sometimes; the 'show all' button on the website isn't working either.
                print(f"ERROR: Page '{url} not found!")
                return
            else:
                raise
        checked_urls.append(url)

        if parent_name:
            parent_name = parent_name + '.' + page_data['headingTitle'] + '.'
        else:
            parent_name = page_data['headingTitle'] + '.'

        # if 'ITVX Live' in page_data['headingTitle']:
        #     testutils.save_json(page_data, 'html/collection_itvx-fast.json')
        # elif 'Funny Favourites' in page_data['headingTitle']:
        #     testutils.save_json(page_data, 'html/collection_itvx-kids.json')
        # elif 'Fresh in' in page_data['headingTitle']:
        #     testutils.save_json(page_data, 'html/collection_just-in_data.json')

        has_keys(page_data, 'headingTitle', 'collection', 'editorialSliders',
                 'pageImageUrl', 'isAccessibleByKids', obj_name=parent_name[:-1])
        expect_keys(page_data, 'headingDescription', 'collectionSlug', obj_name=parent_name[:-1])
        misses_keys(page_data, 'shortFormSlider', obj_name=parent_name[:-1])
        collection = page_data['collection']
        editorial_sliders = page_data['editorialSliders']
        shortform_slider = page_data.get('shortFormSlider')

        if collection is not None:
            # As of May 2024 pageImageUrl is sometimes present on pages with non-empty collection
            # testcase.assertEqual(page_data['pageImageUrl'], '')
            testcase.assertIsNone(editorial_sliders)  # The parser ignores rails if collection has content!
            has_keys(collection, 'headingTitle', 'shows', obj_name=parent_name + collection['sliderName'])
            expect_keys(collection, 'isChildrenCollection', obj_name=parent_name + collection['sliderName'])
            for show in collection['shows']:
                check_shows(testcase, show, parent_name + collection['sliderName'])

        # Some collection have their content divided up in rails.
        if editorial_sliders is not None:
            # Page with rails has an image
            is_url(page_data['pageImageUrl'])

            for slider in editorial_sliders:
                collection_data = slider['collection']
                has_keys(collection_data, 'headingTitle', 'sliderName')
                obj_name = parent_name + collection_data['headingTitle']
                # Standard keys in sliders, but not used in the parser.
                expect_keys(slider, 'containerType', 'displayType', 'id', 'isChildrenCollection', obj_name=obj_name)

                if 'shows' in collection_data:
                    testcase.assertTrue(is_not_empty(collection_data['shows'], list))
                    testcase.assertTrue(is_not_empty(collection_data['itemCount'], int))
                else:
                    # Item is invalid. Has been observed in a sub-collection of a sub-collection.
                    # These items did have a headingLink, but that link was invalid.
                    # The entry was also not shown on the website.
                    testcase.assertFalse('itemCount' in collection_data)
                    print('NOTICE: No shows in Slider', obj_name, '!')
                    return
                heading_link = collection_data.get('headingLink')
                if heading_link:
                    # Yes, strip trailing white space. It has actually happened...
                    page_ref = 'https://www.itv.com/watch' + heading_link['href'].rstrip()
                    CollectionPages.check_page(testcase, page_ref, parent_name)
                else:
                    for show in collection_data['shows']:
                        check_shows(testcase, show, obj_name)

        if shortform_slider:
            # It looks like shortform sliders are no longer present on collection pages
            # Flag if one is found.
            raise AssertionError("shortFormSlider on collection page %s", parent_name)
            # check_short_form_slider(testcase, shortform_slider)

    def test_all_collections(self):
        """Obtain links to collection pages from the main page and test them all."""

        page_data = parsex.scrape_json(fetch.get_document('https://www.itv.com/'))
        editorial_sliders = page_data['editorialSliders']
        for rail in editorial_sliders.values():
            pagelink = rail['collection'].get('headingLink', {}).get('href')
            if not pagelink:
                continue
            self.check_page(self, 'https://www.itv.com/watch' + pagelink)

        for slider in page_data['shortFormSliderContent']:
            if slider['key'] == 'newsShortForm':
                # News is only used from the main page, or as category, not as collection
                continue
            # We consider a page link mandatory
            pagelink = slider['header']['linkHref']
            if pagelink.startswith('/watch/categories'):
                # Check it's a known category and leave additional checks to the categories tests.
                self.assertTrue(pagelink.rsplit('/', 1)[-1] in all_categories,
                                "Unknown category page '{}'.".format(pagelink))
                continue
            self.check_page(self, 'https://www.itv.com' + pagelink)


class WatchPages(unittest.TestCase):
    def check_schedule_now_next_slot(self, progr_data, chan_type, obj_name=None):
        """Check the now/next schedule data returned from an HTML page.
        It is very simular to the data returned by `nownext.oasvc.itv.com`, but not just quite the same.

        """
        all_keys = ('titleId', 'title', 'prodId', 'brandTitle', 'broadcastAt', 'guidance', 'rating',
                    'contentEntityType', 'episodeNumber', 'seriesNumber', 'startAgainPlaylistUrl', 'shortSynopsis',
                    'displayTitle', 'detailedDisplayTitle', 'timestamp',
                    'broadcastEndTimestamp', 'productionId')

        # As of 25-6-2023 all fields of the FAST channel 'Unwind' are either None or False. There
        # some fields missing as well, but there is no point in checking that.
        # From 10-2023 fields of 'citv' are also all None or False. Most likely to be removed in the future.
        if all(not progr_data.get(k) for k in all_keys):
            name = obj_name.lower()
            self.assertTrue(name.startswith('unwind') or
                            name.startswith('itv sport') or
                            name.startswith('space live 24/7 channel'))
            return

        has_keys(progr_data, *all_keys, obj_name=obj_name)
        # These times are in a format like '2022-11-22T20:00Z'
        self.assertTrue(is_iso_utc_time(progr_data['start']))
        self.assertTrue(is_iso_utc_time(progr_data['end']))

        if chan_type == 'fast':
            self.assertIsNone(progr_data['broadcastStartTimestamp'])
            self.assertIsNone(progr_data['broadcastAt'])
            self.assertIsNone(progr_data['broadcastEndTimestamp'])

        if chan_type != 'fast':
            has_keys(progr_data, 'broadcastStartTimestamp', obj_name=obj_name)
            self.assertTrue(is_iso_utc_time(progr_data['broadcastAt']))
            # check timestamps are integers
            self.assertGreater(int(progr_data['broadcastStartTimestamp']), 0)
            self.assertGreater(int(progr_data['broadcastEndTimestamp']), 0)
        self.assertTrue(progr_data['startAgainPlaylistUrl'] is None or is_url(progr_data['startAgainPlaylistUrl']))

    def check_schedule_channel_info(self, channel_info):
        has_keys(channel_info, 'id', 'name', 'slug', 'slots', 'images', 'playlistUrl')
        self.assertTrue(is_url(channel_info['images']['logo'], '.png'))
        self.assertTrue(is_url(channel_info['playlistUrl']))
        self.assertTrue(channel_info['channelType'] in ('fast', 'simulcast'))

    def test_watch_live_itv1(self):
        """The jsonp data primarily contains now/next schedule of all live channels"""
        page = fetch.get_document('https://www.itv.com/watch?channel=itv')
        data = parsex.scrape_json(page)

        # !!! Field channelsMetaData absent since 18-3-2023 !!!
        # channel_data = data['channelsMetaData']
        # # check presence and type of backdrop image
        # self.assertTrue(len(channel_data['images']), 1)     # only backdrop image is available
        # self.assertTrue(is_url(channel_data['images']['backdrop'], '.jpeg'))

        for chan in data['channels']:
            chan_type = chan['channelType']
            self.check_schedule_channel_info(chan)
            self.check_schedule_now_next_slot(chan['slots']['now'], chan_type,
                                              obj_name='{}-Now-on'.format(chan['name']))
            self.check_schedule_now_next_slot(chan['slots']['next'], chan_type,
                                              obj_name='{}-Next-on'.format(chan['name']))

    def test_series_page(self):
        for url in (
                'https://www.itv.com/watch/agatha-christies-marple/L1286',
                'https://www.itv.com/watch/bad-girls/7a0129',
                'https://www.itv.com/watch/midsomer-murders/Ya1096',
                'https://www.itv.com/watch/stonehouse/10a1973',         # programme with BSL
                'https://www.itv.com/watch/the-chase/1a7842/',          # Some episode do not have a title
                ):
            page = fetch.get_document(url)
            # testutils.save_doc(page, 'html/series_miss-marple.html')
            data = parsex.scrape_json(page)
            # testutils.save_json(data, 'html/series_stonehouse-bsl.json')
            programme_data = data['programme']
            check_programme(self, programme_data)
            for series in data['seriesList']:
                check_series(self, series, programme_data['title'])

    def test_premium_episode_page(self):
        url = 'https://www.itv.com/watch/downton-abbey/1a8697/1a8697a0001'
        page = fetch.get_document(url)
        # testutils.save_doc(page, 'html/paid_episode_downton-abbey-s1e1.html')
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/paid_episode_downton-abbey-s1e1.json')
        programme_data = data['programme']
        check_programme(self, programme_data)
        self.assertListEqual(['PAID'], programme_data['tier'])
        for series in data['seriesList']:
            check_series(self, series, programme_data['title'])
            for title in series['titles']:
                self.assertTrue(title['premium'])
        # Check episode - the data of the actual episode the page represents.
        check_title(self, data['episode'], programme_data['title'])

    def test_film_details_page(self):
        page = fetch.get_document('https://www.itv.com/watch/a-day-to-remember/CFD0170')
        # testutils.save_doc(page, 'html/film.html')
        data = parsex.scrape_json(page)
        check_programme(self, data['programme'])
        # Just to flag when imagePresets in no longer present, like most other data structures.
        self.assertTrue('imagePresets' in data['programme'])
        self.assertEqual(1, len(data['seriesList']))
        self.assertEqual(1, len(data['seriesList'][0]['titles']))
        check_series(self, data['seriesList'][0], data['programme']['title'])
        # Film pages do NOT have a field 'episode'
        self.assertTrue('episode' not in data.keys())

    def test_special_details_page(self):
        page = fetch.get_document('https://www.itv.com/watch/how-to-catch-a-cat-killer/10a1951')
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/special_how-to-catch-a-cat-killer_data.json')
        check_programme(self, data['programme'])
        # Just to flag when imagePresets is no longer present, like most other data structures.
        self.assertTrue('imagePresets' in data['programme'])
        self.assertEqual(1, len(data['seriesList']))
        self.assertEqual(1, len(data['seriesList'][0]['titles']))
        check_series(self, data['seriesList'][0], data['programme']['title'])

    def test_news_item_tonight(self):
        page = fetch.get_document('https://www.itv.com/watch/tonight-can-britain-get-talking/1a2803/1a2803a9382')
        # testutils.save_doc(page, 'html/news-tonight.html')
        data = parsex.scrape_json(page)
        check_programme(self, data['programme'])
        # Just to flag when imagePresets in no longer present, like most other data structures.
        self.assertTrue('imagePresets' in data['programme'])
        check_title(self, data['episode'], data['programme']['title'])

    def test_short_news_item(self):
        page = fetch.get_document('https://www.itv.com/watch/news/met-police-officers-investigated-'
                                  'for-gross-misconduct-over-stephen-port-case/fxmdtwy')
        # testutils.save_doc(page, 'html/news-short_item.html')
        data = parsex.scrape_json(page)
        self.assertFalse('programme' in data)
        self.assertTrue('episode' in data)
        # Episodes in short news is not completely conform title specs
        self.assertRaises(AssertionError, check_title, self, data['episode'], 'short-news')
        # Check is does have a field 'playlistUrl', so in can be used in main.play_title()
        self.assertTrue(is_url(data['episode']['playlistUrl']))


class TvGuide(unittest.TestCase):
    """TV guide from the html page of the website

    .. Note::
        The TV guide page is not GEO-blocked, but when accessed from outside the
        UK the schedule data is empty.

    """
    headers = {
        # Without these headers the requests will time out.
        'user-agent': fetch.USER_AGENT,
        'Origin': 'https: /www.itv.com',
    }

    def check_guide(self, data):
        obj_name = 'HTMLguide'
        has_keys(data, 'ITV1', 'ITV2', 'ITVBe', 'ITV3', 'ITV4', obj_name=obj_name)
        for chan_name, chan_guide in data.items():
            for item in chan_guide:
                o_name = '.'.join((obj_name, chan_name, item.get('title', 'Unknown')))
                has_keys(item, 'title', 'start', 'end', 'titleCCId', 'contentTypeITV', 'genres', 'seriesNumber',
                         'contentType', 'episodeAvailableNow', 'episodeLink', 'programmeLink', 'legacyId',
                         'duration', obj_name=o_name)
                self.assertTrue(is_not_empty(item['title'], str))
                self.assertTrue(is_not_empty(item['duration'], int))
                self.assertTrue(is_iso_utc_time(item['start']))
                self.assertTrue(is_iso_utc_time(item['end']))
                # Items like some news and weather do not have a titleCCId, but other live and recorded programmes do.
                self.assertTrue(is_not_empty(item['titleCCId'], str) or isinstance(item['titleCCId'], NONE_T))
                if item.get('contentType') is None:
                    # Some items, probably all live items do not have more info,
                    # but check that is indeed the case.
                    for key in ('contentTypeITV', 'seriesNumber', 'contentType', 'episodeAvailableNow',
                                'episodeLink', 'programmeLink', 'legacyId'):
                        self.assertIsNone(item[key])
                    self.assertEqual(13, len(item))
                    self.assertListEqual([], item['genres'])
                    continue
                misses_keys(item, 'episodeNumber', 'description', 'guidance', obj_name=o_name)
                self.assertTrue(item['contentType'] in ('EPISODE', 'FILM', 'SPECIAL'))
                check_genres(self, item['genres'])
                self.assertTrue(is_not_empty(item['legacyId'], str))
                self.assertIsInstance(item['seriesNumber'], (int, NONE_T))
                # Episode number without a series number does still happen...
                # if item['episodeNumber']:
                #     self.assertTrue(is_not_empty(item['seriesNumber'], int))
                # self.assertTrue(is_not_empty(item['description'], str) or item['description'] is None)
                # self.assertIsInstance(item['guidance'], (str, NONE_T))
                self.assertIsInstance(item['episodeAvailableNow'], bool)
                # Even if episodeAvialableNow is True fields like episodeLink can still be None
                if item['episodeLink'] is not None:
                    self.assertFalse(is_url(item['episodeLink']))
                    self.assertTrue(is_not_empty(item['episodeLink'], str))
                if item['programmeLink'] is not None:
                    self.assertFalse(is_url(item['programmeLink']))
                    self.assertTrue(is_not_empty(item['programmeLink'], str))
                self.assertEqual(13, len(item))     # Just to flag when more data becomes available.

    def test_html_guide_without_headers(self):
        """Requests without the minimum required headers time out"""
        self.assertRaises(requests.Timeout, requests.get, 'https://www.itv.com/watch/tv-guide/', timeout=3)

    def test_html_guide_of_today(self):
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        url = 'https://www.itv.com/watch/tv-guide/' + today
        query = {'position': 'end'}
        page = requests.get(url, headers=self.headers, timeout=3).text
        schedule_data = parsex.scrape_json(page)
        # testutils.save_json(schedule_data, 'schedule/html_schedule.json')
        self.check_guide(schedule_data['tvGuideData'])

    def test_html_guide_week_ago(self):
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        url = 'https://www.itv.com/watch/tv-guide/' + week_ago.strftime('%Y-%m-%d')
        page = requests.get(url, headers=self.headers, timeout=3).text
        data = parsex.scrape_json(page)
        # testutils.save_json(schedule_data, 'json/schedule_week_ago.json')
        self.check_guide(data['tvGuideData'])
        # Check that the schedules are indeed from a week ago
        first_prgrm = data['tvGuideData']['ITV1'][0]
        start_t = datetime.strptime(first_prgrm['start'], '%Y-%m-%dT%H:%M:%SZ')
        self.assertEqual(week_ago.date(), start_t.date())

    def test_html_guide_week_ahead(self):
        week_ahead = datetime.now(timezone.utc) + timedelta(days=7)
        url = 'https://www.itv.com/watch/tv-guide/' + week_ahead.strftime('%Y-%m-%d')
        page = requests.get(url, headers=self.headers, timeout=3).text
        data = parsex.scrape_json(page)
        # testutils.save_json(schedule_data, 'json/schedule_week_ahead.json')
        self.check_guide(data['tvGuideData'])
        # Check that the schedules are indeed from a week ahead
        first_prgrm = data['tvGuideData']['ITV1'][0]
        start_t = datetime.strptime(first_prgrm['start'], '%Y-%m-%dT%H:%M:%SZ')
        self.assertEqual(week_ahead.date(), start_t.date())

    def test_html_guide_8days_ago(self):
        """If more than 7 days ahead is requested, the schedules of today are returned."""
        today = datetime.now(timezone.utc)
        far_ahead = (today - timedelta(days=8)).strftime('%Y-%m-%d')
        url = 'https://www.itv.com/watch/tv-guide/' + far_ahead
        data = parsex.scrape_json(requests.get(url, headers=self.headers, timeout=3).text)
        first_prgrm = data['tvGuideData']['ITV1'][0]
        start_t = datetime.strptime(first_prgrm['start'], '%Y-%m-%dT%H:%M:%SZ')
        self.assertEqual(today.date(), start_t.date())

    def test_html_guide_8days_ahead(self):
        """If more than 7 days ahead is requested, the schedules of today are returned."""
        today = datetime.now(timezone.utc)
        far_ahead = (today + timedelta(days=8)).strftime('%Y-%m-%d')
        url = 'https://www.itv.com/watch/tv-guide/' + far_ahead
        data = parsex.scrape_json(requests.get(url, headers=self.headers, timeout=3).text)
        first_prgrm = data['tvGuideData']['ITV1'][0]
        start_t = datetime.strptime(first_prgrm['start'], '%Y-%m-%dT%H:%M:%SZ')
        self.assertEqual(today.date(), start_t.date())


all_categories = ['factual', 'drama-soaps', 'children', 'films', 'sport',
                  'comedy', 'news', 'entertainment', 'signed-bsl']


class Categories(unittest.TestCase):

    def test_get_available_categories(self):
        """The page categories returns in fact already a full categorie page - the first page in the list
        of categories. Which categorie that is, may change.
        Maybe because of that it is much slower than requesting categories by gql.
        """
        t_s = time.time()
        page = fetch.get_document('https://www.itv.com/watch/categories')
        t_1 = time.time()
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/categories_data.json')
        categories = data['subnav']['items']
        t_2 = time.time()
        for item in categories:
            has_keys(item, 'id', 'label', 'url')
            # url is the full path without domain
            self.assertTrue(item['url'].startswith('/watch/'))

        self.assertEqual(9, len(categories))        # the mobile app has an additional category AD (Audio Described)
        self.assertListEqual([cat['id'] for cat in categories], all_categories)
        # print('Categorie page fetched in {:0.3f}, parsed in {:0.3f}, total: {:0.3f}'.format(
        #     t_1 - t_s, t_2 - t_1, t_2 - t_s))

    def test_all_categories(self):
        for cat in all_categories:
            if cat == 'news':
                # As of May 2023 category news returns a different data structure and has its own test.
                continue
            url = 'https://www.itv.com/watch/categories/' + cat + '/all'
            t_s = time.time()
            page = fetch.get_document(url)
            t_1 = time.time()
            data = parsex.scrape_json(page)
            # if cat in ('children', 'drama-soaps', 'factual', 'films', 'sport'):
            #     testutils.save_json(data, 'html/category_{}.json'.format(cat))
            cat_data = data['category']
            self.assertTrue(is_not_empty(cat_data['slug'], str))
            self.assertTrue(cat_data['id'] in
                            # Yes, at this moment it's 'FILM' not 'FILMS', the parser accepts both.
                            # Also, 'DRAMA_AND_SOAPS' is different. Category id's elsewhere use drama-soaps,
                            # which is like cat_data['slug'], but this ID is not used in the addon at all.
                            ('FILM', 'FACTUAL', 'CHILDREN', 'DRAMA_AND_SOAPS', 'SPORT', 'COMEDY',
                             'ENTERTAINMENT', 'SIGNED_BSL'))
            self.assertTrue(is_not_empty(cat_data['name'], str))
            programmes = data['programmes']
            t_2 = time.time()
            self.assertIsInstance(programmes, list)
            for progr in programmes:
                check_category_item(progr)
                # All normal category items are of type brand, but the checker above still allows other
                # types used in category news.
                assert progr['contentType'] == 'brand'
            if cat == 'films':
                # All films must be playable items.
                playables = [p for p in programmes if p.get('encodedEpisodeId') is None]
                self.assertEqual(len(playables), len(programmes))

    def test_category_news(self):
        url = 'https://www.itv.com/watch/categories/news'
        t_s = time.time()
        page = fetch.get_document(url)
        t_1 = time.time()
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/category_news.json')
        news_data = data['data']
        # Check the hero rail
        for item in news_data['heroAndLatestData']:
            check_short_form_item(item)
        for item in news_data['longformData']:
            check_category_item(item)
        for rail in news_data['curatedRails']:
            self.assertTrue(isinstance(rail['title'], str) and rail['title'])
            for item in rail['clips']:
                check_short_form_item(item)


class MyList(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.token = itv_account.itv_session().access_token
        cls. userid = itv_account.itv_session().user_id

    def test_get_my_list_no_content_type(self):
        """Request My List without specifying header content-type

        """
        # Query parameters 'features' and 'platform' are required!!
        # NOTE:
        #   Platform dotcom may return fewer items than mobile and ctv, even when those items are
        #   presented and playable on the website.
        url = 'https://my-list.prd.user.itv.com/user/{}/mylist?features=mpeg-dash,outband-webvtt,hls,aes,playre' \
              'ady,widevine,fairplay,progressive&platform=ctv&size=52'.format(self.userid)
        headers = {'authorization': 'Bearer ' + self.token}
        # Both webbrowser and app authenticate with header, without any cookie.
        resp = requests.get(url, headers=headers)
        data = resp.json()

        # When no particular type of content is requested a dict is returned
        self.assertIsInstance(data, dict)
        self.assertEqual(resp.headers['content-type'], 'application/vnd.itv.online.perso.my-list.v1+json')

        my_items = data['items']
        self.assertEqual(data['availableSlots'], 52 - len(my_items))
        if len(my_items) == 0:
            print("WARNING - No LastWatched items")
        for item in my_items:
            check_mylist_item(self, item, parent_name='MyList')

    def test_get_my_list_content_type_json(self):
        """Request My List with content-type = application/json"""
        url = 'https://my-list.prd.user.itv.com/user/{}/mylist?features=mpeg-dash,outband-webvtt,hls,aes,playre' \
              'ady,widevine,fairplay,progressive&platform=ctv&size=52'.format(self.userid)
        headers = {'authorization': 'Bearer ' + self.token,
                   'accept': 'application/json'}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        # testutils.save_json(data, 'mylist/mylist_json_data.json')

        self.assertIsInstance(data, list)
        self.assertEqual(resp.headers['content-type'], 'application/json')

    def test_add_and_remove_programme(self):
        """At present only programmes can be added to the list, no individual episodes.

        Itv always returns HTTP status 200 when a syntactical valid request has been made. However,
        that is no guarantee that the requested programme is in fact added to My List.

        """
        progr_id = '2_7931'     # A spy among friends
        url = ('https://my-list.prd.user.itv.com/user/{}/mylist/programme/{}?'
               'features=mpeg-dash,outband-webvtt,hls,aes,playready,'
               'widevine,fairplay,progressive&platform=ctv').format(self.userid, progr_id)
        # Both webbrowser and app authenticate with header, without any cookie.
        headers = {'authorization': 'Bearer ' + self.token}

        # Add the item to the list, only to ensure it is present when it is removed next.
        resp = requests.post(url, headers=headers)
        data = resp.json()['items']
        for item in data:
            check_mylist_item(self, item, 'MyList')
        self.assertTrue(progr_id in (item['programmeId'].replace('/', '_') for item in data))

        # Delete the item
        resp = requests.delete(url, headers=headers)
        data = resp.json()['items']
        for item in data:
            check_mylist_item(self, item, 'MyList')
        self.assertFalse(progr_id in (item['programmeId'].replace('/', '_') for item in data))

        # Add it again now it's certain that the item was not on the list.
        resp = requests.post(url, headers=headers)
        data = resp.json()['items']
        for item in data:
            check_mylist_item(self, item, 'MyList')
        self.assertTrue(progr_id in (item['programmeId'].replace('/', '_') for item in data))
