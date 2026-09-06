#pragma once

#include <array>
#include <limits>
#include <span>
#include "core_math.hpp"

// Geometry uses the same simulation frame as the exported track: (x, -y) * 17.
struct AuthoredBarrierSegment {
    Vec2 a, b;
    float bottom, top, halfThickness;
};
struct AuthoredSurfaceTriangle {
    Vec2 a, b, c;
    bool asphalt;
};
struct AuthoredBarrierHit {
    bool hit = false;
    float time = 1.0f;
    Vec2 normal;
    float penetration = 0.0f;
};

// Continuous separating-axis test for a moving car rectangle and a finite wall.
// Unlike a distance-to-line clamp, this preserves openings and wall endpoints.
inline AuthoredBarrierHit sweepAuthoredBarrier(
    const AuthoredBarrierSegment& wall, Vec2 start, Vec2 end, Vec2 forward,
    float halfLength, float halfWidth, float bottom, float height) {
    AuthoredBarrierHit result;
    if (bottom + height < wall.bottom || bottom > wall.top) return result;
    const float radius = halfLength + halfWidth + wall.halfThickness;
    if (std::max(start.x, end.x) + radius < std::min(wall.a.x, wall.b.x) ||
        std::min(start.x, end.x) - radius > std::max(wall.a.x, wall.b.x) ||
        std::max(start.y, end.y) + radius < std::min(wall.a.y, wall.b.y) ||
        std::min(start.y, end.y) - radius > std::max(wall.a.y, wall.b.y)) return result;
    const float wallLength = length(wall.b-wall.a);
    if (wallLength < 0.001f) return result;
    const Vec2 tangent = (wall.b-wall.a)/wallLength;
    const Vec2 normal{-tangent.y, tangent.x};
    const Vec2 lateral{-forward.y, forward.x};
    const Vec2 center = (wall.a+wall.b)*0.5f;
    const Vec2 movement = end-start;
    const std::array<Vec2,4> axes{normal, tangent, forward, lateral};
    float enter = -std::numeric_limits<float>::infinity();
    float leave = std::numeric_limits<float>::infinity();
    float minimumDepth = std::numeric_limits<float>::infinity();
    Vec2 enterNormal, overlapNormal;
    bool initiallyInside = true;
    for (Vec2 axis : axes) {
        const float extent = halfLength*std::abs(dot(forward,axis)) +
            halfWidth*std::abs(dot(lateral,axis)) +
            wallLength*0.5f*std::abs(dot(tangent,axis)) +
            wall.halfThickness*std::abs(dot(normal,axis));
        const float distance = dot(start-center,axis);
        const float velocity = dot(movement,axis);
        const float depth = extent-std::abs(distance);
        initiallyInside = initiallyInside && depth > 0.001f;
        if (depth < minimumDepth) {
            minimumDepth = depth;
            overlapNormal = axis*(distance >= 0 ? 1.0f : -1.0f);
        }
        if (std::abs(velocity) < 0.00001f) {
            if (depth < 0) return result;
            continue;
        }
        float first = (-extent-distance)/velocity;
        float last = (extent-distance)/velocity;
        if (first > last) std::swap(first,last);
        if (first > enter) {
            enter = first;
            enterNormal = axis*(velocity > 0 ? -1.0f : 1.0f);
        }
        leave = std::min(leave,last);
        if (enter > leave) return result;
    }
    if (initiallyInside) {
        return {true, 0.0f, overlapNormal, minimumDepth};
    }
    if (enter < -0.00001f || enter > 1.0f || leave < 0.0f) return result;
    return {true, std::max(0.0f,enter), enterNormal, 0.0f};
}

inline AuthoredBarrierHit firstAuthoredBarrierHit(
    std::span<const AuthoredBarrierSegment> walls, Vec2 start, Vec2 end,
    Vec2 forward, float halfLength, float halfWidth, float bottom, float height) {
    AuthoredBarrierHit first;
    for (const auto& wall : walls) {
        const auto hit = sweepAuthoredBarrier(wall,start,end,forward,halfLength,halfWidth,bottom,height);
        if (hit.hit && (!first.hit || hit.time < first.time ||
            (hit.time == first.time && hit.penetration > first.penetration))) first = hit;
    }
    return first;
}

// Conservative rectangle separation for telemetry; the minimum is over real walls.
inline float authoredBarrierClearance(std::span<const AuthoredBarrierSegment> walls,
    Vec2 position, Vec2 forward, float halfLength, float halfWidth, float bottom, float height) {
    float nearest = std::numeric_limits<float>::max();
    const Vec2 lateral{-forward.y,forward.x};
    for (const auto& wall:walls) {
        if (bottom+height<wall.bottom || bottom>wall.top) continue;
        const Vec2 tangent=normalize(wall.b-wall.a), normal{-tangent.y,tangent.x};
        const Vec2 delta=position-(wall.a+wall.b)*.5f;
        float gap=-std::numeric_limits<float>::max();
        for (Vec2 axis:std::array<Vec2,4>{normal,tangent,forward,lateral}) {
            const float extent=halfLength*std::abs(dot(forward,axis))+
                halfWidth*std::abs(dot(lateral,axis))+
                length(wall.b-wall.a)*.5f*std::abs(dot(tangent,axis))+
                wall.halfThickness*std::abs(dot(normal,axis));
            gap=std::max(gap,std::abs(dot(delta,axis))-extent);
        }
        nearest=std::min(nearest,gap);
    }
    return nearest;
}

inline bool insideAuthoredSurface(Vec2 p, const AuthoredSurfaceTriangle& t) {
    if (p.x < std::min({t.a.x,t.b.x,t.c.x}) || p.x > std::max({t.a.x,t.b.x,t.c.x}) ||
        p.y < std::min({t.a.y,t.b.y,t.c.y}) || p.y > std::max({t.a.y,t.b.y,t.c.y})) return false;
    const float a = cross(t.b-t.a,p-t.a), b = cross(t.c-t.b,p-t.b), c = cross(t.a-t.c,p-t.c);
    return (a >= -0.001f && b >= -0.001f && c >= -0.001f) ||
           (a <= 0.001f && b <= 0.001f && c <= 0.001f);
}
