#include "FFReplayTimeline.hpp"

#include <algorithm>
#include <cmath>

FFReplayPose InterpolateReplayPose(const FFReplayPose& first, const FFReplayPose& second, double time) {
    time = std::clamp(time, first.time, second.time);
    if (time >= second.time) return second;
    FFReplayPose result = first;
    const float fraction = static_cast<float>((time - first.time) / (second.time - first.time));
    result.time = time;
    result.position = first.position + (second.position - first.position) * fraction;
    result.elevation = std::lerp(first.elevation, second.elevation, fraction);
    result.heading = first.heading + wrapAngle(second.heading - first.heading) * fraction;
    result.speed = std::lerp(first.speed, second.speed, fraction);
    result.steer = std::lerp(first.steer, second.steer, fraction);
    result.pitch = std::lerp(first.pitch, second.pitch, fraction);
    result.roll = std::lerp(first.roll, second.roll, fraction);
    result.rpm = std::lerp(first.rpm, second.rpm, fraction);
    result.lapSeconds = std::lerp(first.lapSeconds, second.lapSeconds, static_cast<double>(fraction));
    return result;
}
