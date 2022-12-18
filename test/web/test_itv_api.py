
from support import testutils
from test.support import fixtures
fixtures.global_setup()

from datetime import datetime, timedelta
import time
import unittest
import requests
import copy

from resources.lib import itv, fetch, errors, parse
from resources.lib import itv_account

from test.support import object_checks


setUpModule = fixtures.setup_web_test


class TestCookies(unittest.TestCase):
    def test_cookie_consent(self):
        r = requests.Session()


# ----------------------------------------------------------------------------------------------------------------------
#           JSON API
# ----------------------------------------------------------------------------------------------------------------------

class LiveSchedules(unittest.TestCase):
    """Request the live schedule
    No cookies or authentication required. Web browser doesn't either.

    """
    def check_schedule(self, start_dt, end_dt):
        t_fmt = '%Y%m%d%H%M'
        resp = requests.get(
                'https://scheduled.oasvc.itv.com/scheduled/itvonline/schedules?',
                params={'from': start_dt.strftime(t_fmt),
                        'to': end_dt.strftime(t_fmt),
                        'platformTag': 'dotcom',        # was 'ctv' until recently, maybe changed since itvX
                        'featureSet': 'mpeg-dash,widevine'},
                headers={'Accept': 'application/vnd.itv.hubsvc.schedule.v2+vnd.itv.hubsvc.channel.v2+hal+json',
                         'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                         'Origin': 'https://www.itv.com',
                         },
                timeout=60)     # Usually a 504 - Gateway Timeout is returned before that.
        resp.raise_for_status()
        data = resp.json()
        # testutils.save_json(data, 'schedule/live_4hrs.json')

        schedule = data['_embedded']['schedule']
        self.assertEqual(6, len(schedule))      # only the 6 main channels are present in the schedule
        for channel_data in schedule:
            programs = channel_data['_embedded']['slot']
            for program in programs:
                object_checks.has_keys(program, 'programmeTitle', 'startTime', 'onAirTimeUTC', 'productionId')
                self.assertTrue(program['startTime'].endswith('Z'))     # start time is in format '2022-11-22T20:00Z'
                self.assertEqual(17, len(program['startTime']))         # has no seconds
            channel_info = channel_data['_embedded']['channel']
            object_checks.has_keys(channel_info, 'name', 'strapline', '_links')
            self.assertTrue(channel_info['_links']['playlist']['href'].startswith('https'))
            return schedule

    def test_main_channels_schedules_4hrs(self):
        now = datetime.utcnow()
        end = now + timedelta(hours=4)
        self.check_schedule(now, end)

    def test_main_channels_schedules_week_in_the_past(self):
        """Live schedules are available to some time in the past.

        Requesting schedules takes some time, but going further in the past quickly increases
        the time the request takes to return. There is definitely a caching problem upstream.
        If we do the same request several times, a response that initially took 10 sec , returns
        in 150 ms after a few attempts.

        .. Note ::
        Regularly requests encounter a 504 - Gateway Timeout error, even requests that on other occasions
        complete without error, but going further in the past increases the change of a time-out.
        """
        now = datetime.utcnow()
        start = now - timedelta(days=4)
        self.check_schedule(start, now)
        # self.assertRaises(requests.ReadTimeout, self.check_schedule, start, now)

    def test_main_channels_schedules_days_in_the_future(self):
        """Live schedules are available up to roughly 1 week in the future. Requests for
        more will usually succeed normally, but do not contain more data.

        See the test above (week_in_the_past) for peculiarities

        """
        now = datetime.utcnow()
        end = now + timedelta(days=8)
        expected_end = now + timedelta(days=7)
        schedule = self.check_schedule(now, end)
        last_programme = schedule[0]['_embedded']['slot'][-1]
        start_dt = datetime.strptime(last_programme['startTime'], '%Y-%m-%dT%H:%MZ')
        self.assertAlmostEqual(start_dt.timestamp(), expected_end.timestamp(), delta=86400)  # give or take a day

    def test_one_day_week_ago(self):
        now = datetime.utcnow()
        end = now - timedelta(days=6)
        schedule = self.check_schedule(start_dt=now - timedelta(days=7), end_dt=end)
        last_programme = schedule[0]['_embedded']['slot'][-1]
        start_dt = datetime.strptime(last_programme['startTime'], '%Y-%m-%dT%H:%MZ')
        self.assertAlmostEqual(start_dt.timestamp(), end.timestamp(), delta=86400)  # give or take a day

    def test_now_next(self):
        resp = requests.get('https://nownext.oasvc.itv.com/channels?broadcaster=itv&featureSet=mpeg-dash,clearkey,'
                            'outband-webvtt,hls,aes,playready,widevine,fairplay&platformTag=dotcom')
        data = resp.json()
        # testutils.save_json(data, 'schedule/now_next.json')
        object_checks.has_keys(data, 'channels', 'images', 'ts')

        self.assertTrue(data['images']['backdrop'].startswith('https://'))
        self.assertTrue(data['images']['backdrop'].endswith('.jpeg'))

        self.assertAlmostEqual(25, len(data['channels']), delta=2)
        for chan in data['channels']:
            object_checks.has_keys(chan, 'id', 'editorialId', 'channelType', 'name', 'streamUrl', 'slots', 'images')
            for program in (chan['slots']['now'], chan['slots']['next']):
                object_checks.has_keys(program, 'titleId', 'prodId', 'contentEntityType', 'start', 'end', 'title',
                                       'brandTitle', 'displayTitle', 'detailedDisplayTitle', 'broadcastAt', 'guidance',
                                       'rating', 'episodeNumber', 'seriesNumber', 'startAgainVod',
                                       'startAgainSimulcast', 'shortSynopsis')
                self.assertIsNotNone(program['displayTitle'])
                self.assertTrue(object_checks.is_iso_time(program['start']))
                self.assertTrue(object_checks.is_iso_time(program['end']))
                if program['broadcastAt'] is not None:      # is None on fast channels
                    self.assertTrue(program['broadcastAt'].endswith('Z'))
                    self.assertTrue(20, len(program['broadcastAt']))


class WatchPages(unittest.TestCase):
    def test_watch_itv1(self):
        acc_data = itv_account.itv_session()
        page = fetch.get_document("https://www.itv.com/watch?channel=itv")
        # testutils.save_doc(page, 'html/watch-itv1.html')
        data = parse.get__next__data_from_page(page)
        print(data)


class Categories(unittest.TestCase):
    cat_req_kwargs = {
        'url': 'https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/categories',
        'headers': {'Accept': 'application/vnd.itv.online.discovery.category.v1+hal+json; charset=UTF-8'}
    }

    def test_categories(self):
        json_resp = requests.get(**self.cat_req_kwargs).json()
        self.assertTrue('_embedded' in json_resp.keys())
        self.assertTrue('categories' in json_resp['_embedded'].keys())
        cat_list = json_resp['_embedded']['categories']
        self.assertIsInstance(cat_list, list)
        for item in cat_list:
            self.assertTrue('name' in item.keys())
            self.assertTrue('_links' in item.keys())
            self.assertTrue(item['_links']['doc:programmes']['href'].startswith('https://'))


class Programmes(unittest.TestCase):
    def get_json(self, url):
        resp = requests.get(
                url,
                headers={'Accept': 'application/vnd.itv.online.discovery.programme.v1+hal+json; charset=UTF-8'}
        )
        return resp.json()

    def _validate_strcuture(self, programs_data):
        self.assertTrue('_embedded' in programs_data.keys())
        self.assertTrue('programmes' in programs_data['_embedded'].keys())
        prog_list = programs_data['_embedded']['programmes']
        self.assertIsInstance(prog_list, list)
        for item in prog_list:
            self.assertTrue('id' in item.keys())
            self.assertTrue('title' in item.keys())
            self.assertTrue('epg' in item['synopses'].keys())
            productions = item['_embedded']['productions']
            self.assertTrue('count' in productions.keys())
            self.assertTrue('_links' in productions.keys())
            self.assertTrue(productions['_links']['doc:productions']['href'].startswith('https://'))
            latest = item['_embedded']['latestProduction']
            self.assertTrue('productionType' in latest.keys())
            self.assertTrue(latest['productionType'] in ('programme', 'PROGRAMME'))

            # series and episodes are not always present, event of there are more than 1 episodes.
            # assertTrue('episode' in latest.keys())

            # EpisodeTitle is not always present, even if there are multiple episodes availble.
            # self.assertTrue('episodeTitle' in latest.keys(),
            #                 msg="No key episodeTitle in production {}".format(latest))

            self.assertTrue('commissioning' in latest['broadcastDateTime'].keys())
            self.assertTrue('iso8601', latest['duration'].keys())
            self.assertTrue('display', latest['duration'].keys())
            self.assertTrue(latest['_links']['image']['href'].startswith('https://'))
            self.assertTrue(latest['_links']['playlist']['href'].startswith('https://'))

    def test_programmes_all(self):
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?'
                                  'broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,'
                                  'widevine,fairplay&sortBy=title')
        self._validate_strcuture(json_resp)

    def test_programs_category_factual(self):
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?'
                                  'category=Factual&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                  'playready,widevine&broadcaster=itv')
        self._validate_strcuture(json_resp)

    def test_programs_are_same_for_different_platforms(self):
        """Test if the number of programs differ for different platforms

        Initially they did not, but now dotcom returns a significant larger number (> 400) of programs than ctv.
        """
        dotcom_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?'
                                    'broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,'
                                    'widevine,fairplay&sortBy=title')
        ctv_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/ctv/programmes?'
                                 'broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,'
                                 'widevine,fairplay&sortBy=title')
        dot_com_programs = dotcom_resp['_embedded']['programmes']
        ctv_programs = ctv_resp['_embedded']['programmes']
        self.assertGreater(len(dot_com_programs), len(ctv_programs))


class Productions(unittest.TestCase):
    def get_json(self, url):
        resp = requests.get(
                url,
                headers={'Accept': 'application/vnd.itv.online.discovery.production.v1+hal+json; charset=UTF-8'}
        )
        return resp.json()

    def _validate_structure(self, productions_data):
        self.assertIsInstance(productions_data['count'], int)
        self.assertTrue('_embedded' in productions_data.keys())
        prod_list = productions_data['_embedded']['productions']
        self.assertIsInstance(prod_list, list)
        for prod in prod_list:
            self.assertTrue('productionId' in prod.keys())
            self.assertEqual(prod['productionType'], 'PROGRAMME')
            self.assertTrue('episodeId' in prod.keys())
            self.assertTrue('iso8601' in prod['duration'].keys())
            self.assertTrue('display' in prod['duration'].keys())
            self.assertTrue('commissioning' in prod['broadcastDateTime'].keys())
            self.assertTrue('epg' in prod['synopses'].keys())
            self.assertTrue('image' in prod['_links'].keys())
            self.assertTrue(prod['_links']['image']['templated'])
            self.assertTrue('href' in prod['_links']['image'].keys())
            self.assertTrue('href' in prod['_links']['playlist'].keys())
            self.assertTrue('playlist' in prod['_links'].keys())
            self.assertTrue('title' in prod['_embedded']['programme'])
            # The following key are optional, thus may not be present at all times
            # self.assertTrue('episodeTitle' in prod.keys())
            # self.assertTrue('series' in prod.keys(),
            #                 msg="key 'series' not present in production '{}'".format(prod['productionId']))
            # self.assertTrue('episode' in prod.keys())
            # self.assertTrue('guidance' in prod.keys())
            # self.assertTrue('original' in prod['broadcastDateTime'].keys())

    def test_productions_midsummer_murders(self):
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                  'programmeId=Y_1096&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                  'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

    def test_productions_2020_the_story_of_us(self):
        """The long call - 4 episodes

        A programme where individual production do not have an episodeTitle
        """
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                  'programmeId=2_6931&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                  'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

    def test_productions_the_thief_his_wife_and_the_canoe(self):
        """The thief, his wife and the canoe - 4 episodes

        A programme where individual production do not have an episodeTitle
        """
        json_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                  'programmeId=10_1187&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                  'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

    def test_productions_coronation_street(self):
        """Coronation Street, several episodes

        A programme where individual episodes do not have keys 'series' and 'episode'
        """
        json_resp =  self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                   'programmeId=1_0694&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                   'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

    def test_productions_the_chase(self):
        """The program item showed 52 episodes, but the productions listing only showed 1 item

        """
        json_resp =  self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/productions?'
                                   'programmeId=1_7842&features=aes,clearkey,fairplay,hls,mpeg-dash,outband-webvtt,'
                                   'playready,widevine&broadcaster=itv')
        self._validate_structure(json_resp)

# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class Playlists(unittest.TestCase):
    def create_post_data(self):
        acc_data = itv_account.itv_session()
        post_data = copy.deepcopy(itv.stream_req_data)
        post_data['user']['token'] = acc_data.access_token
        post_data['client']['supportsAdPods'] = True
        featureset = post_data['variantAvailability']['featureset']
        featureset['min'] = featureset['max']
        return post_data

    def test_get_playlist_live(self):
        """Get the playlists of the main live channels

        For all channels other than ITV the headers User Agent and Origin are required.
        And the cookie consent cookies must present. If any of those are missing the request will time out.
        """
        acc_data = itv_account.itv_session()
        acc_data.refresh()
        post_data = self.create_post_data()

        for channel in ('ITV', 'ITV2', 'ITV3', 'ITV4', 'CITV', 'ITVBe'):
            url = 'https://simulcast.itv.com/playlist/itvonline/' + channel
            resp = requests.post(
                    url,
                    headers={'Accept': 'application/vnd.itv.online.playlist.sim.v3+json',
                             'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                             'Origin':           'https://www.itv.com',
                             # 'Referer':          'https://www.itv.com/',
                             # 'Sec-Fetch-Dest':   'empty',
                             # 'Sec-Fetch-Mode':   'cors ',
                             # 'Sec-Fetch-Site':   'same-site'
                             },
                    cookies=fetch.HttpSession().cookies,  #acc_data.cookie,
                    json=post_data,
                    timeout=10
            )
            self.assertEqual(200, resp.status_code)
            strm_data = resp.json()
            object_checks.check_live_stream_info(strm_data['Playlist'])

    def get_playlist_catchup(self):
        """Request stream of a catchup episode (i.e. production)

        Webbrowsers send several cookies in one single Cookie header:
            - Itv.Session
            - Itv.Cid
            - mid
            - All Syrenisxxx concerning cookie consent
            - _ga_D6PQ6YDTQK
            - _ga
            - Itv.Region

        However, we test with only Itv.Session cookie set and that seems to work fine.

        """
        acc_data = itv_account.itv_session()
        post_data = self.create_post_data()
        # post_data['user']['itvUserId'] = '92a3bfde-bfe1-40ea-ad43-09b8b522b7cb'

        # Snooker UK open episode 10 - an episode without subtitles
        # url = 'https://magni.itv.com/playlist/itvonline/ITV4/10_1758_0023.001'

        # request playlist of an episode of Doc Martin
        url = 'https://magni.itv.com/playlist/itvonline/ITV/1_7665_0049.001'

        # The bigger trip - episode 1
        # url = 'https://magni.itv.com/playlist/itvonline/ITV/10_2772_0001.001'

        # url = 'https://magni.itv.com/playlist/itvonline/ITV/CFD0332_0001.001'


        resp = requests.post(
            url,
            headers={'Accept': 'application/vnd.itv.vod.playlist.v2+json',
                     'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0 ',
                     'Origin': 'https://www.itv.com',
                     },
            json=post_data,
            timeout=10)
        resp = resp.json()

        # resp = itv_account.fetch_authenticated(
        #     fetch.post_json, url,
        #     data=post_data,
        #     headers={'Accept': 'application/vnd.itv.vod.playlist.v2+json'})

        return resp

    def test_get_playlist_catchup(self):
        resp = self.get_playlist_catchup()
        strm_data = resp
        object_checks.check_catchup_dash_stream_info(strm_data['Playlist'])

    # def test_dash_manifest(self):
    #     url = 'https://itvpnpdotcom.cdn1.content.itv.com/10-2772-0001-001/18/2/VAR028/10-2772-0001-001_18_2_VAR028.ism/.mpd?Policy=eyJTdGF0ZW1lbn' \
    #           'QiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9pdHZwbnBkb3Rjb20uY2RuMS5jb250ZW50Lml0di5jb20vMTAtMjc3Mi0wMDAxLTAwMS8xOC8yL1ZBUjAyOC8xMC0yNzcyLTAw' \
    #           'MDEtMDAxXzE4XzJfVkFSMDI4LmlzbS8qIiwiQ29uZGl0aW9uIjp7IkRhdGVMZXNzVGhhbiI6eyJBV1M6RXBvY2hUaW1lIjoxNjYzODI4OTIwfX19XX0_&Signature=SeN' \
    #           'TRPqvV~jRw59gIIEnXtG4-VvBOSfNnWflCosIAyXm2xZ1ZbUREze0X34-o1v2l1MJ4yvXKMMwDhi7Db5rM-gEq9sgm9twvv5k9sMIeynQ7aBhlafgHSc7GqwB6pQ11i5XY' \
    #           '29W5F9WfEAcPLkvH4NlXxYzYnKM4RQKofauAjImxrteCG3XAJDu-Dt~JPLR~EJ3MXtodRFJQGnydT~aukIIO3tuyBjAaUKkB1KmXi7RdkTKdO1~5PfNOLPkB3ZCvUb2jqi' \
    #           'LtUE988solFN8uzOsUKGVVdA--5zahz3RAVIcc9wp8PzDeFj~KEDzMytINmmTIpZUodmWTeu5nYWYRw__&Key-Pair-Id=APKAJB7PCFZAZHWZVIB'
    #
    #     try:
    #         resp = itv_account.fetch_authenticated(fetch.get_document, url)
    #         return True
    #     except errors.FetchError:
    #         return False


class Search(unittest.TestCase):
    search_url = 'https://textsearch.prd.oasvc.itv.com/search'
    search_params = {
        'broadcaster': 'itv',
        'featureSet': 'clearkey,outband-webvtt,hls,aes,playready,widevine,fairplay,bbts,progressive,hd,rtmpe',
        'onlyFree': 'false',
        'platform': 'dotcom',
    }

    def check_result(self, resp_obj):
        object_checks.has_keys(resp_obj, 'results', 'maxScore', obj_name='search_result')
        results = resp_obj['results']
        self.assertIsInstance(results, list)
        for item in results:
            object_checks.has_keys(item, 'id', 'entityType', 'streamingPlatform', 'data', 'score', obj_name='resultItem')
            if item['entityType'] == 'programme':
                self.check_programme_item(item['data'])
            elif item['entityType'] == 'special':
                self.check_special_item(item['data'])
            else:
                raise AssertionError('unknown entityType {}'.format(item['entityType']))

    def check_programme_item(self, item_data):
        object_checks.has_keys(item_data, 'programmeCCId', 'legacyId', 'productionId', 'programmeTitle',
                               'synopsis', 'latestAvailableEpisode', 'totalAvailableEpisodes', 'tier',
                               obj_name='programItem.data')
        self.assertTrue(item_data['latestAvailableEpisode']['imageHref'].startswith('https://'))

    def check_special_item(self, item_data):
        object_checks.has_keys(item_data, 'specialCCId', 'legacyId', 'productionId', 'specialTitle', 'specialProgramme',
                               'synopsis', 'imageHref', 'tier',
                               obj_name='specialItem.data')
        special_data = item_data.get('specialProgramme')
        # The field specialProgramme is not used by the addon, but if present we check it anyway
        if special_data:
            object_checks.has_keys(special_data, 'programmeCCId', 'legacyId', 'programmeTitle',
                                   obj_name='specialItem.data.specialProgramme')
        self.assertTrue(item_data['imageHref'].startswith('https://'))

    def test_search_normal(self):
        self.search_params['query'] = 'the chases'
        resp = requests.get(self.search_url, params=self.search_params).json()
        self.check_result(resp)
        self.assertGreater(len(resp['results']), 3)

    def test_search_without_result(self):
        self.search_params['query'] = 'xprs'
        resp = requests.get(self.search_url, params=self.search_params)
        self.assertEqual(204, resp.status_code)

    def test_search_with_non_free_results(self):
        """Results contain Doctor Foster programme which is can only be watch with a premium account."""
        self.search_params['query'] = 'doctor foster'
        resp = requests.get(self.search_url, params=self.search_params).json()
        self.check_result(resp)
        self.assertEqual('PAID', resp['results'][0]['data']['tier'])
