"""Tests for :pymeth:`main.PlaybackMonitor._is_effectively_complete`.

This predicate is the core of the Task #255 fix — the bug was that the
previous fixed 95% gate let 23-minute episodes (Simpsons 4x03) escape
"watched" marking when stopped in the last 3 minutes.  These tests pin the
two-threshold rule (``≤180s remaining`` OR ``≤8% remaining``).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Primary bug case
# ---------------------------------------------------------------------------

def test_simpsons_4x03_is_complete(main):
    """Primary bug from Task #255.

    Simpsons 4x03 runtime is 23:01 (1381s).  User reports they'd stop at
    ~21:50 (1310s) — which is 94.86%, under the old 95% gate — yet the
    episode *should* be treated as watched.
    """

    assert main.PlaybackMonitor._is_effectively_complete(1310, 1381) is True


# ---------------------------------------------------------------------------
# Seconds-from-end threshold (180s)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "position, duration",
    [
        # Exactly at the seconds-from-end boundary, on a long movie where the
        # percent rule would not kick in.
        (9820, 10000),   # 180s remaining on a ~2h46m movie
        (9900, 10000),   # 100s remaining
        (9999, 10000),   # 1s remaining
        (10000, 10000),  # finished
    ],
)
def test_within_seconds_threshold_marks_complete(main, position, duration):
    assert main.PlaybackMonitor._is_effectively_complete(position, duration) is True


def test_just_outside_seconds_threshold_on_long_movie(main):
    """A 10000s movie stopped with 181s left (98.19%) is still within the
    8% rule, so it must count as complete."""

    # Sanity: percent-remaining = 1.81%, well under 8%, still complete.
    assert main.PlaybackMonitor._is_effectively_complete(9819, 10000) is True


def test_long_movie_well_before_end_is_not_complete(main):
    """A 10000s movie stopped at 8000s (80%) — 2000s remain — is not complete."""

    assert main.PlaybackMonitor._is_effectively_complete(8000, 10000) is False


# ---------------------------------------------------------------------------
# Percent-from-end threshold (8%)
# ---------------------------------------------------------------------------

def test_at_percent_threshold_marks_complete(main):
    """Exactly 8% remaining — boundary is inclusive."""

    # 92% of 10000 = 9200, remaining 800 = 8.0% exactly.
    assert main.PlaybackMonitor._is_effectively_complete(9200, 10000) is True


def test_just_below_percent_threshold_marks_complete(main):
    # 93% played (7% remaining) on a short episode.
    assert main.PlaybackMonitor._is_effectively_complete(1284, 1381) is True


def test_just_above_percent_threshold_is_not_complete(main):
    """91% watched on a short episode — 9% remains, both rules fail."""

    # Episode: 1381s runtime.  Stopped at 1256s -> 125s remaining (9.05%).
    # Seconds rule: 125 > 180? No. But percent: 9.05% > 8%.  So false.
    # Correction: 125s < 180s, so seconds rule *would* trigger.  Use a
    # longer episode to isolate the percent rule.
    # 3600s (1h) show stopped at 3276s -> 324s remain (9%).
    assert main.PlaybackMonitor._is_effectively_complete(3276, 3600) is False


def test_half_way_is_not_complete(main):
    assert main.PlaybackMonitor._is_effectively_complete(600, 1200) is False


# ---------------------------------------------------------------------------
# Degenerate / defensive inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "position, duration",
    [
        (0, 1000),      # no progress
        (-5, 1000),     # negative progress
        (500, 0),       # zero duration
        (500, -100),    # negative duration
        (0, 0),         # both zero
        (None, None),   # both None — the real callers pre-coerce, but the
                        # predicate should still refuse
    ],
)
def test_degenerate_inputs_return_false(main, position, duration):
    # ``None`` needs to fail gracefully — the production code only passes
    # numeric values, but the predicate's guard clause accepts falsy values.
    try:
        result = main.PlaybackMonitor._is_effectively_complete(position, duration)
    except TypeError:
        # None/None is explicitly guarded by the ``not duration`` branch, so
        # a TypeError from arithmetic means we reached comparisons we
        # shouldn't have — fail the test loudly.
        pytest.fail("predicate should short-circuit on falsy inputs")
    assert result is False


def test_position_beyond_duration_is_complete(main):
    """Pathological inputs where position > duration still mean 'watched'."""

    # remaining = max(0, duration - position) = 0, so any positive duration
    # is treated as complete.
    assert main.PlaybackMonitor._is_effectively_complete(1500, 1381) is True


# ---------------------------------------------------------------------------
# Plan regression cases — lifted straight from the task plan note.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "position, duration, expected, label",
    [
        (1310, 1381, True, "Simpsons 4x03, 94.86% — primary bug"),
        (1381, 1381, True, "episode fully played"),
        (1380, 1381, True, "1s before end"),
        (1205, 1381, True, "176s remain — within 180s of end"),
        (1000, 1381, False, "27.6% remaining — resume point"),
        (700, 1381, False, "~50% — resume point"),
        (100, 1381, False, "near start — resume point"),
        (0, 1381, False, "not started"),
        (1500, 1500, True, "exactly at end"),
        (5400, 5400, True, "full-length movie"),
    ],
)
def test_plan_regression_matrix(main, position, duration, expected, label):
    actual = main.PlaybackMonitor._is_effectively_complete(position, duration)
    assert actual is expected, (
        f"{label}: _is_effectively_complete({position},{duration}) "
        f"→ {actual}, expected {expected}"
    )


# ---------------------------------------------------------------------------
# Constants are exposed so they stay trivially tweakable.
# ---------------------------------------------------------------------------

def test_thresholds_are_class_constants(main):
    assert main.PlaybackMonitor.COMPLETE_SECONDS_FROM_END == 180
    assert main.PlaybackMonitor.COMPLETE_PERCENT_FROM_END == pytest.approx(0.08)
