# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2022-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

import json
import os.path
import re

from collections.abc import Iterable
from unittest.mock import Mock
from datetime import datetime
from requests.models import Response
from resources.lib import itv_account


def doc_path(doc: str) -> str:
    """Return the full path to doc in the directory test_docs.
    Makes test docs accessible independent of the current working dir while
    avoiding the use absolute paths.

    .. note ::
        The directory test_docs is to be a sibling of this module's parent directory

    """
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '../test_docs', doc))


def open_json(filename):
    full_path = doc_path(filename)
    with open(full_path) as f:
        return json.load(f)


def is_uuid(uuid: str) -> bool:
    """Test if *uuid* is indeed a uuid"""
    return re.match(r'[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$', uuid) is not None


def open_doc(doc):
    """Returns a partial object that accepts any set of arguments and returns
    the contents of the file specified by *doc_path*.

    Intended to be used as 'new' object in patched tests. In particular to return
    locally saved documents instead of doing web requests.

    """
    def wrapper(*args, **kwargs):
        with open(doc_path(doc), 'r') as f:
            return f.read()
    return wrapper


def save_json(data, filename):
    """Save a data structure in json format to a file in the test_docs directory"""
    with open(doc_path(filename), 'w') as f:
        json.dump(data, f)


def save_doc(data, filename):
    """Save a data as text to a file in the test_docs directory"""
    with open(doc_path(filename), 'w') as f:
        f.write(data)

def save_binary(data, filename):
    """Save a data as bytes to a file in the test_docs directory"""
    with open(doc_path(filename), 'wb') as f:
        f.write(data)


class HttpResponse(Response):
    """Create a requests.Response object with various attributes set.
    Can be used as the `return_value` of a mocked request.request.

    """
    def __init__(self, status_code: int = None, headers: dict = None,
                 content: bytes = None, text: str = None, reason=None):
        super().__init__()
        if status_code is not None:
            self.status_code = status_code
        if headers is not None:
            for k, v in headers.items():
                self.headers[k] = v
        if reason is not None:
            self.reason = reason
        if content is not None:
            self._content = content
            if status_code is None:
                self.status_code = 200
                self.reason = 'OK'
        elif text is not None:
            self._content = text.encode('utf8')
            if status_code is None:
                self.status_code = 200
                self.reason = 'OK'


class mockeddt(datetime):
    mocked_now = datetime.now()

    @classmethod
    def now(cls, tz=None):
        if tz:
            return cls.mocked_now.astimezone(tz)
        else:
            return cls.mocked_now.replace(tzinfo=None)


class SessionMock(itv_account.ItvSession):
    def __init__(self, login=True, refresh=True):
        super().__init__()
        if isinstance(login, Iterable):
            self.login = Mock(side_effect=login)
        else:
            self.login = Mock(return_value=login)
        if isinstance(refresh, Iterable):
            self.refresh = Mock(side_effect=refresh)
        else:
            self.refresh = Mock(return_value=refresh)
    save_account_data = Mock()
