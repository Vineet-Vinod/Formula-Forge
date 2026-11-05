#include "FFRacingLine.hpp"
#include "FFLasVegasAudit.hpp"
#include "FFSimulation.hpp"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>

int main() {
    FFSimulation simulation(TrackLayoutId::LasVegas);
    const std::string directory = "Content/Generated/LasVegas/Data/";
    std::ifstream surface(directory + "drive_surface.bin", std::ios::binary);
    const std::vector<std::uint8_t> bytes{std::istreambuf_iterator<char>(surface), {}};
    std::ifstream limits(directory + "track_limits.bin", std::ios::binary);
    const std::vector<std::uint8_t> limitBytes{std::istreambuf_iterator<char>(limits), {}};
    if (!simulation.driveSurface.Load(bytes) || !simulation.trackLimits.Load(limitBytes)) return 1;
    FFRacingLine line;
    if (!PrepareLasVegasAuditLine(simulation, line)) return 1;
    std::filesystem::create_directories("build/unreal/recordings");
    std::ofstream replay("build/unreal/recordings/lasvegas-native-lap.csv");
    replay << "frame,time,x,y,z,heading,speed,steer,pitch,roll,gear,rpm,grounded,chase,lap_seconds,invalid,unused1,unused2\n";
    replay << std::setprecision(9);
    float maximumSpeed = 0.0f;
    float maximumLane = 0.0f;
    int frame = 0;
    for (int step = 0; step < 120 * 600; ++step) {
        const auto road = simulation.Project(simulation.vehicle.pos);
        const auto control = line.Control(simulation.vehicle, simulation.tuning, road.station, 17.0f, .60f);
        simulation.Step(control, 1.0f / 120.0f);
        const auto& car = simulation.vehicle;
        maximumSpeed = std::max(maximumSpeed, car.forwardSpeed * 3.6f / 17.0f);
        maximumLane = std::max(maximumLane, std::abs(road.lane / 17.0f));
        if (!simulation.OnTrack() || simulation.barrierContact || !car.grounded) {
            std::cerr << "Las Vegas live simulation failed at " << road.station << " m, lane " << road.lane / 17.0f
                      << " speed " << car.forwardSpeed * 3.6f / 17.0f << " kph, contact " << simulation.barrierContact
                      << " grounded " << car.grounded << '\n';
            return 1;
        }
        if (step % 4 == 0 && simulation.trial.completedLaps == 0) {
            replay << frame++ << ',' << step / 120.0 << ',' << car.pos.x / 17.0f << ',' << car.pos.y / 17.0f << ','
                   << car.elevation / 17.0f << ',' << car.heading << ',' << car.forwardSpeed * 3.6f / 17.0f << ','
                   << car.steerAngle << ',' << car.bodyPitch << ',' << car.bodyRoll << ',' << car.gear << ','
                   << car.engineRpmNormalized << ",1,0," << simulation.trial.seconds << ',' << simulation.trial.invalid << ",0,0\n";
        }
        if (simulation.trial.completedLaps >= 1) {
            std::cout << "Las Vegas dynamic lap: " << simulation.trial.lastSeconds << " s, valid=" << simulation.trial.lastValid
                      << ", max speed=" << maximumSpeed << " kph, maximum lane=" << maximumLane << " m\n";
            return simulation.trial.lastValid ? 0 : 1;
        }
    }
    std::cerr << "Las Vegas dynamic lap timed out\n";
    return 1;
}
