"""Group benches that sit together (one OSM node per bench, a few metres apart) into places.

Greedy, best-ranked bench first: it seeds a place, which grows breadth-first over
benches within ``LINK_M`` of any member, but only those within ``WIDTH_M`` of every
member, so no place is wider than ``WIDTH_M`` and a long promenade splits into
several places instead of chaining into one. The seed represents the place.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Sequence


LINK_M = 10.0
WIDTH_M = 25.0
_CELL = 1e-4  # degrees, ~7 m east-west and ~11 m north-south at 52°N
_M_PER_DEG = 111_320.0


def metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Equirectangular distance between (lat, lng) points; fine at these scales."""
    x = (b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(x, b[0] - a[0]) * _M_PER_DEG


def group_places(
    benches: Sequence[tuple[int, float, float]],
    link_m: float = LINK_M,
    width_m: float = WIDTH_M,
) -> list[list[int]]:
    """``benches`` are (id, lat, lng), best first. Returns places as id lists, seed first."""
    pos = {i: (lat, lng) for i, lat, lng in benches}
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, lat, lng in benches:
        grid[(math.floor(lat / _CELL), math.floor(lng / _CELL))].append(i)
    reach = math.ceil(link_m / (_M_PER_DEG * _CELL * 0.6)) + 1  # cells to scan

    def near(i: int):
        lat, lng = pos[i]
        gy, gx = math.floor(lat / _CELL), math.floor(lng / _CELL)
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                yield from grid.get((gy + dy, gx + dx), ())

    placed: set[int] = set()
    places: list[list[int]] = []
    for seed, _, _ in benches:
        if seed in placed:
            continue
        placed.add(seed)
        members, queue = [seed], deque([seed])
        while queue:
            cur = queue.popleft()
            for j in near(cur):
                if (
                    j not in placed
                    and metres(pos[cur], pos[j]) <= link_m
                    and all(metres(pos[m], pos[j]) <= width_m for m in members)
                ):
                    placed.add(j)
                    members.append(j)
                    queue.append(j)
        places.append(members)
    return places
