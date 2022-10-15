
import time
import os
import json
import uuid
import logging

from codequick.support import logger_id

from . import utils
from . import fetch
from . import kodi_utils
from .errors import *


logger = logging.getLogger(logger_id + '.account')


class ItvSession:
    def __init__(self):
        self.account_data = {}
        self.read_account_data()
        addon = utils.addon_info['addon']
        self.uname = addon.getSetting('hub-uname')
        self.passw = addon.getSetting('hub-passw')
        if self.account_data and (
                self.uname != self.account_data.get('uname') or self.passw != self.account_data.get('passw')):
            # Force a new login on a token request
            logger.warning("Stored username and/or password does not match those in the plugin's settings.")
            self.account_data = None

    @property
    def access_token(self):
        if not self.account_data:   # account data can be None or an empty dict
            self.login()
        elif self.account_data['refreshed'] < time.time() - 24 * 3600:
            # renew tokens periodically
            self.refresh()
        return self.account_data['itv_session']['access_token']

    @property
    def cookie(self):
        if not self.account_data:  # account data can be None or an empty dict
            self.login()
        elif self.account_data['refreshed'] < time.time() - 4 * 3600:
            # renew tokens periodically
            self.refresh()
        return self.account_data['cookies']['cookie_str']

    def read_account_data(self):
        session_file = os.path.join(utils.addon_info['profile'], "itv_session")
        logger.debug("Reading account data from file: %s", session_file)
        try:
            with open(session_file, 'r') as f:
                acc_data = json.load(f)
        except (OSError, IOError, ValueError) as err:
            logger.error("Failed to read account data: %r" % err)
            acc_data = None
        self.account_data = acc_data

    def save_account_data(self):
        session_file = os.path.join(utils.addon_info['profile'], "itv_session")
        with open(session_file, 'w') as f:
            json.dump(self.account_data, f)
        logger.debug("ITV account data saved to file")

    def login(self, uname=None, passw=None):
        """Perform login to itv hub.

        Post credentials. The webbrowser sends no other cookies than an akamai-bm-telemetry cookie
        """
        self.account_data = {}

        if uname is None:
            uname = self.uname

        if passw is None:
            passw = self.passw

        req_data = {
            'grant_type': 'password',
            'nonce': utils.random_string(20),
            'username': uname,
            'password': passw,
            'scope': 'content'
        }
        logger.info("trying to log in to ITV account as %s" % self.uname)
        try:
            # Post credentials
            session_data = fetch.post_json(
                'https://auth.prd.user.itv.com/auth',
                req_data,
                headers={'Accept': 'application/vnd.user.auth.v2+json',
                         'Akamai-BM-Telemetry': '7a74G7m23Vrp0o5c9379441.75-1,2,-94,-100,Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0,uaend,11059,20100101,nl,Gecko,5,0,0,0,409881,2462846,1680,1010,1680,1050,1680,925,1680,,cpen:0,i1:0,dm:0,cwen:0,non:1,opc:0,fc:1,sc:0,wrc:1,isc:85,vib:1,bat:0,x11:0,x12:1,5663,0.09571883547,832931231423,0,loc:-1,2,-94,-131,-1,2,-94,-101,do_en,dm_en,t_dis-1,2,-94,-105,0,-1,0,0,2422,113,0;0,-1,0,0,1102,520,0;1,0,0,0,1465,883,0;-1,2,-94,-102,0,0,0,0,2422,113,0;0,-1,1,0,1102,520,0;1,0,1,0,1465,883,0;-1,2,-94,-108,0,1,11374,16,0,0,883;1,1,11749,-2,0,8,883;2,3,11749,-2,0,8,883;3,2,11909,-2,0,8,883;4,2,11941,16,0,8,883;5,1,12086,-2,0,0,883;6,3,12086,-2,0,0,883;7,2,12213,-2,0,0,883;8,1,12422,-2,0,0,883;9,3,12422,-2,0,0,883;10,2,12541,-2,0,0,883;11,1,12766,-2,0,0,883;12,3,12766,-2,0,0,883;-1,2,-94,-110,0,1,1363,1044,37;1,1,1379,1029,47;2,1,1396,998,59;3,1,1413,888,96;4,1,1429,792,122;5,1,1446,698,146;6,1,1462,590,170;7,1,1478,520,186;8,1,1496,478,196;9,1,1512,442,204;10,1,1530,418,210;11,1,1546,406,216;12,1,1562,400,217;13,1,1621,400,219;14,1,1630,400,221;15,1,1742,402,221;16,1,1750,403,222;17,1,1763,405,223;18,1,1780,410,223;19,1,1795,415,224;20,1,1812,425,225;21,1,1829,431,225;22,1,1847,442,225;23,1,1863,455,222;24,1,1880,470,216;25,1,1896,487,211;26,1,1929,506,206;27,1,1930,523,199;28,1,1946,530,195;29,1,1997,531,194;30,1,2026,531,193;31,1,2029,530,191;32,1,2046,529,189;33,1,2063,527,188;34,1,2080,523,184;35,1,2095,519,182;36,1,2113,517,180;37,1,2130,516,180;38,3,2334,516,180,520;39,4,2480,516,180,520;40,2,2480,516,180,520;41,1,3070,518,178;42,1,3078,522,178;43,1,3086,525,178;44,1,3094,527,178;45,1,3099,531,178;46,1,3108,533,178;47,1,3116,535,178;48,1,3125,539,178;49,1,3133,543,178;50,1,3142,548,178;51,1,3149,554,178;52,1,3157,565,178;53,1,3165,576,179;54,1,3174,592,183;55,1,3181,617,189;56,1,3224,844,245;57,1,3240,964,271;58,1,3257,1092,297;59,1,3273,1194,305;60,1,3290,1278,309;61,1,3307,1350,307;62,1,3324,1418,297;63,1,3340,1464,289;64,1,3357,1506,285;65,1,3373,1544,281;66,1,3390,1590,275;67,1,3407,1626,269;68,1,3423,1648,261;69,1,3440,1652,251;70,1,3456,1654,247;71,1,3629,1653,247;72,1,3637,1649,248;73,1,3646,1649,250;74,1,3654,1649,251;75,1,3670,1651,252;76,1,3687,1657,239;77,1,3704,1664,225;78,1,3721,1672,213;79,1,3737,1677,205;80,1,7228,1617,184;81,1,7244,1537,200;82,1,7260,1405,218;83,1,7278,1159,238;84,1,7294,973,254;85,1,7311,775,262;86,1,7329,557,270;87,1,7345,357,274;88,1,7361,197,284;89,1,7378,83,268;90,1,7395,9,236;91,1,7411,-1,-1;92,1,7606,4,218;93,1,7615,9,219;94,1,7622,21,222;95,1,7630,39,222;96,1,7638,64,224;97,1,7646,94,224;98,1,7654,128,218;99,1,7663,160,216;100,1,7671,192,214;101,1,7678,218,214;102,1,7686,250,214;139,3,8277,480,178,520;140,4,8409,480,178,520;141,2,8409,480,178,520;176,3,10288,510,244,883;177,4,10391,510,244,883;178,2,10391,510,244,883;234,3,20817,406,425,1242;235,4,20936,406,425,1242;236,2,20942,406,425,1242;-1,2,-94,-117,-1,2,-94,-111,-1,2,-94,-109,-1,2,-94,-114,-1,2,-94,-103,3,51;2,6537;3,8264;-1,2,-94,-112,https://www.itv.com/hub/user/signin-1,2,-94,-115,169649,606167,32,0,0,0,775783,20959,0,1665862462846,6,17820,13,237,2970,8,0,20960,652788,1,1,49,951,-446417374,26067385,PiZtE,78068,22,0,-1-1,2,-94,-106,-1,0-1,2,-94,-119,-1-1,2,-94,-122,0,0,0,0,1,0,0-1,2,-94,-123,-1,2,-94,-124,-1,2,-94,-126,-1,2,-94,-127,-1,2,-94,-70,-844419666;149504396;dis;,7;true;true;true;-120;true;24;24;true;false;unspecified-1,2,-94,-80,6510-1,2,-94,-116,332483235-1,2,-94,-118,171916-1,2,-94,-129,,,44f5478a49e419c98b42237f92350e68f367f4784614425eab4847066ff6289d,,,,0-1,2,-94,-121,;8;1;0'
                         }
            )

            self.account_data = {
                'uname': self.uname,
                'passw': self.passw,
                'refreshed': time.time(),
                'itv_session': session_data,
                'cookies': {
                    'Itv.Cid': str(uuid.uuid4()),
                }
            }
            cookie_str = self.build_cookie(session_data['access_token'], session_data['refresh_token'])
            self.account_data['cookies']['cookie_str'] = cookie_str
        except FetchError as e:
            # Testing showed that itv hub returned error 400 on failed logins, but accept 401 as well.
            logger.error("Error logging in to ITV account: %r" % e)
            if isinstance(e, AuthenticationError) or (isinstance(e, HttpError) and e.code == 400):
                raise AuthenticationError(
                        "Login to ITV hub failed. Please edit account in settings.")
            else:
                raise
        else:
            self.save_account_data()

    def refresh(self):
        """Refresh tokens.
        Perform a get request with the current renew token in the param string. ITV hub will
        return a json formatted string containing a new access token and a new renew token.

        """
        logger.debug("Refreshing ITV account tokens...")
        try:
            token = self.account_data['itv_session']['refresh_token']
            url = 'https://auth.prd.user.itv.com/token?grant_type=refresh_token&' \
                  'token=content_token refresh_token&refresh=' + token
            # Refresh requests require no autorization header and no cookies at all
            resp = fetch.get_json(
                url,
                headers={'Accept': 'application/vnd.user.auth.v2+json'},
                timeout=10
            )
            new_tokens = resp
            session_data = self.account_data['itv_session']
            session_data.update(new_tokens)
            sess_cookie_str = self.build_cookie(session_data['access_token'], session_data['refresh_token'])
            logger.debug("New session cookie: %s" % sess_cookie_str)
            self.account_data['cookies']['cookie_str'] = sess_cookie_str
            self.account_data['refreshed'] = time.time()
            self.save_account_data()
            return True
        except (KeyError, ValueError, FetchError) as e:
            logger.warning("Failed to refresh ITVtokens - %s: %s" % (type(e), e))
        except TypeError:
            logger.warning("Failed to refresh ITV tokens - No account data present.")
        return False

    def build_cookie(self, access_tkn, refresh_tkn):
        cookiestr = ''.join(
            ('Itv.CookiePolicy.v2=accepted; Itv.Region=ITV|null; Itv.Cid=',
             self.account_data['cookies']['Itv.Cid'],
             '; Itv.Session={%22tokens%22:{%22content%22:{%22entitlement%22:{%22purchased%22:'
             '[]%2C%22failed_availability_checks%22:[]%2C%22source%22:%22%22}%2C%22email_verified%22:true%2C%22'
             'access_token%22:%22',
             access_tkn,
             '%22%2C%22token_type%22:%22bearer%22%2C%22refresh_token%22:%22',
             refresh_tkn,
             '%22}}%2C%22sticky%22:true}'
             )
        )
        return cookiestr


_itv_session_obj = None


def itv_session():
    global _itv_session_obj
    if _itv_session_obj is None:
        _itv_session_obj = ItvSession()
    return _itv_session_obj


def fetch_authenticated(funct, url, **kwargs):
    """Call one of the fetch function with user authentication.

    Call the specified function with authentication header and return the result.
    If the server responds with an authentication error, refresh tokens, or
    login and try once again.

    To prevent headers argument to turn up as both positional and keyword argument,
    accept keyword arguments only, apart from the callable and url.

    """
    account = itv_session()

    for tries in range(2):
        try:
            if 'headers' in kwargs.keys():
                kwargs['headers'].update({
                    'cookie': itv_session().cookie,
                    'Authorization': 'Bearer ' + account.access_token})
            else:
                kwargs['headers'] = {'cookie': itv_session().cookie, 'Authorization': 'Bearer ' + account.access_token}

            return funct(url=url, **kwargs)
        except AuthenticationError:
            if tries == 0:
                if account.refresh() is False:
                    if not (kodi_utils.show_msg_not_logged_in() and account.login()):
                        raise
            else:
                raise
