
# ------------------------------------------------------------------------------
#  Copyright (c) 2022. Dimitri Kroon
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#
#  This file is part of plugin.video.cinetree
#
#  Plugin.video.cinetree is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or (at your
#  option) any later version.
#
#  Plugin.video.cinetree is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#  or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  plugin.video.cinetree. If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

from codequick import Route, Listitem
# noinspection PyProtectedMember
from codequick.listing import strip_formatting


def patch_cc_route():
    """
    Fixes a bug in codequick v1.0.2. by monkey patching
    ``codequick.route.Route.__call__(...)``.

    The problem is that decorating a callback with ``@Route.Register(cache_ttl=60)``
    does not lead to the items the callback returns being cached.

    This will be fixed if you call ``patch_cc_route()`` in the addon before
    ``codequick.run()`` is being called.

    """
    original_call = Route.__call__

    def patched_call(self, route, args, kwargs):
        self.__dict__.update(route.parameters)
        original_call(self, route, args, kwargs)

    Route.__call__ = patched_call


def patch_label_prop():
    """
    Fixes an annoyance in codequick v1.0.2. by monkey patching
    ``codequick.listing.Listitem.label`` property.

    The problem is that setting label on a codequick Listitem will always
    set info['title'] as well, overwriting any existing value.
    It is very nice that codequick ensures that relevant values are set, but
    a more appropriate approach would be to only set those the addon developer
    has not already set.

    This will be fixed if you call ``patch_label_prop()`` in the addon before
    ``codequick.run()`` is being called.

    """
    def label_setter(self, label):
        """Set label and only copy to fields that do not already have a value"""
        self.listitem.setLabel(label)
        unformatted_label = strip_formatting("", label)
        self.params.setdefault("_title_", unformatted_label)
        self.info.setdefault("title", unformatted_label)

    Listitem.label = Listitem.label.setter(label_setter)
