#include "FFPitLane.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <limits>

namespace {
constexpr float CellSize = 16.0f;
constexpr float MaximumLateralMarginMetres = 4.0f;

bool ContainsPoint(const std::array<Vec2, 3>& points, Vec2 position) {
    const float orientation = cross(points[1] - points[0], points[2] - points[0]) >= 0.0f ? 1.0f : -1.0f;
    for (std::size_t index = 0; index < points.size(); ++index) {
        const Vec2 edge = points[(index + 1) % points.size()] - points[index];
        if (orientation * cross(edge, position - points[index]) < -0.001f * length(edge)) return false;
    }
    return true;
}
}

std::uint64_t FFPitLane::CellKey(int column, int row) {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(column)) << 32) |
        static_cast<std::uint32_t>(row);
}

bool FFPitLane::Load(std::span<const std::uint8_t> bytes) {
    constexpr std::array<std::uint8_t, 8> signature{'F', 'F', 'P', 'I', 'T', '1', 0, 0};
    constexpr std::array<std::uint8_t, 8> signature2{'F', 'F', 'P', 'I', 'T', '2', 0, 0};
    constexpr std::array<std::uint8_t, 8> signature3{'F', 'F', 'P', 'I', 'T', '3', 0, 0};
    if (bytes.size() < 20) return false;
    const bool version3 = std::equal(signature3.begin(), signature3.end(), bytes.begin());
    const bool version2 = version3 || std::equal(signature2.begin(), signature2.end(), bytes.begin());
    if (!version2 && !std::equal(signature.begin(), signature.end(), bytes.begin())) return false;
    const std::size_t headerSize = version2 ? 24 : 20;
    const std::size_t sectionSize = version3 ? 44 : 36;
    if (bytes.size() < headerSize) return false;
    std::uint32_t count;
    float entry;
    float exit;
    std::memcpy(&count, bytes.data() + 8, 4);
    std::memcpy(&entry, bytes.data() + 12, 4);
    std::memcpy(&exit, bytes.data() + 16, 4);
    float speedLimit = 80.0f;
    if (version2) std::memcpy(&speedLimit, bytes.data() + 20, 4);
    if (count < 2 || count > 10000 || bytes.size() != headerSize + count * sectionSize ||
        !std::isfinite(speedLimit) || speedLimit < 20.0f || speedLimit > 100.0f ||
        !std::isfinite(entry) || !std::isfinite(exit) || entry < 0.0f || exit <= entry) return false;
    std::vector<FFPitSection> loaded;
    loaded.reserve(count);
    for (std::uint32_t index = 0; index < count; ++index) {
        std::array<float, 11> row{};
        std::memcpy(row.data(), bytes.data() + headerSize + index * sectionSize, sectionSize);
        for (float value : row) {
            if (!std::isfinite(value) || std::abs(value) > 20000.0f) return false;
        }
        FFPitSection section{{row[0], row[1]}, row[2], row[3], row[4], row[5], {row[6], row[7]}, row[8],
            version3 ? row[9] : row[3], version3 ? row[10] : row[3]};
        if (section.halfWidth < 1.5f || section.halfWidth > 12.0f || section.distance < 0.0f ||
            std::abs(length(section.normal) - 1.0f) > 0.01f || std::abs(section.crossSlope) > 0.08f ||
            section.positiveExtent < section.halfWidth || section.negativeExtent < section.halfWidth ||
            section.positiveExtent > 12.0f || section.negativeExtent > 12.0f) return false;
        if (loaded.empty()) {
            if (section.distance > 0.01f) return false;
        } else {
            const auto& previous = loaded.back();
            const float spacing = length(section.position - previous.position);
            if (spacing < 0.01f || spacing > 10.0f || section.distance <= previous.distance ||
                section.distance - previous.distance > 10.0f || section.trackStation < previous.trackStation ||
                std::abs(section.height - previous.height) / spacing > 0.20f) return false;
        }
        loaded.push_back(section);
    }
    if (exit > loaded.back().distance || entry >= exit) return false;
    sections = std::move(loaded);
    limitEntry = entry;
    limitExit = exit;
    speedLimitKph = speedLimit;
    cells.clear();
    for (std::uint32_t index = 0; index + 1 < sections.size(); ++index) {
        const auto& first = sections[index];
        const auto& last = sections[index + 1];
        const float reach = std::max({first.positiveExtent, first.negativeExtent,
            last.positiveExtent, last.negativeExtent}) + MaximumLateralMarginMetres + 0.01f;
        const int firstColumn = static_cast<int>(std::floor((std::min(first.position.x, last.position.x) - reach) / CellSize));
        const int lastColumn = static_cast<int>(std::floor((std::max(first.position.x, last.position.x) + reach) / CellSize));
        const int firstRow = static_cast<int>(std::floor((std::min(first.position.y, last.position.y) - reach) / CellSize));
        const int lastRow = static_cast<int>(std::floor((std::max(first.position.y, last.position.y) + reach) / CellSize));
        for (int row = firstRow; row <= lastRow; ++row) {
            for (int column = firstColumn; column <= lastColumn; ++column) cells[CellKey(column, row)].push_back(index);
        }
    }
    return true;
}

FFPitProjection FFPitLane::Project(Vec2 positionMetres, float lateralMarginMetres) const {
    FFPitProjection result;
    if (!std::isfinite(positionMetres.x) || !std::isfinite(positionMetres.y) ||
        std::abs(positionMetres.x) > 20000.0f || std::abs(positionMetres.y) > 20000.0f ||
        !std::isfinite(lateralMarginMetres) || lateralMarginMetres < 0.0f ||
        lateralMarginMetres > MaximumLateralMarginMetres) return result;
    const auto found = cells.find(CellKey(static_cast<int>(std::floor(positionMetres.x / CellSize)),
        static_cast<int>(std::floor(positionMetres.y / CellSize))));
    if (found == cells.end()) return result;
    float nearest = std::numeric_limits<float>::max();
    for (std::uint32_t index : found->second) {
        const auto& first = sections[index];
        const auto& last = sections[index + 1];
        const Vec2 firstLeft = first.position + first.normal * (first.positiveExtent + lateralMarginMetres);
        const Vec2 firstRight = first.position - first.normal * (first.negativeExtent + lateralMarginMetres);
        const Vec2 lastLeft = last.position + last.normal * (last.positiveExtent + lateralMarginMetres);
        const Vec2 lastRight = last.position - last.normal * (last.negativeExtent + lateralMarginMetres);
        std::array<Vec2, 3> triangle{firstRight, lastRight, lastLeft};
        const bool firstTriangle = ContainsPoint(triangle, positionMetres);
        if (!firstTriangle) {
            triangle = {firstRight, lastLeft, firstLeft};
            if (!ContainsPoint(triangle, positionMetres)) continue;
        }
        const float area = cross(triangle[1] - triangle[0], triangle[2] - triangle[0]);
        if (std::abs(area) <= std::numeric_limits<float>::epsilon()) continue;
        std::array<float, 3> weights{
            cross(triangle[1] - positionMetres, triangle[2] - positionMetres) / area,
            cross(triangle[2] - positionMetres, triangle[0] - positionMetres) / area,
            cross(triangle[0] - positionMetres, triangle[1] - positionMetres) / area};
        for (float& weight : weights) weight = std::clamp(weight, 0.0f, 1.0f);
        const float weightSum = weights[0] + weights[1] + weights[2];
        for (float& weight : weights) weight /= weightSum;
        const Vec2 segment = last.position - first.position;
        const float blend = firstTriangle ? weights[1] + weights[2] : weights[1];
        const Vec2 centre = lerp(first.position, last.position, blend);
        const float distanceSquared = lengthSq(positionMetres - centre);
        if (distanceSquared >= nearest) continue;
        const Vec2 normal = normalize(lerp(first.normal, last.normal, blend));
        const float lane = dot(positionMetres - centre, normal);
        const float halfWidth = lane >= 0 ? lerp(first.positiveExtent, last.positiveExtent, blend) :
            lerp(first.negativeExtent, last.negativeExtent, blend);
        const float queryHalfWidth = halfWidth + lateralMarginMetres;
        if (std::abs(lane) > queryHalfWidth + 0.001f ||
            distanceSquared > (queryHalfWidth + 0.01f) * (queryHalfWidth + 0.01f)) continue;
        nearest = distanceSquared;
        result.inside = true;
        result.position = centre;
        result.distance = lerp(first.distance, last.distance, blend);
        result.controlled = result.distance >= limitEntry && result.distance <= limitExit;
        result.lane = lane;
        result.halfWidth = halfWidth;
        const float firstLeftHeight = first.height + (first.positiveExtent + lateralMarginMetres) * first.crossSlope;
        const float firstRightHeight = first.height - (first.negativeExtent + lateralMarginMetres) * first.crossSlope;
        const float lastLeftHeight = last.height + (last.positiveExtent + lateralMarginMetres) * last.crossSlope;
        const float lastRightHeight = last.height - (last.negativeExtent + lateralMarginMetres) * last.crossSlope;
        result.height = weights[0] * firstRightHeight +
            weights[1] * (firstTriangle ? lastRightHeight : lastLeftHeight) +
            weights[2] * (firstTriangle ? lastLeftHeight : firstLeftHeight);
        result.grade = (last.height - first.height) / length(segment);
        result.trackStation = lerp(first.trackStation, last.trackStation, blend);
        result.tangent = normalize(segment);
    }
    return result;
}

FFPitProjection FFPitLane::Sample(float distanceMetres) const {
    FFPitProjection result;
    if (sections.empty() || !std::isfinite(distanceMetres)) return result;
    const float distance = std::clamp(distanceMetres, 0.0f, sections.back().distance);
    const auto found = std::lower_bound(sections.begin(), sections.end(), distance,
        [](const FFPitSection& section, float value) { return section.distance < value; });
    const std::size_t last = std::clamp<std::size_t>(found - sections.begin(), 1, sections.size() - 1);
    const auto& first = sections[last - 1];
    const auto& second = sections[last];
    const float blend = (distance - first.distance) / (second.distance - first.distance);
    result.inside = true;
    result.controlled = distance >= limitEntry && distance <= limitExit;
    result.distance = distance;
    result.position = lerp(first.position, second.position, blend);
    result.halfWidth = lerp(first.halfWidth, second.halfWidth, blend);
    result.height = lerp(first.height, second.height, blend);
    result.grade = (second.height - first.height) / length(second.position - first.position);
    result.trackStation = lerp(first.trackStation, second.trackStation, blend);
    result.tangent = normalize(second.position - first.position);
    return result;
}

const std::vector<FFPitSection>& FFPitLane::Sections() const {
    return sections;
}

float FFPitLane::SpeedLimitKph() const {
    return speedLimitKph;
}

bool FFComposePitBarriers(std::span<const std::uint8_t> bytes,
    std::span<const AuthoredBarrierSegment> existing, std::vector<AuthoredBarrierSegment>& result) {
    constexpr std::array<std::uint8_t, 8> signature{'F', 'F', 'B', 'A', 'R', '2', 0, 0};
    if (bytes.size() < 16 || !std::equal(signature.begin(), signature.end(), bytes.begin())) return false;
    std::uint32_t count;
    std::uint32_t openingCount;
    std::memcpy(&count, bytes.data() + 8, 4);
    std::memcpy(&openingCount, bytes.data() + 12, 4);
    if (count > 10000 || openingCount == 0 || openingCount > 128 ||
        bytes.size() != 16 + count * 28 + openingCount * 40) return false;
    std::vector<AuthoredBarrierSegment> additions;
    additions.reserve(count);
    for (std::uint32_t index = 0; index < count; ++index) {
        std::array<float, 7> row;
        std::memcpy(row.data(), bytes.data() + 16 + index * 28, 28);
        for (float value : row) if (!std::isfinite(value) || std::abs(value) > 200000.0f) return false;
        if (row[4] >= row[5] || row[6] <= 0.0f || row[6] > 17.0f ||
            lengthSq(Vec2{row[2] - row[0], row[3] - row[1]}) < 0.000001f) return false;
        additions.push_back({{row[0], row[1]}, {row[2], row[3]}, row[4], row[5], row[6]});
    }
    std::vector<FFPitBarrierOpening> openings;
    openings.reserve(openingCount);
    for (std::uint32_t index = 0; index < openingCount; ++index) {
        std::array<float, 10> row;
        std::memcpy(row.data(), bytes.data() + 16 + count * 28 + index * 40, 40);
        for (float value : row) if (!std::isfinite(value) || std::abs(value) > 200000.0f) return false;
        FFPitBarrierOpening opening{{Vec2{row[0], row[1]}, Vec2{row[2], row[3]},
            Vec2{row[4], row[5]}, Vec2{row[6], row[7]}}, row[8], row[9]};
        if (opening.bottom >= opening.top) return false;
        for (std::size_t corner = 0; corner < 4; ++corner) {
            const Vec2 a = opening.corners[corner];
            const Vec2 b = opening.corners[(corner + 1) % 4];
            const Vec2 c = opening.corners[(corner + 2) % 4];
            if (lengthSq(b - a) < 0.000001f || cross(b - a, c - b) <= 0.000001f) return false;
        }
        openings.push_back(opening);
    }
    std::vector<AuthoredBarrierSegment> composed(existing.begin(), existing.end());
    for (const auto& opening : openings) {
        std::vector<AuthoredBarrierSegment> outside;
        outside.reserve(composed.size() + 2);
        for (const auto& segment : composed) {
            if (segment.top <= opening.bottom || segment.bottom >= opening.top) {
                outside.push_back(segment);
                continue;
            }
            float enter = 0.0f;
            float exit = 1.0f;
            const Vec2 delta = segment.b - segment.a;
            for (std::size_t corner = 0; corner < 4 && enter <= exit; ++corner) {
                const Vec2 a = opening.corners[corner];
                const Vec2 edge = opening.corners[(corner + 1) % 4] - a;
                const float first = cross(edge, segment.a - a) + segment.halfThickness * length(edge);
                const float slope = cross(edge, delta);
                if (std::abs(slope) < 0.000001f) {
                    if (first < 0.0f) enter = 2.0f;
                } else if (slope > 0.0f) {
                    enter = std::max(enter, -first / slope);
                } else {
                    exit = std::min(exit, -first / slope);
                }
            }
            if (enter >= exit || enter > 1.0f || exit < 0.0f) {
                outside.push_back(segment);
                continue;
            }
            if (enter > 0.0f) outside.push_back({segment.a, lerp(segment.a, segment.b, enter),
                segment.bottom, segment.top, segment.halfThickness});
            if (exit < 1.0f) outside.push_back({lerp(segment.a, segment.b, exit), segment.b,
                segment.bottom, segment.top, segment.halfThickness});
        }
        composed = std::move(outside);
    }
    composed.insert(composed.end(), additions.begin(), additions.end());
    result = std::move(composed);
    return true;
}

bool FFPitLowerLayerContact(const FFPitProjection& pit, float roadHeightMetres, float vehicleHeightMetres) {
    return pit.inside && pit.height + 1.5f < roadHeightMetres &&
        std::abs(vehicleHeightMetres - pit.height) + 0.5f < std::abs(vehicleHeightMetres - roadHeightMetres);
}
