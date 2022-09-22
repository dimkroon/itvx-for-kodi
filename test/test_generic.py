
from __future__ import unicode_literals
import six
import unittest
import json
import time

import requests

from resources.lib import itv
from resources.lib import utils
from resources.lib import itv_account
from resources.lib import main

import io


class MyTestCase(unittest.TestCase):

    def test_get_stream_url(self):
        acc = itv_account.itv_session()
        strm, key_service = itv.get_live_urls('ITV2')
        six.print_(strm)
        six.print_(key_service)

    def test_get_stream_hdntl_cookie(self):
        acc = itv_account.itv_session()
        manifest, key_service, subtitles = itv.get_live_urls('ITV2')
        resp = requests.request('get', manifest, allow_redirects=False)
        cookies = resp.cookies
        hdntl_cookie = cookies.get('hdntl')
        six.print_(hdntl_cookie)

    def test_get_live_schedule(self):
        schedule = itv.get_live_schedule()
        assert isinstance(schedule, list)
        s = json.dumps(schedule, indent=4)
        six.print_(s)

    def test_submenu_live(self):
        main.sub_menu_live()


class UtilsTests(unittest.TestCase):
    def test_get_addon_info(self):
        addon_inf = utils.addon_info
        self.assertIsInstance(addon_inf, dict)


class ItvAccount(unittest.TestCase):
    def test_itv_session_instantiation(self):
        s = itv_account.ItvSession()
        self.assertIsInstance(s, itv_account.ItvSession)

    def test_login(self):
        s = itv_account.ItvSession()
        s.uname = 'kkist6000000@hotmail.com'
        s.passw = 'Papap0elie'
        s.login()


class SubtitleTest(unittest.TestCase):
    def test_new_parse_xml(self):
        fname = '/home/dim/.kodi/userdata/addon_data/plugin.video.itv/Subtitles/itv.xml'
        f = open(fname, 'r')
        xml_data = f.read()
        f. close()

        fname = '/home/dim/.kodi/userdata/addon_data/plugin.video.itv/Subtitles/itv.srt'
        f = io.open(fname, 'w', encoding='utf-8')
        st = time.time()
        utils.xml_to_srt(xml_data, f)
        f.close()
        et = time.time()
        print('Used time: {}s'.format(et -st))

    def test_old_parse_xml(self):
        ifname = '/home/dim/.kodi/userdata/addon_data/plugin.video.itv/Subtitles/itv.xml'
        f = io.open(ifname, 'r', encoding='utf-8')
        xml_data = f.read()
        f. close()

        ofname = '/home/dim/.kodi/userdata/addon_data/plugin.video.itv/Subtitles/itv.srt'
        st = time.time()
        utils.xml_to_srt(xml_data, ofname)
        et = time.time()
        print('Used time: {}s'.format(et - st))


# class ProxyTest(unittest.TestCase):
#     @classmethod
#     def setUpClass(cls):
#         cls.http_proxy = proxy.HTTPServer(None, ('', proxy.PROXY_PORT))
#         threadStarting = threading.Thread(target=cls.http_proxy.serve_forever)
#         threadStarting.start()
#         cls.proxy_thread = threadStarting
#
#     @classmethod
#     def tearDownClass(cls):
#         cls.http_proxy.shutdown()
#         if cls.proxy_thread is not None:
#             cls.proxy_thread.join()
#             cls.proxy_thread = None
#
#     def test_proxy_get(self):
#         acc = itv_account.itv_session()
#         acc.uname = 'kkist6000000@hotmail.com'
#         acc.passw = 'Papap0elie'
#         manifest_url, key_service = main.get_live_urls('ITV2')
#         manifest_url = 'http://127.0.0.1:{}/itv/{}'.format(proxy.PROXY_PORT, manifest_url[8:])
#         resp = requests.request(
#             'GET',
#             manifest_url,
#             timeout=600,
#             headers = {
#                 'Sec-Fetch-Dest': 'empty',
#                 'Sec-Fetch-Mode': 'cors',
#                 'Sec-Fetch-Site': 'same-site',
#                 'Pragma': 'no-cache',
#                 'Cache-Control': 'no-cache'
#             },
#             allow_redirects=True
#         )
#         s = resp.status_code
#         h = resp.headers
#         c = resp.cookies
#         six.print_(h)


if __name__ == '__main__':
    unittest.main()
