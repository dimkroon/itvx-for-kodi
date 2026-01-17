# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
from __future__ import annotations

import os
import json
import socket
import time

from collections.abc import Sequence, Iterable, MutableMapping

import xbmc
import requests

from datetime import datetime, date, timezone, timedelta
from bisect import bisect_left, bisect_right
from operator import itemgetter

from codequick import Script, Resolver, Route
from codequick.support import build_path


# Logo URLs from now/next.
CHANNELS = {
    'ITV1': {'id': 'viwx.itv1',
             'name': 'ITV1',
             'logo': 'https://images.ctfassets.net/bd5zurrrnk1g/'
                     '54OefyIkbiHPMJUYApbuUX/7dfe2176762fd8ec10f77cd61a318b07/itv1.png?w=512',
             'preset': 1},
    'ITV2': {'id': 'viwx.itv2',
             'name': 'ITV2',
             'logo': 'https://images.ctfassets.net/bd5zurrrnk1g/'
                     'aV9MOsYOMEXHx3iw0p4tk/57b35173231c4290ff199ef8573367ad/itv2.png?w=512',
             'preset': 2},
    'ITVBe': {'id': 'viwx.itvbe',
              'name': 'ITVBe',
              'logo': 'https://images.ctfassets.net/bd5zurrrnk1g/'
                      '6Mul5JVrb06pRu8bNDgIAe/b5309fa32322cc3db398d25e523e2b2e/itvBe.png?w=512',
              'preset': 3},
    'ITV3': {'id': 'viwx.itv3',
             'name': 'ITV3',
             'logo': 'https://images.ctfassets.net/bd5zurrrnk1g/'
                     '39fJAu9LbUJptatyAs8HkL/80ac6eb141104854b209da946ae7a02f/itv3.png?w=512',
             'preset': 4},
    'ITV4': {'id': 'viwx.itv4',
             'name': 'ITV4',
             'logo': 'https://images.ctfassets.net/bd5zurrrnk1g/'
                     '6Dv76O9mtWd6m7DzIavtsf/b3d491289679b8030eae7b4a7db58f2d/itv4.png?w=512',
             'preset': 5}
}


class ChannelSchedule(Sequence):
    """Class containing programme information of a single channel in JSON-EPG
    format.

    """
    TIME_FMT = '%Y-%m-%dT%H:%M:%SZ'

    def __init__(self, channel: str, programmes: Iterable[dict]):
        self.channel = channel
        self._pgm_list = sorted(programmes, key=itemgetter('start'))

    @property
    def programme_list(self):
        return self._pgm_list

    def filter(self, from_time: datetime = None, to_time: datetime = None):
        """Return a new `ChannelSchedule` object with programmes starting between
        `from_time` and `to_time`.

        """
        by_start_time = itemgetter('start')
        if from_time:
            start_idx = bisect_left(self._pgm_list, from_time.strftime(self.TIME_FMT), key=by_start_time)
        else:
            start_idx = 0
        if to_time:
            end_idx = bisect_left(self._pgm_list, to_time.strftime(self.TIME_FMT), lo=start_idx, key=by_start_time)
        else:
            end_idx = len(self._pgm_list)
        return type(self)(self.channel, self._pgm_list[start_idx:end_idx])

    def update_programme_info(self, schedule: ChannelSchedule):
        """Merge the info from `schedule` into the current programmes.

        Based on the programme start time, update the programme info of each programme
        with the corresponding item from `schedule`. All fields that already exist
        will be overwritten if they are present and not None in `schedule`, except
        the programme's end time.

        """
        # Disregard seconds and timezone offset.
        schedule = {item['start'][:16]: item for item in schedule}
        for prgrm_info in self._pgm_list:
            new_info = schedule.get(prgrm_info['start'][:16])
            if new_info:
                # Ensure not to overwrite with None values and programme end time.
                valid_fields = {k: v for k, v in new_info.items() if v is not None and k != 'stop'}
                prgrm_info.update(valid_fields)

    def extend(self, schedule: ChannelSchedule | list):
        """Add programmes from `schedule` that have a start time later than the
        current last programme.

        """
        if not isinstance(schedule, (ChannelSchedule, list)):
            raise TypeError(f"Invalid type {type(schedule).__name__}.")
        if isinstance(schedule, ChannelSchedule):
            new_prgrms = schedule._pgm_list
        else:
            new_prgrms = schedule

        if self._pgm_list:
            last_pgm_start: str = self._pgm_list[-1]['start']
            idx = bisect_right(new_prgrms, last_pgm_start, key=itemgetter('start'))
            self._pgm_list.extend(new_prgrms[idx:])
        else:
            self._pgm_list = new_prgrms[:]

    def __getitem__(self, item):
        result = self._pgm_list.__getitem__(item)
        if isinstance(result, list):
            # return slice
            return type(self)(self.channel, result)
        else:
            # return item
            return result

    def __iter__(self):
        return iter(self._pgm_list)

    def __len__(self):
        return len(self._pgm_list)

    def __eq__(self, other):
        return (isinstance(other, ChannelSchedule)
                and self.channel == other.channel
                and self._pgm_list == other._pgm_list)


class Epg(MutableMapping):
    """Container to hold the schedules of several channels."""
    def __init__(self):
        self._chan_schedules = {}

    @property
    def json_epg(self) -> dict:
        """Return the whole EPG as JSON-EPG formatted Python data structure."""
        epg_data = {name: schedule.programme_list for name, schedule in self._chan_schedules.items()}
        return epg_data

    @classmethod
    def from_json_epg(cls, json_epg: dict) -> Epg:
        """Create a new Epg object from a JSON-EPG formatted Python data structure."""
        new_epg = cls()
        try:
            for chan_name, pgm_list in json_epg.items():
                schedule = ChannelSchedule(chan_name, pgm_list)
                new_epg.add_schedule(schedule)
        except Exception as err:
            xbmc.log(f"[plugin.video.viwx.iptv] Failed to create Epg from JSON-EPG: {repr(err)}.")
        return new_epg

    def add_schedule(self, schedule: ChannelSchedule):
        self._chan_schedules[schedule.channel] = schedule

    def filter(self, from_time: datetime = None, to_time: datetime = None) -> Epg:
        """Return a new `Epg` object with programmes starting between
        `from_time` and `to_time`.

        """
        new_epg = type(self)()
        for chan_name, schedule in self._chan_schedules.items():
            new_epg.add_schedule(schedule.filter(from_time, to_time))
        return new_epg

    def update_programme_info(self, new_epg: Epg):
        """Based on the programme start time, update the programme info of each programme
        of each channel with the info of the corresponding item in `new_epg`. All fields
        that already exist will be overwritten if they are present and not None in
        `schedule`, except the programme's end time.

        """
        for chan_name, schedule in self._chan_schedules.items():
            new_schedule = new_epg.get(chan_name)
            if new_schedule:
                schedule.update_programme_info(new_schedule)

    def extend(self, new_epg: Epg):
        """Add programmes from `new_epg` that start later than the last programmes already
         in the EPG. Add channels from new_epg if not present in the current EPG.

         Earlier programmes are disregarded.

         """
        if not isinstance(new_epg, Epg):
            raise TypeError(f"Param 'new_epg' should be an 'Epg' object not {type(new_epg).__name__}.")
        my_schedules = self._chan_schedules
        other_schedules = new_epg._chan_schedules
        for chan_name, schedule in my_schedules.items():
            if chan_name in other_schedules:
                schedule.extend(other_schedules[chan_name])
        for other_name, other_sched in other_schedules.items():
            if other_name not in my_schedules:
                my_schedules[other_name] = other_sched

    def __setitem__(self, key, value):
        if not isinstance(value, ChannelSchedule):
            raise TypeError(f"Invalid type. Must be a ChannelSchedule object, not '{type(value).__name__}'.")
        self._chan_schedules[key] = value

    def __getitem__(self, key):
        return self._chan_schedules[key]

    def __delitem__(self, key):
        del self._chan_schedules[key]

    def __len__(self):
        return len(self._chan_schedules)

    def __iter__(self):
        return self._chan_schedules.__iter__()


# IPTVManager class from https://github.com/add-ons/service.iptv.manager/wiki/Integration
class IPTVManager:
    """Interface to IPTV Manager"""

    def __init__(self, port):
        """Initialize IPTV Manager object"""
        self.port = port

    def via_socket(func):
        """Send the output of the wrapped function to socket"""

        def send(self):
            """Decorator to send over a socket"""
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', self.port))
            try:
                sock.sendall(json.dumps(func(self)).encode())
            finally:
                sock.close()

        return send

    @via_socket
    def send_channels(self):
        """Return JSON-STREAMS formatted python data structure to IPTV Manager"""
        callback_ref = Resolver.ref('resources.lib.main:play_stream_live')
        chan_list = [
            {
                'id': chan_data.get('id'),
                'name': chan_data.get('name'),
                'logo': chan_data.get('logo'),
                'stream': build_path(callback_ref, query={'channel': name, 'url': None})
            } for name, chan_data in CHANNELS.items()
        ]
        return {'version': 1, 'streams': chan_list}

    @via_socket
    def send_epg(self):
        """Return JSON-EPG formatted python data structure to IPTV Manager"""

        # ITV EPG has hardly more info than the programme title, but does contain
        # replay VOD links. EPG from 'What to Watch' has more info, but a smaller
        # range of available dates and often skips short programmes, like weather
        # and regional news. That's why we request both and merge WtW into ITV EPG.
        itv_epg = itv_schedule()
        wtw_epg = what_to_watch_schedule()
        schedules = merge_epg(itv_epg, wtw_epg)
        epg_data = {CHANNELS[k]['id']: v for k, v in schedules.items()}
        return dict(version=1, epg=epg_data)


@Script.register
def channels(_, port):
    try:
        IPTVManager(int(port)).send_channels()
    except Exception:
        # Catch all errors to prevent codequick showing an error message
        from traceback import format_exc
        xbmc.log("[plugin.video.viwx.iptv] Error in iptvmanager.channels:\n" + format_exc())


@Script.register
def epg(_, port):
    try:
        IPTVManager(int(port)).send_epg()
    except Exception:
        # Catch all errors to prevent codequick showing an error message
        from traceback import format_exc
        xbmc.log("[plugin.video.viwx.iptv] Error in iptvmanager.epg:\n." + format_exc())


def what_to_watch_region_id(region='london'):
    """Return the regionID of `region`."""
    region = region.lower()
    resp = requests.get('https://api.tv-guide.future.sensi.link/platforms')
    data = resp.json()

    for platform in data['platforms']:
        if platform['title'].lower() == 'freeview':
            for item in platform['regions']:
                if item['title'].lower() == region:
                    return item['id']
    return None


def what_to_watch_channel_ids(region_id):
    """Return the channels ID's from all ITV channels based on the region_id"""
    resp = requests.get('https://api.tv-guide.future.sensi.link/channels/' + region_id)
    data = resp.json()

    chan_ids = {}

    itv_channel_names = ('ITV2', 'ITV3', 'ITV4')
    for chan_info in data:
        title = chan_info['title']
        # Full title is something like 'ITV1 London', depending on the region_id.
        if 'ITV1' in title:
            chan_ids['ITV1'] = chan_info['id']
        elif title == 'ITV Quiz':
            chan_ids['ITVBe'] = chan_info['id']
        if any(name == title for name in itv_channel_names):
            chan_ids[title] = chan_info['id']
    return chan_ids


def request_wtw_epg(chan_ids):
    """Return the EPG from whattowatch.com, including only the main ITV channels.

    What to watch return no data more than a few hours in the past.
    """
    now = int(time.time())
    start_t = now - 43200
    end_t = now + 7 * 86400
    wtw_epg = Epg()
    for chan, chan_id in chan_ids.items():
        url = f'https://api.tv-guide.future.sensi.link/schedules/{chan_id}/{start_t}/{end_t}'
        resp = requests.get(url)
        data = resp.json()
        schedule = ChannelSchedule(
            chan,
            filter(None, (parse_wtw_programme(pgm_data) for pgm_data in data))
        )
        wtw_epg.add_schedule(schedule)
    return wtw_epg


def parse_wtw_programme(prgrm_data):
    """Convert programme data from 'what to watch' into the JSON-EPG format
    specified by IptvManager.

    """
    try:
        assets = prgrm_data.get('assets', {})
        summary = assets.get('summary', {})
        # Summary of some programmes, like ITV news, are an empty list.
        if not isinstance(summary, dict):
            summary = {}

        subtitle = assets['title']
        # Only include fields that actually supplement the data from the ITV guide.
        epg_item = {
            'start': prgrm_data['dateTime'][:19] + 'Z',
            'subtitle': subtitle if subtitle != 'Generic' else None,
            'description': summary.get('long') or summary.get('medium') or summary.get('short'),
            'image': prgrm_data.get('media')
        }
        episode_nr = assets.get('number')
        if episode_nr:
            series_nr = assets.get('season') or 0
            epg_item['episode'] = 'S{:02d}E{:02d}'.format(series_nr, episode_nr)
        return epg_item
    except:
        import traceback
        xbmc.log("[plugin.video.viwx.iptv] Failed to parse What-to-Watch schedule item:\n" + traceback.format_exc())
        return None


def what_to_watch_schedule():
    try:
        region_id = what_to_watch_region_id()
        itv_chan_ids = what_to_watch_channel_ids(region_id)
        wtw_epg = request_wtw_epg(itv_chan_ids)
        return wtw_epg
    except:
        import traceback
        xbmc.log("[plugin.video.viwx.iptv] Failed to create What-to-Watch EPG:\n" + traceback.format_exc())
        return {}


def itv_schedule(from_date: date = None):
    """Get the schedules of the main live channels from max a week back to a week ahead.

    These are from the HTML pages that the website uses to show schedules.
    """
    from resources.lib.itvx import get_page_data

    today = datetime.now(timezone.utc).date()
    one_day = timedelta(days=1)
    if from_date:
        # Request no more than 7 days back.
        start_day = max(from_date, today - timedelta(days=7))
    else:
        start_day = today - timedelta(days=7)
    last_day = today + timedelta(days=8)
    itv_epg = Epg()
    while start_day < last_day:
        page_data = get_page_data('/watch/tv-guide/' + start_day.strftime('%Y-%m-%d'))
        guide = page_data['tvGuideData']
        day_epg = Epg()
        for chan_name, progr_list in guide.items():
            programmes = (filter(None, (parse_itv_programme(progr) for progr in progr_list)))
            day_epg.add_schedule(ChannelSchedule(chan_name, programmes))
        itv_epg.extend(day_epg)
        start_day += one_day
    return itv_epg


def parse_itv_programme(data):
    """Parse and item from the HTML page /watch/guide.

    Used to create EPG data for IPTV manager.
    """

    genres = data.get('genres')
    try:
        item = {
            'start': data['start'][:19] + 'Z',
            'stop': data['end'][:19] + 'Z',
            'title': data['title'],
            'genre': genres[0].get('name') if genres else None,
        }

        if data.get('episodeAvailableNow'):
            callback_ref = Route.ref('resources/lib/main:play_stream_catchup')
            item['stream'] = build_path(callback_ref, query={'ccid': data.get('titleCCId', '')})
        return item
    except:
        import traceback
        xbmc.log("[plugin.video.viwx.iptv] Failed to parse ITV schedule item:\n" + traceback.format_exc())
        return None
