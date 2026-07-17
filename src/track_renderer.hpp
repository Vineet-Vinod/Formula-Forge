#pragma once

#include <array>
#include <span>
#include <vector>

#include <raylib.h>

namespace harbor {

struct TrackRenderSample {
    Vector3 center{};
    Vector3 lateral{1.0f, 0.0f, 0.0f};
    float halfWidth = 8.0f;
    float progress = 0.0f;
    Color road{178, 104, 63, 255};
    Color shoulder{224, 175, 102, 255};
    Color terrain{224, 195, 118, 255};
    int zone = 0;
    float bankHeight = 0.0f;
    float terrainSpread = 1.0f;
};

struct TrackGradientAudit {
    static constexpr size_t kPhaseBinCount = 20;
    float maxGradientDegrees = 0.0f;
    float maxCoreGradientDegrees = 0.0f;
    float maxRoadGradientDegrees = 0.0f;
    float maxTerrainGradientDegrees = 0.0f;
    float progress = 0.0f;
    float lane = 0.0f;
    int trianglesAboveLimit = 0;
    int coreTrianglesAboveLimit = 0;
    int roadTrianglesAboveLimit = 0;
    int terrainTrianglesAboveLimit = 0;
    int segmentTrianglesAboveLimit = 0;
    int joinTrianglesAboveLimit = 0;
    float maxSegmentGradientDegrees = 0.0f;
    float maxJoinGradientDegrees = 0.0f;
    std::array<float, kPhaseBinCount> phaseMaxGradientDegrees{};
    std::array<int, kPhaseBinCount> phaseTrianglesAboveLimit{};
};

TrackGradientAudit AuditTrackGradients(std::span<const TrackRenderSample> samples, float limitDegrees);

class TrackRenderer {
public:
    TrackRenderer() = default;
    TrackRenderer(const TrackRenderer&) = delete;
    TrackRenderer& operator=(const TrackRenderer&) = delete;

    void build(std::span<const TrackRenderSample> samples, Shader shader);
    void draw(float progress, float visibleRange = 170.0f, float rearVisibleRange = 24.0f) const;
    void unload();
    bool ready() const { return ready_; }

private:
    struct Chunk {
        Model model{};
        float progress = 0.0f;
    };

    std::vector<Chunk> chunks_;
    Texture2D detailTexture_{};
    float totalProgress_ = 1.0f;
    bool ready_ = false;
};

}  // namespace harbor
