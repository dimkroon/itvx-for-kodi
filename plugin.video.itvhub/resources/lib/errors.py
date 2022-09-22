

class FetchError(IOError):
    pass


class AccountError(Exception):
    def __init__(self, descr):
        super(AccountError, self).__init__(descr)


class AuthenticationError(FetchError):
    def __init__(self, msg=None):
        super(AuthenticationError, self).__init__(
            msg or u'Login required')


class GeoRestrictedError(FetchError):
    def __init__(self, msg=None):
        super(GeoRestrictedError, self).__init__(
            msg or u'Service is not available in this area')


class HttpError(FetchError):
    def __init__(self, code, reason):
        self.code = code
        self.reason = reason
        super(HttpError, self).__init__(u'Connection error: {}'.format(reason))


class ParseError(FetchError):
    def __init__(self, msg=None):
        super(ParseError, self).__init__(
            msg or u'Error parsing data')
