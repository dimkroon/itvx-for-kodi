
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
        print(strm)
        print(key_service)

    def test_get_stream_hdntl_cookie(self):
        acc = itv_account.itv_session()
        manifest, key_service, subtitles = itv.get_live_urls('ITV2')
        resp = requests.request('get', manifest, allow_redirects=False)
        cookies = resp.cookies
        hdntl_cookie = cookies.get('hdntl')
        print(hdntl_cookie)

    def test_get_live_schedule(self):
        schedule = itv.get_live_schedule()
        assert isinstance(schedule, list)
        s = json.dumps(schedule, indent=4)
        print(s)

    def test_submenu_live(self):
        main.sub_menu_live()


class UtilsTests(unittest.TestCase):
    def test_get_addon_info(self):
        addon_inf = utils.addon_info
        self.assertIsInstance(addon_inf, dict)


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




if __name__ == '__main__':
    unittest.main()
