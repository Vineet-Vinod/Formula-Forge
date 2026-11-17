"""Finite reconstructed joins between retained pit-floor height controls."""
from __future__ import annotations

import itertools
import math
from dataclasses import replace

from pit_routes_dataclasses import PitFloorTransition, PitRoute


def resolve_floor_joins(route: PitRoute) -> tuple[PitRoute,list[PitFloorTransition]]:
    sections = route.sections
    grades = [abs(b.z-a.z)/math.hypot(b.x-a.x,b.y-a.y) for a,b in itertools.pairwise(sections)]
    intervals: list[tuple[int,int]] = []
    for index,grade in enumerate(grades):
        if grade<=.20:
            continue
        first = max(0,index-10)
        last = min(len(sections)-1,index+11)
        while abs(sections[last].z-sections[first].z)/(sections[last].distance-sections[first].distance)>.15:
            first = max(0,first-5)
            last = min(len(sections)-1,last+5)
            if last-first>=70:
                raise ValueError('No bounded pit-floor ramp between source controls')
        if intervals and first<=intervals[-1][1]:
            intervals[-1] = (intervals[-1][0],max(last,intervals[-1][1]))
        else:
            intervals.append((first,last))
    result = list(sections)
    proof: list[PitFloorTransition] = []
    for first,last in intervals:
        a,b = sections[first],sections[last]
        maximum_change = 0.0
        for index in range(first,last+1):
            section = sections[index]
            t = (section.distance-a.distance)/(b.distance-a.distance)
            height = a.z+(b.z-a.z)*t
            maximum_change = max(maximum_change,abs(height-section.z))
            result[index] = replace(section,z=height,cross_slope=a.cross_slope+(b.cross_slope-a.cross_slope)*t)
        proof.append(PitFloorTransition(a.distance,b.distance,a.z,b.z,max(grades[first:last]),
            abs(b.z-a.z)/(b.distance-a.distance),maximum_change,
            'Finite estimated entry/exit ramp between retained source-derived level controls. XY and both outside height fields unchanged. This interpolation resolves a pointwise projection/old-paving join; it is not a surveyed pit section. Source/native apron and contact review required.'))
    return replace(route,sections=result),proof
