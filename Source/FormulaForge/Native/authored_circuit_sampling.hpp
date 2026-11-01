#pragma once

#include <vector>
#include "core_math.hpp"
#include "track_catalog.hpp"

// Geographic routes have thousands of close controls. Accumulating their
// 32-subdivision arc lengths in float loses metres over a lap. This sampler
// serves only the reconstructed circuits; the legacy/Monza path is unchanged.
inline std::vector<Vec2> authoredCircuitPlan(std::span<const TrackControlPoint> controls,
        float scale, float targetLength, float units, bool mirror, int sampleCount) {
    const auto control = [&](int i) {
        const int count = static_cast<int>(controls.size());
        const auto& p = controls[(i % count + count) % count];
        return Vec2{p.x * scale, p.y * scale * (mirror ? -1.0f : 1.0f)};
    };
    std::vector<Vec2> dense;
    for (int i = 0; i < static_cast<int>(controls.size()); ++i) {
        const Vec2 p0 = control(i-1), p1 = control(i), p2 = control(i+1), p3 = control(i+2);
        for (int j = 0; j < 32; ++j) {
            const float t = static_cast<float>(j) / 32, t2 = t*t, t3 = t2*t;
            dense.push_back((p1*2.0f + (p2-p0)*t + (p0*2.0f-p1*5.0f+p2*4.0f-p3)*t2 +
                            (p3-p0+(p1-p2)*3.0f)*t3)*0.5f);
        }
    }
    const auto distances = [&]() {
        std::vector<double> arc(dense.size()+1, 0.0);
        for (std::size_t i = 0; i < dense.size(); ++i)
            arc[i+1] = arc[i] + static_cast<double>(length(dense[(i+1)%dense.size()]-dense[i]));
        return arc;
    };
    auto arc = distances();
    const float correction = static_cast<float>(static_cast<double>(targetLength)*units / arc.back());
    for (Vec2& p : dense) p *= correction;
    arc = distances();
    std::vector<Vec2> result;
    result.reserve(sampleCount);
    for (int i = 0; i < sampleCount; ++i) {
        const float progress = targetLength * static_cast<float>(i) / sampleCount;
        const double desired = static_cast<double>(progress * units);
        auto it = std::upper_bound(arc.begin(), arc.end(), desired);
        const auto index = std::min(dense.size()-1, static_cast<std::size_t>(std::max<std::ptrdiff_t>(0,it-arc.begin()-1)));
        const double span = arc[index+1]-arc[index];
        const float t = span > .001 ? static_cast<float>((desired-arc[index])/span) : 0.0f;
        result.push_back(lerp(dense[index],dense[(index+1)%dense.size()],t));
    }
    return result;
}
