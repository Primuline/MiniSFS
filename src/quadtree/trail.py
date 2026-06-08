"""Trail buffer implementation.

Uses collections.deque to maintain a fixed-length history of positions for each body.
Provides rewind, trail retrieval, and fade-out functionality.

Typical usage::

    buffer = TrailBuffer(maxlen=300)
    buffer.push_frame(body_id, x, y)      # Append per frame
    buffer.push_all(bodies)                # Batch append
    trail = buffer.get_trail(body_id)      # Get trail
    pos = buffer.rewind(body_id, frames=60)  # Rewind 60 frames
    buffer.clear(body_id)                  # Clear single body
    buffer.clear_all()                     # Clear all
"""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from src.config import MAX_TRAIL_LENGTH
from src.core.interfaces import ITrailBuffer
from src.core.types import X, Y, IS_ACTIVE

# Fade frames: number of frames the trail persists after a body disappears
FADE_FRAMES: int = 60


class TrailBuffer(ITrailBuffer):
    """Trail buffer, maintains historical coordinate trajectories for each body.

    Uses ``collections.deque`` as the underlying storage with a fixed maximum length.
    Supports per-frame appending, time rewind, trail sequence retrieval, and fade-out effects.

    When a body disappears (collision, merger, or deletion), the trail does not vanish immediately.
    Instead, it fades out gradually via ``_fade_counters`` over FADE_FRAMES frames.

    Attributes:
        maxlen: Maximum trail points per body
        fade_frames: Number of frames for fade-out
    """

    def __init__(
        self,
        maxlen: int = MAX_TRAIL_LENGTH,
        fade_frames: int = FADE_FRAMES,
    ) -> None:
        """Initialize the trail buffer.

        Args:
            maxlen: Maximum trail points per body (default MAX_TRAIL_LENGTH)
            fade_frames: Number of frames for fade-out (default FADE_FRAMES)
        """
        self._maxlen = maxlen
        self._fade_frames: int = fade_frames
        self._trails: Dict[int, deque] = {}
        self._fade_counters: Dict[int, int] = {}

    # ------------------------------------------------------------------
    # ITrailBuffer interface methods
    # ------------------------------------------------------------------

    def push_frame(self, body_id: int, x: float, y: float) -> None:
        """Append a frame of coordinates to the specified body's trail.

        If the body has no trail yet, automatically creates a new deque.
        If the previous frame for this body_id shows a large jump
        (> 1e12 m, indicating that array compaction mapped a different body to this ID),
        automatically clears the old trail and starts recording fresh.

        Args:
            body_id: Body ID
            x: Current frame x-coordinate
            y: Current frame y-coordinate
        """
        if body_id not in self._trails:
            self._trails[body_id] = deque(maxlen=self._maxlen)
        else:
            dq = self._trails[body_id]
            if dq:
                lx, ly = dq[-1]
                # Detect body_id reuse: normal displacement < 1e10m, array compaction jump > 1e11m
                if (x - lx) ** 2 + (y - ly) ** 2 > 1e20:
                    dq.clear()
        self._trails[body_id].append((float(x), float(y)))

    def push_all(self, bodies: np.ndarray, exclude: Optional[set] = None) -> None:
        """Append trail frames for the current positions of all active bodies.

        After appending, starts fade counters for trails of bodies that have disappeared.
        Trail data is only deleted when the counter reaches FADE_FRAMES.

        Args:
            bodies: Body state array of shape (N, NUM_FIELDS)
            exclude: Optional set of body IDs to exclude (e.g., bodies being grabbed/dragged)
        """
        if exclude is None:
            exclude = set()
        active_set = set(int(idx) for idx in np.where(bodies[:, IS_ACTIVE] == 1.0)[0])
        for body_id in active_set:
            if body_id in exclude:
                continue
            self.push_frame(body_id, float(bodies[body_id, X]), float(bodies[body_id, Y]))
        # Stale trail handling: don't delete trails of disappeared bodies, start fade counter
        stale = [bid for bid in self._trails if bid not in active_set]
        for bid in stale:
            self._fade_counters[bid] = self._fade_counters.get(bid, 0) + 1
            if self._fade_counters[bid] >= self._fade_frames:
                del self._trails[bid]
                del self._fade_counters[bid]

    def get_trail(self, body_id: int) -> List[Tuple[float, float]]:
        """Get the trail coordinate list for the specified body (oldest to newest).

        Args:
            body_id: Body ID

        Returns:
            Coordinate list [(x1, y1), (x2, y2), ...], empty list if no trail exists
        """
        if body_id not in self._trails:
            return []
        return list(self._trails[body_id])

    def rewind(self, body_id: int, frames: int) -> Optional[Tuple[float, float]]:
        """Return the coordinates of the specified body from `frames` frames ago.

        Reads from the deque history; frames=0 returns the most recent frame.
        Returns None if history is shorter than `frames`.

        Args:
            body_id: Body ID
            frames: Number of frames to rewind (>= 0)

        Returns:
            (x, y) coordinates, or None if insufficient history
        """
        if body_id not in self._trails:
            return None
        dq = self._trails[body_id]
        if len(dq) <= frames:
            return None
        # deque supports indexed access (Python 3.5+)
        # Forward index 0 = oldest, -1 = newest
        # To rewind from the newest by `frames`, count from the tail
        return dq[-(frames + 1)]

    def clear(self, body_id: int) -> None:
        """Clear the trail and fade counter for the specified body.

        If the body does not exist, does nothing.

        Args:
            body_id: Body ID
        """
        self._trails.pop(body_id, None)
        self._fade_counters.pop(body_id, None)

    def clear_all(self) -> None:
        """Clear trails and fade counters for all bodies."""
        self._trails.clear()
        self._fade_counters.clear()

    # ------------------------------------------------------------------
    # Extension methods
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of bodies currently tracked."""
        return len(self._trails)

    def get_all_trails(self) -> Dict[int, List[Tuple[float, float]]]:
        """Get trail data for all bodies.

        Returns:
            Dictionary of {body_id: [(x, y), ...]}
        """
        return {bid: list(dq) for bid, dq in self._trails.items()}

    def has_trail(self, body_id: int) -> bool:
        """Check whether the specified body has trail data.

        Args:
            body_id: Body ID

        Returns:
            True if trail data exists
        """
        return body_id in self._trails and len(self._trails[body_id]) > 0

    def get_fade_factor(self, body_id: int) -> float:
        """Get the trail fade factor for the specified body.

        Active bodies return 1.0 (no fade).
        Fading bodies return (FADE_FRAMES - counter) / FADE_FRAMES.
        Bodies with no trail return 1.0.

        Args:
            body_id: Body ID

        Returns:
            Fade factor (0.0 ~ 1.0), 1.0 = fully visible, 0.0 = fully transparent
        """
        if body_id not in self._fade_counters or body_id not in self._trails:
            return 1.0
        counter = self._fade_counters[body_id]
        return max(0.0, 1.0 - counter / self._fade_frames)

    def get_fade_factors(self) -> Dict[int, float]:
        """Get trail fade factors for all bodies.

        Returns:
            Dictionary of {body_id: fade_factor}, active bodies have factor 1.0
        """
        result: Dict[int, float] = {}
        for bid in self._trails:
            result[bid] = self.get_fade_factor(bid)
        return result
