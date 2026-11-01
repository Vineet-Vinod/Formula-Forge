#pragma once

#include "FFSimulation.hpp"

struct FFReplayPose {
    int frame;
    double time;
    Vec2 position;
    float elevation;
    float heading;
    float speed;
    float steer;
    float pitch;
    float roll;
    float rpm;
    int gear;
    double lapSeconds;
    bool grounded;
    bool chase;
    bool invalid;
};

FFReplayPose InterpolateReplayPose(const FFReplayPose& First, const FFReplayPose& Second, double Time);
