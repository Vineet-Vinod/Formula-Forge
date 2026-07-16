#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

#include "core_math.hpp"
#include "renderer.hpp"
#include "track_layout.hpp"

namespace {

constexpr int kFrameW = 960;
constexpr int kFrameH = 540;
constexpr float kFixedDt = 1.0f / 120.0f;

struct TrackPoint {
    Vec2 pos;
    Vec2 tangent{1.0f, 0.0f};
    Vec2 normal{0.0f, 1.0f};
    float progress = 0.0f;
    float width = 48.0f;
    float elevation = 0.0f;
    float curvature = 0.0f;
    float signedCurvature = 0.0f;
    uint32_t roadColor = rgb(180, 124, 75);
    uint32_t shoulderColor = rgb(224, 190, 105);
    int zone = 0;
};

struct Prop {
    enum class Type {
        Palm,
        Rock,
        Hut,
        Boat,
        Banner,
        SharkSign,
        Torch,
        FinishGate,
        MarketStall,
        DockCrane,
        TikiMask,
        Waterfall,
        Crystal,
        Chevron
    };
    Type type = Type::Palm;
    float progress = 0.0f;
    float side = 0.0f;
    float scale = 1.0f;
    uint32_t color = rgb(46, 141, 81);
};

class Track {
public:
    Track() { build(); }

    float totalLength() const { return totalLength_; }
    int sampleCount() const { return static_cast<int>(samples_.size()); }
    const std::vector<Prop>& props() const { return props_; }

    TrackPoint sample(float progress) const {
        progress = wrapDistance(progress, totalLength_);
        const float u = progress / totalLength_ * static_cast<float>(samples_.size());
        const int i0 = static_cast<int>(std::floor(u)) % static_cast<int>(samples_.size());
        const int i1 = (i0 + 1) % static_cast<int>(samples_.size());
        const float t = u - std::floor(u);
        TrackPoint out = samples_[i0];
        const TrackPoint& a = samples_[i0];
        const TrackPoint& b = samples_[i1];
        out.pos = lerp(a.pos, b.pos, t);
        out.tangent = normalize(lerp(a.tangent, b.tangent, t));
        out.normal = {-out.tangent.y, out.tangent.x};
        out.progress = progress;
        out.width = lerp(a.width, b.width, t);
        out.elevation = lerp(a.elevation, b.elevation, t);
        out.curvature = lerp(a.curvature, b.curvature, t);
        out.signedCurvature = lerp(a.signedCurvature, b.signedCurvature, t);
        return out;
    }

    int nearestIndex(Vec2 pos) const {
        int best = 0;
        float bestDist = std::numeric_limits<float>::max();
        for (int i = 0; i < static_cast<int>(samples_.size()); ++i) {
            const float d = lengthSq(samples_[i].pos - pos);
            if (d < bestDist) {
                best = i;
                bestDist = d;
            }
        }
        return best;
    }

    int nearestIndexNear(Vec2 pos, int hint, int radius = 96) const {
        if (samples_.empty()) {
            return 0;
        }
        int best = wrappedIndex(hint);
        float bestDist = lengthSq(samples_[static_cast<size_t>(best)].pos - pos);
        for (int offset = -radius; offset <= radius; ++offset) {
            const int index = wrappedIndex(hint + offset);
            const float d = lengthSq(samples_[static_cast<size_t>(index)].pos - pos);
            if (d < bestDist) {
                best = index;
                bestDist = d;
            }
        }
        if (bestDist > 260.0f * 260.0f) {
            return nearestIndex(pos);
        }
        return best;
    }

    const TrackPoint& pointAtIndex(int index) const { return samples_[static_cast<size_t>(wrappedIndex(index))]; }

    std::pair<int, int> turnBalance() const {
        int left = 0;
        int right = 0;
        for (int i = 0; i < sampleCount(); i += 6) {
            const Vec2 a = samples_[static_cast<size_t>(wrappedIndex(i - 6))].tangent;
            const Vec2 b = samples_[static_cast<size_t>(wrappedIndex(i + 6))].tangent;
            const float signedTurn = wrapAngle(angleOf(b) - angleOf(a));
            if (signedTurn > 0.018f) {
                ++left;
            } else if (signedTurn < -0.018f) {
                ++right;
            }
        }
        return {left, right};
    }

private:
    int wrappedIndex(int index) const {
        const int count = sampleCount();
        if (count == 0) {
            return 0;
        }
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

    static TrackPoint decorate(TrackPoint point, float phase) {
        phase -= std::floor(phase);
        point.width = 118.0f;
        point.roadColor = rgb(214, 142, 76);
        point.shoulderColor = rgb(244, 211, 128);
        point.zone = 0;

        if (phase < 0.14f) {
            point.zone = 0;
            point.width = 142.0f;
            point.roadColor = rgb(220, 158, 84);
            point.shoulderColor = rgb(248, 214, 128);
        } else if (phase < 0.29f) {
            point.zone = 1;
            point.width = 112.0f;
            point.roadColor = rgb(151, 96, 58);
            point.shoulderColor = rgb(115, 75, 48);
            point.elevation += 8.0f;
        } else if (phase < 0.42f) {
            point.zone = 2;
            point.width = 124.0f;
            point.roadColor = rgb(174, 103, 80);
            point.shoulderColor = rgb(239, 180, 90);
        } else if (phase < 0.58f) {
            point.zone = 3;
            point.width = 116.0f;
            point.roadColor = rgb(82, 80, 88);
            point.shoulderColor = rgb(49, 53, 62);
            point.elevation += 22.0f * smoothstep((phase - 0.42f) / 0.16f);
        } else if (phase < 0.72f) {
            point.zone = 4;
            point.width = 128.0f;
            point.roadColor = rgb(130, 132, 102);
            point.shoulderColor = rgb(69, 128, 92);
            point.elevation += 20.0f * (1.0f - smoothstep((phase - 0.58f) / 0.14f));
        } else if (phase < 0.85f) {
            point.zone = 5;
            point.width = 108.0f;
            point.roadColor = rgb(151, 88, 48);
            point.shoulderColor = rgb(45, 171, 177);
            point.elevation += 7.0f;
        } else {
            point.zone = 6;
            point.width = 138.0f;
            point.roadColor = rgb(206, 128, 70);
            point.shoulderColor = rgb(240, 196, 105);
        }

        point.elevation += 3.0f * std::sin(phase * kTwoPi * 5.0f);
        return point;
    }

    void build() {
        const auto& control = kBreakwaterControlPoints;
        const auto controlPoint = [&control](int index) {
            const int count = static_cast<int>(control.size());
            int wrapped = index % count;
            if (wrapped < 0) {
                wrapped += count;
            }
            const TrackControlPoint& point = control[static_cast<size_t>(wrapped)];
            return Vec2{point.x, point.y};
        };

        std::vector<Vec2> dense;
        constexpr int kSteps = 28;
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

        constexpr int kSampleCount = 2304;
        samples_.resize(kSampleCount);
        for (int i = 0; i < kSampleCount; ++i) {
            const float desired = totalLength_ * static_cast<float>(i) / kSampleCount;
            auto it = std::upper_bound(cumulative.begin(), cumulative.end(), desired);
            int seg = std::max(0, static_cast<int>(it - cumulative.begin()) - 1);
            if (seg >= static_cast<int>(dense.size())) {
                seg = static_cast<int>(dense.size()) - 1;
            }
            const float span = cumulative[seg + 1] - cumulative[seg];
            const float t = span > 0.001f ? (desired - cumulative[seg]) / span : 0.0f;
            TrackPoint point;
            point.progress = desired;
            point.pos = lerp(dense[seg], dense[(seg + 1) % dense.size()], t);
            samples_[i] = decorate(point, desired / totalLength_);
        }

        for (int i = 0; i < kSampleCount; ++i) {
            TrackPoint& point = samples_[i];
            const Vec2 prev = samples_[(i - 2 + kSampleCount) % kSampleCount].pos;
            const Vec2 next = samples_[(i + 2) % kSampleCount].pos;
            point.tangent = normalize(next - prev);
            point.normal = {-point.tangent.y, point.tangent.x};
        }
        for (int i = 0; i < kSampleCount; ++i) {
            const Vec2 a = samples_[(i - 5 + kSampleCount) % kSampleCount].tangent;
            const Vec2 b = samples_[(i + 5) % kSampleCount].tangent;
            samples_[i].signedCurvature = wrapAngle(angleOf(b) - angleOf(a));
            samples_[i].curvature = std::abs(samples_[i].signedCurvature);
        }

        buildProps();
        buildLandmarks();
    }

    void buildProps() {
        std::mt19937 rng(1776);
        std::uniform_real_distribution<float> jitter(-11.0f, 11.0f);
        const int count = 144;
        for (int i = 0; i < count; ++i) {
            const float p = totalLength_ * (static_cast<float>(i) + 0.37f) / count + jitter(rng);
            const TrackPoint tp = sample(p);
            Prop prop;
            prop.progress = wrapDistance(p, totalLength_);
            prop.side = (i % 2 == 0 ? -1.0f : 1.0f) * (tp.width * 0.5f + 70.0f + static_cast<float>((i * 13) % 84));
            prop.scale = 0.8f + static_cast<float>((i * 7) % 9) * 0.08f;
            if (tp.zone == 1 || tp.zone == 5) {
                prop.type = (i % 5 == 0) ? Prop::Type::DockCrane : ((i % 3 == 0) ? Prop::Type::Boat : Prop::Type::Banner);
                prop.color = rgb(195, 77, 65);
            } else if (tp.zone == 2) {
                prop.type = (i % 4 == 0) ? Prop::Type::MarketStall : ((i % 5 == 0) ? Prop::Type::TikiMask : Prop::Type::Hut);
                prop.color = rgb(228, 85, 68);
            } else if (tp.zone == 3) {
                prop.type = (i % 3 == 0) ? Prop::Type::Crystal : ((i % 2 == 0) ? Prop::Type::Torch : Prop::Type::Rock);
                prop.color = rgb(218, 126, 49);
            } else if (i % 11 == 0) {
                prop.type = Prop::Type::SharkSign;
                prop.color = rgb(58, 125, 161);
            } else if (i % 5 == 0) {
                prop.type = Prop::Type::Hut;
                prop.color = rgb(176, 102, 60);
            } else if (i % 4 == 0) {
                prop.type = Prop::Type::Rock;
                prop.color = rgb(113, 105, 91);
            } else {
                prop.type = Prop::Type::Palm;
                prop.color = rgb(42, 148, 79);
            }
            props_.push_back(prop);
        }
    }

    void addLandmark(float phase, float sideSign, float extraOffset, float scale, Prop::Type type, uint32_t color) {
        const float progress = wrapDistance(totalLength_ * phase, totalLength_);
        const TrackPoint tp = sample(progress);
        Prop prop;
        prop.progress = progress;
        prop.side = sideSign == 0.0f ? 0.0f : sideSign * (tp.width * 0.5f + extraOffset);
        prop.scale = scale;
        prop.type = type;
        prop.color = color;
        props_.push_back(prop);
    }

    void buildLandmarks() {
        addLandmark(0.006f, 0.0f, 0.0f, 2.25f, Prop::Type::FinishGate, rgb(48, 129, 164));
        addLandmark(0.035f, -1.0f, 52.0f, 1.45f, Prop::Type::Chevron, rgb(236, 66, 57));
        addLandmark(0.055f, 1.0f, 54.0f, 1.60f, Prop::Type::SharkSign, rgb(48, 129, 164));
        addLandmark(0.150f, -1.0f, 44.0f, 1.85f, Prop::Type::DockCrane, rgb(219, 84, 61));
        addLandmark(0.185f, 1.0f, 52.0f, 1.55f, Prop::Type::Boat, rgb(230, 80, 58));
        addLandmark(0.245f, -1.0f, 38.0f, 1.45f, Prop::Type::Chevron, rgb(255, 202, 63));
        addLandmark(0.306f, -1.0f, 42.0f, 1.75f, Prop::Type::MarketStall, rgb(237, 73, 84));
        addLandmark(0.337f, 1.0f, 44.0f, 1.70f, Prop::Type::MarketStall, rgb(62, 178, 156));
        addLandmark(0.382f, -1.0f, 48.0f, 1.75f, Prop::Type::TikiMask, rgb(142, 79, 46));
        addLandmark(0.430f, 1.0f, 34.0f, 1.35f, Prop::Type::Crystal, rgb(111, 218, 225));
        addLandmark(0.468f, -1.0f, 36.0f, 1.50f, Prop::Type::Torch, rgb(244, 119, 46));
        addLandmark(0.520f, 1.0f, 42.0f, 1.65f, Prop::Type::Crystal, rgb(122, 204, 255));
        addLandmark(0.605f, -1.0f, 54.0f, 2.05f, Prop::Type::Waterfall, rgb(84, 191, 214));
        addLandmark(0.662f, 1.0f, 46.0f, 1.55f, Prop::Type::Chevron, rgb(236, 66, 57));
        addLandmark(0.735f, -1.0f, 38.0f, 1.70f, Prop::Type::DockCrane, rgb(230, 90, 52));
        addLandmark(0.790f, 1.0f, 44.0f, 1.45f, Prop::Type::Boat, rgb(246, 196, 59));
        addLandmark(0.842f, -1.0f, 38.0f, 1.40f, Prop::Type::Chevron, rgb(255, 202, 63));
        addLandmark(0.904f, 1.0f, 62.0f, 1.90f, Prop::Type::Hut, rgb(181, 96, 55));
        addLandmark(0.955f, -1.0f, 52.0f, 1.60f, Prop::Type::Palm, rgb(38, 148, 84));
    }

    std::vector<TrackPoint> samples_;
    std::vector<Prop> props_;
    float totalLength_ = 1.0f;
};

struct KartSpec {
    std::string name;
    uint32_t body = rgb(230, 60, 48);
    uint32_t accent = rgb(255, 211, 78);
    uint32_t glass = rgb(83, 194, 213);
    float maxSpeed = 124.0f;
    float accel = 92.0f;
    float brake = 140.0f;
    float grip = 1.0f;
    float drift = 1.0f;
    int bodyStyle = 0;
    float wheelScale = 1.0f;
    float cabinScale = 1.0f;
    float noseScale = 1.0f;
};

struct Kart {
    KartSpec spec;
    std::string racer;
    Vec2 pos;
    Vec2 vel;
    float heading = 0.0f;
    float progress = 0.0f;
    int lap = 0;
    int nearest = 0;
    float lane = 0.0f;
    float aiTempo = 1.0f;
    float aiAggression = 0.8f;
    float aiRisk = 0.5f;
    float aiPassBias = 1.0f;
    bool drifting = false;
    float driftCharge = 0.0f;
    float boostTimer = 0.0f;
    float boostPower = 0.0f;
    float slip = 0.0f;
    float contactTimer = 0.0f;
    float fxTimer = 0.0f;
};

struct Particle {
    Vec2 pos;
    Vec2 vel;
    float life = 0.0f;
    float maxLife = 1.0f;
    float size = 1.0f;
    uint32_t color = rgb(255, 255, 255);
};

struct InputState {
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

struct Camera {
    Vec2 pos;
    float yaw = 0.0f;
    float height = 42.0f;
    float horizon = 150.0f;
    float focal = 500.0f;
};

struct ScreenPoint {
    Vec2 p;
    float depth = 0.0f;
    float scale = 0.0f;
    bool visible = false;
};

ScreenPoint projectPoint(Vec2 world, float elevation, const Camera& camera) {
    const Vec2 forward = fromAngle(camera.yaw);
    const Vec2 right{-forward.y, forward.x};
    const Vec2 rel = world - camera.pos;
    const float depth = dot(rel, forward);
    if (depth < 3.0f) {
        return {};
    }
    const float side = dot(rel, right);
    ScreenPoint out;
    out.depth = depth;
    out.scale = camera.focal / depth;
    out.p.x = kFrameW * 0.5f + side * out.scale;
    out.p.y = camera.horizon + (camera.height - elevation) * out.scale;
    out.visible = out.p.y > -220.0f && out.p.y < kFrameH + 260.0f && out.p.x > -700.0f && out.p.x < kFrameW + 700.0f;
    return out;
}

std::vector<KartSpec> makeCars() {
    return {
        {"TIDE HOPPER", rgb(224, 57, 56), rgb(255, 202, 63), rgb(79, 195, 212), 124.0f, 93.0f, 142.0f, 1.02f, 1.00f, 0, 1.00f, 1.00f, 1.00f},
        {"REEF RUNNER", rgb(35, 151, 211), rgb(255, 235, 90), rgb(111, 222, 227), 128.0f, 86.0f, 138.0f, 0.97f, 1.08f, 1, 0.92f, 0.88f, 1.18f},
        {"DUNE FOX", rgb(240, 139, 45), rgb(47, 61, 76), rgb(95, 201, 217), 120.0f, 102.0f, 148.0f, 1.08f, 0.96f, 2, 1.14f, 1.06f, 0.94f},
        {"PIER SHARK", rgb(61, 81, 103), rgb(232, 67, 61), rgb(91, 205, 217), 132.0f, 78.0f, 134.0f, 0.93f, 1.16f, 3, 0.98f, 0.76f, 1.34f},
        {"MANGO MULE", rgb(246, 199, 62), rgb(30, 133, 76), rgb(110, 210, 222), 116.0f, 111.0f, 152.0f, 1.13f, 0.90f, 4, 1.24f, 1.18f, 0.84f},
        {"LAGOON GT", rgb(34, 184, 143), rgb(238, 73, 95), rgb(151, 232, 235), 129.0f, 90.0f, 139.0f, 1.00f, 1.05f, 5, 0.94f, 0.92f, 1.22f},
        {"TIKI RAIL", rgb(132, 78, 44), rgb(248, 125, 54), rgb(98, 196, 210), 121.0f, 98.0f, 146.0f, 1.05f, 1.02f, 6, 1.08f, 1.28f, 0.90f},
        {"STORM BUGGY", rgb(116, 105, 175), rgb(255, 213, 65), rgb(101, 215, 229), 126.0f, 95.0f, 144.0f, 1.00f, 1.10f, 7, 1.02f, 0.96f, 1.08f},
    };
}

std::vector<std::string> makeRacers() {
    return {"KAI", "MAYA", "BRUNO", "LANI", "REX", "NOVA", "SKIP", "ZARA", "COBALT", "TESS"};
}

uint32_t racerColor(std::string_view racer) {
    static constexpr std::array<uint32_t, 10> palette = {
        rgb(255, 211, 80), rgb(238, 78, 91),  rgb(71, 185, 131), rgb(76, 151, 224), rgb(245, 132, 58),
        rgb(179, 112, 219), rgb(242, 233, 201), rgb(39, 51, 63),   rgb(86, 214, 222), rgb(245, 164, 196),
    };
    uint32_t hash = 2166136261u;
    for (char ch : racer) {
        hash ^= static_cast<uint8_t>(ch);
        hash *= 16777619u;
    }
    return palette[hash % palette.size()];
}

float axisUnit(Sint16 value) {
    const float f = static_cast<float>(value) / 32767.0f;
    return std::abs(f) < 0.08f ? 0.0f : std::clamp(f, -1.0f, 1.0f);
}

float triggerUnit(Sint16 value) {
    if (value <= 0) {
        return 0.0f;
    }
    return std::clamp(static_cast<float>(value) / 32767.0f, 0.0f, 1.0f);
}

bool joystickButton(SDL_Joystick* joystick, int button) {
    return joystick && button >= 0 && button < SDL_GetNumJoystickButtons(joystick) && SDL_GetJoystickButton(joystick, button);
}

float joystickAxis(SDL_Joystick* joystick, int axis) {
    if (!joystick || axis < 0 || axis >= SDL_GetNumJoystickAxes(joystick)) {
        return 0.0f;
    }
    return axisUnit(SDL_GetJoystickAxis(joystick, axis));
}

float strongerAxis(float a, float b) { return std::abs(b) > std::abs(a) ? b : a; }

InputState readGamepad(SDL_Gamepad* pad, bool devKeyboard) {
    InputState input;
    if (pad) {
        SDL_Joystick* joystick = SDL_GetGamepadJoystick(pad);
        input.steer = axisUnit(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFTX));
        input.throttle = triggerUnit(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER));
        input.brake = triggerUnit(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFT_TRIGGER));
        input.drift = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER);
        input.a = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_SOUTH);
        input.b = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_EAST);
        input.start = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_START);
        input.back = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_BACK);
        input.left = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_LEFT) || input.steer < -0.55f;
        input.right = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_RIGHT) || input.steer > 0.55f;
        input.up = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_UP);
        input.down = SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_DOWN);

        // Some XInput-compatible USB receivers report as a gamepad but have a
        // broken logical button map. Keep the SDL gamepad path, but also accept
        // the raw Linux/xpad button indices for the same physical controls.
        input.steer = strongerAxis(input.steer, joystickAxis(joystick, 0));
        input.throttle = std::max(input.throttle, std::max(0.0f, joystickAxis(joystick, 5)));
        input.brake = std::max(input.brake, std::max(0.0f, joystickAxis(joystick, 2)));
        input.drift = input.drift || joystickButton(joystick, 5);
        input.a = input.a || joystickButton(joystick, 0);
        input.b = input.b || joystickButton(joystick, 1);
        input.back = input.back || joystickButton(joystick, 6);
        input.start = input.start || joystickButton(joystick, 7);
        input.left = input.left || joystickButton(joystick, 11) || joystickAxis(joystick, 6) < -0.55f;
        input.right = input.right || joystickButton(joystick, 12) || joystickAxis(joystick, 6) > 0.55f;
        input.up = input.up || joystickButton(joystick, 13) || joystickAxis(joystick, 7) < -0.55f;
        input.down = input.down || joystickButton(joystick, 14) || joystickAxis(joystick, 7) > 0.55f;
    }
    if (devKeyboard) {
        int keyCount = 0;
        const bool* keys = SDL_GetKeyboardState(&keyCount);
        const auto key = [&](SDL_Scancode code) { return static_cast<int>(code) < keyCount && keys[code]; };
        const float left = key(SDL_SCANCODE_LEFT) || key(SDL_SCANCODE_A) ? 1.0f : 0.0f;
        const float right = key(SDL_SCANCODE_RIGHT) || key(SDL_SCANCODE_D) ? 1.0f : 0.0f;
        input.steer = std::clamp(input.steer + right - left, -1.0f, 1.0f);
        input.throttle = std::max(input.throttle, key(SDL_SCANCODE_W) || key(SDL_SCANCODE_UP) ? 1.0f : 0.0f);
        input.brake = std::max(input.brake, key(SDL_SCANCODE_S) || key(SDL_SCANCODE_DOWN) ? 1.0f : 0.0f);
        input.drift = input.drift || key(SDL_SCANCODE_LSHIFT) || key(SDL_SCANCODE_RSHIFT);
        input.a = input.a || key(SDL_SCANCODE_RETURN) || key(SDL_SCANCODE_SPACE);
        input.b = input.b || key(SDL_SCANCODE_ESCAPE);
        input.start = input.start || key(SDL_SCANCODE_P);
        input.back = input.back || key(SDL_SCANCODE_R);
        input.left = input.left || key(SDL_SCANCODE_LEFT);
        input.right = input.right || key(SDL_SCANCODE_RIGHT);
        input.up = input.up || key(SDL_SCANCODE_UP);
        input.down = input.down || key(SDL_SCANCODE_DOWN);
    }
    input.steer = std::copysign(std::pow(std::abs(input.steer), 1.12f), input.steer);
    return input;
}

void printControllerSnapshot(SDL_Gamepad* pad) {
    if (!pad) {
        std::cout << "controller: none\n";
        return;
    }
    SDL_Joystick* joystick = SDL_GetGamepadJoystick(pad);
    std::cout << "gamepad buttons A/B/X/Y="
              << SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_SOUTH) << "/"
              << SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_EAST) << "/"
              << SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_WEST) << "/"
              << SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_NORTH)
              << " start/back=" << SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_START) << "/"
              << SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_BACK)
              << " axes LX/LT/RT=" << SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFTX) << "/"
              << SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFT_TRIGGER) << "/"
              << SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER);
    if (joystick) {
        const int buttons = SDL_GetNumJoystickButtons(joystick);
        const int axes = SDL_GetNumJoystickAxes(joystick);
        std::cout << " | raw buttons";
        for (int i = 0; i < std::min(buttons, 12); ++i) {
            std::cout << " " << i << ":" << SDL_GetJoystickButton(joystick, i);
        }
        std::cout << " | raw axes";
        for (int i = 0; i < std::min(axes, 8); ++i) {
            std::cout << " " << i << ":" << SDL_GetJoystickAxis(joystick, i);
        }
    }
    std::cout << "\n";
}

bool pressed(bool now, bool prev) { return now && !prev; }

float carScore(const Kart& kart, float totalLength) {
    return static_cast<float>(kart.lap) * totalLength + kart.progress;
}

std::string formatRaceTime(float seconds) {
    if (!std::isfinite(seconds) || seconds <= 0.0f || seconds > 5999.0f) {
        return "--:--.-";
    }
    const int minutes = static_cast<int>(seconds) / 60;
    const int whole = static_cast<int>(seconds) % 60;
    const int tenths = static_cast<int>(seconds * 10.0f) % 10;
    std::ostringstream out;
    out << minutes << ":" << std::setw(2) << std::setfill('0') << whole << "." << tenths;
    return out.str();
}

enum class DriverStyle { NoBrake, BrakeLine, DriftLine };

struct DriverAuditResult {
    float score = 0.0f;
    int offroadFrames = 0;
    int barrierHits = 0;
    int boostFrames = 0;
    float maxOffroad = 0.0f;
};

class Game {
public:
    enum class Mode { Garage, Race, Pause };

    Game() : track_(), cars_(makeCars()), racers_(makeRacers()) { resetRace(); }

    void update(float dt, const InputState& input, bool hasController) {
        if (input.start && input.back) {
            quitRequested_ = true;
        }

        const bool leftPressed = pressed(input.left, prevInput_.left);
        const bool rightPressed = pressed(input.right, prevInput_.right);
        const bool upPressed = pressed(input.up, prevInput_.up);
        const bool downPressed = pressed(input.down, prevInput_.down);
        const bool aPressed = pressed(input.a, prevInput_.a);
        const bool bPressed = pressed(input.b, prevInput_.b);
        const bool startPressed = pressed(input.start, prevInput_.start);
        const bool backPressed = pressed(input.back, prevInput_.back);

        if (mode_ == Mode::Garage) {
            if (leftPressed) {
                selectedCar_ = (selectedCar_ + static_cast<int>(cars_.size()) - 1) % static_cast<int>(cars_.size());
            }
            if (rightPressed) {
                selectedCar_ = (selectedCar_ + 1) % static_cast<int>(cars_.size());
            }
            if (upPressed) {
                selectedRacer_ = (selectedRacer_ + static_cast<int>(racers_.size()) - 1) % static_cast<int>(racers_.size());
            }
            if (downPressed) {
                selectedRacer_ = (selectedRacer_ + 1) % static_cast<int>(racers_.size());
            }
            if ((aPressed || startPressed) && hasController) {
                resetRace();
                mode_ = Mode::Race;
            }
            prevInput_ = input;
            return;
        }

        if (mode_ == Mode::Pause) {
            if (aPressed || startPressed) {
                mode_ = Mode::Race;
            }
            if (bPressed) {
                mode_ = Mode::Garage;
            }
            prevInput_ = input;
            return;
        }

        if (startPressed) {
            mode_ = Mode::Pause;
        }
        if (backPressed) {
            resetPlayerToTrack();
        }

        if (mode_ == Mode::Race && hasController) {
            if (countdown_ > 0.0f) {
                countdown_ = std::max(0.0f, countdown_ - dt);
                updateCamera(dt);
                updateAmbient(dt);
                computeRacePosition();
                prevInput_ = input;
                return;
            }
            const int oldPlayerLap = karts_[0].lap;
            updatePlayer(karts_[0], input, dt);
            for (size_t i = 1; i < karts_.size(); ++i) {
                updateAi(karts_[i], dt, static_cast<int>(i));
            }
            resolveKartContacts();
            updateParticles(dt);
            updateRaceTimers(dt, oldPlayerLap);
            updateCamera(dt);
            updateAmbient(dt);
            computeRacePosition();
        }

        prevInput_ = input;
    }

    void render(Renderer& r, float fps, bool hasController) {
        if (mode_ == Mode::Garage) {
            renderGarage(r, fps, hasController);
            return;
        }

        renderRace(r, fps, hasController);
        if (mode_ == Mode::Pause) {
            r.fillRect(0, 0, kFrameW, kFrameH, 0x000000);
            renderRace(r, fps, hasController);
            r.fillRect(290, 192, 380, 116, rgb(20, 36, 48));
            r.drawText(374, 216, "PAUSED", 5, rgb(245, 237, 198));
            r.drawText(338, 266, "A/START RESUME", 2, rgb(245, 237, 198));
        }
    }

    bool quitRequested() const { return quitRequested_; }

    void startRaceForDiagnostics() {
        resetRace();
        mode_ = Mode::Race;
        countdown_ = 0.0f;
        prevInput_ = {};
    }

    void updateAutoplay(float dt) {
        if (mode_ != Mode::Race) {
            startRaceForDiagnostics();
        }
        const int oldPlayerLap = karts_[0].lap;
        updateAi(karts_[0], dt, 0);
        for (size_t ai = 1; ai < karts_.size(); ++ai) {
            updateAi(karts_[ai], dt, static_cast<int>(ai));
        }
        resolveKartContacts();
        updateParticles(dt);
        updateRaceTimers(dt, oldPlayerLap);
        updateCamera(dt);
        updateAmbient(dt);
        computeRacePosition();
    }

    void placeForSectionCapture(float phase, float speed) {
        resetRace();
        mode_ = Mode::Race;
        countdown_ = 0.0f;
        const float progress = wrapDistance(track_.totalLength() * phase, track_.totalLength());
        for (size_t i = 0; i < karts_.size(); ++i) {
            Kart& kart = karts_[i];
            const float offset = i == 0 ? 0.0f : 52.0f + static_cast<float>(i) * 32.0f;
            const TrackPoint tp = track_.sample(progress + offset);
            kart.progress = wrapDistance(progress + offset, track_.totalLength());
            kart.lap = 0;
            kart.lane = i == 0 ? 0.0f : ((static_cast<int>(i) % 3) - 1) * 8.0f;
            kart.pos = tp.pos + tp.normal * kart.lane;
            kart.heading = angleOf(tp.tangent);
            kart.vel = tp.tangent * (i == 0 ? speed : std::max(28.0f, speed * (0.74f + static_cast<float>(i % 3) * 0.06f)));
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.drifting = false;
            kart.driftCharge = 0.0f;
            kart.boostTimer = 0.0f;
            kart.boostPower = 0.0f;
            kart.slip = 0.0f;
            kart.contactTimer = 0.0f;
            kart.fxTimer = 0.0f;
        }
        camera_.yaw = karts_[0].heading;
        caveBlend_ = track_.pointAtIndex(karts_[0].nearest).zone == 3 ? 1.0f : 0.0f;
        updateCamera(1.0f);
        updateAmbient(1.0f);
        computeRacePosition();
    }

    bool selfTest() {
        resetRace();
        mode_ = Mode::Race;
        for (int i = 0; i < 1200; ++i) {
            updateAi(karts_[0], kFixedDt, 0);
            for (size_t ai = 1; ai < karts_.size(); ++ai) {
                updateAi(karts_[ai], kFixedDt, static_cast<int>(ai));
            }
            if (!std::isfinite(karts_[0].pos.x) || !std::isfinite(karts_[0].pos.y) || length(karts_[0].vel) > 240.0f) {
                std::cerr << "self-test instability at step " << i << "\n";
                return false;
            }
        }
        const float finalSpeed = length(karts_[0].vel);
        const bool ok = finalSpeed > 20.0f && track_.totalLength() > 2000.0f;
        if (!ok) {
            std::cerr << "self-test final speed " << finalSpeed << ", track length " << track_.totalLength() << "\n";
        }
        return ok;
    }

    bool raceAudit() {
        const auto [leftTurns, rightTurns] = track_.turnBalance();
        int progressJumps = 0;
        int caveToggles = 0;
        int barrierHits = 0;
        bool stable = true;
        float maxSpeed = 0.0f;

        constexpr int kAiAuditSteps = 8400;
        constexpr int kNoBrakeAuditSteps = 4800;
        resetRace();
        mode_ = Mode::Race;
        bool lastCave = track_.pointAtIndex(karts_[0].nearest).zone == 3;
        for (int i = 0; i < kAiAuditSteps; ++i) {
            const int before = karts_[0].nearest;
            updateAi(karts_[0], kFixedDt, 0);
            for (size_t ai = 1; ai < karts_.size(); ++ai) {
                updateAi(karts_[ai], kFixedDt, static_cast<int>(ai));
            }
            const int delta = sampleDelta(before, karts_[0].nearest);
            if (std::abs(delta) > 42) {
                ++progressJumps;
            }
            const bool cave = track_.pointAtIndex(karts_[0].nearest).zone == 3;
            if (cave != lastCave) {
                ++caveToggles;
                lastCave = cave;
            }
            const TrackPoint tp = track_.pointAtIndex(karts_[0].nearest);
            const float lane = std::abs(dot(karts_[0].pos - tp.pos, tp.normal));
            if (lane > tp.width * 0.5f + 13.0f) {
                ++barrierHits;
            }
            maxSpeed = std::max(maxSpeed, length(karts_[0].vel));
            stable = stable && std::isfinite(karts_[0].pos.x) && std::isfinite(karts_[0].pos.y) && length(karts_[0].vel) < 220.0f;
        }

        resetRace();
        mode_ = Mode::Race;
        int fullThrottleJumps = 0;
        int fullThrottleBarrierHits = 0;
        int highCurveSamples = 0;
        int highCurveTooFast = 0;
        float highCurveSpeedSum = 0.0f;
        float maxOffroad = 0.0f;
        for (int i = 0; i < kNoBrakeAuditSteps; ++i) {
            Kart& player = karts_[0];
            const int before = player.nearest;
            const float speed = length(player.vel);
            const TrackPoint target = track_.sample(player.progress + 78.0f + speed * 0.48f);
            const Vec2 forward = fromAngle(player.heading);
            const Vec2 toTarget = normalize(target.pos - player.pos);
            const float angleError = std::atan2(cross(forward, toTarget), dot(forward, toTarget));

            InputState noBrake;
            noBrake.throttle = 1.0f;
            noBrake.steer = std::clamp(angleError * 2.0f, -1.0f, 1.0f);
            updatePlayer(player, noBrake, kFixedDt);

            const int delta = sampleDelta(before, player.nearest);
            if (std::abs(delta) > 42) {
                ++fullThrottleJumps;
            }
            const TrackPoint tp = track_.pointAtIndex(player.nearest);
            const float lane = std::abs(dot(player.pos - tp.pos, tp.normal));
            const float offroad = std::max(0.0f, lane - tp.width * 0.5f);
            maxOffroad = std::max(maxOffroad, offroad);
            if (lane > tp.width * 0.5f + 13.0f) {
                ++fullThrottleBarrierHits;
            }
            if (tp.curvature > 0.125f) {
                ++highCurveSamples;
                const float currentSpeed = length(player.vel);
                highCurveSpeedSum += currentSpeed;
                if (currentSpeed > player.spec.maxSpeed * 0.78f) {
                    ++highCurveTooFast;
                }
            }
            stable = stable && std::isfinite(player.pos.x) && std::isfinite(player.pos.y) && length(player.vel) < 220.0f;
        }

        const float turnRatio = static_cast<float>(std::max(leftTurns, rightTurns)) /
                                static_cast<float>(std::max(1, std::min(leftTurns, rightTurns)));
        const float highCurveAverage = highCurveSamples > 0 ? highCurveSpeedSum / static_cast<float>(highCurveSamples) : 0.0f;
        const DriverAuditResult noBrake = runDriverAudit(DriverStyle::NoBrake);
        const DriverAuditResult brakeLine = runDriverAudit(DriverStyle::BrakeLine);
        const DriverAuditResult driftLine = runDriverAudit(DriverStyle::DriftLine);
        const bool skillOrder = driftLine.score > noBrake.score * 1.08f && driftLine.score > brakeLine.score * 1.15f &&
                                driftLine.boostFrames > 500;
        const bool ok = stable && progressJumps == 0 && fullThrottleJumps == 0 && caveToggles <= 8 && barrierHits < 8 &&
                        leftTurns > 40 && rightTurns > 40 && turnRatio < 2.35f && highCurveSamples > 120 &&
                        highCurveTooFast < highCurveSamples * 55 / 100 && skillOrder;

        std::cout << "race-audit stable=" << stable << " progress_jumps=" << progressJumps
                  << " full_throttle_jumps=" << fullThrottleJumps << " cave_toggles=" << caveToggles
                  << " ai_barrier_hits=" << barrierHits << " turn_balance L/R=" << leftTurns << "/" << rightTurns
                  << " turn_ratio=" << turnRatio << " max_speed=" << maxSpeed
                  << " no_brake_barrier_hits=" << fullThrottleBarrierHits << " no_brake_max_offroad=" << maxOffroad
                  << " high_curve_avg_speed=" << highCurveAverage << " high_curve_too_fast=" << highCurveTooFast << "/"
                  << highCurveSamples << " driver_scores no_brake/brake/drift=" << noBrake.score << "/" << brakeLine.score << "/"
                  << driftLine.score << " driver_offroad=" << noBrake.offroadFrames << "/" << brakeLine.offroadFrames << "/"
                  << driftLine.offroadFrames << " driver_boost=" << noBrake.boostFrames << "/" << brakeLine.boostFrames << "/"
                  << driftLine.boostFrames << " skill_order=" << skillOrder << "\n";
        if (!ok) {
            std::cerr << "race-audit failed\n";
        }
        return ok;
    }

private:
    DriverAuditResult runDriverAudit(DriverStyle style) {
        resetRace();
        mode_ = Mode::Race;
        DriverAuditResult result;
        constexpr int kSteps = 120 * 72;
        for (int i = 0; i < kSteps; ++i) {
            Kart& player = karts_[0];
            const float speed = length(player.vel);
            const TrackPoint here = track_.pointAtIndex(player.nearest);
            const TrackPoint look = track_.sample(player.progress + 92.0f + speed * 0.62f);
            const float curve = std::max(here.curvature, look.curvature);
            float laneTarget = 0.0f;
            if (style == DriverStyle::DriftLine && curve > 0.045f) {
                const float turnSign = std::abs(look.signedCurvature) > 0.001f ? std::copysign(1.0f, look.signedCurvature)
                                                                               : std::copysign(1.0f, angleOf(look.tangent - here.tangent));
                laneTarget = -turnSign * here.width * 0.16f;
            }
            const Vec2 targetPos = look.pos + look.normal * laneTarget;
            const Vec2 forward = fromAngle(player.heading);
            const Vec2 toTarget = normalize(targetPos - player.pos);
            const float angleError = std::atan2(cross(forward, toTarget), dot(forward, toTarget));
            float targetSpeed = player.spec.maxSpeed * (0.98f - std::clamp(curve * 3.35f, 0.0f, 0.31f));
            if (style == DriverStyle::BrakeLine) {
                targetSpeed = player.spec.maxSpeed * (0.92f - std::clamp(curve * 3.55f, 0.0f, 0.35f));
            }
            if (style == DriverStyle::DriftLine) {
                targetSpeed = player.spec.maxSpeed * (1.12f - std::clamp(curve * 1.20f, 0.0f, 0.16f));
            }
            const float laneError =
                std::clamp((dot(player.pos - here.pos, here.normal) - laneTarget) / std::max(1.0f, here.width * 0.5f), -1.8f, 1.8f);
            const float steerGain = style == DriverStyle::NoBrake ? 1.85f : (style == DriverStyle::BrakeLine ? 2.45f : 2.35f);
            const float laneCorrection = style == DriverStyle::NoBrake ? 0.0f : -laneError * (style == DriverStyle::DriftLine ? 0.86f : 0.58f);

            InputState input;
            input.steer = std::clamp(angleError * steerGain + laneCorrection, -1.0f, 1.0f);
            input.throttle = 1.0f;
            if (style == DriverStyle::BrakeLine) {
                input.throttle = speed < targetSpeed + 2.0f ? 1.0f : 0.34f;
                input.brake = (speed > targetSpeed + 5.0f || std::abs(angleError) > 0.68f) ? 0.40f : 0.0f;
            } else if (style == DriverStyle::DriftLine) {
                const bool setupDrift = !player.drifting && curve > 0.052f && speed > 42.0f && std::abs(angleError) > 0.035f;
                const bool holdDrift =
                    player.drifting && player.driftCharge < 0.28f && curve > 0.034f && std::abs(laneError) < 1.20f;
                input.throttle = speed < targetSpeed + 13.0f || player.boostTimer > 0.0f ? 1.0f : 0.72f;
                input.brake = (player.boostTimer <= 0.0f && !setupDrift && !holdDrift &&
                               (speed > targetSpeed + 13.0f || std::abs(angleError) > 0.82f))
                                  ? 0.20f
                                  : 0.0f;
                input.drift = setupDrift || holdDrift;
            }

            updatePlayer(player, input, kFixedDt);
            const TrackPoint tp = track_.pointAtIndex(player.nearest);
            const float lane = std::abs(dot(player.pos - tp.pos, tp.normal));
            const float offroad = std::max(0.0f, lane - tp.width * 0.5f);
            if (offroad > 1.0f) {
                ++result.offroadFrames;
            }
            result.maxOffroad = std::max(result.maxOffroad, offroad);
            if (lane > tp.width * 0.5f + 13.0f) {
                ++result.barrierHits;
            }
            if (player.boostTimer > 0.0f) {
                ++result.boostFrames;
            }
        }
        result.score = carScore(karts_[0], track_.totalLength());
        return result;
    }

    void resetRace() {
        karts_.clear();
        particles_.clear();
        raceTime_ = 0.0f;
        lapTime_ = 0.0f;
        lastLap_ = 0.0f;
        bestLap_ = 0.0f;
        countdown_ = 3.2f;
        const std::array<float, 8> lanes = {-13.0f, 13.0f, -5.5f, 5.5f, -16.0f, 16.0f, -8.0f, 8.0f};
        for (int i = 0; i < 8; ++i) {
            Kart kart;
            kart.spec = cars_[i == 0 ? selectedCar_ : i % static_cast<int>(cars_.size())];
            kart.racer = racers_[i == 0 ? selectedRacer_ : (i * 3) % static_cast<int>(racers_.size())];
            const float rawProgress = 42.0f - static_cast<float>(i / 2) * 24.0f;
            kart.lap = rawProgress < 0.0f ? -1 : 0;
            kart.progress = wrapDistance(rawProgress, track_.totalLength());
            TrackPoint tp = track_.sample(kart.progress);
            kart.lane = lanes[i];
            kart.pos = tp.pos + tp.normal * kart.lane;
            kart.heading = angleOf(tp.tangent);
            kart.vel = tp.tangent * (i == 0 ? 0.0f : 8.0f);
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.aiTempo = 1.02f + 0.035f * static_cast<float>((i * 7) % 5);
            kart.aiAggression = 0.72f + 0.08f * static_cast<float>((i * 5 + 2) % 5);
            kart.aiRisk = 0.38f + 0.11f * static_cast<float>((i * 3 + 1) % 5);
            kart.aiPassBias = (i % 2 == 0 ? -1.0f : 1.0f) * (0.75f + 0.12f * static_cast<float>(i % 3));
            karts_.push_back(kart);
        }
        camera_.yaw = karts_[0].heading;
        caveBlend_ = track_.pointAtIndex(karts_[0].nearest).zone == 3 ? 1.0f : 0.0f;
        updateCamera(1.0f);
        updateAmbient(1.0f);
        computeRacePosition();
    }

    int sampleDelta(int from, int to) const {
        const int count = track_.sampleCount();
        int delta = to - from;
        if (delta > count / 2) {
            delta -= count;
        } else if (delta < -count / 2) {
            delta += count;
        }
        return delta;
    }

    int updateProgress(Kart& kart) {
        const int oldIndex = kart.nearest;
        kart.nearest = track_.nearestIndexNear(kart.pos, oldIndex);
        const int delta = sampleDelta(oldIndex, kart.nearest);
        const TrackPoint& tp = track_.pointAtIndex(kart.nearest);
        kart.progress = tp.progress;
        const int count = track_.sampleCount();
        if (oldIndex > count * 3 / 4 && kart.nearest < count / 4 && delta > 0) {
            kart.lap += 1;
        } else if (oldIndex < count / 4 && kart.nearest > count * 3 / 4 && delta < 0) {
            kart.lap -= 1;
        }
        return delta;
    }

    void resolveKartContacts() {
        constexpr float kKartRadius = 15.5f;
        for (size_t a = 0; a < karts_.size(); ++a) {
            for (size_t b = a + 1; b < karts_.size(); ++b) {
                Vec2 delta = karts_[b].pos - karts_[a].pos;
                float dist = length(delta);
                if (dist < 0.001f) {
                    delta = fromAngle(karts_[a].heading + static_cast<float>(b) * 0.37f);
                    dist = 1.0f;
                }
                const float minDist = kKartRadius * 2.0f;
                if (dist >= minDist) {
                    continue;
                }

                const Vec2 normal = delta / dist;
                const float penetration = minDist - dist;
                const Vec2 push = normal * (penetration * 0.52f);
                karts_[a].pos -= push;
                karts_[b].pos += push;

                const float relSpeed = dot(karts_[b].vel - karts_[a].vel, normal);
                if (relSpeed < 0.0f) {
                    const Vec2 impulse = normal * (-relSpeed * 0.46f);
                    karts_[a].vel -= impulse;
                    karts_[b].vel += impulse;
                }
                const Vec2 tangent{-normal.y, normal.x};
                const float sideRub = dot(karts_[b].vel - karts_[a].vel, tangent);
                const Vec2 rub = tangent * (sideRub * 0.035f);
                karts_[a].vel += rub;
                karts_[b].vel -= rub;
                karts_[a].vel *= 0.985f;
                karts_[b].vel *= 0.985f;
                karts_[a].contactTimer = 0.16f;
                karts_[b].contactTimer = 0.16f;
                updateProgress(karts_[a]);
                updateProgress(karts_[b]);
            }
        }
    }

    void emitParticle(Vec2 pos, Vec2 vel, float life, float size, uint32_t color) {
        if (particles_.size() >= 360) {
            particles_.erase(particles_.begin());
        }
        particles_.push_back({pos, vel, life, life, size, color});
    }

    void updateParticles(float dt) {
        for (Particle& particle : particles_) {
            particle.life -= dt;
            particle.pos += particle.vel * dt;
            particle.vel *= std::exp(-dt * 1.5f);
        }
        particles_.erase(std::remove_if(particles_.begin(), particles_.end(), [](const Particle& particle) { return particle.life <= 0.0f; }),
                         particles_.end());
    }

    void integrateKart(Kart& kart, const InputState& input, float dt) {
        updateProgress(kart);
        const TrackPoint& center = track_.pointAtIndex(kart.nearest);
        kart.lane = dot(kart.pos - center.pos, center.normal);
        const float halfWidth = center.width * 0.5f;
        const float offroad = std::max(0.0f, std::abs(kart.lane) - halfWidth);
        const float surfaceGrip = std::clamp(1.0f - offroad / 56.0f, 0.28f, 1.0f);

        Vec2 forward = fromAngle(kart.heading);
        Vec2 right{-forward.y, forward.x};
        float speed = dot(kart.vel, forward);
        float sideSpeed = dot(kart.vel, right);
        const float absSpeed = std::abs(speed);
        kart.contactTimer = std::max(0.0f, kart.contactTimer - dt);

        const bool wantsDrift = input.drift && std::abs(input.steer) > 0.18f && absSpeed > 28.0f;
        if (wantsDrift) {
            kart.drifting = true;
            kart.boostTimer = 0.0f;
        } else if (kart.drifting && (!input.drift || absSpeed < 24.0f || std::abs(input.steer) < 0.08f)) {
            if (!input.drift && kart.driftCharge > 0.10f && absSpeed > 38.0f) {
                kart.boostPower = kart.driftCharge;
                kart.boostTimer = 0.74f + 2.45f * kart.driftCharge;
            }
            kart.drifting = false;
            kart.driftCharge = 0.0f;
        }

        const float curveDemand = std::clamp(center.curvature * 5.7f + std::abs(input.steer) * 0.34f + offroad / 110.0f, 0.0f, 1.0f);
        const float driftCornerRelief = kart.drifting ? 0.28f : 1.0f;
        if (input.throttle > 0.01f) {
            const float accelFalloff = std::clamp(1.08f - std::abs(speed) / kart.spec.maxSpeed, 0.13f, 1.0f);
            const float cornerAccel = std::clamp(1.0f - curveDemand * 0.48f * driftCornerRelief, 0.46f, 1.0f);
            speed += input.throttle * kart.spec.accel * accelFalloff * cornerAccel * dt;
        }
        if (input.brake > 0.01f) {
            if (speed > 6.0f) {
                speed -= input.brake * kart.spec.brake * (kart.drifting ? 0.16f : 1.0f) * dt;
            } else {
                speed -= input.brake * 55.0f * dt;
            }
        }

        const float cornerRetention = kart.drifting ? 1.08f : (kart.boostTimer > 0.0f ? 0.90f : 0.56f);
        const float cornerLimit = kart.spec.maxSpeed * lerp(1.0f, cornerRetention, curveDemand);
        const float gripOverflow = std::clamp((speed - cornerLimit) / std::max(1.0f, kart.spec.maxSpeed), 0.0f, 1.0f);
        if (speed > cornerLimit) {
            const float turnSign = std::abs(center.signedCurvature) > 0.002f ? std::copysign(1.0f, center.signedCurvature)
                                                                             : std::copysign(1.0f, input.steer == 0.0f ? 1.0f : input.steer);
            sideSpeed -= turnSign * (speed - cornerLimit) * (kart.drifting ? 0.46f : 0.95f) * dt;
            speed -= (speed - cornerLimit) * (kart.drifting ? 0.12f : 0.82f) * dt;
        }
        if (kart.boostTimer > 0.0f && input.throttle > 0.15f && speed > 8.0f) {
            const float boostedMax = kart.spec.maxSpeed * (1.17f + 0.34f * kart.boostPower);
            speed += (118.0f + 154.0f * kart.boostPower) * std::clamp(1.0f - speed / boostedMax, 0.30f, 1.0f) * dt;
            kart.boostTimer = std::max(0.0f, kart.boostTimer - dt);
        } else {
            kart.boostTimer = std::max(0.0f, kart.boostTimer - dt);
        }
        speed -= speed * std::abs(speed) * (0.0018f + gripOverflow * 0.0032f) * dt;
        speed -= speed * offroad * 0.066f * dt;
        speed = std::clamp(speed, -42.0f, kart.spec.maxSpeed * (1.0f + (kart.boostTimer > 0.0f ? 0.10f + 0.36f * kart.boostPower : 0.0f)) *
                                                 (offroad > 1.0f ? 0.56f : 1.0f));

        const float newAbsSpeed = std::abs(speed);
        const float speedFactor = std::clamp(newAbsSpeed / 100.0f, 0.0f, 1.35f);
        float yawRate = input.steer * (1.58f + 1.18f * speedFactor) * surfaceGrip * kart.spec.grip;
        const float highSpeedUndersteer = std::clamp((newAbsSpeed - 58.0f) / 72.0f, 0.0f, 1.0f);
        const float trailBrake = std::clamp(input.brake * std::abs(input.steer) * 1.45f, 0.0f, 1.0f);
        const float liftRotate = std::clamp((0.72f - input.throttle) / 0.72f, 0.0f, 1.0f) * std::abs(input.steer);
        if (kart.drifting) {
            yawRate *= 1.22f * kart.spec.drift;
            sideSpeed += input.steer * (17.0f + newAbsSpeed * 0.30f) * dt;
            sideSpeed *= std::exp(-dt * 1.18f * surfaceGrip);
            const float slipQuality = std::clamp(1.0f - std::abs(std::abs(sideSpeed) - 22.0f) / 38.0f, 0.12f, 1.0f);
            kart.driftCharge = std::clamp(kart.driftCharge + dt * (1.10f + std::abs(input.steer) * 1.92f) * slipQuality, 0.0f, 1.0f);
            if (input.throttle > 0.15f) {
                speed = std::min(speed + input.throttle * (40.0f + 78.0f * kart.driftCharge) * slipQuality * dt,
                                 kart.spec.maxSpeed * 1.22f);
            }
            speed -= speed * 0.00034f * dt;
        } else {
            yawRate *= 1.0f + trailBrake * highSpeedUndersteer * 0.34f + liftRotate * highSpeedUndersteer * 0.22f;
            yawRate *=
                1.0f - std::clamp(highSpeedUndersteer * std::abs(input.steer) * (0.28f + input.throttle * 0.18f) + gripOverflow * 0.92f,
                                   0.0f, 0.68f);
            sideSpeed += input.steer * newAbsSpeed * highSpeedUndersteer * curveDemand * 0.28f * dt;
            sideSpeed *= std::exp(-dt * (3.7f + 1.9f * kart.spec.grip + trailBrake * 2.0f + liftRotate * 0.9f) *
                                  std::max(0.18f, surfaceGrip - gripOverflow * 0.45f));
            kart.driftCharge = std::max(0.0f, kart.driftCharge - dt * 2.0f);
        }
        yawRate *= speed >= -1.0f ? 1.0f : -0.55f;
        kart.heading = wrapAngle(kart.heading + yawRate * dt);

        forward = fromAngle(kart.heading);
        right = {-forward.y, forward.x};
        kart.vel = forward * speed + right * sideSpeed;
        kart.pos += kart.vel * dt;
        kart.slip = sideSpeed;
        kart.fxTimer += dt;
        if (kart.fxTimer >= 0.035f) {
            kart.fxTimer = 0.0f;
            const Vec2 rear = kart.pos - forward * 18.0f;
            const Vec2 puffVel = kart.vel * -0.12f;
            if (kart.boostTimer > 0.0f) {
                emitParticle(rear - right * 6.0f, puffVel - forward * 24.0f, 0.28f, 10.0f, rgb(255, 190, 63));
                emitParticle(rear + right * 6.0f, puffVel - forward * 24.0f, 0.24f, 8.0f, rgb(244, 83, 48));
            } else if (kart.drifting) {
                emitParticle(rear - right * std::copysign(9.0f, sideSpeed == 0.0f ? 1.0f : sideSpeed), puffVel, 0.58f, 13.0f,
                             rgb(218, 226, 218));
            } else if (offroad > 1.0f && absSpeed > 28.0f) {
                emitParticle(rear, puffVel, 0.42f, 12.0f, rgb(220, 177, 95));
            } else if (kart.contactTimer > 0.12f) {
                emitParticle(kart.pos - forward * 8.0f, puffVel, 0.28f, 9.0f, rgb(238, 225, 185));
            }
        }

        updateProgress(kart);
        const TrackPoint& after = track_.pointAtIndex(kart.nearest);
        const float lane = dot(kart.pos - after.pos, after.normal);
        const float hardLimit = after.width * 0.5f + 14.0f;
        if (std::abs(lane) > hardLimit) {
            const float sign = lane > 0.0f ? 1.0f : -1.0f;
            const float excess = std::abs(lane) - hardLimit;
            kart.pos -= after.normal * (sign * excess * 0.92f);
            kart.vel = kart.vel - after.normal * (dot(kart.vel, after.normal) * 1.35f);
            kart.vel *= 0.78f;
            kart.drifting = false;
            updateProgress(kart);
        }
    }

    void updatePlayer(Kart& kart, const InputState& input, float dt) { integrateKart(kart, input, dt); }

    void updateAi(Kart& kart, float dt, int index) {
        const TrackPoint center = track_.sample(kart.progress);
        const float speed = length(kart.vel);
        const float lookahead = 56.0f + speed * (0.50f + kart.aiAggression * 0.08f);
        const TrackPoint target = track_.sample(kart.progress + lookahead);
        float laneTarget = ((index % 3) - 1) * 7.5f + std::sin(kart.progress * 0.006f + index) * (3.0f + kart.aiRisk * 3.5f);
        for (size_t otherIndex = 0; otherIndex < karts_.size(); ++otherIndex) {
            if (otherIndex == static_cast<size_t>(index)) {
                continue;
            }
            const Kart& other = karts_[otherIndex];
            const float ahead = progressAhead(kart.progress, other.progress, track_.totalLength());
            const float behind = progressAhead(other.progress, kart.progress, track_.totalLength());
            if (ahead > 10.0f && ahead < 145.0f && std::abs(other.lane - laneTarget) < 18.0f) {
                laneTarget += kart.aiPassBias * lerp(20.0f, 7.0f, ahead / 145.0f) * (0.75f + kart.aiAggression * 0.35f);
            } else if (behind > 10.0f && behind < 90.0f && std::abs(other.lane - laneTarget) < 15.0f && index != 0) {
                laneTarget -= kart.aiPassBias * lerp(8.0f, 3.0f, behind / 90.0f) * (0.55f + kart.aiAggression * 0.25f);
            }
        }
        const float half = target.width * 0.5f - 13.0f;
        laneTarget = std::clamp(laneTarget, -half, half);
        const Vec2 desired = target.pos + target.normal * laneTarget;
        const Vec2 toTarget = normalize(desired - kart.pos);
        const Vec2 forward = fromAngle(kart.heading);
        const float angleError = std::atan2(cross(forward, toTarget), dot(forward, toTarget));
        const float curveSlow = std::clamp(center.curvature * (2.90f - kart.aiRisk * 0.40f), 0.0f, 0.27f);
        const float pressure =
            index == 0 ? 1.0f
                       : (progressAhead(kart.progress, karts_[0].progress, track_.totalLength()) < 260.0f ? 1.0f + kart.aiAggression * 0.045f
                                                                                                          : 1.0f);
        const float mistake = std::sin(kart.progress * 0.018f + static_cast<float>(index) * 1.7f) > 0.985f ? kart.aiRisk : 0.0f;
        const float targetSpeed = kart.spec.maxSpeed * (0.98f + kart.aiAggression * 0.085f - curveSlow + mistake * 0.035f) *
                                  kart.aiTempo * pressure;

        InputState ai;
        ai.steer = std::clamp(angleError * (1.78f + kart.aiAggression * 0.26f) - mistake * 0.10f * kart.aiPassBias, -1.0f, 1.0f);
        ai.throttle = speed < targetSpeed ? 1.0f : 0.62f;
        ai.brake = (speed > targetSpeed + 18.0f || std::abs(angleError) > 0.86f) ? 0.22f : 0.0f;
        ai.drift = center.curvature > 0.060f && speed > 48.0f && std::abs(angleError) > 0.045f;
        if (ai.drift) {
            ai.brake = 0.0f;
            ai.throttle = 1.0f;
        }
        integrateKart(kart, ai, dt);
    }

    void resetPlayerToTrack() {
        Kart& kart = karts_[0];
        const TrackPoint tp = track_.sample(kart.progress);
        kart.pos = tp.pos;
        kart.heading = angleOf(tp.tangent);
        kart.vel = tp.tangent * 26.0f;
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.progress = track_.pointAtIndex(kart.nearest).progress;
        kart.drifting = false;
        kart.driftCharge = 0.0f;
        kart.boostTimer = 0.0f;
        kart.boostPower = 0.0f;
        kart.slip = 0.0f;
        kart.contactTimer = 0.0f;
        kart.fxTimer = 0.0f;
    }

    void updateCamera(float dt) {
        const Kart& player = karts_[0];
        const float speed = length(player.vel);
        const float speedN = std::clamp(speed / player.spec.maxSpeed, 0.0f, 1.0f);
        const float pullback = smoothstep(speedN);
        const float back = lerp(7.0f, 92.0f, pullback);
        camera_.height = lerp(29.0f, 64.0f, pullback);
        camera_.horizon = lerp(178.0f, 132.0f, pullback);
        camera_.focal = lerp(455.0f, 535.0f, pullback);

        const TrackPoint here = track_.pointAtIndex(player.nearest);
        const TrackPoint look = track_.sample(player.progress + 95.0f + speed * 1.05f);
        const float apexBlend = std::clamp(0.12f + pullback * 0.22f + std::max(here.curvature, look.curvature) * 1.35f, 0.12f, 0.46f);
        const float lookYaw = angleOf(normalize(look.pos - player.pos));
        const float targetYaw = lerpAngle(player.heading, lookYaw, apexBlend) + std::clamp(player.slip * 0.012f, -0.34f, 0.34f);
        camera_.yaw = lerpAngle(camera_.yaw, targetYaw, 1.0f - std::exp(-dt * 6.0f));
        const Vec2 forward = fromAngle(camera_.yaw);
        const Vec2 right{-forward.y, forward.x};
        camera_.pos = player.pos - forward * back + right * std::clamp(player.slip * 0.16f, -9.0f, 9.0f);
    }

    void updateAmbient(float dt) {
        const float target = track_.pointAtIndex(karts_[0].nearest).zone == 3 ? 1.0f : 0.0f;
        caveBlend_ = lerp(caveBlend_, target, 1.0f - std::exp(-dt * 3.6f));
        if (caveBlend_ < 0.015f) {
            caveBlend_ = 0.0f;
        } else if (caveBlend_ > 0.985f) {
            caveBlend_ = 1.0f;
        }
    }

    void computeRacePosition() {
        racePosition_ = 1;
        const float playerScore = carScore(karts_[0], track_.totalLength());
        for (size_t i = 1; i < karts_.size(); ++i) {
            if (carScore(karts_[i], track_.totalLength()) > playerScore) {
                racePosition_ += 1;
            }
        }
    }

    void updateRaceTimers(float dt, int oldPlayerLap) {
        raceTime_ += dt;
        lapTime_ += dt;
        if (karts_[0].lap > oldPlayerLap && lapTime_ > 8.0f) {
            lastLap_ = lapTime_;
            bestLap_ = bestLap_ <= 0.0f ? lapTime_ : std::min(bestLap_, lapTime_);
            lapTime_ = 0.0f;
        }
    }

    void drawRoad(Renderer& r) {
        struct Band {
            ScreenPoint left;
            ScreenPoint right;
            ScreenPoint leftCurb;
            ScreenPoint rightCurb;
            ScreenPoint leftOuter;
            ScreenPoint rightOuter;
            ScreenPoint centerLeft;
            ScreenPoint centerRight;
            TrackPoint tp;
            float distance = 0.0f;
        };

        const auto quadVisible = [](const ScreenPoint& a, const ScreenPoint& b, const ScreenPoint& c, const ScreenPoint& d) {
            return a.visible && b.visible && c.visible && d.visible;
        };

        std::vector<Band> bands;
        float dist = 5.0f;
        for (int i = 0; i < 188; ++i) {
            const float t = static_cast<float>(i) / 187.0f;
            dist += lerp(4.0f, 14.8f, t * t);
            const TrackPoint tp = track_.sample(karts_[0].progress + dist);
            const float half = tp.width * 0.5f;
            const float outer = half + lerp(120.0f, 240.0f, t);
            Band band;
            band.tp = tp;
            band.distance = dist;
            band.left = projectPoint(tp.pos - tp.normal * half, tp.elevation, camera_);
            band.right = projectPoint(tp.pos + tp.normal * half, tp.elevation, camera_);
            band.leftCurb = projectPoint(tp.pos - tp.normal * std::max(0.0f, half - 7.5f), tp.elevation + 0.25f, camera_);
            band.rightCurb = projectPoint(tp.pos + tp.normal * std::max(0.0f, half - 7.5f), tp.elevation + 0.25f, camera_);
            band.leftOuter = projectPoint(tp.pos - tp.normal * outer, tp.elevation - 4.0f, camera_);
            band.rightOuter = projectPoint(tp.pos + tp.normal * outer, tp.elevation - 4.0f, camera_);
            band.centerLeft = projectPoint(tp.pos - tp.normal * 2.2f, tp.elevation + 0.2f, camera_);
            band.centerRight = projectPoint(tp.pos + tp.normal * 2.2f, tp.elevation + 0.2f, camera_);
            bands.push_back(band);
        }

        for (int i = static_cast<int>(bands.size()) - 1; i > 0; --i) {
            const Band& far = bands[static_cast<size_t>(i)];
            const Band& near = bands[static_cast<size_t>(i - 1)];
            if (!quadVisible(far.left, far.right, near.right, near.left)) {
                continue;
            }

            const float fog = std::clamp(1.05f - far.distance / 1350.0f, 0.58f, 1.05f);
            const uint32_t leftTerrain = shade(far.tp.shoulderColor, fog * (far.tp.zone == 3 ? 0.55f : 1.0f));
            const uint32_t rightTerrain = shade(far.tp.shoulderColor, fog * (far.tp.zone == 5 ? 0.82f : 1.0f));
            if (quadVisible(far.leftOuter, far.left, near.left, near.leftOuter)) {
                r.fillQuad(far.leftOuter.p, far.left.p, near.left.p, near.leftOuter.p, leftTerrain);
            }
            if (quadVisible(far.right, far.rightOuter, near.rightOuter, near.right)) {
                r.fillQuad(far.right.p, far.rightOuter.p, near.rightOuter.p, near.right.p, rightTerrain);
            }

            const Vec2 shadowDrop{0.0f, std::clamp(10.0f - far.distance * 0.004f, 3.0f, 10.0f)};
            r.fillQuad(far.left.p + shadowDrop, far.right.p + shadowDrop, near.right.p + shadowDrop, near.left.p + shadowDrop,
                       shade(rgb(78, 50, 40), fog * 0.55f));

            float stripShade = ((static_cast<int>(far.tp.progress / 34.0f) & 1) == 0) ? 1.0f : 0.92f;
            if (far.tp.zone == 1 || far.tp.zone == 5) {
                stripShade = ((static_cast<int>(far.tp.progress / 11.0f) & 1) == 0) ? 1.07f : 0.86f;
            }
            const uint32_t road = shade(far.tp.roadColor, fog * stripShade);
            r.fillQuad(far.left.p, far.right.p, near.right.p, near.left.p, road);

            if (i % 5 == 0 && far.tp.zone != 3) {
                const float laneA = far.tp.width * 0.18f;
                const float laneB = far.tp.width * 0.22f;
                const ScreenPoint farStripeL = projectPoint(far.tp.pos - far.tp.normal * laneB, far.tp.elevation + 0.32f, camera_);
                const ScreenPoint farStripeR = projectPoint(far.tp.pos - far.tp.normal * laneA, far.tp.elevation + 0.32f, camera_);
                const ScreenPoint nearStripeL = projectPoint(near.tp.pos - near.tp.normal * laneB, near.tp.elevation + 0.32f, camera_);
                const ScreenPoint nearStripeR = projectPoint(near.tp.pos - near.tp.normal * laneA, near.tp.elevation + 0.32f, camera_);
                if (quadVisible(farStripeL, farStripeR, nearStripeR, nearStripeL)) {
                    r.fillQuad(farStripeL.p, farStripeR.p, nearStripeR.p, nearStripeL.p, shade(rgb(165, 101, 56), fog * 0.64f));
                }
                const ScreenPoint farStripe2L = projectPoint(far.tp.pos + far.tp.normal * laneA, far.tp.elevation + 0.32f, camera_);
                const ScreenPoint farStripe2R = projectPoint(far.tp.pos + far.tp.normal * laneB, far.tp.elevation + 0.32f, camera_);
                const ScreenPoint nearStripe2L = projectPoint(near.tp.pos + near.tp.normal * laneA, near.tp.elevation + 0.32f, camera_);
                const ScreenPoint nearStripe2R = projectPoint(near.tp.pos + near.tp.normal * laneB, near.tp.elevation + 0.32f, camera_);
                if (quadVisible(farStripe2L, farStripe2R, nearStripe2R, nearStripe2L)) {
                    r.fillQuad(farStripe2L.p, farStripe2R.p, nearStripe2R.p, nearStripe2L.p, shade(rgb(244, 199, 103), fog * 0.58f));
                }
            }

            if (far.tp.curvature > 0.075f && far.tp.zone != 3 && i % 3 == 0 &&
                quadVisible(far.left, far.leftCurb, near.leftCurb, near.left) &&
                quadVisible(far.rightCurb, far.right, near.right, near.rightCurb)) {
                const uint32_t curb = ((static_cast<int>(far.tp.progress / 18.0f) & 1) == 0) ? rgb(236, 67, 57) : rgb(250, 238, 206);
                r.fillQuad(far.left.p, far.leftCurb.p, near.leftCurb.p, near.left.p, shade(curb, fog));
                r.fillQuad(far.rightCurb.p, far.right.p, near.right.p, near.rightCurb.p, shade(curb, fog));
            }
            if ((static_cast<int>(far.tp.progress / 30.0f) & 1) == 0 && far.tp.zone != 3 &&
                quadVisible(far.centerLeft, far.centerRight, near.centerRight, near.centerLeft)) {
                r.fillQuad(far.centerLeft.p, far.centerRight.p, near.centerRight.p, near.centerLeft.p,
                           shade(rgb(248, 229, 148), fog));
            }
            if (i % 4 == 0) {
                r.drawLine(far.left.p, near.left.p, 2, shade(rgb(250, 239, 172), fog * 0.85f));
                r.drawLine(far.right.p, near.right.p, 2, shade(rgb(250, 239, 172), fog * 0.85f));
            }
        }
    }

    void drawProp(Renderer& r, const Prop& prop) {
        const TrackPoint tp = track_.sample(prop.progress);
        const Vec2 world = tp.pos + tp.normal * prop.side;
        const ScreenPoint p = projectPoint(world, tp.elevation, camera_);
        if (!p.visible || p.depth > 900.0f) {
            return;
        }
        float maxScale = 2.65f;
        if (prop.type == Prop::Type::FinishGate) {
            maxScale = 3.15f;
        } else if (prop.type == Prop::Type::DockCrane || prop.type == Prop::Type::Waterfall) {
            maxScale = 2.95f;
        } else if (prop.type == Prop::Type::Hut || prop.type == Prop::Type::SharkSign || prop.type == Prop::Type::MarketStall) {
            maxScale = 2.35f;
        }
        const float s = std::clamp(p.scale * prop.scale, 0.12f, maxScale);
        const int x = static_cast<int>(p.p.x);
        const int y = static_cast<int>(p.p.y);
        const int w = std::max(3, static_cast<int>(18.0f * s));
        const int h = std::max(5, static_cast<int>(42.0f * s));

        switch (prop.type) {
            case Prop::Type::Palm:
                r.drawLine({static_cast<float>(x), static_cast<float>(y)}, {static_cast<float>(x + w / 4), static_cast<float>(y - h)},
                           std::max(2, w / 4), rgb(121, 75, 43));
                for (int i = 0; i < 5; ++i) {
                    const float a = -2.6f + i * 0.62f;
                    const Vec2 top{static_cast<float>(x + w / 4), static_cast<float>(y - h)};
                    const Vec2 tip = top + Vec2{std::cos(a) * w * 1.5f, std::sin(a) * h * 0.55f};
                    r.fillTriangle(top, top + Vec2{static_cast<float>(-w / 3), static_cast<float>(w / 5)}, tip, prop.color);
                }
                break;
            case Prop::Type::Rock:
                r.fillTriangle({static_cast<float>(x - w), static_cast<float>(y)}, {static_cast<float>(x), static_cast<float>(y - h / 2)},
                               {static_cast<float>(x + w), static_cast<float>(y)}, shade(prop.color, 0.9f));
                r.fillTriangle({static_cast<float>(x - w / 2), static_cast<float>(y)}, {static_cast<float>(x + w / 2), static_cast<float>(y - h / 3)},
                               {static_cast<float>(x + w), static_cast<float>(y)}, shade(prop.color, 1.15f));
                break;
            case Prop::Type::Hut:
                r.fillRect(x - w, y - h / 2, w * 2, h / 2, rgb(164, 94, 55));
                r.fillTriangle({static_cast<float>(x - w - 4), static_cast<float>(y - h / 2)},
                               {static_cast<float>(x), static_cast<float>(y - h)},
                               {static_cast<float>(x + w + 4), static_cast<float>(y - h / 2)}, rgb(93, 61, 37));
                break;
            case Prop::Type::Boat:
                r.fillQuad({static_cast<float>(x - w), static_cast<float>(y - h / 3)},
                           {static_cast<float>(x + w), static_cast<float>(y - h / 3)},
                           {static_cast<float>(x + w / 2), static_cast<float>(y)},
                           {static_cast<float>(x - w / 2), static_cast<float>(y)}, rgb(202, 64, 58));
                r.fillTriangle({static_cast<float>(x), static_cast<float>(y - h / 3)},
                               {static_cast<float>(x), static_cast<float>(y - h)},
                               {static_cast<float>(x + w), static_cast<float>(y - h / 2)}, rgb(246, 221, 139));
                break;
            case Prop::Type::Banner:
                r.drawLine({static_cast<float>(x - w), static_cast<float>(y)}, {static_cast<float>(x - w), static_cast<float>(y - h)}, 2,
                           rgb(78, 52, 37));
                r.drawLine({static_cast<float>(x + w), static_cast<float>(y)}, {static_cast<float>(x + w), static_cast<float>(y - h)}, 2,
                           rgb(78, 52, 37));
                r.fillRect(x - w, y - h, w * 2, std::max(3, h / 4), prop.color);
                break;
            case Prop::Type::SharkSign:
                r.drawLine({static_cast<float>(x), static_cast<float>(y)}, {static_cast<float>(x), static_cast<float>(y - h)}, 3,
                           rgb(76, 55, 38));
                r.fillRect(x - w, y - h, w * 2, h / 3, prop.color);
                if (w > 11) {
                    r.drawText(x - w + 3, y - h + 3, "SHARK", std::max(1, w / 18), rgb(245, 244, 218));
                }
                break;
            case Prop::Type::Torch:
                r.drawLine({static_cast<float>(x), static_cast<float>(y)}, {static_cast<float>(x), static_cast<float>(y - h)}, 2,
                           rgb(78, 52, 34));
                r.fillCircle(x, y - h, std::max(2, w / 2), rgb(245, 116, 43));
                r.fillCircle(x, y - h - std::max(1, w / 4), std::max(1, w / 3), rgb(255, 212, 73));
                break;
            case Prop::Type::FinishGate: {
                const int postH = h + h / 2;
                const int span = w * 4;
                const int postW = std::max(3, w / 4);
                r.fillRect(x - span / 2, y - postH, postW, postH, rgb(55, 70, 77));
                r.fillRect(x + span / 2 - postW, y - postH, postW, postH, rgb(55, 70, 77));
                r.fillRect(x - span / 2, y - postH, span, std::max(6, h / 4), prop.color);
                const int tile = std::max(3, h / 9);
                for (int row = 0; row < 3; ++row) {
                    for (int col = 0; col < 12; ++col) {
                        const uint32_t c = ((row + col) & 1) == 0 ? rgb(245, 241, 220) : rgb(21, 28, 34);
                        r.fillRect(x - span / 2 + col * tile, y - postH + row * tile, tile, tile, c);
                    }
                }
                if (w > 10) {
                    r.drawText(x - span / 2 + std::max(4, w / 2), y - postH + std::max(4, h / 3), "HARBOR", std::max(1, w / 18),
                               rgb(255, 239, 169));
                }
                r.fillTriangle({static_cast<float>(x - span / 2), static_cast<float>(y - postH)},
                               {static_cast<float>(x - span / 2 - w), static_cast<float>(y - postH + h / 2)},
                               {static_cast<float>(x - span / 2), static_cast<float>(y - postH + h / 2)}, rgb(236, 67, 57));
                r.fillTriangle({static_cast<float>(x + span / 2), static_cast<float>(y - postH)},
                               {static_cast<float>(x + span / 2 + w), static_cast<float>(y - postH + h / 2)},
                               {static_cast<float>(x + span / 2), static_cast<float>(y - postH + h / 2)}, rgb(255, 205, 70));
                break;
            }
            case Prop::Type::MarketStall:
                r.fillRect(x - w, y - h / 2, w * 2, h / 2, rgb(112, 73, 49));
                r.fillRect(x - w - w / 4, y - h, w * 2 + w / 2, std::max(5, h / 4), prop.color);
                r.fillTriangle({static_cast<float>(x - w - w / 4), static_cast<float>(y - h)},
                               {static_cast<float>(x - w / 2), static_cast<float>(y - h - h / 4)},
                               {static_cast<float>(x), static_cast<float>(y - h)}, shade(prop.color, 1.2f));
                r.fillTriangle({static_cast<float>(x), static_cast<float>(y - h)},
                               {static_cast<float>(x + w / 2), static_cast<float>(y - h - h / 4)},
                               {static_cast<float>(x + w + w / 4), static_cast<float>(y - h)}, shade(prop.color, 0.88f));
                r.fillCircle(x - w / 2, y - h / 4, std::max(2, w / 5), rgb(255, 210, 73));
                r.fillCircle(x + w / 3, y - h / 4, std::max(2, w / 5), rgb(65, 178, 118));
                break;
            case Prop::Type::DockCrane: {
                const Vec2 base{static_cast<float>(x), static_cast<float>(y)};
                const Vec2 top{static_cast<float>(x), static_cast<float>(y - h - h / 2)};
                const Vec2 boom{static_cast<float>(x + w * 3), static_cast<float>(y - h - h / 3)};
                r.drawLine(base, top, std::max(3, w / 4), rgb(93, 68, 50));
                r.drawLine(top, boom, std::max(2, w / 5), prop.color);
                r.drawLine({static_cast<float>(x + w), static_cast<float>(y - h)}, boom, std::max(2, w / 6), shade(prop.color, 0.82f));
                r.drawLine(boom, {boom.x, static_cast<float>(y - h / 2)}, std::max(1, w / 8), rgb(36, 42, 46));
                r.fillRect(static_cast<int>(boom.x - w / 2), y - h / 2, w, std::max(5, h / 4), rgb(163, 94, 47));
                break;
            }
            case Prop::Type::TikiMask:
                r.fillRect(x - w / 2, y - h, w, h, prop.color);
                r.fillTriangle({static_cast<float>(x - w / 2), static_cast<float>(y - h)},
                               {static_cast<float>(x), static_cast<float>(y - h - h / 4)},
                               {static_cast<float>(x + w / 2), static_cast<float>(y - h)}, shade(prop.color, 0.84f));
                r.fillCircle(x - w / 5, y - h * 2 / 3, std::max(2, w / 7), rgb(255, 206, 77));
                r.fillCircle(x + w / 5, y - h * 2 / 3, std::max(2, w / 7), rgb(255, 206, 77));
                r.fillRect(x - w / 4, y - h / 2, w / 2, std::max(3, h / 8), rgb(48, 35, 28));
                r.fillRect(x - w / 3, y - h / 5, w * 2 / 3, std::max(2, h / 12), rgb(239, 221, 158));
                break;
            case Prop::Type::Waterfall:
                r.fillTriangle({static_cast<float>(x - w), static_cast<float>(y)}, {static_cast<float>(x - w / 2), static_cast<float>(y - h)},
                               {static_cast<float>(x + w), static_cast<float>(y)}, rgb(66, 99, 93));
                r.fillRect(x - w / 5, y - h, std::max(3, w / 2), h, prop.color);
                r.fillRect(x - w / 8, y - h, std::max(2, w / 4), h, shade(prop.color, 1.28f));
                r.fillCircle(x, y, std::max(3, w / 2), rgb(204, 240, 224));
                break;
            case Prop::Type::Crystal:
                r.fillTriangle({static_cast<float>(x - w / 2), static_cast<float>(y)}, {static_cast<float>(x), static_cast<float>(y - h)},
                               {static_cast<float>(x + w / 3), static_cast<float>(y)}, prop.color);
                r.fillTriangle({static_cast<float>(x), static_cast<float>(y)}, {static_cast<float>(x + w / 2), static_cast<float>(y - h * 3 / 4)},
                               {static_cast<float>(x + w), static_cast<float>(y)}, shade(prop.color, 0.78f));
                r.fillTriangle({static_cast<float>(x - w), static_cast<float>(y)}, {static_cast<float>(x - w / 2), static_cast<float>(y - h * 2 / 3)},
                               {static_cast<float>(x - w / 5), static_cast<float>(y)}, shade(prop.color, 1.16f));
                break;
            case Prop::Type::Chevron:
                r.drawLine({static_cast<float>(x), static_cast<float>(y)}, {static_cast<float>(x), static_cast<float>(y - h)}, 3,
                           rgb(74, 52, 37));
                r.fillRect(x - w, y - h, w * 2, std::max(6, h / 3), rgb(35, 45, 49));
                if (w > 8) {
                    r.drawText(x - w + 3, y - h + 3, prop.side < 0.0f ? ">>>" : "<<<", std::max(1, w / 15), prop.color);
                }
                break;
        }
    }

    void drawParticles(Renderer& r) {
        for (const Particle& particle : particles_) {
            const ScreenPoint p = projectPoint(particle.pos, 5.0f, camera_);
            if (!p.visible || p.depth > 760.0f) {
                continue;
            }
            const float age = 1.0f - std::clamp(particle.life / std::max(0.001f, particle.maxLife), 0.0f, 1.0f);
            const int radius = std::max(1, static_cast<int>(particle.size * p.scale * (0.75f + age * 0.9f)));
            if (radius > 0 && radius < 60) {
                r.fillCircle(static_cast<int>(p.p.x), static_cast<int>(p.p.y), radius, shade(particle.color, 1.04f - age * 0.36f));
            }
        }
    }

    void drawKartBillboard(Renderer& r, const Kart& kart, const ScreenPoint& p, bool playerHood) {
        const float s = std::clamp(p.scale * (playerHood ? 1.0f : 0.62f), 0.06f, playerHood ? 5.6f : 2.75f);
        const int x = static_cast<int>(p.p.x);
        const int y = static_cast<int>(p.p.y);
        const int w = std::max(7, static_cast<int>((playerHood ? 78.0f : 28.0f) * s));
        const int h = std::max(5, static_cast<int>((playerHood ? 34.0f : 15.0f) * s));
        const int topW = std::max(4, static_cast<int>(w * 0.34f * kart.spec.noseScale));
        const int cabinH = std::max(4, static_cast<int>(h * kart.spec.cabinScale));
        const int wheel = std::max(2, static_cast<int>(h * 0.33f * kart.spec.wheelScale));
        const uint32_t body = mixColor(kart.spec.body, rgb(255, 244, 196), std::clamp(kart.contactTimer * 4.0f, 0.0f, 0.45f));
        const uint32_t helmet = racerColor(kart.racer);
        r.fillQuad({static_cast<float>(x - w / 2), static_cast<float>(y + h / 2)},
                   {static_cast<float>(x + w / 2), static_cast<float>(y + h / 2)},
                   {static_cast<float>(x + w / 3), static_cast<float>(y + h)},
                   {static_cast<float>(x - w / 3), static_cast<float>(y + h)}, rgb(43, 45, 44));
        r.fillCircle(x - w / 3, y + h / 2, wheel, rgb(21, 24, 28));
        r.fillCircle(x + w / 3, y + h / 2, wheel, rgb(21, 24, 28));
        r.fillCircle(x - w / 3, y + h / 3, std::max(2, wheel * 2 / 3), rgb(28, 31, 36));
        r.fillCircle(x + w / 3, y + h / 3, std::max(2, wheel * 2 / 3), rgb(28, 31, 36));
        r.fillQuad({static_cast<float>(x - w / 2), static_cast<float>(y + h / 3)},
                   {static_cast<float>(x + w / 2), static_cast<float>(y + h / 3)},
                   {static_cast<float>(x + topW), static_cast<float>(y - h / 4)},
                   {static_cast<float>(x - topW), static_cast<float>(y - h / 4)}, shade(body, 0.76f));
        r.fillQuad({static_cast<float>(x - w / 2), static_cast<float>(y + h / 4)},
                   {static_cast<float>(x + w / 2), static_cast<float>(y + h / 4)},
                   {static_cast<float>(x + topW), static_cast<float>(y - h / 2)},
                   {static_cast<float>(x - topW), static_cast<float>(y - h / 2)}, body);
        r.fillQuad({static_cast<float>(x - topW * 3 / 4), static_cast<float>(y - h / 2)},
                   {static_cast<float>(x + topW * 3 / 4), static_cast<float>(y - h / 2)},
                   {static_cast<float>(x + topW / 2), static_cast<float>(y - h / 2 - cabinH)},
                   {static_cast<float>(x - topW / 2), static_cast<float>(y - h / 2 - cabinH)}, kart.spec.glass);
        r.fillCircle(x, y - h / 2 - cabinH, std::max(2, h / 4), helmet);
        if (kart.spec.bodyStyle == 3 || kart.spec.bodyStyle == 5) {
            r.fillTriangle({static_cast<float>(x), static_cast<float>(y - h / 2 - cabinH - h / 3)},
                           {static_cast<float>(x + topW), static_cast<float>(y - h / 2)},
                           {static_cast<float>(x - topW / 2), static_cast<float>(y - h / 2)}, shade(kart.spec.accent, 1.06f));
        } else if (kart.spec.bodyStyle == 4 || kart.spec.bodyStyle == 6) {
            r.drawLine({static_cast<float>(x - topW), static_cast<float>(y - h / 2 - cabinH / 2)},
                       {static_cast<float>(x + topW), static_cast<float>(y - h / 2 - cabinH / 2)}, std::max(1, h / 8),
                       shade(kart.spec.accent, 0.82f));
        }
        r.drawLine({static_cast<float>(x - w / 4), static_cast<float>(y - h / 3)},
                   {static_cast<float>(x - topW / 2), static_cast<float>(y - h / 2 - cabinH)}, std::max(1, h / 8), rgb(35, 39, 44));
        r.drawLine({static_cast<float>(x + w / 4), static_cast<float>(y - h / 3)},
                   {static_cast<float>(x + topW / 2), static_cast<float>(y - h / 2 - cabinH)}, std::max(1, h / 8), rgb(35, 39, 44));
        r.fillRect(x - w / 2, y - h / 8, w, std::max(2, h / 5), kart.spec.accent);
        r.fillRect(x - w / 5, y - h / 7, std::max(2, w / 9), std::max(2, h / 7), rgb(255, 238, 150));
        r.fillRect(x + w / 8, y - h / 7, std::max(2, w / 9), std::max(2, h / 7), rgb(255, 238, 150));
    }

    void drawPlayerBuggy(Renderer& r) {
        const Kart& kart = karts_[0];
        const float speedN = std::clamp(length(kart.vel) / kart.spec.maxSpeed, 0.0f, 1.0f);
        const float pullback = smoothstep(speedN);
        const int yBase = static_cast<int>(lerp(575.0f, 516.0f, pullback));
        const int w = static_cast<int>(lerp(256.0f, 142.0f, pullback));
        const int noseW = static_cast<int>(lerp(104.0f, 70.0f, pullback) * kart.spec.noseScale);
        const int h = static_cast<int>(lerp(94.0f, 58.0f, pullback));
        const int slipShift = static_cast<int>(std::clamp(kart.slip * 0.30f, -22.0f, 22.0f) * (1.0f - speedN * 0.28f));
        const int x = kFrameW / 2 + slipShift;
        const int wheel = static_cast<int>(lerp(32.0f, 19.0f, pullback) * kart.spec.wheelScale);
        const int cabinH = static_cast<int>(lerp(44.0f, 30.0f, pullback) * kart.spec.cabinScale);
        const uint32_t body = mixColor(kart.spec.body, rgb(255, 244, 196), std::clamp(kart.contactTimer * 4.0f, 0.0f, 0.45f));
        const uint32_t helmet = racerColor(kart.racer);
        r.fillQuad({static_cast<float>(x - w / 2 - 10), static_cast<float>(yBase - 4)},
                   {static_cast<float>(x + w / 2 + 10), static_cast<float>(yBase - 4)},
                   {static_cast<float>(x + w / 3), static_cast<float>(yBase + 28)},
                   {static_cast<float>(x - w / 3), static_cast<float>(yBase + 28)}, rgb(45, 48, 43));
        r.fillCircle(x - w / 3, yBase - 10, wheel + 3, rgb(15, 18, 22));
        r.fillCircle(x + w / 3, yBase - 10, wheel + 3, rgb(15, 18, 22));
        r.fillCircle(x - w / 3, yBase - 10, std::max(8, wheel / 2), shade(kart.spec.accent, 0.72f));
        r.fillCircle(x + w / 3, yBase - 10, std::max(8, wheel / 2), shade(kart.spec.accent, 0.72f));
        r.fillCircle(x - w / 3, yBase - 10, std::max(5, wheel / 4), rgb(42, 48, 55));
        r.fillCircle(x + w / 3, yBase - 10, std::max(5, wheel / 4), rgb(42, 48, 55));
        r.fillQuad({static_cast<float>(x - w / 2), static_cast<float>(yBase + 4)},
                   {static_cast<float>(x + w / 2), static_cast<float>(yBase + 4)},
                   {static_cast<float>(x + w / 3), static_cast<float>(yBase - h + 8)},
                   {static_cast<float>(x - w / 3), static_cast<float>(yBase - h + 8)}, shade(body, 0.72f));
        r.fillQuad({static_cast<float>(x - w / 2 + 10), static_cast<float>(yBase - 8)},
                   {static_cast<float>(x + w / 2 - 10), static_cast<float>(yBase - 8)},
                   {static_cast<float>(x + noseW / 2), static_cast<float>(yBase - h - 8)},
                   {static_cast<float>(x - noseW / 2), static_cast<float>(yBase - h - 8)}, body);
        r.fillQuad({static_cast<float>(x - noseW / 2), static_cast<float>(yBase - h - 4)},
                   {static_cast<float>(x + noseW / 2), static_cast<float>(yBase - h - 4)},
                   {static_cast<float>(x + noseW / 3), static_cast<float>(yBase - h - cabinH)},
                   {static_cast<float>(x - noseW / 3), static_cast<float>(yBase - h - cabinH)}, kart.spec.glass);
        r.fillCircle(x, yBase - h - cabinH - 2, std::max(10, h / 5), helmet);
        if (kart.spec.bodyStyle == 1 || kart.spec.bodyStyle == 5) {
            r.fillTriangle({static_cast<float>(x), static_cast<float>(yBase - h - cabinH - h / 2)},
                           {static_cast<float>(x + noseW / 2), static_cast<float>(yBase - h - 6)},
                           {static_cast<float>(x - noseW / 3), static_cast<float>(yBase - h - 6)}, shade(kart.spec.accent, 1.1f));
        } else if (kart.spec.bodyStyle == 2 || kart.spec.bodyStyle == 4) {
            r.fillRect(x - w / 2 + 18, yBase - h - 10, w - 36, std::max(5, h / 10), shade(kart.spec.accent, 0.86f));
        } else if (kart.spec.bodyStyle == 6 || kart.spec.bodyStyle == 7) {
            r.drawLine({static_cast<float>(x - w / 3), static_cast<float>(yBase - h - cabinH / 2)},
                       {static_cast<float>(x + w / 3), static_cast<float>(yBase - h - cabinH / 2)}, 5,
                       shade(kart.spec.accent, 0.82f));
        }
        r.fillRect(x - w / 2 + 18, yBase - h / 2, w - 36, std::max(10, h / 7), kart.spec.accent);
        r.fillRect(x - w / 3, yBase - h / 3, std::max(12, w / 6), std::max(8, h / 8), rgb(255, 232, 142));
        r.fillRect(x + w / 6, yBase - h / 3, std::max(12, w / 6), std::max(8, h / 8), rgb(255, 232, 142));
        r.drawLine({static_cast<float>(x - w / 4), static_cast<float>(yBase - h + 2)},
                   {static_cast<float>(x - noseW / 5), static_cast<float>(yBase - h - cabinH - 8)}, 5, rgb(36, 39, 45));
        r.drawLine({static_cast<float>(x + w / 4), static_cast<float>(yBase - h + 2)},
                   {static_cast<float>(x + noseW / 5), static_cast<float>(yBase - h - cabinH - 8)}, 5, rgb(36, 39, 45));
        r.drawLine({static_cast<float>(x - w / 2 + 10), static_cast<float>(yBase - 8)},
                   {static_cast<float>(x + w / 2 - 10), static_cast<float>(yBase - 8)}, 3, shade(kart.spec.accent, 0.78f));
        if (kart.drifting) {
            r.fillCircle(x - w / 2 - 8, yBase - 6, 13, rgb(218, 226, 218));
            r.fillCircle(x + w / 2 + 8, yBase - 6, 13, rgb(218, 226, 218));
        }
    }

    void drawBackdrop(Renderer& r, float cave) {
        const int horizon = static_cast<int>(camera_.horizon);
        if (cave < 0.75f) {
            const uint32_t island = mixColor(rgb(35, 116, 102), rgb(32, 39, 45), cave);
            const uint32_t cloud = mixColor(rgb(250, 245, 217), rgb(77, 82, 86), cave);
            r.fillCircle(126, horizon - 82, 18, shade(cloud, 0.96f));
            r.fillCircle(148, horizon - 88, 26, cloud);
            r.fillCircle(177, horizon - 79, 18, shade(cloud, 0.98f));
            r.fillCircle(606, horizon - 70, 15, shade(cloud, 0.92f));
            r.fillCircle(628, horizon - 78, 23, cloud);
            r.fillCircle(655, horizon - 69, 16, shade(cloud, 0.98f));
            r.fillTriangle({-80.0f, static_cast<float>(horizon + 16)}, {90.0f, static_cast<float>(horizon - 22)},
                           {260.0f, static_cast<float>(horizon + 16)}, shade(island, 0.78f));
            r.fillTriangle({620.0f, static_cast<float>(horizon + 18)}, {774.0f, static_cast<float>(horizon - 30)},
                           {1010.0f, static_cast<float>(horizon + 18)}, shade(island, 0.9f));
            r.fillTriangle({250.0f, static_cast<float>(horizon + 18)}, {390.0f, static_cast<float>(horizon - 14)},
                           {540.0f, static_cast<float>(horizon + 18)}, shade(island, 0.68f));
        }
        if (cave > 0.08f) {
            const uint32_t rock = mixColor(rgb(46, 62, 70), rgb(19, 24, 30), cave);
            r.fillTriangle({80.0f, 0.0f}, {160.0f, static_cast<float>(horizon + 40)}, {245.0f, 0.0f}, rock);
            r.fillTriangle({650.0f, 0.0f}, {745.0f, static_cast<float>(horizon + 56)}, {850.0f, 0.0f}, shade(rock, 1.18f));
            r.fillRect(0, 0, kFrameW, static_cast<int>(54.0f * cave), shade(rock, 0.62f));
        }
    }

    void renderRace(Renderer& r, float fps, bool hasController) {
        const float cave = caveBlend_;
        r.drawSky(mixColor(rgb(74, 187, 232), rgb(24, 36, 54), cave), mixColor(rgb(224, 240, 220), rgb(64, 72, 83), cave),
                  mixColor(rgb(35, 163, 178), rgb(48, 53, 61), cave), static_cast<int>(camera_.horizon));
        drawBackdrop(r, cave);
        if (cave < 0.92f) {
            r.fillCircle(820, 68, 34, mixColor(rgb(255, 220, 93), rgb(54, 56, 63), cave));
            r.fillRect(0, static_cast<int>(camera_.horizon) - 3, kFrameW, 5, mixColor(rgb(32, 136, 162), rgb(38, 47, 57), cave));
            r.fillRect(0, static_cast<int>(camera_.horizon) + 15, kFrameW, 3, mixColor(rgb(76, 207, 208), rgb(45, 58, 66), cave));
            r.fillRect(0, static_cast<int>(camera_.horizon) + 42, kFrameW, 2, mixColor(rgb(23, 132, 151), rgb(34, 42, 50), cave));
        }
        if (cave > 0.05f) {
            r.fillRect(0, 0, kFrameW, 60, mixColor(rgb(74, 187, 232), rgb(24, 30, 39), cave));
            r.fillRect(0, kFrameH - 70, kFrameW, 70, mixColor(rgb(35, 163, 178), rgb(23, 25, 31), cave));
        }

        drawRoad(r);

        struct DrawItem {
            float depth = 0.0f;
            int index = 0;
            bool kart = false;
        };
        std::vector<DrawItem> items;
        for (size_t i = 1; i < karts_.size(); ++i) {
            const float ahead = progressAhead(karts_[0].progress, karts_[i].progress, track_.totalLength());
            if (ahead < 880.0f) {
                const TrackPoint tp = track_.sample(karts_[i].progress);
                const ScreenPoint p = projectPoint(karts_[i].pos, tp.elevation + 6.0f, camera_);
                if (p.visible) {
                    items.push_back({p.depth, static_cast<int>(i), true});
                }
            }
        }
        for (int i = 0; i < static_cast<int>(track_.props().size()); ++i) {
            const float ahead = progressAhead(karts_[0].progress, track_.props()[static_cast<size_t>(i)].progress, track_.totalLength());
            if (ahead < 900.0f) {
                const TrackPoint tp = track_.sample(track_.props()[static_cast<size_t>(i)].progress);
                const ScreenPoint p = projectPoint(tp.pos + tp.normal * track_.props()[static_cast<size_t>(i)].side, tp.elevation, camera_);
                if (p.visible) {
                    items.push_back({p.depth, i, false});
                }
            }
        }
        std::sort(items.begin(), items.end(), [](const DrawItem& a, const DrawItem& b) { return a.depth > b.depth; });
        for (const DrawItem& item : items) {
            if (item.kart) {
                const Kart& kart = karts_[static_cast<size_t>(item.index)];
                const TrackPoint tp = track_.sample(kart.progress);
                drawKartBillboard(r, kart, projectPoint(kart.pos, tp.elevation + 6.0f, camera_), false);
            } else {
                drawProp(r, track_.props()[static_cast<size_t>(item.index)]);
            }
        }

        drawParticles(r);
        drawPlayerBuggy(r);
        renderHud(r, fps, hasController);
    }

    void renderHud(Renderer& r, float fps, bool hasController) {
        const Kart& player = karts_[0];
        const int speed = static_cast<int>(std::round(length(player.vel) * 1.8f));
        r.fillRect(16, 16, 226, 56, rgb(15, 39, 51));
        r.drawText(28, 24, std::to_string(speed) + " KMH", 2, rgb(255, 246, 211));
        r.drawText(28, 46, cars_[selectedCar_].name, 1, rgb(246, 234, 184));
        r.drawText(28, 60, "LAP " + formatRaceTime(lapTime_), 1, rgb(214, 237, 222));
        r.fillRect(740, 16, 202, 56, rgb(15, 39, 51));
        r.drawText(778, 24, "P" + std::to_string(racePosition_) + "/8", 2, rgb(246, 234, 184));
        r.drawText(752, 46, "LAP " + std::to_string(std::max(0, player.lap)), 1, rgb(255, 246, 211));
        r.drawText(752, 60, "BEST " + formatRaceTime(bestLap_ > 0.0f ? bestLap_ : lastLap_), 1, rgb(214, 237, 222));
        r.fillRect(18, 496, 154, 14, rgb(22, 41, 45));
        r.fillRect(21, 499, static_cast<int>(148.0f * player.driftCharge), 8,
                   player.drifting ? rgb(255, 191, 69) : rgb(77, 177, 176));
        r.drawText(22, 516, player.boostTimer > 0.0f ? "BOOST" : (player.drifting ? "DRIFT" : "GRIP"), 1, rgb(252, 240, 200));
        r.drawText(814, 516, std::to_string(static_cast<int>(fps)) + " FPS", 1, rgb(245, 237, 198));
        if (!hasController) {
            r.fillRect(260, 206, 440, 92, rgb(24, 35, 46));
            r.drawText(300, 232, "CONNECT GAMEPAD", 4, rgb(255, 227, 145));
            r.drawText(326, 276, "CONTROLLER ONLY", 2, rgb(245, 237, 198));
        }
        if (countdown_ > 0.0f && hasController) {
            const bool go = countdown_ < 0.55f;
            const std::string text = go ? "GO" : std::to_string(static_cast<int>(std::ceil(countdown_)));
            const int scale = go ? 8 : 10;
            const int width = static_cast<int>(text.size()) * 6 * scale;
            r.fillRect(kFrameW / 2 - width / 2 - 24, 178, width + 48, 92, rgb(18, 44, 54));
            r.drawText(kFrameW / 2 - width / 2, go ? 202 : 188, text, scale, go ? rgb(255, 218, 83) : rgb(255, 244, 204));
        }
    }

    void drawGarageCar(Renderer& r, int cx, int cy, const KartSpec& spec) {
        const int wheel = static_cast<int>(48.0f * spec.wheelScale);
        const int topW = static_cast<int>(115.0f * spec.noseScale);
        const int cabinH = static_cast<int>(65.0f * spec.cabinScale);
        r.fillCircle(cx - 120, cy + 62, wheel, rgb(24, 27, 31));
        r.fillCircle(cx + 120, cy + 62, wheel, rgb(24, 27, 31));
        r.fillCircle(cx - 120, cy + 62, std::max(14, wheel / 2), shade(spec.accent, 0.8f));
        r.fillCircle(cx + 120, cy + 62, std::max(14, wheel / 2), shade(spec.accent, 0.8f));
        r.fillQuad({static_cast<float>(cx - 178), static_cast<float>(cy + 70)},
                   {static_cast<float>(cx + 178), static_cast<float>(cy + 70)},
                   {static_cast<float>(cx + topW), static_cast<float>(cy - 80)},
                   {static_cast<float>(cx - topW), static_cast<float>(cy - 80)}, spec.body);
        r.fillQuad({static_cast<float>(cx - topW * 2 / 3), static_cast<float>(cy - 80)},
                   {static_cast<float>(cx + topW * 2 / 3), static_cast<float>(cy - 80)},
                   {static_cast<float>(cx + topW / 3), static_cast<float>(cy - 80 - cabinH)},
                   {static_cast<float>(cx - topW / 3), static_cast<float>(cy - 80 - cabinH)}, spec.glass);
        if (spec.bodyStyle == 1 || spec.bodyStyle == 3 || spec.bodyStyle == 5) {
            r.fillTriangle({static_cast<float>(cx), static_cast<float>(cy - 80 - cabinH - 52)},
                           {static_cast<float>(cx + topW), static_cast<float>(cy - 80)},
                           {static_cast<float>(cx - topW / 2), static_cast<float>(cy - 80)}, shade(spec.accent, 1.08f));
        } else if (spec.bodyStyle == 4 || spec.bodyStyle == 6 || spec.bodyStyle == 7) {
            r.drawLine({static_cast<float>(cx - 130), static_cast<float>(cy - 80 - cabinH / 2)},
                       {static_cast<float>(cx + 130), static_cast<float>(cy - 80 - cabinH / 2)}, 10, shade(spec.accent, 0.82f));
        }
        r.fillRect(cx - 142, cy - 18, 284, 28, spec.accent);
        r.drawLine({static_cast<float>(cx - 118), static_cast<float>(cy - 76)},
                   {static_cast<float>(cx - topW / 3), static_cast<float>(cy - 80 - cabinH + 6)}, 8, rgb(37, 42, 48));
        r.drawLine({static_cast<float>(cx + 118), static_cast<float>(cy - 76)},
                   {static_cast<float>(cx + topW / 3), static_cast<float>(cy - 80 - cabinH + 6)}, 8, rgb(37, 42, 48));
    }

    void drawGarageThumbnail(Renderer& r, int cx, int cy, const KartSpec& spec, bool selected) {
        if (selected) {
            r.fillRect(cx - 43, cy - 27, 86, 54, rgb(255, 228, 123));
            r.fillRect(cx - 39, cy - 23, 78, 46, rgb(20, 45, 56));
        }
        const int w = 58;
        const int h = 22;
        const int topW = std::max(12, static_cast<int>(22.0f * spec.noseScale));
        const int wheel = std::max(7, static_cast<int>(9.0f * spec.wheelScale));
        r.fillCircle(cx - w / 3, cy + 12, wheel, rgb(19, 22, 26));
        r.fillCircle(cx + w / 3, cy + 12, wheel, rgb(19, 22, 26));
        r.fillQuad({static_cast<float>(cx - w / 2), static_cast<float>(cy + 14)},
                   {static_cast<float>(cx + w / 2), static_cast<float>(cy + 14)},
                   {static_cast<float>(cx + topW), static_cast<float>(cy - h)},
                   {static_cast<float>(cx - topW), static_cast<float>(cy - h)}, spec.body);
        r.fillQuad({static_cast<float>(cx - topW * 2 / 3), static_cast<float>(cy - h)},
                   {static_cast<float>(cx + topW * 2 / 3), static_cast<float>(cy - h)},
                   {static_cast<float>(cx + topW / 3), static_cast<float>(cy - h - 14.0f * spec.cabinScale)},
                   {static_cast<float>(cx - topW / 3), static_cast<float>(cy - h - 14.0f * spec.cabinScale)}, spec.glass);
        if (spec.bodyStyle == 1 || spec.bodyStyle == 3 || spec.bodyStyle == 5) {
            r.fillTriangle({static_cast<float>(cx), static_cast<float>(cy - h - 24)},
                           {static_cast<float>(cx + topW), static_cast<float>(cy - h)},
                           {static_cast<float>(cx - topW / 2), static_cast<float>(cy - h)}, shade(spec.accent, 1.06f));
        } else if (spec.bodyStyle == 4 || spec.bodyStyle == 6 || spec.bodyStyle == 7) {
            r.drawLine({static_cast<float>(cx - 21), static_cast<float>(cy - h - 8)},
                       {static_cast<float>(cx + 21), static_cast<float>(cy - h - 8)}, 3, shade(spec.accent, 0.82f));
        }
        r.fillRect(cx - w / 2 + 4, cy - 6, w - 8, 5, spec.accent);
    }

    void drawDriverPortrait(Renderer& r, int cx, int cy, std::string_view racer) {
        const uint32_t helmet = racerColor(racer);
        r.fillCircle(cx, cy, 42, shade(helmet, 0.78f));
        r.fillCircle(cx, cy - 8, 38, helmet);
        r.fillRect(cx - 34, cy - 2, 68, 18, rgb(37, 45, 53));
        r.fillRect(cx - 25, cy + 4, 20, 8, rgb(122, 219, 230));
        r.fillRect(cx + 5, cy + 4, 20, 8, rgb(122, 219, 230));
        r.fillRect(cx - 22, cy + 28, 44, 24, shade(helmet, 0.62f));
        r.fillTriangle({static_cast<float>(cx - 46), static_cast<float>(cy + 56)},
                       {static_cast<float>(cx), static_cast<float>(cy + 30)},
                       {static_cast<float>(cx + 46), static_cast<float>(cy + 56)}, rgb(37, 45, 53));
    }

    void renderGarage(Renderer& r, float fps, bool hasController) {
        r.drawSky(rgb(71, 184, 232), rgb(229, 241, 217), rgb(43, 166, 175), 210);
        r.fillRect(0, 250, kFrameW, 290, rgb(226, 187, 103));
        r.fillRect(0, 328, kFrameW, 34, rgb(135, 87, 53));
        for (int x = 0; x < kFrameW; x += 70) {
            r.fillRect(x, 328, 4, 34, rgb(88, 58, 43));
        }
        r.fillCircle(826, 76, 38, rgb(255, 220, 93));
        r.drawText(52, 42, "SHARK HARBOR KARTS", 5, rgb(20, 45, 56));
        r.drawText(56, 86, "ONE TRACK / INFINITE LAPS / NO POWERS", 2, rgb(20, 45, 56));
        for (int i = 0; i < static_cast<int>(cars_.size()); ++i) {
            drawGarageThumbnail(r, 136 + i * 92, 164, cars_[static_cast<size_t>(i)], i == selectedCar_);
        }

        drawGarageCar(r, 488, 342, cars_[selectedCar_]);
        r.fillRect(58, 386, 310, 92, rgb(22, 45, 56));
        r.drawText(82, 410, "< " + cars_[selectedCar_].name + " >", 3, rgb(255, 237, 173));
        r.drawText(82, 448, "MAXED DEFAULT", 2, rgb(242, 233, 203));
        r.fillRect(608, 386, 294, 92, rgb(22, 45, 56));
        drawDriverPortrait(r, 654, 422, racers_[selectedRacer_]);
        r.drawText(712, 406, racers_[selectedRacer_], 4, rgb(255, 237, 173));
        r.drawText(712, 452, "DRIVER", 2, rgb(242, 233, 203));

        if (hasController) {
            r.drawText(312, 496, "A/START RACE", 3, rgb(22, 45, 56));
        } else {
            r.fillRect(292, 484, 376, 40, rgb(22, 45, 56));
            r.drawText(318, 496, "CONNECT GAMEPAD", 3, rgb(255, 230, 148));
        }
        r.drawText(816, 16, std::to_string(static_cast<int>(fps)) + " FPS", 2, rgb(22, 45, 56));
    }

    Track track_;
    std::vector<KartSpec> cars_;
    std::vector<std::string> racers_;
    std::vector<Kart> karts_;
    std::vector<Particle> particles_;
    Camera camera_;
    InputState prevInput_;
    Mode mode_ = Mode::Garage;
    int selectedCar_ = 0;
    int selectedRacer_ = 0;
    int racePosition_ = 1;
    float caveBlend_ = 0.0f;
    float raceTime_ = 0.0f;
    float lapTime_ = 0.0f;
    float lastLap_ = 0.0f;
    float bestLap_ = 0.0f;
    float countdown_ = 0.0f;
    bool quitRequested_ = false;
};

SDL_Gamepad* openFirstGamepad() {
    int count = 0;
    SDL_JoystickID* ids = SDL_GetGamepads(&count);
    SDL_Gamepad* pad = nullptr;
    for (int i = 0; i < count && !pad; ++i) {
        if (SDL_IsGamepad(ids[i])) {
            pad = SDL_OpenGamepad(ids[i]);
        }
    }
    SDL_free(ids);
    if (pad) {
        SDL_Joystick* joystick = SDL_GetGamepadJoystick(pad);
        std::cout << "Using gamepad: " << SDL_GetGamepadName(pad);
        if (joystick) {
            std::cout << " (" << SDL_GetNumJoystickAxes(joystick) << " axes, "
                      << SDL_GetNumJoystickButtons(joystick) << " buttons)";
        }
        std::cout << "\n";
    }
    return pad;
}

SDL_Rect letterboxRect(int windowW, int windowH) {
    const float scale = std::min(static_cast<float>(windowW) / kFrameW, static_cast<float>(windowH) / kFrameH);
    SDL_Rect rect;
    rect.w = static_cast<int>(kFrameW * scale);
    rect.h = static_cast<int>(kFrameH * scale);
    rect.x = (windowW - rect.w) / 2;
    rect.y = (windowH - rect.h) / 2;
    return rect;
}

bool hasArg(int argc, char** argv, std::string_view arg) {
    for (int i = 1; i < argc; ++i) {
        if (arg == argv[i]) {
            return true;
        }
    }
    return false;
}

std::optional<std::string> argValue(int argc, char** argv, std::string_view arg) {
    for (int i = 1; i + 1 < argc; ++i) {
        if (arg == argv[i]) {
            return std::string(argv[i + 1]);
        }
    }
    return std::nullopt;
}

bool savePpm(const std::filesystem::path& path, const std::vector<uint32_t>& pixels, int width, int height) {
    std::ofstream out(path, std::ios::binary);
    if (!out) {
        std::cerr << "failed to write " << path << "\n";
        return false;
    }
    out << "P6\n" << width << " " << height << "\n255\n";
    for (uint32_t pixel : pixels) {
        const char rgbBytes[3] = {static_cast<char>((pixel >> 16) & 255), static_cast<char>((pixel >> 8) & 255),
                                  static_cast<char>(pixel & 255)};
        out.write(rgbBytes, sizeof(rgbBytes));
    }
    return static_cast<bool>(out);
}

bool capturePlaytest(const std::filesystem::path& outputDir) {
    std::filesystem::create_directories(outputDir);
    std::vector<uint32_t> pixels(static_cast<size_t>(kFrameW * kFrameH));
    Renderer renderer(pixels, kFrameW, kFrameH);
    Game game;

    game.render(renderer, 60.0f, true);
    if (!savePpm(outputDir / "garage.ppm", pixels, kFrameW, kFrameH)) {
        return false;
    }

    game.startRaceForDiagnostics();
    constexpr int kTotalSteps = 120 * 92;
    const std::array<int, 10> captureSteps = {18, 240, 720, 1440, 2520, 3840, 5400, 7080, 8760, 10920};
    size_t captureIndex = 0;
    for (int step = 0; step <= kTotalSteps; ++step) {
        if (captureIndex < captureSteps.size() && step == captureSteps[captureIndex]) {
            game.render(renderer, 60.0f, true);
            std::ostringstream name;
            name << "race_" << std::setw(2) << std::setfill('0') << captureIndex << ".ppm";
            if (!savePpm(outputDir / name.str(), pixels, kFrameW, kFrameH)) {
                return false;
            }
            ++captureIndex;
        }
        game.updateAutoplay(kFixedDt);
    }

    struct SectionCapture {
        const char* name;
        float phase;
        float speed;
    };
    const std::array<SectionCapture, 7> sections = {{
        {"section_00_beach.ppm", 0.04f, 58.0f},
        {"section_01_dock.ppm", 0.20f, 76.0f},
        {"section_02_market.ppm", 0.35f, 82.0f},
        {"section_03_cave.ppm", 0.50f, 74.0f},
        {"section_04_cliff.ppm", 0.66f, 94.0f},
        {"section_05_pier.ppm", 0.79f, 86.0f},
        {"section_06_lagoon.ppm", 0.92f, 100.0f},
    }};
    int sectionFrames = 0;
    for (const SectionCapture& section : sections) {
        game.placeForSectionCapture(section.phase, section.speed);
        game.render(renderer, 60.0f, true);
        if (!savePpm(outputDir / section.name, pixels, kFrameW, kFrameH)) {
            return false;
        }
        ++sectionFrames;
    }

    std::cout << "captured " << (captureIndex + 1 + sectionFrames) << " frames to " << outputDir << "\n";
    return captureIndex == captureSteps.size();
}

bool perfAudit() {
    std::vector<uint32_t> pixels(static_cast<size_t>(kFrameW * kFrameH));
    Renderer renderer(pixels, kFrameW, kFrameH);
    Game game;

    struct StressSection {
        float phase;
        float speed;
    };
    const std::array<StressSection, 7> sections = {{
        {0.04f, 58.0f},
        {0.20f, 76.0f},
        {0.35f, 82.0f},
        {0.50f, 74.0f},
        {0.66f, 94.0f},
        {0.79f, 86.0f},
        {0.92f, 100.0f},
    }};

    constexpr int kFrames = 420;
    std::vector<double> frameMs;
    frameMs.reserve(kFrames);
    for (int frame = 0; frame < kFrames; ++frame) {
        if (frame % 60 == 0) {
            const StressSection& section = sections[static_cast<size_t>((frame / 60) % static_cast<int>(sections.size()))];
            game.placeForSectionCapture(section.phase, section.speed);
        }
        const auto start = std::chrono::steady_clock::now();
        game.updateAutoplay(kFixedDt);
        game.render(renderer, 60.0f, true);
        const auto end = std::chrono::steady_clock::now();
        frameMs.push_back(std::chrono::duration<double, std::milli>(end - start).count());
    }

    std::sort(frameMs.begin(), frameMs.end());
    const auto percentile = [&frameMs](double p) {
        const size_t index = std::min(frameMs.size() - 1, static_cast<size_t>(std::round((frameMs.size() - 1) * p)));
        return frameMs[index];
    };
    double total = 0.0;
    for (double ms : frameMs) {
        total += ms;
    }
    const double avg = total / static_cast<double>(frameMs.size());
    const double p50 = percentile(0.50);
    const double p95 = percentile(0.95);
    const double max = frameMs.back();
    const bool ok = p95 <= 16.67 && max <= 28.0;

    std::cout << std::fixed << std::setprecision(3)
              << "perf-audit frames=" << kFrames << " avg_ms=" << avg << " p50_ms=" << p50 << " p95_ms=" << p95
              << " max_ms=" << max << " p95_fps=" << (1000.0 / std::max(0.001, p95)) << "\n";
    if (!ok) {
        std::cerr << "perf-audit failed\n";
    }
    return ok;
}

}  // namespace

int runHarborKarts(int argc, char** argv) {
    Game game;
    if (hasArg(argc, argv, "--self-test")) {
        const bool ok = game.selfTest();
        std::cout << (ok ? "self-test passed\n" : "self-test failed\n");
        return ok ? 0 : 1;
    }
    if (hasArg(argc, argv, "--race-audit")) {
        const bool ok = game.raceAudit();
        std::cout << (ok ? "race-audit passed\n" : "race-audit failed\n");
        return ok ? 0 : 1;
    }
    if (const auto outputDir = argValue(argc, argv, "--capture-playtest")) {
        const bool ok = capturePlaytest(*outputDir);
        std::cout << (ok ? "capture-playtest passed\n" : "capture-playtest failed\n");
        return ok ? 0 : 1;
    }
    if (hasArg(argc, argv, "--perf-audit")) {
        const bool ok = perfAudit();
        std::cout << (ok ? "perf-audit passed\n" : "perf-audit failed\n");
        return ok ? 0 : 1;
    }

    const bool devKeyboard = hasArg(argc, argv, "--dev-keyboard");
    const bool smokeRender = hasArg(argc, argv, "--smoke-render");
    const bool diagnoseController = hasArg(argc, argv, "--diagnose-controller");
    const bool windowed = hasArg(argc, argv, "--windowed") || smokeRender || diagnoseController;

    SDL_SetAppMetadata("Formula Buggy", "0.3.0", "local.formula.buggy");
    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMEPAD | SDL_INIT_EVENTS)) {
        std::cerr << "SDL_Init failed: " << SDL_GetError() << "\n";
        return 1;
    }

    SDL_Window* window = SDL_CreateWindow("Formula Buggy", 1280, 720, windowed ? SDL_WINDOW_RESIZABLE : SDL_WINDOW_FULLSCREEN);
    if (!window) {
        std::cerr << "SDL_CreateWindow failed: " << SDL_GetError() << "\n";
        SDL_Quit();
        return 1;
    }
    SDL_SetWindowMinimumSize(window, 960, 540);

    std::vector<uint32_t> pixels(static_cast<size_t>(kFrameW * kFrameH));
    Renderer renderer(pixels, kFrameW, kFrameH);
    SDL_Surface* frame =
        SDL_CreateSurfaceFrom(kFrameW, kFrameH, SDL_PIXELFORMAT_XRGB8888, pixels.data(), kFrameW * static_cast<int>(sizeof(uint32_t)));
    if (!frame) {
        std::cerr << "SDL_CreateSurfaceFrom failed: " << SDL_GetError() << "\n";
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    SDL_Gamepad* pad = openFirstGamepad();
    auto previous = std::chrono::steady_clock::now();
    auto fpsStamp = previous;
    int frames = 0;
    int totalFrames = 0;
    float fps = 60.0f;
    double accumulator = 0.0;
    bool running = true;
    auto diagnosticStamp = previous;

    while (running && !game.quitRequested()) {
        const auto frameStart = std::chrono::steady_clock::now();
        const double frameTime = std::chrono::duration<double>(frameStart - previous).count();
        previous = frameStart;
        accumulator = std::min(0.12, accumulator + frameTime);

        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_EVENT_QUIT) {
                running = false;
            }
            if (devKeyboard && event.type == SDL_EVENT_KEY_DOWN && event.key.key == SDLK_ESCAPE) {
                running = false;
            }
            if (event.type == SDL_EVENT_GAMEPAD_REMOVED && pad && event.gdevice.which == SDL_GetGamepadID(pad)) {
                SDL_CloseGamepad(pad);
                pad = nullptr;
            }
        }

        SDL_UpdateGamepads();
        if (!pad || !SDL_GamepadConnected(pad)) {
            if (pad) {
                SDL_CloseGamepad(pad);
                pad = nullptr;
            }
            pad = openFirstGamepad();
        }

        const bool hasController = pad != nullptr || devKeyboard;
        const InputState input = readGamepad(pad, devKeyboard);
        if (diagnoseController && std::chrono::duration<double>(frameStart - diagnosticStamp).count() >= 0.25) {
            printControllerSnapshot(pad);
            diagnosticStamp = frameStart;
        }
        int steps = 0;
        while (accumulator >= kFixedDt && steps < 8) {
            game.update(kFixedDt, input, hasController);
            accumulator -= kFixedDt;
            ++steps;
        }

        game.render(renderer, fps, pad != nullptr);

        SDL_Surface* screen = SDL_GetWindowSurface(window);
        if (screen) {
            SDL_FillSurfaceRect(screen, nullptr, 0x00000000);
            const SDL_Rect dst = letterboxRect(screen->w, screen->h);
            SDL_BlitSurfaceScaled(frame, nullptr, screen, &dst, SDL_SCALEMODE_LINEAR);
            SDL_UpdateWindowSurface(window);
        }

        ++frames;
        ++totalFrames;
        if (smokeRender && totalFrames >= 12) {
            running = false;
        }
        if (diagnoseController && totalFrames >= 1800) {
            running = false;
        }
        const auto now = std::chrono::steady_clock::now();
        const double fpsElapsed = std::chrono::duration<double>(now - fpsStamp).count();
        if (fpsElapsed >= 0.5) {
            fps = static_cast<float>(frames / fpsElapsed);
            frames = 0;
            fpsStamp = now;
        }

        const double used = std::chrono::duration<double>(std::chrono::steady_clock::now() - frameStart).count();
        if (used < 1.0 / 60.0) {
            std::this_thread::sleep_for(std::chrono::duration<double>((1.0 / 60.0) - used));
        }
    }

    if (pad) {
        SDL_CloseGamepad(pad);
    }
    SDL_DestroySurface(frame);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
