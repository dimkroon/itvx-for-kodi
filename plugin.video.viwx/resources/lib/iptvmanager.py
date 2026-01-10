# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2024-2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------
import json
import socket
import time
import xbmc
import requests

from codequick.script import Script
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
        from resources.lib.main import play_stream_live
        """Return JSON-STREAMS formatted python data structure to IPTV Manager"""
        chan_list = [
            {
                'id': chan_data.get('id'),
                'name': chan_data.get('name'),
                'logo': chan_data.get('logo'),
                'stream': build_path(play_stream_live, query={'channel': name, 'url': None})
            } for name, chan_data in CHANNELS.items()
        ]
        return {'version': 1, 'streams': chan_list}

    @via_socket
    def send_epg(self):
        """Return JSON-EPG formatted python data structure to IPTV Manager"""
        from resources.lib.itvx import get_full_schedule

        # ITV EPG has hardly more info than the programme title, but does contain
        # replay VOD links. EPG from 'What to Watch' has more info, but a smaller
        # range of available dates and often skips short programmes, like weather
        # and regional news. That's why we request both and merge WtW into ITV EPG.
        itv_epg = get_full_schedule()
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
    channels_epg = {}
    for chan, chan_id in chan_ids.items():
        url = f'https://api.tv-guide.future.sensi.link/schedules/{chan_id}/{start_t}/{end_t}'
        resp = requests.get(url)
        data = resp.json()
        pgm_list = filter(None, (parse_wtw_programme(pgm_data) for pgm_data in data))
        channels_epg[chan] = sorted(pgm_list, key=lambda x: x['start'])
    return channels_epg


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


def merge_epg(master_epg, additional_epg):
    """Merge the info from `additional_epg` into `master_epg`.

    Based on the programme start time, update the programme info of `master_epg`
    with the corresponding item of `additional_epg`. All fields that already
    exist in `master_epg` will be overwritten if they are present and not None in
    `additional_epg`.

    """

    for chan, prgrm_list in master_epg.items():
        additional_prgrm_list = additional_epg.get(chan, [])
        # Convert the programmes list into dict with start time as key to make
        # lookup much easier. Seconds and time zone are stripped off, because
        # time formats may different in this respect.
        pgm_dict = {item['start'][:16]: item for item in additional_prgrm_list}
        for pgm in prgrm_list:
            additional_pgm = pgm_dict.get(pgm['start'][:16])
            if additional_pgm:
                # Ensure not to overwrite with None values and programme end time.
                new_info = {k: v for k, v in additional_pgm.items() if v is not None and k != 'stop'}
                pgm.update(new_info)
    return master_epg
