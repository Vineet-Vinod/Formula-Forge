#include "FFSimulation.hpp"

#include <cmath>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>

namespace {
std::vector<std::uint8_t> Read(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

bool Check(TrackLayoutId layout, const std::string& slug, float length) {
    FFSimulation simulation(layout);
    const auto* catalog = findTrackCatalogEntry(layout);
    if (simulation.lapLength != length || simulation.trial.lapLength != length ||
        simulation.Barriers().size() < 100 || simulation.circuitName != catalog->displayName) return false;
    const std::string root = "Content/Generated/" + std::string(slug == "monza" ? "Monza" : "Interlagos") + "/Data/";
    if (!simulation.driveSurface.Load(Read(root + "drive_surface.bin")) ||
        !simulation.trackLimits.Load(Read(root + "track_limits.bin"))) return false;
    float maximumHeightError = 0.0f;
    for (float station = 0; station < length; station += 4.0f) {
        simulation.Reset(station);
        const auto road = simulation.Sample(station);
        const auto height = simulation.driveSurface.Height(road.position.x / 17.0f, -road.position.y / 17.0f);
        if (!height || !simulation.OnTrack()) {
            std::cerr << slug << " missing contact/limits at " << station << '\n';
            return false;
        }
        const float error = std::abs(*height - simulation.Ground(road.position) / 17.0f);
        maximumHeightError = std::max(error, maximumHeightError);
        if (error > .20f || std::abs(road.elevation / 17.0f - sampleTrackElevationMeters(*catalog, station)) > .0001f) {
            std::cerr << slug << " surface disagreement at " << station << ": " << error << "m\n";
            return false;
        }
        const Vec2 normal{-road.tangent.y, road.tangent.x};
        for (const float lane : {-3.0f, 0.0f, 3.0f}) {
            const Vec2 position = road.position + normal * (lane * 17.0f);
            if (firstAuthoredBarrierHit(simulation.Barriers(), position, position, road.tangent,
                    83.6f * .5f, 34.4f * .5f, simulation.Ground(position), .8f * 17.0f).hit) {
                std::cerr << slug << " road corridor blocked at " << station << ", lane " << lane << '\n';
                return false;
            }
        }
    }
    if (layout == TrackLayoutId::Monza) {
        for (float station = 0; station < length; station += 20.0f) {
            const auto road = simulation.Sample(station);
            const Vec2 normal{-road.tangent.y, road.tangent.x};
            for (const float lane : {-30.0f, -20.0f, -10.0f, 10.0f, 20.0f, 30.0f}) {
                const Vec2 position = road.position + normal * (lane * 17.0f);
                const auto projection = simulation.Project(position);
                if (std::abs(projection.lane) / 17.0f < projection.halfWidth + 1.0f) continue;
                const auto height = simulation.driveSurface.Height(position.x / 17.0f, -position.y / 17.0f);
                if (height && std::abs(*height - simulation.Ground(position) / 17.0f) > .05f) {
                    std::cerr << "monza off-road ground disagreement at " << station << ", lane " << lane << '\n';
                    return false;
                }
            }
        }
    }
    if (layout == TrackLayoutId::Interlagos) {
        for (float station = 3750; station < 4140; station += 10) {
            const auto road = simulation.Sample(station);
            const Vec2 inside{road.tangent.y, -road.tangent.x};
            const Vec2 end = road.position + inside * ((road.halfWidth + 10) * 17.0f);
            const Vec2 shoulder = road.position + inside * ((road.halfWidth + 4) * 17.0f);
            if (!firstAuthoredBarrierHit(simulation.Barriers(), road.position, end, road.tangent,
                    83.6f * .5f, 34.4f * .5f, simulation.Ground(shoulder), .8f * 17.0f).hit) {
                std::cerr << "interlagos upper inside protection missing at " << station << '\n';
                return false;
            }
        }
    }
    simulation.Reset();
    const float start = catalog->startPhase * length;
    if (std::abs(simulation.trial.startStation - start) > .001f ||
        std::abs(simulation.Project(simulation.vehicle.pos).station - wrapDistance(start - 20.0f, length)) > .1f) return false;
    ArcadeVehicleControl control;
    control.throttle = .5f;
    for (int step = 0; step < 120; ++step) simulation.Step(control, 1.0f / 120.0f);
    if (!simulation.vehicle.grounded || simulation.vehicle.forwardSpeed <= 0 || simulation.barrierContact) return false;
    FFTrialState trial;
    trial.lapLength = length;
    trial.startStation = start;
    if (start > 30) {
        trial.Reset(length - 1);
        trial.Step(1, true, false, .02);
        if (trial.running) return false;
    }
    trial.Reset(start - 1);
    trial.Step(start + 1, true, false, .02);
    for (float station = 3; station < length; station += 2) trial.Step(start + station, true, false, .02);
    trial.Step(start + 1, true, false, .02);
    if (trial.completedLaps != 1 || !trial.lastValid) return false;
    trial.Step(start + 5, false, false, .02);
    if (!trial.invalid) return false;
    std::cout << slug << ": contact/limits around full lap, retained elevation, launch and timing PASS; max road offset "
              << maximumHeightError << "m; barriers " << simulation.Barriers().size() << '\n';
    return true;
}
}

int main() {
    return Check(TrackLayoutId::Monza, "monza", 5793.0f) &&
        Check(TrackLayoutId::Interlagos, "interlagos", 4309.0f) ? 0 : 1;
}
