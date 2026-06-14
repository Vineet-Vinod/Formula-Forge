#include "harbor_karts_3d.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <limits>
#include <random>
#include <string>
#include <string_view>
#include <vector>

#include <raylib.h>
#include <rlgl.h>
#include <SDL3/SDL.h>

#include "core_math.hpp"
#include "track_layout.hpp"

namespace {

constexpr float kFixedDt = 1.0f / 120.0f;
constexpr float kRenderScale = 0.085f;
constexpr int kKartCount = 8;
constexpr int kSampleCount = 1536;

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
    Color road = {206, 122, 67, 255};
    Color shoulder = {239, 199, 111, 255};
    int zone = 0;
};

struct Prop3D {
    enum class Type { Palm, Rock, Hut, Boat, Market, Crane, Crystal, Torch, Gate, Chevron, Cliff, Sail };

    Type type = Type::Palm;
    float progress = 0.0f;
    float side = 0.0f;
    float scale = 1.0f;
    Color color = {60, 159, 91, 255};
};

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
        out.road = mix(a.road, b.road, t);
        out.shoulder = mix(a.shoulder, b.shoulder, t);
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

    int nearestIndexNear(Vec2 pos, int hint, int radius = 42) const {
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
        const float half = std::max(1.0f, point.width * 0.5f);
        const float banked = point.elevation + point.bank * std::clamp(lane / half, -1.2f, 1.2f);
        return toWorld(point.pos + point.normal * lane, banked);
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
        point.width = 178.0f;
        point.road = {212, 130, 67, 255};
        point.shoulder = {245, 202, 105, 255};
        point.zone = 0;

        if (phase < 0.14f) {
            point.zone = 0;
            point.width = 218.0f;
            point.road = {224, 155, 78, 255};
            point.shoulder = {250, 219, 125, 255};
            point.elevation += 2.0f;
        } else if (phase < 0.29f) {
            point.zone = 1;
            point.width = 164.0f;
            point.road = {143, 87, 49, 255};
            point.shoulder = {112, 76, 50, 255};
            point.elevation += 13.0f;
        } else if (phase < 0.42f) {
            point.zone = 2;
            point.width = 188.0f;
            point.road = {198, 98, 76, 255};
            point.shoulder = {238, 175, 81, 255};
            point.elevation += 5.0f;
        } else if (phase < 0.58f) {
            point.zone = 3;
            point.width = 162.0f;
            point.road = {76, 76, 86, 255};
            point.shoulder = {49, 54, 64, 255};
            point.elevation += 32.0f * smoothstep((phase - 0.42f) / 0.16f);
        } else if (phase < 0.72f) {
            point.zone = 4;
            point.width = 182.0f;
            point.road = {128, 136, 96, 255};
            point.shoulder = {68, 142, 88, 255};
            point.elevation += 28.0f * (1.0f - smoothstep((phase - 0.58f) / 0.14f));
        } else if (phase < 0.85f) {
            point.zone = 5;
            point.width = 158.0f;
            point.road = {144, 82, 47, 255};
            point.shoulder = {48, 170, 184, 255};
            point.elevation += 11.0f;
        } else {
            point.zone = 6;
            point.width = 212.0f;
            point.road = {213, 130, 68, 255};
            point.shoulder = {246, 207, 111, 255};
            point.elevation += 4.0f;
        }

        point.elevation += 4.0f * std::sin(phase * kTwoPi * 4.0f);
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
            return Vec2{p.x, p.y};
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
        }

        buildProps();
    }

    void buildProps() {
        std::mt19937 rng(3119);
        std::uniform_real_distribution<float> jitter(-28.0f, 28.0f);
        const int count = 190;
        for (int i = 0; i < count; ++i) {
            const float p = wrapDistance(totalLength_ * (static_cast<float>(i) + 0.23f) / count + jitter(rng), totalLength_);
            const TrackPoint3D tp = sample(p);
            Prop3D prop;
            prop.progress = p;
            const float sideSign = (i % 2 == 0) ? -1.0f : 1.0f;
            prop.side = sideSign * (tp.width * 0.5f + 82.0f + static_cast<float>((i * 17) % 95));
            prop.scale = 0.75f + static_cast<float>((i * 11) % 9) * 0.09f;

            if (tp.zone == 1 || tp.zone == 5) {
                prop.type = (i % 7 == 0) ? Prop3D::Type::Crane : ((i % 4 == 0) ? Prop3D::Type::Boat : Prop3D::Type::Sail);
                prop.color = (i % 4 == 0) ? Color{232, 74, 61, 255} : Color{245, 191, 56, 255};
            } else if (tp.zone == 2) {
                prop.type = (i % 4 == 0) ? Prop3D::Type::Market : ((i % 6 == 0) ? Prop3D::Type::Hut : Prop3D::Type::Palm);
                prop.color = (i % 3 == 0) ? Color{238, 69, 91, 255} : Color{49, 177, 156, 255};
            } else if (tp.zone == 3) {
                prop.type = (i % 3 == 0) ? Prop3D::Type::Crystal : ((i % 2 == 0) ? Prop3D::Type::Torch : Prop3D::Type::Rock);
                prop.color = (i % 3 == 0) ? Color{111, 218, 236, 255} : Color{238, 115, 45, 255};
            } else if (tp.zone == 4 && i % 3 == 0) {
                prop.type = Prop3D::Type::Cliff;
                prop.color = Color{112, 126, 91, 255};
            } else if (i % 13 == 0) {
                prop.type = Prop3D::Type::Chevron;
                prop.color = Color{237, 62, 54, 255};
            } else if (i % 8 == 0) {
                prop.type = Prop3D::Type::Hut;
                prop.color = Color{181, 93, 53, 255};
            } else if (i % 5 == 0) {
                prop.type = Prop3D::Type::Rock;
                prop.color = Color{119, 111, 92, 255};
            } else {
                prop.type = Prop3D::Type::Palm;
                prop.color = Color{48, 156, 86, 255};
            }
            if (prop.type == Prop3D::Type::Chevron) {
                const float outside = std::abs(tp.signedCurvature) > 0.015f ? -std::copysign(1.0f, tp.signedCurvature) : sideSign;
                prop.side = outside * (tp.width * 0.5f + 48.0f);
                prop.scale *= 1.42f;
            } else if (prop.type == Prop3D::Type::Palm || prop.type == Prop3D::Type::Crane || prop.type == Prop3D::Type::Cliff ||
                       prop.type == Prop3D::Type::Crystal) {
                prop.side += sideSign * 46.0f;
            }
            props_.push_back(prop);
        }

        auto addLandmark = [&](float phase, float sideSign, float extra, float scale, Prop3D::Type type, Color color) {
            const float p = wrapDistance(totalLength_ * phase, totalLength_);
            const TrackPoint3D tp = sample(p);
            props_.push_back({type, p, sideSign * (tp.width * 0.5f + extra), scale, color});
        };
        addLandmark(0.004f, 0.0f, 0.0f, 2.4f, Prop3D::Type::Gate, Color{46, 133, 169, 255});
        addLandmark(0.045f, 1.0f, 52.0f, 1.6f, Prop3D::Type::Chevron, Color{238, 62, 54, 255});
        addLandmark(0.160f, -1.0f, 48.0f, 2.1f, Prop3D::Type::Crane, Color{226, 84, 57, 255});
        addLandmark(0.310f, 1.0f, 56.0f, 2.0f, Prop3D::Type::Market, Color{239, 70, 91, 255});
        addLandmark(0.465f, -1.0f, 44.0f, 1.7f, Prop3D::Type::Torch, Color{249, 122, 43, 255});
        addLandmark(0.520f, 1.0f, 46.0f, 2.1f, Prop3D::Type::Crystal, Color{109, 219, 244, 255});
        addLandmark(0.735f, -1.0f, 48.0f, 2.0f, Prop3D::Type::Crane, Color{236, 92, 51, 255});
        addLandmark(0.905f, 1.0f, 74.0f, 2.2f, Prop3D::Type::Hut, Color{177, 92, 51, 255});
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

std::array<KartSpec3D, 8> makeKartSpecs() {
    return {{
        {"TIDE HOPPER", {224, 57, 56, 255}, {255, 202, 63, 255}, {82, 205, 224, 255}, 145.0f, 128.0f, 206.0f, 1.02f, 1.00f, 34.0f, 48.0f, 15.0f, 0},
        {"REEF RUNNER", {35, 151, 211, 255}, {255, 235, 90, 255}, {111, 222, 227, 255}, 149.0f, 118.0f, 202.0f, 0.97f, 1.09f, 32.0f, 51.0f, 14.0f, 1},
        {"DUNE FOX", {240, 139, 45, 255}, {47, 61, 76, 255}, {95, 201, 217, 255}, 140.0f, 139.0f, 214.0f, 1.08f, 0.96f, 38.0f, 46.0f, 16.0f, 2},
        {"PIER SHARK", {61, 81, 103, 255}, {232, 67, 61, 255}, {91, 205, 217, 255}, 153.0f, 108.0f, 197.0f, 0.93f, 1.17f, 33.0f, 55.0f, 13.0f, 3},
        {"MANGO MULE", {246, 199, 62, 255}, {30, 133, 76, 255}, {110, 210, 222, 255}, 136.0f, 150.0f, 222.0f, 1.14f, 0.91f, 41.0f, 44.0f, 18.0f, 4},
        {"LAGOON GT", {34, 184, 143, 255}, {238, 73, 95, 255}, {151, 232, 235, 255}, 150.0f, 123.0f, 204.0f, 1.00f, 1.06f, 32.0f, 52.0f, 14.0f, 5},
        {"TIKI RAIL", {132, 78, 44, 255}, {248, 125, 54, 255}, {98, 196, 210, 255}, 142.0f, 135.0f, 212.0f, 1.05f, 1.03f, 36.0f, 47.0f, 19.0f, 6},
        {"STORM BUGGY", {116, 105, 175, 255}, {255, 213, 65, 255}, {101, 215, 229, 255}, 147.0f, 129.0f, 209.0f, 1.00f, 1.11f, 34.0f, 50.0f, 15.0f, 7},
    }};
}

std::array<std::string, 10> makeRacers() {
    return {"KAI", "MAYA", "BRUNO", "LANI", "REX", "NOVA", "SKIP", "ZARA", "COBALT", "TESS"};
}

Color racerColor(std::string_view racer) {
    static constexpr std::array<Color, 10> palette = {
        Color{255, 211, 80, 255}, Color{238, 78, 91, 255},  Color{71, 185, 131, 255}, Color{76, 151, 224, 255},
        Color{245, 132, 58, 255}, Color{179, 112, 219, 255}, Color{242, 233, 201, 255}, Color{39, 51, 63, 255},
        Color{86, 214, 222, 255}, Color{245, 164, 196, 255},
    };
    uint32_t hash = 2166136261u;
    for (char ch : racer) {
        hash ^= static_cast<uint8_t>(ch);
        hash *= 16777619u;
    }
    return palette[hash % palette.size()];
}

struct Input3D {
    float steer = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
    bool drift = false;
    bool a = false;
    bool b = false;
    bool start = false;
    bool back = false;
    bool left = false;
    bool right = false;
    bool up = false;
    bool down = false;
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

float triggerValue(int gamepad, int axis) {
    const float raw = GetGamepadAxisMovement(gamepad, axis);
    if (raw < -0.2f) {
        return std::clamp((raw + 1.0f) * 0.5f, 0.0f, 1.0f);
    }
    return std::clamp(raw, 0.0f, 1.0f);
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

void applyKeyboardFallback(Input3D& input, bool devKeyboard) {
    if (!devKeyboard) {
        return;
    }
    input.steer = axisWithDeadzone((IsKeyDown(KEY_RIGHT) ? 1.0f : 0.0f) - (IsKeyDown(KEY_LEFT) ? 1.0f : 0.0f));
    input.throttle = IsKeyDown(KEY_UP) ? 1.0f : input.throttle;
    input.brake = IsKeyDown(KEY_DOWN) ? 1.0f : input.brake;
    input.drift = input.drift || IsKeyDown(KEY_RIGHT_SHIFT) || IsKeyDown(KEY_LEFT_SHIFT);
    input.a = input.a || IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_SPACE);
    input.b = input.b || IsKeyPressed(KEY_BACKSPACE);
    input.start = input.start || IsKeyPressed(KEY_P);
    input.back = input.back || IsKeyPressed(KEY_R);
    input.left = input.left || IsKeyPressed(KEY_A);
    input.right = input.right || IsKeyPressed(KEY_D);
    input.up = input.up || IsKeyPressed(KEY_W);
    input.down = input.down || IsKeyPressed(KEY_S);
}

class ControllerReader {
public:
    ~ControllerReader() {
        if (pad_) {
            SDL_CloseGamepad(pad_);
        } else if (joystick_) {
            SDL_CloseJoystick(joystick_);
        }
    }

    bool available() {
        if (IsGamepadAvailable(0)) {
            return true;
        }
        refresh();
        return pad_ != nullptr || joystick_ != nullptr;
    }

    Input3D read(bool devKeyboard) {
        Input3D input = readRaylib();
        refresh();
        mergeSdl(input);
        applyKeyboardFallback(input, devKeyboard);
        return input;
    }

    void printSnapshot() {
        refresh();
        if (IsGamepadAvailable(0)) {
            std::cout << "raylib controller: " << GetGamepadName(0) << " steer=" << GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_X)
                      << " lt=" << triggerValue(0, GAMEPAD_AXIS_LEFT_TRIGGER) << " rt=" << triggerValue(0, GAMEPAD_AXIS_RIGHT_TRIGGER)
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
    static Input3D readRaylib() {
        Input3D input;
        if (IsGamepadAvailable(0)) {
            input.steer = axisWithDeadzone(GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_X));
            input.throttle = triggerValue(0, GAMEPAD_AXIS_RIGHT_TRIGGER);
            input.brake = triggerValue(0, GAMEPAD_AXIS_LEFT_TRIGGER);
            input.drift = IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_TRIGGER_1);
            input.a = IsGamepadButtonPressed(0, GAMEPAD_BUTTON_RIGHT_FACE_DOWN);
            input.b = IsGamepadButtonPressed(0, GAMEPAD_BUTTON_RIGHT_FACE_RIGHT);
            input.start = IsGamepadButtonPressed(0, GAMEPAD_BUTTON_MIDDLE_RIGHT);
            input.back = IsGamepadButtonPressed(0, GAMEPAD_BUTTON_MIDDLE_LEFT);
            input.left = IsGamepadButtonPressed(0, GAMEPAD_BUTTON_LEFT_FACE_LEFT) || input.steer < -0.55f;
            input.right = IsGamepadButtonPressed(0, GAMEPAD_BUTTON_LEFT_FACE_RIGHT) || input.steer > 0.55f;
            input.up = IsGamepadButtonPressed(0, GAMEPAD_BUTTON_LEFT_FACE_UP);
            input.down = IsGamepadButtonPressed(0, GAMEPAD_BUTTON_LEFT_FACE_DOWN);
        }
        return input;
    }

    void refresh() {
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
    }

    void mergeSdl(Input3D& input) {
        if (pad_) {
            input.steer = std::abs(input.steer) > 0.01f ? input.steer : axisWithDeadzone(sdlAxisUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_LEFTX)));
            input.throttle = std::max(input.throttle, sdlTriggerUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)));
            input.brake = std::max(input.brake, sdlTriggerUnit(SDL_GetGamepadAxis(pad_, SDL_GAMEPAD_AXIS_LEFT_TRIGGER)));
            input.drift = input.drift || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER);
            input.a = input.a || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_SOUTH);
            input.b = input.b || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_EAST);
            input.start = input.start || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_START);
            input.back = input.back || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_BACK);
            input.left = input.left || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_LEFT) || input.steer < -0.55f;
            input.right = input.right || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_RIGHT) || input.steer > 0.55f;
            input.up = input.up || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_UP);
            input.down = input.down || SDL_GetGamepadButton(pad_, SDL_GAMEPAD_BUTTON_DPAD_DOWN);
        }
        if (joystick_) {
            input.steer = std::abs(input.steer) > 0.01f ? input.steer : axisWithDeadzone(rawJoystickAxis(joystick_, 0));
            input.throttle = std::max(input.throttle, std::max(0.0f, rawJoystickAxis(joystick_, 5)));
            input.brake = std::max(input.brake, std::max(0.0f, rawJoystickAxis(joystick_, 2)));
            input.drift = input.drift || rawJoystickButton(joystick_, 5);
            input.a = input.a || rawJoystickButton(joystick_, 0);
            input.b = input.b || rawJoystickButton(joystick_, 1);
            input.back = input.back || rawJoystickButton(joystick_, 6);
            input.start = input.start || rawJoystickButton(joystick_, 7);
            input.left = input.left || rawJoystickButton(joystick_, 11) || input.steer < -0.55f;
            input.right = input.right || rawJoystickButton(joystick_, 12) || input.steer > 0.55f;
            input.up = input.up || rawJoystickButton(joystick_, 13);
            input.down = input.down || rawJoystickButton(joystick_, 14);
        }
    }

    SDL_Gamepad* pad_ = nullptr;
    SDL_Joystick* joystick_ = nullptr;
};

Input3D readInput(ControllerReader& controller, bool devKeyboard) {
    return controller.read(devKeyboard);
}

struct Kart3D {
    KartSpec3D spec;
    std::string racer;
    Vec2 pos;
    Vec2 vel;
    float heading = 0.0f;
    float progress = 0.0f;
    float previousProgress = 0.0f;
    int nearest = 0;
    int lap = 0;
    float lane = 0.0f;
    float steerSmoothed = 0.0f;
    float driftDir = 1.0f;
    bool drifting = false;
    float driftCharge = 0.0f;
    float boostTimer = 0.0f;
    float boostPower = 0.0f;
    float brakeHold = 0.0f;
    float contactTimer = 0.0f;
    float aiTempo = 1.0f;
    float aiRisk = 0.4f;
    float aiPass = 1.0f;
    float aiLaneIntent = 0.0f;
    float aiIntentTimer = 0.0f;
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
    int progressJumps = 0;
    int contacts = 0;
    int offroadFrames = 0;
    int boostFrames = 0;
    int driftFrames = 0;
    int lap = 0;
};

struct RaceAuditResult3D {
    float playerScore = 0.0f;
    float topAiScore = 0.0f;
    float tailAiScore = 0.0f;
    float spread = 0.0f;
    int overtakes = 0;
    int contacts = 0;
    int progressJumps = 0;
    int playerBest = kKartCount;
    int playerWorst = 1;
    int playerFinal = kKartCount;
};

void drawQuad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Color color) {
    DrawTriangle3D(a, b, c, color);
    DrawTriangle3D(a, c, d, color);
}

void drawLocalBox(Vector3 pos, Vector3 size, Color color) {
    DrawCubeV(pos, size, color);
}

void drawLocalWheel(float x, float z, float radius, float width, Color tire, Color hub) {
    DrawCylinderEx({x - width * 0.5f, radius, z}, {x + width * 0.5f, radius, z}, radius, radius, 14, tire);
    DrawCylinderEx({x - width * 0.52f, radius, z}, {x + width * 0.52f, radius, z}, radius * 0.42f, radius * 0.42f, 10, hub);
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

class Game3D {
public:
    enum class Mode { Garage, Race, Pause };

    Game3D() : specs_(makeKartSpecs()), racers_(makeRacers()) { resetRace(); }

    void update(float dt, const Input3D& input, bool hasController) {
        if (mode_ == Mode::Garage) {
            updateGarage(input, hasController);
            updateGarageCamera(dt);
            return;
        }

        if (input.start) {
            mode_ = mode_ == Mode::Race ? Mode::Pause : Mode::Race;
        }
        if (mode_ == Mode::Pause) {
            if (input.b) {
                mode_ = Mode::Garage;
            }
            return;
        }

        raceTime_ += dt;
        if (input.back) {
            resetPlayerToTrack();
        }

        updatePlayer(karts_[0], input, dt);
        for (int i = 1; i < kKartCount; ++i) {
            updateAi(karts_[static_cast<size_t>(i)], dt, i);
        }
        solveKartContacts();
        updateParticles(dt);
        updateRaceOrder();
        updateCamera(dt);
    }

    void render(float fps, bool hasController) {
        BeginDrawing();
        ClearBackground(Color{91, 196, 232, 255});
        drawSkyGradient();
        BeginMode3D(camera_);
        rlDisableBackfaceCulling();
        drawEnvironment();
        drawTrack();
        drawProps();
        drawParticles();
        drawKarts();
        rlEnableBackfaceCulling();
        EndMode3D();
        drawHud(fps, hasController);
        EndDrawing();
    }

    void startRace() {
        resetRace();
        mode_ = Mode::Race;
    }

    Input3D scriptedInput() const {
        const Kart3D& player = karts_[0];
        const float speed = length(player.vel);
        const TrackPoint3D future = track_.sample(player.progress + 95.0f + speed * 0.82f);
        Input3D input;
        input.steer = aiSteerForProgress(player, 0, 0.0f);
        input.throttle = 1.0f;
        input.brake = speed > player.spec.maxSpeed * std::clamp(1.03f - future.curvature * 2.3f, 0.70f, 1.04f) ? 0.38f : 0.0f;
        input.drift = future.curvature > 0.060f && speed > 48.0f && std::abs(input.steer) > 0.10f;
        return input;
    }

    Mode mode() const { return mode_; }

    bool runHandlingAudit() {
        const AuditResult3D noBrake = simulateAuditDriver(AuditDriver::NoBrake, 64.0f);
        const AuditResult3D brake = simulateAuditDriver(AuditDriver::Brake, 64.0f);
        const AuditResult3D drift = simulateAuditDriver(AuditDriver::Drift, 64.0f);
        const bool skillOrder = drift.score > brake.score * 1.015f && brake.score > noBrake.score * 1.025f;
        const bool consequences = noBrake.contacts >= 2 || noBrake.offroadFrames > 120 || noBrake.maxOffroad > 18.0f;
        const bool driftReward = drift.boostFrames > 90 && drift.driftFrames > 120 && drift.contacts <= noBrake.contacts + 1;
        const bool ok = skillOrder && consequences && driftReward;

        auto print = [](const AuditResult3D& r) {
            std::cout << r.name << "_score=" << r.score << " lap=" << r.lap << " avg=" << r.averageSpeed << " max=" << r.maxSpeed
                      << " contacts=" << r.contacts << " offroad_frames=" << r.offroadFrames << " max_offroad=" << r.maxOffroad
                      << " progress_jumps=" << r.progressJumps << " drift_frames=" << r.driftFrames << " boost_frames=" << r.boostFrames
                      << " ";
        };
        std::cout << "handling-audit ";
        print(noBrake);
        print(brake);
        print(drift);
        std::cout << "skill_order=" << skillOrder << " consequences=" << consequences << " drift_reward=" << driftReward << "\n";
        return ok;
    }

    bool runRaceAudit() {
        startRace();
        RaceAuditResult3D result;
        std::array<float, kKartCount> previousScores{};
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

            std::array<std::pair<float, int>, kKartCount> order{};
            for (int i = 0; i < kKartCount; ++i) {
                const Kart3D& kart = karts_[static_cast<size_t>(i)];
                const float progressDelta = signedDistanceToLoop(beforeProgress[static_cast<size_t>(i)], kart.progress, track_.totalLength());
                if (i == 0 && (progressDelta < -40.0f || progressDelta > 90.0f)) {
                    ++result.progressJumps;
                }
                if (beforeContact[static_cast<size_t>(i)] <= 0.001f && kart.contactTimer > 0.05f) {
                    ++result.contacts;
                }
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

        const bool stable = result.progressJumps == 0;
        const bool pressure = result.topAiScore > result.playerScore - 520.0f && result.playerScore > result.tailAiScore - 520.0f;
        const bool activePack = result.overtakes >= 5 && result.playerBest < result.playerWorst;
        const bool tailRecovered = result.tailAiScore > result.playerScore - 2600.0f && result.spread < 3600.0f;
        const bool cleanEnough = result.contacts < 150;
        const bool ok = stable && pressure && activePack && tailRecovered && cleanEnough;

        std::cout << "race-audit-3d player=" << result.playerScore << " top_ai=" << result.topAiScore << " tail_ai=" << result.tailAiScore
                  << " spread=" << result.spread << " overtakes=" << result.overtakes << " contacts=" << result.contacts
                  << " progress_jumps=" << result.progressJumps << " player_pos=" << result.playerFinal << " best=" << result.playerBest
                  << " worst=" << result.playerWorst << " stable=" << stable << " pressure=" << pressure << " active_pack=" << activePack
                  << " tail_recovered=" << tailRecovered << " clean=" << cleanEnough << "\n";
        return ok;
    }

private:
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
        if ((input.a || input.start) && hasController) {
            startRace();
        }
    }

    void updateGarageCamera(float dt) {
        (void)dt;
        const TrackPoint3D start = track_.sample(0.0f);
        const Vector3 focus = track_.roadPoint(start, 0.0f);
        camera_.position = add(focus, {0.0f, 8.0f, -18.0f});
        camera_.target = add(focus, {0.0f, 2.2f, 0.0f});
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = 56.0f;
        camera_.projection = CAMERA_PERSPECTIVE;
    }

    void resetRace() {
        karts_.clear();
        const TrackPoint3D start = track_.sample(0.0f);
        for (int i = 0; i < kKartCount; ++i) {
            Kart3D kart;
            kart.spec = specs_[static_cast<size_t>(i == 0 ? selectedCar_ : i % static_cast<int>(specs_.size()))];
            kart.racer = racers_[static_cast<size_t>(i == 0 ? selectedRacer_ : (i * 3) % static_cast<int>(racers_.size()))];
            const float stagger = i == 0 ? 0.0f : 48.0f + static_cast<float>((i - 1) / 2) * 54.0f;
            const float lane = i == 0 ? 0.0f : ((i % 2 == 0 ? -1.0f : 1.0f) * (18.0f + static_cast<float>((i - 1) / 2) * 5.0f));
            const TrackPoint3D grid = track_.sample(stagger);
            kart.pos = grid.pos + grid.normal * lane;
            kart.heading = angleOf(grid.tangent);
            kart.vel = grid.tangent * (i == 0 ? 0.0f : 22.0f);
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.progress = track_.pointAtIndex(kart.nearest).progress;
            kart.previousProgress = kart.progress;
            kart.aiTempo = 1.05f - static_cast<float>(i) * 0.006f;
            kart.aiRisk = 0.25f + static_cast<float>((i * 7) % 9) * 0.055f;
            kart.aiPass = (i % 2 == 0) ? -1.0f : 1.0f;
            karts_.push_back(kart);
        }
        particles_.clear();
        raceTime_ = 0.0f;
        playerPosition_ = 1;
        updateRaceOrder();
        const Vector3 focus = track_.roadPoint(start, 0.0f);
        camera_.position = add(focus, {0.0f, 5.0f, -16.0f});
        camera_.target = focus;
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = 60.0f;
        camera_.projection = CAMERA_PERSPECTIVE;
    }

    void updateProgress(Kart3D& kart) {
        kart.nearest = track_.nearestIndexNear(kart.pos, kart.nearest);
        const TrackPoint3D& center = track_.pointAtIndex(kart.nearest);
        kart.previousProgress = kart.progress;
        kart.progress = center.progress;
        kart.lane = dot(kart.pos - center.pos, center.normal);
        const float delta = signedDistanceToLoop(kart.previousProgress, kart.progress, track_.totalLength());
        if (delta < -track_.totalLength() * 0.35f) {
            ++kart.lap;
        } else if (delta > track_.totalLength() * 0.35f && kart.lap > 0) {
            --kart.lap;
        }
    }

    void updatePlayer(Kart3D& kart, const Input3D& input, float dt) { integrateKart(kart, input, dt, true); }

    float raceScore(const Kart3D& kart) const { return static_cast<float>(kart.lap) * track_.totalLength() + kart.progress; }

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
        if (raceTime_ > 8.0f && kart.lap == 0 && kart.progress < 140.0f && speed < 34.0f) {
            const TrackPoint3D recovery = track_.sample(260.0f + static_cast<float>(index) * 28.0f);
            const float lane = (index % 2 == 0 ? -1.0f : 1.0f) * 18.0f;
            kart.pos = recovery.pos + recovery.normal * lane;
            kart.heading = angleOf(recovery.tangent);
            kart.vel = recovery.tangent * 72.0f;
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.progress = track_.pointAtIndex(kart.nearest).progress;
            kart.previousProgress = kart.progress;
            kart.lane = lane;
            kart.drifting = false;
            kart.contactTimer = 0.0f;
            center = track_.sample(kart.progress);
            speed = length(kart.vel);
        }
        const float lookahead = 78.0f + speed * (0.70f + kart.aiRisk * 0.18f);
        const TrackPoint3D future = track_.sample(kart.progress + lookahead);
        const TrackPoint3D apex = track_.sample(kart.progress + 135.0f + speed * 0.52f);

        kart.aiIntentTimer -= dt;
        if (kart.aiIntentTimer <= 0.0f) {
            kart.aiIntentTimer = 1.15f + 0.17f * static_cast<float>((index * 5) % 6);
            kart.aiLaneIntent = kart.aiPass * (18.0f + 13.0f * std::sin(raceTime_ * 0.7f + static_cast<float>(index)));
            kart.aiPass *= -1.0f;
        }

        float laneTarget = kart.aiLaneIntent - std::copysign(28.0f, apex.signedCurvature) * std::clamp(apex.curvature * 4.0f, 0.0f, 1.0f);
        for (int i = 0; i < kKartCount; ++i) {
            if (i == index) {
                continue;
            }
            const Kart3D& other = karts_[static_cast<size_t>(i)];
            const float ahead = progressAhead(kart.progress, other.progress, track_.totalLength());
            if (ahead > 8.0f && ahead < 145.0f && std::abs(other.lane - laneTarget) < 24.0f) {
                laneTarget += kart.aiPass * (34.0f - ahead * 0.12f);
            }
        }
        const float half = future.width * 0.5f - 26.0f;
        laneTarget = std::clamp(laneTarget, -half, half);

        const Vec2 targetPos = future.pos + future.normal * laneTarget;
        const Vec2 forward = fromAngle(kart.heading);
        const Vec2 toTarget = normalize(targetPos - kart.pos);
        const float angleError = std::atan2(cross(forward, toTarget), dot(forward, toTarget));
        const float futureCorner = std::max(center.curvature, std::max(future.curvature, apex.curvature));
        float leaderScore = raceScore(karts_[0]);
        for (const Kart3D& other : karts_) {
            leaderScore = std::max(leaderScore, raceScore(other));
        }
        const float leaderGap = leaderScore - raceScore(kart);
        const float catchup = std::clamp((leaderGap - 700.0f) / 2000.0f, 0.0f, 0.10f);
        const float targetSpeed = kart.spec.maxSpeed * (kart.aiTempo + catchup) * std::clamp(1.07f - futureCorner * 2.05f, 0.76f, 1.10f);

        Input3D ai;
        ai.steer = std::clamp(angleError * (1.92f + kart.aiRisk * 0.36f), -1.0f, 1.0f);
        ai.throttle = speed < targetSpeed + 6.0f ? 1.0f : 0.55f;
        ai.brake = speed > targetSpeed + 20.0f ? 0.35f : 0.0f;
        ai.drift = futureCorner > 0.065f && speed > 48.0f && std::abs(angleError) > 0.055f;
        if (ai.drift) {
            ai.throttle = 1.0f;
            ai.brake = 0.0f;
        }
        integrateKart(kart, ai, dt, false);
    }

    Input3D auditInput(AuditDriver driver, const Kart3D& kart) const {
        const float speed = length(kart.vel);
        const TrackPoint3D future = track_.sample(kart.progress + 95.0f + speed * 0.88f);
        const TrackPoint3D apex = track_.sample(kart.progress + 155.0f + speed * 0.58f);
        const float corner = std::max(future.curvature, apex.curvature);
        const float turnSign = apex.signedCurvature == 0.0f ? future.signedCurvature : apex.signedCurvature;
        float laneTarget = 0.0f;
        if (driver == AuditDriver::Drift) {
            laneTarget = -std::copysign(8.0f, turnSign) * std::clamp(corner * 3.0f, 0.0f, 1.0f);
        }

        Input3D input;
        input.steer = aiSteerForProgress(kart, 0, laneTarget);
        input.throttle = 1.0f;

        const float targetSpeed = kart.spec.maxSpeed * std::clamp(1.08f - corner * 2.95f, 0.60f, 1.08f);
        if (driver == AuditDriver::Brake || driver == AuditDriver::Drift) {
            const bool needsBrake = speed > targetSpeed + (driver == AuditDriver::Drift ? 16.0f : 7.0f);
            if (needsBrake) {
                input.brake = std::clamp((speed - targetSpeed) / 42.0f, driver == AuditDriver::Drift ? 0.18f : 0.30f, 0.82f);
                input.throttle = driver == AuditDriver::Drift ? 0.92f : 0.65f;
            }
        }
        if (driver == AuditDriver::Drift) {
            const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
            const bool nearEdge = std::abs(kart.lane) > center.width * 0.5f - 26.0f;
            const bool signChange = kart.drifting && std::abs(input.steer) > 0.10f && input.steer * kart.driftDir < -0.05f;
            const bool releaseForExit = kart.drifting && (kart.driftCharge >= 0.52f || future.curvature < 0.060f || nearEdge || signChange);
            const bool entryDemand = kart.boostTimer <= 0.04f && !nearEdge && corner > 0.055f && speed > 46.0f && std::abs(input.steer) > 0.075f;
            input.drift = kart.drifting ? !releaseForExit : entryDemand;
            if (input.drift) {
                input.throttle = 1.0f;
                input.brake = 0.0f;
            }
        }
        return input;
    }

    AuditResult3D simulateAuditDriver(AuditDriver driver, float seconds) {
        particles_.clear();
        const TrackPoint3D start = track_.sample(0.0f);
        Kart3D kart;
        kart.spec = specs_[0];
        kart.racer = racers_[0];
        kart.pos = start.pos;
        kart.heading = angleOf(start.tangent);
        kart.vel = {};
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.progress = track_.pointAtIndex(kart.nearest).progress;
        kart.previousProgress = kart.progress;

        AuditResult3D result;
        result.name = driver == AuditDriver::NoBrake ? "no_brake" : (driver == AuditDriver::Brake ? "brake" : "drift");

        const int frames = static_cast<int>(seconds / kFixedDt);
        float speedSum = 0.0f;
        float cumulativeProgress = 0.0f;
        for (int frame = 0; frame < frames; ++frame) {
            const float beforeContact = kart.contactTimer;
            const float beforeProgress = kart.progress;
            const Input3D input = auditInput(driver, kart);
            integrateKart(kart, input, kFixedDt, true);
            const float progressDelta = signedDistanceToLoop(beforeProgress, kart.progress, track_.totalLength());
            if (progressDelta < -40.0f || progressDelta > 90.0f) {
                ++result.progressJumps;
            } else {
                cumulativeProgress += progressDelta;
            }
            const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
            const float offroad = std::max(0.0f, std::abs(kart.lane) - center.width * 0.5f);
            const float speed = std::max(0.0f, dot(kart.vel, fromAngle(kart.heading)));
            speedSum += speed;
            result.maxSpeed = std::max(result.maxSpeed, speed);
            result.maxOffroad = std::max(result.maxOffroad, offroad);
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
        laneTarget -= std::copysign(22.0f, future.signedCurvature) * std::clamp(future.curvature * 4.2f, 0.0f, 1.0f);
        const Vec2 desired = future.pos + future.normal * laneTarget;
        const Vec2 forward = fromAngle(kart.heading);
        const Vec2 toTarget = normalize(desired - kart.pos);
        return std::clamp(std::atan2(cross(forward, toTarget), dot(forward, toTarget)) * 1.95f, -1.0f, 1.0f);
    }

    void integrateKart(Kart3D& kart, const Input3D& rawInput, float dt, bool player) {
        updateProgress(kart);
        const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
        const float halfWidth = center.width * 0.5f;
        const float shoulder = 42.0f;
        const float offroad = std::max(0.0f, std::abs(kart.lane) - halfWidth);
        const float surfaceGrip = std::clamp(1.0f - offroad / shoulder, 0.24f, 1.0f);
        const float surfaceDrag = 1.0f + offroad * 0.130f;

        Input3D input = rawInput;
        kart.steerSmoothed = lerp(kart.steerSmoothed, input.steer, 1.0f - std::exp(-dt / 0.042f));
        input.steer = kart.steerSmoothed;

        Vec2 forward = fromAngle(kart.heading);
        Vec2 right{-forward.y, forward.x};
        float speed = dot(kart.vel, forward);
        float sideSpeed = dot(kart.vel, right);
        const float absSpeed = std::abs(speed);

        kart.contactTimer = std::max(0.0f, kart.contactTimer - dt);
        kart.brakeHold = input.brake > 0.5f ? kart.brakeHold + dt : 0.0f;

        const bool driftEntry = input.drift && !kart.drifting && std::abs(input.steer) > 0.22f && absSpeed > 42.0f;
        if (driftEntry) {
            kart.drifting = true;
            kart.driftDir = input.steer < 0.0f ? -1.0f : 1.0f;
            kart.driftCharge = 0.0f;
        }
        if (kart.drifting && (!input.drift || absSpeed < 30.0f)) {
            if (!input.drift && kart.driftCharge >= 0.35f && absSpeed > 38.0f) {
                if (kart.driftCharge >= 1.05f) {
                    kart.boostTimer = 1.22f;
                    kart.boostPower = 1.0f;
                } else if (kart.driftCharge >= 0.50f) {
                    kart.boostTimer = 1.04f;
                    kart.boostPower = 0.62f;
                } else {
                    kart.boostTimer = 0.68f;
                    kart.boostPower = 0.36f;
                }
            }
            kart.drifting = false;
            kart.driftCharge = 0.0f;
        }

        if (input.throttle > 0.01f) {
            const float max = kart.spec.maxSpeed * (kart.boostTimer > 0.0f ? (1.12f + 0.20f * kart.boostPower) : 1.0f);
            const float falloff = std::clamp(1.13f - std::abs(speed) / max, 0.14f, 1.0f);
            speed += input.throttle * kart.spec.accel * falloff * surfaceGrip * dt;
        }

        if (input.brake > 0.01f) {
            if (speed > 7.0f) {
                speed -= input.brake * kart.spec.brake * (kart.drifting ? 0.15f : 1.0f) * dt;
            } else if (kart.brakeHold > 0.25f) {
                speed -= input.brake * 58.0f * dt;
            }
        }

        const float highSpeed = std::clamp((std::abs(speed) - 48.0f) / 86.0f, 0.0f, 1.0f);
        const float steerAbs = std::abs(input.steer);
        const float gripBudget = (player ? 1.0f : 1.07f) * surfaceGrip * kart.spec.grip;
        const float curveDemand = center.curvature * highSpeed * highSpeed * (9.4f + std::abs(speed) * 0.022f);
        const float lateralDemand = steerAbs * highSpeed * (1.25f + std::abs(speed) / 150.0f) + curveDemand;
        const float overflow = std::clamp((lateralDemand - gripBudget * 0.62f) / 0.82f, 0.0f, 1.0f);

        if (kart.boostTimer > 0.0f && input.throttle > 0.1f && speed > 5.0f) {
            speed += (180.0f + 68.0f * kart.boostPower) * std::clamp(1.0f - speed / (kart.spec.maxSpeed * 1.32f), 0.24f, 1.0f) * dt;
            kart.boostTimer = std::max(0.0f, kart.boostTimer - dt);
        } else {
            kart.boostTimer = std::max(0.0f, kart.boostTimer - dt);
        }

        float yawRate = input.steer * lerp(3.55f, 1.62f, std::clamp(std::abs(speed) / 150.0f, 0.0f, 1.0f)) * surfaceGrip * kart.spec.grip;
        if (kart.drifting) {
            yawRate = (kart.driftDir * 0.66f + input.steer * 0.34f) * 4.24f * kart.spec.drift * surfaceGrip;
            const float targetSlip = kart.driftDir * (8.5f + 4.5f * std::clamp(std::abs(speed) / 135.0f, 0.0f, 1.0f));
            sideSpeed = lerp(sideSpeed, targetSlip, 1.0f - std::exp(-dt * 2.4f));
            speed += input.throttle * 46.0f * dt;
            speed *= std::exp(-dt * 0.009f);
            const float slipQuality = std::clamp(1.0f - std::abs(std::abs(sideSpeed) - 12.0f) / 18.0f, 0.62f, 1.0f);
            kart.driftCharge = std::min(1.25f, kart.driftCharge + dt * (2.25f + steerAbs * 1.85f) * slipQuality);
        } else {
            yawRate *= (1.0f - overflow * 0.68f);
            const float trailRotation = input.brake * steerAbs * highSpeed * 0.42f;
            yawRate *= 1.0f + trailRotation;
            sideSpeed += input.steer * std::abs(speed) * highSpeed * (0.38f + overflow * 0.85f) * dt;
            if (std::abs(center.signedCurvature) > 0.004f && speed > 35.0f) {
                const float outside = -std::copysign(1.0f, center.signedCurvature);
                sideSpeed += outside * std::abs(speed) * (0.32f + overflow * 1.15f) * curveDemand * dt;
            }
            sideSpeed *= std::exp(-dt * (3.25f + 2.3f * surfaceGrip - overflow * 1.65f));
            kart.driftCharge = std::max(0.0f, kart.driftCharge - dt * 2.4f);
        }

        speed -= speed * std::abs(speed) * 0.00155f * surfaceDrag * dt;
        if (offroad > 1.0f) {
            speed -= speed * offroad * 0.095f * dt;
            sideSpeed -= sideSpeed * offroad * 0.078f * dt;
        }
        const float speedCap = kart.spec.maxSpeed * (kart.boostTimer > 0.0f ? (1.12f + 0.20f * kart.boostPower) : 1.0f) *
                               (offroad > 2.0f ? 0.58f : 1.0f);
        speed = std::clamp(speed, -42.0f, speedCap);

        kart.heading = wrapAngle(kart.heading + yawRate * (speed >= -1.0f ? 1.0f : -0.55f) * dt);
        forward = fromAngle(kart.heading);
        right = {-forward.y, forward.x};
        kart.vel = forward * speed + right * sideSpeed;
        kart.pos += kart.vel * dt;
        emitFx(kart, center, offroad, dt);
        constrainToTrack(kart);
        updateProgress(kart);
    }

    void constrainToTrack(Kart3D& kart) {
        const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
        const float lane = dot(kart.pos - center.pos, center.normal);
        const float hardLimit = center.width * 0.5f + 54.0f;
        if (std::abs(lane) <= hardLimit) {
            return;
        }
        const float sign = lane > 0.0f ? 1.0f : -1.0f;
        const float excess = std::abs(lane) - hardLimit;
        kart.pos -= center.normal * (sign * excess);
        const float normalVelocity = dot(kart.vel, center.normal);
        if (normalVelocity * sign > 0.0f) {
            kart.vel -= center.normal * (normalVelocity * 1.24f);
            kart.vel *= 0.62f;
        } else {
            kart.vel *= 0.84f;
        }
        kart.drifting = false;
        kart.contactTimer = 0.28f;
    }

    void solveKartContacts() {
        for (int a = 0; a < kKartCount; ++a) {
            for (int b = a + 1; b < kKartCount; ++b) {
                Kart3D& ka = karts_[static_cast<size_t>(a)];
                Kart3D& kb = karts_[static_cast<size_t>(b)];
                const Vec2 delta = kb.pos - ka.pos;
                const float minDist = (ka.spec.width + kb.spec.width) * 0.46f;
                const float d2 = lengthSq(delta);
                if (d2 < minDist * minDist && d2 > 0.0001f) {
                    const float d = std::sqrt(d2);
                    const Vec2 n = delta / d;
                    const float push = (minDist - d) * 0.52f;
                    ka.pos -= n * push;
                    kb.pos += n * push;
                    const float va = dot(ka.vel, n);
                    const float vb = dot(kb.vel, n);
                    const float rel = va - vb;
                    if (rel > 0.0f) {
                        const float impulse = rel * 0.38f;
                        ka.vel -= n * impulse;
                        kb.vel += n * impulse;
                    }
                    ka.vel *= 0.985f;
                    kb.vel *= 0.985f;
                    ka.contactTimer = 0.22f;
                    kb.contactTimer = 0.22f;
                }
            }
        }
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
        if (kart.boostTimer > 0.0f) {
            emitParticle(rear, baseVel - forward * 36.0f, center.elevation + 4.0f, 0.20f, 4.8f, Color{255, 181, 45, 210});
            emitParticle(rear - Vec2{-forward.y, forward.x} * 8.0f, baseVel - forward * 24.0f, center.elevation + 3.0f, 0.18f, 3.8f,
                         Color{244, 67, 43, 205});
        } else if (kart.drifting) {
            emitParticle(rear, baseVel, center.elevation + 2.5f, 0.46f, 5.5f, Color{226, 232, 219, 185});
        } else if (offroad > 2.0f && length(kart.vel) > 28.0f) {
            emitParticle(rear, baseVel, center.elevation + 2.0f, 0.38f, 5.0f, Color{225, 188, 99, 180});
        } else if (kart.contactTimer > 0.14f) {
            emitParticle(kart.pos, baseVel, center.elevation + 5.0f, 0.22f, 4.5f, Color{245, 231, 165, 210});
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
        const TrackPoint3D tp = track_.sample(kart.progress);
        kart.pos = tp.pos;
        kart.heading = angleOf(tp.tangent);
        kart.vel = tp.tangent * 34.0f;
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.drifting = false;
        kart.boostTimer = 0.0f;
        kart.boostPower = 0.0f;
        kart.driftCharge = 0.0f;
        kart.contactTimer = 0.0f;
    }

    void updateRaceOrder() {
        std::array<std::pair<float, int>, kKartCount> order;
        for (int i = 0; i < kKartCount; ++i) {
            const Kart3D& kart = karts_[static_cast<size_t>(i)];
            order[static_cast<size_t>(i)] = {static_cast<float>(kart.lap) * track_.totalLength() + kart.progress, i};
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
        const TrackPoint3D future = track_.sample(player.progress + 110.0f + length(player.vel) * 1.22f);
        const Vec2 apexDir = normalize((future.pos + future.normal * std::clamp(player.lane * 0.3f, -20.0f, 20.0f)) - player.pos);
        const Vec2 blended = normalize(lerp(forward2, apexDir, std::clamp(0.27f + future.curvature * 3.0f, 0.27f, 0.57f)));
        const float speed = length(player.vel);
        const float back = lerp(88.0f, 222.0f, std::clamp(speed / 150.0f, 0.0f, 1.0f));
        const float height = lerp(72.0f, 126.0f, std::clamp(speed / 150.0f, 0.0f, 1.0f));
        const TrackPoint3D ground = track_.sample(player.progress);
        const Vector3 focus = toWorld(player.pos, ground.elevation + 12.0f);
        const Vector3 desiredPos = toWorld(player.pos - blended * back, ground.elevation + height);
        const Vector3 desiredTarget = toWorld(player.pos + blended * (46.0f + speed * 0.31f), ground.elevation + 16.0f);
        const float blend = 1.0f - std::exp(-dt * 6.4f);
        camera_.position = add(camera_.position, mul(sub(desiredPos, camera_.position), blend));
        camera_.target = add(camera_.target, mul(sub(desiredTarget, camera_.target), blend));
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = lerp(58.0f, 68.0f, std::clamp(speed / 155.0f, 0.0f, 1.0f));
        camera_.projection = CAMERA_PERSPECTIVE;
        (void)focus;
    }

    void drawEnvironment() {
        DrawPlane({0.0f, -0.30f, 0.0f}, {260.0f, 230.0f}, Color{41, 183, 196, 255});
        DrawPlane({0.0f, -0.20f, 0.0f}, {185.0f, 175.0f}, Color{246, 212, 132, 255});
        DrawPlane({-36.0f, -0.16f, 10.0f}, {65.0f, 62.0f}, Color{77, 161, 92, 255});
        DrawPlane({52.0f, -0.15f, -38.0f}, {78.0f, 58.0f}, Color{88, 172, 98, 255});

        for (int i = 0; i < 22; ++i) {
            const float x = -106.0f + static_cast<float>((i * 37) % 220);
            const float z = -88.0f + static_cast<float>((i * 53) % 178);
            DrawCubeV({x, 0.02f, z}, {9.0f + static_cast<float>(i % 4) * 2.0f, 0.05f, 0.28f}, Color{240, 249, 229, 160});
        }

        DrawSphere({-92.0f, 58.0f, -72.0f}, 9.0f, Color{255, 219, 90, 255});
        for (int i = 0; i < 6; ++i) {
            DrawCubeV({-76.0f + static_cast<float>(i) * 25.0f, 45.0f + std::sin(static_cast<float>(i)) * 5.0f, -82.0f},
                      {13.0f, 2.4f, 3.0f}, Color{236, 252, 255, 205});
        }
    }

    void drawTrack() {
        const auto& samples = track_.samples();
        constexpr int stride = 3;
        for (int i = 0; i < track_.sampleCount(); i += stride) {
            const TrackPoint3D& a = samples[static_cast<size_t>(i)];
            const TrackPoint3D& b = samples[static_cast<size_t>((i + stride) % track_.sampleCount())];
            const float shoulderA = a.width * 0.5f + 32.0f;
            const float shoulderB = b.width * 0.5f + 32.0f;
            const Color shoulder = shade(mix(a.shoulder, b.shoulder, 0.5f), (i / stride) % 2 == 0 ? 1.0f : 0.95f);

            const float halfA = a.width * 0.5f;
            const float halfB = b.width * 0.5f;
            drawQuad(track_.roadPoint(a, -shoulderA), track_.roadPoint(b, -shoulderB), track_.roadPoint(b, -halfB),
                     track_.roadPoint(a, -halfA), shoulder);
            drawQuad(track_.roadPoint(a, halfA), track_.roadPoint(b, halfB), track_.roadPoint(b, shoulderB), track_.roadPoint(a, shoulderA),
                     shoulder);

            const Color road = shade(mix(a.road, b.road, 0.5f), (i / stride) % 2 == 0 ? 1.05f : 0.96f);
            drawQuad(lift(track_.roadPoint(a, -halfA), 0.028f), lift(track_.roadPoint(b, -halfB), 0.028f),
                     lift(track_.roadPoint(b, halfB), 0.028f), lift(track_.roadPoint(a, halfA), 0.028f), road);

            const Color lip = a.zone == 3 ? Color{23, 30, 39, 255} : Color{74, 59, 45, 255};
            const float lipWidth = 4.8f;
            drawQuad(lift(track_.roadPoint(a, -halfA - lipWidth), 0.052f), lift(track_.roadPoint(b, -halfB - lipWidth), 0.052f),
                     lift(track_.roadPoint(b, -halfB), 0.052f), lift(track_.roadPoint(a, -halfA), 0.052f), lip);
            drawQuad(lift(track_.roadPoint(a, halfA), 0.052f), lift(track_.roadPoint(b, halfB), 0.052f),
                     lift(track_.roadPoint(b, halfB + lipWidth), 0.052f), lift(track_.roadPoint(a, halfA + lipWidth), 0.052f), lip);

            if ((a.zone == 1 || a.zone == 5) && (i / stride) % 5 == 0) {
                const Color plank = shade(road, 0.72f);
                drawQuad(lift(track_.roadPoint(a, -halfA + 7.0f), 0.062f), lift(track_.roadPoint(b, -halfB + 7.0f), 0.062f),
                         lift(track_.roadPoint(b, halfB - 7.0f), 0.062f), lift(track_.roadPoint(a, halfA - 7.0f), 0.062f),
                         plank);
            }
        }

        for (int i = 0; i < track_.sampleCount(); i += 10) {
            const TrackPoint3D& p = samples[static_cast<size_t>(i)];
            const bool curveMarker = p.curvature > 0.030f || p.zone == 1 || p.zone == 5;
            if (!curveMarker && i % 20 != 0) {
                continue;
            }
            for (float side : {-1.0f, 1.0f}) {
                const float lane = side * (p.width * 0.5f + 3.5f);
                const Vector3 pos = lift(track_.roadPoint(p, lane), 0.09f);
                rlPushMatrix();
                rlTranslatef(pos.x, pos.y + 0.16f, pos.z);
                rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
                const Color curb = (i / 10) % 2 == 0 ? Color{255, 232, 83, 255} : Color{255, 255, 236, 255};
                DrawCubeV({0.0f, 0.0f, 0.0f}, {0.44f, 0.22f, curveMarker ? 1.55f : 1.15f}, curb);
                rlPopMatrix();
            }
        }

        const bool showGate = mode_ == Mode::Garage || karts_.empty() || (karts_[0].lap == 0 && karts_[0].progress < 34.0f);
        if (showGate) {
            const TrackPoint3D start = track_.sample(0.0f);
            const Vector3 gate = track_.roadPoint(start, 0.0f);
            rlPushMatrix();
            rlTranslatef(gate.x, gate.y + 4.15f, gate.z);
            rlRotatef(90.0f - angleOf(start.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
            DrawCubeV({0.0f, 0.0f, 0.0f}, {start.width * kRenderScale + 3.0f, 0.34f, 0.42f}, Color{255, 235, 106, 255});
            DrawCubeV({-start.width * kRenderScale * 0.5f, -2.35f, 0.0f}, {0.46f, 5.1f, 0.46f}, Color{48, 130, 166, 255});
            DrawCubeV({start.width * kRenderScale * 0.5f, -2.35f, 0.0f}, {0.46f, 5.1f, 0.46f}, Color{48, 130, 166, 255});
            rlPopMatrix();
        }
    }

    void drawProp(const Prop3D& prop) {
        const TrackPoint3D p = track_.sample(prop.progress);
        const Vector3 base = track_.roadPoint(p, prop.side);
        const float s = prop.scale;
        switch (prop.type) {
            case Prop3D::Type::Palm:
                DrawCylinderEx(base, add(base, {0.0f, 5.4f * s, 0.0f}), 0.18f * s, 0.12f * s, 8, Color{126, 82, 45, 255});
                for (int i = 0; i < 5; ++i) {
                    rlPushMatrix();
                    rlTranslatef(base.x, base.y + 5.4f * s, base.z);
                    rlRotatef(static_cast<float>(i) * 72.0f, 0.0f, 1.0f, 0.0f);
                    DrawCubeV({0.0f, 0.0f, 1.35f * s}, {0.38f * s, 0.16f * s, 2.8f * s}, Color{38, 151, 82, 255});
                    rlPopMatrix();
                }
                break;
            case Prop3D::Type::Rock:
            case Prop3D::Type::Cliff:
                DrawCubeV(add(base, {0.0f, 0.65f * s, 0.0f}), {1.9f * s, 1.3f * s, 1.55f * s}, prop.color);
                DrawCubeV(add(base, {0.6f * s, 1.25f * s, -0.2f * s}), {1.2f * s, 1.4f * s, 1.0f * s}, shade(prop.color, 1.15f));
                break;
            case Prop3D::Type::Hut:
                DrawCubeV(add(base, {0.0f, 0.9f * s, 0.0f}), {2.8f * s, 1.8f * s, 2.4f * s}, Color{174, 91, 52, 255});
                DrawCylinder(add(base, {0.0f, 2.2f * s, 0.0f}), 0.0f, 2.1f * s, 1.45f * s, 4, Color{239, 185, 92, 255});
                break;
            case Prop3D::Type::Boat:
                rlPushMatrix();
                rlTranslatef(base.x, base.y + 0.55f * s, base.z);
                rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
                DrawCubeV({0.0f, 0.0f, 0.0f}, {3.7f * s, 0.8f * s, 1.4f * s}, prop.color);
                DrawCubeV({0.0f, 1.0f * s, 0.0f}, {0.18f * s, 2.4f * s, 0.18f * s}, Color{81, 66, 45, 255});
                DrawCubeV({0.8f * s, 1.5f * s, 0.0f}, {1.3f * s, 1.8f * s, 0.08f * s}, Color{246, 239, 186, 255});
                rlPopMatrix();
                break;
            case Prop3D::Type::Market:
                DrawCubeV(add(base, {0.0f, 0.75f * s, 0.0f}), {2.8f * s, 1.5f * s, 2.1f * s}, shade(prop.color, 0.85f));
                DrawCubeV(add(base, {0.0f, 1.75f * s, 0.0f}), {3.2f * s, 0.35f * s, 2.5f * s}, prop.color);
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
                DrawCubeV(add(base, {0.65f * s, 1.8f * s, 0.0f}), {1.3f * s, 1.7f * s, 0.08f * s}, prop.color);
                break;
        }
    }

    void drawProps() {
        for (const Prop3D& prop : track_.props()) {
            drawProp(prop);
        }
    }

    void drawKart(const Kart3D& kart, bool player) {
        const TrackPoint3D ground = track_.sample(kart.progress);
        const Vector3 base = toWorld(kart.pos, ground.elevation + 3.2f);
        const float w = kart.spec.width * kRenderScale;
        const float l = kart.spec.length * kRenderScale;
        const float h = kart.spec.height * kRenderScale;

        DrawCylinder(add(toWorld(kart.pos, ground.elevation + 0.05f), {0.0f, 0.02f, 0.0f}), w * 0.78f, w * 0.78f, 0.035f, 18,
                     Color{28, 35, 37, 90});

        rlPushMatrix();
        rlTranslatef(base.x, base.y, base.z);
        rlRotatef(90.0f - kart.heading * RAD2DEG, 0.0f, 1.0f, 0.0f);
        const float lean = std::clamp(kart.steerSmoothed * length(kart.vel) / 150.0f, -0.55f, 0.55f);
        rlRotatef(-lean * 8.0f, 0.0f, 0.0f, 1.0f);

        drawLocalBox({0.0f, h * 0.55f, 0.0f}, {w, h * 0.55f, l}, shade(kart.spec.body, kart.contactTimer > 0.0f ? 1.25f : 1.0f));
        drawLocalBox({0.0f, h * 1.05f, -l * 0.06f}, {w * 0.72f, h * 0.72f, l * 0.46f}, kart.spec.body);
        drawLocalBox({0.0f, h * 1.42f, -l * 0.16f}, {w * 0.46f, h * 0.42f, l * 0.34f}, kart.spec.glass);
        drawLocalBox({0.0f, h * 0.92f, l * 0.40f}, {w * 0.92f, h * 0.17f, l * 0.12f}, kart.spec.accent);
        drawLocalBox({0.0f, h * 0.90f, -l * 0.52f}, {w * 0.58f, h * 0.15f, l * 0.15f}, kart.spec.accent);
        drawLocalBox({0.0f, h * 0.52f, l * 0.58f}, {w * 1.05f, h * 0.20f, l * 0.12f}, shade(kart.spec.accent, 0.92f));
        drawLocalBox({0.0f, h * 0.50f, -l * 0.66f}, {w * 0.88f, h * 0.18f, l * 0.11f}, shade(kart.spec.accent, 0.82f));

        const Color fender = shade(kart.spec.body, 0.78f);
        for (float sx : {-1.0f, 1.0f}) {
            drawLocalBox({sx * w * 0.57f, h * 0.62f, l * 0.34f}, {w * 0.30f, h * 0.22f, l * 0.28f}, fender);
            drawLocalBox({sx * w * 0.57f, h * 0.60f, -l * 0.38f}, {w * 0.29f, h * 0.20f, l * 0.26f}, fender);
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
        drawLocalWheel(-w * 0.55f, l * 0.35f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent);
        drawLocalWheel(w * 0.55f, l * 0.35f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent);
        drawLocalWheel(-w * 0.55f, -l * 0.38f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent);
        drawLocalWheel(w * 0.55f, -l * 0.38f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent);

        const Color helmet = racerColor(kart.racer);
        DrawSphere({0.0f, h * 1.82f, -l * 0.12f}, h * 0.28f, helmet);
        DrawCubeV({0.0f, h * 1.70f, h * 0.02f}, {w * 0.52f, h * 0.10f, l * 0.58f}, Color{35, 43, 51, 255});
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
        std::array<int, kKartCount> order{};
        for (int i = 0; i < kKartCount; ++i) {
            order[static_cast<size_t>(i)] = i;
        }
        std::sort(order.begin(), order.end(), [&](int a, int b) {
            return lengthSq(karts_[static_cast<size_t>(a)].pos - karts_[0].pos) >
                   lengthSq(karts_[static_cast<size_t>(b)].pos - karts_[0].pos);
        });
        for (int index : order) {
            drawKart(karts_[static_cast<size_t>(index)], index == 0);
        }
    }

    void drawParticles() {
        for (const Particle3D& p : particles_) {
            const float t = std::clamp(p.life / p.maxLife, 0.0f, 1.0f);
            Color c = p.color;
            c.a = static_cast<unsigned char>(static_cast<float>(c.a) * t);
            DrawSphere(toWorld(p.pos, p.elevation), p.size * kRenderScale * (1.1f - t * 0.2f), c);
        }
    }

    void drawGarageHud(bool hasController) {
        const int w = GetScreenWidth();
        DrawRectangle(0, 0, w, 96, Color{12, 40, 50, 220});
        DrawText("SHARK HARBOR KARTS", 34, 20, 28, Color{255, 235, 145, 255});
        DrawText(specs_[static_cast<size_t>(selectedCar_)].name.c_str(), 36, 58, 22, WHITE);
        DrawText(racers_[static_cast<size_t>(selectedRacer_)].c_str(), w - 240, 28, 30, Color{255, 235, 145, 255});
        DrawText("A START  D-PAD SELECT", w - 344, 62, 18, Color{216, 243, 236, 255});
        if (!hasController) {
            DrawRectangle(0, GetScreenHeight() - 58, w, 58, Color{120, 32, 38, 225});
            DrawText("CONTROLLER REQUIRED", 34, GetScreenHeight() - 42, 24, Color{255, 241, 206, 255});
        }
    }

    void drawRaceHud(float fps, bool hasController) {
        const Kart3D& player = karts_[0];
        const float speed = std::max(0.0f, dot(player.vel, fromAngle(player.heading))) * 1.22f;
        DrawRectangle(24, 22, 280, 100, Color{10, 43, 55, 218});
        DrawText(TextFormat("%03d KMH", static_cast<int>(speed + 0.5f)), 40, 35, 32, Color{255, 235, 164, 255});
        DrawText(player.spec.name.c_str(), 42, 76, 18, Color{218, 242, 231, 255});
        DrawText(TextFormat("LAP %d", player.lap + 1), 42, 98, 18, Color{218, 242, 231, 255});

        const int w = GetScreenWidth();
        DrawRectangle(w - 260, 22, 228, 100, Color{10, 43, 55, 218});
        DrawText(TextFormat("P%d/8", playerPosition_), w - 222, 36, 32, Color{255, 235, 164, 255});
        DrawText(TextFormat("%02d:%04.1f", static_cast<int>(raceTime_ / 60.0f), std::fmod(raceTime_, 60.0f)), w - 222, 82, 18,
                 Color{218, 242, 231, 255});

        const int meterX = 34;
        const int meterY = GetScreenHeight() - 86;
        DrawRectangle(meterX, meterY, 232, 22, Color{10, 43, 55, 210});
        const float charge = player.drifting ? std::clamp(player.driftCharge / 1.2f, 0.0f, 1.0f) : std::clamp(player.boostTimer / 1.15f, 0.0f, 1.0f);
        DrawRectangle(meterX + 3, meterY + 3, static_cast<int>(226.0f * charge), 16,
                      player.boostTimer > 0.0f ? Color{255, 169, 43, 255} : Color{90, 218, 231, 255});
        DrawText(player.drifting ? "DRIFT" : "BOOST", meterX, meterY - 25, 18, Color{230, 247, 241, 255});

        DrawText(TextFormat("%.0f FPS", fps), w - 104, GetScreenHeight() - 34, 18, Color{255, 235, 164, 255});
        if (!hasController) {
            DrawRectangle(0, GetScreenHeight() - 92, w, 36, Color{120, 32, 38, 215});
            DrawText("CONTROLLER REQUIRED", 34, GetScreenHeight() - 84, 20, Color{255, 241, 206, 255});
        }
    }

    void drawHud(float fps, bool hasController) {
        if (mode_ == Mode::Garage) {
            drawGarageHud(hasController);
        } else {
            drawRaceHud(fps, hasController);
        }
        if (mode_ == Mode::Pause) {
            const int w = GetScreenWidth();
            const int h = GetScreenHeight();
            DrawRectangle(w / 2 - 160, h / 2 - 54, 320, 108, Color{10, 43, 55, 230});
            DrawText("PAUSED", w / 2 - 70, h / 2 - 34, 34, Color{255, 235, 145, 255});
            DrawText("START RESUME  B GARAGE", w / 2 - 120, h / 2 + 10, 18, Color{218, 242, 231, 255});
        }
    }

    Track3D track_;
    std::array<KartSpec3D, 8> specs_;
    std::array<std::string, 10> racers_;
    std::vector<Kart3D> karts_;
    std::vector<Particle3D> particles_;
    Camera camera_{};
    Mode mode_ = Mode::Garage;
    int selectedCar_ = 0;
    int selectedRacer_ = 0;
    int playerPosition_ = 1;
    float raceTime_ = 0.0f;
    float garageSpin_ = 0.0f;
    float fxAccumulator_ = 0.0f;
};

}  // namespace

int runHarborKarts3D(int argc, char** argv) {
    const bool windowed = hasArg(argc, argv, "--windowed") || hasArg(argc, argv, "--smoke-render") ||
                          hasArg(argc, argv, "--diagnose-controller") || hasArg(argc, argv, "--handling-audit") ||
                          hasArg(argc, argv, "--race-audit");
    const bool devKeyboard = hasArg(argc, argv, "--dev-keyboard");
    const bool smokeRender = hasArg(argc, argv, "--smoke-render");
    const bool capturePlaytest = hasArg(argc, argv, "--capture-playtest");
    const bool diagnoseController = hasArg(argc, argv, "--diagnose-controller");
    const bool handlingAudit = hasArg(argc, argv, "--handling-audit");
    const bool raceAudit = hasArg(argc, argv, "--race-audit");
    const std::filesystem::path launchDir = std::filesystem::current_path();
    const std::filesystem::path captureDir = launchDir / "build" / "playtest_frames";

    SetTraceLogLevel(LOG_ERROR);
    SetConfigFlags(FLAG_VSYNC_HINT | FLAG_WINDOW_RESIZABLE);
    InitWindow(1280, 720, "Shark Harbor Karts 3D");
    ChangeDirectory(launchDir.string().c_str());
    SetTargetFPS(120);
    if (!windowed) {
        const int monitor = GetCurrentMonitor();
        SetWindowSize(GetMonitorWidth(monitor), GetMonitorHeight(monitor));
        ToggleFullscreen();
    }

    ControllerReader controller;
    Game3D game;
    if (capturePlaytest) {
        std::filesystem::create_directories(captureDir);
        game.startRace();
    }
    if (handlingAudit) {
        const bool ok = game.runHandlingAudit();
        CloseWindow();
        return ok ? 0 : 1;
    }
    if (raceAudit) {
        const bool ok = game.runRaceAudit();
        CloseWindow();
        return ok ? 0 : 1;
    }

    double previous = GetTime();
    double accumulator = 0.0;
    int frames = 0;
    double diagnosticStamp = GetTime();

    while (!WindowShouldClose()) {
        const double now = GetTime();
        accumulator += std::min(0.10, now - previous);
        previous = now;

        const Input3D input = capturePlaytest ? game.scriptedInput() : readInput(controller, devKeyboard);
        const bool hasController = capturePlaytest || controller.available() || devKeyboard;
        while (accumulator >= kFixedDt) {
            game.update(kFixedDt, input, hasController);
            accumulator -= kFixedDt;
        }
        game.render(static_cast<float>(GetFPS()), hasController);

        if (capturePlaytest && (frames == 70 || frames == 190 || frames == 360)) {
            const std::filesystem::path path = std::filesystem::path("../playtest_frames") / TextFormat("harbor_karts_3d_%03d.png", frames);
            TakeScreenshot(path.string().c_str());
        }

        if (diagnoseController && now - diagnosticStamp > 0.25) {
            controller.printSnapshot();
            diagnosticStamp = now;
        }
        ++frames;
        if ((smokeRender && frames > 180) || (capturePlaytest && frames > 430) || (diagnoseController && frames > 900)) {
            break;
        }
    }

    CloseWindow();
    return 0;
}
