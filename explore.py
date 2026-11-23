"""Sanity check: does the GRID data load? Prints the event types in one VALORANT series."""
from collections import Counter

from opscope.data import iter_events, load_series, series_file

series = load_series("val")
print(f"{len(series)} VALORANT series")
first = series[0]
print("First series:", first)

counts = Counter(ev.get("type") for ev in iter_events(series_file(first)))
for event_type, n in counts.most_common(30):
    print(f"{n:>7}  {event_type}")
