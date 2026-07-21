#pragma once

#include <optional>
#include <string>
#include <string_view>

#include <raylib.h>

namespace formula_forge::assets {

struct DimensionLimits {
    // raylib/glTF axes: width X, height Y, length Z, all in meters.
    Vector3 minimum{};
    Vector3 maximum{};
};

struct GlbLoadOptions {
    float metersToWorld = 1.0f;
    std::optional<DimensionLimits> dimensions;
    bool loadAnimations = true;
};

class GlbAsset {
public:
    GlbAsset(const GlbAsset&) = delete;
    GlbAsset& operator=(const GlbAsset&) = delete;
    GlbAsset(GlbAsset&& other) noexcept;
    GlbAsset& operator=(GlbAsset&& other) noexcept;
    ~GlbAsset();

    // A raylib window/OpenGL context must exist before this call.
    static std::optional<GlbAsset> load(
        const std::string& glbPath,
        const GlbLoadOptions& options = {},
        std::string* error = nullptr);

    [[nodiscard]] const Model& model() const { return model_; }
    [[nodiscard]] BoundingBox localBounds() const { return bounds_; }
    [[nodiscard]] Vector3 dimensionsMeters() const;
    [[nodiscard]] float metersToWorld() const { return metersToWorld_; }
    [[nodiscard]] int animationCount() const { return animationCount_; }
    [[nodiscard]] int findAnimation(std::string_view name) const;
    [[nodiscard]] int countAnimation(std::string_view name) const;

    // GLB clips are sampled by raylib at 60 frames per second.
    bool sampleAnimation(int animationIndex, float timeSeconds);
    bool sampleAnimation(std::string_view name, float timeSeconds, int fallbackIndex = -1);
    void draw(Vector3 worldPosition, float yawRadians, Color tint = WHITE) const;

private:
    GlbAsset() = default;
    void release();

    Model model_{};
    ModelAnimation* animations_ = nullptr;
    int animationCount_ = 0;
    BoundingBox bounds_{};
    float metersToWorld_ = 1.0f;
    bool loaded_ = false;
};

}  // namespace formula_forge::assets
