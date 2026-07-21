#include "glb_asset.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <utility>

namespace formula_forge::assets {
namespace {

constexpr float kAnimationFramesPerSecond = 60.0f;

Vector3 boundsDimensions(BoundingBox bounds) {
    return {
        bounds.max.x - bounds.min.x,
        bounds.max.y - bounds.min.y,
        bounds.max.z - bounds.min.z,
    };
}

bool inRange(Vector3 value, const DimensionLimits& limits) {
    return value.x >= limits.minimum.x && value.x <= limits.maximum.x &&
           value.y >= limits.minimum.y && value.y <= limits.maximum.y &&
           value.z >= limits.minimum.z && value.z <= limits.maximum.z;
}

bool hasUsableModelData(const Model& model) {
    if (model.meshCount <= 0 || model.materialCount <= 0 ||
        model.meshes == nullptr || model.materials == nullptr || model.meshMaterial == nullptr) {
        return false;
    }
    for (int index = 0; index < model.meshCount; ++index) {
        const Mesh& mesh = model.meshes[index];
        if (mesh.vertexCount <= 0 || mesh.vertices == nullptr ||
            model.meshMaterial[index] < 0 || model.meshMaterial[index] >= model.materialCount) {
            return false;
        }
    }
    return true;
}

void setError(std::string* destination, std::string message) {
    if (destination != nullptr) {
        *destination = std::move(message);
    }
}

}  // namespace

GlbAsset::GlbAsset(GlbAsset&& other) noexcept
    : model_(other.model_),
      animations_(other.animations_),
      animationCount_(other.animationCount_),
      bounds_(other.bounds_),
      metersToWorld_(other.metersToWorld_),
      loaded_(other.loaded_) {
    other.model_ = {};
    other.animations_ = nullptr;
    other.animationCount_ = 0;
    other.loaded_ = false;
}

GlbAsset& GlbAsset::operator=(GlbAsset&& other) noexcept {
    if (this == &other) {
        return *this;
    }
    release();
    model_ = other.model_;
    animations_ = other.animations_;
    animationCount_ = other.animationCount_;
    bounds_ = other.bounds_;
    metersToWorld_ = other.metersToWorld_;
    loaded_ = other.loaded_;
    other.model_ = {};
    other.animations_ = nullptr;
    other.animationCount_ = 0;
    other.loaded_ = false;
    return *this;
}

GlbAsset::~GlbAsset() {
    release();
}

std::optional<GlbAsset> GlbAsset::load(
    const std::string& glbPath,
    const GlbLoadOptions& options,
    std::string* error) {
    if (options.metersToWorld <= 0.0f || !std::isfinite(options.metersToWorld)) {
        setError(error, "metersToWorld must be finite and positive");
        return std::nullopt;
    }
    if (std::filesystem::path(glbPath).extension() != ".glb") {
        setError(error, "asset must use the .glb runtime format: " + glbPath);
        return std::nullopt;
    }
    if (!std::filesystem::is_regular_file(glbPath)) {
        setError(error, "GLB asset does not exist: " + glbPath);
        return std::nullopt;
    }

    GlbAsset asset;
    asset.model_ = LoadModel(glbPath.c_str());
    asset.loaded_ = true;
    // IsModelValid() also requires every populated VBO slot to be nonzero.
    // GLES2 deliberately CPU-skins models and leaves bone VBO slots empty, so
    // validate the loaded model data that this wrapper actually consumes.
    if (!hasUsableModelData(asset.model_)) {
        setError(error, "raylib failed to load GLB asset: " + glbPath);
        return std::nullopt;
    }
    asset.bounds_ = GetModelBoundingBox(asset.model_);
    asset.metersToWorld_ = options.metersToWorld;

    const Vector3 dimensions = asset.dimensionsMeters();
    if (options.dimensions && !inRange(dimensions, *options.dimensions)) {
        setError(
            error,
            "GLB dimensions are outside the integration contract: " +
                std::to_string(dimensions.x) + " x " +
                std::to_string(dimensions.y) + " x " +
                std::to_string(dimensions.z) + " meters (X/Y/Z)");
        return std::nullopt;
    }

    if (options.loadAnimations) {
        asset.animations_ = LoadModelAnimations(glbPath.c_str(), &asset.animationCount_);
        if (asset.animationCount_ > 0 && asset.animations_ == nullptr) {
            setError(error, "raylib failed to allocate GLB animations: " + glbPath);
            return std::nullopt;
        }
        for (int index = 0; index < asset.animationCount_; ++index) {
            const ModelAnimation& animation = asset.animations_[index];
            if (animation.keyframeCount <= 0 || animation.keyframePoses == nullptr) {
                setError(error, "GLB contains an empty animation: " + glbPath);
                return std::nullopt;
            }
            if (!IsModelAnimationValid(asset.model_, animation)) {
                setError(error, "GLB contains an animation incompatible with its model: " + glbPath);
                return std::nullopt;
            }
        }
    }
    return asset;
}

Vector3 GlbAsset::dimensionsMeters() const {
    return boundsDimensions(bounds_);
}

int GlbAsset::findAnimation(std::string_view name) const {
    for (int index = 0; index < animationCount_; ++index) {
        const std::string_view animationName(animations_[index].name);
        if (animationName == name) {
            return index;
        }
    }
    return -1;
}

int GlbAsset::countAnimation(std::string_view name) const {
    int count = 0;
    for (int index = 0; index < animationCount_; ++index) {
        const std::string_view animationName(animations_[index].name);
        count += animationName == name ? 1 : 0;
    }
    return count;
}

bool GlbAsset::sampleAnimation(int animationIndex, float timeSeconds) {
    if (!loaded_ || animationIndex < 0 || animationIndex >= animationCount_ || !std::isfinite(timeSeconds)) {
        return false;
    }
    const ModelAnimation& animation = animations_[animationIndex];
    if (animation.keyframeCount <= 0) {
        return false;
    }
    const float frame = std::fmod(std::max(0.0f, timeSeconds) * kAnimationFramesPerSecond,
                                  static_cast<float>(animation.keyframeCount));
    UpdateModelAnimation(model_, animation, frame);
    return true;
}

bool GlbAsset::sampleAnimation(std::string_view name, float timeSeconds, int fallbackIndex) {
    const int namedIndex = findAnimation(name);
    return sampleAnimation(namedIndex >= 0 ? namedIndex : fallbackIndex, timeSeconds);
}

void GlbAsset::draw(Vector3 worldPosition, float yawRadians, Color tint) const {
    if (!loaded_) {
        return;
    }
    DrawModelEx(
        model_,
        worldPosition,
        Vector3{0.0f, 1.0f, 0.0f},
        yawRadians * RAD2DEG,
        Vector3{metersToWorld_, metersToWorld_, metersToWorld_},
        tint);
}

void GlbAsset::release() {
    if (animations_ != nullptr) {
        UnloadModelAnimations(animations_, animationCount_);
        animations_ = nullptr;
        animationCount_ = 0;
    }
    if (loaded_) {
        UnloadModel(model_);
        model_ = {};
        loaded_ = false;
    }
}

}  // namespace formula_forge::assets
