#include "track_renderer.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

namespace harbor {
namespace {

constexpr std::array<float, 19> kLaneCuts = {
    -3.40f, -2.70f, -2.10f, -1.72f, -1.38f, -1.08f, -0.94f, -0.80f, -0.42f, 0.0f,
    0.42f,  0.80f,  0.94f,  1.08f,  1.38f,  1.72f,  2.10f,  2.70f,  3.40f,
};
constexpr size_t kSegmentsPerChunk = 12;

Vector3 add(Vector3 a, Vector3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
Vector3 subtract(Vector3 a, Vector3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
Vector3 scale(Vector3 value, float amount) { return {value.x * amount, value.y * amount, value.z * amount}; }
Vector3 negate(Vector3 value) { return {-value.x, -value.y, -value.z}; }
Vector3 cross3(Vector3 a, Vector3 b) {
    return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}
float length3(Vector3 value) { return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z); }
Vector3 normalize3(Vector3 value) {
    const float magnitude = length3(value);
    return magnitude > 0.00001f ? scale(value, 1.0f / magnitude) : Vector3{0.0f, 1.0f, 0.0f};
}
float distance3(Vector3 a, Vector3 b) { return length3(subtract(a, b)); }

float smoothstep01(float value) {
    value = std::clamp(value, 0.0f, 1.0f);
    return value * value * (3.0f - 2.0f * value);
}

Color shade(Color color, float amount) {
    const auto channel = [amount](unsigned char value) {
        return static_cast<unsigned char>(std::clamp(static_cast<float>(value) * amount, 0.0f, 255.0f));
    };
    return {channel(color.r), channel(color.g), channel(color.b), color.a};
}

Color mix(Color a, Color b, float t) {
    t = std::clamp(t, 0.0f, 1.0f);
    const auto channel = [t](unsigned char x, unsigned char y) {
        return static_cast<unsigned char>(static_cast<float>(x) + (static_cast<float>(y) - static_cast<float>(x)) * t);
    };
    return {channel(a.r, b.r), channel(a.g, b.g), channel(a.b, b.b), channel(a.a, b.a)};
}

Color surfaceColor(const TrackRenderSample& sample, float lane) {
    const float distance = std::abs(lane);
    if (distance <= 0.80f) {
        return shade(sample.road, 1.06f - distance / 0.80f * 0.13f);
    }
    if (distance <= 1.04f) {
        return mix(sample.road, sample.shoulder, (distance - 0.80f) / 0.24f);
    }
    return mix(sample.shoulder, sample.terrain, std::clamp((distance - 1.04f) / 0.34f, 0.0f, 1.0f));
}

Vector3 samplePoint(const TrackRenderSample& sample, float lane) {
    const float crown = std::max(0.0f, 1.0f - std::abs(lane) / 0.82f) * 0.045f;
    const float laneMagnitude = std::abs(lane);
    const float spreadStart = sample.terrainSpread < 0.999f ? 1.04f : 1.38f;
    const float spreadLane = laneMagnitude <= spreadStart
                                 ? lane
                                 : std::copysign(spreadStart + (laneMagnitude - spreadStart) * sample.terrainSpread, lane);
    Vector3 point = add(sample.center, add(scale(sample.lateral, sample.halfWidth * spreadLane),
                                           {0.0f, crown + sample.bankHeight * std::clamp(lane, -1.2f, 1.2f), 0.0f}));
    const float terrainBlend = smoothstep01((std::abs(lane) - 1.38f) / (3.40f - 1.38f));
    point.y += (sample.terrainEdgeElevation - point.y) * terrainBlend;
    return point;
}

struct SurfaceVertex {
    Vector3 position{};
    float u = 0.0f;
    float v = 0.0f;
    float lane = 0.0f;
    Color color = WHITE;
};

Vector3 horizontalLateral(Vector3 from, Vector3 to) {
    const Vector3 delta = subtract(to, from);
    const float magnitude = std::sqrt(delta.x * delta.x + delta.z * delta.z);
    return magnitude > 0.00001f ? Vector3{-delta.z / magnitude, 0.0f, delta.x / magnitude} : Vector3{1.0f, 0.0f, 0.0f};
}

TrackRenderSample orientSample(TrackRenderSample sample, Vector3 horizontal) {
    sample.lateral = horizontal;
    return sample;
}

SurfaceVertex surfaceVertex(const TrackRenderSample& sample, float lane, float distance) {
    return {samplePoint(sample, lane), lane * 1.8f, distance * 0.022f, lane, surfaceColor(sample, lane)};
}

template <typename Visitor>
void visitSurfaceTriangles(std::span<const TrackRenderSample> samples, size_t start, size_t segmentCount, float totalProgress,
                           Visitor&& visitor) {
    for (size_t segment = 0; segment < segmentCount; ++segment) {
        const size_t unwrapped = start + segment;
        const size_t index = unwrapped % samples.size();
        const size_t nextIndex = (index + 1) % samples.size();
        const size_t afterIndex = (index + 2) % samples.size();
        const TrackRenderSample& rawCurrent = samples[index];
        const TrackRenderSample& rawNext = samples[nextIndex];
        const Vector3 segmentLateral = horizontalLateral(rawCurrent.center, rawNext.center);
        const Vector3 followingLateral = horizontalLateral(rawNext.center, samples[afterIndex].center);
        const TrackRenderSample current = orientSample(rawCurrent, segmentLateral);
        const TrackRenderSample next = orientSample(rawNext, segmentLateral);
        const TrackRenderSample incomingJoin = orientSample(rawNext, segmentLateral);
        const TrackRenderSample outgoingJoin = orientSample(rawNext, followingLateral);
        const float currentDistance = rawCurrent.progress + (unwrapped >= samples.size() ? totalProgress : 0.0f);
        const float nextDistance = rawNext.progress + (unwrapped + 1 >= samples.size() ? totalProgress : 0.0f);

        for (size_t column = 0; column + 1 < kLaneCuts.size(); ++column) {
            const float laneA = kLaneCuts[column];
            const float laneB = kLaneCuts[column + 1];
            const float lane = (laneA + laneB) * 0.5f;
            const SurfaceVertex a = surfaceVertex(current, laneA, currentDistance);
            const SurfaceVertex b = surfaceVertex(next, laneA, nextDistance);
            const SurfaceVertex c = surfaceVertex(next, laneB, nextDistance);
            const SurfaceVertex d = surfaceVertex(current, laneB, currentDistance);
            visitor(a, c, b, rawCurrent.progress, lane, false);
            visitor(a, d, c, rawCurrent.progress, lane, false);

            const SurfaceVertex joinA = surfaceVertex(incomingJoin, laneA, nextDistance);
            const SurfaceVertex joinB = surfaceVertex(outgoingJoin, laneA, nextDistance);
            const SurfaceVertex joinC = surfaceVertex(outgoingJoin, laneB, nextDistance);
            const SurfaceVertex joinD = surfaceVertex(incomingJoin, laneB, nextDistance);
            visitor(joinA, joinC, joinB, rawNext.progress, lane, true);
            visitor(joinA, joinD, joinC, rawNext.progress, lane, true);
        }
    }
}

void appendVertex(std::vector<float>& vertices, std::vector<float>& texcoords, std::vector<float>& normals,
                  std::vector<unsigned char>& colors, Vector3 position, Vector3 normal, float u, float v, Color color) {
    vertices.insert(vertices.end(), {position.x, position.y, position.z});
    texcoords.insert(texcoords.end(), {u, v});
    normals.insert(normals.end(), {normal.x, normal.y, normal.z});
    colors.insert(colors.end(), {color.r, color.g, color.b, color.a});
}

Mesh uploadMesh(std::vector<float>& vertices, std::vector<float>& texcoords, std::vector<float>& normals,
                std::vector<unsigned char>& colors, std::vector<unsigned short>& indices) {
    Mesh mesh{};
    mesh.vertexCount = static_cast<int>(vertices.size() / 3);
    mesh.triangleCount = static_cast<int>(indices.size() / 3);
    mesh.vertices = static_cast<float*>(MemAlloc(vertices.size() * sizeof(float)));
    mesh.texcoords = static_cast<float*>(MemAlloc(texcoords.size() * sizeof(float)));
    mesh.normals = static_cast<float*>(MemAlloc(normals.size() * sizeof(float)));
    mesh.colors = static_cast<unsigned char*>(MemAlloc(colors.size() * sizeof(unsigned char)));
    mesh.indices = static_cast<unsigned short*>(MemAlloc(indices.size() * sizeof(unsigned short)));
    std::copy(vertices.begin(), vertices.end(), mesh.vertices);
    std::copy(texcoords.begin(), texcoords.end(), mesh.texcoords);
    std::copy(normals.begin(), normals.end(), mesh.normals);
    std::copy(colors.begin(), colors.end(), mesh.colors);
    std::copy(indices.begin(), indices.end(), mesh.indices);
    UploadMesh(&mesh, false);
    return mesh;
}

Model makeSurfaceChunk(std::span<const TrackRenderSample> samples, size_t start, size_t segmentCount, float totalProgress) {
    std::vector<float> vertices;
    std::vector<float> texcoords;
    std::vector<float> normals;
    std::vector<unsigned char> colors;
    std::vector<unsigned short> indices;
    const size_t triangleCount = segmentCount * (kLaneCuts.size() - 1) * 4;
    vertices.reserve(triangleCount * 9);
    texcoords.reserve(triangleCount * 6);
    normals.reserve(triangleCount * 9);
    colors.reserve(triangleCount * 12);
    indices.reserve(triangleCount * 3);

    visitSurfaceTriangles(samples, start, segmentCount, totalProgress,
                          [&](SurfaceVertex a, SurfaceVertex b, SurfaceVertex c, float, float, bool) {
                              Vector3 normal = normalize3(cross3(subtract(b.position, a.position), subtract(c.position, a.position)));
                              if (normal.y < 0.0f) {
                                  std::swap(b, c);
                                  normal = negate(normal);
                              }
                              const auto first = static_cast<unsigned short>(vertices.size() / 3);
                              appendVertex(vertices, texcoords, normals, colors, a.position, normal, a.u, a.v, a.color);
                              appendVertex(vertices, texcoords, normals, colors, b.position, normal, b.u, b.v, b.color);
                              appendVertex(vertices, texcoords, normals, colors, c.position, normal, c.u, c.v, c.color);
                              indices.insert(indices.end(), {first, static_cast<unsigned short>(first + 1),
                                                            static_cast<unsigned short>(first + 2)});
                          });
    return LoadModelFromMesh(uploadMesh(vertices, texcoords, normals, colors, indices));
}

Texture2D makeDetailTexture() {
    constexpr int size = 256;
    Image image = GenImageColor(size, size, WHITE);
    uint32_t hash = 0x8b31a4d7u;
    for (int y = 0; y < size; ++y) {
        for (int x = 0; x < size; ++x) {
            hash ^= hash << 13;
            hash ^= hash >> 17;
            hash ^= hash << 5;
            const int grain = static_cast<int>(hash & 31u) - 16;
            const float macro = std::sin(static_cast<float>(x) * 0.105f + static_cast<float>(y) * 0.029f) * 10.0f;
            const float crossGrain = std::sin(static_cast<float>(x) * 0.037f - static_cast<float>(y) * 0.071f) * 7.0f;
            const int aggregate = ((x / 7 + y / 5) % 11 == 0) ? -17 : 0;
            const int raw = static_cast<int>(226.0f + macro + crossGrain) + grain + aggregate;
            const unsigned char value = static_cast<unsigned char>(std::clamp(raw, 180, 255));
            ImageDrawPixel(&image, x, y,
                           {value, static_cast<unsigned char>(std::clamp(raw - 2, 176, 255)),
                            static_cast<unsigned char>(std::clamp(raw - 5, 172, 255)), 255});
        }
    }
    Texture2D texture = LoadTextureFromImage(image);
    UnloadImage(image);
    SetTextureFilter(texture, TEXTURE_FILTER_BILINEAR);
    SetTextureWrap(texture, TEXTURE_WRAP_REPEAT);
    return texture;
}

float signedLoopDistance(float from, float to, float total) {
    float distance = to - from;
    while (distance > total * 0.5f) {
        distance -= total;
    }
    while (distance < -total * 0.5f) {
        distance += total;
    }
    return distance;
}

}  // namespace

TrackGradientAudit AuditTrackGradients(std::span<const TrackRenderSample> samples, float limitDegrees) {
    TrackGradientAudit result;
    if (samples.size() < 3) {
        return result;
    }

    const float totalProgress = samples.back().progress + distance3(samples.back().center, samples.front().center);
    const auto inspectTriangle = [&](Vector3 a, Vector3 b, Vector3 c, float progress, float lane, bool join) {
        const Vector3 normal = normalize3(cross3(subtract(b, a), subtract(c, a)));
        const float vertical = std::clamp(std::abs(normal.y), 0.0f, 1.0f);
        const float gradient = std::acos(vertical) * RAD2DEG;
        if (join) {
            result.maxJoinGradientDegrees = std::max(result.maxJoinGradientDegrees, gradient);
        } else {
            result.maxSegmentGradientDegrees = std::max(result.maxSegmentGradientDegrees, gradient);
        }
        const bool core = std::abs(lane) <= 0.80f;
        const size_t phaseBin = std::min(TrackGradientAudit::kPhaseBinCount - 1,
                                         static_cast<size_t>(progress / std::max(0.001f, totalProgress) *
                                                             static_cast<float>(TrackGradientAudit::kPhaseBinCount)));
        result.phaseMaxGradientDegrees[phaseBin] = std::max(result.phaseMaxGradientDegrees[phaseBin], gradient);
        const bool road = std::abs(lane) <= 1.38f;
        if (core) {
            result.maxCoreGradientDegrees = std::max(result.maxCoreGradientDegrees, gradient);
        }
        if (road) {
            result.maxRoadGradientDegrees = std::max(result.maxRoadGradientDegrees, gradient);
        } else {
            result.maxTerrainGradientDegrees = std::max(result.maxTerrainGradientDegrees, gradient);
        }
        if (gradient > limitDegrees) {
            ++result.trianglesAboveLimit;
            result.joinTrianglesAboveLimit += join ? 1 : 0;
            result.segmentTrianglesAboveLimit += join ? 0 : 1;
            result.coreTrianglesAboveLimit += core ? 1 : 0;
            ++result.phaseTrianglesAboveLimit[phaseBin];
            if (road) {
                ++result.roadTrianglesAboveLimit;
            } else {
                ++result.terrainTrianglesAboveLimit;
            }
        }
        if (gradient > result.maxGradientDegrees) {
            result.maxGradientDegrees = gradient;
            result.progress = progress;
            result.lane = lane;
        }
    };

    visitSurfaceTriangles(samples, 0, samples.size(), totalProgress,
                          [&](const SurfaceVertex& a, const SurfaceVertex& b, const SurfaceVertex& c, float progress, float lane,
                              bool join) {
                              inspectTriangle(a.position, b.position, c.position, progress, lane, join);
                          });
    return result;
}

void TrackRenderer::build(std::span<const TrackRenderSample> samples, Shader shader) {
    unload();
    if (samples.size() < 3) {
        return;
    }
    totalProgress_ = samples.back().progress + distance3(samples.back().center, samples.front().center);
    detailTexture_ = makeDetailTexture();

    for (size_t start = 0; start < samples.size(); start += kSegmentsPerChunk) {
        const size_t segmentCount = std::min(kSegmentsPerChunk, samples.size() - start);
        Model model = makeSurfaceChunk(samples, start, segmentCount, totalProgress_);
        SetMaterialTexture(&model.materials[0], MATERIAL_MAP_DIFFUSE, detailTexture_);
        if (IsShaderValid(shader)) {
            model.materials[0].shader = shader;
        }
        const size_t midpoint = (start + segmentCount / 2) % samples.size();
        Vector3 center{};
        for (size_t offset = 0; offset <= segmentCount; ++offset) {
            center = add(center, samples[(start + offset) % samples.size()].center);
        }
        center = scale(center, 1.0f / static_cast<float>(segmentCount + 1));
        float radius = 0.0f;
        for (size_t offset = 0; offset <= segmentCount; ++offset) {
            const TrackRenderSample& sample = samples[(start + offset) % samples.size()];
            radius = std::max(radius, distance3(center, sample.center) + sample.halfWidth * 3.4f);
        }
        chunks_.push_back({model, samples[midpoint].progress, center, radius});
    }
    ready_ = !chunks_.empty();
}

void TrackRenderer::draw(float progress, float visibleRange, float rearVisibleRange,
                         Vector3 cameraPosition, float spatialRange) const {
    if (!ready_) {
        return;
    }
    progress = std::fmod(progress, totalProgress_);
    if (progress < 0.0f) {
        progress += totalProgress_;
    }
    const float chunkAllowance = totalProgress_ / std::max(1.0f, static_cast<float>(chunks_.size())) * 0.60f;
    for (const Chunk& chunk : chunks_) {
        const float distance = signedLoopDistance(progress, chunk.progress, totalProgress_);
        // Retain a long forward corridor, but reject geometry behind the chase
        // camera so it cannot cross the near plane. Small chunks make the edge
        // move smoothly instead of dropping a large section at once.
        const bool courseVisible = distance >= -rearVisibleRange - chunkAllowance &&
                                   distance <= visibleRange + chunkAllowance;
        const bool spatialVisible = spatialRange > 0.0f &&
                                    distance3(cameraPosition, chunk.center) <= spatialRange + chunk.radius;
        if (courseVisible || spatialVisible) {
            DrawModel(chunk.model, {}, 1.0f, WHITE);
        }
    }
}

void TrackRenderer::unload() {
    if (!ready_) {
        return;
    }
    for (Chunk& chunk : chunks_) {
        UnloadModel(chunk.model);
    }
    chunks_.clear();
    UnloadTexture(detailTexture_);
    detailTexture_ = {};
    totalProgress_ = 1.0f;
    ready_ = false;
}

}  // namespace harbor
