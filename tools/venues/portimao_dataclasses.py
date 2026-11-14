from dataclasses import dataclass

from circuit_dataclasses import Point


@dataclass(frozen=True)
class StandFrame:
    center: Point
    axis: Point
    rear: Point
    width: float
    datum: float
    roof: float
