#include "FFBodySupport.hpp"
#include <cmath>

FFBodyFloorMargins FFBodyFloorExpansion(double heightSpan,
        const std::array<double, 3>& vertical, const std::array<double, 3>& scale) {
    if (heightSpan < 0.0 || vertical[2] <= 0.5 || scale[0] <= 0.0 || scale[1] <= 0.0 || scale[2] <= 0.0) return {};
    return {heightSpan * std::abs(vertical[0] * scale[2] / (vertical[2] * scale[0])),
        heightSpan * std::abs(vertical[1] * scale[2] / (vertical[2] * scale[1])), true};
}
