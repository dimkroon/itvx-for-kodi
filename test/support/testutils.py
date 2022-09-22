# ------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#
#  This file is part of plugin.video.itvhub
#
#  Plugin.video.itvhub is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or (at your
#  option) any later version.
#
#  Plugin.video.itvhub is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#  or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  plugin.video.itvhub. If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

import json
import os.path
import re

from requests.models import Response


def doc_path(doc: str) -> str:
    """Return the full path to doc in the directory test_docs.
    Makes test docs accessible independent of the current working dir while
    avoiding the use absolute paths.

    .. note ::
        The directory test_docs is to a sibling of this module's parent directory

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

    Intended to be used as new object in patched tests. In particular to return
    locally saved documents instead of doing web requests.

    """
    def wrapper(*args, **kwargs):
        with open(doc_path(doc), 'r') as f:
            return f.read()
    return wrapper


class HttpResponse(Response):
    """Create a requests.Response object with various attributes set.
    Can be used as the `return_value` of a mocked request.request.

    """
    def __init__(self, status_code: int = None, headers: dict = None, content: bytes = None, reason=None):
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

