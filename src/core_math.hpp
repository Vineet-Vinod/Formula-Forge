#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

constexpr float kPi = 3.14159265358979323846f;
constexpr float kTwoPi = 2.0f * kPi;

constexpr uint32_t rgb(uint8_t r, uint8_t g, uint8_t b) {
    return (static_cast<uint32_t>(r) << 16) | (static_cast<uint32_t>(g) << 8) |
           static_cast<uint32_t>(b);
}

inline float lerp(float a, float b, float t) { return a + (b - a) * t; }

inline uint32_t shade(uint32_t color, float amount) {
    amount = std::clamp(amount, 0.0f, 2.0f);
    const auto channel = [amount](uint32_t v) {
        return static_cast<uint8_t>(std::clamp(static_cast<float>(v) * amount, 0.0f, 255.0f));
    };
    return rgb(channel((color >> 16) & 255), channel((color >> 8) & 255), channel(color & 255));
}

inline uint32_t mixColor(uint32_t a, uint32_t b, float t) {
    t = std::clamp(t, 0.0f, 1.0f);
    const auto channel = [t](uint32_t av, uint32_t bv) {
        return static_cast<uint8_t>(
            std::clamp(static_cast<float>(av) + (static_cast<float>(bv) - static_cast<float>(av)) * t, 0.0f, 255.0f));
    };
    return rgb(channel((a >> 16) & 255, (b >> 16) & 255), channel((a >> 8) & 255, (b >> 8) & 255),
               channel(a & 255, b & 255));
}

inline float smoothstep(float t) {
    t = std::clamp(t, 0.0f, 1.0f);
    return t * t * (3.0f - 2.0f * t);
}

inline float wrapAngle(float angle) {
    while (angle <= -kPi) {
        angle += kTwoPi;
    }
    while (angle > kPi) {
        angle -= kTwoPi;
    }
    return angle;
}

inline float lerpAngle(float a, float b, float t) {
    return a + wrapAngle(b - a) * std::clamp(t, 0.0f, 1.0f);
}

struct Vec2 {
    float x = 0.0f;
    float y = 0.0f;

    Vec2() = default;
    Vec2(float xIn, float yIn) : x(xIn), y(yIn) {}

    Vec2 operator+(Vec2 other) const { return {x + other.x, y + other.y}; }
    Vec2 operator-(Vec2 other) const { return {x - other.x, y - other.y}; }
    Vec2 operator*(float scalar) const { return {x * scalar, y * scalar}; }
    Vec2 operator/(float scalar) const { return {x / scalar, y / scalar}; }
    Vec2& operator+=(Vec2 other) {
        x += other.x;
        y += other.y;
        return *this;
    }
    Vec2& operator-=(Vec2 other) {
        x -= other.x;
        y -= other.y;
        return *this;
    }
    Vec2& operator*=(float scalar) {
        x *= scalar;
        y *= scalar;
        return *this;
    }
};

inline float dot(Vec2 a, Vec2 b) { return a.x * b.x + a.y * b.y; }
inline float cross(Vec2 a, Vec2 b) { return a.x * b.y - a.y * b.x; }
inline float lengthSq(Vec2 v) { return dot(v, v); }
inline float length(Vec2 v) { return std::sqrt(lengthSq(v)); }

inline Vec2 normalize(Vec2 v) {
    const float len = length(v);
    if (len < 0.0001f) {
        return {1.0f, 0.0f};
    }
    return v / len;
}

inline Vec2 lerp(Vec2 a, Vec2 b, float t) { return a + (b - a) * t; }
inline Vec2 fromAngle(float angle) { return {std::cos(angle), std::sin(angle)}; }
inline float angleOf(Vec2 v) { return std::atan2(v.y, v.x); }

inline float wrapDistance(float value, float total) {
    while (value < 0.0f) {
        value += total;
    }
    while (value >= total) {
        value -= total;
    }
    return value;
}

inline float progressAhead(float from, float to, float total) {
    float delta = to - from;
    while (delta < 0.0f) {
        delta += total;
    }
    while (delta >= total) {
        delta -= total;
    }
    return delta;
}
