#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>

#include <raylib.h>

namespace arcade_render {

enum class FormulaBodyStyle : std::uint8_t {
    Standard,
    Rally,
    Speedster,
    Utility,
};

enum class DriverHeadwear : std::uint8_t {
    Hair,
    Helmet,
    Bandana,
    Visor,
};

enum class TropicalPropKind : std::uint8_t {
    Palm,
    RockCluster,
    BeachHut,
    MarketStall,
    FishingBoat,
    DockCrane,
    TrackBanner,
    Torch,
};

struct DirectionalLightFog {
    // Direction from the shaded surface toward the sun.
    Vector3 sunDirection{-0.42f, 0.78f, -0.46f};
    Color sunColor{255, 238, 196, 255};
    Color skyAmbient{117, 177, 205, 255};
    Color groundAmbient{85, 93, 74, 255};
    Color fogColor{146, 213, 226, 255};
    Vector3 cameraPosition{};
    float fogStart = 72.0f;
    float fogEnd = 210.0f;
    float exposure = 1.0f;
};

struct DriverVisualSpec {
    Color skin{191, 121, 73, 255};
    Color shirt{40, 164, 170, 255};
    Color headwear{255, 205, 66, 255};
    Color hair{44, 31, 24, 255};
    Color gloves{34, 42, 47, 255};
    DriverHeadwear headwearStyle = DriverHeadwear::Helmet;
    std::uint8_t variant = 0;
};

struct FormulaVisualSpec {
    FormulaBodyStyle style = FormulaBodyStyle::Standard;
    Color body{225, 58, 52, 255};
    Color accent{255, 202, 61, 255};
    Color trim{38, 45, 49, 255};
    Color glass{72, 188, 211, 220};
    Color rim{244, 186, 49, 255};
    DriverVisualSpec driver{};
    float width = 2.45f;
    float length = 4.15f;
    float bodyHeight = 1.12f;
    float wheelRadius = 0.62f;
    float wheelWidth = 0.43f;
    float rideHeight = 0.28f;
};

struct FormulaRenderState {
    // World-space tire contact-plane origin. Forward is local +Z.
    Vector3 position{};
    Vector3 shadowPosition{};
    bool useGroundShadowPosition = false;
    float headingRadians = 0.0f;
    float pitchRadians = 0.0f;
    float rollRadians = 0.0f;
    float steeringRadians = 0.0f;
    float wheelSpinRadians = 0.0f;
    std::array<float, 4> suspensionCompression{};  // FL, FR, RL, RR in [0, 1].
    float suspensionTravel = 0.18f;
    float speedNormalized = 0.0f;
    float boostAmount = 0.0f;
    // Presentation inputs. They are deliberately independent from the vehicle
    // simulation so AI, replays, and garage previews can share this renderer.
    float brakeAmount = 0.0f;
    float dustAmount = 0.0f;
    float airborneAmount = 0.0f;
    float visualTime = 0.0f;
    float damageFlash = 0.0f;
    float driverLean = 0.0f;
};

struct TropicalPropSpec {
    TropicalPropKind kind = TropicalPropKind::Palm;
    Color primary{55, 157, 83, 255};
    Color accent{244, 191, 60, 255};
    Color detail{111, 75, 45, 255};
    std::uint32_t variant = 0;
};

struct TropicalPropState {
    Vector3 position{};
    float yawRadians = 0.0f;
    float scale = 1.0f;
    float windPhase = 0.0f;
};

FormulaVisualSpec MakeFormulaVisualSpec(FormulaBodyStyle style, Color body, Color accent);
TropicalPropSpec MakeTropicalPropSpec(TropicalPropKind kind, std::uint32_t variant = 0);

struct AuthoredAssetAuditResult {
    int loadedCars = 0;
    int loadedDrivers = 0;
    int loadedTracks = 0;
    int dimensionChecks = 0;
    int animationChecks = 0;
    int loadFailures = 0;
    int clipFailures = 0;
    int failures = 0;
    bool ok = false;
};

class ArcadeRender {
public:
    ArcadeRender();
    ~ArcadeRender();

    ArcadeRender(const ArcadeRender&) = delete;
    ArcadeRender& operator=(const ArcadeRender&) = delete;
    ArcadeRender(ArcadeRender&&) noexcept;
    ArcadeRender& operator=(ArcadeRender&&) noexcept;

    // A valid raylib window/context must exist before initialize(). Call shutdown()
    // before CloseWindow(). Drawing functions are intended for BeginMode3D().
    bool initialize();
    void shutdown();
    bool ready() const;
    [[nodiscard]] AuthoredAssetAuditResult auditAuthoredAssets() const;

    void setLighting(const DirectionalLightFog& lighting);
    // Borrowed handle for static world materials. The caller must not unload it,
    // and it becomes invalid after shutdown().
    Shader worldShader() const;
    // Draws one complete authored world layer. A false return means callers
    // must retain the procedural environment, road, and prop fallback.
    bool drawAuthoredTrack(std::size_t trackIndex);
    void drawFormulaCar(const FormulaVisualSpec& spec, const FormulaRenderState& state);
    void drawTropicalProp(const TropicalPropSpec& spec, const TropicalPropState& state);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace arcade_render
