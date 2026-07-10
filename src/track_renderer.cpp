#include "track_renderer.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

namespace harbor {
namespace {

constexpr std::array<float, 13> kLaneCuts = {
    -1.72f, -1.38f, -1.08f, -0.94f, -0.80f, -0.42f, 0.0f, 0.42f, 0.80f, 0.94f, 1.08f, 1.38f, 1.72f,
};
constexpr size_t kSegmentsPerChunk = 48;

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
    return add(sample.center, add(scale(sample.lateral, sample.halfWidth * lane), {0.0f, crown, 0.0f}));
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
    const size_t rows = segmentCount + 1;
    const size_t columns = kLaneCuts.size();
    std::vector<float> vertices;
    std::vector<float> texcoords;
    std::vector<float> normals;
    std::vector<unsigned char> colors;
    std::vector<unsigned short> indices;
    vertices.reserve(rows * columns * 3);
    texcoords.reserve(rows * columns * 2);
    normals.reserve(rows * columns * 3);
    colors.reserve(rows * columns * 4);
    indices.reserve(segmentCount * (columns - 1) * 6);

    for (size_t row = 0; row < rows; ++row) {
        const size_t unwrapped = start + row;
        const size_t index = unwrapped % samples.size();
        const TrackRenderSample& sample = samples[index];
        const TrackRenderSample& previous = samples[(index + samples.size() - 1) % samples.size()];
        const TrackRenderSample& next = samples[(index + 1) % samples.size()];
        const Vector3 forward = normalize3(subtract(next.center, previous.center));
        Vector3 normal = normalize3(cross3(sample.lateral, forward));
        if (normal.y < 0.0f) {
            normal = negate(normal);
        }
        const float distance = sample.progress + (unwrapped >= samples.size() ? totalProgress : 0.0f);
        for (size_t column = 0; column < columns; ++column) {
            const float lane = kLaneCuts[column];
            appendVertex(vertices, texcoords, normals, colors, samplePoint(sample, lane), normal, lane * 1.8f,
                         distance * 0.022f, surfaceColor(sample, lane));
        }
    }

    for (size_t row = 0; row < segmentCount; ++row) {
        for (size_t column = 0; column + 1 < columns; ++column) {
            const auto a = static_cast<unsigned short>(row * columns + column);
            const auto b = static_cast<unsigned short>((row + 1) * columns + column);
            const auto c = static_cast<unsigned short>((row + 1) * columns + column + 1);
            const auto d = static_cast<unsigned short>(row * columns + column + 1);
            indices.insert(indices.end(), {a, c, b, a, d, c});
        }
    }
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
            const int grain = static_cast<int>(hash & 15u) - 8;
            const int striation = static_cast<int>(3.0f * std::sin(static_cast<float>(y) * 0.31f + static_cast<float>(x) * 0.07f));
            const unsigned char value = static_cast<unsigned char>(std::clamp(238 + grain + striation, 214, 252));
            ImageDrawPixel(&image, x, y, {value, value, static_cast<unsigned char>(std::min(255, value + 3)), 255});
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
        chunks_.push_back({model, samples[midpoint].progress});
    }
    ready_ = !chunks_.empty();
}

void TrackRenderer::draw(float progress, float visibleRange) const {
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
        if (distance >= -32.0f - chunkAllowance && distance <= visibleRange + chunkAllowance) {
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
