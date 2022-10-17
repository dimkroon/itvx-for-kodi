
from test.support import fixtures
fixtures.global_setup()

import time
import unittest
import requests

from resources.lib import itv, fetch, errors
from resources.lib import itv_account

from test.support import object_checks


setUpModule = fixtures.setup_web_test


class TestCookies(unittest.TestCase):
    def test_cookie_consent(self):
        r = requests.Session()


# ----------------------------------------------------------------------------------------------------------------------
#           JSON API
# ----------------------------------------------------------------------------------------------------------------------


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
        dotcom_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/dotcom/programmes?'
                                    'broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,'
                                    'widevine,fairplay&sortBy=title')
        ctv_resp = self.get_json('https://discovery.hubsvc.itv.com/platform/itvonline/ctv/programmes?'
                                 'broadcaster=itv&features=mpeg-dash,clearkey,outband-webvtt,hls,aes,playready,'
                                 'widevine,fairplay&sortBy=title')
        dot_com_programs = dotcom_resp['_embedded']['programmes']
        ctv_programs = ctv_resp['_embedded']['programmes']
        self.assertEqual(len(dot_com_programs), len(ctv_programs))


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
        post_data = itv.stream_req_data.copy()
        post_data['user']['token'] = acc_data.access_token
        post_data['client']['supportsAdPods'] = True
        featureset = post_data['variantAvailability']['featureset']
        featureset['min'] = featureset['max']
        return post_data

    def test_get_playlist_live(self):
        acc_data = itv_account.itv_session()
        post_data = self.create_post_data()

        for channel in ('ITV', 'ITV2', 'ITV3', 'ITV4', 'CITV', 'ITVBe'):
            url = 'https://simulcast.itv.com/playlist/itvonline/' + channel
            resp = requests.post(
                    url,
                    headers={'Accept': 'application/vnd.itv.online.playlist.sim.v3+json',
                           'Cookie': acc_data.cookie},
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
        url = 'https://magni.itv.com/playlist/itvonline/ITV4/10_1758_0023.001'

        # request playlist of an episode of Doc Martin
        # url = 'https://magni.itv.com/playlist/itvonline/ITV/1_7665_0049.001'

        # The bigger trip - episode 1
        # url = 'https://magni.itv.com/playlist/itvonline/ITV/10_2772_0001.001'

        # url = 'https://magni.itv.com/playlist/itvonline/ITV/CFD0332_0001.001'

        # NOTE:
        #    Sometimes the returned json data contains a base url of
        #    'https://itvpnpdotcom.cdn1.content.itv.com/'
        #    and other times 'https://itvpnpdotcom.blue.content.itv.com/'
        #    Important difference is that the first returns an error 403 - Forbidden,
        #    least quite often.
        #    IMPORTANT: The webbrowser seems to have the same problem. If a similar request
        #    returns an url to cdn1.content.itv.com we get the 'Oops' popup.
        #
        #    The webbrowsers sends all cookies with this request, but it also seems to work
        #    without any.
        #    Anyway; it appears that without the itv.Session coockie there is a better change
        #    to get links to blue.content.itv.com.
        # resp = requests.post(
        #     url,
        #     headers={'Accept': 'application/vnd.itv.vod.playlist.v2+json'},
        #     json=post_data)
        resp = itv_account.fetch_authenticated(
            fetch.post_json, url,
            data=post_data,
            headers={'Accept': 'application/vnd.itv.vod.playlist.v2+json'})

        return resp

    def test_get_playlist_catchup(self):
        resp = self.get_playlist_catchup()
        strm_data = resp
        object_checks.check_catchup_dash_stream_info(strm_data['Playlist'])

    def test_replace_cdn1_for_blue_in_manifest_url(self):
        """Since urls to cdn1.content.itv.com always seem to fail with http status 403 - forbidden,
        this tries to replace cdn1 for blue, as these urls always work.

        Conclusion:
            Replacing is not possible, all changed requests fail with the same http status 403.
            There is very little we can do, as the webbrowser has exactly the same problem!
        """
        for i in range(10):
            print("Try {}".format(i))
            resp = self.get_playlist_catchup()
            strm_data = resp.json()['Playlist']['Video']
            base_url = strm_data['Base']
            if 'cdn1' in base_url:
                print('    url = cnd1')
                base_url = base_url.replace('cdn1', 'blue')
            else:
                print('    url = blue')
            dash_url = base_url + strm_data['MediaFiles'][0]['Href']
            if self.test_dash_manifest(dash_url):
                print('    SUCCESS!')
            else:
                print('    FAIL!')
            time.sleep(5)

    def test_dash_manifest(self, url):
        # url = 'https://itvpnpdotcom.cdn1.content.itv.com/10-2772-0001-001/18/2/VAR028/10-2772-0001-001_18_2_VAR028.ism/.mpd?Policy=eyJTdGF0ZW1lbn' \
        #       'QiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9pdHZwbnBkb3Rjb20uY2RuMS5jb250ZW50Lml0di5jb20vMTAtMjc3Mi0wMDAxLTAwMS8xOC8yL1ZBUjAyOC8xMC0yNzcyLTAw' \
        #       'MDEtMDAxXzE4XzJfVkFSMDI4LmlzbS8qIiwiQ29uZGl0aW9uIjp7IkRhdGVMZXNzVGhhbiI6eyJBV1M6RXBvY2hUaW1lIjoxNjYzODI4OTIwfX19XX0_&Signature=SeN' \
        #       'TRPqvV~jRw59gIIEnXtG4-VvBOSfNnWflCosIAyXm2xZ1ZbUREze0X34-o1v2l1MJ4yvXKMMwDhi7Db5rM-gEq9sgm9twvv5k9sMIeynQ7aBhlafgHSc7GqwB6pQ11i5XY' \
        #       '29W5F9WfEAcPLkvH4NlXxYzYnKM4RQKofauAjImxrteCG3XAJDu-Dt~JPLR~EJ3MXtodRFJQGnydT~aukIIO3tuyBjAaUKkB1KmXi7RdkTKdO1~5PfNOLPkB3ZCvUb2jqi' \
        #       'LtUE988solFN8uzOsUKGVVdA--5zahz3RAVIcc9wp8PzDeFj~KEDzMytINmmTIpZUodmWTeu5nYWYRw__&Key-Pair-Id=APKAJB7PCFZAZHWZVIB'

        try:
            resp = itv_account.fetch_authenticated(fetch.get_document, url)
            return True
        except errors.FetchError:
            return False