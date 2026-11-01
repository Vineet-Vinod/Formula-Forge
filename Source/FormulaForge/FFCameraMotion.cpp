#include "FFCameraMotion.hpp"
#include <cmath>

void FFCameraChannel::Reset(double target) {
    position = target;
    velocity = 0.0;
}

void FFCameraChannel::Step(double target, double seconds, double frequency) {
    if (seconds <= 0.0) return;
    const double omega = frequency * 2.0 * 3.141592653589793;
    const double difference = position - target;
    const double momentum = velocity + omega * difference;
    const double decay = std::exp(-omega * seconds);
    position = target + (difference + momentum * seconds) * decay;
    velocity = (velocity - omega * momentum * seconds) * decay;
}

void FFCameraMotion::Update(double height, double pitchTarget, double rollTarget, double seconds) {
    if (!initialized || seconds <= 0.0) {
        elevation.Reset(height);
        pitch.Reset(pitchTarget);
        roll.Reset(rollTarget);
        initialized = true;
        return;
    }
    elevation.Step(height, seconds, 3.0);
    pitch.Step(pitchTarget, seconds, 3.5);
    roll.Step(rollTarget, seconds, 3.5);
}
