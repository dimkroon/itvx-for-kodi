# ----------------------------------------------------------------------------------------------------------------------
#  Copyright (c) 2025 Dimitri Kroon.
#  This file is part of plugin.video.viwx.
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt
# ----------------------------------------------------------------------------------------------------------------------


from resources.lib.parsex import timecode2seconds


class Interval:
    __slots__ = ['start', 'end']
    # Ignore intervals less than this.
    MIN_INTERVAL = 5

    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end

    @property
    def interval(self):
        return self.end - self.start

    @classmethod
    def from_dict(cls, time_code):
        """Create in Interval object from a dict in a format as found in time codes
        in playlists from itvx.

        :param dict time_code: a dict with keys `StartTime` and `EndTime`, and their
            value must be in the format `hh:mm:ss:ms`, where ms has 3 digits and all
            others 2.
        :returns: An Interval object, or None if `time_code` is invalid,
        :rtype: Interval

        """
        try:
            start = timecode2seconds(time_code['StartTime'])
            end = timecode2seconds(time_code['EndTime'])
            if end - start >= cls.MIN_INTERVAL:
                # return Interval(start, end)
                return cls(start, end)
        except (KeyError, TypeError):
            pass
        return None

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
    # The maximum number of seconds between the end of one interval and the start
    # of the next for both to be merged into one event.
    MERGE_GAP = 2

    def __init__(self, *timecodes):
        raw_intervals = (Interval.from_dict(tc) for tc in timecodes)
        self._intervals = self._merge_intervals(raw_intervals)
        self._total = None

    @property
    def total_seconds(self):
        if self._total is None:
            self._total = sum(ival.interval for ival in self._intervals)
        return self._total

    @property
    def skip_from_start(self):
        """True when the first skip interval is at the start of the video."""
        return self._intervals[0] and self._intervals[0].start <= self.MERGE_GAP

    def _merge_intervals(self, intervals):
        """Merge overlapping intervals, or intervals that start no longer
        than `MERGE_GAP` seconds after the previous ends."""
        sorted_ivals = sorted((ival for ival in intervals if ival))
        if not sorted_ivals:
            return []

        prev_ival = sorted_ivals[0]
        merged_ivals = [prev_ival]
        for next_ival in sorted_ivals[1:]:
            if prev_ival.end + self.MERGE_GAP >= next_ival.start:
                prev_ival.end = max(prev_ival.end, next_ival.end)
            else:
                merged_ivals.append(next_ival)
                prev_ival = next_ival
        return merged_ivals

    def add(self, new_item=None):
        if isinstance(new_item, dict):
            new_item = Interval.from_dict(new_item)
        if not isinstance(new_item, Interval):
            raise ValueError(f"Invalid object: '{new_item}'.")
        self._intervals.append(new_item)
        new_intervals = self._merge_intervals(self._intervals)
        self._intervals.clear()
        self._intervals.extend(new_intervals)

    def pop(self):
        return self._intervals.pop(0)

    def __bool__(self):
        return len(self._intervals) > 0

    def __len__(self):
        return len(self._intervals)

    def __iter__(self):
        return iter(self._intervals)

    def __delitem__(self, idx):
        del self._intervals[idx]

    def __getitem__(self, idx):
        return self._intervals[idx]


