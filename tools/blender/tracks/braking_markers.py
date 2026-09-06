"""Project policy for distance boards; independent of any Blender scene or vehicle tuning."""


def marker_distances(approach_m, requires_braking=True):
    """Available distance since the previous complex exit, measured along the track.

    These are Formula Forge readability thresholds, not an FIA regulation.
    A corner complex gets one sequence, before its first braking turn.
    """
    if not requires_braking or approach_m < 100:
        return ()
    if approach_m >= 600:
        return (200, 150, 100, 50)
    if approach_m >= 300:
        return (150, 100, 50)
    if approach_m >= 150:
        return (100, 50)
    return (50,)


def plan_markers(zones, lap_length):
    result = []
    for zone in zones:
        entry = zone['entry_m']
        approach = (entry-zone['previous_exit_m']) % lap_length
        for distance in marker_distances(approach, zone.get('requires_braking',True)):
            result.append(dict(turn=zone['turn'],distance_m=distance,
                               station_m=(entry-distance)%lap_length,
                               entry_m=entry,approach_m=approach,
                               side=zone['side']))
    return result
