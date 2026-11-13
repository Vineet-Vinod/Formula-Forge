"""The bounded Spa bank refinement retains the existing terrain datum."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BankRefinement:
    core_bounds_m: tuple[float, float, float, float]
    subdivisions: int = 48
    transition_cells: int = 1
