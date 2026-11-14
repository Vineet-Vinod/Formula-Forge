#include "generated_circuit.hpp"

#include "authored_circuit_sampling.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <limits>
#include <tuple>
#include <utility>

namespace {
constexpr float Units = 17.0f;
constexpr float Kerb = 0.85f;
#include "track_data/lasvegas_boundaries.inc"
#include "track_data/malaysia_paving.inc"

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
        return 0.10f;
    }
    const float minimum = track.generated ? 0.05f : 1.2f;
    float width = std::clamp(sampleTrackShoulderMeters(track, station, left), minimum, 24.0f);
    if (sampleTrackBankFadeMeters(track, station) == 0.0f &&
        (!track.authoredBarriers.empty() || track.id == TrackLayoutId::Japan)) {
        for (const auto& zone : track.runoffProfile) {
            const bool inside = zone.startMeters <= zone.endMeters ?
                station >= zone.startMeters && station <= zone.endMeters :
                station >= zone.startMeters || station <= zone.endMeters;
            if (inside && (zone.side == 0 || (zone.side > 0) == left)) {
                width = std::max(width, zone.widthMeters - 0.95f);
            }
        }
    }
    return width;
}

float circuitSurfaceHeight(const CircuitSample& sample, float lane) noexcept {
    if (sample.bankQuadratic == 0.0f && sample.bankFade == 0.0f) return sample.elevation + sample.bankSlope * lane;
    return sample.elevation + trackLateralHeightMeters(
        sample.bankSlope, sample.bankQuadratic, sample.halfWidth, lane,
        sample.bankFade, sample.bankOuterPositive, sample.bankOuterNegative);
}

bool circuitBankedPaving(const TrackCatalogEntry& track, float station, bool positiveSide) noexcept {
    // Sepang's apron contact comes from its rendered mesh, not a full-shoulder bank strip.
    if (track.id == TrackLayoutId::Malaysia) {
        return false;
    }
    if (sampleTrackBankFadeMeters(track, station) > 0.0f) return true;
    const bool progressive = std::any_of(track.bankProfile.begin(), track.bankProfile.end(),
        [](const TrackBankPoint& point) { return point.quadraticPerMeter != 0.0f; });
    const bool jeddahBank = track.id == TrackLayoutId::Jeddah && sampleTrackBankDegrees(track, station) != 0.0f;
    if (!progressive && !jeddahBank) return false;
    for (const auto& zone : track.runoffProfile) {
        const bool inside = zone.startMeters <= zone.endMeters ?
            station >= zone.startMeters && station <= zone.endMeters :
            station >= zone.startMeters || station <= zone.endMeters;
        if (inside && zone.widthMeters > 0.0f && zone.surface == TrackRunoffSurface::Asphalt &&
            (zone.side == 0 || (zone.side > 0) == positiveSide)) return true;
    }
    return false;
}

float circuitPavedBankReach(const TrackCatalogEntry& track, const CircuitSample& sample, bool positiveSide) noexcept {
    const float nominal = sample.halfWidth + Kerb + circuitShoulderMeters(track, sample.station, positiveSide);
    const Vec2 origin{sample.sim.x / Units, -sample.sim.y / Units};
    const float sign = positiveSide ? 1.0f : -1.0f;
    const Vec2 ray{-sample.tangent.y * sign, -sample.tangent.x * sign};
    float nearest = std::numeric_limits<float>::infinity();
    for (const auto& wall : track.authoredBarriers) {
        const Vec2 edge{wall.bx - wall.ax, wall.by - wall.ay};
        const float denominator = ray.x * edge.y - ray.y * edge.x;
        if (std::abs(denominator) < .000001f) continue;
        const Vec2 delta{wall.ax - origin.x, wall.ay - origin.y};
        const float distance = (delta.x * edge.y - delta.y * edge.x) / denominator;
        const float position = (delta.x * ray.y - delta.y * ray.x) / denominator;
        if (distance <= sample.halfWidth || distance > nominal + 1.1f || position < 0 || position > 1) continue;
        const float normalIncidence = std::abs(denominator) / std::max(.001f, length(edge));
        nearest = std::min(nearest, distance - wall.halfThickness / normalIncidence - .02f);
    }
    return std::isfinite(nearest) ? nearest : nominal - .17f;
}

std::vector<float> circuitBankEdgeFractions(const CircuitSample& first, const CircuitSample& second,
    float firstSpan, float secondSpan) {
    std::vector<float> fractions{0.0f};
    const float span = std::max(firstSpan, secondSpan);
    if (span <= 0.0f) return {0.0f, 1.0f};
    const float fade = std::min(std::max(first.bankFade, second.bankFade), span);
    const int fineCount = fade > .005f ? static_cast<int>(std::ceil(fade / .1f)) : 0;
    const float fineEnd = fineCount ? fade : 0.0f;
    for (int index = 1; index <= fineCount; ++index) {
        fractions.push_back((fineEnd * static_cast<float>(index) / fineCount) / span);
    }
    const float remaining = span - fineEnd;
    if (remaining > 0.0f) {
        const int coarseCount = std::max(1, static_cast<int>(std::ceil(remaining / 1.5f)));
        for (int index = 1; index < coarseCount; ++index) {
            fractions.push_back((fineEnd + remaining * static_cast<float>(index) / coarseCount) / span);
        }
        fractions.push_back(1.0f);
    }
    return fractions;
}

std::vector<CircuitSample> sampleCircuit(const TrackCatalogEntry& track, int sampleCount) {
    if (sampleCount == 0) sampleCount = track.id == TrackLayoutId::LasVegas ? 12288 : track.surfaceSamples;
    const int tangentSpan = sampleCount >= 8192 ? 1 : std::max(1, sampleCount / 512);
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
            sampleTrackBankQuadratic(track, station),
            sampleTrackBankFadeMeters(track, station),
            sampleTrackBankOuterSlope(track, station, true),
            sampleTrackBankOuterSlope(track, station, false),
        };
    }
    return samples;
}

void buildGeneratedSupport(const TrackCatalogEntry& track, const std::vector<CircuitSample>& samples, GeneratedSupport& support) {
    support.barriers.clear();
    support.runoff.clear();
    const int count = static_cast<int>(samples.size());
    const bool paved = streetVenue(track);
    if (track.id != TrackLayoutId::LasVegas || kLasVegasWalls.empty()) {
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
                Vec2 a = offsetPoint(first, laneA);
                Vec2 b = offsetPoint(second, laneB);
                if (track.authoredBarriers.empty()) {
                    a = separate(a, first);
                    b = separate(b, second);
                }
                const float bottomA = circuitSurfaceHeight(first, laneA) * Units;
                const float bottomB = circuitSurfaceHeight(second, laneB) * Units;
                const float clearance = std::min(first.halfWidth, second.halfWidth) * Units;
                bool crosses = !track.authoredBarriers.empty();
                for (int step = 0; step <= 4 && !crosses; ++step) {
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

    }
    if (track.id == TrackLayoutId::LasVegas && !kLasVegasWalls.empty()) {
        support.barriers.assign(kLasVegasWalls.begin(), kLasVegasWalls.end());
        for (const auto& triangle : kLasVegasPaving) {
            support.runoff.push_back({{triangle[0] * Units, -triangle[1] * Units},
                                      {triangle[3] * Units, -triangle[4] * Units},
                                      {triangle[6] * Units, -triangle[7] * Units}, true});
        }
    }
    if (!track.authoredBarriers.empty()) {
        support.barriers.clear();
        for (const auto& wall : track.authoredBarriers) {
            support.barriers.push_back({{wall.ax * Units, -wall.ay * Units},
                {wall.bx * Units, -wall.by * Units}, wall.bottom * Units,
                wall.top * Units, wall.halfThickness * Units});
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
            const float metres = std::sqrt(best) / Units;
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
        const float height = circuitSurfaceHeight(sample, lane);
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
        const bool progressive = first.bankQuadratic != 0.0f || second.bankQuadratic != 0.0f;
        const bool bankEdges = first.bankFade > 0.0f || second.bankFade > 0.0f;
        const bool jeddahBank = track.id == TrackLayoutId::Jeddah &&
            (first.bankSlope != 0.0f || second.bankSlope != 0.0f);
        const bool malaysiaKerb = track.id == TrackLayoutId::Malaysia && bankEdges;
        const float extra = malaysiaKerb ? 1.25f : bankEdges ? 0.0f : progressive || jeddahBank ? 1.25f : 0.35f;
        const int strips = progressive ? 8 : 1;
        for (int strip = 0; strip < strips; ++strip) {
            const float high = 1.0f - 2.0f * static_cast<float>(strip) / strips;
            const float low = 1.0f - 2.0f * static_cast<float>(strip + 1) / strips;
            const auto a = sourceEdge(first, high * (first.halfWidth + extra));
            const auto b = sourceEdge(first, low * (first.halfWidth + extra));
            const auto c = sourceEdge(second, high * (second.halfWidth + extra));
            const auto d = sourceEdge(second, low * (second.halfWidth + extra));
            pushDrive(a, b, d);
            pushDrive(a, d, c);
        }
        for (const bool positiveSide : {true, false}) {
            if (!circuitBankedPaving(track, first.station, positiveSide) &&
                !circuitBankedPaving(track, second.station, positiveSide)) continue;
            const float sign = positiveSide ? 1.0f : -1.0f;
            const float startA = first.halfWidth + extra;
            const float startB = second.halfWidth + extra;
            const float endA = circuitPavedBankReach(track, first, positiveSide);
            const float endB = circuitPavedBankReach(track, second, positiveSide);
            if (endA <= startA || endB <= startB) continue;
            if (bankEdges) {
                const auto fractions = circuitBankEdgeFractions(first, second, endA - startA, endB - startB);
                for (std::size_t strip = 0; strip + 1 < fractions.size(); ++strip) {
                    const float lo = fractions[strip], hi = fractions[strip + 1];
                    const auto a = sourceEdge(first, sign * (startA + (endA - startA) * lo));
                    const auto b = sourceEdge(second, sign * (startB + (endB - startB) * lo));
                    const auto c = sourceEdge(second, sign * (startB + (endB - startB) * hi));
                    const auto d = sourceEdge(first, sign * (startA + (endA - startA) * hi));
                    pushDrive(a, b, c);
                    pushDrive(a, c, d);
                }
                continue;
            }
            const int apronStrips = std::max(1, static_cast<int>(std::ceil(std::max(endA - startA, endB - startB) / 1.5f)));
            for (int strip = 0; strip < apronStrips; ++strip) {
                const float lo = static_cast<float>(strip) / apronStrips;
                const float hi = static_cast<float>(strip + 1) / apronStrips;
                const auto a = sourceEdge(first, sign * (startA + (endA - startA) * lo));
                const auto b = sourceEdge(second, sign * (startB + (endB - startB) * lo));
                const auto c = sourceEdge(second, sign * (startB + (endB - startB) * hi));
                const auto d = sourceEdge(first, sign * (startA + (endA - startA) * hi));
                pushDrive(a, b, c);
                pushDrive(a, c, d);
            }
        }
        const auto la = limitEdge(first, first.halfWidth);
        const auto ra = limitEdge(first, -first.halfWidth);
        const auto lb = limitEdge(second, second.halfWidth);
        const auto rb = limitEdge(second, -second.halfWidth);
        pushLimit(la, ra, rb);
        pushLimit(la, rb, lb);
    }
    if (track.id == TrackLayoutId::LasVegas) {
        for (const auto& triangle : kLasVegasPaving) drive.insert(drive.end(), triangle.begin(), triangle.end());
    }
    if (track.id == TrackLayoutId::Malaysia) {
        for (const auto& triangle : kMalaysiaPaving) drive.insert(drive.end(), triangle.begin(), triangle.end());
    }
    const bool surface = writeBytes(directory + "/drive_surface.bin", "FFSURF1", 8,
        static_cast<std::uint32_t>(drive.size() / 9), drive.data(), drive.size());
    const bool bounds = writeBytes(directory + "/track_limits.bin", "FFTL", 4,
        static_cast<std::uint32_t>(limits.size() / 6), limits.data(), limits.size());
    return surface && bounds && !drive.empty() && !limits.empty();
}
