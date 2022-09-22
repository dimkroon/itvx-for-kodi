
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
                         'Akamai-BM-Telemetry': '7a74G7m23Vrp0o5c9352021.75-1,2,-94,-100,Mozilla/5.0 (X11; Ubuntu; '
                                                'Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0,uaend,11059,'
                                                '20100101,nl,Gecko,5,0,0,0,407540,66425,1680,1010,1680,1050,1680,925,'
                                                '1680,,cpen:0,i1:0,dm:0,cwen:0,non:1,opc:0,fc:1,sc:0,wrc:1,isc:85,vib:'
                                                '1,bat:0,x11:0,x12:1,5657,0.507668991253,828175033212.5,0,loc:-1,2,-94,'
                                                '-131,-1,2,-94,-101,do_en,dm_en,t_dis-1,2,-94,-105,0,-1,0,0,2422,113,'
                                                '0;0,-1,0,0,1102,520,0;1,0,0,0,1465,883,0;-1,2,-94,-102,0,0,0,0,2422,'
                                                '113,0;0,-1,1,0,1102,520,0;1,0,1,0,1465,883,0;-1,2,-94,-108,0,1,36596,'
                                                '17,0,0,883;1,1,36900,86,0,4,883;2,2,37123,17,0,4,883;3,2,37154,-2,0,0,'
                                                '883;-1,2,-94,-110,0,1,924,1519,36;1,1,941,1517,48;2,1,958,1517,61;3,1,'
                                                '974,1517,66;4,1,991,1515,101;5,1,1007,1514,148;6,1,1024,1510,244;7,1,'
                                                '1040,1514,394;8,1,1058,1542,498;9,1,1074,1586,590;10,1,1092,1630,688;'
                                                '11,1,1107,1676,804;12,1,12209,1535,243;13,1,12226,1307,277;14,1,12243,'
                                                '1157,283;15,1,12260,1017,289;16,1,12276,903,309;17,1,12292,819,333;18,'
                                                '1,12310,765,343;19,1,12326,747,332;20,1,12343,746,332;21,1,12522,751,'
                                                '338;22,1,12531,752,342;23,1,12539,750,345;24,1,12547,747,346;25,1,'
                                                '12555,740,349;26,1,12563,730,352;27,1,12570,721,353;28,1,12578,710,'
                                                '355;29,1,12586,700,355;30,1,12594,684,353;31,1,12603,669,347;32,1,'
                                                '12611,656,339;33,1,12619,633,327;34,1,12627,610,315;35,1,12635,590,'
                                                '305;36,1,12642,567,292;37,1,12651,552,281;38,1,12658,533,270;39,1,'
                                                '12672,522,262;40,1,12689,506,246;41,1,12705,497,235;42,1,12722,491,'
                                                '228;43,1,12738,488,221;44,1,12755,484,209;45,1,12771,482,204;46,1,'
                                                '12788,480,197;47,1,12805,474,188;48,1,12821,470,178;49,1,12839,465,'
                                                '173;50,1,12855,463,169;51,1,12938,465,168;52,1,12946,466,167;53,1,'
                                                '12954,468,167;54,1,12971,470,166;55,1,12987,472,166;56,1,13002,474,'
                                                '167;57,1,13010,475,169;58,1,13018,477,169;59,1,13034,479,171;60,1,'
                                                '13042,480,171;61,1,13058,481,171;62,1,13091,483,171;63,3,13609,483,'
                                                '171,520;64,4,13691,483,171,520;65,2,13691,483,171,520;66,1,14115,483,'
                                                '172;67,1,14131,483,174;68,1,14138,483,176;69,1,14155,483,178;70,1,'
                                                '14163,483,180;71,1,14170,483,184;72,1,14178,483,185;73,1,14186,482,'
                                                '188;74,1,14194,482,191;75,1,16084,482,211;76,1,16093,483,212;77,1,'
                                                '16110,483,215;78,1,16127,483,219;79,1,16144,484,221;80,1,16161,485,'
                                                '228;81,1,16177,486,234;82,1,16194,487,238;83,1,16209,488,244;84,1,'
                                                '16227,489,250;85,1,16243,490,252;86,1,16260,491,253;87,1,16444,491,'
                                                '251;88,1,16458,492,250;89,1,16475,492,248;90,1,16491,492,246;91,1,'
                                                '16499,493,245;92,1,16523,493,244;93,1,16539,493,242;94,3,16643,493,'
                                                '242,883;95,4,16746,493,242,883;96,2,16746,493,242,883;97,1,17603,495,'
                                                '241;98,1,17610,497,239;99,1,17620,500,238;100,1,17628,505,237;101,1,'
                                                '17637,516,236;102,1,17645,527,233;103,1,17651,543,231;104,1,17659,558,'
                                                '226;105,1,17667,579,220;178,3,34798,494,238,883;179,4,34902,494,238,'
                                                '883;180,2,34902,494,238,883;363,3,42958,402,420,1242;364,4,43052,402,'
                                                '420,1242;365,2,43062,402,420,1242;-1,2,-94,-117,-1,2,-94,-111,-1,2,'
                                                '-94,-109,-1,2,-94,-114,-1,2,-94,-103,3,54;2,2792;3,13596;2,19337;3,'
                                                '33579;-1,2,-94,-112,https://www.itv.com/hub/user/signin-1,2,-94,-115,'
                                                '151444,1689766,32,0,0,0,1841177,43071,0,1656350066425,6,17719,4,366,'
                                                '2953,8,0,43074,1726698,1,1,49,139,1456603985,26067385,PiZtE,40243,51,'
                                                '0,-1-1,2,-94,-106,-1,0-1,2,-94,-119,-1-1,2,-94,-122,0,0,0,0,1,0,0-1,2,'
                                                '-94,-123,-1,2,-94,-124,-1,2,-94,-126,-1,2,-94,-127,-1,2,-94,-70,'
                                                '-844419666;149504396;dis;,7;true;true;true;-120;true;24;24;true;false;'
                                                '1-1,2,-94,-80,5392-1,2,-94,-116,996378-1,2,-94,-118,168110-1,2,-94,'
                                                '-129,,,0,,,,0-1,2,-94,-121,;7;1;0'
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
