# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
import time

from test.support import fixtures
fixtures.global_setup()

import unittest
from unittest.mock import patch
import os

from resources.lib import itv_account
from support.object_checks import is_not_empty

import requests


setUpModule = fixtures.setup_web_test


class Pair(unittest.TestCase):
    headers = {
        'accept': 'application/vnd.user.auth.v2+json',
        'origin': 'https://app.10ft.itv.com',
        'referer': 'https://app.10ft.itv.com/'
    }

    def test_paring(self):
        # Request code
        pairing_code = self.get_code()

        # Verify code every 3 seconds
        for _ in range(2):
            self.verify(pairing_code, expect_success=False)
            time.sleep(3)

        # Enter the code
        self.enter_code(pairing_code)

        # Verify once again
        time.sleep(1)
        self.verify(pairing_code, expect_success=True)

    # @unittest.skip("This test will take over 10 minutes to complete.")
    def test_verify_timing(self):
        """Verification must be done within 5 minutes after entering the code in a webbrowser."""
        # pairing_code = self.get_code()
        # print(f"Pairing with code {pairing_code}")
        # time.sleep(1)
        # self.enter_code(pairing_code)
        # time.sleep(295)
        # self.verify(pairing_code, expect_success=True)

        pairing_code = self.get_code()
        print(f"Pairing with code {pairing_code}")
        time.sleep(60)
        self.enter_code(pairing_code)
        time.sleep(400)
        self.verify(pairing_code, expect_success=False)

    def get_code(self):
        resp = requests.get('https://auth.prd.user.itv.com/generate/code', headers=self.headers, timeout=15)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        self.assertEqual(1, len(data))  # Just to flag when more info becomes available.
        pairing_code = data['code']
        self.assertTrue(is_not_empty(pairing_code, str))
        return pairing_code

    def verify(self, pairing_code, expect_success=False):
        verify_url = f'https://auth.prd.user.itv.com/verify/{pairing_code}'
        resp = requests.get(url=verify_url, headers=self.headers)
        if expect_success:
            self.assertEqual(200, resp.status_code, f"Unexpected verify response: {resp.status_code}: '{resp.text}'")
            data = resp.json()
            self.assertEqual(1, len(data))
            itv_account.parse_token(data['token'])  # verify it's a real token.
        else:
            self.assertEqual(404, resp.status_code, f"Unexpected verify response: {resp.status_code}: '{resp.text}'")
            data = resp.json()
            self.assertEqual(3, len(data))  # Just to flag when more info becomes available.
            self.assertEqual("Code Not Found", data['error'])
            self.assertEqual("Code Not Found", data['error_description'])

    def enter_code(self, pairing_code: str):
        """What is normally done in a web browser."""
        token = itv_account.itv_session().account_data['itv_session']['refresh_token']
        self.assertGreater(len(token), 10)      # Ensure we have valid token.
        resp = requests.post(
            url='https://auth.prd.user.itv.com/validate/code',
            headers={
                'user-agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0',
                'accept': 'application/vnd.user.auth.v2+json',
                'origin': 'https://www.itv.com',
                'referer': 'https://www.itv.com/'
            },
            timeout=5,
            json={'code': pairing_code,     # Must be of type string!
                  'token': token})

        self.assertEqual(200, resp.status_code, f"Unexpected enter response: {resp.status_code}: '{resp.text}'", )
        print("Response entering code: '{}'".format(resp.text))


    def test_enter_code(self):
        self.enter_code('376096')

    def test_verify_code(self):
        self.verify('376096')