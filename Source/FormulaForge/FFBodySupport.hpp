#pragma once

#include <array>

struct FFBodyFloorMargins {
    double longitudinal = 0.0;
    double lateral = 0.0;
    bool valid = false;
};

FFBodyFloorMargins FFBodyFloorExpansion(double HeightSpan,
    const std::array<double, 3>& VerticalDirection, const std::array<double, 3>& Scale);
