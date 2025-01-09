# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------

from collections import abc

from resources.lib.parsex import timecode2seconds



class Interval:
    __slots__ = ['start', 'end']

    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end

    @property
    def interval(self):
        return self.end - self.start

    def __bool__(self):
        return self.interval > 0

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            raise ValueError
        return self.start == other.start and self.end == other.end

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            raise ValueError
        return self.start < other.start or (self.start == other.start and self.end < other.end)

    def __le__(self, other):
        if not isinstance(other, type(self)):
            raise ValueError
        return self.start < other.start or (self.start == other.start and self.end <= other.end)


class SkipIntervals():
    # Intervals of less than this are ignored.
    MIN_INTERVAL = 5
    # The maximum number of seconds between the end of one time and the start
    # of the next time code for both to be merged into one event.
    MERGE_GAP = 2

    def __init__(self, *timecodes):
        raw_intervals = (self._parse_timecode(tc) for tc in timecodes)
        self._intervals = self._merge_intervals(raw_intervals)
        self._iter = iter(self._intervals)
        self._total = None

    @property
    def total_seconds(self):
        if self._total is None:
            self._total = sum(ival.interval for ival in self._intervals[:-1])
        return self._total

    @property
    def skip_from_start(self):
        """True when the first skip interval is at the very start of the video."""
        return self._intervals[0] and self._intervals[0].start <= self.MIN_INTERVAL

    def _parse_timecode(self, time_code):
        if time_code is not None:
            start = timecode2seconds(time_code.get('StartTime'))
            end = timecode2seconds(time_code.get('EndTime'))
            if end - start >= self.MIN_INTERVAL:
                # return Interval(start, end)
                return Interval(start, end)
        else:
            return None

    def _merge_intervals(self, intervals):
        sorted_offsets = sorted((interval for interval in intervals if interval))
        if not sorted_offsets:
            return []

        prev_offset = sorted_offsets[0]
        merged_offsets = [prev_offset]
        for next_offset in sorted_offsets[1:]:
            if prev_offset.end + self.MERGE_GAP >= next_offset.start:
                prev_offset.end = max(prev_offset.end, next_offset.end)
            else:
                merged_offsets.append(next_offset)
                prev_offset = next_offset
        merged_offsets.append(Interval(float('inf'),float('inf')))
        return merged_offsets

    def pop(self):
        return self._intervals.pop(0)

    def __bool__(self):
        return len(self._intervals) > 1

    def __len__(self):
        return len(self._intervals) -1

    def __iter__(self):
        return self

    def __next__(self):
        return self._iter.__next__()

    def __delitem__(self, idx):
        del self._intervals[idx]

    def __getitem__(self, idx):
        return self._intervals[idx]

    def add(self, new_item=None):
        if isinstance(new_item, dict):
            item_keys = tuple(new_item.keys())
            if not all(k in item_keys for k in ('StartTime', 'EndTime')):
                raise ValueError(f"Incompatible compatible dict object: '{new_item}'.")
            new_item = self._parse_timecode(new_item)
        elif not isinstance(new_item, Interval):
            raise ValueError(f"Invalid object: '{new_item}'.")
        self._intervals.append(new_item)
        self._intervals = self._merge_intervals(self._intervals)


