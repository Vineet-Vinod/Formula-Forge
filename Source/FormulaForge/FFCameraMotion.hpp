#pragma once

struct FFCameraChannel {
    double position = 0.0;
    double velocity = 0.0;
    void Reset(double Target);
    void Step(double Target, double Seconds, double Frequency);
};

struct FFCameraMotion {
    FFCameraChannel elevation;
    FFCameraChannel pitch;
    FFCameraChannel roll;
    bool initialized = false;
    void Update(double Elevation, double Pitch, double Roll, double Seconds);
};
