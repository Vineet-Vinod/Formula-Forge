#include "harbor_karts_3d.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <limits>
#include <memory>
#include <random>
#include <string>
#include <string_view>
#include <vector>

#include <raylib.h>
#include <rlgl.h>
#include <SDL3/SDL.h>

#include "arcade_audio.hpp"
#include "arcade_hud.hpp"
#include "arcade_race.hpp"
#include "arcade_render.hpp"
#include "arcade_vehicle.hpp"
#include "core_math.hpp"
#include "track_renderer.hpp"
#include "track_layout.hpp"

namespace {

constexpr float kFixedDt = 1.0f / 120.0f;
constexpr float kRenderScale = 0.085f;
constexpr int kKartCount = 6;
constexpr int kSampleCount = 1536;
constexpr float kRaceStartProgress = 980.0f;
constexpr float kRoadSurfaceRatio = 0.40f;
constexpr float kRoadLaneInset = 4.0f;
constexpr float kHardBoundaryInset = 18.0f;
constexpr float kTrackSurfaceLift = 0.018f;
constexpr float kKartWheelGroundClearance = 0.42f;
constexpr float kContactProgressWindow = 240.0f;
constexpr float kContactVerticalWindow = 7.0f;
constexpr int kInfiniteLaps = 0;
constexpr std::array<int, 4> kLapOptions = {2, 5, 10, kInfiniteLaps};

Color mix(Color a, Color b, float t) {
    t = std::clamp(t, 0.0f, 1.0f);
    const auto channel = [t](unsigned char av, unsigned char bv) {
        return static_cast<unsigned char>(std::clamp(static_cast<float>(av) + (static_cast<float>(bv) - static_cast<float>(av)) * t,
                                                     0.0f, 255.0f));
    };
    return {channel(a.r, b.r), channel(a.g, b.g), channel(a.b, b.b), channel(a.a, b.a)};
}

Color shade(Color c, float amount) {
    const auto channel = [amount](unsigned char v) {
        return static_cast<unsigned char>(std::clamp(static_cast<float>(v) * amount, 0.0f, 255.0f));
    };
    return {channel(c.r), channel(c.g), channel(c.b), c.a};
}

Vector3 toWorld(Vec2 p, float elevation = 0.0f) {
    return {p.x * kRenderScale, elevation * kRenderScale, p.y * kRenderScale};
}

Vector3 add(Vector3 a, Vector3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
Vector3 sub(Vector3 a, Vector3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
Vector3 mul(Vector3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
Vector3 lift(Vector3 v, float amount) { return {v.x, v.y + amount, v.z}; }

float signedDistanceToLoop(float from, float to, float total) {
    float d = to - from;
    while (d > total * 0.5f) {
        d -= total;
    }
    while (d < -total * 0.5f) {
        d += total;
    }
    return d;
}

bool hasArg(int argc, char** argv, std::string_view arg) {
    for (int i = 1; i < argc; ++i) {
        if (arg == argv[i]) {
            return true;
        }
    }
    return false;
}

struct TrackPoint3D {
    Vec2 pos;
    Vec2 tangent{1.0f, 0.0f};
    Vec2 normal{0.0f, 1.0f};
    float progress = 0.0f;
    float width = 180.0f;
    float elevation = 0.0f;
    float bank = 0.0f;
    float curvature = 0.0f;
    float signedCurvature = 0.0f;
    float grade = 0.0f;
    float launchVelocity = 0.0f;
    Color road = {206, 122, 67, 255};
    Color shoulder = {239, 199, 111, 255};
    Color natural = {244, 207, 124, 255};
    int zone = 0;
};

float bankedElevation(const TrackPoint3D& point, float lane) {
    const float half = std::max(1.0f, point.width * 0.5f);
    return point.elevation + point.bank * std::clamp(lane / half, -1.2f, 1.2f);
}

float bankRollDegrees(const TrackPoint3D& point) {
    const float half = std::max(1.0f, point.width * 0.5f);
    return -std::atan2(point.bank, half) * RAD2DEG;
}

struct Prop3D {
    enum class Type { Palm, Rock, Hut, Boat, Market, Crane, Crystal, Torch, Gate, Chevron, Cliff, Sail };

    Type type = Type::Palm;
    float progress = 0.0f;
    float side = 0.0f;
    float scale = 1.0f;
    Color color = {60, 159, 91, 255};
};

struct ZoneMaterial3D {
    Color road = {214, 142, 76, 255};
    Color shoulder = {240, 198, 108, 255};
    Color natural = {244, 207, 124, 255};
};

ZoneMaterial3D baseZoneMaterial(int zone) {
    switch (zone) {
        case 1:
            return {{150, 101, 65, 255}, {176, 128, 82, 255}, {204, 168, 103, 255}};
        case 2:
            return {{211, 134, 84, 255}, {232, 181, 100, 255}, {229, 174, 98, 255}};
        case 3:
            return {{98, 98, 99, 255}, {111, 108, 99, 255}, {125, 119, 101, 255}};
        case 4:
            return {{137, 153, 100, 255}, {122, 166, 96, 255}, {109, 169, 94, 255}};
        case 5:
            return {{147, 108, 74, 255}, {123, 150, 124, 255}, {82, 168, 166, 255}};
        case 6:
            return {{216, 149, 82, 255}, {239, 200, 112, 255}, {241, 199, 109, 255}};
        default:
            return {{224, 156, 86, 255}, {242, 205, 119, 255}, {244, 209, 130, 255}};
    }
}

ZoneMaterial3D mixMaterial(ZoneMaterial3D a, ZoneMaterial3D b, float t) {
    return {mix(a.road, b.road, t), mix(a.shoulder, b.shoulder, t), mix(a.natural, b.natural, t)};
}

int zoneForPhase(float phase) {
    if (phase < 0.30f) {
        return 0;
    }
    if (phase < 0.60f) {
        return 2;
    }
    if (phase < 0.90f) {
        return 4;
    }
    return 0;
}

float trackWidthForZone(int zone) {
    switch (zone) {
        case 2:
            return 190.0f;
        case 4:
            return 202.0f;
        default:
            return 216.0f;
    }
}

ZoneMaterial3D materialForPhase(float phase) {
    ZoneMaterial3D material = baseZoneMaterial(zoneForPhase(phase));
    static constexpr float kBlend = 0.034f;
    static constexpr std::array<std::array<float, 3>, 3> kBoundaries = {
        {{0.30f, 0.0f, 2.0f}, {0.60f, 2.0f, 4.0f}, {0.90f, 4.0f, 0.0f}}};
    for (const auto& boundary : kBoundaries) {
        const float p = boundary[0];
        if (phase >= p - kBlend && phase <= p + kBlend) {
            const float t = smoothstep((phase - (p - kBlend)) / (kBlend * 2.0f));
            material = mixMaterial(baseZoneMaterial(static_cast<int>(boundary[1])), baseZoneMaterial(static_cast<int>(boundary[2])), t);
        }
    }
    return material;
}

float elevationForPhase(float phase) {
    phase -= std::floor(phase);
    static constexpr std::array<std::array<float, 2>, 10> kElevation = {{{0.00f, 4.0f},
                                                                         {0.10f, 2.0f},
                                                                         {0.18f, 13.0f},
                                                                         {0.29f, 13.0f},
                                                                         {0.42f, 5.0f},
                                                                         {0.58f, 32.0f},
                                                                         {0.72f, 8.0f},
                                                                         {0.85f, 11.0f},
                                                                         {0.96f, 4.0f},
                                                                         {1.00f, 4.0f}}};
    for (size_t i = 0; i + 1 < kElevation.size(); ++i) {
        const float a = kElevation[i][0];
        const float b = kElevation[i + 1][0];
        if (phase >= a && phase <= b) {
            const float t = smoothstep((phase - a) / std::max(0.001f, b - a));
            return lerp(kElevation[i][1], kElevation[i + 1][1], t);
        }
    }
    return kElevation.back()[1];
}

float signedPhaseDistance(float phase, float center) {
    float d = phase - center;
    while (d > 0.5f) d -= 1.0f;
    while (d < -0.5f) d += 1.0f;
    return d;
}

float rampHeightForPhase(float phase) {
    static constexpr std::array<float, 3> kRampCenters = {0.105f, 0.455f, 0.765f};
    float height = 0.0f;
    for (float center : kRampCenters) {
        const float d = signedPhaseDistance(phase, center);
        if (d >= -0.008f && d < -0.001f) {
            height += lerp(0.0f, 12.0f, smoothstep((d + 0.008f) / 0.007f));
        } else if (d >= -0.001f && d <= 0.012f) {
            height += lerp(12.0f, 0.0f, smoothstep((d + 0.001f) / 0.013f));
        }
    }
    return height;
}

float rampLaunchForPhase(float phase) {
    static constexpr std::array<float, 3> kRampCenters = {0.105f, 0.455f, 0.765f};
    for (float center : kRampCenters) {
        const float d = signedPhaseDistance(phase, center);
        if (d >= -0.0015f && d <= 0.0008f) {
            return 43.0f;
        }
    }
    return 0.0f;
}

class Track3D {
public:
    Track3D() { build(); }

    float totalLength() const { return totalLength_; }
    int sampleCount() const { return static_cast<int>(samples_.size()); }
    const std::vector<TrackPoint3D>& samples() const { return samples_; }
    const std::vector<Prop3D>& props() const { return props_; }

    TrackPoint3D sample(float progress) const {
        progress = wrapDistance(progress, totalLength_);
        const float u = progress / totalLength_ * static_cast<float>(samples_.size());
        const int i0 = static_cast<int>(std::floor(u)) % sampleCount();
        const int i1 = (i0 + 1) % sampleCount();
        const float t = u - std::floor(u);
        const TrackPoint3D& a = samples_[static_cast<size_t>(i0)];
        const TrackPoint3D& b = samples_[static_cast<size_t>(i1)];

        TrackPoint3D out = a;
        out.pos = lerp(a.pos, b.pos, t);
        out.tangent = normalize(lerp(a.tangent, b.tangent, t));
        out.normal = {-out.tangent.y, out.tangent.x};
        out.progress = progress;
        out.width = lerp(a.width, b.width, t);
        out.elevation = lerp(a.elevation, b.elevation, t);
        out.bank = lerp(a.bank, b.bank, t);
        out.curvature = lerp(a.curvature, b.curvature, t);
        out.signedCurvature = lerp(a.signedCurvature, b.signedCurvature, t);
        out.grade = lerp(a.grade, b.grade, t);
        out.launchVelocity = std::max(a.launchVelocity, b.launchVelocity);
        out.road = mix(a.road, b.road, t);
        out.shoulder = mix(a.shoulder, b.shoulder, t);
        out.natural = mix(a.natural, b.natural, t);
        out.zone = t < 0.5f ? a.zone : b.zone;
        return out;
    }

    const TrackPoint3D& pointAtIndex(int index) const { return samples_[static_cast<size_t>(wrappedIndex(index))]; }

    int nearestIndex(Vec2 pos) const {
        int best = 0;
        float bestDist = std::numeric_limits<float>::max();
        for (int i = 0; i < sampleCount(); ++i) {
            const float d = lengthSq(samples_[static_cast<size_t>(i)].pos - pos);
            if (d < bestDist) {
                best = i;
                bestDist = d;
            }
        }
        return best;
    }

    int nearestIndexNear(Vec2 pos, int hint, int radius = 24) const {
        int best = wrappedIndex(hint);
        float bestScore = lengthSq(samples_[static_cast<size_t>(best)].pos - pos);
        for (int offset = -radius; offset <= radius; ++offset) {
            const int index = wrappedIndex(hint + offset);
            const float d = lengthSq(samples_[static_cast<size_t>(index)].pos - pos);
            const float score = d + static_cast<float>(offset * offset) * 25.0f;
            if (score < bestScore) {
                best = index;
                bestScore = score;
            }
        }
        return best;
    }

    Vector3 roadPoint(const TrackPoint3D& point, float lane) const {
        return toWorld(point.pos + point.normal * lane, bankedElevation(point, lane));
    }

private:
    int wrappedIndex(int index) const {
        const int count = sampleCount();
        int wrapped = index % count;
        if (wrapped < 0) {
            wrapped += count;
        }
        return wrapped;
    }

    static Vec2 catmull(Vec2 p0, Vec2 p1, Vec2 p2, Vec2 p3, float t) {
        const float t2 = t * t;
        const float t3 = t2 * t;
        return (p1 * 2.0f + (p2 - p0) * t + (p0 * 2.0f - p1 * 5.0f + p2 * 4.0f - p3) * t2 +
                (p3 - p0 + (p1 - p2) * 3.0f) * t3) *
               0.5f;
    }

    static TrackPoint3D decorate(TrackPoint3D point, float phase) {
        phase -= std::floor(phase);
        const ZoneMaterial3D material = materialForPhase(phase);
        point.zone = zoneForPhase(phase);
        point.width = trackWidthForZone(point.zone);
        point.road = material.road;
        point.shoulder = material.shoulder;
        point.natural = material.natural;

        point.elevation += elevationForPhase(phase);
        point.elevation += 1.8f * std::sin(phase * kTwoPi * 3.0f);
        point.elevation += rampHeightForPhase(phase);
        point.launchVelocity = rampLaunchForPhase(phase);
        return point;
    }

    void build() {
        const auto& control = kSharkHarborControlPoints;
        const auto controlPoint = [&control](int index) {
            const int count = static_cast<int>(control.size());
            int wrapped = index % count;
            if (wrapped < 0) {
                wrapped += count;
            }
            const TrackControlPoint& p = control[static_cast<size_t>(wrapped)];
            return Vec2{p.x * kSharkHarborCourseScale, p.y * kSharkHarborCourseScale};
        };

        std::vector<Vec2> dense;
        constexpr int kSteps = 32;
        for (int i = 0; i < static_cast<int>(control.size()); ++i) {
            const Vec2 p0 = controlPoint(i - 1);
            const Vec2 p1 = controlPoint(i);
            const Vec2 p2 = controlPoint(i + 1);
            const Vec2 p3 = controlPoint(i + 2);
            for (int s = 0; s < kSteps; ++s) {
                dense.push_back(catmull(p0, p1, p2, p3, static_cast<float>(s) / kSteps));
            }
        }

        std::vector<float> cumulative(dense.size() + 1, 0.0f);
        for (size_t i = 0; i < dense.size(); ++i) {
            cumulative[i + 1] = cumulative[i] + length(dense[(i + 1) % dense.size()] - dense[i]);
        }
        totalLength_ = cumulative.back();

        samples_.resize(kSampleCount);
        for (int i = 0; i < kSampleCount; ++i) {
            const float desired = totalLength_ * static_cast<float>(i) / kSampleCount;
            auto it = std::upper_bound(cumulative.begin(), cumulative.end(), desired);
            int seg = std::max(0, static_cast<int>(it - cumulative.begin()) - 1);
            if (seg >= static_cast<int>(dense.size())) {
                seg = static_cast<int>(dense.size()) - 1;
            }
            const float span = cumulative[static_cast<size_t>(seg + 1)] - cumulative[static_cast<size_t>(seg)];
            const float t = span > 0.001f ? (desired - cumulative[static_cast<size_t>(seg)]) / span : 0.0f;
            TrackPoint3D point;
            point.progress = desired;
            point.pos = lerp(dense[static_cast<size_t>(seg)], dense[static_cast<size_t>((seg + 1) % dense.size())], t);
            samples_[static_cast<size_t>(i)] = decorate(point, desired / totalLength_);
        }

        for (int i = 0; i < kSampleCount; ++i) {
            TrackPoint3D& p = samples_[static_cast<size_t>(i)];
            const Vec2 prev = samples_[static_cast<size_t>((i - 3 + kSampleCount) % kSampleCount)].pos;
            const Vec2 next = samples_[static_cast<size_t>((i + 3) % kSampleCount)].pos;
            p.tangent = normalize(next - prev);
            p.normal = {-p.tangent.y, p.tangent.x};
        }
        for (int i = 0; i < kSampleCount; ++i) {
            const Vec2 a = samples_[static_cast<size_t>((i - 8 + kSampleCount) % kSampleCount)].tangent;
            const Vec2 b = samples_[static_cast<size_t>((i + 8) % kSampleCount)].tangent;
            const float signedTurn = wrapAngle(angleOf(b) - angleOf(a));
            TrackPoint3D& p = samples_[static_cast<size_t>(i)];
            p.signedCurvature = signedTurn;
            p.curvature = std::abs(signedTurn);
            p.bank = std::clamp(-signedTurn * 140.0f, -13.0f, 13.0f);
            const TrackPoint3D& elevationPrev = samples_[static_cast<size_t>((i - 2 + kSampleCount) % kSampleCount)];
            const TrackPoint3D& elevationNext = samples_[static_cast<size_t>((i + 2) % kSampleCount)];
            const float horizontalSpan = std::max(0.01f, length(elevationNext.pos - elevationPrev.pos));
            p.grade = (elevationNext.elevation - elevationPrev.elevation) / horizontalSpan;
        }

        buildProps();
    }

    void buildProps() {
        std::mt19937 rng(3119);
        std::uniform_real_distribution<float> jitter(-24.0f, 24.0f);
        const int count = 156;
        for (int i = 0; i < count; ++i) {
            const float p = wrapDistance(totalLength_ * (static_cast<float>(i) + 0.23f) / count + jitter(rng), totalLength_);
            if (std::abs(signedDistanceToLoop(kRaceStartProgress, p, totalLength_)) < 620.0f) {
                continue;
            }
            const TrackPoint3D tp = sample(p);
            Prop3D prop;
            prop.progress = p;
            const float sideSign = (i % 2 == 0) ? -1.0f : 1.0f;
            prop.side = sideSign * (tp.width * 0.5f + 130.0f + static_cast<float>((i * 17) % 145));
            prop.scale = 0.75f + static_cast<float>((i * 11) % 9) * 0.09f;

            if (tp.zone == 0) {
                prop.type = (i % 9 == 0) ? Prop3D::Type::Boat
                                         : ((i % 5 == 0) ? Prop3D::Type::Hut : ((i % 3 == 0) ? Prop3D::Type::Sail : Prop3D::Type::Palm));
                prop.color = (i % 4 == 0) ? Color{235, 82, 62, 255} : Color{245, 191, 56, 255};
            } else if (tp.zone == 2) {
                prop.type = (i % 5 == 0) ? Prop3D::Type::Market : ((i % 7 == 0) ? Prop3D::Type::Crane : Prop3D::Type::Hut);
                prop.color = (i % 3 == 0) ? Color{238, 69, 91, 255} : Color{48, 167, 157, 255};
            } else {
                prop.type = (i % 6 == 0) ? Prop3D::Type::Cliff : ((i % 4 == 0) ? Prop3D::Type::Rock : Prop3D::Type::Palm);
                prop.color = (i % 6 == 0) ? Color{93, 116, 82, 255} : Color{45, 145, 76, 255};
            }
            if (prop.type == Prop3D::Type::Chevron) {
                const float outside = std::abs(tp.signedCurvature) > 0.015f ? -std::copysign(1.0f, tp.signedCurvature) : sideSign;
                prop.side = outside * (tp.width * 0.5f + 112.0f);
                prop.scale *= 1.30f;
            } else if (prop.type == Prop3D::Type::Palm || prop.type == Prop3D::Type::Crane || prop.type == Prop3D::Type::Cliff ||
                       prop.type == Prop3D::Type::Crystal) {
                prop.side += sideSign * 72.0f;
            }
            props_.push_back(prop);
        }

        auto addLandmark = [&](float phase, float sideSign, float extra, float scale, Prop3D::Type type, Color color) {
            const float p = wrapDistance(totalLength_ * phase, totalLength_);
            const TrackPoint3D tp = sample(p);
            props_.push_back({type, p, sideSign * (tp.width * 0.5f + extra), scale, color});
        };
        addLandmark(0.105f, 1.0f, 92.0f, 1.70f, Prop3D::Type::Chevron, Color{238, 62, 54, 255});
        addLandmark(0.205f, -1.0f, 160.0f, 2.15f, Prop3D::Type::Boat, Color{239, 191, 56, 255});
        addLandmark(0.325f, 1.0f, 142.0f, 2.20f, Prop3D::Type::Market, Color{239, 70, 91, 255});
        addLandmark(0.455f, -1.0f, 136.0f, 2.00f, Prop3D::Type::Crane, Color{236, 92, 51, 255});
        addLandmark(0.610f, 1.0f, 145.0f, 2.25f, Prop3D::Type::Hut, Color{52, 151, 90, 255});
        addLandmark(0.765f, -1.0f, 138.0f, 2.45f, Prop3D::Type::Cliff, Color{92, 117, 83, 255});
        addLandmark(0.900f, 1.0f, 142.0f, 2.10f, Prop3D::Type::Palm, Color{47, 157, 84, 255});
    }

    std::vector<TrackPoint3D> samples_;
    std::vector<Prop3D> props_;
    float totalLength_ = 1.0f;
};

struct KartSpec3D {
    std::string name;
    Color body;
    Color accent;
    Color glass;
    float maxSpeed = 145.0f;
    float accel = 128.0f;
    float brake = 205.0f;
    float grip = 1.0f;
    float drift = 1.0f;
    float width = 34.0f;
    float length = 48.0f;
    float height = 15.0f;
    int bodyStyle = 0;
};

ArcadeVehicleConfig tuningForSpec(const KartSpec3D& spec) {
    ArcadeVehicleConfig tuning;
    tuning.maxForwardSpeed = spec.maxSpeed * 1.64f;
    tuning.engineAcceleration = spec.accel * 0.72f;
    tuning.launchAccelerationBonus = spec.accel * 0.27f;
    tuning.brakeDeceleration = spec.brake * 1.52f;
    tuning.wheelbase = spec.length * 0.72f;
    tuning.wheelRadius = std::max(6.0f, spec.height * 0.52f);
    tuning.lateralGripAcceleration *= spec.grip;
    tuning.driftGripAcceleration *= spec.grip * 0.96f;
    tuning.driftYawBase *= spec.drift;
    tuning.driftYawSpeedGain *= spec.drift;
    tuning.driftChargeRate *= 1.12f * spec.drift;
    tuning.maxBodyRoll *= 1.08f;
    return tuning;
}

std::array<KartSpec3D, 8> makeKartSpecs() {
    return {{
        {"TIDE HOPPER", {224, 57, 56, 255}, {255, 202, 63, 255}, {82, 205, 224, 255}, 198.0f, 258.0f, 214.0f, 1.02f, 1.05f, 34.0f, 48.0f, 15.0f, 0},
        {"REEF RUNNER", {35, 151, 211, 255}, {255, 235, 90, 255}, {111, 222, 227, 255}, 204.0f, 240.0f, 208.0f, 0.98f, 1.14f, 32.0f, 51.0f, 14.0f, 1},
        {"DUNE FOX", {240, 139, 45, 255}, {47, 61, 76, 255}, {95, 201, 217, 255}, 190.0f, 278.0f, 222.0f, 1.09f, 1.00f, 38.0f, 46.0f, 16.0f, 2},
        {"PIER SHARK", {61, 81, 103, 255}, {232, 67, 61, 255}, {91, 205, 217, 255}, 210.0f, 224.0f, 204.0f, 0.94f, 1.22f, 33.0f, 55.0f, 13.0f, 3},
        {"MANGO MULE", {246, 199, 62, 255}, {30, 133, 76, 255}, {110, 210, 222, 255}, 184.0f, 292.0f, 232.0f, 1.15f, 0.96f, 41.0f, 44.0f, 18.0f, 4},
        {"LAGOON GT", {34, 184, 143, 255}, {238, 73, 95, 255}, {151, 232, 235, 255}, 206.0f, 246.0f, 212.0f, 1.01f, 1.11f, 32.0f, 52.0f, 14.0f, 5},
        {"TIKI RAIL", {132, 78, 44, 255}, {248, 125, 54, 255}, {98, 196, 210, 255}, 194.0f, 266.0f, 220.0f, 1.06f, 1.08f, 36.0f, 47.0f, 19.0f, 6},
        {"STORM BUGGY", {116, 105, 175, 255}, {255, 213, 65, 255}, {101, 215, 229, 255}, 202.0f, 254.0f, 216.0f, 1.01f, 1.16f, 34.0f, 50.0f, 15.0f, 7},
    }};
}

std::array<std::string, 10> makeRacers() {
    return {"KAI", "MAYA", "BRUNO", "LANI", "REX", "NOVA", "SKIP", "ZARA", "COBALT", "TESS"};
}

uint32_t stableHash(std::string_view text) {
    uint32_t hash = 2166136261u;
    for (char ch : text) {
        hash ^= static_cast<uint8_t>(ch);
        hash *= 16777619u;
    }
    return hash;
}

Color racerColor(std::string_view racer) {
    static constexpr std::array<Color, 10> palette = {
        Color{255, 211, 80, 255}, Color{238, 78, 91, 255},  Color{71, 185, 131, 255}, Color{76, 151, 224, 255},
        Color{245, 132, 58, 255}, Color{179, 112, 219, 255}, Color{242, 233, 201, 255}, Color{39, 51, 63, 255},
        Color{86, 214, 222, 255}, Color{245, 164, 196, 255},
    };
    const uint32_t hash = stableHash(racer);
    return palette[hash % palette.size()];
}

struct Input3D {
    float steer = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
    bool drift = false;
    bool a = false;
    bool b = false;
    bool bHeld = false;
    bool start = false;
    bool back = false;
    bool left = false;
    bool right = false;
    bool up = false;
    bool down = false;
    bool pageLeft = false;
    bool pageRight = false;
    bool quit = false;
};

float axisWithDeadzone(float value) {
    value = std::clamp(value, -1.0f, 1.0f);
    const float dead = 0.11f;
    if (std::abs(value) < dead) {
        return 0.0f;
    }
    const float sign = value < 0.0f ? -1.0f : 1.0f;
    const float normalized = (std::abs(value) - dead) / (1.0f - dead);
    const float curved = 0.72f * normalized + 0.28f * normalized * normalized * normalized;
    return sign * curved;
}

float normalizeRaylibTrigger(float raw, bool& signedRange) {
    raw = std::clamp(raw, -1.0f, 1.0f);
    if (raw < -0.50f) {
        signedRange = true;
    }
    const float normalized = signedRange ? std::clamp((raw + 1.0f) * 0.5f, 0.0f, 1.0f) : std::clamp(raw, 0.0f, 1.0f);
    return normalized < 0.035f ? 0.0f : (normalized - 0.035f) / 0.965f;
}

float triggerValue(int gamepad, int axis, bool& signedRange) {
    return normalizeRaylibTrigger(GetGamepadAxisMovement(gamepad, axis), signedRange);
}

float canonicalHardBrake(float leftTrigger, bool bHeld) {
    constexpr float kPressedThreshold = 0.12f;
    return (leftTrigger >= kPressedThreshold || bHeld) ? 1.0f : 0.0f;
}

Input3D canonicalPlayerInput(Input3D input) {
    input.brake = canonicalHardBrake(input.brake, input.bHeld);
    return input;
}

bool controllerContractAudit() {
    bool zeroBased = false;
    const float zeroReleased = normalizeRaylibTrigger(0.0f, zeroBased);
    const float zeroPressed = normalizeRaylibTrigger(1.0f, zeroBased);
    bool signedRange = false;
    const float signedReleased = normalizeRaylibTrigger(-1.0f, signedRange);
    const float signedHalf = normalizeRaylibTrigger(0.0f, signedRange);
    const float signedPressed = normalizeRaylibTrigger(1.0f, signedRange);
    std::array<Input3D, 5> bSequence{};
    bSequence[1].bHeld = true;
    bSequence[2].bHeld = true;
    const std::array<float, 5> expectedBrake = {0.0f, 1.0f, 1.0f, 0.0f, 0.0f};
    bool bReleaseClears = true;
    for (size_t i = 0; i < bSequence.size(); ++i) {
        bReleaseClears = bReleaseClears && canonicalPlayerInput(bSequence[i]).brake == expectedBrake[i];
    }
    return canonicalHardBrake(0.0f, false) == 0.0f && canonicalHardBrake(0.20f, false) == 1.0f &&
           canonicalHardBrake(0.55f, false) == 1.0f && canonicalHardBrake(1.0f, false) == 1.0f &&
           canonicalHardBrake(0.0f, true) == 1.0f && canonicalHardBrake(1.0f, true) == 1.0f && bReleaseClears &&
           zeroReleased == 0.0f && zeroPressed == 1.0f && signedReleased == 0.0f && signedHalf > 0.45f &&
           signedHalf < 0.55f && signedPressed == 1.0f;
}

float sdlAxisUnit(Sint16 value) {
    const float f = static_cast<float>(value) / 32767.0f;
    return std::abs(f) < 0.08f ? 0.0f : std::clamp(f, -1.0f, 1.0f);
}

float sdlTriggerUnit(Sint16 value) {
    if (value <= 0) {
        return 0.0f;
    }
    return std::clamp(static_cast<float>(value) / 32767.0f, 0.0f, 1.0f);
}

float rawJoystickAxis(SDL_Joystick* joystick, int axis) {
    if (!joystick || axis < 0 || axis >= SDL_GetNumJoystickAxes(joystick)) {
        return 0.0f;
    }
    return sdlAxisUnit(SDL_GetJoystickAxis(joystick, axis));
}

bool rawJoystickButton(SDL_Joystick* joystick, int button) {
    return joystick && button >= 0 && button < SDL_GetNumJoystickButtons(joystick) && SDL_GetJoystickButton(joystick, button);
}

void applyKeyboardFallback(Input3D& input, bool keyboardEnabled) {
    if (!keyboardEnabled) {
        return;
    }
    const float keyboardSteer = (IsKeyDown(KEY_RIGHT) || IsKeyDown(KEY_D) ? 1.0f : 0.0f) -
                                (IsKeyDown(KEY_LEFT) || IsKeyDown(KEY_A) ? 1.0f : 0.0f);
    if (std::abs(keyboardSteer) > std::abs(input.steer)) {
        input.steer = keyboardSteer;
    }
    input.throttle = (IsKeyDown(KEY_UP) || IsKeyDown(KEY_W)) ? 1.0f : input.throttle;
    input.brake = (IsKeyDown(KEY_DOWN) || IsKeyDown(KEY_S)) ? 1.0f : input.brake;
    input.drift = input.drift || IsKeyDown(KEY_RIGHT_SHIFT) || IsKeyDown(KEY_LEFT_SHIFT) || IsKeyDown(KEY_SPACE);
    input.a = input.a || IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_SPACE);
    input.b = input.b || IsKeyPressed(KEY_BACKSPACE);
    input.start = input.start || IsKeyPressed(KEY_P) || IsKeyPressed(KEY_ESCAPE);
    input.back = input.back || IsKeyPressed(KEY_R);
    input.left = input.left || IsKeyPressed(KEY_A) || IsKeyPressed(KEY_LEFT);
    input.right = input.right || IsKeyPressed(KEY_D) || IsKeyPressed(KEY_RIGHT);
    input.up = input.up || IsKeyPressed(KEY_W);
    input.down = input.down || IsKeyPressed(KEY_S);
    input.pageLeft = input.pageLeft || IsKeyPressed(KEY_Q);
    input.pageRight = input.pageRight || IsKeyPressed(KEY_E);
    input.quit = input.quit || IsKeyPressed(KEY_F10);
}

class ControllerReader {
public:
    explicit ControllerReader(bool sdlFallbackReady) : sdlFallbackReady_(sdlFallbackReady) {}

    ~ControllerReader() {
        close();
    }

    void shutdown() { close(); }

    bool available() {
        if (IsGamepadAvailable(0)) {
            return true;
        }
        refresh();
        return pad_ != nullptr || joystick_ != nullptr;
    }

    Input3D read(bool devKeyboard) {
        updateSdlState();
        refresh();
        Input3D input;
        if (pad_) {
            mergeSdl(input);
        } else if (IsGamepadAvailable(0)) {
            input = readRaylib();
        } else if (joystick_) {
            mergeSdl(input);
        }
        applyKeyboardFallback(input, devKeyboard);
        input.brake = canonicalHardBrake(input.brake, input.bHeld);
        return edgeFiltered(input);
    }

    void printSnapshot() {
        refresh();
        if (IsGamepadAvailable(0)) {
            std::cout << "raylib controller: " << GetGamepadName(0) << " steer=" << GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_X)
                      << " lt=" << triggerValue(0, GAMEPAD_AXIS_LEFT_TRIGGER, raylibLeftTriggerSigned_)
                      << " rt=" << triggerValue(0, GAMEPAD_AXIS_RIGHT_TRIGGER, raylibRightTriggerSigned_)
                      << " rb=" << IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_TRIGGER_1)
                      << " a=" << IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_FACE_DOWN) << "\n";
        }
        if (pad_) {
            std::cout << "sdl gamepad: " << SDL_GetGamepadName(pad_) << " steer=" << sdlAxisUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_LEFTX))
                      << " lt=" << sdlTriggerUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_LEFT_TRIGGER))
                      << " rt=" << sdlTriggerUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER))
                      << " rb=" << SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER)
                      << " a=" << SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_SOUTH) << "\n";
        } else if (joystick_) {
            std::cout << "sdl joystick: " << SDL_GetJoystickName(joystick_) << " axes=" << SDL_GetNumJoystickAxes(joystick_)
                      << " buttons=" << SDL_GetNumJoystickButtons(joystick_) << " steer=" << rawJoystickAxis(joystick_, 0)
                      << " lt=" << std::max(0.0f, rawJoystickAxis(joystick_, 2))
                      << " rt=" << std::max(0.0f, rawJoystickAxis(joystick_, 5)) << " rb=" << rawJoystickButton(joystick_, 5)
                      << " a=" << rawJoystickButton(joystick_, 0) << "\n";
        }
        if (!IsGamepadAvailable(0) && !pad_ && !joystick_) {
            std::cout << "controller: none\n";
        }
    }

private:
    Input3D readRaylib() {
        Input3D input;
        if (IsGamepadAvailable(0)) {
            input.steer = axisWithDeadzone(GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_X));
            input.throttle = triggerValue(0, GAMEPAD_AXIS_RIGHT_TRIGGER, raylibRightTriggerSigned_);
            input.brake = triggerValue(0, GAMEPAD_AXIS_LEFT_TRIGGER, raylibLeftTriggerSigned_);
            input.drift = IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_TRIGGER_1);
            input.a = IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_FACE_DOWN);
            input.bHeld = IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_FACE_RIGHT);
            input.start = IsGamepadButtonDown(0, GAMEPAD_BUTTON_MIDDLE_RIGHT);
            input.back = IsGamepadButtonDown(0, GAMEPAD_BUTTON_MIDDLE_LEFT);
            input.left = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_LEFT) || input.steer < -0.55f;
            input.right = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_RIGHT) || input.steer > 0.55f;
            input.up = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_UP);
            input.down = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_DOWN);
            const float dpadSteer = (IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_RIGHT) ? 1.0f : 0.0f) -
                                    (IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_LEFT) ? 1.0f : 0.0f);
            if (std::abs(dpadSteer) > std::abs(input.steer)) {
                input.steer = dpadSteer;
            }
            input.pageLeft = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_TRIGGER_1);
            input.pageRight = IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_TRIGGER_1);
        } else {
            raylibLeftTriggerSigned_ = false;
            raylibRightTriggerSigned_ = false;
        }
        return input;
    }

    Input3D edgeFiltered(const Input3D& current) {
        const auto pressed = [](bool now, bool before) { return now && !before; };
        Input3D out = current;
        out.a = pressed(current.a, previousDigital_.a);
        out.b = current.b || pressed(current.bHeld, previousDigital_.bHeld);
        out.start = pressed(current.start, previousDigital_.start);
        out.back = pressed(current.back, previousDigital_.back);
        out.left = pressed(current.left, previousDigital_.left);
        out.right = pressed(current.right, previousDigital_.right);
        out.up = pressed(current.up, previousDigital_.up);
        out.down = pressed(current.down, previousDigital_.down);
        out.pageLeft = pressed(current.pageLeft, previousDigital_.pageLeft);
        out.pageRight = pressed(current.pageRight, previousDigital_.pageRight);
        out.quit = current.quit || (current.start && current.back);
        previousDigital_ = current;
        return out;
    }

    void updateSdlState() {
        if (!sdlFallbackReady_) {
            return;
        }
        SDL_PumpEvents();
        SDL_UpdateGamepads();
        SDL_UpdateJoysticks();
    }

    void refresh() {
        if (!sdlFallbackReady_) {
            return;
        }
        if (pad_ && SDL_GamepadConnected(pad_)) {
            joystick_ = SDL_GetGamepadJoystick(pad_);
            return;
        }
        if (joystick_ && SDL_JoystickConnected(joystick_)) {
            return;
        }
        close();

        int count = 0;
        SDL_JoystickID* pads = SDL_GetGamepads(&count);
        if (pads && count > 0) {
            pad_ = SDL_OpenGamepad(pads[0]);
            if (pad_) {
                joystick_ = SDL_GetGamepadJoystick(pad_);
            }
        }
        SDL_free(pads);
        if (pad_) {
            return;
        }

        SDL_JoystickID* joysticks = SDL_GetJoysticks(&count);
        if (joysticks && count > 0) {
            joystick_ = SDL_OpenJoystick(joysticks[0]);
        }
        SDL_free(joysticks);
    }

    void close() {
        if (pad_) {
            SDL_CloseGamepad(pad_);
            pad_ = nullptr;
            joystick_ = nullptr;
        } else if (joystick_) {
            SDL_CloseJoystick(joystick_);
            joystick_ = nullptr;
        }
        previousDigital_ = {};
        raylibLeftTriggerSigned_ = false;
        raylibRightTriggerSigned_ = false;
    }

    void mergeSdl(Input3D& input) {
        if (pad_) {
            input.steer = std::abs(input.steer) > 0.01f ? input.steer : axisWithDeadzone(sdlAxisUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_LEFTX)));
            input.throttle = std::max(input.throttle, sdlTriggerUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)));
            input.brake = std::max(input.brake, sdlTriggerUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_LEFT_TRIGGER)));
            input.drift = input.drift || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER);
            input.a = input.a || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_SOUTH);
            input.bHeld = input.bHeld || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_EAST);
            input.start = input.start || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_START);
            input.back = input.back || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_BACK);
            input.left = input.left || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_LEFT) || input.steer < -0.55f;
            input.right = input.right || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_RIGHT) || input.steer > 0.55f;
            input.up = input.up || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_UP);
            input.down = input.down || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_DOWN);
            input.pageLeft = input.pageLeft || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_LEFT_SHOULDER);
            input.pageRight = input.pageRight || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER);
            const float dpadSteer = (SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_RIGHT) ? 1.0f : 0.0f) -
                                    (SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_LEFT) ? 1.0f : 0.0f);
            if (std::abs(dpadSteer) > std::abs(input.steer)) {
                input.steer = dpadSteer;
            }
        } else if (joystick_) {
            input.steer = std::abs(input.steer) > 0.01f ? input.steer : axisWithDeadzone(rawJoystickAxis(joystick_, 0));
            input.throttle = std::max(input.throttle, std::max(0.0f, rawJoystickAxis(joystick_, 5)));
            input.brake = std::max(input.brake, std::max(0.0f, rawJoystickAxis(joystick_, 2)));
            input.drift = input.drift || rawJoystickButton(joystick_, 5);
            input.a = input.a || rawJoystickButton(joystick_, 0);
            input.back = input.back || rawJoystickButton(joystick_, 6);
            input.start = input.start || rawJoystickButton(joystick_, 7);
            input.pageLeft = input.pageLeft || rawJoystickButton(joystick_, 4);
            input.pageRight = input.pageRight || rawJoystickButton(joystick_, 5);
            input.bHeld = input.bHeld || rawJoystickButton(joystick_, 1);
            input.left = input.left || rawJoystickButton(joystick_, 11) || input.steer < -0.55f;
            input.right = input.right || rawJoystickButton(joystick_, 12) || input.steer > 0.55f;
            input.up = input.up || rawJoystickButton(joystick_, 13);
            input.down = input.down || rawJoystickButton(joystick_, 14);
        }
    }

    SDL_Gamepad* pad_ = nullptr;
    SDL_Joystick* joystick_ = nullptr;
    Input3D previousDigital_{};
    bool sdlFallbackReady_ = false;
    bool raylibLeftTriggerSigned_ = false;
    bool raylibRightTriggerSigned_ = false;
};

Input3D readInput(ControllerReader& controller, bool devKeyboard) {
    return controller.read(devKeyboard);
}

struct Kart3D : ArcadeVehicleState {
    KartSpec3D spec;
    ArcadeVehicleConfig tuning;
    ArcadeVehicleTelemetry telemetry;
    std::string racer;
    float progress = 0.0f;
    float previousProgress = 0.0f;
    int nearest = 0;
    int lap = 0;
    float lane = 0.0f;
    float aiTempo = 1.0f;
    float aiRisk = 0.4f;
    float aiPass = 1.0f;
    float aiLaneIntent = 0.0f;
    float aiIntentTimer = 0.0f;
    float ghostTimer = 0.0f;
    float stuckTimer = 0.0f;
};

struct Particle3D {
    Vec2 pos;
    Vec2 vel;
    float elevation = 0.0f;
    float life = 0.0f;
    float maxLife = 1.0f;
    float size = 1.0f;
    Color color = WHITE;
};

enum class AuditDriver { NoBrake, Brake, Drift };

struct AuditResult3D {
    const char* name = "";
    float score = 0.0f;
    float maxSpeed = 0.0f;
    float averageSpeed = 0.0f;
    float maxOffroad = 0.0f;
    float maxDriftCharge = 0.0f;
    float minGroundClearance = std::numeric_limits<float>::max();
    float maxAirTime = 0.0f;
    int progressJumps = 0;
    int contacts = 0;
    int offroadFrames = 0;
    int boostFrames = 0;
    int driftFrames = 0;
    int landings = 0;
    int lap = 0;
};

struct RaceAuditResult3D {
    float playerScore = 0.0f;
    float topAiScore = 0.0f;
    float tailAiScore = 0.0f;
    float spread = 0.0f;
    float maxOverlap = 0.0f;
    float maxRoadViolation = 0.0f;
    float minGroundClearance = std::numeric_limits<float>::max();
    float validatedLapSeconds = 0.0f;
    float contactBeginningsPerLap = 0.0f;
    int overtakes = 0;
    int contacts = 0;
    int progressJumps = 0;
    int overlapFrames = 0;
    int roadViolationFrames = 0;
    int playerBest = kKartCount;
    int playerWorst = 1;
    int playerFinal = kKartCount;
};

struct CollisionAuditResult3D {
    const char* name = "";
    float maxOverlap = 0.0f;
    int overlapFrames = 0;
    int contactFrames = 0;
};

struct KartContact3D {
    bool touching = false;
    Vec2 normal{1.0f, 0.0f};
    float penetration = 0.0f;
};

float contactHalfLength(const Kart3D& kart) {
    return kart.spec.length * 0.59f;
}

float contactHalfWidth(const Kart3D& kart) {
    return kart.spec.width * 0.64f;
}

float roadSurfaceHalfWidth(const TrackPoint3D& point) {
    return point.width * kRoadSurfaceRatio;
}

float roadCenterLimit(const Kart3D& kart, const TrackPoint3D& point) {
    return std::max(0.0f, roadSurfaceHalfWidth(point) - contactHalfWidth(kart) - kRoadLaneInset);
}

float roadEdgeViolation(const Kart3D& kart, const TrackPoint3D& point) {
    const float lane = dot(kart.pos - point.pos, point.normal);
    return std::max(0.0f, std::abs(lane) - roadCenterLimit(kart, point));
}

float activeRendererWheelGroundClearance(const Kart3D& kart) {
    const float wheelRadius = std::max(0.50f, kart.spec.height * kRenderScale * 0.46f);
    const float travel = std::max(wheelRadius * 0.30f, 0.18f);
    const float suspension = std::clamp(kart.suspensionCompression, 0.0f, 1.0f);
    const float pitchLoad = std::clamp(kart.bodyPitch * 2.8f, -0.22f, 0.22f);
    const float rollLoad = std::clamp(kart.bodyRoll * 2.2f, -0.22f, 0.22f);
    const std::array<float, 4> compression = {
        std::clamp(0.16f + suspension + pitchLoad + rollLoad, 0.0f, 1.0f),
        std::clamp(0.16f + suspension + pitchLoad - rollLoad, 0.0f, 1.0f),
        std::clamp(0.16f + suspension - pitchLoad + rollLoad, 0.0f, 1.0f),
        std::clamp(0.16f + suspension - pitchLoad - rollLoad, 0.0f, 1.0f),
    };
    float averageBottom = 0.0f;
    for (float value : compression) {
        averageBottom += (0.48f - value) * travel;
    }
    averageBottom /= static_cast<float>(compression.size());
    // The active renderer lowers the buggy root by this average wheel-bottom
    // offset while grounded, leaving the tire contact plane on the track.
    const float rendererRootCorrection = -averageBottom;
    return rendererRootCorrection + averageBottom;
}

float kartMass(const Kart3D& kart) {
    const float footprint = kart.spec.width * kart.spec.length;
    return std::clamp(0.72f + footprint / 2100.0f + kart.spec.height / 75.0f, 1.15f, 2.15f);
}

float inverseKartMass(const Kart3D& kart) {
    return 1.0f / kartMass(kart);
}

float projectedKartExtent(const Kart3D& kart, Vec2 axis) {
    const Vec2 forward = fromAngle(kart.heading);
    const Vec2 right{-forward.y, forward.x};
    return std::abs(dot(axis, forward)) * contactHalfLength(kart) + std::abs(dot(axis, right)) * contactHalfWidth(kart);
}

KartContact3D kartContact(const Kart3D& a, const Kart3D& b) {
    const Vec2 af = fromAngle(a.heading);
    const Vec2 ar{-af.y, af.x};
    const Vec2 bf = fromAngle(b.heading);
    const Vec2 br{-bf.y, bf.x};
    const Vec2 delta = b.pos - a.pos;
    const std::array<Vec2, 4> axes = {af, ar, bf, br};

    KartContact3D contact;
    contact.touching = true;
    contact.penetration = std::numeric_limits<float>::max();

    for (Vec2 axis : axes) {
        axis = normalize(axis);
        const float projectedDistance = std::abs(dot(delta, axis));
        const float overlap = projectedKartExtent(a, axis) + projectedKartExtent(b, axis) - projectedDistance;
        if (overlap <= 0.0f) {
            return {};
        }
        if (overlap < contact.penetration) {
            contact.penetration = overlap;
            contact.normal = dot(delta, axis) < 0.0f ? axis * -1.0f : axis;
        }
    }

    if (lengthSq(delta) < 0.0001f) {
        contact.normal = af;
    }
    return contact;
}

void drawQuad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Color color) {
    DrawTriangle3D(a, b, c, color);
    DrawTriangle3D(a, c, d, color);
}

void gradientVertex(Vector3 v, Color color) {
    rlColor4ub(color.r, color.g, color.b, color.a);
    rlVertex3f(v.x, v.y, v.z);
}

void drawGradientQuad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Color ca, Color cb, Color cc, Color cd) {
    rlBegin(RL_TRIANGLES);
    gradientVertex(a, ca);
    gradientVertex(b, cb);
    gradientVertex(c, cc);
    gradientVertex(a, ca);
    gradientVertex(c, cc);
    gradientVertex(d, cd);
    rlEnd();
    rlColor4ub(255, 255, 255, 255);
}

void drawFlatOval(Vector3 pos, float radiusX, float radiusZ, float height, Color color, int segments = 48) {
    rlPushMatrix();
    rlTranslatef(pos.x, pos.y, pos.z);
    rlScalef(radiusX, 1.0f, radiusZ);
    DrawCylinder({0.0f, 0.0f, 0.0f}, 1.0f, 1.0f, height, segments, color);
    rlPopMatrix();
}

void drawGradientOval(Vector3 pos, float radiusX, float radiusZ, Color center, Color edge, int segments = 72) {
    rlBegin(RL_TRIANGLES);
    for (int i = 0; i < segments; ++i) {
        const float a0 = static_cast<float>(i) / static_cast<float>(segments) * kTwoPi;
        const float a1 = static_cast<float>(i + 1) / static_cast<float>(segments) * kTwoPi;
        gradientVertex(pos, center);
        gradientVertex({pos.x + std::cos(a0) * radiusX, pos.y, pos.z + std::sin(a0) * radiusZ}, edge);
        gradientVertex({pos.x + std::cos(a1) * radiusX, pos.y, pos.z + std::sin(a1) * radiusZ}, edge);
    }
    rlEnd();
    rlColor4ub(255, 255, 255, 255);
}

void drawLocalBox(Vector3 pos, Vector3 size, Color color) {
    DrawCubeV(pos, size, color);
}

void drawLocalEllipsoid(Vector3 pos, Vector3 radius, Color color) {
    rlPushMatrix();
    rlTranslatef(pos.x, pos.y, pos.z);
    rlScalef(radius.x, radius.y, radius.z);
    DrawSphere({0.0f, 0.0f, 0.0f}, 1.0f, color);
    rlPopMatrix();
}

void drawLocalTaperedBox(Vector3 pos, Vector3 size, float frontScale, float rearScale, Color color) {
    const float y0 = pos.y - size.y * 0.5f;
    const float y1 = pos.y + size.y * 0.5f;
    const float zf = pos.z + size.z * 0.5f;
    const float zr = pos.z - size.z * 0.5f;
    const float xf = size.x * 0.5f * frontScale;
    const float xr = size.x * 0.5f * rearScale;

    const Vector3 fbl{pos.x - xf, y0, zf};
    const Vector3 fbr{pos.x + xf, y0, zf};
    const Vector3 ftl{pos.x - xf, y1, zf};
    const Vector3 ftr{pos.x + xf, y1, zf};
    const Vector3 rbl{pos.x - xr, y0, zr};
    const Vector3 rbr{pos.x + xr, y0, zr};
    const Vector3 rtl{pos.x - xr, y1, zr};
    const Vector3 rtr{pos.x + xr, y1, zr};

    drawQuad(ftl, ftr, rtr, rtl, shade(color, 1.04f));
    drawQuad(fbl, rbl, rbr, fbr, shade(color, 0.70f));
    drawQuad(fbl, ftl, rtl, rbl, shade(color, 0.86f));
    drawQuad(fbr, rbr, rtr, ftr, shade(color, 0.78f));
    drawQuad(fbl, fbr, ftr, ftl, shade(color, 1.08f));
    drawQuad(rbl, rtl, rtr, rbr, shade(color, 0.82f));
}

void drawLocalWedge(Vector3 pos, Vector3 size, float frontTopScale, Color color) {
    const float x0 = pos.x - size.x * 0.5f;
    const float x1 = pos.x + size.x * 0.5f;
    const float y0 = pos.y - size.y * 0.5f;
    const float yRear = pos.y + size.y * 0.5f;
    const float yFront = y0 + size.y * std::clamp(frontTopScale, 0.10f, 1.0f);
    const float zf = pos.z + size.z * 0.5f;
    const float zr = pos.z - size.z * 0.5f;

    const Vector3 fbl{x0, y0, zf};
    const Vector3 fbr{x1, y0, zf};
    const Vector3 ftl{x0, yFront, zf};
    const Vector3 ftr{x1, yFront, zf};
    const Vector3 rbl{x0, y0, zr};
    const Vector3 rbr{x1, y0, zr};
    const Vector3 rtl{x0, yRear, zr};
    const Vector3 rtr{x1, yRear, zr};

    drawQuad(ftl, ftr, rtr, rtl, shade(color, 1.10f));
    drawQuad(fbl, rbl, rbr, fbr, shade(color, 0.70f));
    drawQuad(fbl, ftl, rtl, rbl, shade(color, 0.86f));
    drawQuad(fbr, rbr, rtr, ftr, shade(color, 0.78f));
    drawQuad(fbl, fbr, ftr, ftl, shade(color, 1.02f));
    drawQuad(rbl, rtl, rtr, rbr, shade(color, 0.92f));
}

void drawLocalWheel(float x, float z, float radius, float width, Color tire, Color hub, float spinDeg, float steerDeg, bool front) {
    rlPushMatrix();
    rlTranslatef(x, radius, z);
    if (front) {
        rlRotatef(steerDeg, 0.0f, 1.0f, 0.0f);
    }
    DrawCylinderEx({-width * 0.5f, 0.0f, 0.0f}, {width * 0.5f, 0.0f, 0.0f}, radius, radius, 20, tire);
    DrawCylinderEx({-width * 0.54f, 0.0f, 0.0f}, {width * 0.54f, 0.0f, 0.0f}, radius * 0.46f, radius * 0.46f, 12, hub);
    for (int i = 0; i < 8; ++i) {
        const float a = (spinDeg + static_cast<float>(i) * 45.0f) * DEG2RAD;
        const float cy = std::sin(a) * radius * 0.92f;
        const float cz = std::cos(a) * radius * 0.92f;
        rlPushMatrix();
        rlTranslatef(0.0f, cy, cz);
        rlRotatef(-spinDeg + static_cast<float>(i) * 12.0f, 1.0f, 0.0f, 0.0f);
        DrawCubeV({0.0f, 0.0f, 0.0f}, {width * 1.12f, radius * 0.11f, radius * 0.24f}, shade(tire, 1.22f));
        rlPopMatrix();
    }
    for (int i = 0; i < 5; ++i) {
        const float a = (spinDeg + static_cast<float>(i) * 72.0f) * DEG2RAD;
        DrawCylinderEx({-width * 0.58f, 0.0f, 0.0f}, {-width * 0.60f, std::sin(a) * radius * 0.38f, std::cos(a) * radius * 0.38f},
                       radius * 0.035f, radius * 0.035f, 6, shade(hub, 1.25f));
        DrawCylinderEx({width * 0.58f, 0.0f, 0.0f}, {width * 0.60f, std::sin(a) * radius * 0.38f, std::cos(a) * radius * 0.38f},
                       radius * 0.035f, radius * 0.035f, 6, shade(hub, 1.25f));
    }
    rlPopMatrix();
}

void drawSkyGradient() {
    const int w = GetScreenWidth();
    const int h = GetScreenHeight();
    constexpr int kBands = 36;
    for (int i = 0; i < kBands; ++i) {
        const float t = static_cast<float>(i) / static_cast<float>(kBands - 1);
        const int y0 = i * h / kBands;
        const int y1 = (i + 1) * h / kBands + 1;
        DrawRectangle(0, y0, w, y1 - y0, mix(Color{69, 189, 237, 255}, Color{177, 238, 244, 255}, t));
    }
}

float offroadReachForZone(int zone) {
    switch (zone) {
        case 1:
        case 5:
            return 154.0f;
        case 3:
            return 132.0f;
        case 4:
            return 224.0f;
        default:
            return 196.0f;
    }
}

float hardBoundaryLaneLimit(const Kart3D& kart, const TrackPoint3D& point) {
    const float shoulder = std::min(42.0f, offroadReachForZone(point.zone) * 0.22f);
    return roadCenterLimit(kart, point) + shoulder - kHardBoundaryInset * 0.20f;
}

Color naturalSurfaceColor(int zone) {
    return baseZoneMaterial(zone).natural;
}

Color surfaceColorAt(const TrackPoint3D& point, float lane) {
    const float half = point.width * 0.5f;
    const float roadHalf = roadSurfaceHalfWidth(point);
    const float absLane = std::abs(lane);
    const Color natural = point.natural;
    const float crown = smoothstep(absLane / std::max(roadHalf, 1.0f));
    const float shoulderT = smoothstep((absLane - roadHalf) / std::max(half - roadHalf, 1.0f));
    const float wildT = smoothstep((absLane - half) / std::max(offroadReachForZone(point.zone) * 0.94f, 1.0f));
    Color base = mix(shade(point.road, 0.92f), shade(point.road, 0.72f), crown * 0.62f);
    base = mix(base, point.shoulder, shoulderT * 0.92f);
    base = mix(base, natural, wildT * 0.96f);

    const float grain = 0.5f + 0.5f * std::sin(point.progress * 0.018f + lane * 0.047f + static_cast<float>(point.zone) * 1.7f);
    const float broad = 0.5f + 0.5f * std::sin(point.progress * 0.0041f - lane * 0.013f);
    return shade(base, 0.972f + grain * 0.026f + broad * 0.022f);
}

std::array<float, 17> surfaceCuts(const TrackPoint3D& point) {
    const float half = point.width * 0.5f;
    const float reach = offroadReachForZone(point.zone);
    return {-half - reach,
            -half - reach * 0.68f,
            -half - reach * 0.42f,
            -half - reach * 0.20f,
            -half - reach * 0.04f,
            -half * 0.82f,
            -half * 0.54f,
            -half * 0.26f,
            0.0f,
            half * 0.26f,
            half * 0.54f,
            half * 0.82f,
            half + reach * 0.04f,
            half + reach * 0.20f,
            half + reach * 0.42f,
            half + reach * 0.68f,
            half + reach};
}

class Game3D {
public:
    enum class Mode { Garage, Race, Pause };

    explicit Game3D(bool enableAudio = true) : specs_(makeKartSpecs()), racers_(makeRacers()) {
        renderer_.initialize();
        if (enableAudio) {
            audio_.initialize();
        }
        buildParticleTexture();
        buildTrackRenderer();
        resetRace();
    }

    ~Game3D() {
        shutdown();
    }

    void shutdown() {
        audio_.shutdown();
        if (IsWindowReady()) {
            trackRenderer_.unload();
            if (IsTextureValid(particleTexture_)) {
                UnloadTexture(particleTexture_);
                particleTexture_ = {};
            }
            renderer_.shutdown();
        }
    }

    void update(float dt, const Input3D& input, bool hasController) {
        if (mode_ == Mode::Garage) {
            updateGarage(input, hasController);
            updateGarageCamera(dt);
            updateAudio(dt, input, false);
            return;
        }

        if (input.start) {
            mode_ = mode_ == Mode::Race ? Mode::Pause : Mode::Race;
        }
        if (mode_ == Mode::Pause) {
            updateAudio(dt, input, false);
            if (input.b) {
                mode_ = Mode::Garage;
            }
            return;
        }

        if (raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Countdown) {
            const auto raceInputs = currentRaceInputs();
            raceFlow_->update(dt, raceInputs);
            raceTime_ = static_cast<float>(raceFlow_->raceTimeSeconds());
            if (raceFlow_->phase() == ArcadeRacePhase::Racing) {
                countdownGoTimer_ = 0.72f;
            }
            updateCamera(dt);
            updateAudio(dt, input, false);
            return;
        }
        countdownGoTimer_ = std::max(0.0f, countdownGoTimer_ - dt);
        if (input.back) {
            resetPlayerToTrack();
        }

        Input3D playerInput = raceFinished_ ? Input3D{} : input;
        updatePlayer(karts_[0], playerInput, dt);
        for (int i = 1; i < kKartCount; ++i) {
            updateAi(karts_[static_cast<size_t>(i)], dt, i);
        }
        solveKartContacts();
        updateParticles(dt);
        if (raceFlow_) {
            const auto raceInputs = currentRaceInputs();
            raceFlow_->update(dt, raceInputs);
            raceTime_ = static_cast<float>(raceFlow_->raceTimeSeconds());
            for (int i = 0; i < kKartCount; ++i) {
                karts_[static_cast<size_t>(i)].lap = static_cast<int>(raceFlow_->racer(static_cast<size_t>(i)).completedLaps);
            }
        }
        updateRaceOrder();
        updateFinishState();
        updateCamera(dt);
        updateAudio(dt, playerInput, !raceFinished_);
    }

    void render(float fps, bool hasController) {
        BeginDrawing();
        ClearBackground(Color{91, 196, 232, 255});
        drawSkyGradient();
        arcade_render::DirectionalLightFog lighting;
        lighting.cameraPosition = camera_.position;
        lighting.fogStart = 74.0f;
        lighting.fogEnd = 235.0f;
        lighting.exposure = 0.80f;
        renderer_.setLighting(lighting);
        BeginMode3D(camera_);
        rlDisableBackfaceCulling();
        drawEnvironment();
        rlEnableBackfaceCulling();
        drawTrack();
        drawProps();
        drawParticles();
        drawKarts();
        EndMode3D();
        drawSpeedFx();
        drawHud(fps, hasController);
        EndDrawing();
    }

    void startRace() {
        resetRace();
        mode_ = Mode::Race;
    }

    void setupSectionTour(float phase, int variant) {
        resetRace();
        mode_ = Mode::Race;
        particles_.clear();
        raceTime_ = phase * 18.0f;

        const float baseProgress = wrapDistance(track_.totalLength() * phase, track_.totalLength());
        static constexpr std::array<float, kKartCount> kProgressOffset = {0.0f, 78.0f, 156.0f, -82.0f, -112.0f, 244.0f};
        static constexpr std::array<float, kKartCount> kLaneOffset = {0.0f, -22.0f, 26.0f, -30.0f, 28.0f, 10.0f};

        for (int i = 0; i < kKartCount; ++i) {
            Kart3D& kart = karts_[static_cast<size_t>(i)];
            const float progress = wrapDistance(baseProgress + kProgressOffset[static_cast<size_t>(i)] +
                                                    static_cast<float>((variant * (i + 3)) % 17) * 2.0f,
                                                track_.totalLength());
            const TrackPoint3D point = track_.sample(progress);
            const float lane = std::clamp(kLaneOffset[static_cast<size_t>(i)], -roadCenterLimit(kart, point), roadCenterLimit(kart, point));
            kart.pos = point.pos + point.normal * lane;
            kart.heading = angleOf(point.tangent) + static_cast<float>((i % 3) - 1) * 0.018f;
            kart.vel = point.tangent * (i == 0 ? 104.0f : 82.0f + static_cast<float>((i * 7) % 20));
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.progress = track_.pointAtIndex(kart.nearest).progress;
            kart.previousProgress = kart.progress;
            kart.lap = 0;
            kart.lane = lane;
            kart.ghostTimer = 1.0f;
            kart.contactTimer = 0.0f;
            kart.drifting = false;
            kart.boostTimer = i == 0 && variant % 3 == 1 ? 0.35f : 0.0f;
            kart.driftCharge = 0.0f;
            kart.steerSmoothed = (variant % 2 == 0 ? -0.18f : 0.18f) * std::clamp(point.curvature * 7.0f, 0.0f, 1.0f);
        }

        if (raceFlow_) {
            const auto inputs = currentRaceInputs();
            for (int i = 0; i < kKartCount; ++i) {
                raceFlow_->rebaseRacerSample(static_cast<size_t>(i), inputs[static_cast<size_t>(i)]);
            }
            raceFlow_->beginRace();
        }
        updateRaceOrder();
        const Kart3D& player = karts_[0];
        const TrackPoint3D ground = track_.sample(player.progress);
        const TrackPoint3D future = track_.sample(player.progress + 150.0f);
        const Vec2 view = normalize(lerp(fromAngle(player.heading), future.tangent, 0.35f));
        const Vec2 side = ground.normal * (variant % 2 == 0 ? 24.0f : -16.0f);
        const float groundY = bankedElevation(ground, player.lane);
        camera_.position = toWorld(player.pos - view * 190.0f + side, groundY + 82.0f);
        camera_.target = toWorld(player.pos + view * 122.0f + ground.normal * 6.0f, groundY + 13.0f);
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = 60.0f;
        camera_.projection = CAMERA_PERSPECTIVE;
    }

    Input3D scriptedInput() const {
        return auditInput(AuditDriver::Drift, karts_[0]);
    }

    Mode mode() const { return mode_; }

    bool runHandlingAudit() {
        const AuditResult3D noBrake = simulateAuditDriver(AuditDriver::NoBrake, 64.0f);
        const AuditResult3D brake = simulateAuditDriver(AuditDriver::Brake, 64.0f);
        const AuditResult3D drift = simulateAuditDriver(AuditDriver::Drift, 64.0f);
        const bool controlledRoad = brake.offroadFrames <= noBrake.offroadFrames && brake.maxOffroad <= 40.0f;
        const bool noBrakeConsequences = noBrake.offroadFrames > 120 || noBrake.maxOffroad > 18.0f ||
                                         noBrake.averageSpeed > brake.averageSpeed * 1.10f;
        const bool groundClear = std::abs(noBrake.minGroundClearance) <= 0.03f && std::abs(brake.minGroundClearance) <= 0.03f &&
                                 std::abs(drift.minGroundClearance) <= 0.03f;
        const bool stable = noBrake.progressJumps == 0 && brake.progressJumps == 0 && drift.progressJumps == 0;
        const bool moving = std::max({noBrake.score, brake.score, drift.score}) > track_.totalLength() * 0.50f;
        const float measuredLapSeconds = brake.score > 1.0f ? 64.0f * track_.totalLength() / brake.score : 999.0f;
        const bool referencePace = measuredLapSeconds >= 30.0f && measuredLapSeconds <= 38.0f;
        const bool authoredJumps = drift.maxAirTime >= 0.80f && drift.maxAirTime <= 1.30f && drift.landings >= 2;
        const bool inputContract = controllerContractAudit();
        const bool ok = controlledRoad && noBrakeConsequences && groundClear && stable && moving && authoredJumps && inputContract;

        auto print = [](const AuditResult3D& r) {
            std::cout << r.name << "_score=" << r.score << " lap=" << r.lap << " avg=" << r.averageSpeed << " max=" << r.maxSpeed
                      << " contacts=" << r.contacts << " offroad_frames=" << r.offroadFrames << " max_offroad=" << r.maxOffroad
                      << " max_drift_charge=" << r.maxDriftCharge
                      << " min_ground_clearance=" << r.minGroundClearance << " progress_jumps=" << r.progressJumps
                      << " max_airtime=" << r.maxAirTime << " landings=" << r.landings
                      << " drift_frames=" << r.driftFrames << " boost_frames=" << r.boostFrames << " ";
        };
        std::cout << "handling-audit ";
        print(noBrake);
        print(brake);
        print(drift);
        std::cout << "controlled_road=" << controlledRoad << " no_brake_consequences=" << noBrakeConsequences
                  << " ground_clear=" << groundClear << " stable=" << stable << " moving=" << moving << " reference_pace=" << referencePace
                  << " measured_lap_s=" << measuredLapSeconds
                  << " authored_jumps=" << authoredJumps
                  << " input_contract=" << inputContract
                  << "\n";
        return ok;
    }

    bool runRaceAudit() {
        startRace();
        RaceAuditResult3D result;
        std::array<float, kKartCount> previousScores{};
        std::array<float, kKartCount> maxRoadViolationByKart{};
        std::array<int, kKartCount> roadViolationFramesByKart{};
        double lapStartProgress = 0.0;
        bool lapClockStarted = false;
        for (int i = 0; i < kKartCount; ++i) {
            previousScores[static_cast<size_t>(i)] = raceScore(karts_[static_cast<size_t>(i)]);
        }

        constexpr int frames = static_cast<int>(80.0f / kFixedDt);
        for (int frame = 0; frame < frames; ++frame) {
            std::array<float, kKartCount> beforeContact{};
            std::array<float, kKartCount> beforeProgress{};
            for (int i = 0; i < kKartCount; ++i) {
                beforeContact[static_cast<size_t>(i)] = karts_[static_cast<size_t>(i)].contactTimer;
                beforeProgress[static_cast<size_t>(i)] = karts_[static_cast<size_t>(i)].progress;
            }

            update(kFixedDt, scriptedInput(), true);
            if (raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Racing) {
                const double progress = raceFlow_->racer(0).continuousTrackProgress;
                if (!lapClockStarted) {
                    lapClockStarted = true;
                    lapStartProgress = progress;
                } else if (result.validatedLapSeconds <= 0.0f && progress - lapStartProgress >= 1.0) {
                    result.validatedLapSeconds = static_cast<float>(raceFlow_->raceTimeSeconds());
                }
            }

            std::array<std::pair<float, int>, kKartCount> order{};
            for (int i = 0; i < kKartCount; ++i) {
                const Kart3D& kart = karts_[static_cast<size_t>(i)];
                const float progressDelta = signedDistanceToLoop(beforeProgress[static_cast<size_t>(i)], kart.progress, track_.totalLength());
                if (progressDelta < -40.0f || progressDelta > 90.0f) {
                    ++result.progressJumps;
                }
                if (i == 0 && beforeContact[0] <= 0.001f && kart.contactTimer > 0.05f) {
                    ++result.contacts;
                }
                const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
                const float roadViolation = roadEdgeViolation(kart, center);
                result.maxRoadViolation = std::max(result.maxRoadViolation, roadViolation);
                maxRoadViolationByKart[static_cast<size_t>(i)] = std::max(maxRoadViolationByKart[static_cast<size_t>(i)], roadViolation);
                if (roadViolation > 0.01f) {
                    ++result.roadViolationFrames;
                    ++roadViolationFramesByKart[static_cast<size_t>(i)];
                }
                result.minGroundClearance = std::min(result.minGroundClearance, activeRendererWheelGroundClearance(kart));
                const float score = raceScore(kart);
                order[static_cast<size_t>(i)] = {score, i};
            }

            for (int a = 0; a < kKartCount; ++a) {
                for (int b = a + 1; b < kKartCount; ++b) {
                    const float before = previousScores[static_cast<size_t>(a)] - previousScores[static_cast<size_t>(b)];
                    const float after = orderScore(order, a) - orderScore(order, b);
                    if (std::abs(before) > 6.0f && std::abs(after) > 6.0f && before * after < 0.0f) {
                        ++result.overtakes;
                    }
                }
            }

            for (int i = 0; i < kKartCount; ++i) {
                previousScores[static_cast<size_t>(i)] = orderScore(order, i);
            }
            const float overlap = maxKartOverlap();
            result.maxOverlap = std::max(result.maxOverlap, overlap);
            if (overlap > 1.25f) {
                ++result.overlapFrames;
            }
            result.playerBest = std::min(result.playerBest, playerPosition_);
            result.playerWorst = std::max(result.playerWorst, playerPosition_);
        }

        std::array<float, kKartCount> finalScores{};
        for (int i = 0; i < kKartCount; ++i) {
            finalScores[static_cast<size_t>(i)] = raceScore(karts_[static_cast<size_t>(i)]);
        }
        result.playerScore = finalScores[0];
        result.topAiScore = finalScores[1];
        result.tailAiScore = finalScores[1];
        for (int i = 1; i < kKartCount; ++i) {
            result.topAiScore = std::max(result.topAiScore, finalScores[static_cast<size_t>(i)]);
            result.tailAiScore = std::min(result.tailAiScore, finalScores[static_cast<size_t>(i)]);
        }
        result.spread = std::max(result.topAiScore, result.playerScore) - std::min(result.tailAiScore, result.playerScore);
        result.playerFinal = playerPosition_;
        if (lapClockStarted && raceFlow_) {
            const double lapsDriven = std::max(1.0, raceFlow_->racer(0).continuousTrackProgress - lapStartProgress);
            result.contactBeginningsPerLap = static_cast<float>(static_cast<double>(result.contacts) / lapsDriven);
        }

        const bool stable = result.progressJumps == 0;
        const bool pressure = result.topAiScore > result.playerScore - 950.0f && result.playerScore > result.tailAiScore - 700.0f;
        const bool activePack = result.spread < 3000.0f && result.playerBest < result.playerWorst;
        const bool tailRecovered = result.tailAiScore > result.playerScore - 3300.0f && result.spread < 3400.0f;
        const bool cleanEnough = result.contactBeginningsPerLap <= 20.0f;
        const bool separated = result.maxOverlap < 2.0f && result.overlapFrames < 4;
        const bool shoulderControlled = result.maxRoadViolation <= 42.0f && result.roadViolationFrames < 9000;
        const bool groundClear = std::abs(result.minGroundClearance) <= 0.03f;
        const bool referenceLap = result.validatedLapSeconds >= 48.0f && result.validatedLapSeconds <= 56.0f;
        const bool ok = shoulderControlled && groundClear && stable && pressure && activePack && tailRecovered && cleanEnough && separated && referenceLap;

        std::cout << "race-audit-3d player=" << result.playerScore << " top_ai=" << result.topAiScore << " tail_ai=" << result.tailAiScore
                  << " spread=" << result.spread << " overtakes=" << result.overtakes << " contacts=" << result.contacts
                  << " progress_jumps=" << result.progressJumps << " player_pos=" << result.playerFinal << " best=" << result.playerBest
                  << " worst=" << result.playerWorst << " stable=" << stable << " pressure=" << pressure << " active_pack=" << activePack
                  << " tail_recovered=" << tailRecovered << " clean=" << cleanEnough << " separated=" << separated
                  << " shoulder_controlled=" << shoulderControlled << " ground_clear=" << groundClear
                  << " validated_lap_s=" << result.validatedLapSeconds << " reference_lap=" << referenceLap
                  << " contacts_per_lap=" << result.contactBeginningsPerLap
                  << " max_road_violation=" << result.maxRoadViolation
                  << " road_violation_frames=" << result.roadViolationFrames << " min_ground_clearance=" << result.minGroundClearance
                  << " max_overlap=" << result.maxOverlap << " overlap_frames=" << result.overlapFrames << " scores=";
        for (int i = 0; i < kKartCount; ++i) {
            const Kart3D& kart = karts_[static_cast<size_t>(i)];
            std::cout << (i == 0 ? "" : ",") << i << ":" << finalScores[static_cast<size_t>(i)] << "/" << kart.lap << "/"
                      << static_cast<int>(kart.progress);
        }
        std::cout << " road_by_kart=";
        for (int i = 0; i < kKartCount; ++i) {
            std::cout << (i == 0 ? "" : ",") << i << ":" << maxRoadViolationByKart[static_cast<size_t>(i)] << "/"
                      << roadViolationFramesByKart[static_cast<size_t>(i)];
        }
        std::cout << "\n";
        return ok;
    }

    bool runCollisionAudit() {
        const CollisionAuditResult3D rearEnd = simulateCollisionScenario("rear_end", 0);
        const CollisionAuditResult3D headOn = simulateCollisionScenario("head_on", 1);
        const CollisionAuditResult3D sideSwipe = simulateCollisionScenario("side_swipe", 2);
        const bool rearOk = rearEnd.contactFrames > 0 && rearEnd.maxOverlap < 1.25f && rearEnd.overlapFrames == 0;
        const bool headOk = headOn.contactFrames > 0 && headOn.maxOverlap < 1.25f && headOn.overlapFrames == 0;
        const bool sideOk = sideSwipe.contactFrames > 0 && sideSwipe.maxOverlap < 1.25f && sideSwipe.overlapFrames == 0;
        Kart3D light;
        Kart3D heavy;
        light.spec = specs_[1];
        heavy.spec = specs_[4];
        const float invLight = inverseKartMass(light);
        const float invHeavy = inverseKartMass(heavy);
        const float lightResponseFirst = invLight / (invLight + invHeavy);
        const float lightResponseSecond = invLight / (invHeavy + invLight);
        const bool massDistinct = kartMass(heavy) > kartMass(light) * 1.08f;
        const bool roleSymmetric = std::abs(lightResponseFirst - lightResponseSecond) < 0.000001f;
        light.progress = 400.0f;
        heavy.progress = 400.0f;
        light.elevation = 0.0f;
        heavy.elevation = kContactVerticalWindow + 0.5f;
        light.ghostTimer = 0.0f;
        heavy.ghostTimer = 0.0f;
        const bool jumpClears = !shouldTestKartContact(light, heavy);
        const bool ok = rearOk && headOk && sideOk && massDistinct && roleSymmetric && jumpClears;

        auto print = [](const CollisionAuditResult3D& r) {
            std::cout << r.name << "_max_overlap=" << r.maxOverlap << " " << r.name << "_overlap_frames=" << r.overlapFrames << " "
                      << r.name << "_contact_frames=" << r.contactFrames << " ";
        };
        std::cout << "collision-audit-3d ";
        print(rearEnd);
        print(headOn);
        print(sideSwipe);
        std::cout << "rear_ok=" << rearOk << " head_ok=" << headOk << " side_ok=" << sideOk << " mass_distinct=" << massDistinct
                  << " role_symmetric=" << roleSymmetric << " jump_clears=" << jumpClears << "\n";
        return ok;
    }

    float playerRaceScoreForCapture() const {
        return raceFlow_ ? static_cast<float>(raceFlow_->racer(0).continuousTrackProgress * static_cast<double>(track_.totalLength()))
                         : raceScore(karts_[0]);
    }

    float lapLengthForCapture() const { return track_.totalLength(); }

private:
    void updateAudio(float dt, const Input3D& input, bool driving) {
        ArcadeAudioInput audioInput;
        audioInput.deltaTime = dt;
        if (driving && !karts_.empty()) {
            const Kart3D& player = karts_[0];
            audioInput.speedNormalized = std::clamp(player.telemetry.normalizedSpeed, 0.0f, 1.0f);
            audioInput.throttle = input.throttle;
            audioInput.brake = std::max(input.brake, player.brakeLoad);
            audioInput.slip = std::clamp(std::abs(player.slipAngle) / 0.70f, 0.0f, 1.0f);
            audioInput.grounded = player.grounded;
            audioInput.landingImpulse = player.landingImpulse;
        }
        audio_.update(audioInput);
    }

    void buildParticleTexture() {
        constexpr int size = 64;
        Image image = GenImageColor(size, size, BLANK);
        for (int y = 0; y < size; ++y) {
            for (int x = 0; x < size; ++x) {
                const float dx = (static_cast<float>(x) + 0.5f) / size * 2.0f - 1.0f;
                const float dy = (static_cast<float>(y) + 0.5f) / size * 2.0f - 1.0f;
                const float radius = std::sqrt(dx * dx + dy * dy);
                const float alpha = std::pow(std::clamp(1.0f - radius, 0.0f, 1.0f), 1.65f);
                ImageDrawPixel(&image, x, y, {255, 255, 255, static_cast<unsigned char>(alpha * 235.0f)});
            }
        }
        particleTexture_ = LoadTextureFromImage(image);
        UnloadImage(image);
        SetTextureFilter(particleTexture_, TEXTURE_FILTER_BILINEAR);
    }

    std::array<ArcadeRacerInput, kKartCount> currentRaceInputs() const {
        std::array<ArcadeRacerInput, kKartCount> inputs{};
        for (int i = 0; i < kKartCount; ++i) {
            const Kart3D& kart = karts_[static_cast<size_t>(i)];
            const TrackPoint3D trackPoint = track_.sample(kart.progress);
            inputs[static_cast<size_t>(i)].normalizedTrackProgress = raceLapProgress(kart) / track_.totalLength();
            inputs[static_cast<size_t>(i)].forwardAlignment = dot(fromAngle(kart.heading), trackPoint.tangent);
        }
        return inputs;
    }

    void buildTrackRenderer() {
        std::vector<harbor::TrackRenderSample> samples;
        samples.reserve(track_.samples().size());
        for (const TrackPoint3D& point : track_.samples()) {
            const Vector3 center = lift(track_.roadPoint(point, 0.0f), kTrackSurfaceLift);
            const Vector3 lanePoint = lift(track_.roadPoint(point, 1.0f), kTrackSurfaceLift);
            Vector3 lateral = sub(lanePoint, center);
            const float magnitude = std::sqrt(lateral.x * lateral.x + lateral.y * lateral.y + lateral.z * lateral.z);
            lateral = magnitude > 0.0001f ? mul(lateral, 1.0f / magnitude) : Vector3{1.0f, 0.0f, 0.0f};
            samples.push_back({center, lateral, point.width * 0.5f * kRenderScale, point.progress * kRenderScale, point.road,
                               point.shoulder, point.natural, point.zone});
        }
        trackRenderer_.build(samples, {});
    }

    void updateGarage(const Input3D& input, bool hasController) {
        garageSpin_ += GetFrameTime();
        if (input.left) {
            selectedCar_ = (selectedCar_ + static_cast<int>(specs_.size()) - 1) % static_cast<int>(specs_.size());
        }
        if (input.right) {
            selectedCar_ = (selectedCar_ + 1) % static_cast<int>(specs_.size());
        }
        if (input.up) {
            selectedRacer_ = (selectedRacer_ + static_cast<int>(racers_.size()) - 1) % static_cast<int>(racers_.size());
        }
        if (input.down) {
            selectedRacer_ = (selectedRacer_ + 1) % static_cast<int>(racers_.size());
        }
        if (input.pageLeft) {
            selectedLapOption_ = (selectedLapOption_ + static_cast<int>(kLapOptions.size()) - 1) % static_cast<int>(kLapOptions.size());
        }
        if (input.pageRight) {
            selectedLapOption_ = (selectedLapOption_ + 1) % static_cast<int>(kLapOptions.size());
        }
        if ((input.a || input.start) && hasController) {
            startRace();
        }
    }

    void updateGarageCamera(float dt) {
        (void)dt;
        const TrackPoint3D start = track_.sample(kRaceStartProgress);
        const float focusLane = 10.0f;
        const float cameraLane = 148.0f;
        const Vector3 focus = toWorld(start.pos + start.tangent * 32.0f + start.normal * focusLane, bankedElevation(start, focusLane) + 11.0f);
        camera_.position =
            toWorld(start.pos + start.tangent * 132.0f + start.normal * cameraLane, bankedElevation(start, cameraLane) + 50.0f);
        camera_.target = focus;
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = 48.0f;
        camera_.projection = CAMERA_PERSPECTIVE;
    }

    void resetRace() {
        karts_.clear();
        const TrackPoint3D start = track_.sample(kRaceStartProgress);
        for (int i = 0; i < kKartCount; ++i) {
            Kart3D kart;
            kart.spec = specs_[static_cast<size_t>(i == 0 ? selectedCar_ : i % static_cast<int>(specs_.size()))];
            kart.tuning = tuningForSpec(kart.spec);
            kart.racer = racers_[static_cast<size_t>(i == 0 ? selectedRacer_ : (i * 3) % static_cast<int>(racers_.size()))];
            static constexpr std::array<float, kKartCount> kGridProgress = {-420.0f, -84.0f, -126.0f, -246.0f, -288.0f, -374.0f};
            static constexpr std::array<float, kKartCount> kGridLane = {34.0f, -34.0f, 34.0f, -34.0f, 34.0f, -34.0f};
            const float stagger = kRaceStartProgress + kGridProgress[static_cast<size_t>(i)];
            const TrackPoint3D grid = track_.sample(stagger);
            const float lane = std::clamp(kGridLane[static_cast<size_t>(i)], -roadCenterLimit(kart, grid), roadCenterLimit(kart, grid));
            kart.pos = grid.pos + grid.normal * lane;
            kart.heading = angleOf(grid.tangent);
            kart.vel = {};
            kart.elevation = bankedElevation(grid, lane);
            kart.verticalSpeed = 0.0f;
            kart.grounded = true;
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.progress = track_.pointAtIndex(kart.nearest).progress;
            kart.previousProgress = kart.progress;
            kart.lap = -1;
            kart.lane = lane;
            kart.aiTempo = 0.650f - static_cast<float>(i) * 0.012f;
            kart.aiRisk = 0.25f + static_cast<float>((i * 7) % 9) * 0.055f;
            kart.aiPass = (i % 2 == 0) ? -1.0f : 1.0f;
            kart.ghostTimer = 1.0f;
            karts_.push_back(kart);
        }
        particles_.clear();
        raceTime_ = 0.0f;
        finishTime_ = 0.0f;
        countdownGoTimer_ = 0.0f;
        raceFinished_ = false;
        playerPosition_ = 1;
        ArcadeRaceConfig raceConfig;
        raceConfig.lapCount = static_cast<uint32_t>(std::max(1, targetLaps()));
        raceConfig.infiniteLaps = targetLaps() == kInfiniteLaps;
        raceConfig.countdownSeconds = 3.0f;
        raceConfig.checkpointGates = {{0.0f, 0.0f}, {0.18f, 0.18f}, {0.38f, 0.38f},
                                      {0.58f, 0.58f}, {0.78f, 0.78f}};
        raceFlow_ = std::make_unique<ArcadeRaceFlow>(raceConfig, kKartCount);
        const auto inputs = currentRaceInputs();
        raceFlow_->update(0.0f, inputs);
        raceFlow_->beginCountdown();
        updateRaceOrder();
        const Vector3 focus = track_.roadPoint(start, 0.0f);
        camera_.position = add(focus, {0.0f, 5.0f, -16.0f});
        camera_.target = focus;
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = 60.0f;
        camera_.projection = CAMERA_PERSPECTIVE;
        cameraElevation_ = start.elevation;
    }

    void updateProgress(Kart3D& kart) {
        const float oldRaceProgress = progressAhead(kRaceStartProgress, kart.progress, track_.totalLength());
        kart.nearest = track_.nearestIndexNear(kart.pos, kart.nearest, 4);
        const TrackPoint3D& center = track_.pointAtIndex(kart.nearest);
        kart.previousProgress = kart.progress;
        kart.progress = center.progress;
        kart.lane = dot(kart.pos - center.pos, center.normal);
        const float newRaceProgress = progressAhead(kRaceStartProgress, kart.progress, track_.totalLength());
        if (oldRaceProgress > track_.totalLength() * 0.70f && newRaceProgress < track_.totalLength() * 0.30f) {
            ++kart.lap;
        } else if (oldRaceProgress < track_.totalLength() * 0.30f && newRaceProgress > track_.totalLength() * 0.70f &&
                   kart.lap > -1) {
            --kart.lap;
        }
    }

    void updatePlayer(Kart3D& kart, const Input3D& input, float dt) {
        integrateKart(kart, canonicalPlayerInput(input), dt, true);
    }

    float raceLapProgress(const Kart3D& kart) const { return progressAhead(kRaceStartProgress, kart.progress, track_.totalLength()); }

    float raceScore(const Kart3D& kart) const { return static_cast<float>(kart.lap) * track_.totalLength() + raceLapProgress(kart); }

    int targetLaps() const { return kLapOptions[static_cast<size_t>(selectedLapOption_)]; }

    const char* lapOptionText(int index) const {
        const int laps = kLapOptions[static_cast<size_t>(index)];
        switch (laps) {
            case 2:
                return "2";
            case 5:
                return "5";
            case 10:
                return "10";
            default:
                return "INF";
        }
    }

    void updateFinishState() {
        const int laps = targetLaps();
        const bool validatedFinish = raceFlow_ && raceFlow_->racer(0).finished;
        const bool legacyFinish = !raceFlow_ && laps != kInfiniteLaps && karts_[0].lap >= laps;
        if (!raceFinished_ && (validatedFinish || legacyFinish)) {
            raceFinished_ = true;
            finishTime_ = validatedFinish ? static_cast<float>(raceFlow_->racer(0).finishTimeSeconds) : raceTime_;
            karts_[0].vel *= 0.35f;
            karts_[0].boostTimer = 0.0f;
            karts_[0].drifting = false;
        }
    }

    static float orderScore(const std::array<std::pair<float, int>, kKartCount>& order, int kartIndex) {
        for (const auto& entry : order) {
            if (entry.second == kartIndex) {
                return entry.first;
            }
        }
        return 0.0f;
    }

    void updateAi(Kart3D& kart, float dt, int index) {
        TrackPoint3D center = track_.sample(kart.progress);
        float speed = length(kart.vel);
        float leaderScore = raceScore(karts_[0]);
        for (const Kart3D& other : karts_) {
            leaderScore = std::max(leaderScore, raceScore(other));
        }
        const float selfScore = raceScore(kart);
        const float leaderGap = leaderScore - selfScore;

        const float lookahead = 78.0f + speed * (0.70f + kart.aiRisk * 0.18f);
        const TrackPoint3D future = track_.sample(kart.progress + lookahead);
        const TrackPoint3D apex = track_.sample(kart.progress + 135.0f + speed * 0.52f);

        kart.aiIntentTimer -= dt;
        if (kart.aiIntentTimer <= 0.0f) {
            kart.aiIntentTimer = 1.15f + 0.17f * static_cast<float>((index * 5) % 6);
            kart.aiLaneIntent = kart.aiPass * (18.0f + 13.0f * std::sin(raceTime_ * 0.7f + static_cast<float>(index)));
            kart.aiPass *= -1.0f;
        }

        float laneTarget = kart.aiLaneIntent - std::copysign(18.0f, apex.signedCurvature) * std::clamp(apex.curvature * 4.0f, 0.0f, 1.0f);
        for (int i = 0; i < kKartCount; ++i) {
            if (i == index) {
                continue;
            }
            const Kart3D& other = karts_[static_cast<size_t>(i)];
            const float ahead = progressAhead(kart.progress, other.progress, track_.totalLength());
            if (ahead > 5.0f && ahead < 225.0f && std::abs(other.lane - laneTarget) < 42.0f) {
                const float passRoom = std::clamp((225.0f - ahead) / 180.0f, 0.0f, 1.0f);
                laneTarget += kart.aiPass * (24.0f + passRoom * 32.0f);
            }
        }
        const float half = roadCenterLimit(kart, future);
        laneTarget = std::clamp(laneTarget, -half, half);
        const float currentRoadLimit = roadCenterLimit(kart, center);
        const float laneExcess = std::max(0.0f, std::abs(kart.lane) - currentRoadLimit);
        const float recovery = std::clamp(laneExcess / 42.0f, 0.0f, 1.0f);
        if (laneExcess > 1.0f) {
            laneTarget = 0.0f;
        }

        const Vec2 targetPos = future.pos + future.normal * laneTarget;
        const Vec2 forward = fromAngle(kart.heading);
        const Vec2 toTarget = normalize(targetPos - kart.pos);
        const float angleError = std::atan2(cross(forward, toTarget), dot(forward, toTarget));
        const float futureCorner = std::max(center.curvature, std::max(future.curvature, apex.curvature));
        const float catchup = std::clamp((leaderGap - 650.0f) / 2600.0f, 0.0f, 0.07f);
        const float pacePulse = 1.0f + 0.026f * std::sin(raceTime_ * (0.23f + kart.aiRisk * 0.05f) + static_cast<float>(index) * 1.73f);
        const float targetSpeed =
            kart.tuning.maxForwardSpeed * (kart.aiTempo + catchup) * pacePulse * std::clamp(1.03f - futureCorner * 1.90f, 0.70f, 1.03f) *
            (1.0f - recovery * 0.38f);

        Input3D ai;
        ai.steer = std::clamp(angleError * (1.92f + kart.aiRisk * 0.36f), -1.0f, 1.0f);
        ai.throttle = speed < targetSpeed + 5.0f ? 1.0f : 0.0f;
        ai.brake = speed > targetSpeed + 10.0f ? std::clamp((speed - targetSpeed) / 38.0f, 0.24f, 0.78f) : 0.0f;
        ai.drift = futureCorner > 0.055f && speed > 46.0f && speed < targetSpeed + 24.0f && std::abs(angleError) > 0.050f;
        if (ai.drift) {
            ai.throttle = speed < targetSpeed + 12.0f ? 1.0f : 0.45f;
            ai.brake = speed > targetSpeed + 18.0f ? 0.22f : 0.0f;
        }
        if (laneExcess > 1.0f) {
            ai.throttle = std::min(ai.throttle, 0.58f);
            ai.brake = std::max(ai.brake, std::clamp(laneExcess / 42.0f, 0.16f, 0.62f));
            ai.drift = false;
        }
        integrateKart(kart, ai, dt, false);
    }

    Input3D auditInput(AuditDriver driver, const Kart3D& kart) const {
        const float speed = length(kart.vel);
        const TrackPoint3D future = track_.sample(kart.progress + 95.0f + speed * 0.88f);
        const TrackPoint3D apex = track_.sample(kart.progress + 155.0f + speed * 0.58f);
        const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
        const float corner = std::max(future.curvature, apex.curvature);
        const float turnSign = apex.signedCurvature == 0.0f ? future.signedCurvature : apex.signedCurvature;
        const float laneExcess = std::max(0.0f, std::abs(kart.lane) - roadCenterLimit(kart, center));
        float laneTarget = 0.0f;
        if (driver == AuditDriver::Drift && laneExcess <= 1.0f) {
            laneTarget = -std::copysign(6.0f, turnSign) * std::clamp(corner * 2.6f, 0.0f, 1.0f);
        }

        Input3D input;
        input.steer = aiSteerForProgress(kart, 0, laneTarget);
        input.throttle = 1.0f;

        const float targetSpeed = kart.tuning.maxForwardSpeed *
                                  std::clamp((driver == AuditDriver::Drift ? 1.06f : 1.04f) - corner * 3.15f, 0.56f, 1.05f);
        if (driver == AuditDriver::Brake || driver == AuditDriver::Drift) {
            const bool needsBrake = speed > targetSpeed + (driver == AuditDriver::Drift ? 12.0f : 7.0f);
            if (needsBrake) {
                input.brake = std::clamp((speed - targetSpeed) / 42.0f, driver == AuditDriver::Drift ? 0.14f : 0.22f, 0.78f);
                input.throttle = driver == AuditDriver::Drift ? 0.86f : 0.68f;
            }
        }
        if (driver != AuditDriver::NoBrake && laneExcess > 1.0f) {
            input.steer = aiSteerForProgress(kart, 0, 0.0f);
            input.throttle = std::min(input.throttle, 0.62f);
            input.brake = std::max(input.brake, std::clamp(laneExcess / 38.0f, 0.20f, 0.70f));
            input.drift = false;
        }
        if (driver == AuditDriver::Drift && laneExcess <= 1.0f) {
            const bool nearEdge = std::abs(kart.lane) > std::max(0.0f, roadCenterLimit(kart, center) - 4.0f);
            const bool entryDemand = kart.boostTimer <= 0.04f && !nearEdge && corner > 0.042f && speed > 44.0f && std::abs(input.steer) > 0.070f;
            input.drift = false;
            if (entryDemand && kart.brakeLoad < 0.72f) {
                input.throttle = 1.0f;
                input.brake = 1.0f;
            }
        }
        return input;
    }

    AuditResult3D simulateAuditDriver(AuditDriver driver, float seconds) {
        particles_.clear();
        const TrackPoint3D start = track_.sample(0.0f);
        Kart3D kart;
        kart.spec = specs_[0];
        kart.tuning = tuningForSpec(kart.spec);
        kart.racer = racers_[0];
        kart.pos = start.pos;
        kart.heading = angleOf(start.tangent);
        kart.vel = {};
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.progress = track_.pointAtIndex(kart.nearest).progress;
        kart.previousProgress = kart.progress;

        AuditResult3D result;
        result.name = driver == AuditDriver::NoBrake ? "no_brake" : (driver == AuditDriver::Brake ? "brake" : "attack");

        const int frames = static_cast<int>(seconds / kFixedDt);
        float speedSum = 0.0f;
        float cumulativeProgress = 0.0f;
        for (int frame = 0; frame < frames; ++frame) {
            const float beforeContact = kart.contactTimer;
            const float beforeProgress = kart.progress;
            const bool wasGrounded = kart.grounded;
            const Input3D input = auditInput(driver, kart);
            updatePlayer(kart, input, kFixedDt);
            const float progressDelta = signedDistanceToLoop(beforeProgress, kart.progress, track_.totalLength());
            if (progressDelta < -40.0f || progressDelta > 90.0f) {
                ++result.progressJumps;
            } else {
                cumulativeProgress += progressDelta;
            }
            const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
            const float offroad = roadEdgeViolation(kart, center);
            const float speed = std::max(0.0f, dot(kart.vel, fromAngle(kart.heading)));
            speedSum += speed;
            result.maxSpeed = std::max(result.maxSpeed, speed);
            result.maxOffroad = std::max(result.maxOffroad, offroad);
            result.maxDriftCharge = std::max(result.maxDriftCharge, kart.driftCharge);
            result.maxAirTime = std::max(result.maxAirTime, kart.airborneTime);
            result.landings += !wasGrounded && kart.grounded ? 1 : 0;
            result.minGroundClearance = std::min(result.minGroundClearance, activeRendererWheelGroundClearance(kart));
            result.offroadFrames += offroad > 1.0f ? 1 : 0;
            result.driftFrames += kart.drifting ? 1 : 0;
            result.boostFrames += kart.boostTimer > 0.0f ? 1 : 0;
            if (beforeContact <= 0.001f && kart.contactTimer > 0.05f) {
                ++result.contacts;
            }
        }
        result.score = cumulativeProgress;
        result.averageSpeed = speedSum / static_cast<float>(frames);
        result.lap = kart.lap;
        particles_.clear();
        return result;
    }

    float aiSteerForProgress(const Kart3D& kart, int index, float laneTarget) const {
        (void)index;
        const TrackPoint3D future = track_.sample(kart.progress + 128.0f + length(kart.vel) * 0.65f);
        laneTarget -= std::copysign(13.0f, future.signedCurvature) * std::clamp(future.curvature * 4.0f, 0.0f, 1.0f);
        const Vec2 desired = future.pos + future.normal * laneTarget;
        const Vec2 forward = fromAngle(kart.heading);
        const Vec2 toTarget = normalize(desired - kart.pos);
        return std::clamp(std::atan2(cross(forward, toTarget), dot(forward, toTarget)) * 1.95f, -1.0f, 1.0f);
    }

    CollisionAuditResult3D simulateCollisionScenario(const char* name, int scenario) {
        resetRace();
        CollisionAuditResult3D result;
        result.name = name;

        const TrackPoint3D base = track_.sample(2600.0f + static_cast<float>(scenario) * 860.0f);
        const Vec2 forward = base.tangent;
        const Vec2 right = base.normal;
        const float heading = angleOf(forward);

        for (int i = 2; i < kKartCount; ++i) {
            TrackPoint3D park = track_.sample(5200.0f + static_cast<float>(i) * 540.0f);
            Kart3D& kart = karts_[static_cast<size_t>(i)];
            kart.pos = park.pos + park.normal * (680.0f + static_cast<float>(i) * 40.0f);
            kart.vel = {};
            kart.heading = angleOf(park.tangent);
            kart.nearest = track_.nearestIndex(kart.pos);
            updateProgress(kart);
        }

        auto place = [&](int index, Vec2 pos, float kartHeading, Vec2 vel) {
            Kart3D& kart = karts_[static_cast<size_t>(index)];
            kart.pos = pos;
            kart.heading = kartHeading;
            kart.vel = vel;
            kart.drifting = false;
            kart.boostTimer = 0.0f;
            kart.contactTimer = 0.0f;
            kart.ghostTimer = 0.0f;
            kart.elevation = bankedElevation(base, 0.0f);
            kart.verticalSpeed = 0.0f;
            kart.grounded = true;
            kart.nearest = track_.nearestIndex(kart.pos);
            updateProgress(kart);
        };

        if (scenario == 0) {
            place(0, base.pos - forward * 92.0f, heading, forward * 126.0f);
            place(1, base.pos, heading, forward * 44.0f);
        } else if (scenario == 1) {
            place(0, base.pos - forward * 88.0f, heading, forward * 98.0f);
            place(1, base.pos + forward * 88.0f, wrapAngle(heading + kPi), forward * -96.0f);
        } else {
            place(0, base.pos - forward * 44.0f - right * 34.0f, heading, forward * 92.0f + right * 18.0f);
            place(1, base.pos + forward * 8.0f + right * 22.0f, heading, forward * 80.0f - right * 12.0f);
        }

        constexpr int kFrames = static_cast<int>(3.2f / kFixedDt);
        for (int frame = 0; frame < kFrames; ++frame) {
            for (int i = 0; i < 2; ++i) {
                Kart3D& kart = karts_[static_cast<size_t>(i)];
                kart.contactTimer = std::max(0.0f, kart.contactTimer - kFixedDt);
                kart.pos += kart.vel * kFixedDt;
                kart.vel *= std::exp(-kFixedDt * 0.08f);
                updateProgress(kart);
            }
            solveKartContacts();
            const float overlap = maxKartOverlap();
            result.maxOverlap = std::max(result.maxOverlap, overlap);
            if (overlap > 1.25f) {
                ++result.overlapFrames;
            }
            if (karts_[0].contactTimer > 0.05f || karts_[1].contactTimer > 0.05f) {
                ++result.contactFrames;
            }
        }
        return result;
    }

    void integrateKart(Kart3D& kart, const Input3D& input, float dt, bool player) {
        kart.ghostTimer = std::max(0.0f, kart.ghostTimer - dt);
        updateProgress(kart);
        const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
        const float offroad = roadEdgeViolation(kart, center);
        const float laneAbs = std::abs(kart.lane);
        const float halfFootprint = contactHalfWidth(kart);
        const float roadHalf = roadSurfaceHalfWidth(center);
        const float tireCoverage = std::clamp((laneAbs + halfFootprint - roadHalf) / std::max(1.0f, halfFootprint * 2.0f), 0.0f, 1.0f);
        const float shoulder = smoothstep(tireCoverage);
        const float beyondShoulder = std::max(0.0f, laneAbs + halfFootprint - center.width * 0.5f);
        const float deepOffroad = smoothstep(std::clamp(beyondShoulder / 58.0f, 0.0f, 1.0f));

        ArcadeSurface surface;
        surface.grip = lerp(1.0f, 0.92f, shoulder) * lerp(1.0f, 0.70f, deepOffroad);
        surface.acceleration = lerp(1.0f, 0.98f, shoulder) * lerp(1.0f, 0.84f, deepOffroad);
        surface.rollingResistance = 1.0f + shoulder * 0.18f + deepOffroad * 1.85f;
        surface.steering = lerp(1.0f, 0.96f, shoulder) * lerp(1.0f, 0.80f, deepOffroad);
        surface.maxSpeed = lerp(1.0f, 0.84f, deepOffroad);
        surface.driftCharge = lerp(1.0f, 0.45f, shoulder);
        surface.bumpiness = shoulder * 0.12f + deepOffroad * 0.48f;
        surface.groundElevation = bankedElevation(center, kart.lane);
        surface.groundGrade = center.grade;
        surface.launchVelocity = tireCoverage < 0.60f ? center.launchVelocity : 0.0f;
        surface.allowsDrift = deepOffroad < 0.35f;

        ArcadeVehicleControl control;
        control.steer = input.steer;
        control.throttle = input.throttle;
        control.brake = input.brake;
        control.drift = input.drift;
        kart.telemetry = stepArcadeVehicle(kart, kart.tuning, control, surface, dt);

        const bool stuckOffroad = length(kart.vel) < 14.0f && offroad > 6.0f && input.throttle > 0.55f;
        kart.stuckTimer = stuckOffroad ? kart.stuckTimer + dt : 0.0f;
        if (kart.stuckTimer > 2.2f) {
            kart.pos = center.pos;
            kart.heading = angleOf(center.tangent);
            kart.vel = center.tangent * 32.0f;
            kart.elevation = bankedElevation(center, 0.0f);
            kart.verticalSpeed = 0.0f;
            kart.airborneTime = 0.0f;
            kart.landingImpulse = 0.0f;
            kart.grounded = true;
            kart.yawRate = 0.0f;
            kart.drifting = false;
            kart.driftPhase = ArcadeDriftPhase::Grip;
            kart.driftCharge = 0.0f;
            kart.ghostTimer = 1.0f;
            kart.stuckTimer = 0.0f;
        }

        if (!player) {
            const float aiLimit = kart.tuning.maxForwardSpeed * (0.78f + kart.aiTempo * 0.16f);
            const float speed = length(kart.vel);
            if (speed > aiLimit) {
                kart.vel *= aiLimit / speed;
            }
        }

        emitFx(kart, center, offroad, dt);
        updateProgress(kart);
        constrainToTrack(kart);
        updateProgress(kart);
    }

    void constrainToTrack(Kart3D& kart) {
        const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
        const float lane = dot(kart.pos - center.pos, center.normal);
        const float driveableLimit = hardBoundaryLaneLimit(kart, center);
        if (std::abs(lane) <= driveableLimit) {
            return;
        }
        const float sign = lane > 0.0f ? 1.0f : -1.0f;
        const float excess = std::abs(lane) - driveableLimit;
        kart.pos -= center.normal * (sign * excess);
        const float normalVelocity = dot(kart.vel, center.normal);
        if (normalVelocity * sign > 0.0f) {
            kart.vel -= center.normal * normalVelocity;
            kart.vel *= 0.96f;
        } else {
            kart.vel *= 0.992f;
        }
        kart.drifting = false;
    }

    bool shouldTestKartContact(const Kart3D& a, const Kart3D& b) const {
        if (a.ghostTimer > 0.0f || b.ghostTimer > 0.0f) {
            return false;
        }
        const float progressGap = std::abs(signedDistanceToLoop(a.progress, b.progress, track_.totalLength()));
        if (progressGap > kContactProgressWindow) {
            return false;
        }
        const float elevationA = a.elevation;
        const float elevationB = b.elevation;
        return std::abs(elevationA - elevationB) <= kContactVerticalWindow;
    }

    void solveKartContacts() {
        std::array<bool, kKartCount> moved{};
        constexpr int kContactIterations = 4;
        for (int iter = 0; iter < kContactIterations; ++iter) {
            for (int a = 0; a < kKartCount; ++a) {
                for (int b = a + 1; b < kKartCount; ++b) {
                    Kart3D& ka = karts_[static_cast<size_t>(a)];
                    Kart3D& kb = karts_[static_cast<size_t>(b)];
                    if (!shouldTestKartContact(ka, kb)) {
                        continue;
                    }
                    const KartContact3D contact = kartContact(ka, kb);
                    if (!contact.touching || contact.penetration < 0.05f) {
                        continue;
                    }

                    const Vec2 n = contact.normal;
                    const float invA = inverseKartMass(ka);
                    const float invB = inverseKartMass(kb);
                    const float invSum = invA + invB;
                    const float correctionDepth = std::max(0.0f, contact.penetration - 0.18f);
                    const Vec2 correction = n * (correctionDepth * 0.86f / invSum);
                    ka.pos -= correction * invA;
                    kb.pos += correction * invB;
                    moved[static_cast<size_t>(a)] = true;
                    moved[static_cast<size_t>(b)] = true;

                    if (iter == 0) {
                        const Vec2 relativeVelocity = kb.vel - ka.vel;
                        const float closingSpeed = dot(relativeVelocity, n);
                        if (closingSpeed < 0.0f) {
                            const float impulse = -(1.0f + 0.10f) * closingSpeed / invSum;
                            ka.vel -= n * (impulse * invA);
                            kb.vel += n * (impulse * invB);

                            const Vec2 tangent{-n.y, n.x};
                            const float tangentSpeed = dot(kb.vel - ka.vel, tangent);
                            const float tangentImpulse = std::clamp(-tangentSpeed * 0.08f / invSum, -impulse * 0.24f, impulse * 0.24f);
                            ka.vel -= tangent * (tangentImpulse * invA);
                            kb.vel += tangent * (tangentImpulse * invB);
                        }

                        ka.vel *= 0.996f;
                        kb.vel *= 0.996f;
                    }

                    ka.contactTimer = 0.40f;
                    kb.contactTimer = 0.40f;
                }
            }
        }
        for (int i = 0; i < kKartCount; ++i) {
            if (moved[static_cast<size_t>(i)]) {
                Kart3D& kart = karts_[static_cast<size_t>(i)];
                updateProgress(kart);
                constrainToTrack(kart);
                updateProgress(kart);
            }
        }
    }

    float maxKartOverlap() const {
        float maxOverlap = 0.0f;
        for (int a = 0; a < kKartCount; ++a) {
            for (int b = a + 1; b < kKartCount; ++b) {
                const Kart3D& ka = karts_[static_cast<size_t>(a)];
                const Kart3D& kb = karts_[static_cast<size_t>(b)];
                if (!shouldTestKartContact(ka, kb)) {
                    continue;
                }
                const KartContact3D contact = kartContact(ka, kb);
                if (contact.touching) {
                    maxOverlap = std::max(maxOverlap, contact.penetration);
                }
            }
        }
        return maxOverlap;
    }

    void emitFx(const Kart3D& kart, const TrackPoint3D& center, float offroad, float dt) {
        fxAccumulator_ += dt;
        if (fxAccumulator_ < 0.026f) {
            return;
        }
        fxAccumulator_ = 0.0f;
        const Vec2 forward = fromAngle(kart.heading);
        const Vec2 rear = kart.pos - forward * (kart.spec.length * 0.46f);
        const Vec2 baseVel = kart.vel * -0.10f - forward * 10.0f;
        const float rearLane = dot(rear - center.pos, center.normal);
        const float surfaceElevation = bankedElevation(center, rearLane);
        if (kart.boostTimer > 0.0f) {
            emitParticle(rear, baseVel - forward * 36.0f, surfaceElevation + 4.0f, 0.20f, 4.8f, Color{255, 181, 45, 210});
            emitParticle(rear - Vec2{-forward.y, forward.x} * 8.0f, baseVel - forward * 24.0f, surfaceElevation + 3.0f, 0.18f, 3.8f,
                         Color{244, 67, 43, 205});
        } else if (kart.drifting) {
            emitParticle(rear, baseVel, surfaceElevation + 2.5f, 0.46f, 5.5f, Color{226, 232, 219, 185});
        } else if (offroad > 2.0f && length(kart.vel) > 28.0f) {
            Color dust = mix(naturalSurfaceColor(center.zone), Color{242, 232, 194, 255}, 0.34f);
            dust.a = 184;
            emitParticle(rear, baseVel, surfaceElevation + 2.0f, 0.42f, 5.8f, dust);
        } else if (kart.contactTimer > 0.14f) {
            emitParticle(kart.pos, baseVel, surfaceElevation + 5.0f, 0.22f, 4.5f, Color{245, 231, 165, 210});
        }
    }

    void emitParticle(Vec2 pos, Vec2 vel, float elevation, float life, float size, Color color) {
        if (particles_.size() > 520) {
            particles_.erase(particles_.begin());
        }
        particles_.push_back({pos, vel, elevation, life, life, size, color});
    }

    void updateParticles(float dt) {
        for (Particle3D& p : particles_) {
            p.life -= dt;
            p.pos += p.vel * dt;
            p.vel *= std::exp(-dt * 1.8f);
            p.elevation += dt * 7.0f;
        }
        particles_.erase(std::remove_if(particles_.begin(), particles_.end(), [](const Particle3D& p) { return p.life <= 0.0f; }),
                         particles_.end());
    }

    void resetPlayerToTrack() {
        Kart3D& kart = karts_[0];
        float resetProgress = kart.progress;
        if (raceFlow_) {
            const ArcadeCheckpointResetInfo reset = raceFlow_->lastValidReset(0);
            if (reset.valid) {
                resetProgress = wrapDistance(kRaceStartProgress + reset.normalizedTrackProgress * track_.totalLength(), track_.totalLength());
            }
        }
        const TrackPoint3D tp = track_.sample(resetProgress);
        kart.pos = tp.pos;
        kart.heading = angleOf(tp.tangent);
        kart.vel = tp.tangent * 34.0f;
        kart.elevation = bankedElevation(tp, 0.0f);
        kart.verticalSpeed = 0.0f;
        kart.airborneTime = 0.0f;
        kart.landingImpulse = 0.0f;
        kart.grounded = true;
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.drifting = false;
        kart.boostTimer = 0.0f;
        kart.boostPower = 0.0f;
        kart.driftCharge = 0.0f;
        kart.contactTimer = 0.0f;
        kart.ghostTimer = 1.0f;
        updateProgress(kart);
        if (raceFlow_) {
            const auto inputs = currentRaceInputs();
            raceFlow_->rebaseRacerSample(0, inputs[0]);
        }
    }

    void updateRaceOrder() {
        std::array<std::pair<float, int>, kKartCount> order;
        for (int i = 0; i < kKartCount; ++i) {
            const Kart3D& kart = karts_[static_cast<size_t>(i)];
            const float score = raceFlow_ ? static_cast<float>(raceFlow_->racer(static_cast<size_t>(i)).validatedRaceProgress *
                                                               static_cast<double>(track_.totalLength()))
                                          : raceScore(kart);
            order[static_cast<size_t>(i)] = {score, i};
        }
        std::sort(order.begin(), order.end(), [](auto a, auto b) { return a.first > b.first; });
        for (int i = 0; i < kKartCount; ++i) {
            if (order[static_cast<size_t>(i)].second == 0) {
                playerPosition_ = i + 1;
                return;
            }
        }
    }

    void updateCamera(float dt) {
        const Kart3D& player = karts_[0];
        const Vec2 forward2 = fromAngle(player.heading);
        const float speed = length(player.vel);
        const Vec2 velocityDirection = speed > 12.0f ? normalize(player.vel) : forward2;
        const Vec2 chaseDirection = normalize(lerp(forward2, velocityDirection, 0.32f));
        const float speedT = std::clamp(speed / std::max(1.0f, player.tuning.maxForwardSpeed), 0.0f, 1.0f);
        const float back = lerp(64.0f, 69.0f, speedT);
        const float height = lerp(27.0f, 30.0f, speedT);
        const TrackPoint3D ground = track_.sample(player.progress);
        const float playerGround = bankedElevation(ground, player.lane);
        const float impactShake = std::clamp(player.contactTimer / 0.22f, 0.0f, 1.0f);
        const float boostShake = player.boostTimer > 0.0f ? 0.34f + player.boostPower * 0.34f : 0.0f;
        const float landingShake = std::clamp(player.landingImpulse / 45.0f, 0.0f, 1.0f) * 2.4f;
        const float shake = impactShake * 2.2f + boostShake + landingShake;
        const Vec2 cameraSide{-chaseDirection.y, chaseDirection.x};
        const float lateralShake = std::sin(raceTime_ * 51.0f) * shake;
        const float verticalShake = std::sin(raceTime_ * 67.0f + 0.8f) * shake * 0.55f;
        const Vec2 desiredPlanar = player.pos - chaseDirection * back + cameraSide * lateralShake;
        const Vec2 lookDirection = normalize(lerp(forward2, velocityDirection, 0.18f));
        const float airHeight = std::max(0.0f, player.elevation - playerGround);
        const float desiredElevation = playerGround + airHeight * 0.18f;
        const float verticalResponse = player.grounded ? 6.5f : 2.1f;
        cameraElevation_ = lerp(cameraElevation_, desiredElevation, 1.0f - std::exp(-dt * verticalResponse));
        const Vector3 desiredPos = toWorld(desiredPlanar, cameraElevation_ + height + verticalShake);
        const float targetElevation = playerGround + airHeight * 0.58f;
        const Vector3 desiredTarget = toWorld(player.pos + lookDirection * (42.0f + speed * 0.08f), targetElevation + 8.0f);
        const float blend = 1.0f - std::exp(-dt * 10.5f);
        camera_.position = add(camera_.position, mul(sub(desiredPos, camera_.position), blend));
        const float targetBlend = 1.0f - std::exp(-dt * 10.5f);
        camera_.target = add(camera_.target, mul(sub(desiredTarget, camera_.target), targetBlend));
        camera_.up = {0.0f, 1.0f, 0.0f};
        const float desiredFov = lerp(58.0f, 71.0f, speedT) + (player.boostTimer > 0.0f ? 1.8f : 0.0f);
        cameraFov_ = lerp(cameraFov_, desiredFov, 1.0f - std::exp(-dt * 4.2f));
        camera_.fovy = cameraFov_;
        camera_.projection = CAMERA_PERSPECTIVE;
    }

    void drawEnvironment() {
        DrawPlane({0.0f, -0.44f, 0.0f}, {390.0f, 340.0f}, Color{37, 166, 192, 255});

        // One continuous island sits beneath the complete loop. Overlapping
        // terrain plates mark sectors without ever exposing a floating road.
        drawFlatOval({0.0f, -0.43f, -3.0f}, 166.0f, 130.0f, 0.16f, Color{213, 173, 91, 255}, 112);
        drawFlatOval({0.0f, -0.31f, -3.0f}, 158.0f, 122.0f, 0.10f, Color{230, 193, 108, 255}, 112);
        drawGradientOval({0.0f, -0.36f, -3.0f}, 164.0f, 128.0f, Color{227, 188, 105, 255}, Color{214, 173, 91, 255}, 112);
        drawGradientOval({0.0f, -0.31f, -3.0f}, 157.0f, 121.0f, Color{235, 199, 115, 255}, Color{224, 184, 98, 255}, 112);
        drawFlatOval({0.0f, -0.255f, -42.0f}, 148.0f, 72.0f, 0.035f, Color{237, 201, 117, 255}, 96);
        drawFlatOval({84.0f, -0.225f, 4.0f}, 70.0f, 78.0f, 0.035f, Color{218, 180, 108, 255}, 80);
        drawFlatOval({-25.0f, -0.175f, 65.0f}, 124.0f, 57.0f, 0.035f, Color{107, 157, 82, 255}, 92);
        drawFlatOval({-96.0f, -0.145f, 21.0f}, 49.0f, 61.0f, 0.035f, Color{95, 150, 79, 255}, 64);
        drawGradientOval({0.0f, -0.285f, -42.0f}, 148.0f, 72.0f, Color{244, 210, 128, 255}, Color{226, 187, 102, 255}, 96);
        drawGradientOval({84.0f, -0.235f, 4.0f}, 70.0f, 78.0f, Color{205, 165, 101, 255}, Color{229, 193, 118, 255}, 80);
        drawGradientOval({-25.0f, -0.19f, 65.0f}, 124.0f, 57.0f, Color{80, 147, 77, 255}, Color{160, 176, 99, 255}, 92);
        drawGradientOval({-96.0f, -0.16f, 21.0f}, 49.0f, 61.0f, Color{73, 139, 75, 255}, Color{187, 181, 102, 255}, 64);

        // Foam and exposed reefs make the shoreline readable in the distance.
        for (int i = 0; i < 28; ++i) {
            const float angle = kTwoPi * static_cast<float>(i) / 28.0f;
            const float x = std::cos(angle) * (157.0f + static_cast<float>(i % 3) * 1.8f);
            const float z = -3.0f + std::sin(angle) * (121.0f + static_cast<float>((i + 1) % 4));
            drawFlatOval({x, -0.37f, z}, 4.2f + static_cast<float>(i % 4) * 0.65f, 0.26f, 0.014f,
                         Color{222, 245, 231, 155}, 18);
        }

        // Permanent jungle ridge silhouettes replace isolated scenery that
        // previously appeared to pop as the road renderer culled chunks.
        for (int i = 0; i < 11; ++i) {
            const float x = -119.0f + static_cast<float>(i) * 23.0f;
            const float height = 5.0f + static_cast<float>((i * 7) % 5) * 1.1f;
            DrawSphere({x, height * 0.34f, 130.0f + std::sin(static_cast<float>(i) * 1.8f) * 4.0f}, height,
                       i % 2 == 0 ? Color{64, 121, 71, 255} : Color{78, 137, 73, 255});
        }

        DrawSphere({-116.0f, 56.0f, -86.0f}, 8.5f, Color{255, 219, 90, 255});
        for (int i = 0; i < 6; ++i) {
            DrawCubeV({-78.0f + static_cast<float>(i) * 27.0f, 45.0f + std::sin(static_cast<float>(i)) * 5.0f, -98.0f},
                      {13.0f, 2.4f, 3.0f}, Color{236, 252, 255, 205});
        }
    }

    void drawTrack() {
        const auto& samples = track_.samples();
        if (trackRenderer_.ready()) {
            const float viewProgress = mode_ == Mode::Garage || karts_.empty() ? kRaceStartProgress : karts_[0].progress;
            trackRenderer_.draw(viewProgress * kRenderScale, 260.0f);
        } else {
            constexpr int stride = 2;
            for (int i = 0; i < track_.sampleCount(); i += stride) {
            const TrackPoint3D& a = samples[static_cast<size_t>(i)];
            const TrackPoint3D& b = samples[static_cast<size_t>((i + stride) % track_.sampleCount())];
            const float halfA = a.width * 0.5f;
            const float halfB = b.width * 0.5f;
            const std::array<float, 17> cutsA = surfaceCuts(a);
            const std::array<float, 17> cutsB = surfaceCuts(b);

            for (size_t band = 0; band + 1 < cutsA.size(); ++band) {
                drawGradientQuad(lift(track_.roadPoint(a, cutsA[band]), kTrackSurfaceLift),
                                 lift(track_.roadPoint(b, cutsB[band]), kTrackSurfaceLift),
                                 lift(track_.roadPoint(b, cutsB[band + 1]), kTrackSurfaceLift),
                                 lift(track_.roadPoint(a, cutsA[band + 1]), kTrackSurfaceLift), surfaceColorAt(a, cutsA[band]),
                                 surfaceColorAt(b, cutsB[band]), surfaceColorAt(b, cutsB[band + 1]),
                                 surfaceColorAt(a, cutsA[band + 1]));
            }

            if ((a.zone == 1 || a.zone == 5) && (i / stride) % 8 == 0) {
                Color plank = shade(mix(mix(a.road, b.road, 0.5f), mix(a.shoulder, b.shoulder, 0.5f), 0.48f), 0.94f);
                plank.a = 126;
                drawQuad(lift(track_.roadPoint(a, -halfA * 0.80f), 0.050f), lift(track_.roadPoint(b, -halfB * 0.80f), 0.050f),
                         lift(track_.roadPoint(b, halfB * 0.80f), 0.050f), lift(track_.roadPoint(a, halfA * 0.80f), 0.050f), plank);
            }

            if ((i / stride) % 7 == 0) {
                for (float lane : {-28.0f, 28.0f}) {
                    Color rut = shade(surfaceColorAt(a, lane), 0.93f);
                    rut.a = 44;
                    drawQuad(lift(track_.roadPoint(a, lane - 1.3f), 0.055f), lift(track_.roadPoint(b, lane - 1.3f), 0.055f),
                             lift(track_.roadPoint(b, lane + 1.3f), 0.055f), lift(track_.roadPoint(a, lane + 1.3f), 0.055f), rut);
                }
            }

            if ((i / stride) % 47 == 0) {
                for (float side : {-1.0f, 1.0f}) {
                    const float noise = static_cast<float>((i * 31 + (side > 0.0f ? 19 : 7)) % 76);
                    const float lane = side * (a.width * 0.5f + 42.0f + noise);
                    const Vector3 pos = lift(track_.roadPoint(a, lane), 0.066f);
                    Color chip = mix(surfaceColorAt(a, lane), naturalSurfaceColor(a.zone), 0.50f);
                    if (a.zone == 3) {
                        chip = shade(chip, 0.92f);
                    }
                    chip = shade(chip, side > 0.0f ? 0.99f : 1.02f);
                    drawFlatOval(pos, 0.22f + noise * 0.003f, 0.11f + noise * 0.002f, 0.020f, chip, 10);
                }
            }
            }
        }

        for (int i = 0; i < track_.sampleCount(); i += 24) {
            const TrackPoint3D& p = samples[static_cast<size_t>(i)];
            if (p.curvature < 0.028f) {
                continue;
            }
            const float outside = std::abs(p.signedCurvature) > 0.004f ? -std::copysign(1.0f, p.signedCurvature) : 1.0f;
            const float lane = outside * (p.width * 0.5f + 28.0f);
            const Vector3 pos = lift(track_.roadPoint(p, lane), 0.08f);
            rlPushMatrix();
            rlTranslatef(pos.x, pos.y + 0.72f, pos.z);
            rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
            DrawCubeV({0.0f, 0.0f, 0.0f}, {0.22f, 1.36f, 2.35f}, Color{30, 39, 43, 255});
            DrawCubeV({0.0f, -1.15f, 0.0f}, {0.20f, 1.05f, 0.20f}, Color{225, 225, 208, 255});
            const float arrowDirection = outside > 0.0f ? -1.0f : 1.0f;
            for (float z : {-0.62f, 0.0f, 0.62f}) {
                rlPushMatrix();
                rlTranslatef(-0.13f, 0.13f, z + arrowDirection * 0.12f);
                rlRotatef(arrowDirection * 42.0f, 1.0f, 0.0f, 0.0f);
                DrawCubeV({0.0f, 0.0f, 0.0f}, {0.07f, 0.16f, 0.72f}, Color{255, 213, 54, 255});
                rlPopMatrix();
            }
            rlPopMatrix();
        }

        // Low sector-specific edge geometry follows the same lane boundary as
        // collision resolution. It gives every corner a stable silhouette and
        // communicates exactly how much shoulder remains available.
        constexpr int boundaryStride = 10;
        for (int i = 0; i < track_.sampleCount(); i += boundaryStride) {
            const TrackPoint3D& p = samples[static_cast<size_t>(i)];
            const TrackPoint3D& next = samples[static_cast<size_t>((i + boundaryStride) % track_.sampleCount())];
            const float segmentLength = length(next.pos - p.pos) * kRenderScale * 1.05f;
            for (float side : {-1.0f, 1.0f}) {
                const float lane = side * (p.width * 0.5f + 18.0f);
                const Vector3 edge = track_.roadPoint(p, lane);
                rlPushMatrix();
                rlTranslatef(edge.x, edge.y + (p.zone == 2 ? 0.53f : 0.34f), edge.z);
                rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
                if (p.zone == 0) {
                    DrawCubeV({0.0f, 0.0f, 0.0f}, {0.24f, 0.30f, segmentLength}, Color{113, 76, 45, 255});
                    DrawCubeV({0.0f, -0.31f, -segmentLength * 0.42f}, {0.34f, 0.72f, 0.34f}, Color{86, 62, 42, 255});
                    DrawCubeV({0.0f, -0.31f, segmentLength * 0.42f}, {0.34f, 0.72f, 0.34f}, Color{86, 62, 42, 255});
                } else if (p.zone == 2) {
                    const Color wall = ((i / boundaryStride) % 2 == 0) ? Color{238, 116, 83, 255} : Color{242, 199, 119, 255};
                    DrawCubeV({0.0f, 0.0f, 0.0f}, {0.56f, 1.04f, segmentLength}, wall);
                    DrawCubeV({0.0f, 0.58f, 0.0f}, {0.68f, 0.16f, segmentLength}, Color{250, 226, 153, 255});
                } else {
                    const float rise = 0.58f + static_cast<float>((i / boundaryStride) % 3) * 0.12f;
                    DrawCubeV({0.0f, 0.0f, 0.0f}, {0.72f, rise, segmentLength}, Color{76, 101, 67, 255});
                    DrawCubeV({0.0f, rise * 0.48f, 0.0f}, {0.84f, 0.22f, segmentLength * 0.96f}, Color{111, 129, 75, 255});
                }
                rlPopMatrix();
            }
        }

        if (mode_ != Mode::Garage) {
            const TrackPoint3D start = track_.sample(kRaceStartProgress);
            const TrackPoint3D after = track_.sample(kRaceStartProgress + 10.0f);
            const float half = start.width * 0.5f;
            constexpr int kCells = 12;
            for (int cell = 0; cell < kCells; ++cell) {
                const float lane0 = lerp(-half, half, static_cast<float>(cell) / kCells);
                const float lane1 = lerp(-half, half, static_cast<float>(cell + 1) / kCells);
                const Color c = (cell % 2 == 0) ? Color{248, 246, 218, 255} : Color{30, 39, 44, 255};
                drawQuad(lift(track_.roadPoint(start, lane0), 0.095f), lift(track_.roadPoint(after, lane0), 0.095f),
                         lift(track_.roadPoint(after, lane1), 0.095f), lift(track_.roadPoint(start, lane1), 0.095f), c);
            }

            const Vector3 gate = track_.roadPoint(start, 0.0f);
            rlPushMatrix();
            rlTranslatef(gate.x, gate.y + 4.15f, gate.z);
            rlRotatef(90.0f - angleOf(start.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
            const float bannerW = start.width * kRenderScale + 3.0f;
            DrawCubeV({0.0f, 0.0f, 0.0f}, {bannerW, 0.18f, 0.28f}, Color{255, 235, 106, 255});
            for (int i = 0; i < 10; ++i) {
                const float x = -bannerW * 0.5f + (static_cast<float>(i) + 0.5f) * bannerW / 10.0f;
                DrawCubeV({x, 0.21f, 0.0f}, {bannerW / 10.2f, 0.24f, 0.34f},
                          (i % 2 == 0) ? Color{246, 246, 226, 255} : Color{26, 34, 39, 255});
            }
            DrawCubeV({-start.width * kRenderScale * 0.5f, -2.35f, 0.0f}, {0.46f, 5.1f, 0.46f}, Color{48, 130, 166, 255});
            DrawCubeV({start.width * kRenderScale * 0.5f, -2.35f, 0.0f}, {0.46f, 5.1f, 0.46f}, Color{48, 130, 166, 255});
            rlPopMatrix();
        }
    }

    void drawProp(const Prop3D& prop) {
        const TrackPoint3D p = track_.sample(prop.progress);
        const Vector3 base = track_.roadPoint(p, prop.side);
        const float s = prop.scale;
        if (renderer_.ready()) {
            arcade_render::TropicalPropKind kind = arcade_render::TropicalPropKind::RockCluster;
            float scaleMultiplier = 1.0f;
            switch (prop.type) {
                case Prop3D::Type::Palm:
                    kind = arcade_render::TropicalPropKind::Palm;
                    break;
                case Prop3D::Type::Rock:
                    kind = arcade_render::TropicalPropKind::RockCluster;
                    break;
                case Prop3D::Type::Cliff:
                case Prop3D::Type::Crystal:
                    kind = arcade_render::TropicalPropKind::RockCluster;
                    scaleMultiplier = prop.type == Prop3D::Type::Cliff ? 2.25f : 0.88f;
                    break;
                case Prop3D::Type::Hut:
                    kind = arcade_render::TropicalPropKind::BeachHut;
                    break;
                case Prop3D::Type::Boat:
                case Prop3D::Type::Sail:
                    kind = arcade_render::TropicalPropKind::FishingBoat;
                    scaleMultiplier = prop.type == Prop3D::Type::Sail ? 0.82f : 1.0f;
                    break;
                case Prop3D::Type::Market:
                    kind = arcade_render::TropicalPropKind::MarketStall;
                    break;
                case Prop3D::Type::Crane:
                    kind = arcade_render::TropicalPropKind::DockCrane;
                    break;
                case Prop3D::Type::Torch:
                    kind = arcade_render::TropicalPropKind::Torch;
                    break;
                case Prop3D::Type::Gate:
                case Prop3D::Type::Chevron:
                    kind = arcade_render::TropicalPropKind::TrackBanner;
                    scaleMultiplier = 0.72f;
                    break;
            }
            const uint32_t variant = static_cast<uint32_t>(std::abs(static_cast<int>(prop.progress * 0.071f))) % 97u;
            arcade_render::TropicalPropSpec spec = arcade_render::MakeTropicalPropSpec(kind, variant);
            spec.primary = prop.color;
            arcade_render::TropicalPropState state;
            state.position = lift(base, 0.025f);
            state.yawRadians = kPi * 0.5f - angleOf(p.tangent);
            state.scale = s * scaleMultiplier;
            state.windPhase = raceTime_ * 1.4f + prop.progress * 0.011f;
            renderer_.drawTropicalProp(spec, state);
            return;
        }
        switch (prop.type) {
            case Prop3D::Type::Palm:
                DrawCylinderEx(base, add(base, {0.0f, 5.4f * s, 0.0f}), 0.20f * s, 0.12f * s, 9, Color{126, 82, 45, 255});
                drawLocalEllipsoid(add(base, {0.0f, 5.32f * s, 0.0f}), {0.34f * s, 0.24f * s, 0.34f * s},
                                   Color{118, 90, 46, 255});
                for (int i = 0; i < 5; ++i) {
                    rlPushMatrix();
                    rlTranslatef(base.x, base.y + 5.4f * s, base.z);
                    rlRotatef(static_cast<float>(i) * 72.0f, 0.0f, 1.0f, 0.0f);
                    rlRotatef(-12.0f, 1.0f, 0.0f, 0.0f);
                    drawLocalEllipsoid({0.0f, 0.0f, 1.22f * s}, {0.30f * s, 0.070f * s, 1.35f * s},
                                       i % 2 == 0 ? Color{39, 158, 86, 255} : Color{69, 174, 92, 255});
                    rlPopMatrix();
                }
                break;
            case Prop3D::Type::Rock:
            case Prop3D::Type::Cliff:
                drawLocalEllipsoid(add(base, {0.0f, 0.55f * s, 0.0f}), {1.12f * s, 0.66f * s, 0.92f * s}, prop.color);
                drawLocalEllipsoid(add(base, {0.58f * s, 0.96f * s, -0.18f * s}), {0.72f * s, 0.78f * s, 0.58f * s},
                                   shade(prop.color, 1.12f));
                drawLocalEllipsoid(add(base, {-0.54f * s, 0.42f * s, 0.32f * s}), {0.58f * s, 0.42f * s, 0.52f * s},
                                   shade(prop.color, 0.86f));
                break;
            case Prop3D::Type::Hut:
                drawLocalTaperedBox(add(base, {0.0f, 0.9f * s, 0.0f}), {2.8f * s, 1.8f * s, 2.4f * s}, 0.86f, 1.02f,
                                    Color{174, 91, 52, 255});
                DrawCylinder(add(base, {0.0f, 2.2f * s, 0.0f}), 0.0f, 2.1f * s, 1.45f * s, 6, Color{239, 185, 92, 255});
                DrawCubeV(add(base, {0.0f, 1.0f * s, 1.22f * s}), {0.76f * s, 0.86f * s, 0.08f * s}, Color{76, 62, 48, 255});
                break;
            case Prop3D::Type::Boat:
                rlPushMatrix();
                rlTranslatef(base.x, base.y + 0.55f * s, base.z);
                rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
                drawLocalTaperedBox({0.0f, 0.0f, 0.0f}, {3.7f * s, 0.8f * s, 1.4f * s}, 0.52f, 1.06f, prop.color);
                drawLocalEllipsoid({0.0f, 0.18f * s, 0.0f}, {1.34f * s, 0.20f * s, 0.38f * s}, shade(prop.color, 1.12f));
                DrawCubeV({0.0f, 1.0f * s, 0.0f}, {0.18f * s, 2.4f * s, 0.18f * s}, Color{81, 66, 45, 255});
                drawLocalWedge({0.8f * s, 1.5f * s, 0.0f}, {1.3f * s, 1.8f * s, 0.08f * s}, 0.18f, Color{246, 239, 186, 255});
                rlPopMatrix();
                break;
            case Prop3D::Type::Market:
                drawLocalTaperedBox(add(base, {0.0f, 0.75f * s, 0.0f}), {2.8f * s, 1.5f * s, 2.1f * s}, 0.92f, 1.02f,
                                    shade(prop.color, 0.85f));
                drawLocalWedge(add(base, {0.0f, 1.75f * s, 0.0f}), {3.2f * s, 0.42f * s, 2.5f * s}, 0.78f, prop.color);
                break;
            case Prop3D::Type::Crane:
                DrawCubeV(add(base, {0.0f, 2.1f * s, 0.0f}), {0.45f * s, 4.2f * s, 0.45f * s}, Color{92, 70, 55, 255});
                DrawCubeV(add(base, {1.7f * s, 4.1f * s, 0.0f}), {3.5f * s, 0.32f * s, 0.32f * s}, prop.color);
                break;
            case Prop3D::Type::Crystal:
                DrawCylinder(add(base, {0.0f, 1.15f * s, 0.0f}), 0.0f, 0.75f * s, 2.3f * s, 5, prop.color);
                DrawCylinder(add(base, {0.9f * s, 0.8f * s, 0.4f * s}), 0.0f, 0.45f * s, 1.6f * s, 5, shade(prop.color, 1.15f));
                break;
            case Prop3D::Type::Torch:
                DrawCylinderEx(base, add(base, {0.0f, 2.4f * s, 0.0f}), 0.12f * s, 0.10f * s, 7, Color{92, 57, 36, 255});
                DrawSphere(add(base, {0.0f, 2.72f * s, 0.0f}), 0.45f * s, Color{255, 154, 41, 255});
                break;
            case Prop3D::Type::Gate:
                break;
            case Prop3D::Type::Chevron:
                rlPushMatrix();
                rlTranslatef(base.x, base.y + 1.0f * s, base.z);
                rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
                DrawCubeV({0.0f, 0.0f, 0.0f}, {0.22f * s, 1.8f * s, 2.4f * s}, prop.color);
                DrawCubeV({0.0f, 0.0f, 0.0f}, {0.28f * s, 0.55f * s, 1.9f * s}, Color{255, 235, 114, 255});
                rlPopMatrix();
                break;
            case Prop3D::Type::Sail:
                DrawCubeV(add(base, {0.0f, 1.2f * s, 0.0f}), {0.18f * s, 2.4f * s, 0.18f * s}, Color{92, 70, 52, 255});
                drawLocalWedge(add(base, {0.65f * s, 1.8f * s, 0.0f}), {1.3f * s, 1.7f * s, 0.08f * s}, 0.16f, prop.color);
                break;
        }
    }

    bool shouldDrawRaceProp(const Prop3D& prop) const {
        if (mode_ == Mode::Garage || karts_.empty()) {
            return true;
        }

        const bool largeOccluder = prop.type == Prop3D::Type::Palm || prop.type == Prop3D::Type::Hut ||
                                   prop.type == Prop3D::Type::Boat || prop.type == Prop3D::Type::Market ||
                                   prop.type == Prop3D::Type::Crane || prop.type == Prop3D::Type::Cliff ||
                                   prop.type == Prop3D::Type::Sail;
        const TrackPoint3D point = track_.sample(prop.progress);
        const Vector3 propCenter = lift(track_.roadPoint(point, prop.side), 2.2f * prop.scale);
        const Vector3 cameraToProp = sub(propCenter, camera_.position);
        const float cameraDistanceSq = cameraToProp.x * cameraToProp.x + cameraToProp.y * cameraToProp.y + cameraToProp.z * cameraToProp.z;
        const float cameraClearance = prop.type == Prop3D::Type::Palm ? 14.0f + prop.scale * 4.0f : 4.0f + prop.scale * 2.4f;
        if (cameraDistanceSq < cameraClearance * cameraClearance) {
            return false;
        }
        const Kart3D& player = karts_[0];
        const Vector3 playerPosition = toWorld(player.pos, bankedElevation(track_.sample(player.progress), player.lane));
        const Vector3 playerToProp = sub(propCenter, playerPosition);
        const Vector3 playerForward{std::cos(player.heading), 0.0f, std::sin(player.heading)};
        const Vector3 playerRight{-playerForward.z, 0.0f, playerForward.x};
        const float forwardDistance = playerToProp.x * playerForward.x + playerToProp.z * playerForward.z;
        const float lateralDistance = playerToProp.x * playerRight.x + playerToProp.z * playerRight.z;
        if (forwardDistance > -5.0f && forwardDistance < 58.0f && std::abs(lateralDistance) < 13.0f) {
            return false;
        }
        if (!largeOccluder) {
            return true;
        }
        const Vector3 cameraRay = sub(camera_.target, camera_.position);
        const Vector3 toProp = sub(propCenter, camera_.position);
        const float rayLengthSq = cameraRay.x * cameraRay.x + cameraRay.y * cameraRay.y + cameraRay.z * cameraRay.z;
        if (rayLengthSq < 0.001f) {
            return true;
        }
        const float t = (toProp.x * cameraRay.x + toProp.y * cameraRay.y + toProp.z * cameraRay.z) / rayLengthSq;
        if (t <= 0.04f || t >= 1.05f) {
            return true;
        }
        const Vector3 closest = add(camera_.position, mul(cameraRay, t));
        const Vector3 delta = sub(propCenter, closest);
        const float distanceSq = delta.x * delta.x + delta.y * delta.y + delta.z * delta.z;
        float radius = 1.7f * prop.scale;
        if (prop.type == Prop3D::Type::Hut || prop.type == Prop3D::Type::Market || prop.type == Prop3D::Type::Boat) {
            radius = 3.0f * prop.scale;
        } else if (prop.type == Prop3D::Type::Crane || prop.type == Prop3D::Type::Cliff) {
            radius = 2.5f * prop.scale;
        }
        return distanceSq > radius * radius;
    }

    void drawProps() {
        if (mode_ == Mode::Garage) {
            return;
        }
        for (const Prop3D& prop : track_.props()) {
            if (!shouldDrawRaceProp(prop)) {
                continue;
            }
            drawProp(prop);
        }
    }

    void drawDriver(const Kart3D& kart, float w, float l, float h, bool player) {
        const uint32_t hash = stableHash(kart.racer);
        static constexpr std::array<Color, 6> kSkin = {
            Color{116, 67, 43, 255},  Color{154, 94, 55, 255}, Color{191, 121, 73, 255},
            Color{218, 153, 98, 255}, Color{235, 177, 121, 255}, Color{92, 54, 41, 255},
        };
        static constexpr std::array<Color, 6> kHair = {
            Color{39, 30, 25, 255},  Color{75, 48, 31, 255}, Color{132, 83, 38, 255},
            Color{226, 174, 78, 255}, Color{35, 43, 51, 255}, Color{206, 79, 84, 255},
        };

        const Color skin = kSkin[hash % kSkin.size()];
        const Color helmet = racerColor(kart.racer);
        const Color shirt = shade(racerColor(kart.racer), 0.82f + static_cast<float>((hash >> 3) % 5) * 0.04f);
        const Color glove = shade(kart.spec.body, 0.55f);
        const bool garageIdle = mode_ == Mode::Garage && player;
        const float idle = garageIdle ? std::sin(garageSpin_ * 2.2f + static_cast<float>(hash % 11)) : std::sin(kart.progress * 0.035f);
        const float steerPose = kart.steerSmoothed * 0.22f;

        DrawCylinderEx({0.0f, h * 1.02f, -l * 0.07f}, {0.0f, h * 1.38f, -l * 0.04f}, w * 0.10f, w * 0.145f, 12, shirt);
        drawLocalEllipsoid({0.0f, h * 1.27f, -l * 0.03f}, {w * 0.155f, h * 0.17f, l * 0.095f}, shade(shirt, 1.12f));
        drawLocalBox({0.0f, h * 1.08f, -l * 0.20f}, {w * 0.45f, h * 0.17f, l * 0.12f}, Color{34, 43, 49, 255});
        DrawCylinderEx({0.0f, h * 1.42f, -l * 0.03f}, {0.0f, h * 1.54f, -l * 0.02f}, w * 0.07f, w * 0.06f, 8,
                       skin);

        const Vector3 leftShoulder{-w * 0.18f, h * 1.34f, -l * 0.01f};
        const Vector3 rightShoulder{w * 0.18f, h * 1.34f, -l * 0.01f};
        Vector3 leftHand{-w * (0.17f + steerPose), h * 1.18f, l * 0.23f};
        Vector3 rightHand{w * (0.17f - steerPose), h * 1.18f, l * 0.23f};
        if (garageIdle && (hash & 1u) == 0u) {
            rightHand = {w * 0.34f, h * (1.62f + idle * 0.12f), l * 0.06f};
        }
        DrawCylinderEx(leftShoulder, leftHand, h * 0.038f, h * 0.044f, 8, skin);
        DrawCylinderEx(rightShoulder, rightHand, h * 0.038f, h * 0.044f, 8, skin);
        drawLocalEllipsoid(leftHand, {w * 0.055f, h * 0.048f, h * 0.048f}, glove);
        drawLocalEllipsoid(rightHand, {w * 0.055f, h * 0.048f, h * 0.048f}, glove);

        DrawCylinderEx({-w * 0.21f, h * 1.16f, l * 0.25f}, {w * 0.21f, h * 1.16f, l * 0.25f}, h * 0.032f, h * 0.032f,
                       12, Color{31, 38, 44, 255});
        DrawCylinderEx({0.0f, h * 1.08f, l * 0.15f}, {0.0f, h * 1.16f, l * 0.25f}, h * 0.024f, h * 0.024f, 8,
                       Color{31, 38, 44, 255});

        drawLocalEllipsoid({0.0f, h * 1.70f + idle * h * 0.018f, -l * 0.02f}, {h * 0.25f, h * 0.29f, h * 0.25f}, helmet);
        drawLocalEllipsoid({0.0f, h * 1.66f + idle * h * 0.018f, l * 0.08f}, {h * 0.16f, h * 0.16f, h * 0.075f}, skin);
        DrawCubeV({0.0f, h * 1.71f + idle * h * 0.018f, l * 0.145f}, {w * 0.25f, h * 0.075f, h * 0.045f},
                  Color{34, 50, 60, 255});

        const int hairStyle = static_cast<int>((hash >> 4) % 4u);
        const Color hair = kHair[(hash >> 7) % kHair.size()];
        if (hairStyle == 0) {
            drawLocalEllipsoid({0.0f, h * 1.93f, -l * 0.03f}, {h * 0.18f, h * 0.08f, h * 0.20f}, hair);
        } else if (hairStyle == 1) {
            DrawCylinderEx({0.0f, h * 1.93f, -l * 0.05f}, {0.0f, h * 2.12f, -l * 0.07f}, h * 0.075f, 0.0f, 6, hair);
        } else if (hairStyle == 2) {
            DrawCubeV({0.0f, h * 1.96f, -l * 0.03f}, {w * 0.42f, h * 0.07f, l * 0.20f}, hair);
        } else {
            DrawCylinderEx({-w * 0.20f, h * 1.76f, -l * 0.08f}, {-w * 0.34f, h * 1.48f, -l * 0.11f}, h * 0.045f,
                           h * 0.030f, 7, hair);
        }
    }

    void drawKart(const Kart3D& kart, bool player) {
        const TrackPoint3D ground = track_.sample(kart.progress);
        const float surfaceElevation = bankedElevation(ground, kart.lane);
        const Vector3 groundSurface = toWorld(kart.pos, surfaceElevation);
        const Vector3 vehicleSurface = toWorld(kart.pos, kart.elevation);
        if (renderer_.ready()) {
            const auto style = static_cast<arcade_render::BuggyBodyStyle>(kart.spec.bodyStyle % 4);
            arcade_render::BuggyVisualSpec spec = arcade_render::MakeBuggyVisualSpec(style, kart.spec.body, kart.spec.accent);
            spec.glass = kart.spec.glass;
            spec.width = kart.spec.width * kRenderScale * 0.88f;
            spec.length = kart.spec.length * kRenderScale * 1.02f;
            spec.bodyHeight = kart.spec.height * kRenderScale * 0.78f;
            spec.wheelRadius = std::max(0.50f, kart.spec.height * kRenderScale * 0.46f);
            spec.wheelWidth = spec.width * 0.17f;
            spec.rideHeight = spec.bodyHeight * 0.18f;

            const uint32_t hash = stableHash(kart.racer);
            static constexpr std::array<Color, 6> kSkin = {
                Color{116, 67, 43, 255},  Color{154, 94, 55, 255}, Color{191, 121, 73, 255},
                Color{218, 153, 98, 255}, Color{235, 177, 121, 255}, Color{92, 54, 41, 255},
            };
            static constexpr std::array<Color, 6> kHair = {
                Color{39, 30, 25, 255},  Color{75, 48, 31, 255}, Color{132, 83, 38, 255},
                Color{226, 174, 78, 255}, Color{35, 43, 51, 255}, Color{206, 79, 84, 255},
            };
            spec.driver.skin = kSkin[hash % kSkin.size()];
            spec.driver.hair = kHair[(hash >> 7) % kHair.size()];
            spec.driver.shirt = shade(racerColor(kart.racer), 0.86f);
            spec.driver.headwear = racerColor(kart.racer);
            spec.driver.gloves = shade(kart.spec.body, 0.48f);
            spec.driver.headwearStyle = static_cast<arcade_render::DriverHeadwear>((hash >> 4) % 4u);

            arcade_render::BuggyRenderState state;
            state.position = lift(vehicleSurface, kTrackSurfaceLift);
            state.shadowPosition = lift(groundSurface, kTrackSurfaceLift + 0.005f);
            state.useGroundShadowPosition = true;
            state.headingRadians = kPi * 0.5f - kart.heading;
            state.pitchRadians = kart.bodyPitch;
            state.rollRadians = kart.bodyRoll + (kart.grounded ? bankRollDegrees(ground) * DEG2RAD : 0.0f);
            state.steeringRadians = kart.steerAngle;
            state.wheelSpinRadians = kart.wheelSpin;
            const float suspension = std::clamp(kart.suspensionCompression, 0.0f, 1.0f);
            const float pitchLoad = std::clamp(kart.bodyPitch * 2.8f, -0.22f, 0.22f);
            const float rollLoad = std::clamp(kart.bodyRoll * 2.2f, -0.22f, 0.22f);
            state.suspensionCompression = {
                std::clamp(0.16f + suspension + pitchLoad + rollLoad, 0.0f, 1.0f),
                std::clamp(0.16f + suspension + pitchLoad - rollLoad, 0.0f, 1.0f),
                std::clamp(0.16f + suspension - pitchLoad + rollLoad, 0.0f, 1.0f),
                std::clamp(0.16f + suspension - pitchLoad - rollLoad, 0.0f, 1.0f),
            };
            state.speedNormalized = std::clamp(length(kart.vel) / kart.tuning.maxForwardSpeed, 0.0f, 1.25f);
            state.boostAmount = kart.boostTimer > 0.0f ? 0.55f + kart.boostPower * 0.45f : 0.0f;
            state.brakeAmount = kart.brakeLoad;
            state.dustAmount = std::clamp(roadEdgeViolation(kart, ground) / 22.0f, 0.0f, 1.0f) *
                               std::clamp(state.speedNormalized * 1.4f, 0.0f, 1.0f);
            state.airborneAmount = kart.grounded ? 0.0f : std::clamp(kart.airborneTime / 0.18f, 0.0f, 1.0f);
            state.visualTime = raceTime_ + static_cast<float>(hash & 255u) * 0.013f;
            state.damageFlash = std::clamp(kart.contactTimer / 0.22f, 0.0f, 1.0f);
            state.driverLean = std::clamp(-kart.steerSmoothed - kart.slipAngle * 0.45f, -1.0f, 1.0f);
            renderer_.drawBuggy(spec, state);
            (void)player;
            return;
        }
        const Vector3 base = lift(vehicleSurface, kTrackSurfaceLift + kKartWheelGroundClearance);
        const float w = kart.spec.width * kRenderScale;
        const float l = kart.spec.length * kRenderScale;
        const float h = kart.spec.height * kRenderScale;

        const Vector3 shadow = lift(groundSurface, kTrackSurfaceLift + 0.006f);
        rlPushMatrix();
        rlTranslatef(shadow.x, shadow.y, shadow.z);
        rlRotatef(90.0f - kart.heading * RAD2DEG, 0.0f, 1.0f, 0.0f);
        rlRotatef(kart.grounded ? bankRollDegrees(ground) : 0.0f, 0.0f, 0.0f, 1.0f);
        DrawCylinder({0.0f, 0.0f, 0.0f}, w * 0.78f, w * 0.78f, 0.035f, 18, Color{28, 35, 37, 90});
        rlPopMatrix();

        rlPushMatrix();
        rlTranslatef(base.x, base.y, base.z);
        rlRotatef(90.0f - kart.heading * RAD2DEG, 0.0f, 1.0f, 0.0f);
        const float speed = length(kart.vel);
        const float speedT = std::clamp(speed / 150.0f, 0.0f, 1.0f);
        const float bounce = std::sin(kart.progress * 0.075f + static_cast<float>(kart.spec.bodyStyle)) * 0.045f * speedT;
        const float pitch = kart.bodyPitch * RAD2DEG;
        const float contactLift = kart.contactTimer > 0.0f ? std::max(0.0f, std::sin(kart.contactTimer * 80.0f) * 0.035f) : 0.0f;
        rlTranslatef(0.0f, std::max(0.0f, bounce) + contactLift, 0.0f);
        rlRotatef(kart.grounded ? bankRollDegrees(ground) : 0.0f, 0.0f, 0.0f, 1.0f);
        rlRotatef(pitch, 1.0f, 0.0f, 0.0f);
        const float lean = std::clamp(kart.steerSmoothed * length(kart.vel) / 150.0f, -0.55f, 0.55f);
        rlRotatef(-lean * 8.0f, 0.0f, 0.0f, 1.0f);

        const Color body = shade(kart.spec.body, kart.contactTimer > 0.0f ? 1.24f : 1.0f);
        drawLocalTaperedBox({0.0f, h * 0.48f, -l * 0.02f}, {w * 1.10f, h * 0.60f, l * 0.94f}, 0.72f, 1.03f, body);
        drawLocalWedge({0.0f, h * 0.84f, l * 0.22f}, {w * 0.96f, h * 0.52f, l * 0.55f}, 0.34f, shade(body, 1.08f));
        drawLocalTaperedBox({0.0f, h * 0.89f, -l * 0.37f}, {w * 0.90f, h * 0.56f, l * 0.44f}, 0.94f, 0.76f, shade(body, 0.96f));
        drawLocalEllipsoid({0.0f, h * 1.14f, -l * 0.13f}, {w * 0.32f, h * 0.075f, l * 0.24f}, shade(body, 0.62f));
        drawLocalEllipsoid({0.0f, h * 1.30f, -l * 0.13f}, {w * 0.245f, h * 0.19f, l * 0.175f}, shade(kart.spec.glass, 0.84f));
        DrawCubeV({0.0f, h * 1.20f, l * 0.025f}, {w * 0.38f, h * 0.055f, l * 0.060f}, shade(kart.spec.glass, 0.58f));
        drawLocalBox({0.0f, h * 0.78f, l * 0.48f}, {w * 0.84f, h * 0.13f, l * 0.11f}, kart.spec.accent);
        drawLocalBox({0.0f, h * 0.76f, -l * 0.58f}, {w * 0.58f, h * 0.13f, l * 0.14f}, kart.spec.accent);
        DrawCylinderEx({-w * 0.40f, h * 0.42f, l * 0.56f}, {w * 0.40f, h * 0.42f, l * 0.56f}, h * 0.060f, h * 0.060f, 10,
                       shade(kart.spec.accent, 0.88f));
        DrawCylinderEx({-w * 0.34f, h * 0.40f, -l * 0.67f}, {w * 0.34f, h * 0.40f, -l * 0.67f}, h * 0.050f, h * 0.050f,
                       10, shade(kart.spec.accent, 0.78f));

        const Color fender = shade(kart.spec.body, 0.78f);
        for (float sx : {-1.0f, 1.0f}) {
            drawLocalEllipsoid({sx * w * 0.55f, h * 0.58f, l * 0.34f}, {w * 0.17f, h * 0.13f, l * 0.18f}, fender);
            drawLocalEllipsoid({sx * w * 0.55f, h * 0.56f, -l * 0.38f}, {w * 0.16f, h * 0.12f, l * 0.17f}, fender);
            drawLocalBox({sx * w * 0.51f, h * 0.38f, l * 0.04f}, {w * 0.08f, h * 0.28f, l * 0.54f}, shade(body, 0.72f));
        }

        switch (kart.spec.bodyStyle % 8) {
            case 0:
                drawLocalBox({0.0f, h * 1.58f, -l * 0.66f}, {w * 0.95f, h * 0.14f, l * 0.20f}, kart.spec.accent);
                drawLocalBox({-w * 0.42f, h * 1.30f, -l * 0.58f}, {w * 0.09f, h * 0.72f, l * 0.08f}, shade(kart.spec.body, 0.72f));
                drawLocalBox({w * 0.42f, h * 1.30f, -l * 0.58f}, {w * 0.09f, h * 0.72f, l * 0.08f}, shade(kart.spec.body, 0.72f));
                break;
            case 1:
                drawLocalBox({0.0f, h * 0.92f, l * 0.58f}, {w * 0.54f, h * 0.30f, l * 0.30f}, shade(kart.spec.body, 1.12f));
                drawLocalBox({0.0f, h * 1.72f, -l * 0.30f}, {w * 0.16f, h * 0.72f, l * 0.14f}, kart.spec.accent);
                break;
            case 2:
                for (float sx : {-1.0f, 1.0f}) {
                    drawLocalBox({sx * w * 0.34f, h * 1.74f, -l * 0.12f}, {w * 0.08f, h * 1.10f, l * 0.08f}, shade(kart.spec.accent, 0.88f));
                }
                drawLocalBox({0.0f, h * 2.18f, -l * 0.12f}, {w * 0.82f, h * 0.10f, l * 0.12f}, shade(kart.spec.accent, 0.88f));
                break;
            case 3:
                drawLocalBox({0.0f, h * 0.82f, l * 0.68f}, {w * 0.42f, h * 0.22f, l * 0.42f}, shade(kart.spec.body, 1.12f));
                drawLocalBox({0.0f, h * 1.02f, -l * 0.66f}, {w * 0.34f, h * 0.18f, l * 0.20f}, kart.spec.accent);
                break;
            case 4:
                drawLocalBox({0.0f, h * 1.34f, -l * 0.18f}, {w * 0.78f, h * 0.30f, l * 0.56f}, shade(kart.spec.body, 1.08f));
                drawLocalBox({0.0f, h * 1.72f, -l * 0.20f}, {w * 0.50f, h * 0.22f, l * 0.26f}, kart.spec.glass);
                break;
            case 5:
                drawLocalBox({-w * 0.30f, h * 0.74f, -l * 0.76f}, {w * 0.16f, h * 0.16f, l * 0.30f}, Color{45, 49, 52, 255});
                drawLocalBox({w * 0.30f, h * 0.74f, -l * 0.76f}, {w * 0.16f, h * 0.16f, l * 0.30f}, Color{45, 49, 52, 255});
                break;
            case 6:
                drawLocalBox({-w * 0.38f, h * 1.84f, -l * 0.10f}, {w * 0.08f, h * 0.10f, l * 0.72f}, kart.spec.accent);
                drawLocalBox({w * 0.38f, h * 1.84f, -l * 0.10f}, {w * 0.08f, h * 0.10f, l * 0.72f}, kart.spec.accent);
                break;
            default:
                drawLocalBox({-w * 0.46f, h * 1.12f, -l * 0.52f}, {w * 0.14f, h * 0.62f, l * 0.20f}, kart.spec.accent);
                drawLocalBox({w * 0.46f, h * 1.12f, -l * 0.52f}, {w * 0.14f, h * 0.62f, l * 0.20f}, kart.spec.accent);
                break;
        }

        const float tireR = std::max(0.42f, h * 0.48f);
        const float tireW = w * 0.32f;
        const float wheelSpin = std::fmod(-kart.progress * kRenderScale / std::max(0.01f, tireR) * RAD2DEG, 360.0f);
        const float steerDeg = kart.steerSmoothed * 24.0f;
        drawLocalWheel(-w * 0.55f, l * 0.35f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent, wheelSpin, steerDeg, true);
        drawLocalWheel(w * 0.55f, l * 0.35f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent, wheelSpin, steerDeg, true);
        drawLocalWheel(-w * 0.55f, -l * 0.38f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent, wheelSpin, 0.0f, false);
        drawLocalWheel(w * 0.55f, -l * 0.38f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent, wheelSpin, 0.0f, false);

        drawDriver(kart, w, l, h, player);
        if (kart.boostTimer > 0.0f) {
            DrawCylinderEx({-w * 0.22f, h * 0.42f, -l * 0.62f}, {-w * 0.22f, h * 0.42f, -l * 1.12f}, h * 0.20f, 0.0f, 8,
                           Color{255, 171, 42, 220});
            DrawCylinderEx({w * 0.22f, h * 0.42f, -l * 0.62f}, {w * 0.22f, h * 0.42f, -l * 1.12f}, h * 0.20f, 0.0f, 8,
                           Color{242, 73, 42, 205});
        }
        if (player) {
            DrawCubeV({0.0f, h * 2.35f, 0.0f}, {w * 0.55f, h * 0.08f, l * 0.08f}, Color{255, 238, 107, 255});
        }
        rlPopMatrix();
    }

    void drawKarts() {
        if (mode_ == Mode::Garage) {
            const TrackPoint3D start = track_.sample(kRaceStartProgress + 52.0f);
            Kart3D preview = karts_[0];
            preview.spec = specs_[static_cast<size_t>(selectedCar_)];
            preview.racer = racers_[static_cast<size_t>(selectedRacer_)];
            preview.pos = start.pos;
            preview.heading = angleOf(start.tangent) + std::sin(garageSpin_ * 0.58f) * 0.10f;
            preview.vel = start.tangent * 38.0f;
            preview.progress = start.progress;
            preview.nearest = track_.nearestIndex(preview.pos);
            preview.steerSmoothed = std::sin(garageSpin_ * 1.2f) * 0.08f;
            drawKart(preview, true);
            return;
        }
        std::array<int, kKartCount> order{};
        for (int i = 0; i < kKartCount; ++i) {
            order[static_cast<size_t>(i)] = i;
        }
        std::sort(order.begin(), order.end(), [&](int a, int b) {
            return lengthSq(karts_[static_cast<size_t>(a)].pos - karts_[0].pos) >
                   lengthSq(karts_[static_cast<size_t>(b)].pos - karts_[0].pos);
        });
        for (int index : order) {
            if (index != 0) {
                const Kart3D& kart = karts_[static_cast<size_t>(index)];
                const TrackPoint3D ground = track_.sample(kart.progress);
                const Vector3 center = toWorld(kart.pos, bankedElevation(ground, kart.lane));
                const Vector3 offset = sub(center, camera_.position);
                const float distanceSq = offset.x * offset.x + offset.y * offset.y + offset.z * offset.z;
                // Reject only geometry effectively intersecting the camera's
                // near plane. Racing opponents must remain visible in contact.
                if (distanceSq < 1.5f * 1.5f) {
                    continue;
                }
            }
            drawKart(karts_[static_cast<size_t>(index)], index == 0);
        }
    }

    void drawParticles() {
        for (const Particle3D& p : particles_) {
            const float t = std::clamp(p.life / p.maxLife, 0.0f, 1.0f);
            Color c = p.color;
            c.a = static_cast<unsigned char>(static_cast<float>(c.a) * t);
            const float size = p.size * kRenderScale * (1.35f - t * 0.25f);
            if (IsTextureValid(particleTexture_)) {
                DrawBillboard(camera_, particleTexture_, toWorld(p.pos, p.elevation), size, c);
            } else {
                DrawSphere(toWorld(p.pos, p.elevation), size * 0.5f, c);
            }
        }
    }

    void drawSpeedFx() {
        if (mode_ == Mode::Garage || karts_.empty()) {
            return;
        }
        const Kart3D& player = karts_[0];
        float amount = std::clamp((length(player.vel) / player.tuning.maxForwardSpeed - 0.42f) / 0.58f, 0.0f, 1.0f);
        if (player.boostTimer > 0.0f) {
            amount = std::max(amount, 0.72f + player.boostPower * 0.28f);
        }
        if (amount <= 0.01f) {
            return;
        }
        const float width = static_cast<float>(GetScreenWidth());
        const float height = static_cast<float>(GetScreenHeight());
        const Vector2 center{width * 0.5f, height * 0.48f};
        for (int i = 0; i < 22; ++i) {
            const float seed = std::fmod(static_cast<float>(i) * 0.6180339f + raceTime_ * (0.31f + i * 0.003f), 1.0f);
            const float angle = static_cast<float>(i) / 22.0f * kTwoPi + 0.19f;
            const Vector2 direction{std::cos(angle), std::sin(angle)};
            const float radial = lerp(0.34f, 0.72f, seed);
            const float radius = std::min(width, height) * radial;
            const float lineLength = lerp(16.0f, 58.0f, amount) * (0.65f + seed * 0.7f);
            const Vector2 start{center.x + direction.x * radius, center.y + direction.y * radius};
            const Vector2 end{start.x + direction.x * lineLength, start.y + direction.y * lineLength};
            const unsigned char alpha = static_cast<unsigned char>((22.0f + seed * 44.0f) * amount);
            DrawLineEx(start, end, 1.0f + amount * 1.5f, Color{224, 249, 247, alpha});
        }
    }

    void drawHud(float fps, bool hasController) {
        (void)fps;
        if (mode_ == Mode::Garage) {
            const KartSpec3D& spec = specs_[static_cast<size_t>(selectedCar_)];
            harbor::ui::GarageHudViewModel view;
            view.eventName = "SUNSET COVE GRAND PRIX";
            view.vehicleName = spec.name;
            static constexpr std::array<const char*, 4> kClasses = {"ALL-ROUNDER", "RALLY", "DRIFTER", "HEAVY"};
            view.vehicleClass = kClasses[static_cast<size_t>(spec.bodyStyle) % kClasses.size()];
            view.driverName = racers_[static_cast<size_t>(selectedRacer_)];
            view.stats.speed = std::clamp((spec.maxSpeed - 178.0f) / 34.0f, 0.12f, 1.0f);
            view.stats.acceleration = std::clamp((spec.accel - 214.0f) / 82.0f, 0.12f, 1.0f);
            view.stats.handling = std::clamp((spec.grip * 0.58f + spec.drift * 0.42f - 0.88f) / 0.36f, 0.12f, 1.0f);
            view.stats.strength = std::clamp((spec.width - 30.0f) / 12.0f * 0.62f + (spec.height - 12.0f) / 8.0f * 0.38f,
                                             0.12f, 1.0f);
            view.vehicleIndex = selectedCar_;
            view.vehicleCount = static_cast<int>(specs_.size());
            view.driverIndex = selectedRacer_;
            view.driverCount = static_cast<int>(racers_.size());
            view.lapOptions = kLapOptions;
            view.selectedLapOption = selectedLapOption_;
            view.presentationTimeSeconds = garageSpin_;
            view.canStart = true;
            view.controllerConnected = hasController;
            harbor::ui::DrawGarageHud(view);
        } else {
            const Kart3D& player = karts_[0];
            const int laps = targetLaps();
            harbor::ui::RaceHudViewModel view;
            view.vehicleName = player.spec.name;
            view.driverName = player.racer;
            view.speedKph = static_cast<int>(std::max(0.0f, player.telemetry.forwardSpeed) * 1.22f + 0.5f);
            view.currentLap = laps == kInfiniteLaps ? std::max(1, player.lap + 1) : std::clamp(player.lap + 1, 1, laps);
            view.totalLaps = laps;
            view.position = playerPosition_;
            view.racerCount = kKartCount;
            view.raceTimeSeconds = raceTime_;
            view.racerProgressCount = kKartCount;
            view.playerProgressIndex = 0;
            const float raceDistance = laps == kInfiniteLaps ? track_.totalLength() : track_.totalLength() * static_cast<float>(laps);
            for (int i = 0; i < kKartCount; ++i) {
                const float score = raceScore(karts_[static_cast<size_t>(i)]);
                view.racerProgress[static_cast<size_t>(i)] = laps == kInfiniteLaps
                                                                 ? raceLapProgress(karts_[static_cast<size_t>(i)]) / track_.totalLength()
                                                                 : std::clamp(score / raceDistance, 0.0f, 1.0f);
            }
            view.raceProgress = view.racerProgress[0];
            view.driftCharge = std::clamp(player.driftCharge / player.tuning.tierThreeCharge, 0.0f, 1.0f);
            view.boostCharge = std::clamp(player.boostTimer / player.tuning.tierThreeBoostDuration, 0.0f, 1.0f);
            view.presentationTimeSeconds = raceTime_;
            view.boostActive = player.boostTimer > 0.0f;
            view.wrongWay = raceFlow_ && raceFlow_->racer(0).wrongWay;
            view.finished = raceFinished_;
            view.controllerConnected = hasController;
            harbor::ui::DrawRaceHud(view);
            harbor::ui::CountdownHudViewModel countdown;
            countdown.visible = (raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Countdown) || countdownGoTimer_ > 0.0f;
            countdown.secondsRemaining = raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Countdown
                                             ? raceFlow_->countdownRemainingSeconds()
                                             : 0.0f;
            harbor::ui::DrawCountdownHud(countdown);
        }
        if (mode_ == Mode::Pause) {
            harbor::ui::PauseHudViewModel view;
            view.eventName = "SUNSET COVE GRAND PRIX";
            view.currentLap = std::max(1, karts_[0].lap + 1);
            view.totalLaps = targetLaps();
            view.raceTimeSeconds = raceTime_;
            view.showRestart = false;
            view.showQuit = false;
            view.visible = true;
            harbor::ui::DrawPauseHud(view);
        }
    }

    Track3D track_;
    std::array<KartSpec3D, 8> specs_;
    std::array<std::string, 10> racers_;
    std::vector<Kart3D> karts_;
    std::vector<Particle3D> particles_;
    std::unique_ptr<ArcadeRaceFlow> raceFlow_;
    arcade_render::ArcadeRender renderer_;
    ArcadeAudio audio_;
    harbor::TrackRenderer trackRenderer_;
    Texture2D particleTexture_{};
    Camera camera_{};
    Mode mode_ = Mode::Garage;
    int selectedCar_ = 0;
    int selectedRacer_ = 0;
    int selectedLapOption_ = 0;
    int playerPosition_ = 1;
    float raceTime_ = 0.0f;
    float finishTime_ = 0.0f;
    float garageSpin_ = 0.0f;
    float fxAccumulator_ = 0.0f;
    float cameraFov_ = 58.0f;
    float cameraElevation_ = 0.0f;
    float countdownGoTimer_ = 0.0f;
    bool raceFinished_ = false;
};

}  // namespace

int runHarborKarts3D(int argc, char** argv) {
    const bool inputAudit = hasArg(argc, argv, "--input-audit");
    if (inputAudit) {
        const bool ok = controllerContractAudit();
        std::cout << "input-audit sequence=0,1,1,0,0 trigger_ranges=valid authoritative_backend=single ok=" << ok << "\n";
        return ok ? 0 : 1;
    }
    const bool audioAudit = hasArg(argc, argv, "--audio-audit");
    if (audioAudit) {
        const ArcadeAudioAuditResult result = runArcadeAudioUnitAudit();
        std::cout << "audio-audit checks=" << result.checks << " failures=" << result.failures << " idle_rms=" << result.idleRms
                  << " full_rms=" << result.fullSpeedRms << " scrub_delta=" << result.scrubRmsIncrease
                  << " landing_peak=" << result.landingPeak << " peak=" << result.peakMagnitude
                  << " deterministic_hash=" << result.deterministicHash << " ok=" << result.ok << "\n";
        return result.ok ? 0 : 1;
    }
    const bool raceFlowAudit = hasArg(argc, argv, "--race-flow-audit");
    if (raceFlowAudit) {
        const ArcadeRaceAuditResult result = runArcadeRaceUnitAudit();
        std::cout << "race-flow-audit checks=" << result.checks << " failures=" << result.failures
                  << " phases=" << result.phasesValid << " checkpoints=" << result.checkpointsValid
                  << " wrong_way=" << result.wrongWayValid << " finish_order=" << result.finishOrderingValid
                  << " infinite=" << result.infiniteModeValid << " discontinuity_guard=" << result.discontinuityGuardValid
                  << " ok=" << result.ok << "\n";
        return result.ok ? 0 : 1;
    }
    const bool vehicleAudit = hasArg(argc, argv, "--vehicle-audit");
    if (vehicleAudit) {
        const ArcadeVehicleAuditResult result = runArcadeVehicleUnitAudit();
        std::cout << "vehicle-audit checks=" << result.checks << " failures=" << result.failures
                  << " straight_speed=" << result.straightLineSpeed << " stop_speed=" << result.stoppedSpeed
                  << " momentum_error=" << result.momentumError << " drift_slip=" << result.driftPeakSlip
                  << " drift_boost_tier=" << result.driftBoostTier << " loose_surface_ratio=" << result.looseSurfaceSpeedRatio
                  << " shoulder_ratio=" << result.shoulderSpeedRatio << " brake_yaw=" << result.brakeOversteerPeakYaw
                  << " brake_slip=" << result.brakeOversteerPeakSlip << " brake_recovery=" << result.brakeRecoverySlip
                  << " brake_load_2s=" << result.brakeLoadAfterRelease
                  << " jump_apex=" << result.jumpApex << " jump_airtime=" << result.jumpAirTime
                  << " landing_impulse=" << result.jumpLandingImpulse << " jump_step_error=" << result.jumpFixedStepError
                  << " jump_pitch_up=" << result.jumpNoseUpPitch << " jump_pitch_down=" << result.jumpNoseDownPitch
                  << " fixed_step_error=" << result.fixedStepPositionError << " ok=" << result.ok << "\n";
        return result.ok ? 0 : 1;
    }
    const bool windowed = hasArg(argc, argv, "--windowed") || hasArg(argc, argv, "--smoke-render") ||
                          hasArg(argc, argv, "--diagnose-controller") || hasArg(argc, argv, "--handling-audit") ||
                          hasArg(argc, argv, "--race-audit") || hasArg(argc, argv, "--collision-audit") ||
                          hasArg(argc, argv, "--perf-audit") || hasArg(argc, argv, "--capture-lap") ||
                          hasArg(argc, argv, "--capture-driven-lap") || hasArg(argc, argv, "--capture-section-tour");
    const bool smokeRender = hasArg(argc, argv, "--smoke-render");
    const bool capturePlaytest = hasArg(argc, argv, "--capture-playtest");
    const bool captureDrivenLap = hasArg(argc, argv, "--capture-lap") || hasArg(argc, argv, "--capture-driven-lap");
    const bool captureSectionTour = hasArg(argc, argv, "--capture-section-tour");
    const bool diagnoseController = hasArg(argc, argv, "--diagnose-controller");
    const bool handlingAudit = hasArg(argc, argv, "--handling-audit");
    const bool raceAudit = hasArg(argc, argv, "--race-audit");
    const bool collisionAudit = hasArg(argc, argv, "--collision-audit");
    const bool perfAudit = hasArg(argc, argv, "--perf-audit");
    const std::filesystem::path launchDir = std::filesystem::current_path();
    const std::filesystem::path captureDir = launchDir / "build" / "playtest_frames";

    SetTraceLogLevel(LOG_ERROR);
    unsigned int configFlags = FLAG_WINDOW_RESIZABLE | FLAG_MSAA_4X_HINT;
    if (!(smokeRender || capturePlaytest || captureDrivenLap || captureSectionTour || perfAudit)) {
        configFlags |= FLAG_VSYNC_HINT;
    }
    SetConfigFlags(configFlags);
    InitWindow(1280, 720, "Shark Harbor Karts 3D");
    SetExitKey(KEY_NULL);
    ChangeDirectory(launchDir.string().c_str());
    SetTargetFPS(120);
    if (!windowed) {
        const int monitor = GetCurrentMonitor();
        SetWindowSize(GetMonitorWidth(monitor), GetMonitorHeight(monitor));
        ToggleFullscreen();
    }

    constexpr SDL_InitFlags kSdlInputFlags = static_cast<SDL_InitFlags>(SDL_INIT_GAMEPAD | SDL_INIT_JOYSTICK);
    const bool sdlInputReady = SDL_InitSubSystem(kSdlInputFlags);
    if (!sdlInputReady) {
        std::cerr << "SDL gamepad fallback unavailable: " << SDL_GetError() << "\n";
    }

    ControllerReader controller(sdlInputReady);
    const bool automatedRun = smokeRender || capturePlaytest || captureDrivenLap || captureSectionTour || handlingAudit || raceAudit ||
                              collisionAudit || perfAudit || diagnoseController;
    Game3D game(!automatedRun);
    bool runtimeCleaned = false;
    const auto cleanupRuntime = [&]() {
        if (runtimeCleaned) {
            return;
        }
        game.shutdown();
        controller.shutdown();
        if (sdlInputReady) {
            SDL_QuitSubSystem(kSdlInputFlags);
        }
        CloseWindow();
        runtimeCleaned = true;
    };
    if (capturePlaytest || captureDrivenLap || captureSectionTour || perfAudit) {
        std::filesystem::create_directories(captureDir);
    }
    if (perfAudit) {
        game.startRace();
    }
    if (handlingAudit) {
        const bool ok = game.runHandlingAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (raceAudit) {
        const bool ok = game.runRaceAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (collisionAudit) {
        const bool ok = game.runCollisionAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (captureSectionTour) {
        static constexpr std::array<float, 9> kTourPhases = {0.035f, 0.135f, 0.245f, 0.355f, 0.465f,
                                                             0.575f, 0.690f, 0.805f, 0.920f};
        for (size_t i = 0; i < kTourPhases.size(); ++i) {
            game.setupSectionTour(kTourPhases[i], static_cast<int>(i));
            game.render(60.0f, true);
            const std::filesystem::path path =
                std::filesystem::path("../playtest_frames") / TextFormat("harbor_karts_3d_section_tour_%02d.png", static_cast<int>(i));
            TakeScreenshot(path.string().c_str());
        }
        cleanupRuntime();
        return 0;
    }
    if (captureDrivenLap) {
        game.startRace();
        const float startScore = game.playerRaceScoreForCapture();
        const float lapLength = game.lapLengthForCapture();
        static constexpr std::array<float, 10> kLapMilestones = {0.03f, 0.12f, 0.22f, 0.32f, 0.42f,
                                                                 0.52f, 0.62f, 0.72f, 0.84f, 0.96f};
        size_t nextCapture = 0;
        int simFrames = 0;
        float distance = 0.0f;
        const int maxFrames = static_cast<int>(170.0f / kFixedDt);
        while ((nextCapture < kLapMilestones.size() || distance < lapLength) && simFrames < maxFrames) {
            const Input3D input = game.scriptedInput();
            game.update(kFixedDt, input, true);
            ++simFrames;
            distance = game.playerRaceScoreForCapture() - startScore;
            if (nextCapture < kLapMilestones.size() && distance >= lapLength * kLapMilestones[nextCapture]) {
                game.render(60.0f, true);
                const std::filesystem::path path = std::filesystem::path("../playtest_frames") /
                                                   TextFormat("harbor_karts_3d_driven_lap_%02d.png",
                                                              static_cast<int>(nextCapture));
                TakeScreenshot(path.string().c_str());
                ++nextCapture;
            }
        }
        cleanupRuntime();
        std::cout << "capture-driven-lap frames=" << simFrames << " captures=" << nextCapture
                  << " distance=" << distance << " lap_length=" << lapLength << "\n";
        return nextCapture == kLapMilestones.size() && distance >= lapLength ? 0 : 1;
    }

    double previous = GetTime();
    double accumulator = 0.0;
    int frames = 0;
    double diagnosticStamp = GetTime();
    std::vector<float> frameTimesMs;
    if (perfAudit) {
        frameTimesMs.reserve(520);
    }

    while (!WindowShouldClose()) {
        const double frameBegin = GetTime();
        const double now = GetTime();
        accumulator += std::min(0.10, now - previous);
        previous = now;

        Input3D input = capturePlaytest ? game.scriptedInput() : readInput(controller, true);
        if (input.quit) {
            break;
        }
        const bool hasController = true;
        while (accumulator >= kFixedDt) {
            game.update(kFixedDt, input, hasController);
            input.a = false;
            input.b = false;
            input.start = false;
            input.back = false;
            input.left = false;
            input.right = false;
            input.up = false;
            input.down = false;
            input.pageLeft = false;
            input.pageRight = false;
            accumulator -= kFixedDt;
        }
        game.render(static_cast<float>(GetFPS()), hasController);

        if (capturePlaytest && frames == 70) {
            const std::filesystem::path path = std::filesystem::path("../playtest_frames") / "harbor_karts_3d_garage.png";
            TakeScreenshot(path.string().c_str());
            game.startRace();
        }
        if (capturePlaytest && (frames == 190 || frames == 360 || frames == 500)) {
            const std::filesystem::path path = std::filesystem::path("../playtest_frames") / TextFormat("harbor_karts_3d_%03d.png", frames);
            TakeScreenshot(path.string().c_str());
        }

        if (diagnoseController && now - diagnosticStamp > 0.25) {
            controller.printSnapshot();
            diagnosticStamp = now;
        }
        if (perfAudit && frames > 30) {
            frameTimesMs.push_back(static_cast<float>((GetTime() - frameBegin) * 1000.0));
        }
        ++frames;
        if ((smokeRender && frames > 180) || (capturePlaytest && frames > 540) || (diagnoseController && frames > 900) ||
            (perfAudit && frames > 520)) {
            break;
        }
    }

    cleanupRuntime();
    if (perfAudit) {
        std::sort(frameTimesMs.begin(), frameTimesMs.end());
        const auto percentile = [&](float p) {
            if (frameTimesMs.empty()) {
                return 0.0f;
            }
            const size_t index = std::min(frameTimesMs.size() - 1, static_cast<size_t>(p * static_cast<float>(frameTimesMs.size() - 1)));
            return frameTimesMs[index];
        };
        const float p50 = percentile(0.50f);
        const float p95 = percentile(0.95f);
        const float maxFrame = frameTimesMs.empty() ? 0.0f : frameTimesMs.back();
        const bool ok = p95 <= 19.2f && maxFrame <= 34.0f;
        std::cout << "perf-audit-3d frames=" << frameTimesMs.size() << " p50_ms=" << p50 << " p95_ms=" << p95 << " max_ms=" << maxFrame
                  << " ok=" << ok << "\n";
        return ok ? 0 : 1;
    }
    return 0;
}
