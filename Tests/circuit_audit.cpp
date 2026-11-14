#include "FFSimulation.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <string>

namespace {
std::vector<std::uint8_t> Read(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

bool CheckProgressiveBank() {
    for (float slope : {-0.3f, 0.0f, 0.16f, 0.4f}) {
        for (float lane : {-15.0f, -6.0f, -2.0f, 0.0f, 3.0f, 6.0f, 15.0f}) {
            if (std::bit_cast<std::uint32_t>(trackLateralHeightMeters(slope, 0.0f, 6.0f, lane)) !=
                std::bit_cast<std::uint32_t>(slope * lane)) return false;
            if (trackLateralSlope(slope, 0.0f, 6.0f, lane) != slope) return false;
        }
    }
    CircuitSample sample;
    sample.elevation = 3.0f;
    sample.halfWidth = 6.0f;
    sample.bankSlope = 0.16f;
    sample.bankQuadratic = 0.01f;
    if (std::abs(circuitSurfaceHeight(sample, -6.0f) - 2.4f) > .000001f ||
        std::abs(circuitSurfaceHeight(sample, 6.0f) - 4.32f) > .000001f) return false;
    for (float lane : {-12.0f, -6.0f, -3.0f, 0.0f, 3.0f, 6.0f, 12.0f}) {
        const float derivative = (circuitSurfaceHeight(sample, lane + .01f) -
            circuitSurfaceHeight(sample, lane - .01f)) / .02f;
        if (std::abs(derivative - trackLateralSlope(.16f, .01f, 6.0f, lane)) > .0001f) return false;
    }
    if (trackLateralSlope(.16f, .01f, 6.0f, -12.0f) != trackLateralSlope(.16f, .01f, 6.0f, -6.0f) ||
        trackLateralSlope(.16f, .01f, 6.0f, 12.0f) != trackLateralSlope(.16f, .01f, 6.0f, 6.0f)) return false;
    TrackCatalogEntry fixture;
    fixture.targetLengthMeters = 200.0f;
    fixture.shoulderMeters = 5.0f;
    const std::array<TrackBankPoint, 2> banking{{{0, 9.090277f, .01f}, {200, 9.090277f, .01f}}};
    const std::array<TrackRunoffZone, 1> paving{{{0, 50, 1, TrackRunoffSurface::Asphalt, 3}}};
    const std::array<TrackBarrier, 1> walls{{{-1, -10.5f, 51, -10.5f, 0, 10, .15f}}};
    fixture.bankProfile = banking;
    fixture.runoffProfile = paving;
    fixture.authoredBarriers = walls;
    sample.sim = {425, 0};
    sample.tangent = {1, 0};
    if (std::abs(circuitPavedBankReach(fixture, sample, true) - 10.33f) > .00001f) return false;
    const std::vector<CircuitSample> samples{
        {{0, 0}, {1, 0}, 0, 3, 6, .16f, .01f},
        {{850, 0}, {1, 0}, 50, 3, 6, .16f, .01f},
        {{850, -850}, {0, -1}, 100, 3, 6, .16f, .01f},
        {{0, -850}, {-1, 0}, 150, 3, 6, .16f, .01f},
    };
    const std::string directory = "build/tmp/bank-contact-fixture";
    std::filesystem::create_directories(directory);
    if (!writeGeneratedContact(fixture, samples, directory)) return false;
    FFDriveSurface surface;
    if (!surface.Load(Read(directory + "/drive_surface.bin"))) return false;
    for (float lane : {-7.2f, -7.0f, -6.75f, -6.5f, -5.5f, -3.0f, 0.0f, 2.0f, 5.5f}) {
        const auto height = surface.Height(25.0f, -lane);
        if (!height || std::abs(*height - circuitSurfaceHeight(sample, lane)) > .01f) return false;
    }
    for (float lane : {7.5f, 9.0f, 10.25f}) {
        const auto height = surface.Height(25.0f, -lane);
        if (!height || std::abs(*height - circuitSurfaceHeight(sample, lane)) > .00001f) return false;
    }
    if (surface.Height(25.0f, -10.4f) || surface.Height(25.0f, 9.0f)) return false;
    const std::array<TrackBankPoint, 2> planar{{{0, 9.090277f}, {200, 9.090277f}}};
    fixture.bankProfile = planar;
    if (circuitBankedPaving(fixture, 25, true)) return false;
    fixture.id = TrackLayoutId::Jeddah;
    if (!circuitBankedPaving(fixture, 25, true) || circuitBankedPaving(fixture, 25, false)) return false;
    auto planarSamples = samples;
    for (auto& point : planarSamples) point.bankQuadratic = 0.0f;
    if (!writeGeneratedContact(fixture, planarSamples, directory) ||
        !surface.Load(Read(directory + "/drive_surface.bin"))) return false;
    for (float lane : {-7.2f, -7.0f, -6.75f, -6.5f, 7.0f, 9.0f, 10.25f}) {
        const auto height = surface.Height(25.0f, -lane);
        if (!height || std::abs(*height - (3.0f + .16f * lane)) > .00001f) return false;
    }
    const std::array<TrackBankPoint, 2> flat{{{0, 0}, {200, 0}}};
    fixture.bankProfile = flat;
    if (circuitBankedPaving(fixture, 25, true)) return false;
    return true;
}

bool CheckBankEdges() {
    TrackCatalogEntry fixture;
    fixture.targetLengthMeters = 200;
    fixture.shoulderMeters = 15;
    const std::array<TrackBankPoint, 2> bank{{{0, 6, 0, .25f, .015f, .03f}, {200, 6, 0, .25f, .015f, .03f}}};
    const std::array<TrackBarrier, 2> walls{{{-1, -17.9999f, 51, -18.0051f, 0, 10, .15f}, {-1, 14, 51, 14, 0, 10, .15f}}};
    fixture.bankProfile = bank;
    fixture.authoredBarriers = walls;
    const float slope = std::tan(6.0f * kPi / 180.0f);
    std::vector<CircuitSample> samples{
        {{0, 0}, {1, 0}, 0, 3, 4.5f, slope},
        {{850, 0}, {1, 0}, 50, 3, 4.5f, slope},
        {{850, -850}, {0, -1}, 100, 3, 4.5f, slope},
        {{0, -850}, {-1, 0}, 150, 3, 4.5f, slope},
    };
    const std::string directory = "build/tmp/bank-edge-fixture";
    std::filesystem::create_directories(directory);
    if (!writeGeneratedContact(fixture, samples, directory)) return false;
    const auto limits = Read(directory + "/track_limits.bin");
    for (auto& point : samples) {
        point.bankFade = .25f;
        point.bankOuterPositive = .015f;
        point.bankOuterNegative = .03f;
    }
    if (!writeGeneratedContact(fixture, samples, directory) || limits != Read(directory + "/track_limits.bin")) return false;
    FFDriveSurface surface;
    if (!surface.Load(Read(directory + "/drive_surface.bin"))) return false;
    const auto& sample = samples.front();
    const auto fractions = circuitBankEdgeFractions(samples[0], samples[1], 20.934f, 20.939f);
    if (fractions.front() != 0 || fractions.back() != 1) return false;
    for (std::size_t index = 1; index < fractions.size(); ++index) {
        if ((fractions[index] - fractions[index - 1]) * 20.934f < .005f) return false;
    }
    for (float lane = -13.75f; lane < 17.8f; lane += .025f) {
        const auto height = surface.Height(25.0f, -lane);
        if (!height || std::abs(*height - circuitSurfaceHeight(sample, lane)) > .002f) return false;
        const float derivative = (circuitSurfaceHeight(sample, lane + .001f) -
            circuitSurfaceHeight(sample, lane - .001f)) / .002f;
        if (std::abs(derivative - trackLateralSlope(slope, 0, 4.5f, lane, .25f, .015f, .03f)) > .0005f) return false;
    }
    if (surface.Height(25, -18) || surface.Height(25, 14)) return false;
    if (std::abs(circuitSurfaceHeight(sample, 24) - (3 + slope * 4.5f +
        (slope + .015f) * .125f + .015f * (24 - 4.75f))) > .00001f) return false;
    const std::array<TrackShoulderPoint, 3> shoulders{{{0, 5, 1.25f}, {100, 24, 1.25f}, {200, 5, 1.25f}}};
    const std::array<TrackRunoffZone, 1> gravel{{{0, 200, 1, TrackRunoffSurface::Gravel, 40}}};
    fixture.shoulders = shoulders;
    fixture.runoffProfile = gravel;
    if (circuitShoulderMeters(fixture, 0, true) != 5 ||
        circuitShoulderMeters(fixture, 100, true) != 24 ||
        circuitShoulderMeters(fixture, 0, false) != 1.25f) return false;
    const std::array<TrackBankPoint, 2> legacy{{{0, 6}, {200, 6}}};
    fixture.bankProfile = legacy;
    if (std::abs(circuitShoulderMeters(fixture, 0, true) - 39.05f) > .00001f) return false;
    return true;
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
    if (track.id == TrackLayoutId::Malaysia) {
        int flatApronWitnesses = 0;
        for (const auto& triangle : simulation.driveSurface.Triangles()) {
            Vec2 centre{};
            for (const auto& point : triangle.points) {
                centre += Vec2{point.positionX * 17.0f / 3.0f, -point.positionY * 17.0f / 3.0f};
            }
            const auto road = simulation.Project(centre);
            if (std::abs(road.lane) / 17.0f <= road.halfWidth + 1.4f ||
                sampleTrackBankQuadratic(track, road.station) != 0.0f ||
                sampleTrackBankFadeMeters(track, road.station) != 0.0f) continue;
            const auto contact = simulation.driveSurface.Height(centre.x / 17.0f, -centre.y / 17.0f);
            if (!contact || std::abs(simulation.Ground(centre) / 17.0f - *contact) > .0002f) {
                std::cerr << "Malaysia flat apron does not use its rendered contact mesh\n";
                return false;
            }
            ++flatApronWitnesses;
        }
        if (flatApronWitnesses == 0) return false;
        for (float station = 0; station < length; station += 20.0f) {
            if (station >= 4800.0f && station <= 5300.0f) continue;
            const auto road = simulation.Sample(station);
            const Vec2 normal{-road.tangent.y, road.tangent.x};
            for (float lane : {-2.5f, 0.0f, 2.5f}) {
                const Vec2 position = road.position + normal * (lane * 17.0f);
                const auto projected = simulation.Project(position);
                if (std::abs(simulation.Ground(position) - projected.elevation) / 17.0f > .002f) {
                    std::cerr << "Malaysia packed contact changed the unchanged core road height at "
                              << station << ", lane " << lane << '\n';
                    return false;
                }
            }
        }
    }
    if (!track.authoredBarriers.empty()) {
        // Source-registered T13/T14 ends; every other barrier endpoint stays paired.
        const std::array<std::pair<float, float>, 4> turkeyOpeningEnds{{
            {-347.4275f, 26.1874f}, {-369.4077f, 36.1422f},
            {-314.1103f, -9.9649f}, {-290.8085f, -40.2754f}
        }};
        std::array<bool, 4> foundOpeningEnds{};
        const std::array<float, 2> hockenheimOpeningStations{{3660, 3990}};
        std::array<bool, 2> foundHockenheimEnds{};
        std::map<std::pair<float,float>,int> endpoints;
        for (const auto& wall : track.authoredBarriers) {
            ++endpoints[{wall.ax,wall.ay}];
            ++endpoints[{wall.bx,wall.by}];
        }
        for (const auto& [point,count] : endpoints) {
            if (count%2 != 0) {
                if (track.id == TrackLayoutId::Hockenheim && count == 1) {
                    const auto projection = simulation.Project({point.first * 17, -point.second * 17});
                    const auto opening = std::find_if(hockenheimOpeningStations.begin(), hockenheimOpeningStations.end(),
                        [&](float expected) { return std::abs(projection.station - expected) < .05f; });
                    if (opening != hockenheimOpeningStations.end() && projection.lane < 0 &&
                        std::abs(projection.lane) / 17 - projection.halfWidth <= 40.01f) {
                        const auto index = opening - hockenheimOpeningStations.begin();
                        if (foundHockenheimEnds[index]) return false;
                        foundHockenheimEnds[index] = true;
                        continue;
                    }
                }
                if (track.id == TrackLayoutId::Turkey && count == 1) {
                    const auto opening = std::find_if(turkeyOpeningEnds.begin(), turkeyOpeningEnds.end(),
                        [&](const auto& expected) {
                            return std::hypot(point.first - expected.first, point.second - expected.second) < .001f;
                        });
                    if (opening != turkeyOpeningEnds.end()) {
                        foundOpeningEnds[opening - turkeyOpeningEnds.begin()] = true;
                        continue;
                    }
                }
                std::cerr << track.slug << " open protection at " << point.first << ',' << point.second << '\n';
                return false;
            }
        }
        if (track.id == TrackLayoutId::Hockenheim &&
            !std::all_of(foundHockenheimEnds.begin(), foundHockenheimEnds.end(), [](bool found) { return found; })) {
            std::cerr << "hockenheim source-registered Sachs opening ends missing\n";
            return false;
        }
        if (track.id == TrackLayoutId::Turkey &&
            !std::all_of(foundOpeningEnds.begin(), foundOpeningEnds.end(), [](bool found) { return found; })) {
            std::cerr << "turkey source-registered T13/T14 protection openings missing\n";
            return false;
        }
    }
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
        if (sampleTrackBankQuadratic(track, station) != 0.0f) {
            for (const float lane : {-4.0f, -2.0f, 0.0f, 2.0f, 4.0f}) {
                const Vec2 position = road.position + normal * (lane * 17.0f);
                const auto surface = simulation.driveSurface.Height(position.x / 17.0f, -position.y / 17.0f);
                if (!surface || std::abs(*surface - simulation.Ground(position) / 17.0f) > .02f) {
                    std::cerr << track.slug << " progressive contact disagreement at " << station << ", lane " << lane << '\n';
                    return false;
                }
            }
        }
        if (sampleTrackBankQuadratic(track, station) != 0.0f || sampleTrackBankFadeMeters(track, station) > 0.0f ||
            (track.id == TrackLayoutId::Jeddah && road.bankSlope != 0.0f)) {
            const CircuitSample sample{road.position, road.tangent, station, road.elevation / 17.0f,
                road.halfWidth, road.bankSlope, sampleTrackBankQuadratic(track, station),
                sampleTrackBankFadeMeters(track, station), sampleTrackBankOuterSlope(track, station, true),
                sampleTrackBankOuterSlope(track, station, false)};
            for (float side : {-1.0f, 1.0f}) {
                for (float beyond : {.5f, .75f, 1.0f, 1.2f}) {
                    const float lane = side * (road.halfWidth + beyond);
                    const Vec2 position = road.position + normal * (lane * 17.0f);
                    const auto surface = simulation.driveSurface.Height(position.x / 17.0f, -position.y / 17.0f);
                    const float expected = circuitSurfaceHeight(sample, lane);
                    if (!surface || std::abs(*surface - expected) > .02f ||
                        std::abs(simulation.Ground(position) / 17.0f - expected) > .02f) {
                        std::cerr << track.slug << " banked kerb support disagreement at " << station << ", lane " << lane
                                  << ": expected " << expected << ", contact " << (surface ? *surface : -9999.0f)
                                  << ", ground " << simulation.Ground(position) / 17.0f << '\n';
                        return false;
                    }
                }
            }
        }
        for (const bool positiveSide : {true, false}) {
            if (!circuitBankedPaving(track, station, positiveSide)) continue;
            const CircuitSample sample{road.position, road.tangent, station, road.elevation / 17.0f,
                road.halfWidth, road.bankSlope, sampleTrackBankQuadratic(track, station),
                sampleTrackBankFadeMeters(track, station), sampleTrackBankOuterSlope(track, station, true),
                sampleTrackBankOuterSlope(track, station, false)};
            const float inner = road.halfWidth + .35f;
            const float outer = circuitPavedBankReach(track, sample, positiveSide);
            for (const float fraction : {.1f, .5f, .9f, .99f}) {
                const float lane = (positiveSide ? 1.0f : -1.0f) * (inner + (outer - inner) * fraction);
                const Vec2 position = road.position + normal * (lane * 17.0f);
                const auto surface = simulation.driveSurface.Height(position.x / 17.0f, -position.y / 17.0f);
                const float expected = circuitSurfaceHeight(sample, lane);
                if (!surface || std::abs(*surface - expected) > .02f ||
                    std::abs(simulation.Ground(position) / 17.0f - expected) > .02f) {
                    std::cerr << track.slug << " paved-bank support missing at " << station << ", lane " << lane
                              << ": expected " << expected << ", contact " << (surface ? *surface : -9999.0f)
                              << ", ground " << simulation.Ground(position) / 17.0f << '\n';
                    return false;
                }
            }
        }
        for (const float lane : {-2.5f, 0.0f, 2.5f}) {
            const Vec2 position = road.position + normal * (lane * 17.0f);
            if (track.id == TrackLayoutId::Turkey || track.id == TrackLayoutId::Hockenheim) {
                if (!simulation.trackLimits.Touches(position / 17.0f, {1.0f, 0.0f}, 0.0f)) {
                    std::cerr << track.slug << " road leaves white-line envelope at " << station << " lane " << lane << '\n';
                    return false;
                }
            } else if (!track.authoredBarriers.empty()) {
                const float x = position.x / 17.0f, y = -position.y / 17.0f;
                bool inside = false;
                for (const auto& wall : track.authoredBarriers) {
                    if ((wall.ay > y) != (wall.by > y) &&
                        x < wall.ax + (y-wall.ay)*(wall.bx-wall.ax)/(wall.by-wall.ay)) inside = !inside;
                }
                if (!inside) {
                    std::cerr << track.slug << " road leaves closed protection at " << station << " lane " << lane << '\n';
                    return false;
                }
            }
            if (firstAuthoredBarrierHit(simulation.Barriers(), position, position, road.tangent,
                    0.6f * 17.0f, 0.45f * 17.0f, simulation.Ground(position), 0.8f * 17.0f).hit) {
                std::cerr << track.slug << " road blocked at " << station << " lane " << lane << '\n';
                return false;
            }
        }
        if (track.id != TrackLayoutId::LasVegas && track.authoredBarriers.empty() && std::fmod(station, 40.0f) < 8.0f) {
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
                const float bottom = road.elevation + trackLateralHeightMeters(road.bankSlope,
                    sampleTrackBankQuadratic(track, station), road.halfWidth, wallLane) * 17.0f;
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
    if (!CheckBankEdges()) {
        std::cerr << "bank-edge height, derivative, contact or white-line mismatch\n";
        return 1;
    }
    if (!CheckProgressiveBank()) {
        std::cerr << "progressive-bank height, derivative or contact mismatch\n";
        return 1;
    }
    if (!Check(TrackLayoutId::Monza, "monza", 5793.0f) || !Check(TrackLayoutId::Interlagos, "interlagos", 4309.0f)) return 1;
    for (const TrackCatalogEntry& track : trackCatalog()) {
        if (track.generated && !CheckGenerated(track)) return 1;
    }
    return 0;
}
