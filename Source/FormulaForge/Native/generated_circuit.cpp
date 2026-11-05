#include "generated_circuit.hpp"

#include "authored_circuit_sampling.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <tuple>

namespace {
constexpr float Units = 17.0f;
constexpr float Kerb = 0.85f;

Vec2 leftNormal(Vec2 tangent) { return {-tangent.y, tangent.x}; }


bool streetVenue(const TrackCatalogEntry& track) {
    const std::string_view tag = track.environmentTag;
    return tag == "corniche" || tag == "park-street" || tag == "island" || tag == "harbour" ||
        tag == "city" || tag == "marina" || tag == "strip" || tag == "capital";
}

Vec2 offsetPoint(const CircuitSample& sample, float laneMetres) {
    return sample.sim + leftNormal(sample.tangent) * (laneMetres * Units);
}

float distanceToSegment(Vec2 point, Vec2 a, Vec2 b) {
    const Vec2 span = b - a;
    const float t = std::clamp(dot(point - a, span) / std::max(0.001f, lengthSq(span)), 0.0f, 1.0f);
    return length(point - (a + span * t));
}

bool writeBytes(const std::string& path, const char* magic, std::size_t magicSize, std::uint32_t count, const float* values, std::size_t valueCount) {
    std::ofstream output(path, std::ios::binary);
    if (!output) return false;
    output.write(magic, static_cast<std::streamsize>(magicSize));
    output.write(reinterpret_cast<const char*>(&count), 4);
    output.write(reinterpret_cast<const char*>(values), static_cast<std::streamsize>(valueCount * sizeof(float)));
    return static_cast<bool>(output);
}
}

float circuitShoulderMeters(const TrackCatalogEntry& track, float station, bool left) {
    if (track.id == TrackLayoutId::LasVegas) {
        const auto apron = [station](float center, float extent, float width) {
            const float t = std::clamp(1.0f - std::abs(station - center) / extent, 0.0f, 1.0f);
            return width * t * t * (3.0f - 2.0f * t);
        };
        // Reference dry lap: T1 has an open paved apron; the city sections are wall tight.
        return 2.2f + (left ? apron(1982.0f, 110.0f, 10.0f) + apron(654.0f, 65.0f, 3.0f)
                           : apron(3278.0f, 65.0f, 3.5f));
    }
    return std::clamp(sampleTrackShoulderMeters(track, station, left), 1.2f, 24.0f);
}

std::vector<CircuitSample> sampleCircuit(const TrackCatalogEntry& track, int sampleCount) {
    if (sampleCount == 0) sampleCount = track.id == TrackLayoutId::LasVegas ? 6144 : 1536;
    const int tangentSpan = std::max(1, sampleCount / 512);
    const auto plan = authoredCircuitPlan(track.centerline, track.centerlineScale, track.targetLengthMeters, Units,
        track.mirrorCenterlineY, sampleCount);
    const int count = static_cast<int>(plan.size());
    std::vector<CircuitSample> samples(count);
    for (int index = 0; index < count; ++index) {
        const float station = track.targetLengthMeters * static_cast<float>(index) / static_cast<float>(count);
        samples[index] = CircuitSample{
            plan[index],
            normalize(plan[(index + tangentSpan) % count] - plan[(index + count - tangentSpan) % count]),
            station,
            sampleTrackElevationMeters(track, station),
            sampleTrackWidthMeters(track, station) * 0.5f,
            std::tan(sampleTrackBankDegrees(track, station) * kPi / 180.0f),
        };
    }
    return samples;
}

void buildGeneratedSupport(const TrackCatalogEntry& track, const std::vector<CircuitSample>& samples, GeneratedSupport& support) {
    support.barriers.clear();
    support.runoff.clear();
    const int count = static_cast<int>(samples.size());
    const bool paved = streetVenue(track);
    for (int index = 0; index < count; ++index) {
        const int next = (index + 1) % count;
        const CircuitSample& first = samples[index];
        const CircuitSample& second = samples[next];
        for (const bool left : {true, false}) {
            const float sign = left ? 1.0f : -1.0f;
            const float laneA = sign * (first.halfWidth + Kerb + circuitShoulderMeters(track, first.station, left));
            const float laneB = sign * (second.halfWidth + Kerb + circuitShoulderMeters(track, second.station, left));
            const auto separate = [&](Vec2 point, const CircuitSample& own) {
                const float minimum = (own.halfWidth + 1.0f) * Units;
                for (int step = 0; step < 10; ++step) {
                    bool crowded = false;
                    for (int other = 0; other < count; other += std::max(1, count / 1536)) {
                        float gap = std::abs(own.station - samples[other].station);
                        gap = std::min(gap, track.targetLengthMeters - gap);
                        if (gap < 50.0f || length(samples[other].sim - own.sim) < 8.0f * Units) continue;
                        if (length(point - samples[other].sim) < (samples[other].halfWidth + 1.0f) * Units) {
                            crowded = true;
                            break;
                        }
                    }
                    const Vec2 toward = own.sim - point;
                    const float distance = length(toward);
                    if (!crowded || distance <= minimum + 0.05f * Units) break;
                    point += toward / distance * Units;
                }
                const Vec2 delta = point - own.sim;
                const float distance = length(delta);
                if (distance < minimum) return own.sim + delta / std::max(0.001f, distance) * minimum;
                return point;
            };
            Vec2 a = separate(offsetPoint(first, laneA), first);
            Vec2 b = separate(offsetPoint(second, laneB), second);
            const float bottomA = (first.elevation + first.bankSlope * laneA) * Units;
            const float bottomB = (second.elevation + second.bankSlope * laneB) * Units;
            const float clearance = std::min(first.halfWidth, second.halfWidth) * Units;
            bool crosses = false;
            for (int step = 0; step <= 4; ++step) {
                const Vec2 point = first.sim + (second.sim - first.sim) * (static_cast<float>(step) / 4.0f);
                if (distanceToSegment(point, a, b) < clearance) crosses = true;
            }
            for (int step = 0; step <= 4 && !crosses; ++step) {
                const Vec2 point = a + (b - a) * (static_cast<float>(step) / 4.0f);
                for (int other = 0; other < count; other += std::max(1, count / 1536)) {
                    float gap = std::abs(first.station - samples[other].station);
                    gap = std::min(gap, track.targetLengthMeters - gap);
                    if (gap < 25.0f || length(samples[other].sim - first.sim) < 8.0f * Units) continue;
                    if (std::abs(first.elevation - samples[other].elevation) > 3.0f) continue;
                    if (length(point - samples[other].sim) < samples[other].halfWidth * Units) {
                        crosses = true;
                        break;
                    }
                }
            }
            if (crosses) {
                // The straight wall would cut a lane. Leave this join open rather than block the road.
            } else {
                const float bottom = std::min(bottomA, bottomB);
                support.barriers.push_back({a, b, bottom, bottom + 0.95f * Units, 0.15f * Units});
            }
            const Vec2 roadA = offsetPoint(first, sign * (first.halfWidth + Kerb));
            const Vec2 roadB = offsetPoint(second, sign * (second.halfWidth + Kerb));
            bool asphalt = paved;
            for (const TrackRunoffZone& zone : track.runoffProfile) {
                if (zone.widthMeters <= 0.0f || first.station < zone.startMeters || first.station > zone.endMeters) continue;
                if (zone.side != 0 && (zone.side > 0) != left) continue;
                asphalt = zone.surface == TrackRunoffSurface::Asphalt;
            }
            support.runoff.push_back({roadA, a, b, asphalt});
            support.runoff.push_back({roadA, b, roadB, asphalt});
        }
    }

    float minX = 1.0e9f, maxX = -1.0e9f, minY = 1.0e9f, maxY = -1.0e9f;
    for (const CircuitSample& sample : samples) {
        minX = std::min(minX, sample.sim.x / Units);
        maxX = std::max(maxX, sample.sim.x / Units);
        minY = std::min(minY, -sample.sim.y / Units);
        maxY = std::max(maxY, -sample.sim.y / Units);
    }
    constexpr float margin = 48.0f;
    constexpr float step = 8.0f;
    minX -= margin;
    minY -= margin;
    maxX += margin;
    maxY += margin;
    const int columns = std::max(2, static_cast<int>(std::ceil((maxX - minX) / step)) + 1);
    const int rows = std::max(2, static_cast<int>(std::ceil((maxY - minY) / step)) + 1);
    support.heights.assign(static_cast<std::size_t>(columns) * static_cast<std::size_t>(rows), 0);
    const int stride = std::max(1, count / 512);
    for (int row = 0; row < rows; ++row) {
        for (int column = 0; column < columns; ++column) {
            const float x = minX + column * step;
            const float y = minY + row * step;
            const Vec2 sim{x * Units, -y * Units};
            int nearest = 0;
            int second = 0;
            float best = 1.0e12f;
            float secondBest = 1.0e12f;
            for (int index = 0; index < count; index += stride) {
                const float distance = lengthSq(samples[index].sim - sim);
                if (distance < best) {
                    second = nearest;
                    secondBest = best;
                    best = distance;
                    nearest = index;
                } else if (distance < secondBest) {
                    secondBest = distance;
                    second = index;
                }
            }
            const CircuitSample& sample = samples[nearest];
            float height = sample.elevation;
            const float metres = std::sqrt(best) / (track.id == TrackLayoutId::LasVegas ? Units : 1.0f);
            const float stationGap = std::abs(sample.station - samples[second].station);
            if (track.deckSeparation && stationGap > 200.0f && stationGap < track.targetLengthMeters - 200.0f &&
                std::sqrt(secondBest) < 18.0f) {
                height = std::min(height, samples[second].elevation);
            } else if (metres > sample.halfWidth + 2.0f) {
                height -= std::min(2.0f, 0.018f * (metres - sample.halfWidth));
            }
            support.heights[static_cast<std::size_t>(row) * columns + column] =
                static_cast<std::int16_t>(std::clamp(static_cast<int>(std::lround(height * 100.0f)), -32768, 32767));
        }
    }
    support.ground.x0 = minX;
    support.ground.y0 = minY;
    support.ground.step = step;
    support.ground.columns = columns;
    support.ground.rows = rows;
    support.ground.heights = support.heights;
}

bool writeGeneratedContact(const TrackCatalogEntry& track, const std::vector<CircuitSample>& samples, const std::string& directory) {
    std::vector<float> drive;
    std::vector<float> limits;
    const int count = static_cast<int>(samples.size());
    auto sourceEdge = [](const CircuitSample& sample, float lane) {
        const Vec2 sim = offsetPoint(sample, lane);
        const float height = sample.elevation + sample.bankSlope * lane;
        return std::tuple<float, float, float>{sim.x / Units, -sim.y / Units, height};
    };
    auto limitEdge = [](const CircuitSample& sample, float lane) {
        const Vec2 sim = offsetPoint(sample, lane);
        return std::tuple<float, float>{sim.x / Units, sim.y / Units};
    };
    auto pushDrive = [&](auto a, auto b, auto c) {
        const float area = (std::get<0>(b) - std::get<0>(a)) * (std::get<1>(c) - std::get<1>(a)) -
            (std::get<1>(b) - std::get<1>(a)) * (std::get<0>(c) - std::get<0>(a));
        if (std::abs(area) < 0.0001f) return;
        drive.insert(drive.end(), {std::get<0>(a), std::get<1>(a), std::get<2>(a), std::get<0>(b), std::get<1>(b), std::get<2>(b),
            std::get<0>(c), std::get<1>(c), std::get<2>(c)});
    };
    auto pushLimit = [&](auto a, auto b, auto c) {
        const float area = (std::get<0>(b) - std::get<0>(a)) * (std::get<1>(c) - std::get<1>(a)) -
            (std::get<1>(b) - std::get<1>(a)) * (std::get<0>(c) - std::get<0>(a));
        if (std::abs(area) < 0.000001f) return;
        limits.insert(limits.end(), {std::get<0>(a), std::get<1>(a), std::get<0>(b), std::get<1>(b), std::get<0>(c), std::get<1>(c)});
    };
    for (int index = 0; index < count; ++index) {
        const CircuitSample& first = samples[index];
        const CircuitSample& second = samples[(index + 1) % count];
        constexpr float extra = 0.35f;
        const auto a = sourceEdge(first, first.halfWidth + extra);
        const auto b = sourceEdge(first, -(first.halfWidth + extra));
        const auto c = sourceEdge(second, second.halfWidth + extra);
        const auto d = sourceEdge(second, -(second.halfWidth + extra));
        pushDrive(a, b, d);
        pushDrive(a, d, c);
        const auto la = limitEdge(first, first.halfWidth);
        const auto ra = limitEdge(first, -first.halfWidth);
        const auto lb = limitEdge(second, second.halfWidth);
        const auto rb = limitEdge(second, -second.halfWidth);
        pushLimit(la, ra, rb);
        pushLimit(la, rb, lb);
    }
    (void)track;
    const bool surface = writeBytes(directory + "/drive_surface.bin", "FFSURF1", 8,
        static_cast<std::uint32_t>(drive.size() / 9), drive.data(), drive.size());
    const bool bounds = writeBytes(directory + "/track_limits.bin", "FFTL", 4,
        static_cast<std::uint32_t>(limits.size() / 6), limits.data(), limits.size());
    return surface && bounds && !drive.empty() && !limits.empty();
}
