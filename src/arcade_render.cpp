#include "arcade_render.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#if defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
#endif
#include <raymath.h>
#if defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

#include "glb_asset.hpp"

namespace arcade_render {
namespace {

constexpr float kPi = 3.14159265358979323846f;
constexpr float kTwoPi = 2.0f * kPi;

constexpr const char* kLightingVertexShader = R"GLSL(#version 100
attribute vec3 vertexPosition;
attribute vec2 vertexTexCoord;
attribute vec3 vertexNormal;
attribute vec4 vertexColor;

uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;

varying vec3 fragPosition;
varying vec2 fragTexCoord;
varying vec3 fragNormal;
varying vec4 fragColor;

void main()
{
    vec4 worldPosition = matModel*vec4(vertexPosition, 1.0);
    fragPosition = worldPosition.xyz;
    fragTexCoord = vertexTexCoord;
    fragNormal = normalize((matNormal*vec4(vertexNormal, 0.0)).xyz);
    fragColor = vertexColor;
    gl_Position = mvp*vec4(vertexPosition, 1.0);
}
)GLSL";

constexpr const char* kLightingFragmentShader = R"GLSL(#version 100
precision mediump float;

varying vec3 fragPosition;
varying vec2 fragTexCoord;
varying vec3 fragNormal;
varying vec4 fragColor;

uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec3 viewPos;
uniform vec3 sunDirection;
uniform vec3 sunColor;
uniform vec3 skyAmbient;
uniform vec3 groundAmbient;
uniform vec3 fogColor;
uniform float fogStart;
uniform float fogEnd;
uniform float materialGloss;
uniform float exposure;

void main()
{
    vec4 texel = texture2D(texture0, fragTexCoord);
    vec4 base = texel*colDiffuse*fragColor;
    vec3 normal = normalize(fragNormal);
    vec3 sun = normalize(sunDirection);
    vec3 viewDirection = normalize(viewPos - fragPosition);

    float upFactor = normal.y*0.5 + 0.5;
    vec3 ambient = mix(groundAmbient, skyAmbient, upFactor);
    float direct = max(dot(normal, sun), 0.0);
    float wrapped = smoothstep(-0.12, 0.72, direct);
    vec3 halfDirection = normalize(sun + viewDirection);
    float shine = mix(12.0, 52.0, materialGloss);
    float specular = pow(max(dot(normal, halfDirection), 0.0), shine)*direct*materialGloss;
    float rim = pow(1.0 - max(dot(normal, viewDirection), 0.0), 3.0)*0.11;

    // A broad fill keeps stylized vehicle silhouettes readable on shaded track
    // sections without flattening their sun-facing planes.
    vec3 lit = base.rgb*(ambient + vec3(0.075) + sunColor*(0.10 + 0.61*wrapped));
    lit += sunColor*specular*0.48 + skyAmbient*rim;
    lit *= exposure;
    lit = lit/(vec3(0.92) + lit*0.22);

    float distanceToCamera = length(viewPos - fragPosition);
    float fogAmount = smoothstep(fogStart, max(fogStart + 0.01, fogEnd), distanceToCamera);
    vec3 finalColor = mix(lit, fogColor, fogAmount);
    gl_FragColor = vec4(finalColor, base.a);
}
)GLSL";

float clamp01(float value) {
    return std::clamp(value, 0.0f, 1.0f);
}

Color shade(Color color, float factor) {
    const auto channel = [factor](unsigned char value) {
        return static_cast<unsigned char>(std::clamp(static_cast<float>(value) * factor, 0.0f, 255.0f));
    };
    return {channel(color.r), channel(color.g), channel(color.b), color.a};
}

Color mixColor(Color a, Color b, float amount) {
    amount = clamp01(amount);
    const auto channel = [amount](unsigned char av, unsigned char bv) {
        return static_cast<unsigned char>(static_cast<float>(av) +
                                          (static_cast<float>(bv) - static_cast<float>(av)) * amount);
    };
    return {channel(a.r, b.r), channel(a.g, b.g), channel(a.b, b.b), channel(a.a, b.a)};
}

Vector3 add(Vector3 a, Vector3 b) {
    return {a.x + b.x, a.y + b.y, a.z + b.z};
}

Vector3 subtract(Vector3 a, Vector3 b) {
    return {a.x - b.x, a.y - b.y, a.z - b.z};
}

Vector3 multiply(Vector3 value, float scale) {
    return {value.x * scale, value.y * scale, value.z * scale};
}

float magnitude(Vector3 value) {
    return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
}

Vector3 normalized(Vector3 value, Vector3 fallback = {0.0f, 1.0f, 0.0f}) {
    const float length = magnitude(value);
    if (length < 0.00001f) {
        return fallback;
    }
    return multiply(value, 1.0f / length);
}

Vector3 cross(Vector3 a, Vector3 b) {
    return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}

Matrix compose(Vector3 position, Vector3 scale, Vector3 rotation = {}) {
    Matrix result = MatrixScale(scale.x, scale.y, scale.z);
    result = MatrixMultiply(result, MatrixRotateX(rotation.x));
    result = MatrixMultiply(result, MatrixRotateZ(rotation.z));
    result = MatrixMultiply(result, MatrixRotateY(rotation.y));
    return MatrixMultiply(result, MatrixTranslate(position.x, position.y, position.z));
}

Matrix childTransform(Matrix local, Matrix parent) {
    return MatrixMultiply(local, parent);
}

Vector3 colorVector(Color color) {
    return {static_cast<float>(color.r) / 255.0f, static_cast<float>(color.g) / 255.0f,
            static_cast<float>(color.b) / 255.0f};
}

struct MeshBuilder {
    std::vector<float> positions;
    std::vector<float> normals;
    std::vector<float> texcoords;
    std::vector<unsigned short> indices;

    unsigned short vertex(Vector3 position, Vector3 normal, Vector2 uv = {}) {
        const auto index = static_cast<unsigned short>(positions.size() / 3);
        positions.insert(positions.end(), {position.x, position.y, position.z});
        normals.insert(normals.end(), {normal.x, normal.y, normal.z});
        texcoords.insert(texcoords.end(), {uv.x, uv.y});
        return index;
    }

    void triangle(Vector3 a, Vector3 b, Vector3 c, Vector2 ua = {}, Vector2 ub = {}, Vector2 uc = {}) {
        const Vector3 normal = normalized(cross(subtract(b, a), subtract(c, a)));
        const unsigned short first = vertex(a, normal, ua);
        indices.insert(indices.end(), {first, static_cast<unsigned short>(first + 1), static_cast<unsigned short>(first + 2)});
        vertex(b, normal, ub);
        vertex(c, normal, uc);
    }

    void quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d) {
        const Vector3 normal = normalized(cross(subtract(b, a), subtract(c, a)));
        const unsigned short first = vertex(a, normal, {0.0f, 1.0f});
        vertex(b, normal, {1.0f, 1.0f});
        vertex(c, normal, {1.0f, 0.0f});
        vertex(d, normal, {0.0f, 0.0f});
        indices.insert(indices.end(), {first, static_cast<unsigned short>(first + 1), static_cast<unsigned short>(first + 2), first,
                                       static_cast<unsigned short>(first + 2), static_cast<unsigned short>(first + 3)});
    }

    void smoothQuad(unsigned short a, unsigned short b, unsigned short c, unsigned short d) {
        indices.insert(indices.end(), {a, b, c, a, c, d});
    }

    Mesh upload() {
        Mesh mesh{};
        mesh.vertexCount = static_cast<int>(positions.size() / 3);
        mesh.triangleCount = static_cast<int>(indices.size() / 3);
        mesh.vertices = static_cast<float*>(MemAlloc(positions.size() * sizeof(float)));
        mesh.normals = static_cast<float*>(MemAlloc(normals.size() * sizeof(float)));
        mesh.texcoords = static_cast<float*>(MemAlloc(texcoords.size() * sizeof(float)));
        mesh.indices = static_cast<unsigned short*>(MemAlloc(indices.size() * sizeof(unsigned short)));
        std::copy(positions.begin(), positions.end(), mesh.vertices);
        std::copy(normals.begin(), normals.end(), mesh.normals);
        std::copy(texcoords.begin(), texcoords.end(), mesh.texcoords);
        std::copy(indices.begin(), indices.end(), mesh.indices);
        UploadMesh(&mesh, false);
        return mesh;
    }
};

void addUnitBox(MeshBuilder& builder) {
    constexpr float n = -0.5f;
    constexpr float p = 0.5f;
    builder.quad({n, p, n}, {n, p, p}, {p, p, p}, {p, p, n});
    builder.quad({n, n, n}, {p, n, n}, {p, n, p}, {n, n, p});
    builder.quad({n, n, p}, {p, n, p}, {p, p, p}, {n, p, p});
    builder.quad({p, n, n}, {n, n, n}, {n, p, n}, {p, p, n});
    builder.quad({p, n, p}, {p, n, n}, {p, p, n}, {p, p, p});
    builder.quad({n, n, n}, {n, n, p}, {n, p, p}, {n, p, n});
}

Mesh makeUnitBox() {
    MeshBuilder builder;
    addUnitBox(builder);
    return builder.upload();
}

Mesh makeCylinder(int sides) {
    MeshBuilder builder;
    const unsigned short bottomCenter = builder.vertex({0.0f, -0.5f, 0.0f}, {0.0f, -1.0f, 0.0f}, {0.5f, 0.5f});
    const unsigned short topCenter = builder.vertex({0.0f, 0.5f, 0.0f}, {0.0f, 1.0f, 0.0f}, {0.5f, 0.5f});
    std::vector<unsigned short> bottom;
    std::vector<unsigned short> top;
    std::vector<unsigned short> sideBottom;
    std::vector<unsigned short> sideTop;
    for (int i = 0; i <= sides; ++i) {
        const float angle = kTwoPi * static_cast<float>(i) / static_cast<float>(sides);
        const float x = std::cos(angle);
        const float z = std::sin(angle);
        bottom.push_back(builder.vertex({x, -0.5f, z}, {0.0f, -1.0f, 0.0f}, {x * 0.5f + 0.5f, z * 0.5f + 0.5f}));
        top.push_back(builder.vertex({x, 0.5f, z}, {0.0f, 1.0f, 0.0f}, {x * 0.5f + 0.5f, z * 0.5f + 0.5f}));
        sideBottom.push_back(builder.vertex({x, -0.5f, z}, {x, 0.0f, z}, {static_cast<float>(i) / sides, 1.0f}));
        sideTop.push_back(builder.vertex({x, 0.5f, z}, {x, 0.0f, z}, {static_cast<float>(i) / sides, 0.0f}));
    }
    for (int i = 0; i < sides; ++i) {
        builder.indices.insert(builder.indices.end(), {bottomCenter, bottom[static_cast<size_t>(i + 1)], bottom[static_cast<size_t>(i)]});
        builder.indices.insert(builder.indices.end(), {topCenter, top[static_cast<size_t>(i)], top[static_cast<size_t>(i + 1)]});
        builder.smoothQuad(sideBottom[static_cast<size_t>(i)], sideBottom[static_cast<size_t>(i + 1)],
                           sideTop[static_cast<size_t>(i + 1)], sideTop[static_cast<size_t>(i)]);
    }
    return builder.upload();
}

Mesh makeCone(int sides) {
    MeshBuilder builder;
    const unsigned short bottomCenter = builder.vertex({0.0f, -0.5f, 0.0f}, {0.0f, -1.0f, 0.0f});
    std::vector<unsigned short> bottom;
    std::vector<unsigned short> sideBottom;
    std::vector<unsigned short> sideTop;
    const float slope = 0.62f;
    for (int i = 0; i <= sides; ++i) {
        const float angle = kTwoPi * static_cast<float>(i) / static_cast<float>(sides);
        const float x = std::cos(angle);
        const float z = std::sin(angle);
        bottom.push_back(builder.vertex({x, -0.5f, z}, {0.0f, -1.0f, 0.0f}));
        const Vector3 normal = normalized({x, slope, z});
        sideBottom.push_back(builder.vertex({x, -0.5f, z}, normal, {static_cast<float>(i) / sides, 1.0f}));
        sideTop.push_back(builder.vertex({0.0f, 0.5f, 0.0f}, normal, {static_cast<float>(i) / sides, 0.0f}));
    }
    for (int i = 0; i < sides; ++i) {
        builder.indices.insert(builder.indices.end(), {bottomCenter, bottom[static_cast<size_t>(i + 1)], bottom[static_cast<size_t>(i)]});
        builder.indices.insert(builder.indices.end(), {sideBottom[static_cast<size_t>(i)], sideBottom[static_cast<size_t>(i + 1)],
                                                       sideTop[static_cast<size_t>(i)]});
    }
    return builder.upload();
}

Mesh makeUvSphere(int rings, int segments) {
    MeshBuilder builder;
    std::vector<unsigned short> vertices;
    vertices.reserve(static_cast<size_t>((rings + 1) * (segments + 1)));
    for (int ring = 0; ring <= rings; ++ring) {
        const float v = static_cast<float>(ring) / static_cast<float>(rings);
        const float latitude = (v - 0.5f) * kPi;
        const float y = std::sin(latitude);
        const float radius = std::cos(latitude);
        for (int segment = 0; segment <= segments; ++segment) {
            const float u = static_cast<float>(segment) / static_cast<float>(segments);
            const float longitude = u * kTwoPi;
            const Vector3 normal{radius * std::cos(longitude), y, radius * std::sin(longitude)};
            vertices.push_back(builder.vertex(normal, normal, {u, 1.0f - v}));
        }
    }
    for (int ring = 0; ring < rings; ++ring) {
        for (int segment = 0; segment < segments; ++segment) {
            const size_t row = static_cast<size_t>(segments + 1);
            const unsigned short a = vertices[static_cast<size_t>(ring) * row + static_cast<size_t>(segment)];
            const unsigned short b = vertices[static_cast<size_t>(ring + 1) * row + static_cast<size_t>(segment)];
            const unsigned short c = vertices[static_cast<size_t>(ring + 1) * row + static_cast<size_t>(segment + 1)];
            const unsigned short d = vertices[static_cast<size_t>(ring) * row + static_cast<size_t>(segment + 1)];
            builder.smoothQuad(a, b, c, d);
        }
    }
    return builder.upload();
}

Mesh makeWheelTire() {
    MeshBuilder builder;
    constexpr int kSegments = 28;
    constexpr int kSides = 10;
    constexpr float kMajor = 0.72f;
    constexpr float kTube = 0.28f;
    std::vector<unsigned short> vertices;
    vertices.reserve(static_cast<size_t>((kSegments + 1) * (kSides + 1)));
    for (int segment = 0; segment <= kSegments; ++segment) {
        const float u = static_cast<float>(segment) / static_cast<float>(kSegments);
        const float around = u * kTwoPi;
        const float tread = 1.0f + ((segment & 1) == 0 ? 0.035f : -0.008f);
        for (int side = 0; side <= kSides; ++side) {
            const float v = static_cast<float>(side) / static_cast<float>(kSides);
            const float tubeAngle = v * kTwoPi;
            const float radial = kMajor + kTube * std::cos(tubeAngle) * tread;
            const Vector3 position{kTube * std::sin(tubeAngle), radial * std::cos(around), radial * std::sin(around)};
            const Vector3 normal = normalized({std::sin(tubeAngle), std::cos(tubeAngle) * std::cos(around),
                                               std::cos(tubeAngle) * std::sin(around)});
            vertices.push_back(builder.vertex(position, normal, {u * 4.0f, v}));
        }
    }
    for (int segment = 0; segment < kSegments; ++segment) {
        for (int side = 0; side < kSides; ++side) {
            const size_t row = static_cast<size_t>(kSides + 1);
            const unsigned short a = vertices[static_cast<size_t>(segment) * row + static_cast<size_t>(side)];
            const unsigned short b = vertices[static_cast<size_t>(segment + 1) * row + static_cast<size_t>(side)];
            const unsigned short c = vertices[static_cast<size_t>(segment + 1) * row + static_cast<size_t>(side + 1)];
            const unsigned short d = vertices[static_cast<size_t>(segment) * row + static_cast<size_t>(side + 1)];
            builder.smoothQuad(a, b, c, d);
        }
    }
    return builder.upload();
}

Mesh makeWheelRim() {
    MeshBuilder builder;
    constexpr float kHalfWidth = 0.42f;
    constexpr float kOuter = 0.64f;
    constexpr float kHub = 0.17f;
    constexpr float kSpoke = 0.075f;
    for (int side = 0; side < 2; ++side) {
        const float x = side == 0 ? -kHalfWidth : kHalfWidth;
        const float facing = side == 0 ? -1.0f : 1.0f;
        for (int i = 0; i < 6; ++i) {
            const float angle = kTwoPi * static_cast<float>(i) / 6.0f;
            const Vector3 tangent{0.0f, -std::sin(angle), std::cos(angle)};
            const Vector3 radial{0.0f, std::cos(angle), std::sin(angle)};
            const Vector3 inner = multiply(radial, kHub);
            const Vector3 outer = multiply(radial, kOuter);
            const Vector3 offset = multiply(tangent, kSpoke);
            const Vector3 normal{facing, 0.0f, 0.0f};
            const unsigned short first = builder.vertex(add({x, inner.y, inner.z}, offset), normal);
            builder.vertex(add({x, outer.y, outer.z}, offset), normal);
            builder.vertex(subtract({x, outer.y, outer.z}, offset), normal);
            builder.vertex(subtract({x, inner.y, inner.z}, offset), normal);
            if (side == 0) {
                builder.indices.insert(builder.indices.end(), {first, static_cast<unsigned short>(first + 2), static_cast<unsigned short>(first + 1),
                                                               first, static_cast<unsigned short>(first + 3), static_cast<unsigned short>(first + 2)});
            } else {
                builder.indices.insert(builder.indices.end(), {first, static_cast<unsigned short>(first + 1), static_cast<unsigned short>(first + 2),
                                                               first, static_cast<unsigned short>(first + 2), static_cast<unsigned short>(first + 3)});
            }
        }
    }
    constexpr int kRingSides = 18;
    for (int i = 0; i < kRingSides; ++i) {
        const float a0 = kTwoPi * static_cast<float>(i) / kRingSides;
        const float a1 = kTwoPi * static_cast<float>(i + 1) / kRingSides;
        builder.quad({-kHalfWidth, kOuter * std::cos(a0), kOuter * std::sin(a0)},
                     {-kHalfWidth, kOuter * std::cos(a1), kOuter * std::sin(a1)},
                     {kHalfWidth, kOuter * std::cos(a1), kOuter * std::sin(a1)},
                     {kHalfWidth, kOuter * std::cos(a0), kOuter * std::sin(a0)});
    }
    return builder.upload();
}

struct BodySection {
    float z;
    float width;
    float bottom;
    float height;
};

std::array<Vector3, 8> bodyRing(const BodySection& section) {
    const float w = section.width;
    const float y = section.bottom;
    const float h = section.height;
    return {{{-w * 0.56f, y, section.z},
             {w * 0.56f, y, section.z},
             {w, y + h * 0.25f, section.z},
             {w * 0.90f, y + h * 0.76f, section.z},
             {w * 0.55f, y + h, section.z},
             {-w * 0.55f, y + h, section.z},
             {-w * 0.90f, y + h * 0.76f, section.z},
             {-w, y + h * 0.25f, section.z}}};
}

Mesh makeBody(BuggyBodyStyle style) {
    std::array<BodySection, 6> sections{};
    switch (style) {
        case BuggyBodyStyle::BeachBuggy:
            sections = {{{1.00f, 0.50f, 0.18f, 0.35f}, {0.77f, 0.91f, 0.06f, 0.72f}, {0.35f, 1.00f, 0.02f, 0.87f},
                         {-0.20f, 0.98f, 0.03f, 0.82f}, {-0.72f, 0.89f, 0.11f, 0.70f}, {-1.00f, 0.65f, 0.20f, 0.47f}}};
            break;
        case BuggyBodyStyle::Rally:
            sections = {{{1.00f, 0.46f, 0.22f, 0.34f}, {0.74f, 0.88f, 0.08f, 0.64f}, {0.30f, 0.98f, 0.03f, 0.92f},
                         {-0.24f, 1.00f, 0.03f, 0.94f}, {-0.72f, 0.94f, 0.07f, 0.82f}, {-1.00f, 0.72f, 0.16f, 0.61f}}};
            break;
        case BuggyBodyStyle::Speedster:
            sections = {{{1.00f, 0.38f, 0.22f, 0.25f}, {0.78f, 0.78f, 0.11f, 0.48f}, {0.35f, 0.98f, 0.03f, 0.64f},
                         {-0.24f, 1.00f, 0.03f, 0.65f}, {-0.76f, 0.91f, 0.12f, 0.56f}, {-1.00f, 0.58f, 0.24f, 0.38f}}};
            break;
        case BuggyBodyStyle::Utility:
            sections = {{{1.00f, 0.64f, 0.13f, 0.50f}, {0.76f, 0.94f, 0.02f, 0.84f}, {0.34f, 1.00f, 0.00f, 0.98f},
                         {-0.22f, 1.00f, 0.00f, 1.00f}, {-0.75f, 0.98f, 0.03f, 0.96f}, {-1.00f, 0.78f, 0.11f, 0.72f}}};
            break;
    }

    MeshBuilder builder;
    std::array<std::array<Vector3, 8>, 6> rings{};
    for (size_t i = 0; i < sections.size(); ++i) {
        rings[i] = bodyRing(sections[i]);
    }
    for (size_t section = 0; section + 1 < rings.size(); ++section) {
        for (size_t edge = 0; edge < rings[section].size(); ++edge) {
            const size_t next = (edge + 1) % rings[section].size();
            builder.quad(rings[section][edge], rings[section + 1][edge], rings[section + 1][next], rings[section][next]);
        }
    }
    Vector3 frontCenter{0.0f, sections.front().bottom + sections.front().height * 0.48f, sections.front().z};
    Vector3 rearCenter{0.0f, sections.back().bottom + sections.back().height * 0.48f, sections.back().z};
    for (size_t edge = 0; edge < rings.front().size(); ++edge) {
        const size_t next = (edge + 1) % rings.front().size();
        builder.triangle(frontCenter, rings.front()[edge], rings.front()[next]);
        builder.triangle(rearCenter, rings.back()[next], rings.back()[edge]);
    }
    return builder.upload();
}

Mesh makeSpring() {
    MeshBuilder builder;
    constexpr int kSteps = 72;
    constexpr int kSides = 6;
    constexpr float kTurns = 7.0f;
    constexpr float kRadius = 0.27f;
    constexpr float kTube = 0.055f;
    std::vector<unsigned short> vertices;
    vertices.reserve(static_cast<size_t>((kSteps + 1) * (kSides + 1)));
    for (int step = 0; step <= kSteps; ++step) {
        const float t = static_cast<float>(step) / kSteps;
        const float angle = t * kTurns * kTwoPi;
        const Vector3 center{kRadius * std::cos(angle), t - 0.5f, kRadius * std::sin(angle)};
        const Vector3 outward{std::cos(angle), 0.0f, std::sin(angle)};
        const Vector3 tangent = normalized({-kRadius * std::sin(angle) * kTurns * kTwoPi, 1.0f,
                                            kRadius * std::cos(angle) * kTurns * kTwoPi});
        const Vector3 binormal = normalized(cross(tangent, outward));
        for (int side = 0; side <= kSides; ++side) {
            const float sideAngle = kTwoPi * static_cast<float>(side) / kSides;
            const Vector3 normal = normalized(add(multiply(outward, std::cos(sideAngle)), multiply(binormal, std::sin(sideAngle))));
            vertices.push_back(builder.vertex(add(center, multiply(normal, kTube)), normal, {t, static_cast<float>(side) / kSides}));
        }
    }
    for (int step = 0; step < kSteps; ++step) {
        for (int side = 0; side < kSides; ++side) {
            const size_t row = static_cast<size_t>(kSides + 1);
            const unsigned short a = vertices[static_cast<size_t>(step) * row + static_cast<size_t>(side)];
            const unsigned short b = vertices[static_cast<size_t>(step + 1) * row + static_cast<size_t>(side)];
            const unsigned short c = vertices[static_cast<size_t>(step + 1) * row + static_cast<size_t>(side + 1)];
            const unsigned short d = vertices[static_cast<size_t>(step) * row + static_cast<size_t>(side + 1)];
            builder.smoothQuad(a, b, c, d);
        }
    }
    return builder.upload();
}

Mesh makeLeaf() {
    MeshBuilder builder;
    constexpr int kSegments = 6;
    std::array<Vector3, kSegments + 1> left{};
    std::array<Vector3, kSegments + 1> right{};
    for (int i = 0; i <= kSegments; ++i) {
        const float t = static_cast<float>(i) / kSegments;
        const float width = std::sin(t * kPi) * 0.42f;
        const float y = std::sin(t * kPi) * 0.16f - t * t * 0.28f;
        left[static_cast<size_t>(i)] = {-width, y, t * 2.4f};
        right[static_cast<size_t>(i)] = {width, y, t * 2.4f};
    }
    for (int i = 0; i < kSegments; ++i) {
        const Vector3 a = left[static_cast<size_t>(i)];
        const Vector3 b = right[static_cast<size_t>(i)];
        const Vector3 c = right[static_cast<size_t>(i + 1)];
        const Vector3 d = left[static_cast<size_t>(i + 1)];
        builder.quad(a, b, c, d);
        builder.quad(d, c, b, a);
    }
    return builder.upload();
}

Mesh makeFacetedRock() {
    MeshBuilder builder;
    constexpr int kSegments = 8;
    constexpr int kRings = 4;
    std::array<std::array<Vector3, kSegments>, kRings> rings{};
    constexpr std::array<float, kRings> heights = {-0.55f, -0.12f, 0.34f, 0.72f};
    constexpr std::array<float, kRings> radii = {0.56f, 0.96f, 0.78f, 0.25f};
    for (int ring = 0; ring < kRings; ++ring) {
        for (int segment = 0; segment < kSegments; ++segment) {
            const float angle = kTwoPi * static_cast<float>(segment) / kSegments + static_cast<float>(ring & 1) * 0.19f;
            const float jitter = 0.88f + 0.10f * std::sin(static_cast<float>(segment * 13 + ring * 7));
            rings[static_cast<size_t>(ring)][static_cast<size_t>(segment)] =
                {std::cos(angle) * radii[static_cast<size_t>(ring)] * jitter, heights[static_cast<size_t>(ring)],
                 std::sin(angle) * radii[static_cast<size_t>(ring)] * jitter};
        }
    }
    for (int ring = 0; ring + 1 < kRings; ++ring) {
        for (int segment = 0; segment < kSegments; ++segment) {
            const int next = (segment + 1) % kSegments;
            builder.quad(rings[static_cast<size_t>(ring)][static_cast<size_t>(segment)],
                         rings[static_cast<size_t>(ring)][static_cast<size_t>(next)],
                         rings[static_cast<size_t>(ring + 1)][static_cast<size_t>(next)],
                         rings[static_cast<size_t>(ring + 1)][static_cast<size_t>(segment)]);
        }
    }
    for (int segment = 0; segment < kSegments; ++segment) {
        const int next = (segment + 1) % kSegments;
        builder.triangle({0.0f, -0.58f, 0.0f}, rings.front()[static_cast<size_t>(next)], rings.front()[static_cast<size_t>(segment)]);
        builder.triangle({0.0f, 0.80f, 0.0f}, rings.back()[static_cast<size_t>(segment)], rings.back()[static_cast<size_t>(next)]);
    }
    return builder.upload();
}

Mesh makeHipRoof() {
    MeshBuilder builder;
    const Vector3 peak{0.0f, 0.65f, 0.0f};
    constexpr float x = 0.5f;
    constexpr float z = 0.5f;
    constexpr float y = -0.5f;
    builder.triangle({-x, y, z}, {x, y, z}, peak);
    builder.triangle({x, y, z}, {x, y, -z}, peak);
    builder.triangle({x, y, -z}, {-x, y, -z}, peak);
    builder.triangle({-x, y, -z}, {-x, y, z}, peak);
    builder.quad({-x, y, -z}, {x, y, -z}, {x, y, z}, {-x, y, z});
    return builder.upload();
}

Mesh makeBoatHull() {
    MeshBuilder builder;
    const std::array<Vector3, 6> top = {{{-0.32f, 0.35f, 1.0f}, {0.32f, 0.35f, 1.0f}, {0.50f, 0.35f, 0.30f},
                                         {0.48f, 0.35f, -0.85f}, {-0.48f, 0.35f, -0.85f}, {-0.50f, 0.35f, 0.30f}}};
    const std::array<Vector3, 6> keel = {{{-0.05f, -0.45f, 0.92f}, {0.05f, -0.45f, 0.92f}, {0.22f, -0.42f, 0.20f},
                                          {0.24f, -0.28f, -0.78f}, {-0.24f, -0.28f, -0.78f}, {-0.22f, -0.42f, 0.20f}}};
    for (size_t i = 0; i < top.size(); ++i) {
        const size_t next = (i + 1) % top.size();
        builder.quad(top[i], top[next], keel[next], keel[i]);
    }
    builder.quad(top[5], top[4], top[3], top[2]);
    builder.triangle(top[5], top[2], top[1]);
    builder.triangle(top[5], top[1], top[0]);
    return builder.upload();
}

Mesh makeGroundDisc(int segments) {
    MeshBuilder builder;
    const unsigned short center = builder.vertex({0.0f, 0.0f, 0.0f}, {0.0f, 1.0f, 0.0f}, {0.5f, 0.5f});
    std::vector<unsigned short> edge;
    for (int i = 0; i <= segments; ++i) {
        const float angle = kTwoPi * static_cast<float>(i) / segments;
        const float x = std::cos(angle);
        const float z = std::sin(angle);
        edge.push_back(builder.vertex({x, 0.0f, z}, {0.0f, 1.0f, 0.0f}, {x * 0.5f + 0.5f, z * 0.5f + 0.5f}));
    }
    for (int i = 0; i < segments; ++i) {
        builder.indices.insert(builder.indices.end(), {center, edge[static_cast<size_t>(i)], edge[static_cast<size_t>(i + 1)]});
    }
    return builder.upload();
}

}  // namespace

struct ArcadeRender::Impl {
    Shader shader{};
    Material material{};
    bool initialized = false;

    std::array<Mesh, 4> bodies{};
    Mesh box{};
    Mesh cylinder{};
    Mesh cone{};
    Mesh sphere{};
    Mesh tire{};
    Mesh rim{};
    Mesh spring{};
    Mesh leaf{};
    Mesh rock{};
    Mesh roof{};
    Mesh boatHull{};
    Mesh shadow{};
    std::array<std::optional<formula_buggy::assets::GlbAsset>, 4> authoredCars{};
    std::array<std::optional<formula_buggy::assets::GlbAsset>, 6> authoredDrivers{};
    std::array<std::optional<formula_buggy::assets::GlbAsset>, 5> authoredTracks{};

    int sunDirectionLoc = -1;
    int sunColorLoc = -1;
    int skyAmbientLoc = -1;
    int groundAmbientLoc = -1;
    int fogColorLoc = -1;
    int fogStartLoc = -1;
    int fogEndLoc = -1;
    int viewPositionLoc = -1;
    int glossLoc = -1;
    int exposureLoc = -1;

    void setUniform(int location, const void* value, int type) {
        if (location >= 0) {
            SetShaderValue(shader, location, value, type);
        }
    }

    void draw(Mesh mesh, Matrix transform, Color color, float gloss = 0.12f) {
        material.maps[MATERIAL_MAP_DIFFUSE].color = color;
        setUniform(glossLoc, &gloss, SHADER_UNIFORM_FLOAT);
        DrawMesh(mesh, material, transform);
    }

    void loadAuthoredAssets() {
        static constexpr std::array<const char*, 4> kCarPaths = {
            "assets_src/vehicles/tidebreaker/tidebreaker.glb",
            "assets_src/vehicles/reefrunner/reefrunner.glb",
            "assets_src/vehicles/sunskipper/sunskipper.glb",
            "assets_src/vehicles/boardwalk/boardwalk.glb",
        };
        static constexpr std::array<const char*, 6> kDriverPaths = {
            "assets_src/drivers/imani_reef/imani_reef.glb",
            "assets_src/drivers/dax_calder/dax_calder.glb",
            "assets_src/drivers/marina_quill/marina_quill.glb",
            "assets_src/drivers/niko_brass/niko_brass.glb",
            "assets_src/drivers/sol_vega/sol_vega.glb",
            "assets_src/drivers/bea_torque/bea_torque.glb",
        };
        struct TrackAssetSpec {
            const char* path;
            float worldScale;
            formula_buggy::assets::DimensionLimits dimensions;
        };
        // These scales and raw glTF bounds mirror each asset's checked-in
        // runtime_alignment and measured_bounds_gltf_y_up metadata.
        static constexpr std::array<TrackAssetSpec, 5> kTrackSpecs = {{
            {"assets_src/tracks/spa/spa.glb", 1.445f,
             {{3000.0f, 104.0f, 1990.0f}, {3120.0f, 111.0f, 2090.0f}}},
            {"assets_src/tracks/suzuka/suzuka.glb", 1.445f,
             {{2970.0f, 42.0f, 1710.0f}, {3090.0f, 48.0f, 1800.0f}}},
            {"assets_src/tracks/silverstone/silverstone.glb", 1.445f,
             {{2530.0f, 18.0f, 1960.0f}, {2650.0f, 23.0f, 2060.0f}}},
            {"assets_src/tracks/monza/monza.glb", 1.445f,
             {{3320.0f, 24.0f, 1850.0f}, {3460.0f, 30.0f, 1960.0f}}},
            {"assets_src/tracks/interlagos/interlagos.glb", 1.445f,
             {{1280.0f, 51.0f, 1750.0f}, {1360.0f, 57.0f, 1860.0f}}},
        }};
        formula_buggy::assets::GlbLoadOptions carOptions;
        carOptions.dimensions = formula_buggy::assets::DimensionLimits{
            {1.90f, 0.90f, 4.70f}, {2.15f, 1.30f, 5.10f}};
        formula_buggy::assets::GlbLoadOptions driverOptions;
        driverOptions.dimensions = formula_buggy::assets::DimensionLimits{
            {0.45f, 0.80f, 0.45f}, {1.20f, 1.60f, 1.40f}};
        for (size_t i = 0; i < kCarPaths.size(); ++i) {
            std::string error;
            authoredCars[i] = formula_buggy::assets::GlbAsset::load(kCarPaths[i], carOptions, &error);
            if (!authoredCars[i] && FileExists(kCarPaths[i])) {
                TraceLog(LOG_ERROR, "Authored car rejected: %s", error.c_str());
            }
        }
        for (size_t i = 0; i < kDriverPaths.size(); ++i) {
            std::string error;
            authoredDrivers[i] = formula_buggy::assets::GlbAsset::load(kDriverPaths[i], driverOptions, &error);
            if (!authoredDrivers[i] && FileExists(kDriverPaths[i])) {
                TraceLog(LOG_ERROR, "Authored driver rejected: %s", error.c_str());
            }
        }
        for (size_t i = 0; i < kTrackSpecs.size(); ++i) {
            const TrackAssetSpec& spec = kTrackSpecs[i];
            formula_buggy::assets::GlbLoadOptions options;
            options.metersToWorld = spec.worldScale;
            options.dimensions = spec.dimensions;
            options.loadAnimations = false;
            std::string error;
            authoredTracks[i] = formula_buggy::assets::GlbAsset::load(spec.path, options, &error);
            if (!authoredTracks[i] && FileExists(spec.path)) {
                TraceLog(LOG_ERROR, "Authored track rejected: %s", error.c_str());
            }
        }
    }

    [[nodiscard]] AuthoredAssetAuditResult auditAuthoredAssets() const {
        static constexpr std::array<std::string_view, 5> kExpectedClips = {
            "idle", "accelerate", "brake", "turn_left", "turn_right"};
        AuthoredAssetAuditResult result;
        const auto inspect = [&](const auto& assets, int& loadedCount) {
            for (const auto& asset : assets) {
                if (!asset) {
                    ++result.loadFailures;
                    ++result.failures;
                    continue;
                }
                ++loadedCount;
                ++result.dimensionChecks;
                ++result.animationChecks;
                if (asset->animationCount() != static_cast<int>(kExpectedClips.size())) {
                    ++result.clipFailures;
                    ++result.failures;
                }
                for (const std::string_view clip : kExpectedClips) {
                    ++result.animationChecks;
                    if (asset->countAnimation(clip) != 1) {
                        ++result.clipFailures;
                        ++result.failures;
                    }
                }
            }
        };
        inspect(authoredCars, result.loadedCars);
        inspect(authoredDrivers, result.loadedDrivers);
        for (const auto& track : authoredTracks) {
            if (!track) {
                ++result.loadFailures;
                ++result.failures;
                continue;
            }
            ++result.loadedTracks;
            ++result.dimensionChecks;
        }
        result.ok = result.loadedCars == static_cast<int>(authoredCars.size()) &&
                    result.loadedDrivers == static_cast<int>(authoredDrivers.size()) &&
                    result.loadedTracks == static_cast<int>(authoredTracks.size()) &&
                    result.failures == 0;
        return result;
    }

    void drawAuthoredModel(const formula_buggy::assets::GlbAsset& asset, Matrix transform, float gloss = 0.12f) {
        setUniform(glossLoc, &gloss, SHADER_UNIFORM_FLOAT);
        const Model& model = asset.model();
        for (int meshIndex = 0; meshIndex < model.meshCount; ++meshIndex) {
            const int materialIndex = model.meshMaterial != nullptr ? model.meshMaterial[meshIndex] : 0;
            Material loadedMaterial = model.materials[std::clamp(materialIndex, 0, model.materialCount - 1)];
            loadedMaterial.shader = shader;
            DrawMesh(model.meshes[meshIndex], loadedMaterial, childTransform(model.transform, transform));
        }
    }

    bool drawAuthoredTrack(size_t trackIndex) {
        if (trackIndex >= authoredTracks.size() || !authoredTracks[trackIndex]) {
            return false;
        }
        const auto& track = *authoredTracks[trackIndex];
        const float scale = track.metersToWorld();
        drawAuthoredModel(track, MatrixScale(scale, scale, scale), 0.08f);
        return true;
    }

    bool drawAuthoredBuggy(const BuggyVisualSpec& spec, const BuggyRenderState& state, Matrix root) {
        const size_t carIndex = std::min(static_cast<size_t>(spec.style), authoredCars.size() - 1);
        auto& car = authoredCars[carIndex];
        auto& driver = authoredDrivers[spec.driver.variant % authoredDrivers.size()];
        if (!car || !driver) {
            return false;
        }
        std::string_view clip = "idle";
        if (state.brakeAmount > 0.10f) {
            clip = "brake";
        } else if (state.steeringRadians < -0.06f) {
            clip = "turn_left";
        } else if (state.steeringRadians > 0.06f) {
            clip = "turn_right";
        } else if (state.speedNormalized > 0.03f) {
            clip = "accelerate";
        }
        car->sampleAnimation(clip, state.visualTime, 0);
        const Vector3 carDimensions = car->dimensionsMeters();
        const float carScale = spec.length / std::max(0.01f, carDimensions.z);
        const Matrix carTransform = childTransform(MatrixScale(carScale, carScale, carScale), root);
        drawAuthoredModel(*car, carTransform);

        driver->sampleAnimation(clip, state.visualTime, 0);
        Matrix driverLocal = compose({0.0f, 0.74f * carScale, -0.12f * carScale},
                                     {carScale, carScale, carScale},
                                     {0.0f, 0.0f, -state.driverLean * 0.035f});
        drawAuthoredModel(*driver, childTransform(driverLocal, root));
        return true;
    }

    void drawPart(Mesh mesh, Matrix parent, Vector3 position, Vector3 scale, Color color, float gloss = 0.12f,
                  Vector3 rotation = {}) {
        draw(mesh, childTransform(compose(position, scale, rotation), parent), color, gloss);
    }

    void drawBox(Matrix parent, Vector3 position, Vector3 scale, Color color, float gloss = 0.12f,
                 Vector3 rotation = {}) {
        drawPart(box, parent, position, scale, color, gloss, rotation);
    }

    void drawSphere(Matrix parent, Vector3 position, Vector3 radius, Color color, float gloss = 0.12f) {
        drawPart(sphere, parent, position, radius, color, gloss);
    }

    void drawRod(Matrix parent, Vector3 from, Vector3 to, float radius, Color color, float gloss = 0.10f) {
        const Vector3 delta = subtract(to, from);
        const float length = magnitude(delta);
        if (length < 0.0001f) {
            return;
        }
        const Vector3 middle = multiply(add(from, to), 0.5f);
        const Quaternion orientation = QuaternionFromVector3ToVector3({0.0f, 1.0f, 0.0f}, multiply(delta, 1.0f / length));
        Matrix local = MatrixScale(radius, length, radius);
        local = MatrixMultiply(local, QuaternionToMatrix(orientation));
        local = MatrixMultiply(local, MatrixTranslate(middle.x, middle.y, middle.z));
        draw(cylinder, childTransform(local, parent), color, gloss);
    }

    void drawSpring(Matrix parent, Vector3 from, Vector3 to, float radiusScale, Color color) {
        const Vector3 delta = subtract(to, from);
        const float length = magnitude(delta);
        if (length < 0.0001f) {
            return;
        }
        const Vector3 middle = multiply(add(from, to), 0.5f);
        const Quaternion orientation = QuaternionFromVector3ToVector3({0.0f, 1.0f, 0.0f}, multiply(delta, 1.0f / length));
        Matrix local = MatrixScale(radiusScale, length, radiusScale);
        local = MatrixMultiply(local, QuaternionToMatrix(orientation));
        local = MatrixMultiply(local, MatrixTranslate(middle.x, middle.y, middle.z));
        draw(spring, childTransform(local, parent), color, 0.42f);
    }

    void drawDriver(const BuggyVisualSpec& spec, const BuggyRenderState& state, Matrix root, float bodyBase) {
        const float w = spec.width;
        const float l = spec.length;
        const float h = spec.bodyHeight;
        const float lean = std::clamp(state.driverLean, -1.0f, 1.0f);
        const float centerX = lean * w * 0.075f;
        const DriverVisualSpec& driver = spec.driver;

        drawBox(root, {centerX, bodyBase + h * 0.81f, -l * 0.12f}, {w * 0.43f, h * 0.42f, l * 0.24f},
                shade(spec.trim, 0.78f), 0.08f, {0.12f, 0.0f, -lean * 0.08f});
        drawPart(cylinder, root, {centerX, bodyBase + h * 1.40f, -l * 0.08f}, {w * 0.16f, h * 0.56f, w * 0.16f},
                 driver.shirt, 0.16f, {0.10f, 0.0f, -lean * 0.10f});

        const Vector3 leftShoulder{centerX - w * 0.17f, bodyBase + h * 1.58f, -l * 0.04f};
        const Vector3 rightShoulder{centerX + w * 0.17f, bodyBase + h * 1.58f, -l * 0.04f};
        const float steer = std::clamp(state.steeringRadians, -0.75f, 0.75f);
        const Vector3 leftHand{centerX - w * 0.13f - steer * w * 0.05f, bodyBase + h * 1.33f + steer * h * 0.05f,
                               l * 0.16f};
        const Vector3 rightHand{centerX + w * 0.13f - steer * w * 0.05f, bodyBase + h * 1.33f - steer * h * 0.05f,
                                l * 0.16f};
        drawRod(root, leftShoulder, leftHand, h * 0.052f, driver.skin);
        drawRod(root, rightShoulder, rightHand, h * 0.052f, driver.skin);
        drawSphere(root, leftHand, {h * 0.070f, h * 0.065f, h * 0.070f}, driver.gloves, 0.20f);
        drawSphere(root, rightHand, {h * 0.070f, h * 0.065f, h * 0.070f}, driver.gloves, 0.20f);

        const Vector3 wheelCenter{centerX, bodyBase + h * 1.32f, l * 0.17f};
        drawPart(tire, root, wheelCenter, {h * 0.11f, h * 0.25f, h * 0.25f}, shade(spec.trim, 0.62f), 0.25f,
                 {0.0f, kPi * 0.5f, steer});
        drawRod(root, {centerX, bodyBase + h * 1.14f, l * 0.05f}, wheelCenter, h * 0.027f, shade(spec.trim, 0.70f));

        const Vector3 neck{centerX, bodyBase + h * 1.76f, -l * 0.06f};
        drawPart(cylinder, root, neck, {h * 0.075f, h * 0.18f, h * 0.075f}, driver.skin, 0.10f);
        const Vector3 head{centerX, bodyBase + h * 2.06f, -l * 0.035f};
        drawSphere(root, head, {h * 0.28f, h * 0.33f, h * 0.28f}, driver.skin, 0.20f);

        switch (driver.headwearStyle) {
            case DriverHeadwear::Helmet:
                drawSphere(root, {head.x, head.y + h * 0.08f, head.z - h * 0.015f}, {h * 0.32f, h * 0.34f, h * 0.31f},
                           driver.headwear, 0.42f);
                drawBox(root, {head.x, head.y + h * 0.015f, head.z + h * 0.27f}, {h * 0.45f, h * 0.12f, h * 0.045f},
                        spec.glass, 0.70f, {-0.10f, 0.0f, 0.0f});
                break;
            case DriverHeadwear::Hair:
                drawSphere(root, {head.x, head.y + h * 0.25f, head.z - h * 0.07f}, {h * 0.29f, h * 0.16f, h * 0.28f},
                           driver.hair, 0.08f);
                break;
            case DriverHeadwear::Bandana:
                drawBox(root, {head.x, head.y + h * 0.20f, head.z}, {h * 0.56f, h * 0.10f, h * 0.46f}, driver.headwear, 0.12f);
                drawRod(root, {head.x - h * 0.22f, head.y + h * 0.18f, head.z - h * 0.18f},
                        {head.x - h * 0.37f, head.y - h * 0.02f, head.z - h * 0.36f}, h * 0.035f, driver.headwear);
                break;
            case DriverHeadwear::Visor:
                drawBox(root, {head.x, head.y + h * 0.22f, head.z}, {h * 0.59f, h * 0.11f, h * 0.48f}, driver.headwear, 0.18f);
                drawBox(root, {head.x, head.y + h * 0.16f, head.z + h * 0.29f}, {h * 0.55f, h * 0.08f, h * 0.21f},
                        shade(driver.headwear, 1.08f), 0.20f);
                break;
        }
    }

    void drawWheelAndSuspension(const BuggyVisualSpec& spec, const BuggyRenderState& state, Matrix root, int index,
                                float bodyBase) {
        const bool front = index < 2;
        const bool left = (index & 1) == 0;
        const float side = left ? -1.0f : 1.0f;
        const float z = (front ? 0.36f : -0.36f) * spec.length;
        const float compression = clamp01(state.suspensionCompression[static_cast<size_t>(index)]);
        const float travel = std::max(spec.wheelRadius * 0.30f, std::max(0.0f, state.suspensionTravel));
        const float droop = clamp01(state.airborneAmount) * travel * 0.36f;
        const float wheelY = spec.wheelRadius + (0.48f - compression) * travel - droop;
        const float wheelX = side * spec.width * 0.56f;
        const Vector3 hub{wheelX, wheelY, z};
        const Vector3 upperAnchor{side * spec.width * 0.34f, bodyBase + spec.bodyHeight * 0.43f, z};
        const Vector3 lowerAnchor{side * spec.width * 0.36f, bodyBase + spec.bodyHeight * 0.04f, z};
        const Vector3 upperHub{wheelX - side * spec.wheelWidth * 0.18f, wheelY + spec.wheelRadius * 0.25f, z};
        const Vector3 lowerHub{wheelX - side * spec.wheelWidth * 0.18f, wheelY - spec.wheelRadius * 0.18f, z};
        drawRod(root, upperAnchor, upperHub, spec.wheelRadius * 0.055f, shade(spec.trim, 1.28f), 0.48f);
        drawRod(root, lowerAnchor, lowerHub, spec.wheelRadius * 0.065f, shade(spec.trim, 1.10f), 0.42f);
        drawRod(root, {side * spec.width * 0.24f, bodyBase + spec.bodyHeight * 0.30f, z}, hub,
                spec.wheelRadius * 0.047f, shade(spec.trim, 0.75f), 0.32f);
        drawSpring(root, {side * spec.width * 0.36f, bodyBase + spec.bodyHeight * 0.62f, z}, upperHub,
                   spec.wheelRadius * 0.44f, spec.accent);

        // The dark upright and bright cap make suspension movement legible even
        // when the car occupies only a small part of the screen.
        drawRod(root, upperHub, lowerHub, spec.wheelRadius * 0.080f, shade(spec.trim, 0.56f), 0.20f);
        drawSphere(root, hub, {spec.wheelRadius * 0.18f, spec.wheelRadius * 0.18f, spec.wheelRadius * 0.18f},
                   shade(spec.trim, 1.46f), 0.62f);

        Vector3 wheelRotation{state.wheelSpinRadians, front ? state.steeringRadians : 0.0f, 0.0f};
        Matrix wheelLocal = compose(hub, {spec.wheelWidth / 0.56f, spec.wheelRadius, spec.wheelRadius}, wheelRotation);
        const Matrix wheelWorld = childTransform(wheelLocal, root);
        draw(tire, wheelWorld, shade(spec.trim, 0.48f), 0.16f);
        Matrix rimLocal = compose(hub, {spec.wheelWidth * 0.73f, spec.wheelRadius * 0.70f, spec.wheelRadius * 0.70f}, wheelRotation);
        draw(rim, childTransform(rimLocal, root), spec.rim, 0.58f);
        drawPart(cylinder, root, hub, {spec.wheelWidth * 0.86f, spec.wheelRadius * 0.16f, spec.wheelRadius * 0.16f},
                 shade(spec.trim, 1.42f), 0.68f, {0.0f, 0.0f, kPi * 0.5f});
    }

    void drawStyleDetails(const BuggyVisualSpec& spec, Matrix root, float bodyBase) {
        const float w = spec.width;
        const float l = spec.length;
        const float h = spec.bodyHeight;
        switch (spec.style) {
            case BuggyBodyStyle::BeachBuggy:
                drawRod(root, {-w * 0.38f, bodyBase + h * 0.72f, -l * 0.28f},
                        {-w * 0.35f, bodyBase + h * 2.14f, -l * 0.22f}, h * 0.055f, spec.trim, 0.40f);
                drawRod(root, {w * 0.38f, bodyBase + h * 0.72f, -l * 0.28f},
                        {w * 0.35f, bodyBase + h * 2.14f, -l * 0.22f}, h * 0.055f, spec.trim, 0.40f);
                drawRod(root, {-w * 0.35f, bodyBase + h * 2.14f, -l * 0.22f},
                        {w * 0.35f, bodyBase + h * 2.14f, -l * 0.22f}, h * 0.055f, spec.trim, 0.40f);
                drawRod(root, {-w * 0.35f, bodyBase + h * 2.14f, -l * 0.22f},
                        {-w * 0.29f, bodyBase + h * 0.92f, l * 0.10f}, h * 0.047f, spec.trim, 0.36f);
                drawRod(root, {w * 0.35f, bodyBase + h * 2.14f, -l * 0.22f},
                        {w * 0.29f, bodyBase + h * 0.92f, l * 0.10f}, h * 0.047f, spec.trim, 0.36f);
                break;
            case BuggyBodyStyle::Rally:
                drawBox(root, {0.0f, bodyBase + h * 1.18f, -l * 0.12f}, {w * 0.77f, h * 0.65f, l * 0.40f},
                        shade(spec.body, 0.96f), 0.32f, {-0.04f, 0.0f, 0.0f});
                drawBox(root, {0.0f, bodyBase + h * 1.26f, l * 0.10f}, {w * 0.62f, h * 0.43f, h * 0.055f}, spec.glass,
                        0.72f, {-0.21f, 0.0f, 0.0f});
                drawPart(sphere, root, {-w * 0.31f, bodyBase + h * 0.86f, l * 0.48f}, {h * 0.12f, h * 0.12f, h * 0.06f},
                         {255, 242, 196, 255}, 0.78f);
                drawPart(sphere, root, {w * 0.31f, bodyBase + h * 0.86f, l * 0.48f}, {h * 0.12f, h * 0.12f, h * 0.06f},
                         {255, 242, 196, 255}, 0.78f);
                break;
            case BuggyBodyStyle::Speedster:
                drawBox(root, {0.0f, bodyBase + h * 1.18f, -l * 0.47f}, {w * 0.98f, h * 0.11f, l * 0.19f}, spec.accent,
                        0.42f);
                drawRod(root, {-w * 0.39f, bodyBase + h * 0.69f, -l * 0.43f},
                        {-w * 0.39f, bodyBase + h * 1.15f, -l * 0.47f}, h * 0.045f, spec.trim, 0.38f);
                drawRod(root, {w * 0.39f, bodyBase + h * 0.69f, -l * 0.43f},
                        {w * 0.39f, bodyBase + h * 1.15f, -l * 0.47f}, h * 0.045f, spec.trim, 0.38f);
                drawBox(root, {0.0f, bodyBase + h * 0.65f, l * 0.49f}, {w * 0.50f, h * 0.16f, l * 0.12f}, spec.accent,
                        0.36f, {-0.10f, 0.0f, 0.0f});
                break;
            case BuggyBodyStyle::Utility:
                drawRod(root, {-w * 0.39f, bodyBase + h * 0.72f, l * 0.42f},
                        {-w * 0.46f, bodyBase + h * 0.47f, l * 0.60f}, h * 0.060f, spec.trim, 0.42f);
                drawRod(root, {w * 0.39f, bodyBase + h * 0.72f, l * 0.42f},
                        {w * 0.46f, bodyBase + h * 0.47f, l * 0.60f}, h * 0.060f, spec.trim, 0.42f);
                drawRod(root, {-w * 0.46f, bodyBase + h * 0.47f, l * 0.60f},
                        {w * 0.46f, bodyBase + h * 0.47f, l * 0.60f}, h * 0.060f, spec.trim, 0.42f);
                drawBox(root, {0.0f, bodyBase + h * 1.42f, -l * 0.23f}, {w * 0.76f, h * 0.08f, l * 0.37f},
                        shade(spec.trim, 1.12f), 0.32f);
                break;
        }
    }

    void drawVehicleSignals(const BuggyVisualSpec& spec, const BuggyRenderState& state, Matrix root, float bodyBase) {
        const float w = spec.width;
        const float l = spec.length;
        const float h = spec.bodyHeight;
        const float braking = clamp01(state.brakeAmount);
        const Color tail = mixColor(Color{150, 24, 18, 255}, Color{255, 77, 40, 255}, braking);

        drawBox(root, {0.0f, bodyBase + h * 0.21f, -l * 0.565f}, {w * 0.76f, h * 0.11f, h * 0.10f},
                shade(spec.trim, 1.28f), 0.40f);
        for (float side : {-1.0f, 1.0f}) {
            drawBox(root, {side * w * 0.34f, bodyBase + h * 0.52f, -l * 0.535f},
                    {w * 0.16f, h * 0.17f, h * 0.055f}, tail, 0.76f);
            drawPart(cylinder, root, {side * w * 0.24f, bodyBase + h * 0.18f, -l * 0.59f},
                     {h * 0.075f, h * 0.18f, h * 0.075f}, shade(spec.trim, 1.54f), 0.72f,
                     {kPi * 0.5f, 0.0f, 0.0f});
        }
        drawBox(root, {0.0f, bodyBase + h * 0.43f, -l * 0.548f}, {w * 0.24f, h * 0.14f, h * 0.035f},
                Color{235, 221, 163, 255}, 0.24f);

        drawBox(root, {0.0f, bodyBase + h * 0.22f, l * 0.565f}, {w * 0.71f, h * 0.10f, h * 0.11f},
                shade(spec.trim, 1.24f), 0.38f);
        for (float side : {-1.0f, 1.0f}) {
            drawSphere(root, {side * w * 0.30f, bodyBase + h * 0.54f, l * 0.535f},
                       {h * 0.13f, h * 0.13f, h * 0.07f}, Color{255, 239, 187, 255}, 0.82f);
        }
    }

    void drawDust(const BuggyVisualSpec& spec, const BuggyRenderState& state, Matrix root, float bodyBase) {
        const float amount = clamp01(state.dustAmount) * (0.35f + 0.65f * clamp01(state.speedNormalized));
        if (amount < 0.015f) {
            return;
        }
        const float phase = state.visualTime * (5.0f + 7.0f * clamp01(state.speedNormalized));
        const Color dust{190, 155, 105, static_cast<unsigned char>(52 + static_cast<int>(amount * 100.0f))};
        for (int i = 0; i < 4; ++i) {
            const float lane = (i & 1) == 0 ? -1.0f : 1.0f;
            const float age = 0.32f + 0.19f * static_cast<float>(i / 2);
            const float wobble = std::sin(phase + static_cast<float>(i) * 2.17f);
            const float radius = spec.wheelRadius * (0.38f + age * amount);
            drawSphere(root,
                       {lane * spec.width * (0.48f + 0.05f * wobble), bodyBase * 0.15f + radius * 0.42f,
                        -spec.length * (0.43f + age * 0.46f)},
                       {radius * 1.25f, radius * 0.68f, radius * 1.65f}, dust, 0.0f);
        }
    }

    void drawBuggy(const BuggyVisualSpec& spec, const BuggyRenderState& state) {
        const float w = std::max(1.2f, spec.width);
        const float l = std::max(2.0f, spec.length);
        const float h = std::max(0.55f, spec.bodyHeight);
        const float bodyBase = spec.wheelRadius * 0.64f + std::max(0.05f, spec.rideHeight);
        const float travel = std::max(spec.wheelRadius * 0.30f, std::max(0.0f, state.suspensionTravel));
        float averageCompression = 0.0f;
        for (float compression : state.suspensionCompression) {
            averageCompression += clamp01(compression);
        }
        averageCompression /= static_cast<float>(state.suspensionCompression.size());
        const float groundedWheelBottom = (0.48f - averageCompression) * travel;
        const Matrix authoredRoot = compose(state.position, {1.0f, 1.0f, 1.0f},
                                            {state.pitchRadians, state.headingRadians, state.rollRadians});

        const float grounded = 1.0f - 0.74f * clamp01(state.airborneAmount);
        const Color shadowColor{24, 31, 31, static_cast<unsigned char>((110 + static_cast<int>(55.0f * clamp01(state.speedNormalized))) * grounded)};
        const Vector3 shadowPosition = state.useGroundShadowPosition ? state.shadowPosition : state.position;
        Matrix shadowTransform = compose(add(shadowPosition, {0.0f, 0.018f, 0.0f}), {w * 0.73f, 1.0f, l * 0.43f},
                                          {0.0f, state.headingRadians, 0.0f});
        draw(shadow, shadowTransform, shadowColor, 0.0f);

        // Authored vehicles use a tire-contact origin. Applying the procedural
        // suspension root correction to them pushed all four tires below the
        // road at low speed, when compression approaches its resting value.
        if (drawAuthoredBuggy(spec, state, authoredRoot)) {
            drawDust(spec, state, authoredRoot, bodyBase);
            const float boost = clamp01(state.boostAmount);
            if (boost > 0.01f) {
                const float flameLength = h * (0.45f + boost * 0.72f);
                for (float side : {-1.0f, 1.0f}) {
                    drawPart(cone, authoredRoot, {side * w * 0.21f, bodyBase + h * 0.28f, -l * 0.63f},
                             {h * 0.14f, flameLength, h * 0.14f}, Color{255, 167, 42, 220}, 0.08f,
                             {-kPi * 0.5f, 0.0f, 0.0f});
                }
            }
            return;
        }

        Vector3 rootPosition = state.position;
        rootPosition.y -= groundedWheelBottom * (1.0f - clamp01(state.airborneAmount));
        Matrix root = compose(rootPosition, {1.0f, 1.0f, 1.0f},
                              {state.pitchRadians, state.headingRadians, state.rollRadians});

        drawBox(root, {0.0f, bodyBase - h * 0.01f, 0.0f}, {w * 0.72f, h * 0.19f, l * 0.70f}, shade(spec.trim, 0.68f),
                0.28f);
        for (int index = 0; index < 4; ++index) {
            drawWheelAndSuspension(spec, state, root, index, bodyBase);
        }

        Color bodyColor = mixColor(spec.body, WHITE, clamp01(state.damageFlash) * 0.62f);
        const size_t bodyIndex = static_cast<size_t>(spec.style);
        drawPart(bodies[bodyIndex], root, {0.0f, bodyBase, 0.0f}, {w * 0.50f, h, l * 0.50f}, bodyColor, 0.42f);
        drawBox(root, {0.0f, bodyBase + h * 0.67f, l * 0.31f}, {w * 0.55f, h * 0.10f, l * 0.32f}, spec.accent, 0.46f,
                {-0.08f, 0.0f, 0.0f});
        drawBox(root, {0.0f, bodyBase + h * 0.40f, -l * 0.48f}, {w * 0.61f, h * 0.13f, l * 0.10f}, spec.accent,
                0.34f);
        drawBox(root, {-w * 0.51f, bodyBase + h * 0.35f, 0.0f}, {w * 0.065f, h * 0.29f, l * 0.55f},
                shade(bodyColor, 0.72f), 0.24f);
        drawBox(root, {w * 0.51f, bodyBase + h * 0.35f, 0.0f}, {w * 0.065f, h * 0.29f, l * 0.55f},
                shade(bodyColor, 0.72f), 0.24f);
        drawStyleDetails(spec, root, bodyBase);
        drawVehicleSignals(spec, state, root, bodyBase);
        drawDriver(spec, state, root, bodyBase);
        drawDust(spec, state, root, bodyBase);

        const float boost = clamp01(state.boostAmount);
        if (boost > 0.01f) {
            const float flameLength = h * (0.45f + boost * 0.72f);
            for (float side : {-1.0f, 1.0f}) {
                drawPart(cone, root, {side * w * 0.21f, bodyBase + h * 0.28f, -l * 0.63f},
                         {h * 0.14f, flameLength, h * 0.14f}, Color{255, 167, 42, 220}, 0.08f,
                         {-kPi * 0.5f, 0.0f, 0.0f});
                drawPart(cone, root, {side * w * 0.21f, bodyBase + h * 0.28f, -l * 0.61f},
                         {h * 0.07f, flameLength * 0.65f, h * 0.07f}, Color{255, 239, 161, 235}, 0.08f,
                         {-kPi * 0.5f, 0.0f, 0.0f});
            }
        }
    }

    void drawPalm(const TropicalPropSpec& spec, const TropicalPropState& state, Matrix root) {
        const float bend = std::sin(state.windPhase + static_cast<float>(spec.variant) * 1.71f) * 0.10f;
        std::array<Vector3, 6> trunk{};
        for (size_t i = 0; i < trunk.size(); ++i) {
            const float t = static_cast<float>(i) / static_cast<float>(trunk.size() - 1);
            trunk[i] = {bend * t * t * 2.4f + std::sin(t * 2.6f + spec.variant) * 0.10f, t * 6.2f,
                        std::sin(t * 1.7f + static_cast<float>(spec.variant)) * 0.18f};
            if (i > 0) {
                drawRod(root, trunk[i - 1], trunk[i], 0.25f - t * 0.11f, spec.detail, 0.10f);
            }
        }
        const Vector3 crown = trunk.back();
        drawSphere(root, crown, {0.40f, 0.31f, 0.40f}, shade(spec.detail, 0.88f), 0.12f);
        for (int i = 0; i < 9; ++i) {
            const float yaw = static_cast<float>(i) * kTwoPi / 9.0f + static_cast<float>(spec.variant) * 0.29f;
            const float droop = -0.14f - 0.06f * static_cast<float>(i & 1) + bend * std::cos(yaw);
            drawPart(leaf, root, crown, {1.0f + 0.08f * static_cast<float>((i + spec.variant) % 3), 1.0f, 1.0f},
                     (i & 1) == 0 ? spec.primary : shade(spec.primary, 1.13f), 0.08f, {droop, yaw, 0.0f});
        }
        for (int i = 0; i < 3; ++i) {
            const float yaw = static_cast<float>(i) * kTwoPi / 3.0f;
            drawSphere(root, add(crown, {std::cos(yaw) * 0.29f, -0.28f, std::sin(yaw) * 0.29f}),
                       {0.16f, 0.18f, 0.16f}, shade(spec.detail, 0.72f), 0.18f);
        }
        for (int i = 0; i < 3; ++i) {
            const float yaw = static_cast<float>(i) * 2.17f + static_cast<float>(spec.variant);
            drawPart(leaf, root, {std::cos(yaw) * 0.45f, 0.02f, std::sin(yaw) * 0.45f},
                     {0.20f, 0.20f, 0.34f}, shade(spec.primary, 0.76f + 0.10f * static_cast<float>(i)), 0.03f,
                     {-0.24f, yaw, 0.0f});
        }
    }

    void drawRockCluster(const TropicalPropSpec& spec, Matrix root) {
        drawPart(rock, root, {0.0f, 0.72f, 0.0f}, {1.18f, 1.10f, 1.00f}, spec.primary, 0.10f,
                 {0.0f, static_cast<float>(spec.variant) * 0.63f, 0.0f});
        drawPart(rock, root, {0.82f, 0.42f, -0.18f}, {0.72f, 0.65f, 0.68f}, shade(spec.primary, 1.12f), 0.11f,
                 {0.0f, 1.4f, 0.0f});
        drawPart(rock, root, {-0.72f, 0.30f, 0.31f}, {0.58f, 0.47f, 0.62f}, shade(spec.primary, 0.83f), 0.08f,
                 {0.0f, -0.7f, 0.0f});
        for (int i = 0; i < 3; ++i) {
            const float yaw = static_cast<float>(i) * 2.07f + static_cast<float>(spec.variant) * 0.31f;
            drawPart(leaf, root, {std::cos(yaw) * 0.86f, 0.03f, std::sin(yaw) * 0.72f}, {0.15f, 0.16f, 0.30f},
                     Color{61, 127, 70, 255}, 0.03f, {-0.30f, yaw, 0.0f});
        }
    }

    void drawBeachHut(const TropicalPropSpec& spec, Matrix root) {
        drawBox(root, {0.0f, 1.15f, 0.0f}, {3.25f, 2.30f, 2.75f}, spec.primary, 0.10f);
        for (float x : {-1.38f, 1.38f}) {
            for (float z : {-1.08f, 1.08f}) {
                drawRod(root, {x, 0.0f, z}, {x, 2.80f, z}, 0.105f, spec.detail, 0.12f);
            }
        }
        drawPart(roof, root, {0.0f, 2.84f, 0.0f}, {4.05f, 1.72f, 3.55f}, spec.accent, 0.06f);
        drawBox(root, {0.0f, 1.00f, 1.39f}, {0.78f, 1.24f, 0.08f}, shade(spec.detail, 0.72f), 0.08f);
        drawBox(root, {-0.95f, 1.28f, 1.40f}, {0.61f, 0.60f, 0.08f}, shade(spec.accent, 0.82f), 0.12f);
        drawBox(root, {0.95f, 1.28f, 1.40f}, {0.61f, 0.60f, 0.08f}, shade(spec.accent, 0.82f), 0.12f);
        drawBox(root, {0.0f, 0.24f, 1.43f}, {3.02f, 0.14f, 0.10f}, shade(spec.detail, 1.22f), 0.14f);
        drawBox(root, {0.0f, 2.16f, 1.43f}, {3.02f, 0.13f, 0.10f}, shade(spec.detail, 1.16f), 0.14f);
    }

    void drawMarket(const TropicalPropSpec& spec, Matrix root) {
        for (float x : {-1.35f, 1.35f}) {
            for (float z : {-0.92f, 0.92f}) {
                drawRod(root, {x, 0.0f, z}, {x, 2.65f, z}, 0.075f, spec.detail, 0.20f);
            }
        }
        drawPart(roof, root, {0.0f, 2.66f, 0.0f}, {3.25f, 0.92f, 2.35f}, spec.primary, 0.20f);
        drawBox(root, {0.0f, 0.88f, 0.48f}, {2.85f, 0.18f, 0.92f}, spec.detail, 0.12f);
        for (int i = 0; i < 4; ++i) {
            const float x = -1.02f + static_cast<float>(i) * 0.68f;
            drawBox(root, {x, 1.14f, 0.48f}, {0.48f, 0.40f, 0.58f}, (i & 1) == 0 ? spec.accent : shade(spec.primary, 1.18f),
                    0.08f, {0.0f, static_cast<float>(i) * 0.15f, 0.0f});
        }
    }

    void drawBoat(const TropicalPropSpec& spec, Matrix root) {
        drawPart(boatHull, root, {0.0f, 0.68f, 0.0f}, {2.45f, 1.22f, 3.60f}, spec.primary, 0.30f);
        drawBox(root, {0.0f, 1.17f, -0.55f}, {1.62f, 0.14f, 1.30f}, shade(spec.accent, 1.04f), 0.18f);
        drawRod(root, {0.0f, 0.96f, -0.22f}, {0.0f, 4.35f, -0.22f}, 0.085f, spec.detail, 0.22f);
        drawPart(leaf, root, {0.08f, 4.05f, -0.22f}, {1.23f, 1.0f, 1.10f}, Color{246, 238, 203, 255}, 0.06f,
                 {0.0f, 0.0f, -kPi * 0.5f});
        drawBox(root, {0.0f, 1.08f, 1.02f}, {0.78f, 0.17f, 0.38f}, spec.accent, 0.32f);
    }

    void drawCrane(const TropicalPropSpec& spec, Matrix root) {
        drawBox(root, {0.0f, 2.60f, 0.0f}, {0.48f, 5.20f, 0.48f}, spec.detail, 0.38f);
        drawRod(root, {-0.10f, 4.85f, 0.0f}, {4.30f, 5.70f, 0.0f}, 0.13f, spec.primary, 0.42f);
        drawRod(root, {0.10f, 4.80f, 0.0f}, {-2.00f, 5.10f, 0.0f}, 0.13f, spec.primary, 0.42f);
        drawRod(root, {3.92f, 5.62f, 0.0f}, {3.92f, 2.02f, 0.0f}, 0.035f, shade(spec.detail, 0.50f), 0.30f);
        drawBox(root, {3.92f, 1.72f, 0.0f}, {0.45f, 0.50f, 0.45f}, spec.accent, 0.45f);
        drawBox(root, {0.0f, 0.34f, 0.0f}, {1.55f, 0.68f, 1.38f}, shade(spec.primary, 0.75f), 0.36f);
    }

    void drawBanner(const TropicalPropSpec& spec, Matrix root) {
        drawRod(root, {-1.72f, 0.0f, 0.0f}, {-1.72f, 3.15f, 0.0f}, 0.10f, spec.detail, 0.28f);
        drawRod(root, {1.72f, 0.0f, 0.0f}, {1.72f, 3.15f, 0.0f}, 0.10f, spec.detail, 0.28f);
        drawBox(root, {0.0f, 2.46f, 0.0f}, {3.42f, 1.00f, 0.10f}, spec.primary, 0.18f);
        drawBox(root, {0.0f, 2.46f, 0.058f}, {2.28f, 0.18f, 0.025f}, spec.accent, 0.10f,
                {0.0f, 0.0f, ((spec.variant & 1U) == 0U ? -0.18f : 0.18f)});
    }

    void drawTorch(const TropicalPropSpec& spec, const TropicalPropState& state, Matrix root) {
        drawRod(root, {0.0f, 0.0f, 0.0f}, {0.0f, 2.32f, 0.0f}, 0.09f, spec.detail, 0.12f);
        drawPart(cone, root, {0.0f, 2.36f, 0.0f}, {0.33f, 0.42f, 0.33f}, shade(spec.detail, 0.72f), 0.16f,
                 {kPi, 0.0f, 0.0f});
        const float flicker = 0.92f + 0.10f * std::sin(state.windPhase * 4.3f + static_cast<float>(spec.variant));
        drawPart(cone, root, {0.0f, 2.88f, 0.0f}, {0.38f * flicker, 1.02f * flicker, 0.38f * flicker},
                 Color{255, 116, 32, 230}, 0.06f);
        drawPart(cone, root, {0.0f, 2.77f, 0.0f}, {0.19f * flicker, 0.62f * flicker, 0.19f * flicker}, spec.accent, 0.05f);
    }

    void drawTropicalProp(const TropicalPropSpec& spec, const TropicalPropState& state) {
        const float scale = std::max(0.05f, state.scale);
        const Matrix root = compose(state.position, {scale, scale, scale}, {0.0f, state.yawRadians, 0.0f});
        switch (spec.kind) {
            case TropicalPropKind::Palm:
                drawPalm(spec, state, root);
                break;
            case TropicalPropKind::RockCluster:
                drawRockCluster(spec, root);
                break;
            case TropicalPropKind::BeachHut:
                drawBeachHut(spec, root);
                break;
            case TropicalPropKind::MarketStall:
                drawMarket(spec, root);
                break;
            case TropicalPropKind::FishingBoat:
                drawBoat(spec, root);
                break;
            case TropicalPropKind::DockCrane:
                drawCrane(spec, root);
                break;
            case TropicalPropKind::TrackBanner:
                drawBanner(spec, root);
                break;
            case TropicalPropKind::Torch:
                drawTorch(spec, state, root);
                break;
        }
    }
};

BuggyVisualSpec MakeBuggyVisualSpec(BuggyBodyStyle style, Color body, Color accent) {
    BuggyVisualSpec spec;
    spec.style = style;
    spec.body = body;
    spec.accent = accent;
    spec.rim = accent;
    switch (style) {
        case BuggyBodyStyle::BeachBuggy:
            spec.width = 2.45f;
            spec.length = 4.15f;
            spec.bodyHeight = 1.12f;
            spec.wheelRadius = 0.64f;
            break;
        case BuggyBodyStyle::Rally:
            spec.width = 2.32f;
            spec.length = 4.35f;
            spec.bodyHeight = 1.18f;
            spec.wheelRadius = 0.58f;
            break;
        case BuggyBodyStyle::Speedster:
            spec.width = 2.25f;
            spec.length = 4.52f;
            spec.bodyHeight = 0.96f;
            spec.wheelRadius = 0.57f;
            spec.rideHeight = 0.20f;
            break;
        case BuggyBodyStyle::Utility:
            spec.width = 2.62f;
            spec.length = 4.02f;
            spec.bodyHeight = 1.28f;
            spec.wheelRadius = 0.68f;
            spec.wheelWidth = 0.47f;
            spec.rideHeight = 0.34f;
            break;
    }
    return spec;
}

TropicalPropSpec MakeTropicalPropSpec(TropicalPropKind kind, std::uint32_t variant) {
    TropicalPropSpec spec;
    spec.kind = kind;
    spec.variant = variant;
    switch (kind) {
        case TropicalPropKind::Palm:
            spec.primary = {45, 156, 82, 255};
            spec.accent = {84, 184, 91, 255};
            spec.detail = {119, 77, 43, 255};
            break;
        case TropicalPropKind::RockCluster:
            spec.primary = {112, 111, 99, 255};
            spec.accent = {145, 140, 116, 255};
            spec.detail = {72, 73, 69, 255};
            break;
        case TropicalPropKind::BeachHut:
            spec.primary = {179, 92, 51, 255};
            spec.accent = {239, 188, 89, 255};
            spec.detail = {91, 62, 40, 255};
            break;
        case TropicalPropKind::MarketStall:
            spec.primary = (variant & 1U) == 0U ? Color{232, 69, 88, 255} : Color{43, 174, 153, 255};
            spec.accent = {249, 202, 69, 255};
            spec.detail = {84, 60, 45, 255};
            break;
        case TropicalPropKind::FishingBoat:
            spec.primary = (variant & 1U) == 0U ? Color{51, 151, 202, 255} : Color{224, 77, 58, 255};
            spec.accent = {246, 196, 63, 255};
            spec.detail = {82, 61, 44, 255};
            break;
        case TropicalPropKind::DockCrane:
            spec.primary = {221, 77, 53, 255};
            spec.accent = {244, 188, 54, 255};
            spec.detail = {77, 67, 57, 255};
            break;
        case TropicalPropKind::TrackBanner:
            spec.primary = (variant & 1U) == 0U ? Color{228, 59, 54, 255} : Color{35, 145, 178, 255};
            spec.accent = {255, 226, 93, 255};
            spec.detail = {61, 67, 61, 255};
            break;
        case TropicalPropKind::Torch:
            spec.primary = {243, 97, 37, 255};
            spec.accent = {255, 220, 78, 255};
            spec.detail = {91, 57, 36, 255};
            break;
    }
    return spec;
}

ArcadeRender::ArcadeRender() : impl_(std::make_unique<Impl>()) {}

ArcadeRender::~ArcadeRender() {
    if (impl_ && impl_->initialized && IsWindowReady()) {
        shutdown();
    }
}

ArcadeRender::ArcadeRender(ArcadeRender&&) noexcept = default;
ArcadeRender& ArcadeRender::operator=(ArcadeRender&& other) noexcept {
    if (this != &other) {
        if (impl_ && impl_->initialized && IsWindowReady()) {
            shutdown();
        }
        impl_ = std::move(other.impl_);
    }
    return *this;
}

bool ArcadeRender::initialize() {
    if (!impl_) {
        impl_ = std::make_unique<Impl>();
    }
    if (impl_->initialized) {
        return true;
    }
    if (!IsWindowReady()) {
        return false;
    }

    impl_->shader = LoadShaderFromMemory(kLightingVertexShader, kLightingFragmentShader);
    if (impl_->shader.id == 0) {
        return false;
    }
    impl_->shader.locs[SHADER_LOC_VERTEX_POSITION] = GetShaderLocationAttrib(impl_->shader, "vertexPosition");
    impl_->shader.locs[SHADER_LOC_VERTEX_TEXCOORD01] = GetShaderLocationAttrib(impl_->shader, "vertexTexCoord");
    impl_->shader.locs[SHADER_LOC_VERTEX_NORMAL] = GetShaderLocationAttrib(impl_->shader, "vertexNormal");
    impl_->shader.locs[SHADER_LOC_VERTEX_COLOR] = GetShaderLocationAttrib(impl_->shader, "vertexColor");
    impl_->shader.locs[SHADER_LOC_MATRIX_MVP] = GetShaderLocation(impl_->shader, "mvp");
    impl_->shader.locs[SHADER_LOC_MATRIX_MODEL] = GetShaderLocation(impl_->shader, "matModel");
    impl_->shader.locs[SHADER_LOC_MATRIX_NORMAL] = GetShaderLocation(impl_->shader, "matNormal");
    impl_->shader.locs[SHADER_LOC_COLOR_DIFFUSE] = GetShaderLocation(impl_->shader, "colDiffuse");
    impl_->shader.locs[SHADER_LOC_MAP_DIFFUSE] = GetShaderLocation(impl_->shader, "texture0");

    impl_->sunDirectionLoc = GetShaderLocation(impl_->shader, "sunDirection");
    impl_->sunColorLoc = GetShaderLocation(impl_->shader, "sunColor");
    impl_->skyAmbientLoc = GetShaderLocation(impl_->shader, "skyAmbient");
    impl_->groundAmbientLoc = GetShaderLocation(impl_->shader, "groundAmbient");
    impl_->fogColorLoc = GetShaderLocation(impl_->shader, "fogColor");
    impl_->fogStartLoc = GetShaderLocation(impl_->shader, "fogStart");
    impl_->fogEndLoc = GetShaderLocation(impl_->shader, "fogEnd");
    impl_->viewPositionLoc = GetShaderLocation(impl_->shader, "viewPos");
    impl_->glossLoc = GetShaderLocation(impl_->shader, "materialGloss");
    impl_->exposureLoc = GetShaderLocation(impl_->shader, "exposure");

    impl_->material = LoadMaterialDefault();
    impl_->material.shader = impl_->shader;
    impl_->bodies[0] = makeBody(BuggyBodyStyle::BeachBuggy);
    impl_->bodies[1] = makeBody(BuggyBodyStyle::Rally);
    impl_->bodies[2] = makeBody(BuggyBodyStyle::Speedster);
    impl_->bodies[3] = makeBody(BuggyBodyStyle::Utility);
    impl_->box = makeUnitBox();
    impl_->cylinder = makeCylinder(14);
    impl_->cone = makeCone(14);
    impl_->sphere = makeUvSphere(10, 16);
    impl_->tire = makeWheelTire();
    impl_->rim = makeWheelRim();
    impl_->spring = makeSpring();
    impl_->leaf = makeLeaf();
    impl_->rock = makeFacetedRock();
    impl_->roof = makeHipRoof();
    impl_->boatHull = makeBoatHull();
    impl_->shadow = makeGroundDisc(28);
    impl_->loadAuthoredAssets();
    impl_->initialized = true;
    setLighting(DirectionalLightFog{});
    return true;
}

void ArcadeRender::shutdown() {
    if (!impl_ || !impl_->initialized) {
        return;
    }
    for (Mesh& body : impl_->bodies) {
        UnloadMesh(body);
        body = {};
    }
    for (Mesh* mesh : {&impl_->box, &impl_->cylinder, &impl_->cone, &impl_->sphere, &impl_->tire, &impl_->rim,
                       &impl_->spring, &impl_->leaf, &impl_->rock, &impl_->roof, &impl_->boatHull, &impl_->shadow}) {
        UnloadMesh(*mesh);
        *mesh = {};
    }
    UnloadMaterial(impl_->material);
    impl_->material = {};
    for (auto& car : impl_->authoredCars) {
        car.reset();
    }
    for (auto& driver : impl_->authoredDrivers) {
        driver.reset();
    }
    for (auto& track : impl_->authoredTracks) {
        track.reset();
    }
    impl_->shader = {};
    impl_->initialized = false;
}

bool ArcadeRender::ready() const {
    return impl_ && impl_->initialized;
}

AuthoredAssetAuditResult ArcadeRender::auditAuthoredAssets() const {
    if (!ready()) {
        AuthoredAssetAuditResult result;
        result.loadFailures = 1;
        result.failures = 1;
        return result;
    }
    return impl_->auditAuthoredAssets();
}

void ArcadeRender::setLighting(const DirectionalLightFog& lighting) {
    if (!ready()) {
        return;
    }
    const Vector3 sunDirection = normalized(lighting.sunDirection, {-0.42f, 0.78f, -0.46f});
    const Vector3 sunColor = colorVector(lighting.sunColor);
    const Vector3 skyAmbient = multiply(colorVector(lighting.skyAmbient), 0.56f);
    const Vector3 groundAmbient = multiply(colorVector(lighting.groundAmbient), 0.34f);
    const Vector3 fogColor = colorVector(lighting.fogColor);
    const float fogStart = std::max(0.0f, lighting.fogStart);
    const float fogEnd = std::max(fogStart + 0.01f, lighting.fogEnd);
    const float exposure = std::max(0.01f, lighting.exposure);
    impl_->setUniform(impl_->sunDirectionLoc, &sunDirection, SHADER_UNIFORM_VEC3);
    impl_->setUniform(impl_->sunColorLoc, &sunColor, SHADER_UNIFORM_VEC3);
    impl_->setUniform(impl_->skyAmbientLoc, &skyAmbient, SHADER_UNIFORM_VEC3);
    impl_->setUniform(impl_->groundAmbientLoc, &groundAmbient, SHADER_UNIFORM_VEC3);
    impl_->setUniform(impl_->fogColorLoc, &fogColor, SHADER_UNIFORM_VEC3);
    impl_->setUniform(impl_->fogStartLoc, &fogStart, SHADER_UNIFORM_FLOAT);
    impl_->setUniform(impl_->fogEndLoc, &fogEnd, SHADER_UNIFORM_FLOAT);
    impl_->setUniform(impl_->viewPositionLoc, &lighting.cameraPosition, SHADER_UNIFORM_VEC3);
    impl_->setUniform(impl_->exposureLoc, &exposure, SHADER_UNIFORM_FLOAT);
}

Shader ArcadeRender::worldShader() const {
    return ready() ? impl_->shader : Shader{};
}

bool ArcadeRender::drawAuthoredTrack(std::size_t trackIndex) {
    return ready() && impl_->drawAuthoredTrack(trackIndex);
}

void ArcadeRender::drawBuggy(const BuggyVisualSpec& spec, const BuggyRenderState& state) {
    if (ready()) {
        impl_->drawBuggy(spec, state);
    }
}

void ArcadeRender::drawTropicalProp(const TropicalPropSpec& spec, const TropicalPropState& state) {
    if (ready()) {
        impl_->drawTropicalProp(spec, state);
    }
}

}  // namespace arcade_render
