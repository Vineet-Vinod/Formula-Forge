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

bool CheckGenerated(const TrackCatalogEntry& track) {
    const TrackShapeAuditResult shape = auditTrackCatalogShape(track);
    if (!shape.ok()) {
        std::cerr << track.slug << " shape failed aspect " << shape.aspectRatio
                  << " crossings " << shape.selfIntersections
                  << " landmarks " << shape.landmarkFailures << "/" << shape.landmarkChecks << '\n';
        return false;
    }
    FFSimulation simulation(track.id);
    const std::string root = "Content/Generated/" + std::string(track.contentDir) + "/";
    if (!simulation.driveSurface.Load(Read(root + "drive_surface.bin")) ||
        !simulation.trackLimits.Load(Read(root + "track_limits.bin"))) {
        std::cerr << track.slug << " contact files missing\n";
        return false;
    }
    const float length = track.targetLengthMeters;
    if (std::abs(simulation.lapLength - length) > 0.05f || simulation.Barriers().size() < length / 4.0f) {
        std::cerr << track.slug << " length or barrier count\n";
        return false;
    }
    const float seam = std::abs(sampleTrackElevationMeters(track, 0.0f) - sampleTrackElevationMeters(track, length));
    if (seam > 0.05f) {
        std::cerr << track.slug << " elevation does not close: " << seam << " m\n";
        return false;
    }
    for (float station = 0; station < length; station += 8.0f) {
        simulation.Reset(station);
        const auto road = simulation.Sample(station);
        const auto height = simulation.driveSurface.Height(road.position.x / 17.0f, -road.position.y / 17.0f);
        if (!height || !simulation.OnTrack()) {
            std::cerr << track.slug << " missing contact at " << station << '\n';
            return false;
        }
        const float error = std::abs(*height - simulation.Ground(road.position) / 17.0f);
        const bool deckOverlap = track.deckSeparation && error > 4.0f && error < 8.0f;
        if (error > 0.20f && !deckOverlap) {
            std::cerr << track.slug << " surface disagreement at " << station << ": " << error << " m\n";
            return false;
        }
        const Vec2 normal{-road.tangent.y, road.tangent.x};
        for (const float lane : {-2.5f, 0.0f, 2.5f}) {
            const Vec2 position = road.position + normal * (lane * 17.0f);
            if (firstAuthoredBarrierHit(simulation.Barriers(), position, position, road.tangent,
                    0.6f * 17.0f, 0.45f * 17.0f, simulation.Ground(position), 0.8f * 17.0f).hit) {
                std::cerr << track.slug << " road blocked at " << station << " lane " << lane << '\n';
                return false;
            }
        }
        if (std::fmod(station, 40.0f) < 8.0f) {
            for (const bool left : {true, false}) {
                bool besideAnotherRoad = false;
                for (float other = 0.0f; other < length; other += 20.0f) {
                    const float gap = std::min(std::abs(other - station), length - std::abs(other - station));
                    if (gap < 40.0f) continue;
                    const auto neighbour = simulation.Sample(other);
                    const Vec2 delta = neighbour.position - road.position;
                    const float side = dot(delta, normal);
                    if (::length(delta) < 22.0f * 17.0f && ((left && side > 0.0f) || (!left && side < 0.0f))) {
                        besideAnotherRoad = true;
                        break;
                    }
                }
                if (besideAnotherRoad) continue;
                const float sign = left ? 1.0f : -1.0f;
                const float beside = road.halfWidth + 1.4f;
                const float outer = road.halfWidth + circuitShoulderMeters(track, station, left) + 6.0f;
                const Vec2 start = road.position + normal * (sign * beside * 17.0f);
                const Vec2 end = road.position + normal * (sign * outer * 17.0f);
                const float wallLane = sign * (road.halfWidth + 0.85f + circuitShoulderMeters(track, station, left));
                const float bottom = road.elevation + road.bankSlope * wallLane * 17.0f;
                if (!firstAuthoredBarrierHit(simulation.Barriers(), start, end, road.tangent,
                        83.6f * 0.5f, 34.4f * 0.5f, bottom, 0.8f * 17.0f).hit) {
                    std::cerr << track.slug << " missing " << (left ? "left" : "right") << " wall at " << station << '\n';
                    return false;
                }
            }
        }
    }
    simulation.Reset();
    ArcadeVehicleControl control;
    control.throttle = 0.5f;
    for (int step = 0; step < 120; ++step) simulation.Step(control, 1.0f / 120.0f);
    if (!simulation.vehicle.grounded || simulation.vehicle.forwardSpeed <= 0.0f || simulation.barrierContact) {
        std::cerr << track.slug << " did not launch cleanly\n";
        return false;
    }
    std::cout << track.slug << ": " << length << " m, barriers " << simulation.Barriers().size()
              << ", relief " << track.nominalElevationReliefMeters << " m PASS\n";
    return true;
}

int main() {
    if (!Check(TrackLayoutId::Monza, "monza", 5793.0f) || !Check(TrackLayoutId::Interlagos, "interlagos", 4309.0f)) return 1;
    for (const TrackCatalogEntry& track : trackCatalog()) {
        if (track.generated && !CheckGenerated(track)) return 1;
    }
    return 0;
}
