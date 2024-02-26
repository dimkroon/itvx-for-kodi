
# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2024 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from test.support import fixtures
fixtures.global_setup()

import time
import unittest
import requests
from datetime import datetime

from resources.lib import fetch, parsex, utils, errors, main, itv_account
from support.object_checks import (
    has_keys,
    expect_keys,
    misses_keys,
    is_url,
    is_iso_utc_time,
    is_tier_info,
    is_not_empty,
    is_encoded_programme_id,
    is_encoded_episode_id,
    check_short_form_slider,
    check_short_form_item,
    check_category_item
)
from support import testutils

setUpModule = fixtures.setup_web_test

# A list of all pages that have been checked. Prevents loops and checking the same page
# over again when it appears in multiple collections.
checked_urls = []


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
        return
    href = collection_data.get('headingLink')
    if href:
        page_ref = 'https://www.itv.com/watch' + href
        return page_ref, obj_name
    else:
        for show in collection_data['shows']:
            check_shows(testcase, show, obj_name)


def check_shows(testcase, show, parent_name):
    """Check an item of a collection page or in a rail on the main page."""
    testcase.assertTrue(show.get('contentType') in
                        ('series', 'brand', 'film', 'special', 'episode', 'collection', 'fastchannelspot',
                        'simulcastspot', 'page', None),
                        "{}: Unexpected title type '{}'.".format('.'.join((parent_name, show['title'])),
                                                                 show.get('contentType', '')))
    if show.get('contentType') is None:
        # This type is not actually a show
        return True
    if show['contentType'] == 'collection':
        return check_rail_item_type_collection(testcase, show, parent_name)
    if show['contentType'] == 'fastchannelspot':
        return check_collection_item_type_fastchannelspot(testcase, show, parent_name)
    if show['contentType'] == 'simulcastspot':
        return check_item_type_simulcastspot(testcase, show, parent_name)
    if show['contentType'] == 'page':
        return check_item_type_page(testcase, show, parent_name)
    # Not always present: 'contentInfo'
    has_keys(show, 'contentType', 'title', 'description', 'titleSlug', 'imageTemplate',
             'encodedProgrammeId', obj_name='{}-show-{}'.format(parent_name, show['title']))
    if show['contentType'] in ('series', 'episode'):
        has_keys(show, 'encodedEpisodeId', obj_name='{}-show-{}'.format(parent_name, show['title']))
    else:
        misses_keys(show, 'encodedEpisodeId', obj_name='{}-show-{}'.format(parent_name, show['title']))
    testcase.assertTrue(is_url(show['imageTemplate']))


def check_programme(self, progr_data):
    """Formerly known as 'Brand'"""
    obj_name = progr_data['title']
    has_keys(progr_data, 'title', 'image', 'longDescription', 'description',
             'encodedProgrammeId', 'titleSlug', 'tier',
             obj_name=obj_name)
    expect_keys(progr_data, 'imagePresets', 'categories', 'programmeId')
    self.assertTrue(is_encoded_programme_id(progr_data['encodedProgrammeId']))
    self.assertTrue(is_not_empty(progr_data['title'], str))
    self.assertTrue(is_not_empty(progr_data['longDescription'], str))
    self.assertTrue(is_not_empty(progr_data['description'], str))
    self.assertTrue(is_url(progr_data['image']))
    self.assertTrue(is_not_empty(progr_data['categories'], list))
    self.assertTrue(is_not_empty(progr_data['titleSlug'], str))
    self.assertTrue(is_tier_info(progr_data['tier']))
    if 'numberOfAvailableSeries' in progr_data:
        self.assertTrue(is_not_empty(progr_data['numberOfAvailableSeries'], int))


def check_series(self, series, parent_name):
    obj_name = '{}-{}'.format(parent_name, series['seriesLabel'])
    has_keys(series, 'seriesLabel', 'seriesNumber', 'numberOfAvailableEpisodes', 'titles',
             obj_name=obj_name)
    expect_keys(series, 'legacyId', 'fullSeries', 'seriesType', 'longRunning')
    self.assertTrue(is_not_empty(series['seriesNumber'], str))
    self.assertTrue(is_not_empty(series['seriesLabel'], str))
    # A programme can have single episodes not belonging to a series, like the Christmas special.
    # These are of type 'EPISODE'.
    self.assertTrue(series['seriesType'] in ('SERIES', 'FILM', 'EPISODE'))
    self.assertTrue(is_not_empty(series['numberOfAvailableEpisodes'], int))
    for episode in series['titles']:
        check_title(self, episode, obj_name)


def check_title(self, title, parent_name):
    obj_name = '{}-title-{}'.format(parent_name, title['episodeTitle'])
    has_keys(title, 'availabilityFrom', 'availabilityUntil', 'contentInfo', 'dateTime', 'description',
             'duration', 'encodedEpisodeId', 'episodeTitle', 'guidance', 'image', 'longDescription',
             'notFormattedDuration', 'playlistUrl', 'productionType', 'premium', 'tier', 'series', obj_name=obj_name)

    expect_keys(title, 'audioDescribed', 'availabilityFeatures', 'categories', 'heroCtaLabel', 'episodeId',
                'fullSeriesRange', 'linearContent', 'longRunning', 'partnership',
                'productionId', 'programmeId', 'subtitled', 'visuallySigned', 'regionalisation', obj_name=obj_name)

    self.assertIsInstance(title['audioDescribed'], bool)
    self.assertTrue(is_iso_utc_time(title['availabilityFrom']))
    self.assertTrue(is_iso_utc_time(title['availabilityUntil']))
    self.assertIsInstance(title['categories'], list)
    self.assertTrue(is_not_empty(title['contentInfo'], str))
    self.assertTrue(is_iso_utc_time(title['dateTime']))
    self.assertTrue(is_not_empty(title['description'], str))
    self.assertTrue(is_not_empty(title['duration'], str))
    self.assertFalse(title['duration'].startswith('P'))  # duration is not in iso format
    self.assertTrue(is_encoded_episode_id(title['encodedEpisodeId']))
    self.assertTrue(is_not_empty(title['episodeTitle'], str) or title['episodeTitle'] is None)
    self.assertTrue(is_not_empty(title['longDescription'], str))
    self.assertTrue(is_url(title['image']))
    self.assertTrue(is_url(title['playlistUrl']))
    self.assertIsInstance(title['premium'], bool)
    self.assertTrue(title['productionType'] in('EPISODE', 'FILM', 'SPECIAL'))
    self.assertIsInstance(title['subtitled'], bool)
    if title['premium']:
        self.assertListEqual(['PAID'], title['tier'])
    else:
        self.assertListEqual(['FREE'], title['tier'])

    if title['productionType'] == 'EPISODE':
        expect_keys(title, 'isFullSeries', 'nextProductionId', )
        self.assertTrue(is_not_empty(title['episode'], int))
        # Some episodes do not belong to a series, like the Christmas special
        self.assertTrue(is_not_empty(title['series'], int) or title['series'] is None)

    if title['productionType'] == 'SPECIAL':
        self.assertIsNone(title['episode'])
        self.assertEqual('others', title['series'])
        self.assertGreater(title['productionYear'], 1900)
        # Specials have been observed with a title['dataTime'] of 1-1-1970, but also real dates occur.

    if title['productionType'] in ('EPISODE', 'FILM', 'SPECIAL'):
        pass

    if title['productionType'] == 'FILM':
        self.assertGreater(title['productionYear'], 1900)
        self.assertTrue('episode' not in title)
        self.assertIsNone(title['series'])
        self.assertEqual(utils.strptime(title['dateTime'], '%Y-%m-%dT%H:%M:%S.%fZ'), datetime(1970, 1, 1))


def check_episode(self, episode, parent_name):
    obj_name = '{}-{}'.format(parent_name, episode['episodeTitle'])
    check_title(self, episode, parent_name)
    has_keys(episode, 'daysLeft', 'seriesNumber', 'episodeNumber', 'href', 'programmeTitle', obj_name=obj_name)


def check_rail_item_type_collection(self, item, parent_name):
    """Check items of type collection found on heroContent and editorialSliders."""
    has_keys(item, 'contentType', 'title', 'titleSlug', 'collectionId', 'imageTemplate',
             obj_name='{}.{}'.format(parent_name, item.get('title', 'unknown')))
    expect_keys(item, 'imagePresets', 'channel', obj_name='{}.{}'.format(parent_name, item.get('title', 'unknown')))
    self.assertFalse(is_not_empty(item['imagePresets'], dict))
    self.assertTrue(is_url(item['imageTemplate']))
    self.assertTrue(is_not_empty(item['title'], str))
    self.assertTrue(is_not_empty(item['titleSlug'], str))
    self.assertTrue(is_not_empty(item['collectionId'], str))


def check_item_type_page(testcase, item, parent_name):
    """Check items of type page.
    Items of type page have been found in heroContent on the main page and as a
    show in a collection. In the latter, page items are disregarded, so this
    function currently only checks hero items.

    Page items are very similar to items of type collection. The only difference
    is the use of field 'pageId' instead of 'collectionId'.
    Furthermore, the urls of page appear to require a querystring to return without error.

    """
    has_keys(item, 'contentType', 'title', 'titleSlug', 'pageId', 'imageTemplate',
             obj_name='{}.{}'.format(parent_name, item.get('title', 'unknown')))
    # ctalable and arialabel seem to be specific to Hero items
    expect_keys(item, 'imagePresets', 'ctaLabel', 'ariaLabel',
                obj_name='{}.{}'.format(parent_name, item.get('title', 'unknown')))
    testcase.assertFalse(is_not_empty(item['imagePresets'], dict))
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
    resp = requests.get(url, headers=headers, timeout=4)
    testcase.assertEqual(404, resp.status_code)
    # Check the contents of the collection page with querystring added to url
    CollectionPages.check_page(testcase, url + '?ind', parent_name)


def check_collection_item_type_fastchannelspot(self, item, parent_name):
    name = '{}.{}'.format(parent_name, item.get('title', 'unknown'))
    has_keys(item, 'contentType', 'title', 'channel', 'description', 'imageTemplate',
             obj_name=name)
    expect_keys(item, 'contentInfo', 'imagePresets', 'tagNames', obj_name=name)
    # Keys available in simulcastspot, but not found in fastchannelspots. Flag any changes
    misses_keys(item, 'genre', 'startDateTime', 'endDateTime', 'progress', obj_name=name)
    self.assertEqual({}, item['imagePresets'])
    self.assertTrue(is_url(item['imageTemplate']))
    self.assertTrue(is_not_empty(item['title'], str))
    self.assertTrue(is_not_empty(item['channel'], str))
    self.assertTrue(is_url(item['imageTemplate']))


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
    expect_keys(item, 'contentInfo', 'imagePresets', 'tagNames', obj_name=name)
    self.assertEqual({}, item['imagePresets'])
    self.assertTrue(is_url(item['imageTemplate']))
    self.assertTrue(is_not_empty(item['title'], str))
    self.assertTrue(is_not_empty(item['channel'], str))
    self.assertTrue(is_url(item['imageTemplate']))
    # Generic check on start and end time. Items from hero use different format than those from collection.
    # Hero and collection will each perform additional checks on the format.
    self.assertTrue(is_not_empty(item['startDateTime'], str))
    self.assertTrue(is_not_empty(item['endDateTime'], str))


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
                            ('simulcastspot', 'fastchannelspot', 'series', 'film', 'special', 'brand',
                             'collection', 'page', 'upsellspot'))
            if content_type == 'upsellspot':
                continue
            if content_type == 'simulcastspot':
                check_item_type_simulcastspot(self, item, parent_name='hero-item')
                # Flag if key normally only present in collections become available in hero items as well
                misses_keys(item, 'contentinfo', 'progress', obj_name='hero-item.'+ item['title'])
                # Start and end times in Simulcastspots in hero are normally not in iso format.
                # Flag if this changes.
                self.assertFalse(is_iso_utc_time(item['startDateTime']))
                self.assertFalse(is_iso_utc_time(item['endDateTime']))
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
                         'contentInfo', 'tagName', obj_name=item['title'])
                self.assertIsInstance(item['contentInfo'], list)

                if item['contentType']in ('simulcastspot', 'fastchannelspot'):
                    has_keys(item, 'channel', obj_name=item['title'])
                else:
                    has_keys(item, 'encodedProgrammeId', 'programmeId', obj_name=item['title'])
                    # As of 06-2023 field genre seems to be removed from all types of hero content.
                    # Just keep the check in for a while.
                    expect_keys(item, 'genre', obj_name='Hero-item ' + item['title'])

                if item['contentType'] == 'special':
                    # Field 'dateTime' not always present in special title
                    has_keys(item, 'encodedEpisodeId', 'duration', obj_name=item['title'])

                if item['contentType'] == 'series':
                    has_keys(item, 'encodedEpisodeId', 'brandImageTemplate', 'series', obj_name=item['title'])

                if item['contentType'] == 'film':
                    # Fields not always present:  'dateTime'
                    has_keys(item, 'productionYear', 'duration', obj_name=item['title'])

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
            header  = slider['header']
            # ShortFromSlider on the main page should have a reference to the collection page.
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

        page_data = parsex.scrape_json(fetch.get_document(url))
        checked_urls.append(url)

        if parent_name:
            parent_name = parent_name + '.' + page_data['headingTitle'] + '.'
        else:
            parent_name = page_data['headingTitle'] + '.'

        # if 'Rugby World Cup' in page_data['headingTitle']:
        #     testutils.save_json(page_data, 'html/collection_rugby-world-cup.json')
        has_keys(page_data, 'headingTitle', 'collection', 'editorialSliders', 'shortFormSlider',
                 'pageImageUrl', 'isAccessibleByKids', obj_name=parent_name[:-1])
        expect_keys(page_data, 'headingDescription', obj_name=parent_name[:-1])
        collection = page_data['collection']
        editorial_sliders = page_data['editorialSliders']
        shortform_slider = page_data['shortFormSlider']

        if collection is not None:
            # Page without rails has no image, notify when that changes.
            testcase.assertEqual(page_data['pageImageUrl'], '')
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

        # The same as the original shortFromSlider from the main page now made available on the collection page
        if shortform_slider is not None:
            check_short_form_slider(testcase, shortform_slider, name='collection-' + page_data['headingTitle'])

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
            self.assertTrue(obj_name.lower().startswith('unwind') or obj_name.lower().startswith('citv'))
            return

        has_keys(progr_data, *all_keys, obj_name=obj_name)
        # These times are in a format like '2022-11-22T20:00Z'
        self.assertTrue(is_iso_utc_time(progr_data['start']))
        self.assertTrue(is_iso_utc_time(progr_data['end']))

        if chan_type == 'fast':
            misses_keys(progr_data, 'broadcastStartTimestamp', obj_name=obj_name)
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
        # testutils.save_doc(page, 'html/watch-itv1.html')
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
                ):
            page = fetch.get_document(url)
            # testutils.save_doc(page, 'html/series_bad-girls.html')
            data = parsex.scrape_json(page)
            # testutils.save_json(data, 'html/series_midsomer-murders.json')
            programme_data = data['programme']
            check_programme(self, programme_data)
            for series in data['seriesList']:
                check_series(self, series, programme_data['title'])

    def test_premium_episode_page(self):
        url = 'https://www.itv.com/watch/downton-abbey/1a8697/1a8697a0001'
        page = fetch.get_document(url)
        # testutils.save_doc(page, 'html/paid_episode_downton-abbey-s1e1.html')
        data = parsex.scrape_json(page)
        programme_data = data['programme']
        check_programme(self, programme_data)
        self.assertListEqual(['PAID'], programme_data['tier'])
        for series in data['seriesList']:
            check_series(self, series, programme_data['title'])
            for title in series['titles']:
                self.assertTrue(title['premium'])

    def test_film_details_page(self):
        page = fetch.get_document('https://www.itv.com/watch/danny-collins/10a3142')
        # testutils.save_doc(page, 'html/film_danny-collins.html')
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/film_danny-collins.json')
        check_programme(self, data['programme'])
        self.assertEqual(1, len(data['seriesList']))
        self.assertEqual(1, len(data['seriesList'][0]['titles']))
        check_series(self, data['seriesList'][0], data['programme']['title'])

    def test_special_details_page(self):
        page = fetch.get_document('https://www.itv.com/watch/how-to-catch-a-cat-killer/10a1951')
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/special_how-to-catch-a-cat-killer_data.json')
        check_programme(self, data['programme'])
        self.assertEqual(1, len(data['seriesList']))
        self.assertEqual(1, len(data['seriesList'][0]['titles']))
        check_series(self, data['seriesList'][0], data['programme']['title'])

    def test_news_item_tonight(self):
        page = fetch.get_document('https://www.itv.com/watch/tonight-can-britain-get-talking/1a2803/1a2803a9382')
        # testutils.save_doc(page, 'html/news-tonight.html')
        data = parsex.scrape_json(page)
        check_programme(self, data['programme'])

    def test_short_news_item(self):
        page = fetch.get_document('https://www.itv.com/watch/news/met-police-officers-investigated-for-gross-misconduct-over-stephen-port-case/fxmdtwy')
        # testutils.save_doc(page, 'html/news-short_item.html')
        data = parsex.scrape_json(page)
        self.assertFalse('programme' in data)
        self.assertTrue('episode' in data)
        self.assertTrue(is_url(data['episode']['playlistUrl']))


class TvGuide(unittest.TestCase):
    def test_guide_of_today(self):
        today = ''  # datetime.utcnow().strftime(('%Y-%m-%d'))
        url = 'https://www.itv.com/watch/tv-guide/' + today
        page = fetch.get_document(url)
        # testutils.save_doc(page, 'html/tv_guide.html')
        self.assertRaises(errors.ParseError,  parsex.scrape_json, page)


class Categories(unittest.TestCase):
    all_categories = ['factual', 'drama-soaps', 'children', 'films', 'sport', 'comedy', 'news', 'entertainment']

    def test_get_available_categories(self):
        """The page categories returns in fact already a full categorie page - the first page in the list
        of categories. Which categorie that is, may change.
        Maybe because of that it is much slower than requesting categories by gql.
        """
        t_s = time.time()
        page = fetch.get_document('https://www.itv.com/watch/categories')
        # testutils.save_doc(page, 'html/categories.html')
        t_1 = time.time()
        data = parsex.scrape_json(page)
        # testutils.save_json(data, 'html/categories_data.json')
        categories = data['subnav']['items']
        t_2 = time.time()
        for item in categories:
            has_keys(item, 'id', 'label', 'url')
            # url is the full path without domain
            self.assertTrue(item['url'].startswith('/watch/'))

        self.assertEqual(8, len(categories))        # the mobile app has an additional category AD (Audio Described)
        self.assertListEqual([cat['id'] for cat in categories], self.all_categories)
        # print('Categorie page fetched in {:0.3f}, parsed in {:0.3f}, total: {:0.3f}'.format(
        #     t_1 - t_s, t_2 - t_1, t_2 - t_s))

    def test_all_categories(self):
        for cat in self.all_categories:
            if cat == 'news':
                # As of May 2023 category news returns a different data structure and has its own test.
                continue
            url = 'https://www.itv.com/watch/categories/' + cat + '/all'
            t_s = time.time()
            page = fetch.get_document(url)
            t_1 = time.time()
            data = parsex.scrape_json(page)
            # if cat == 'films':
            #     testutils.save_json(data, 'html/category_{}.json'.format(cat))
            programmes = data['programmes']
            t_2 = time.time()
            self.assertIsInstance(programmes, list)
            for progr in programmes:
                check_category_item(progr)
            if cat == 'films':
                # All films must be playable items.
                playables = [p for p in programmes if p['encodedEpisodeId']['letterA'] == '']
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
              'ady,widevine,fairplay,progressive&platform=ctv'.format(self.userid)
        headers = {'authorization': 'Bearer ' + self.token}
        # Both webbrowser and app authenticate with header, without any cookie.
        resp = requests.get(url, headers=headers)
        data = resp.json()
        # testutils.save_json(data, 'mylist/mylist_data.json')

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
              'ady,widevine,fairplay,progressive&platform=ctv'.format(self.userid)
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
        url = 'https://my-list.prd.user.itv.com/user/{}/mylist/programme/{}?features=mpeg-dash,outband-webvtt,hls,aes,playre' \
              'ady,widevine,fairplay,progressive&platform=ctv'.format(self.userid, progr_id)
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
