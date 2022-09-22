

import unittest


from resources.lib import main



class LegacyTests(unittest.TestCase):
    def test_submenushows(self):
        r = main.sub_menu_shows('https://www.itv.com/hub/shows')
        print(r)