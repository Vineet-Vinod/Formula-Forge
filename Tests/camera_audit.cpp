#include "FFCameraMotion.hpp"
#include <cmath>
#include <iostream>

int main() {
    FFCameraChannel fast;
    FFCameraChannel slow;
    fast.Reset(0.0);
    slow.Reset(0.0);
    for (int step = 0; step < 120; ++step) fast.Step(1.0, 1.0 / 120.0, 3.0);
    for (int step = 0; step < 30; ++step) slow.Step(1.0, 1.0 / 30.0, 3.0);
    if (std::abs(fast.position - slow.position) > 0.000000001 || fast.position > 1.0 || fast.position < 0.99) return 1;
    const double pausedPosition = slow.position;
    slow.Step(-4.0, 0.0, 3.0);
    if (slow.position != pausedPosition) return 1;
    FFCameraMotion motion;
    motion.Update(100.0, 0.0, 0.0, 0.0);
    motion.Update(120.0, 0.0, -12.0 * 0.08, 1.0 / 16.0);
    if (std::abs(motion.roll.position) > 0.5 || motion.elevation.position >= 120.0) return 1;
    motion.Update(-40.0, 5.0, 2.0, 0.0);
    if (motion.elevation.position != -40.0 || motion.pitch.position != 5.0 || motion.roll.position != 2.0) return 1;
    std::cout << "Camera presentation: frame-rate-independent critical damping, kerb impulse, pause and reset: PASS\n";
}
