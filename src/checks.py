"""Decide whether a freshly built guide is safe to publish."""

MAX_BYTES = 95 * 1024 * 1024
FIRST_RUN_MIN_CHANNELS = 1000
MIN_SHARE_OF_LAST_NIGHT = 0.8
MIN_SHARE_WITH_UPCOMING = 0.5


def find_problems(stats, size_bytes, previous_status=None):
    problems = []
    last_night = (previous_status or {}).get("channels")
    if stats.channels == 0:
        problems.append("the guide has no channels")
    elif last_night and stats.channels < MIN_SHARE_OF_LAST_NIGHT * last_night:
        problems.append(f"only {stats.channels:,} channels, down from {last_night:,} last night")
    elif not last_night and stats.channels < FIRST_RUN_MIN_CHANNELS:
        problems.append(f"only {stats.channels:,} channels; a first run needs at least {FIRST_RUN_MIN_CHANNELS:,}")
    if stats.channels and stats.channels_with_upcoming < MIN_SHARE_WITH_UPCOMING * stats.channels:
        problems.append(f"only {stats.channels_with_upcoming:,} of {stats.channels:,} channels have "
                        f"programmes in the next 24 hours")
    if size_bytes > MAX_BYTES:
        problems.append(f"the guide is {size_bytes / 1048576:.0f} MB, over the {MAX_BYTES // 1048576} MB limit")
    return problems
