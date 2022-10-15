
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
                         'Akamai-BM-Telemetry': 'e=cGxObkJ6ZG1rcnRhNk8rRXhreThCdTZzWnovSFVVKzluUzVTL3dvSEwzR0paTUN2eXZZ'
                                                'MTFzT1F3Yi8rWndNMGZIakV6dzhDdlpMTXB6MFFPcThrRHFZMWV6V0k4MU9QZndBRTczeE'
                                                'JHWHFIV0svQXRkNzdudlV3Sm1hT3d4SUpmazJKUmF3UGlrNWZ2UnVXQTk3c1M4bVdteVly'
                                                'UytBZmlDaWhXWkJsenBRazRYYURvamJESnFQYXQrZ3RIZGwyUVk=&&&sensor_data=Mjs'
                                                '4ODg4ODg4Ozc3Nzc3Nzc7NzQsNCwwLDEsNSw0ODtXLCZMKDpCNnBgPHNnZEMqXjlgKTdUc'
                                                'HxCWzRiUUY1fjBpcTt+Mlk1OTlRIy0wZVsrbk9uK0g5L0dhMHFuXmRYZ0JFeV8qQntjezI'
                                                '8PiluSGIuWDo5MXhrNVQ/V2RXS3olcnJPN2RoZV9sWmw8PHhme1B6XnU3MTZVJGJPcHUwJ'
                                                'TwgMHhrKVFVWSBHJGpaNzh9KVk+YkwwN2Jid2xyeCwzSz9uQDFiKS0zXSZ4bENiRzUpdkk'
                                                'hSFViMFNVSFRlKX1LTUh3QnN8TmE1YF0sOC4zeytsVi5eZ3VPNSMjLT9pdTsxI0hRXVhwL'
                                                'loqK2pyYnZzfl1lLmogOXJNRUlobjlPdiokOVR9b3k1akpJOjo9USppUyggNX1CfGZjYzE'
                                                '8bSZXZiw2RShsJDhxXWVUbWArM0U0LFRCVUEla3x3QVVweyw4aXV6b1J3MHteNmgrK0pFb'
                                                'W5yaEhyKHRqeixgZ1duRl0+SmNDO1oyfmdmdChGYCsmNEAsJEtpV11yfmRwU3tmLVhtKyA'
                                                'gQm1jT19oNkN5KENEbVhHdEc+PWBqRXZQI2ppdDJLSEF2RjswU1cvNmckTV8ka2w/eHt3O'
                                                'ko0YFd5bEB3OjBfam5sbmgtMm0ya3lTX1pZJVUzRjdGJWk5OndeO208Ym14VjU2MVtsKU9'
                                                'Le0VoIC04cjxbay5lNXdrT0QtcTNlcChkT1ZgLEp2PSNOb0chdjRya2A3Sn1iSj8heixXJ'
                                                'F9sdnFOZmdXWEpwXXxuKF1oK3NOa3JXMCB0Yk9RKXk0Rl9yXkhoZVpFZWZXIGZTS2woOj9'
                                                'ee15SRzJVbDkqdj1+QVZOQWJrVnNdPSZyWihlPD0zfVNuVzctICovLj1+YkNkPiUgTWJQI'
                                                'HBEOX5sUi9AalpnKUxDe35FMDI7MDl6aHBUZWUlQyRlWj5vW0tZOTNhKCxdKkosckRZKkN'
                                                'rQCwpSVhaV1Z9ZnVLKkBVTV8kRnl0SFlLU2d1Smh2XWFKaGAraD10fUYsd3x1JHVqW0t4U'
                                                '15XP3ZxWnp8RUlofj0sL1ZDUl84IF1JREldSlk7Q2VGVm1KUikvRE1zKlRefld3WDwqakF'
                                                'adm18czIyM2xKKSF+WVQxNDBjcEJZITJTYmtIKU1kTih3di8yRUtnWV1Nfj1WSS02O3UvT'
                                                'mxBWyg1ODJ8MVk4Iy8jNnFsdTAsI29hfEoyczs8aX5iL1J0SFNsVk92QS5mcn07QnZ7RT9'
                                                'RM35BfW82cCVVI2AsZChUeTIvIT5palhhLChEcF47UF9JT3I+OzlXaDk5WC5kNGIkSjk/b'
                                                'TkyIT9UJC9ld0wvcFpfXWttYSxEd1U8dFk0bkJPTlMjZ11beXpac0ZhQVJpYGZIJCksSnN'
                                                'ULHVaRnZXLldXVzlBdn02UStUJUV2OlllbEB8KS9dOG10UiglWzhsRlJPQigoOFlxRDpUK'
                                                'WIpQVBNQiQ7M3o7QXNzUS4peUAqPUorbzAsZy1lTEx1ZjEgLUJQbzM3IUx6ITJGcSZPMWd'
                                                '4ME5rJWhWLHJHOChIdkc0dGs2cS5ySTcwMSgra3lDLT1nZEdtflMgb05CIXE2aiVEODxQd'
                                                '049QCkxWz4lYGBKYzswIUBhOFU9d29bc05+d2k0YjBHN3AkdCoxMy03cFosVVpIezV3XU8'
                                                '5Jnd2TTNbKSl7THNsV1lKaHAzIzx+bzg6eXo9YkYpfnNxYFtAMzQlLzFlNzRxKiZLS3d3M'
                                                'iNzPmp8IVIhdFlsS1tFRC8hVy0vbnVVKjFTWCUmTVppWVhBdyYqKTQrfHtsJnYqc11AeH4'
                                                '4JEpXSmt5WlB0JEM7Qy1veyRoRkMuNzBMR05RQndecihzT1JjICxSbzdRdml3YVJtfFotQ'
                                                'jFWTV1uIWx6XkFKZ09AR00qPGgtUnQ3PlE0IEhlTjFCMEtJdnhwMDx2NChSNygtRWg2bSt'
                                                'ne1JOP15dSDIwanooOnpJTnZzSDt4THVrZHUpVHxReVZLMzRxK29CYmFLY18tOF0mPEVRR'
                                                'D1wMyswSF8zVTt0Yi9YezEsL1kjdm82P2ghS1kzO1hIR3hJS0VtX2I5X0ZJdU1lajM/Ozl'
                                                'CNltkUkl+THAoO0ZCfE1gXi9NIGRQN25PNlZ4SjJtQU4/ZyRjb158VmhIKjhxTV1nKlU/c'
                                                'nNTSnRoNnZ9el5MSEt0MXk3fUQqQGZsfl1EVF8yaGA5fm5tVTBlTFZxTDRCQXk8dUkrY0V'
                                                'vMW9VQF0+UCxiWDZCKyRwUTp0KEI5by47bDkrVkBvNiZiSHZwaSE4bk9OQkQuKHNwUzZOb'
                                                'mAjay4yeTtOSHdwLG0tRjouTGdJPD18KnhbJiplT145fXk6cTdyVnIpQm48WDZUTUIkQil'
                                                '5aWVyb358dChRd0lIP2Eja0lQdCtkVS4gOm9dWC9PVS9KRFNfbGpwYEVzS0tEMipqRVFGM'
                                                'zApaEJnSDlJbVZKKD5KYVd9LC0lfGIuIUF1TD1fMX1Yb3lbTnZWY2RKKXJieyNERnYpNn4'
                                                'wZj1AWistV0BESUVDUDc6Wz47KDV2fW0vNWNoREhkVmJBLDlDflldP0pXWlhqZlQ2eSpCO'
                                                'mNnXilCYn1GMiwyYm9kazBqUFFDXUd2aiAgIWNZWX5oTFdTejppKVh0RDxHQDFRYVYzOit'
                                                'BSHV3NDI2IWIqOTh5OD9nLFp7UXhFTW1ZSHkkfGF3dDkxKnQ4Lz5+XjtnZ01mfktpS2hWf'
                                                'kJNeGpALFpHOlZOdyBOVygkfCUjRyB2bC1FdEkvVDphN05pa2s3Z1RRaXNEYCxFanQtLCh'
                                                'eK3ooR2Y0a1IvcEUgRF9fZT5tZkAjQTh1XSNGVntqdUElNShbbV8gdElIeFsmQlVXQHl5a'
                                                'SlHfX11P3EtV1FgNW58JEx9Z0A2Z2V9cjhnbz4gVU1VeVJiNCBVYzJbKGtTL2xeL0xERyV'
                                                'kTzshW0gwelsgSCU0VS1ZOmlFbzhTZEkzPVY+Z145On1iaGkxelVDM3wwPXpDLFFAczMmW'
                                                'WcmdjhQOHJPQF9vLGFDeXhoRzolTjp6T0hneWV3UyFoJjYxfHNoQSN8cCpveWxuTC5aISh'
                                                'eIDZ8VUkgdV9TLmc6Nj88XX5qRC1DUE1yYFZGNVQkeSFNbFV+IE5fNzBxL3M/O0BsRyBze'
                                                'GstJTo8RzMmVnwqIVVxXzVHIzJ6Zkw3cTY0OGo+NnwzMUZMb3Mjb15Hd3p9TiBnSkw8TkM'
                                                '+IXVBbkcxazo+IWlKclE3PFEmOnxLYHJNc29gXWFqXmM/Rm1KYmdLKSh8Ri5kJkAwe3VLT'
                                                'DA7WjJsWllkWiBgfnJwPXMsTjF5eXgqQm00YWkpKkR6WCEmeERTPTFOcm0uKXlTO355akF'
                                                'RVX01QCxVPzdDSTApTGtQJCMmQUNqaitzKmpTITkhcCslWnloZk9rPkhXRjxjeWNTWGB3K'
                                                'FBfe3glaWspTDkwTGEtSl5aPykpNFJIOms4KHl2flRaLj5TaHZsYntVXVFedUokX0NiYWw'
                                                'pQj85bjowLDtTdSBZajVHa15TdE5KR34laDkjXURoR2cwNyxzMzIpV2UxQHc9bXo0NDdtN'
                                                '0pNcC94PW15YnRxQW10dlYoJC5SZkFPNFs7R21gcj0kMz13NHZXQyZxSzU3Oj4hJU5ZTEt'
                                                'TMGJGYUhXNy5EIF50dV16cUg/ISBiUyhdZ31XPVlTKk1+V0dyV3BBTWNGZkRZNWteUTgwJ'
                                                'GtfNnB+MSlvIzM2MXJ7LWlJb1ZOeWBHaTFmQjV9JW50Zlc7bTNXNTRJaUFfUClzZElnTVd'
                                                '2al8pP19vcDFeKGhTKCF7KmRSTmU+WDcjZ1JKIFtDWG99aSpZQSQwezs2SDkxKGcuW1tHc'
                                                'y5ySEUuL3JjN3hGZmxqaz4hSkJLYFlsc3RZS3lRU0twPyVlUU9NOzFwWypPYFojZ1hJQ1B'
                                                'meykvNzd5WyxCQnE+fGtfaGZYTTooKDE0Qn1CTz1SUCQmRkplV1k0Yi50Nlt9aGlraGZ4Y'
                                                'lF0VWh9Sjg2JktXICRXVH4gJl0vPis9dkVHaFtocn1pY0QlKkArOnJ4LE5oJURkfi8ycV1'
                                                'kXWdFJTROVWdkbWppUjJFZls4SkZjfmJoR1IoKTssZy4+JnB1ciouVVdDWXZTNk90Y1Nxa'
                                                'kJfLVc7T2hNNCxSOVRHNEI6U2g1KFpUZks5WH13YXwuYixvI2UtXWx6fHs6ZVZFVmArKFN'
                                                'jJjZOME9SLHZ7NE92SCxVOGY/U2ptZC9ZYEdkbDlNIz1baHd0amBmb0Q/UDlfIXVgR0NdR'
                                                'yVJTWBOUnBzQSFlcStfOGooP2Q8XUNsb3Fpbm1rZzB6ICReMmg8WkU6Z0VqOUppcHVQL0B'
                                                'Jdzd8WlM5JFg3bEBDWCRpc3ZNWzdXP2pyQFNkfnVhb3VNJWVCP3ohWUd7U1d3VkBJNH5FL'
                                                'FI1WUtbODtrLX0zQyNMSCwmeG1WRSlnaX1wVWdVUnJlL35NM2M9OmZGPkxjSU54bGdfWUo'
                                                '6IFttLS1wMj9vRS9mUjN6TSM1V0c7aHdbPUgvQCszISNdQmorJntFUDRvTygvXmMtZXxFR'
                                                'jMwIHcyTEpfU11UO0c8NnMhdkFiQ3J0SFMtYlY+ajEpLGEqKE9ZTjx3NyY8bTw0aGptKlI'
                                                '9fnh+ZVdEOG89Z0VqSlBdW1piIDs0SUp1L21GT0F8MG9RfGdmaXBMK2I6SU09SU5JVmgoJ'
                                                'kVSblhhKWp9YlcxLm5jZHJmYlpMfFFhelkqLypDR2ooUi5obGpHKz5aM2ZYU1NPXy5wWl0'
                                                '6aSM3VU9bX3o3WyNEUWVoclo3U3JMKWF8P3FHR1JUYDV3JFArcXksS2s6Ujc6WUN7ZyNbL'
                                                'WdXUlFeMzE6TkI/LXc9TWYuQVN2JmkuYXtMYWwmUWxncDZObyUqVWRkdTx2aHxLPDZLYjJ'
                                                'MLEs1TyQxakU5XiF+bHhyQkteLHRWcVZXbWZCMlVyMCtCeVF7VGkwKnxNcXFkKSFaYzNSe'
                                                'iE5L35bJioyS189OVojPzBHMV9SXy5eZV92fExtIVZRPGdTVCVnXWsoVDFiWjZtTDFfJSM'
                                                'oaD1yLyhLfkJCWyxecXBzSlQ1TW07e1hAY3JaPWosMUEjY1JwQGE2Sj5aNVUpfDBoSmNvP'
                                                'mtPNTF8aEdDX0ZFcD19LUBhLkY3fn0kSn4tPy1XeDRbPzBobElgPTRhOU9nTjRKaTVSPGl'
                                                'TKXs6UXE5fm8pXiNYWC8/KTh6VEQzRWVWR2JnI3htaiNXUHVVaipzdCpmMXFrVV9sYXpKM'
                                                'Ec0XURAXzhKKHo5TSh+Si9Pb2dmfkMkSHBwVGxUeyU6THY5OjpqcVswMWxfQUx6X3M4RUV'
                                                '3PipqdmwlIzYzeCt7QnQhfkBiRCYkfGxRVzcjP3JqeUJKbFlAXyUtTk9YQEFzRVVNJko3f'
                                                'HltcGxxQENUMkFAeExIO1NUbC5OUmlRWSVhdHZQfitQX2BoWGxMQH5JVmpDIXltMjtjd04'
                                                '6OVlfdm45OSE/SzlAQV8/W1FPfU9sc1pJQj1lZUlgKjNUU2Q5KzFUNEdoakdwYzA3MWpse'
                                                'jkod1VoNCZEcikvSzRrKjkvRzRBTC92PTUvaXdwUmV3aVk+W0UhPDMyWF8gcyY6K3E8VkU'
                                                'ob2RMMX0lP0BGOipQbmRManpCdUdzVmo+WWhjVzxCNjQ1LFVmbTtpbCZyYDNaK0E8dVJMV'
                                                'CxlNmh7STQtUCp5ey5STnBGV3ouRzozMjg5NU1ee3pYZW9IJTdZUl80V3chKT5leTRtcXw'
                                                '4OTVURzZFbUYtX1Z6dkdBR3h3ek4tMTVMW0Bdc1UvR2lkezV5L2xYVWtOPnphbC5UJC8sb'
                                                'E06PFBKej59dnxDQ15wVjpJTU9VQnNvT3wrKkh7fUIgY3Z7R2hFZ1cjYTNaYGhbNiVgSnF'
                                                'rQEA2JWxhP3owPCRlfTxdKm8zTF5JbT9HYkk5WWdLJXthd1RoSzxoX3ouc2UpeW06IV1PJ'
                                                'XA2biRBPi1HbV18IXEmeSpwYk41TXtnXW8ubkgoc2FAOWRLY3whYj9UJiEleDl+VXoyblA'
                                                'lTERCayFsOEJ4cFNILWctRk9KIEBObSAjKy4+QUZdJE15fG8/aUtlKmx6Z2U4KEJ5e3g9S'
                                                'Gxea2l+fkI4UDI2ZTlBQ3V4MDhtZGpTSj8vUCsqPmtEPy5APWhuazhTfDVGT2I8PW9eTE5'
                                                'EUj1LKzJYO0RqIWZqVmpNRlVYfkU4QHtyZHpeISRqfXg7ITRwdVM7QlIvdyEjOFJwM1lvN'
                                                'y0valJzKWBAMjg6dlFTaUNgPiZBTVF+NDRaeEFNfm9kbkxeTXMhYkRMQVJTJnVBLkQqYnk'
                                                '/MXQrNmEkVHhDZSgvSj43U3VZPUxXZGw3PlJkcUtBZiN9ZzQlZyFeMGRKUm16b2QmTUk4O'
                                                'UB0ekRgIHQuemo4Xn5NeSVheF4zZkBvIDtBM2ApeHEsOllqOVgjOTs+OVkzIyVNXkdyWHw'
                                                '3NyA0ZElZKDFXW3R5UWM5SyA2RUc3dU1RW3g1RVE9dG4zRj5oNmN0dSwhP0pRRCVDcXtVW'
                                                'FQoXXV1TWhQICFdVihmJmJfdlVBLTNbJlchYXJbczdDSSRrdylefXtGYl4+Ry5GKk0reF4'
                                                '4TnozeV4/cGhORUxLfWp5LmY8Lml4Ul02K1o1Vl9XN0RWWSx0ckEjaChgaHhpVncuckozK'
                                                '3lCdmo7JXIvTkcpOlAsXj5zazxlSTQ+O0hDZlFWaEExOCsyIX02OVsjbmklSSNbP1Z0WCB'
                                                'rWnMoJCRFaEszLys9ND8sNWlkMVU+SGZZYjw0fHNKUHtzfShNREc4NXJ6bCoqQURJKCNDe'
                                                'WRmLltCTndybFlENXM1Y2RiOWxeS1NTRUNtNDYtTlksYS46JiUxWlFOSER+fj1ocHNVIGZ'
                                                'mLzFMUDdRfVZgNFo8SHtALXdLIyEveCo6eElTaHExV2cpNWkgOml7QXhSMiwxZ2BRQlA+Y'
                                                'EZMYiRKM08hZUNFR15sQlJuPy0xMnVZd0wrY2JZbWJyISkjd2M+XnVaRUBNbCVXb0Q0ICA'
                                                'rdmh9MnxXQVh3dTtGWllPNnA8W0cxW2csRHYwUzF+L0MmezBqTDZAUXp7RU1ecHNfUnQvW'
                                                '1hjb3YkYixwM1t1KG9fLVtGPF5CXXVCWXNRJHJdLWdSTmh6THBSKmU0bXwyLTBkJndiejB'
                                                'TbEZGc3w6LCtUMQ=='
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
