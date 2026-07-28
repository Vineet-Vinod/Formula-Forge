#include "game.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <limits>
#include <memory>
#include <random>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

#include <raylib.h>
#include <rlgl.h>
#include <SDL3/SDL.h>

#include "arcade_audio.hpp"
#include "agent_play_protocol.hpp"
#include "arcade_hud.hpp"
#include "arcade_race.hpp"
#include "arcade_render.hpp"
#include "arcade_vehicle.hpp"
#include "core_math.hpp"
#include "track_renderer.hpp"
#include "track_types.hpp"
#include "track_catalog.hpp"
#include "track_clearance_audit.hpp"

namespace {

constexpr float kFixedDt = 1.0f / 120.0f;
// Uncommitted Monza experiment: preserve the validated solo controller in
// clean air, then layer racecraft around it only when other cars are present.
constexpr bool kMonzaRacecraftExperiment = true;
constexpr float kRenderScale = 0.085f;
constexpr float kSpaRenderForwardRange = 850.0f;
constexpr float kSpaRenderRearRange = 170.0f;
constexpr int kKartCount = 11;
constexpr int kSampleCount = 1536;
constexpr float kRoadSurfaceRatio = 0.40f;
constexpr float kRoadLaneInset = 4.0f;
constexpr float kHardBoundaryInset = 18.0f;
constexpr float kMetricCurbWidthMeters = 0.85f;
constexpr float kMetricRunoffWidthMeters = 4.0f;
constexpr float kMetricTerrainReachMeters = 36.0f;
constexpr float kMetricBarrierOffsetMeters = 6.0f;
constexpr float kMetricBarrierThicknessMeters = 0.34f;
constexpr float kMetricRoadSurfaceOffsetMeters = 0.06f;
constexpr float kVisualTireClearanceWorld = 0.010f;
constexpr float kTerrainSurfaceY = -0.18f;
constexpr float kTrackSurfaceLift = 0.018f;
constexpr float kKartWheelGroundClearance = 0.42f;
constexpr float kContactProgressWindow = 240.0f;
constexpr float kContactVerticalWindow = 7.0f;
constexpr float kStandardGravityMetersPerSecondSquared = 9.80665f;
constexpr int kInfiniteLaps = 0;
constexpr std::array<int, 4> kLapOptions = {2, 5, 10, kInfiniteLaps};
constexpr int kLapOptionCount = static_cast<int>(kLapOptions.size());
constexpr float kLoadingScreenSeconds = 2.35f;
constexpr float kMenuSteerThreshold = 0.20f;
constexpr float kTcamBackMeters = 0.68f;
constexpr float kTcamHeightMeters = 1.84f;
constexpr float kTcamLookAheadMeters = 38.0f;
constexpr float kTcamTargetHeightMeters = 0.38f;
constexpr float kTcamFovDegrees = 80.0f;
constexpr float kGridFirstRowClearanceMeters = 1.0f;
constexpr float kGridSlotGapMeters = 3.0f;
constexpr float kDrsTopSpeedExtraKph = 30.0f;
constexpr float kDrsDetectionMaximumGapSeconds = 1.0f;
constexpr float kMonzaDraftTopSpeedScale = 1.018f;
constexpr float kAiRaceOptimalLapRatio = 1.0f;
constexpr float kMonzaPeakSoloLapSeconds = 68.800f;
constexpr float kAiRaceControllerPlanRatio = 1.0f;
constexpr float kAiCornerVariabilityStdDev = 0.05f;

constexpr float gridSlotGapMeters(
    TrackLayoutId layout) {
    // This mirrors the generated starting_grid_slots asset contract.
    return layout == TrackLayoutId::Monza
               ? 12.0f
               : kGridSlotGapMeters;
}

float runtimeGridSideForSlot(int slot) {
    // Blender's plan-Y axis becomes the opposite lateral direction after the
    // authored glTF track is transformed into raylib world space.
    const float authoredSide = slot % 2 == 0 ? -1.0f : 1.0f;
    return -authoredSide;
}

bool isMetricCircuit(TrackLayoutId layout) {
    (void)layout;
    return true;
}

float speedKphPerSimulationUnit(TrackLayoutId layout) {
    return isMetricCircuit(layout) ? 3.6f / kTrackSimulationUnitsPerMeter : 1.22f;
}

const TrackCatalogEntry* catalogEntryForLayout(TrackLayoutId layout) {
    return findTrackCatalogEntry(layout);
}

float trackProgressRenderScale(TrackLayoutId layout) {
    return isMetricCircuit(layout) ? kTrackSimulationUnitsPerMeter * kRenderScale : kRenderScale;
}

float authoredRoadSurfaceLift(TrackLayoutId layout) {
    return isMetricCircuit(layout)
               ? kMetricRoadSurfaceOffsetMeters * kTrackSimulationUnitsPerMeter * kRenderScale
               : kTrackSurfaceLift;
}

struct MapSpec3D {
    TrackLayoutId layout;
    const char* name;
    const char* eventName;
    const char* subtitle;
    const char* backstory;
};

constexpr std::array<MapSpec3D, 12> kMaps = {{
    {TrackLayoutId::Spa, "SPA-FRANCORCHAMPS", "BELGIAN GRAND PRIX", "7.004 KM / 19 TURNS / 102.2 M RELIEF",
     "An Ardennes classic that climbs steeply from Eau Rouge to Raidillon and the Kemmel Straight before descending home."},
    {TrackLayoutId::Suzuka, "SUZUKA", "SUZUKA GRAND PRIX", "5.807 KM / 18 TURNS / FIGURE EIGHT",
     "A flowing figure-eight with rhythmic esses, a climbing crossover and a committed final sector."},
    {TrackLayoutId::Silverstone, "SILVERSTONE", "SILVERSTONE GRAND PRIX", "5.891 KM / 18 TURNS / FAST SWEEPERS",
     "A historic airfield circuit built around fast direction changes, broad sweepers and long, open straights."},
    {TrackLayoutId::Monza, "MONZA", "MONZA GRAND PRIX", "5.793 KM / 11 TURNS / HIGH SPEED",
     "Long royal-park straights broken by heavy braking zones, chicanes and the broad Curva Alboreto."},
    {TrackLayoutId::Interlagos, "INTERLAGOS", "INTERLAGOS GRAND PRIX", "4.309 KM / 15 TURNS / ANTI-CLOCKWISE",
     "A compact Sao Paulo bowl that drops through the Senna S and climbs hard from Juncao back to the line."},
    {TrackLayoutId::Shanghai, "SHANGHAI", "CHINESE GRAND PRIX", "5.451 KM / 16 TURNS / 1.175 KM BACK STRAIGHT",
     "Tightening and opening snail complexes frame a long back straight and one of the lap's hardest braking zones."},
    {TrackLayoutId::Bahrain, "BAHRAIN", "BAHRAIN GRAND PRIX", "5.412 KM / 15 TURNS / CLOCKWISE",
     "Floodlit desert straights lead into hard braking zones, a downhill off-camber left and traction-heavy exits."},
    {TrackLayoutId::Sepang, "SEPANG", "MALAYSIAN GRAND PRIX", "5.543 KM / 15 TURNS / TROPICAL",
     "Two long straights bookend opposing hairpins, while broad linked bends reward commitment in humid conditions."},
    {TrackLayoutId::Cota, "COTA", "UNITED STATES GRAND PRIX", "5.513 KM / 20 TURNS / 30.9 M RELIEF",
     "A steep climb to Turn 1 opens an anti-clockwise lap of rapid esses, a long back straight and stadium corners."},
    {TrackLayoutId::Istanbul, "ISTANBUL PARK", "TURKISH GRAND PRIX", "5.338 KM / 14 TURNS / ANTI-CLOCKWISE",
     "A steep, flowing lap is defined by the sustained four-apex Turn 8 and the heavy braking sequence at the end."},
    {TrackLayoutId::Hockenheim, "HOCKENHEIM", "GERMAN GRAND PRIX", "4.574 KM / 17 TURNS / CLOCKWISE",
     "The modern layout pairs the long Parabolika run and hairpin with a compact, technical stadium section."},
    {TrackLayoutId::Buddh, "BUDDH", "INDIAN GRAND PRIX", "5.125 KM / 16 TURNS / CLOCKWISE",
     "A very wide lap climbs through its opening sector, then mixes long straights with a sweeping technical middle."},
}};

struct RaceResult3D {
    int kartIndex = 0;
    int position = 1;
    float finishTimeSeconds = 0.0f;
    int lapsCompleted = 0;
};

struct FormulaCornerTarget {
    const char* name;
    float lapFraction;
    float speedKph;
    int gear;
    bool fullThrottle;
};

// Dry qualifying references, rounded from representative modern F1 telemetry.
// These are used as handling calibration targets, not as scripted car speeds.
constexpr std::array<FormulaCornerTarget, 11> kSpaFormulaTargets = {{
    {"La Source", 0.055f, 77.0f, 2, false},
    {"Eau Rouge/Raidillon", 0.145f, 302.0f, 8, true},
    {"Les Combes", 0.320f, 156.0f, 4, false},
    {"Bruxelles", 0.420f, 125.0f, 4, false},
    {"No Name", 0.479f, 208.0f, 5, false},
    {"Pouhon", 0.560f, 284.0f, 7, true},
    {"Fagnes", 0.650f, 182.0f, 5, false},
    {"Campus", 0.674f, 160.0f, 4, false},
    {"Stavelot", 0.720f, 243.0f, 6, false},
    {"Blanchimont", 0.875f, 307.0f, 8, true},
    {"Bus Stop", 0.965f, 72.0f, 2, false},
}};

constexpr std::array<FormulaCornerTarget, 9> kSuzukaFormulaTargets = {{
    {"Turn 1/2", 0.097f, 172.0f, 5, false},
    {"S Curves", 0.153f, 205.0f, 5, false},
    {"Dunlop", 0.222f, 245.0f, 6, false},
    {"Degner 1", 0.319f, 267.0f, 7, true},
    {"Degner 2", 0.347f, 139.0f, 4, false},
    {"Hairpin", 0.458f, 74.0f, 3, false},
    {"Spoon", 0.690f, 168.0f, 5, false},
    {"130R", 0.819f, 297.0f, 8, true},
    {"Casio Triangle", 0.875f, 89.0f, 3, false},
}};

constexpr std::array<FormulaCornerTarget, 12> kSilverstoneFormulaTargets = {{
    {"Abbey", 0.042f, 295.0f, 8, true},
    {"Village", 0.125f, 113.0f, 3, false},
    {"The Loop", 0.153f, 94.0f, 3, false},
    {"Brooklands", 0.315f, 156.0f, 4, false},
    {"Luffield", 0.347f, 114.0f, 4, false},
    {"Woodcote", 0.430f, 259.0f, 6, true},
    {"Copse", 0.500f, 290.0f, 8, true},
    {"Maggotts", 0.583f, 263.0f, 7, false},
    {"Becketts", 0.611f, 226.0f, 6, false},
    {"Stowe", 0.833f, 230.0f, 6, false},
    {"Vale", 0.903f, 99.0f, 3, false},
    {"Club", 0.945f, 171.0f, 4, false},
}};

constexpr std::array<FormulaCornerTarget, 7> kMonzaFormulaTargets = {{
    {"Rettifilo", 0.056f, 73.0f, 2, false},
    {"Curva Grande", 0.153f, 294.0f, 8, true},
    {"Roggia", 0.278f, 113.0f, 3, false},
    {"Lesmo 1", 0.347f, 207.0f, 5, false},
    {"Lesmo 2", 0.430f, 190.0f, 5, false},
    {"Ascari", 0.611f, 194.0f, 5, false},
    {"Parabolica", 0.806f, 215.0f, 5, false},
}};

constexpr std::array<FormulaCornerTarget, 9> kInterlagosFormulaTargets = {{
    {"Senna S", 0.097f, 110.0f, 3, false},
    {"Curva do Sol", 0.167f, 228.0f, 6, false},
    {"Descida do Lago", 0.347f, 167.0f, 4, false},
    {"Ferradura", 0.500f, 226.0f, 6, false},
    {"Pinheirinho", 0.583f, 108.0f, 3, false},
    {"Bico de Pato", 0.667f, 88.0f, 3, false},
    {"Mergulho", 0.720f, 206.0f, 5, false},
    {"Juncao", 0.778f, 119.0f, 3, false},
    {"Final sweep", 0.910f, 267.0f, 7, true},
}};

constexpr std::array<FormulaCornerTarget, 9> kShanghaiFormulaTargets = {{
    {"Turns 1-2", 0.107f, 108.0f, 3, false},
    {"Turns 3-4", 0.135f, 95.0f, 3, false},
    {"Turn 6", 0.258f, 82.0f, 2, false},
    {"Turns 7-8", 0.369f, 188.0f, 6, false},
    {"Turns 9-10", 0.436f, 150.0f, 4, false},
    {"Turn 11", 0.539f, 90.0f, 3, false},
    {"Turns 12-13", 0.562f, 135.0f, 5, false},
    {"Turn 14", 0.848f, 70.0f, 2, false},
    {"Back straight", 0.750f, 315.0f, 8, true},
}};

constexpr std::array<FormulaCornerTarget, 9> kBahrainFormulaTargets = {{
    {"Turn 1", 0.099f, 82.0f, 2, false},
    {"Turns 2-3", 0.129f, 145.0f, 4, false},
    {"Turn 4", 0.247f, 105.0f, 3, false},
    {"Turns 5-7", 0.313f, 205.0f, 6, false},
    {"Turn 8", 0.381f, 90.0f, 2, false},
    {"Turn 10", 0.464f, 78.0f, 2, false},
    {"Turns 11-12", 0.636f, 195.0f, 5, false},
    {"Turn 13", 0.723f, 125.0f, 3, false},
    {"Main straight", 0.965f, 285.0f, 8, true},
}};

constexpr std::array<FormulaCornerTarget, 9> kSepangFormulaTargets = {{
    {"Turns 1-2", 0.135f, 85.0f, 2, false},
    {"Turn 4", 0.289f, 120.0f, 3, false},
    {"Turns 5-6", 0.465f, 220.0f, 6, false},
    {"Turn 9", 0.572f, 78.0f, 2, false},
    {"Turn 11", 0.635f, 120.0f, 3, false},
    {"Turns 12-13", 0.698f, 205.0f, 5, false},
    {"Turn 14", 0.761f, 110.0f, 3, false},
    {"Turn 15", 0.931f, 80.0f, 2, false},
    {"Back straight", 0.845f, 300.0f, 8, true},
}};

constexpr std::array<FormulaCornerTarget, 9> kCotaFormulaTargets = {{
    {"Turn 1", 0.064f, 78.0f, 2, false},
    {"Turns 3-6", 0.225f, 235.0f, 6, false},
    {"Turns 7-9", 0.300f, 190.0f, 5, false},
    {"Turn 11", 0.414f, 82.0f, 2, false},
    {"Turn 12", 0.631f, 88.0f, 2, false},
    {"Turns 13-15", 0.705f, 105.0f, 3, false},
    {"Turns 16-18", 0.805f, 190.0f, 5, false},
    {"Turn 20", 0.917f, 120.0f, 3, false},
    {"Back straight", 0.535f, 315.0f, 8, true},
}};

constexpr std::array<FormulaCornerTarget, 9> kIstanbulFormulaTargets = {{
    {"Turn 1", 0.046f, 95.0f, 3, false},
    {"Turns 2-3", 0.195f, 185.0f, 5, false},
    {"Turns 4-5", 0.255f, 145.0f, 4, false},
    {"Turns 6-7", 0.390f, 125.0f, 3, false},
    {"Turn 8 entry", 0.590f, 245.0f, 6, false},
    {"Turn 8 exit", 0.635f, 230.0f, 6, false},
    {"Turns 9-10", 0.870f, 110.0f, 3, false},
    {"Turns 12-14", 0.925f, 85.0f, 2, false},
    {"Back straight", 0.760f, 310.0f, 8, true},
}};

constexpr std::array<FormulaCornerTarget, 9> kHockenheimFormulaTargets = {{
    {"Nordkurve", 0.061f, 175.0f, 5, false},
    {"Turn 2", 0.183f, 95.0f, 3, false},
    {"Turn 3", 0.214f, 145.0f, 4, false},
    {"Spitzkehre", 0.458f, 65.0f, 2, false},
    {"Turn 7", 0.557f, 135.0f, 4, false},
    {"Mercedes", 0.618f, 115.0f, 3, false},
    {"Mobil 1", 0.763f, 170.0f, 5, false},
    {"Sachs", 0.832f, 90.0f, 2, false},
    {"Parabolika", 0.340f, 310.0f, 8, true},
}};

constexpr std::array<FormulaCornerTarget, 9> kBuddhFormulaTargets = {{
    {"Turn 1", 0.061f, 95.0f, 3, false},
    {"Turn 3", 0.136f, 82.0f, 2, false},
    {"Turn 4", 0.388f, 75.0f, 2, false},
    {"Turns 5-7", 0.510f, 145.0f, 4, false},
    {"Turns 8-9", 0.570f, 175.0f, 5, false},
    {"Turn 10", 0.687f, 125.0f, 3, false},
    {"Turns 11-12", 0.770f, 205.0f, 5, false},
    {"Turn 16", 0.918f, 120.0f, 3, false},
    {"Back straight", 0.275f, 315.0f, 8, true},
}};

std::span<const FormulaCornerTarget> formulaCornerTargets(TrackLayoutId layout) {
    switch (layout) {
        case TrackLayoutId::Spa: return kSpaFormulaTargets;
        case TrackLayoutId::Suzuka: return kSuzukaFormulaTargets;
        case TrackLayoutId::Silverstone: return kSilverstoneFormulaTargets;
        case TrackLayoutId::Monza: return kMonzaFormulaTargets;
        case TrackLayoutId::Interlagos: return kInterlagosFormulaTargets;
        case TrackLayoutId::Shanghai: return kShanghaiFormulaTargets;
        case TrackLayoutId::Bahrain: return kBahrainFormulaTargets;
        case TrackLayoutId::Sepang: return kSepangFormulaTargets;
        case TrackLayoutId::Cota: return kCotaFormulaTargets;
        case TrackLayoutId::Istanbul: return kIstanbulFormulaTargets;
        case TrackLayoutId::Hockenheim: return kHockenheimFormulaTargets;
        case TrackLayoutId::Buddh: return kBuddhFormulaTargets;
    }
    return {};
}

struct AiCircuitProfile {
    const char* name;
    float baselineLapSeconds;
    float minimumAuditLapSeconds;
    float maximumAuditLapSeconds;
    float minimumLaunchLapSeconds;
    float maximumLaunchLapSeconds;
    int maximumBrakeDriftFrames;
    float maximumRoadViolationMeters;
    float maximumProgressStep;
};

// Each circuit gets its demonstrated minimum-time flying-lap baseline. The
// baseline drives player adaptation; the audit envelope keeps each circuit
// honest about pace, braking stability, and its projection/road geometry
// without forcing every layout through one arbitrary threshold.
constexpr AiCircuitProfile aiCircuitProfile(TrackLayoutId layout) {
    switch (layout) {
        case TrackLayoutId::Spa:
            return {"spa", 108.417f, 105.0f, 112.0f, 110.0f, 116.0f, 1500, 4.5f, 3.5f};
        case TrackLayoutId::Suzuka:
            return {"suzuka", 98.025f, 105.0f, 112.0f, 110.0f, 117.0f, 1500, 5.5f, 2.5f};
        case TrackLayoutId::Silverstone:
            return {"silverstone", 91.292f, 95.0f, 102.0f, 99.0f, 106.0f, 1500, 4.5f, 2.5f};
        case TrackLayoutId::Monza:
            return {"monza", 71.742f, 71.0f, 76.0f, 75.0f, 81.0f, 1500, 4.5f, 2.5f};
        case TrackLayoutId::Interlagos:
            return {"interlagos", 73.075f, 73.0f, 79.0f, 78.0f, 84.0f, 1500, 4.5f, 2.5f};
        case TrackLayoutId::Shanghai:
            return {"shanghai", 99.400f, 102.5f, 107.5f, 106.5f, 112.5f, 1500, 4.5f, 2.7f};
        case TrackLayoutId::Bahrain:
            return {"bahrain", 92.758f, 93.0f, 99.0f, 98.0f, 103.0f, 1800, 4.5f, 2.5f};
        case TrackLayoutId::Sepang:
            return {"sepang", 97.125f, 98.0f, 103.0f, 102.0f, 108.0f, 1800, 4.5f, 2.5f};
        case TrackLayoutId::Cota:
            return {"cota", 103.900f, 105.0f, 111.0f, 109.0f, 116.0f, 1800, 4.5f, 2.5f};
        case TrackLayoutId::Istanbul:
            return {"istanbul", 92.483f, 93.0f, 98.0f, 97.0f, 102.0f, 1800, 4.5f, 2.5f};
        case TrackLayoutId::Hockenheim:
            return {"hockenheim", 80.750f, 78.0f, 83.0f, 82.0f, 87.0f, 1800, 4.5f, 2.5f};
        case TrackLayoutId::Buddh:
            return {"buddh", 87.700f, 88.0f, 93.0f, 92.0f, 97.0f, 1800, 4.5f, 2.5f};
    }
    return {"unknown", 90.0f, 60.0f, 220.0f, 60.0f, 230.0f, 1500, 4.5f, 2.5f};
}

struct AiTimeTrialProfile {
    int smoothingSpan;
    float roadFraction;
    float speedReserve;
    float brakePlanningFraction;
    float lookaheadBaseMeters;
    float lookaheadSpeedSeconds;
    float lookaheadMaximumMeters;
    float headingGain;
    float crossTrackGain;
    float benchmarkLapSeconds;
};

constexpr AiTimeTrialProfile aiTimeTrialProfile(TrackLayoutId layout) {
    switch (layout) {
        case TrackLayoutId::Spa:
            return {6, 0.00f, 0.975f, 0.82f, 14.0f, 0.18f, 34.0f, 0.60f, 0.68f, 108.417f};
        case TrackLayoutId::Suzuka:
            return {6, 0.30f, 0.990f, 0.70f, 6.0f, 0.10f, 18.0f, 0.90f, 0.95f, 98.025f};
        case TrackLayoutId::Silverstone:
            return {6, 0.75f, 1.000f, 0.76f, 16.0f, 0.30f, 50.0f, 0.86f, 0.72f, 91.292f};
        case TrackLayoutId::Monza:
            return {2, 0.850f, 1.040f, 0.56f, 14.75f, 0.190f, 50.0f, 0.86f, 0.72f, 70.9333f};
        case TrackLayoutId::Interlagos:
            return {6, 0.75f, 1.000f, 0.68f, 12.0f, 0.30f, 50.0f, 0.86f, 0.72f, 73.075f};
        case TrackLayoutId::Shanghai:
            return {6, 0.50f, 1.000f, 0.78f, 8.0f, 0.12f, 24.0f, 0.86f, 0.72f, 99.400f};
        case TrackLayoutId::Bahrain:
            return {6, 0.50f, 0.980f, 0.74f, 16.0f, 0.40f, 46.0f, 0.86f, 0.72f, 92.758f};
        case TrackLayoutId::Sepang:
            return {6, 0.40f, 1.000f, 0.74f, 8.0f, 0.12f, 24.0f, 0.86f, 0.72f, 97.125f};
        case TrackLayoutId::Cota:
            return {6, 0.40f, 1.000f, 0.74f, 4.0f, 0.18f, 24.0f, 1.00f, 0.90f, 103.900f};
        case TrackLayoutId::Istanbul:
            return {6, 0.40f, 0.980f, 0.70f, 8.0f, 0.12f, 24.0f, 0.86f, 0.72f, 92.483f};
        case TrackLayoutId::Hockenheim:
            return {6, 0.30f, 1.000f, 0.74f, 8.0f, 0.12f, 24.0f, 0.86f, 0.72f, 80.750f};
        case TrackLayoutId::Buddh:
            return {6, 0.50f, 1.000f, 0.70f, 8.0f, 0.12f, 24.0f, 0.86f, 0.72f, 87.700f};
    }
    return {6, 0.50f, 0.985f, 0.82f, 10.0f, 0.25f, 38.0f, 0.86f, 0.72f, 120.0f};
}

constexpr std::array<float, 24>
    kMonzaOptimizedLineOffsetsMeters = {
        -0.51098f, 0.0f, -1.0f, 0.635078f,
        2.89874f, -0.5f, 1.02535f, -2.21272f,
        0.422858f, -1.58885f, 2.50481f, 0.995015f,
        0.00821996f, 2.07876f, -0.0949583f, 0.663471f,
        0.198252f, -1.68023f, -3.0f, 0.0f,
        -3.0f, 0.286772f, -1.30252f, 0.424598f};

Color mix(Color a, Color b, float t) {
    t = std::clamp(t, 0.0f, 1.0f);
    const auto channel = [t](unsigned char av, unsigned char bv) {
        return static_cast<unsigned char>(std::clamp(static_cast<float>(av) + (static_cast<float>(bv) - static_cast<float>(av)) * t,
                                                     0.0f, 255.0f));
    };
    return {channel(a.r, b.r), channel(a.g, b.g), channel(a.b, b.b), channel(a.a, b.a)};
}

Color shade(Color c, float amount) {
    const auto channel = [amount](unsigned char v) {
        return static_cast<unsigned char>(std::clamp(static_cast<float>(v) * amount, 0.0f, 255.0f));
    };
    return {channel(c.r), channel(c.g), channel(c.b), c.a};
}

Vector3 toWorld(Vec2 p, float elevation = 0.0f) {
    return {p.x * kRenderScale, elevation * kRenderScale, p.y * kRenderScale};
}

Vector3 add(Vector3 a, Vector3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
Vector3 sub(Vector3 a, Vector3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
Vector3 mul(Vector3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
Vector3 lift(Vector3 v, float amount) { return {v.x, v.y + amount, v.z}; }

float signedDistanceToLoop(float from, float to, float total) {
    float d = to - from;
    while (d > total * 0.5f) {
        d -= total;
    }
    while (d < -total * 0.5f) {
        d += total;
    }
    return d;
}

bool hasArg(int argc, char** argv, std::string_view arg) {
    for (int i = 1; i < argc; ++i) {
        if (arg == argv[i]) {
            return true;
        }
    }
    return false;
}

struct TrackPoint3D {
    Vec2 pos;
    Vec2 tangent{1.0f, 0.0f};
    Vec2 normal{0.0f, 1.0f};
    float progress = 0.0f;
    float width = 180.0f;
    float elevation = 0.0f;
    float bank = 0.0f;
    float curvature = 0.0f;
    float signedCurvature = 0.0f;
    float grade = 0.0f;
    float launchVelocity = 0.0f;
    Color road = {206, 122, 67, 255};
    Color shoulder = {239, 199, 111, 255};
    Color natural = {244, 207, 124, 255};
    int zone = 0;
    bool metricCircuit = false;
};

float metricGroundElevation(const TrackPoint3D& point, float lane) {
    const float half = std::max(1.0f, point.width * 0.5f);
    const float crossfall = point.bank / half;
    const float roadHalf = point.width * kRoadSurfaceRatio;
    const float transition = roadHalf + kMetricRunoffWidthMeters * kTrackSimulationUnitsPerMeter;
    const float outer = roadHalf + kMetricTerrainReachMeters * kTrackSimulationUnitsPerMeter;
    const float laneMagnitude = std::abs(lane);
    if (laneMagnitude <= transition) {
        return point.elevation + crossfall * lane;
    }
    const float side = lane < 0.0f ? -1.0f : 1.0f;
    const float transitionHeight = crossfall * side * transition;
    const float blend = smoothstep(std::clamp((laneMagnitude - transition) /
                                                   std::max(1.0f, outer - transition),
                                               0.0f, 1.0f));
    return point.elevation + lerp(transitionHeight, 0.0f, blend);
}

float bankedElevation(const TrackPoint3D& point, float lane) {
    if (point.metricCircuit) {
        return metricGroundElevation(point, lane);
    }
    const float half = std::max(1.0f, point.width * 0.5f);
    return point.elevation + point.bank * std::clamp(lane / half, -1.2f, 1.2f);
}

float bankRollDegrees(const TrackPoint3D& point, float lane = 0.0f) {
    constexpr float kDerivativeHalfSpan = 1.0f;
    const float rise = bankedElevation(point, lane + kDerivativeHalfSpan) -
                       bankedElevation(point, lane - kDerivativeHalfSpan);
    return -std::atan2(rise, kDerivativeHalfSpan * 2.0f) * RAD2DEG;
}

struct Prop3D {
    enum class Type { Palm, Rock, Hut, Boat, Market, Crane, Crystal, Torch, Gate, Chevron, Cliff, Sail };

    Type type = Type::Palm;
    float progress = 0.0f;
    float side = 0.0f;
    float scale = 1.0f;
    Color color = {60, 159, 91, 255};
};

struct ZoneMaterial3D {
    Color road = {214, 142, 76, 255};
    Color shoulder = {240, 198, 108, 255};
    Color natural = {244, 207, 124, 255};
};

ZoneMaterial3D baseZoneMaterial(int zone) {
    switch (zone) {
        case 1:
            return {{150, 101, 65, 255}, {176, 128, 82, 255}, {204, 168, 103, 255}};
        case 2:
            return {{211, 134, 84, 255}, {232, 181, 100, 255}, {229, 174, 98, 255}};
        case 3:
            return {{98, 98, 99, 255}, {111, 108, 99, 255}, {125, 119, 101, 255}};
        case 4:
            return {{137, 153, 100, 255}, {122, 166, 96, 255}, {109, 169, 94, 255}};
        case 5:
            return {{147, 108, 74, 255}, {123, 150, 124, 255}, {82, 168, 166, 255}};
        case 6:
            return {{216, 149, 82, 255}, {239, 200, 112, 255}, {241, 199, 109, 255}};
        default:
            return {{224, 156, 86, 255}, {242, 205, 119, 255}, {244, 209, 130, 255}};
    }
}

ZoneMaterial3D mixMaterial(ZoneMaterial3D a, ZoneMaterial3D b, float t) {
    return {mix(a.road, b.road, t), mix(a.shoulder, b.shoulder, t), mix(a.natural, b.natural, t)};
}

int zoneForPhase(float phase) {
    if (phase < 0.30f) {
        return 0;
    }
    if (phase < 0.60f) {
        return 2;
    }
    if (phase < 0.90f) {
        return 4;
    }
    return 0;
}

float trackWidthForZone(int zone) {
    switch (zone) {
        case 2:
            return 190.0f;
        case 4:
            return 202.0f;
        default:
            return 216.0f;
    }
}

float trackWidthForPhase(float phase) {
    phase -= std::floor(phase);
    constexpr float kBlend = 0.034f;
    static constexpr std::array<std::array<float, 3>, 3> kBoundaries = {
        {{0.30f, 0.0f, 2.0f}, {0.60f, 2.0f, 4.0f}, {0.90f, 4.0f, 0.0f}}};
    float width = trackWidthForZone(zoneForPhase(phase));
    for (const auto& boundary : kBoundaries) {
        if (phase >= boundary[0] - kBlend && phase <= boundary[0] + kBlend) {
            const float blend = smoothstep((phase - boundary[0] + kBlend) / (kBlend * 2.0f));
            width = lerp(trackWidthForZone(static_cast<int>(boundary[1])), trackWidthForZone(static_cast<int>(boundary[2])), blend);
        }
    }
    return width;
}

ZoneMaterial3D materialForPhase(float phase) {
    ZoneMaterial3D material = baseZoneMaterial(zoneForPhase(phase));
    static constexpr float kBlend = 0.034f;
    static constexpr std::array<std::array<float, 3>, 3> kBoundaries = {
        {{0.30f, 0.0f, 2.0f}, {0.60f, 2.0f, 4.0f}, {0.90f, 4.0f, 0.0f}}};
    for (const auto& boundary : kBoundaries) {
        const float p = boundary[0];
        if (phase >= p - kBlend && phase <= p + kBlend) {
            const float t = smoothstep((phase - (p - kBlend)) / (kBlend * 2.0f));
            material = mixMaterial(baseZoneMaterial(static_cast<int>(boundary[1])), baseZoneMaterial(static_cast<int>(boundary[2])), t);
        }
    }
    return material;
}

float metricTrackElevationMeters(TrackLayoutId layout, float distanceMeters) {
    const TrackCatalogEntry* entry = catalogEntryForLayout(layout);
    return entry != nullptr ? sampleTrackElevationMeters(*entry, distanceMeters) : 0.0f;
}

float metricTrackWidthMeters(TrackLayoutId layout, float distanceMeters, float phase) {
    (void)phase;
    const TrackCatalogEntry* entry = catalogEntryForLayout(layout);
    return entry != nullptr ? sampleTrackWidthMeters(*entry, distanceMeters) : 14.0f;
}

float metricTrackBankDegrees(TrackLayoutId layout, float distanceMeters) {
    const TrackCatalogEntry* entry = catalogEntryForLayout(layout);
    return entry != nullptr ? sampleTrackBankDegrees(*entry, distanceMeters) : 0.0f;
}

std::span<const TrackRunoffZone> metricTrackRunoffProfile(TrackLayoutId layout) {
    const TrackCatalogEntry* entry = catalogEntryForLayout(layout);
    return entry != nullptr ? entry->runoffProfile : std::span<const TrackRunoffZone>{};
}

const TrackRunoffZone* metricRunoffZoneAt(TrackLayoutId layout, float distanceMeters,
                                          float laneMeters, float roadHalfWidthMeters) {
    const int side = laneMeters < 0.0f ? -1 : 1;
    const float runoffDistance = std::abs(laneMeters) - roadHalfWidthMeters;
    if (runoffDistance < 0.95f) {
        return nullptr;
    }
    for (const TrackRunoffZone& zone : metricTrackRunoffProfile(layout)) {
        const bool stationMatches = distanceMeters >= zone.startMeters && distanceMeters <= zone.endMeters;
        const bool sideMatches = zone.side == 0 || zone.side == side;
        if (stationMatches && sideMatches && runoffDistance <= 0.95f + zone.widthMeters) {
            return &zone;
        }
    }
    return nullptr;
}

struct TrackProjection3D {
    float progress = 0.0f;
    float lane = 0.0f;
    int nearest = 0;
};

class Track3D {
public:
    explicit Track3D(TrackLayoutId layout = TrackLayoutId::Spa) : layout_(layout) { build(); }

    float totalLength() const { return totalLength_; }
    float startProgress() const {
        const TrackCatalogEntry* entry = catalogEntryForLayout(layout_);
        return totalLength_ * (entry != nullptr ? entry->startPhase : 0.0f);
    }
    TrackLayoutId layout() const { return layout_; }
    int sampleCount() const { return static_cast<int>(samples_.size()); }
    const std::vector<TrackPoint3D>& samples() const { return samples_; }
    const std::vector<Prop3D>& props() const { return props_; }

    TrackPoint3D sample(float progress) const {
        progress = wrapDistance(progress, totalLength_);
        const float u = progress / totalLength_ * static_cast<float>(samples_.size());
        const int i0 = static_cast<int>(std::floor(u)) % sampleCount();
        const int i1 = (i0 + 1) % sampleCount();
        const float t = u - std::floor(u);
        const TrackPoint3D& a = samples_[static_cast<size_t>(i0)];
        const TrackPoint3D& b = samples_[static_cast<size_t>(i1)];

        TrackPoint3D out = a;
        out.pos = lerp(a.pos, b.pos, t);
        out.tangent = normalize(lerp(a.tangent, b.tangent, t));
        out.normal = {-out.tangent.y, out.tangent.x};
        out.progress = progress;
        out.width = lerp(a.width, b.width, t);
        out.elevation = isMetricCircuit(layout_)
                            ? metricTrackElevationMeters(layout_, progress) * kTrackSimulationUnitsPerMeter
                            : lerp(a.elevation, b.elevation, t);
        out.bank = lerp(a.bank, b.bank, t);
        out.curvature = lerp(a.curvature, b.curvature, t);
        out.signedCurvature = lerp(a.signedCurvature, b.signedCurvature, t);
        out.grade = lerp(a.grade, b.grade, t);
        out.launchVelocity = std::max(a.launchVelocity, b.launchVelocity);
        out.road = mix(a.road, b.road, t);
        out.shoulder = mix(a.shoulder, b.shoulder, t);
        out.natural = mix(a.natural, b.natural, t);
        out.zone = t < 0.5f ? a.zone : b.zone;
        return out;
    }

    const TrackPoint3D& pointAtIndex(int index) const { return samples_[static_cast<size_t>(wrappedIndex(index))]; }

    int nearestIndex(Vec2 pos) const {
        int best = 0;
        float bestDist = std::numeric_limits<float>::max();
        for (int i = 0; i < sampleCount(); ++i) {
            const float d = lengthSq(samples_[static_cast<size_t>(i)].pos - pos);
            if (d < bestDist) {
                best = i;
                bestDist = d;
            }
        }
        return best;
    }

    int nearestIndexNear(Vec2 pos, int hint, int radius = 24) const {
        int best = wrappedIndex(hint);
        float bestScore = lengthSq(samples_[static_cast<size_t>(best)].pos - pos);
        for (int offset = -radius; offset <= radius; ++offset) {
            const int index = wrappedIndex(hint + offset);
            const float d = lengthSq(samples_[static_cast<size_t>(index)].pos - pos);
            const float score = d + static_cast<float>(offset * offset) * 25.0f;
            if (score < bestScore) {
                best = index;
                bestScore = score;
            }
        }
        return best;
    }

    TrackProjection3D projectNear(Vec2 pos, int hint, int radius = 6) const {
        float bestDistanceSq = std::numeric_limits<float>::max();
        float bestProgress = pointAtIndex(hint).progress;
        int bestNearest = wrappedIndex(hint);
        const float progressStep = totalLength_ / static_cast<float>(sampleCount());
        for (int offset = -radius; offset <= radius; ++offset) {
            const int index = wrappedIndex(hint + offset);
            const Vec2 a = pointAtIndex(index).pos;
            const Vec2 b = pointAtIndex(index + 1).pos;
            const Vec2 segment = b - a;
            const float segmentLengthSq = std::max(0.0001f, lengthSq(segment));
            const float t = std::clamp(dot(pos - a, segment) / segmentLengthSq, 0.0f, 1.0f);
            const Vec2 closest = a + segment * t;
            const float distanceSq = lengthSq(pos - closest);
            if (distanceSq < bestDistanceSq) {
                bestDistanceSq = distanceSq;
                bestProgress = wrapDistance(pointAtIndex(index).progress + progressStep * t, totalLength_);
                bestNearest = wrappedIndex(index + (t >= 0.5f ? 1 : 0));
            }
        }
        const TrackPoint3D center = sample(bestProgress);
        return {bestProgress, dot(pos - center.pos, center.normal), bestNearest};
    }

    Vector3 roadPoint(const TrackPoint3D& point, float lane) const {
        return toWorld(point.pos + point.normal * lane, bankedElevation(point, lane));
    }

    void rebuild(TrackLayoutId layout) {
        if (layout == layout_ && !samples_.empty()) {
            return;
        }
        layout_ = layout;
        samples_.clear();
        props_.clear();
        build();
    }

private:
    int wrappedIndex(int index) const {
        const int count = sampleCount();
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

    TrackPoint3D decorate(TrackPoint3D point, float phase, float progress) const {
        phase -= std::floor(phase);
        const ZoneMaterial3D material = materialForPhase(phase);
        point.zone = zoneForPhase(phase);
        point.metricCircuit = isMetricCircuit(layout_);
        point.width = isMetricCircuit(layout_)
                          ? metricTrackWidthMeters(layout_, progress, phase) * kTrackSimulationUnitsPerMeter /
                                (kRoadSurfaceRatio * 2.0f)
                          : trackWidthForPhase(phase);
        if (isMetricCircuit(layout_)) {
            const float bankRadians = metricTrackBankDegrees(layout_, progress) * DEG2RAD;
            point.bank = std::tan(bankRadians) * point.width * 0.5f;
        }
        point.road = material.road;
        point.shoulder = material.shoulder;
        point.natural = material.natural;

        point.elevation = metricTrackElevationMeters(layout_, progress) * kTrackSimulationUnitsPerMeter;
        point.launchVelocity = 0.0f;
        return point;
    }

    void buildFromControl(std::span<const TrackControlPoint> control, float scale, float targetLength,
                          float simulationUnitsPerDistance = 1.0f, bool mirrorVertical = false) {
        const auto controlPoint = [&control, scale, mirrorVertical](int index) {
            const int count = static_cast<int>(control.size());
            int wrapped = index % count;
            if (wrapped < 0) {
                wrapped += count;
            }
            const TrackControlPoint& p = control[static_cast<size_t>(wrapped)];
            return Vec2{p.x * scale, p.y * scale * (mirrorVertical ? -1.0f : 1.0f)};
        };

        std::vector<Vec2> dense;
        constexpr int kSteps = 32;
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
        if (targetLength > 0.0f) {
            const float targetSpatialLength = targetLength * simulationUnitsPerDistance;
            const float correction = targetSpatialLength / std::max(0.001f, cumulative.back());
            for (Vec2& point : dense) {
                point *= correction;
            }
            cumulative.assign(dense.size() + 1, 0.0f);
            for (size_t i = 0; i < dense.size(); ++i) {
                cumulative[i + 1] = cumulative[i] + length(dense[(i + 1) % dense.size()] - dense[i]);
            }
        }
        totalLength_ = targetLength > 0.0f ? targetLength : cumulative.back();

        samples_.resize(kSampleCount);
        for (int i = 0; i < kSampleCount; ++i) {
            const float desired = totalLength_ * static_cast<float>(i) / kSampleCount;
            const float desiredSpatial = targetLength > 0.0f ? desired * simulationUnitsPerDistance : desired;
            auto it = std::upper_bound(cumulative.begin(), cumulative.end(), desiredSpatial);
            int seg = std::max(0, static_cast<int>(it - cumulative.begin()) - 1);
            if (seg >= static_cast<int>(dense.size())) {
                seg = static_cast<int>(dense.size()) - 1;
            }
            const float span = cumulative[static_cast<size_t>(seg + 1)] - cumulative[static_cast<size_t>(seg)];
            const float t = span > 0.001f ? (desiredSpatial - cumulative[static_cast<size_t>(seg)]) / span : 0.0f;
            TrackPoint3D point;
            point.progress = desired;
            point.pos = lerp(dense[static_cast<size_t>(seg)], dense[static_cast<size_t>((seg + 1) % dense.size())], t);
            samples_[static_cast<size_t>(i)] = decorate(point, desired / totalLength_, desired);
        }

        for (int i = 0; i < kSampleCount; ++i) {
            TrackPoint3D& p = samples_[static_cast<size_t>(i)];
            const Vec2 prev = samples_[static_cast<size_t>((i - 3 + kSampleCount) % kSampleCount)].pos;
            const Vec2 next = samples_[static_cast<size_t>((i + 3) % kSampleCount)].pos;
            p.tangent = normalize(next - prev);
            p.normal = {-p.tangent.y, p.tangent.x};
        }
        for (int i = 0; i < kSampleCount; ++i) {
            const Vec2 a = samples_[static_cast<size_t>((i - 8 + kSampleCount) % kSampleCount)].tangent;
            const Vec2 b = samples_[static_cast<size_t>((i + 8) % kSampleCount)].tangent;
            const float signedTurn = wrapAngle(angleOf(b) - angleOf(a));
            TrackPoint3D& p = samples_[static_cast<size_t>(i)];
            p.signedCurvature = signedTurn;
            p.curvature = std::abs(signedTurn);
            if (!isMetricCircuit(layout_)) {
                p.bank = std::clamp(-signedTurn * 140.0f, -13.0f, 13.0f);
            }
            const TrackPoint3D& elevationPrev = samples_[static_cast<size_t>((i - 2 + kSampleCount) % kSampleCount)];
            const TrackPoint3D& elevationNext = samples_[static_cast<size_t>((i + 2) % kSampleCount)];
            const float horizontalSpan = std::max(0.01f, length(elevationNext.pos - elevationPrev.pos));
            p.grade = (elevationNext.elevation - elevationPrev.elevation) / horizontalSpan;
        }

        if (!isMetricCircuit(layout_)) {
            std::array<float, kSampleCount> smoothedBank{};
            constexpr int kBankSmoothingRadius = 24;
            for (int i = 0; i < kSampleCount; ++i) {
                float weightedBank = 0.0f;
                float totalWeight = 0.0f;
                for (int offset = -kBankSmoothingRadius; offset <= kBankSmoothingRadius; ++offset) {
                    const int index = (i + offset + kSampleCount) % kSampleCount;
                    const float weight = static_cast<float>(kBankSmoothingRadius + 1 - std::abs(offset));
                    weightedBank += samples_[static_cast<size_t>(index)].bank * weight;
                    totalWeight += weight;
                }
                smoothedBank[static_cast<size_t>(i)] = weightedBank / totalWeight;
            }
            for (int i = 0; i < kSampleCount; ++i) {
                samples_[static_cast<size_t>(i)].bank = smoothedBank[static_cast<size_t>(i)];
            }
        }

        buildProps();
    }

    void build() {
        if (const TrackCatalogEntry* entry = catalogEntryForLayout(layout_)) {
            // TrackControlPoint uses Cartesian XY, while raylib drives on its
            // Y-up XZ plane. Reflecting plan Y here preserves real-world turn
            // handedness after that orientation-reversing basis conversion.
            buildFromControl(entry->centerline, entry->centerlineScale, entry->targetLengthMeters,
                             kTrackSimulationUnitsPerMeter, entry->mirrorCenterlineY);
        }
    }

    void buildProps() {
        std::mt19937 rng(3119);
        std::uniform_real_distribution<float> jitter(-24.0f, 24.0f);
        const bool metricCircuit = isMetricCircuit(layout_);
        const int count = metricCircuit ? 360 : 156;
        for (int i = 0; i < count; ++i) {
            const float p = wrapDistance(totalLength_ * (static_cast<float>(i) + 0.23f) / count + jitter(rng), totalLength_);
            const float startClearance = metricCircuit ? 90.0f : 620.0f;
            if (std::abs(signedDistanceToLoop(startProgress(), p, totalLength_)) < startClearance) {
                continue;
            }
            const TrackPoint3D tp = sample(p);
            Prop3D prop;
            prop.progress = p;
            const float sideSign = (i % 2 == 0) ? -1.0f : 1.0f;
            const float baseSetback = metricCircuit ? 48.0f : 130.0f;
            const int setbackRange = metricCircuit ? 130 : 145;
            prop.side = sideSign * (tp.width * 0.5f + baseSetback + static_cast<float>((i * 17) % setbackRange));
            prop.scale = metricCircuit ? 1.05f + static_cast<float>((i * 11) % 10) * 0.11f
                             : 0.75f + static_cast<float>((i * 11) % 9) * 0.09f;

            if (tp.zone == 0) {
                prop.type = (i % 9 == 0) ? Prop3D::Type::Boat
                                         : ((i % 5 == 0) ? Prop3D::Type::Hut : ((i % 3 == 0) ? Prop3D::Type::Sail : Prop3D::Type::Palm));
                prop.color = (i % 4 == 0) ? Color{235, 82, 62, 255} : Color{245, 191, 56, 255};
            } else if (tp.zone == 2) {
                prop.type = (i % 5 == 0) ? Prop3D::Type::Market : ((i % 7 == 0) ? Prop3D::Type::Crane : Prop3D::Type::Hut);
                prop.color = (i % 3 == 0) ? Color{238, 69, 91, 255} : Color{48, 167, 157, 255};
            } else {
                prop.type = (i % 6 == 0) ? Prop3D::Type::Cliff : ((i % 4 == 0) ? Prop3D::Type::Rock : Prop3D::Type::Palm);
                prop.color = (i % 6 == 0) ? Color{93, 116, 82, 255} : Color{45, 145, 76, 255};
            }
            if (prop.type == Prop3D::Type::Chevron) {
                const float outside = std::abs(tp.signedCurvature) > 0.015f ? -std::copysign(1.0f, tp.signedCurvature) : sideSign;
                prop.side = outside * (tp.width * 0.5f + 112.0f);
                prop.scale *= 1.30f;
            } else if (prop.type == Prop3D::Type::Palm || prop.type == Prop3D::Type::Crane || prop.type == Prop3D::Type::Cliff ||
                       prop.type == Prop3D::Type::Crystal) {
                prop.side += sideSign * 72.0f;
            }
            props_.push_back(prop);
        }

        auto addLandmark = [&](float phase, float sideSign, float extra, float scale, Prop3D::Type type, Color color) {
            const float p = wrapDistance(totalLength_ * phase, totalLength_);
            const TrackPoint3D tp = sample(p);
            props_.push_back({type, p, sideSign * (tp.width * 0.5f + extra), scale, color});
        };
        addLandmark(0.105f, 1.0f, 92.0f, 1.70f, Prop3D::Type::Sail, Color{238, 62, 54, 255});
        addLandmark(0.205f, -1.0f, 160.0f, 2.15f, Prop3D::Type::Boat, Color{239, 191, 56, 255});
        addLandmark(0.325f, 1.0f, 142.0f, 2.20f, Prop3D::Type::Market, Color{239, 70, 91, 255});
        addLandmark(0.455f, -1.0f, 136.0f, 2.00f, Prop3D::Type::Crane, Color{236, 92, 51, 255});
        addLandmark(0.610f, 1.0f, 145.0f, 2.25f, Prop3D::Type::Hut, Color{52, 151, 90, 255});
        addLandmark(0.765f, -1.0f, 138.0f, 2.45f, Prop3D::Type::Cliff, Color{92, 117, 83, 255});
        addLandmark(0.900f, 1.0f, 142.0f, 2.10f, Prop3D::Type::Palm, Color{47, 157, 84, 255});

        if (metricCircuit) {
            struct ScenicCluster {
                float phase;
                Prop3D::Type anchor;
                Color color;
            };
            static constexpr std::array<ScenicCluster, 14> kClusters = {{
                {0.015f, Prop3D::Type::Market, Color{238, 76, 84, 255}},
                {0.085f, Prop3D::Type::Hut, Color{242, 180, 65, 255}},
                {0.155f, Prop3D::Type::Cliff, Color{94, 126, 82, 255}},
                {0.225f, Prop3D::Type::Palm, Color{49, 151, 78, 255}},
                {0.300f, Prop3D::Type::Crane, Color{232, 104, 62, 255}},
                {0.375f, Prop3D::Type::Market, Color{49, 164, 150, 255}},
                {0.450f, Prop3D::Type::Hut, Color{242, 180, 65, 255}},
                {0.525f, Prop3D::Type::Market, Color{49, 164, 150, 255}},
                {0.600f, Prop3D::Type::Cliff, Color{100, 119, 79, 255}},
                {0.675f, Prop3D::Type::Hut, Color{224, 94, 67, 255}},
                {0.750f, Prop3D::Type::Palm, Color{49, 151, 78, 255}},
                {0.825f, Prop3D::Type::Cliff, Color{100, 119, 79, 255}},
                {0.900f, Prop3D::Type::Boat, Color{240, 190, 61, 255}},
                {0.965f, Prop3D::Type::Market, Color{238, 76, 84, 255}},
            }};
            for (size_t clusterIndex = 0; clusterIndex < kClusters.size(); ++clusterIndex) {
                const ScenicCluster& cluster = kClusters[clusterIndex];
                for (int item = 0; item < 5; ++item) {
                    const float offset = (static_cast<float>(item) - 2.0f) * 0.0023f;
                    const float side = ((item + static_cast<int>(clusterIndex)) % 2 == 0) ? -1.0f : 1.0f;
                    Prop3D::Type type = item == 0 ? cluster.anchor
                                                 : (item == 1 ? Prop3D::Type::Palm
                                                              : (item == 2 ? Prop3D::Type::Hut
                                                                           : (item == 3 ? Prop3D::Type::Rock
                                                                                        : Prop3D::Type::Torch)));
                    const float extra = 52.0f + static_cast<float>((item * 37 + clusterIndex * 19) % 82);
                    addLandmark(cluster.phase + offset, side, extra, 1.40f + item * 0.28f, type,
                                item % 2 == 0 ? cluster.color : shade(cluster.color, 1.10f));
                }
            }
        }
    }

    std::vector<TrackPoint3D> samples_;
    std::vector<Prop3D> props_;
    float totalLength_ = 1.0f;
    TrackLayoutId layout_ = TrackLayoutId::Spa;
};

bool runTrackCatalogAudit() {
    bool allOk = true;
    for (const TrackCatalogEntry& catalogEntry : trackCatalog()) {
        const TrackCatalogEntry* catalog = &catalogEntry;
        Track3D track(catalog->id);
        float planarMeters = 0.0f;
        float minElevation = std::numeric_limits<float>::max();
        float maxElevation = std::numeric_limits<float>::lowest();
        float minWidth = std::numeric_limits<float>::max();
        float maxWidth = 0.0f;
        bool finite = true;
        for (int i = 0; i < track.sampleCount(); ++i) {
            const TrackPoint3D& a = track.pointAtIndex(i);
            const TrackPoint3D& b = track.pointAtIndex(i + 1);
            planarMeters += length(b.pos - a.pos) / kTrackSimulationUnitsPerMeter;
            const float elevation = a.elevation / kTrackSimulationUnitsPerMeter;
            const float width = a.width * kRoadSurfaceRatio * 2.0f / kTrackSimulationUnitsPerMeter;
            minElevation = std::min(minElevation, elevation);
            maxElevation = std::max(maxElevation, elevation);
            minWidth = std::min(minWidth, width);
            maxWidth = std::max(maxWidth, width);
            finite = finite && std::isfinite(a.pos.x) && std::isfinite(a.pos.y) &&
                     std::isfinite(a.elevation) && std::isfinite(a.width) &&
                     std::abs(length(a.tangent) - 1.0f) < 0.01f;
        }
        const float relief = maxElevation - minElevation;
        const TrackShapeAuditResult shape = auditTrackCatalogShape(*catalog);
        std::size_t runtimeLandmarkFailures = 0;
        constexpr float kTurnWindow = 0.018f;
        for (const TrackTurnExpectation& expected : trackTurnExpectations(catalog->id)) {
            const TrackPoint3D before = track.sample(
                (expected.lapFraction - kTurnWindow) * track.totalLength());
            const TrackPoint3D center = track.sample(expected.lapFraction * track.totalLength());
            const TrackPoint3D after = track.sample(
                (expected.lapFraction + kTurnWindow) * track.totalLength());
            const Vec2 first = center.pos - before.pos;
            const Vec2 second = after.pos - center.pos;
            const float simulationTurn = std::atan2(cross(first, second), dot(first, second));
            // Mapping simulation (x, y) directly to world (x, z) reverses
            // orientation around world-up, so the driver-visible sign is the
            // negative of the simulation XY cross product.
            const float visibleTurn = -simulationTurn;
            const float expectedSign = static_cast<float>(static_cast<int>(expected.direction));
            runtimeLandmarkFailures += visibleTurn * expectedSign < 0.08f ? 1u : 0u;
        }
        const bool ok = finite && std::abs(track.totalLength() - catalog->targetLengthMeters) < 0.01f &&
                        std::abs(planarMeters - catalog->targetLengthMeters) < 2.0f &&
                        std::abs(relief - catalog->nominalElevationReliefMeters) < 0.10f &&
                        minWidth >= 9.0f && maxWidth <= 26.0f && shape.ok() &&
                        runtimeLandmarkFailures == 0;
        std::cout << "track-catalog-audit name=" << catalog->displayName
                  << " target_m=" << catalog->targetLengthMeters
                  << " planar_m=" << planarMeters
                  << " turns=" << catalog->turnCount
                  << " relief_m=" << relief
                  << " width_m=" << minWidth << "," << maxWidth
                  << " clockwise=" << catalog->clockwise
                  << " aspect=" << shape.aspectRatio
                  << " intersections=" << shape.selfIntersections
                  << " landmark_failures=" << shape.landmarkFailures << "/" << shape.landmarkChecks
                  << " visible_landmark_failures=" << runtimeLandmarkFailures << "/" << shape.landmarkChecks
                  << " finite=" << finite
                  << " ok=" << ok << "\n";
        allOk = allOk && ok;
    }
    return allOk;
}

bool runSpaGeometryAudit() {
    const TrackCatalogEntry* spaCatalog = findTrackCatalogEntry(TrackLayoutId::Spa);
    if (spaCatalog == nullptr) {
        std::cout << "spa-audit missing_catalog=1 ok=0\n";
        return false;
    }
    Track3D track(TrackLayoutId::Spa);
    float planarLength = 0.0f;
    float surfaceLength = 0.0f;
    float maxGrade = 0.0f;
    for (int i = 0; i < track.sampleCount(); ++i) {
        const TrackPoint3D& a = track.pointAtIndex(i);
        const TrackPoint3D& b = track.pointAtIndex(i + 1);
        const float planar = length(b.pos - a.pos);
        const float rise = b.elevation - a.elevation;
        planarLength += planar;
        surfaceLength += std::sqrt(planar * planar + rise * rise);
        maxGrade = std::max(maxGrade, std::abs(a.grade));
    }

    float stationError = 0.0f;
    float minElevation = std::numeric_limits<float>::max();
    float maxElevation = std::numeric_limits<float>::lowest();
    for (const TrackElevationPoint& station : spaCatalog->elevationProfile) {
        const float sampled = track.sample(station.distanceMeters).elevation / kTrackSimulationUnitsPerMeter;
        stationError = std::max(stationError, std::abs(sampled - station.elevationMeters));
        minElevation = std::min(minElevation, sampled);
        maxElevation = std::max(maxElevation, sampled);
    }
    std::vector<formula_forge::TrackClearanceSample> clearanceSamples;
    clearanceSamples.reserve(track.samples().size());
    for (const TrackPoint3D& point : track.samples()) {
        const float physicalRoadHalfWidth = point.width * kRoadSurfaceRatio;
        clearanceSamples.push_back({point.pos.x, point.pos.y, point.elevation, point.progress,
                                    physicalRoadHalfWidth, physicalRoadHalfWidth});
    }
    formula_forge::TrackClearanceAuditSettings clearanceSettings;
    clearanceSettings.totalLength = track.totalLength();
    clearanceSettings.widestKartWidth = 41.0f;
    clearanceSettings.roadLaneInset = kRoadLaneInset;
    clearanceSettings.twoKartPassingMargin = 0.5f * kTrackSimulationUnitsPerMeter;
    clearanceSettings.localArcExclusion = 600.0f;
    clearanceSettings.verticalOverlapTolerance = 7.0f * kTrackSimulationUnitsPerMeter;
    clearanceSettings.minimumSegmentLength = 0.1f;
    clearanceSettings.overlapTolerance = 0.05f * kTrackSimulationUnitsPerMeter;
    clearanceSettings.widthParityTolerance = 0.01f;
    const formula_forge::TrackClearanceAuditResult clearance =
        formula_forge::AuditTrackClearance(clearanceSamples, clearanceSettings);

    planarLength /= kTrackSimulationUnitsPerMeter;
    surfaceLength /= kTrackSimulationUnitsPerMeter;
    const float lengthError = std::abs(track.totalLength() - spaCatalog->targetLengthMeters);
    const float relief = maxElevation - minElevation;
    const auto signedTurn = [&](float start, float end) {
        float total = 0.0f;
        for (float progress = start; progress <= end; progress += 10.0f) {
            total += track.sample(progress).signedCurvature;
        }
        return total;
    };
    const float laSourceTurn = signedTurn(250.0f, 650.0f);
    const std::array<float, 3> eauRougeTurns = {
        signedTurn(950.0f, 1050.0f), signedTurn(1050.0f, 1350.0f), signedTurn(1350.0f, 1550.0f)};
    float maxEauRougeCurvature = 0.0f;
    for (float progress = 900.0f; progress <= 1650.0f; progress += 5.0f) {
        maxEauRougeCurvature = std::max(maxEauRougeCurvature, track.sample(progress).curvature);
    }
    const bool ok = lengthError <= 0.01f &&
                    std::abs(relief - spaCatalog->nominalElevationReliefMeters) <= 0.03f &&
                    stationError <= 0.03f &&
                    std::abs(planarLength - spaCatalog->targetLengthMeters) <= 1.5f &&
                    std::isfinite(surfaceLength) && maxGrade <= 0.25f && clearance.ok() && laSourceTurn > 0.5f &&
                    eauRougeTurns[0] < -0.25f && eauRougeTurns[1] > 0.5f && eauRougeTurns[2] < -0.25f &&
                    maxEauRougeCurvature < 0.65f;
    std::cout << "spa-audit length_m=" << track.totalLength() << " planar_mesh_m=" << planarLength
              << " surface_mesh_m=" << surfaceLength << " relief_m=" << relief
              << " station_error_m=" << stationError << " max_grade=" << maxGrade
              << " road_width_m=" << clearance.minPhysicalRoadWidth / kTrackSimulationUnitsPerMeter << ".."
              << clearance.maxPhysicalRoadWidth / kTrackSimulationUnitsPerMeter
              << " passing_clearance_m=" << clearance.minTwoKartPassingClearance / kTrackSimulationUnitsPerMeter
              << " branch_clearance_m=" << clearance.minPhysicalNonLocalClearance / kTrackSimulationUnitsPerMeter
              << " overlap_pairs=" << clearance.physicalOverlapPairs
              << " rendered_width_margin_m=" << clearance.minRenderedPhysicalMargin / kTrackSimulationUnitsPerMeter
              << " la_source_turn=" << laSourceTurn
              << " eau_rouge_turns=" << eauRougeTurns[0] << "," << eauRougeTurns[1] << "," << eauRougeTurns[2]
              << " eau_max_curvature=" << maxEauRougeCurvature
              << " ok=" << ok << "\n";
    return ok;
}

struct KartSpec3D {
    std::string name;
    Color body;
    Color accent;
    Color glass;
    float maxSpeed = 145.0f;
    float accel = 128.0f;
    float brake = 205.0f;
    float grip = 1.0f;
    float drift = 1.0f;
    float width = 34.0f;
    float length = 48.0f;
    float height = 15.0f;
    int bodyStyle = 0;
};

constexpr float kRacePaceScale = 1.405f;

// Smoothed from the player's validated 24.475 second flying lap. These are
// targets for the physics controller, never positional overrides.
constexpr std::array<float, 128> kAttackingReferenceLane = {
    -69.80f, -72.30f, -67.95f, -62.84f, -54.19f, -30.94f, 7.59f,   24.76f,
    33.44f,  30.21f,  34.67f,  44.72f,  42.18f,  40.90f,  47.49f,  34.36f,
    20.02f,  19.12f,  32.83f,  51.50f,  66.44f,  76.45f,  79.93f,  71.48f,
    55.41f,  37.22f,  26.69f,  22.68f,  20.87f,  19.82f,  19.17f,  19.06f,
    19.63f,  21.25f,  25.28f,  31.15f,  33.76f,  32.31f,  28.40f,  26.14f,
    27.70f,  30.87f,  34.09f,  36.94f,  39.07f,  39.60f,  37.20f,  29.79f,
    17.05f,  2.04f,   -16.82f, -21.52f, 5.98f,   46.43f,  70.84f,  69.95f,
    26.61f,  -32.64f, -63.52f, -36.12f, -7.53f,  -3.09f,  -55.81f, -82.00f,
    -69.68f, -53.64f, -38.00f, -20.47f, -5.16f,  -4.41f,  0.34f,   9.90f,
    22.66f,  39.49f,  50.53f,  44.85f,  46.03f,  64.89f,  81.58f,  76.26f,
    51.25f,  -9.02f,  -65.56f, -79.64f, -64.23f, -42.02f, -23.27f, -6.28f,
    9.44f,   19.91f,  23.08f,  22.37f,  19.65f,  13.72f,  5.40f,   -3.25f,
    -8.65f,  -5.36f,  3.54f,   10.04f,  10.07f,  -2.90f,  -44.53f, -73.46f,
    -21.42f, 29.45f,  39.72f,  42.82f,  60.78f,  82.00f,  66.24f,  25.73f,
    -8.33f,  -20.18f, -20.88f, -12.08f, 13.48f,  38.95f,  51.98f,  59.16f,
    63.44f,  56.18f,  34.94f,  -3.60f,  -46.99f, -63.68f, -58.95f, -52.49f,
};

constexpr std::array<float, 128> kAttackingReferenceSpeed = {
    366.42f, 374.72f, 382.52f, 389.84f, 395.16f, 397.28f, 401.83f, 406.57f,
    399.81f, 382.22f, 377.16f, 381.78f, 388.06f, 391.73f, 391.34f, 394.53f,
    400.13f, 402.98f, 406.49f, 410.64f, 414.25f, 417.47f, 420.15f, 422.72f,
    424.96f, 427.07f, 429.08f, 430.81f, 432.30f, 433.67f, 434.92f, 436.11f,
    437.16f, 438.12f, 439.00f, 439.78f, 440.49f, 441.19f, 441.84f, 442.43f,
    443.01f, 443.52f, 443.97f, 444.40f, 442.69f, 431.59f, 420.62f, 410.33f,
    399.77f, 397.16f, 402.31f, 407.02f, 411.21f, 415.46f, 418.16f, 419.64f,
    420.83f, 423.05f, 423.84f, 418.59f, 360.86f, 352.99f, 326.83f, 262.11f,
    296.58f, 325.46f, 344.39f, 359.64f, 371.66f, 381.29f, 388.83f, 323.12f,
    322.61f, 312.25f, 297.30f, 294.84f, 306.35f, 318.35f, 335.99f, 343.47f,
    355.98f, 367.30f, 380.57f, 385.52f, 387.62f, 394.31f, 400.35f, 405.35f,
    409.74f, 413.70f, 417.05f, 419.97f, 422.58f, 424.86f, 426.99f, 428.83f,
    430.58f, 432.09f, 433.47f, 434.75f, 436.03f, 437.29f, 438.58f, 314.40f,
    270.86f, 245.29f, 249.59f, 242.19f, 258.28f, 198.38f, 198.85f, 201.80f,
    259.01f, 299.39f, 325.29f, 344.43f, 360.15f, 372.51f, 380.60f, 387.55f,
    383.49f, 378.37f, 375.32f, 373.50f, 321.46f, 313.73f, 328.13f, 346.54f,
};

template <size_t N>
float sampleWrappedProfile(const std::array<float, N>& profile, float phase) {
    const float coordinate = wrapDistance(phase, 1.0f) * static_cast<float>(N);
    const size_t first = static_cast<size_t>(coordinate) % N;
    const size_t second = (first + 1) % N;
    return lerp(profile[first], profile[second], coordinate - std::floor(coordinate));
}

ArcadeVehicleConfig tuningForSpec(const KartSpec3D& spec) {
    ArcadeVehicleConfig tuning;
    constexpr float kAccelerationScale = kRacePaceScale * kRacePaceScale;
    tuning.maxForwardSpeed = spec.maxSpeed * 1.64f * kRacePaceScale;
    tuning.engineAcceleration = spec.accel * 0.72f * kAccelerationScale;
    tuning.launchAccelerationBonus = spec.accel * 0.27f * kAccelerationScale;
    tuning.brakeDeceleration = spec.brake * 1.82f * kAccelerationScale;
    tuning.reverseAcceleration *= kAccelerationScale;
    tuning.wheelbase = spec.length * 0.65f;
    tuning.wheelRadius = std::max(6.0f, spec.height * 0.52f);
    tuning.lateralGripAcceleration *= spec.grip * 1.10f * kAccelerationScale;
    tuning.driftGripAcceleration *= spec.grip * 0.96f * kAccelerationScale;
    tuning.maxSteerLowSpeed = 0.42f;
    tuning.maxSteerHighSpeed = 0.10f;
    tuning.maxYawRateLowSpeed = 2.20f;
    tuning.maxYawRateHighSpeed = 0.82f;
    tuning.steerResponse *= kRacePaceScale;
    tuning.steerReturnResponse *= kRacePaceScale;
    tuning.yawResponseGrip *= kRacePaceScale;
    tuning.yawResponseExit *= kRacePaceScale;
    tuning.lateralGripResponse *= kRacePaceScale;
    tuning.brakeLoadResponse *= kRacePaceScale;
    tuning.brakeReleaseResponse *= kRacePaceScale;
    tuning.brakeOversteerSteerThreshold = 0.16f;
    tuning.brakeOversteerYawGain = 0.28f;
    tuning.brakeYawLimitScale = 1.04f;
    tuning.brakeOversteerSlip = 0.045f;
    tuning.brakeSlipResponse = 12.0f;
    tuning.brakeSlipRecovery = 20.0f;
    tuning.downforceGripGain = 0.62f;
    tuning.tireLimitedYawScale = 0.90f;
    tuning.accelerationGripUsageScale = 0.78f;
    tuning.driftMinEntrySpeed = tuning.maxForwardSpeed * 2.0f;
    tuning.driftMinSustainSpeed = tuning.maxForwardSpeed * 2.0f;
    tuning.boostAcceleration *= kAccelerationScale;
    tuning.gravity *= kAccelerationScale;
    tuning.landingImpulseDecay *= kRacePaceScale;
    tuning.maxBodyRoll *= 0.46f;
    tuning.maxBodyPitch *= 0.70f;
    tuning.maxBrakePitch *= 0.62f;
    return tuning;
}

std::array<KartSpec3D, 11> makeKartSpecs() {
    // All entries share one mechanical and collision specification. The
    // selection changes the authored appearance and livery only.
    return {{
        {"Mercedes", {11, 13, 14, 255}, {39, 244, 210, 255}, {39, 244, 210, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 0},
        {"Ferrari", {232, 0, 45, 255}, {244, 244, 242, 255}, {244, 244, 242, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 1},
        {"Mclaren", {255, 95, 0, 255}, {17, 18, 23, 255}, {17, 18, 23, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 2},
        {"Red Bull", {3, 9, 41, 255}, {230, 2, 5, 255}, {230, 2, 5, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 3},
        {"Racing Bulls", {244, 244, 242, 255}, {102, 146, 255, 255}, {102, 146, 255, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 4},
        {"Alpine", {0, 161, 232, 255}, {255, 135, 188, 255}, {255, 135, 188, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 5},
        {"Audi", {199, 203, 204, 255}, {255, 45, 0, 255}, {255, 45, 0, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 6},
        {"Haas", {222, 225, 226, 255}, {229, 27, 42, 255}, {229, 27, 42, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 7},
        {"Williams", {24, 104, 219, 255}, {244, 244, 242, 255}, {244, 244, 242, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 8},
        {"Aston Martin", {34, 153, 113, 255}, {206, 220, 0, 255}, {206, 220, 0, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 9},
        {"Cadillac", {35, 36, 40, 255}, {170, 170, 173, 255}, {170, 170, 173, 255}, 198.0f, 258.0f, 214.0f, 1.05f, 0.98f, 34.4f, 83.6f, 18.4f, 10},
    }};
}

std::array<std::string, kKartCount> makeRacers() {
    return {"Dark", "Max", "Charles", "Lewis", "Oscar", "George",
            "Lando", "Fernando", "Carlos", "Pierre", "Alex"};
}

std::uint8_t racerAssetVariant(std::string_view racer) {
    (void)racer;
    return 0u;
}

uint32_t stableHash(std::string_view text) {
    uint32_t hash = 2166136261u;
    for (char ch : text) {
        hash ^= static_cast<uint8_t>(ch);
        hash *= 16777619u;
    }
    return hash;
}

Color racerColor(std::string_view racer) {
    static constexpr std::array<Color, 10> palette = {
        Color{255, 211, 80, 255}, Color{238, 78, 91, 255},  Color{71, 185, 131, 255}, Color{76, 151, 224, 255},
        Color{245, 132, 58, 255}, Color{179, 112, 219, 255}, Color{242, 233, 201, 255}, Color{39, 51, 63, 255},
        Color{86, 214, 222, 255}, Color{245, 164, 196, 255},
    };
    const uint32_t hash = stableHash(racer);
    return palette[hash % palette.size()];
}

struct Input3D {
    float steer = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
    bool drift = false;
    bool a = false;
    bool b = false;
    bool bHeld = false;
    bool start = false;
    bool back = false;
    bool left = false;
    bool right = false;
    bool up = false;
    bool down = false;
    bool pageLeft = false;
    bool pageRight = false;
    bool triggerLeft = false;
    bool triggerRight = false;
    bool shiftDown = false;
    bool shiftUp = false;
    bool automaticShift = false;
    bool quit = false;
};

float axisWithDeadzone(float value) {
    value = std::clamp(value, -1.0f, 1.0f);
    const float dead = 0.14f;
    if (std::abs(value) < dead) {
        return 0.0f;
    }
    const float sign = value < 0.0f ? -1.0f : 1.0f;
    const float normalized = (std::abs(value) - dead) / (1.0f - dead);
    const float curved = 0.25f * normalized + 0.75f * normalized * normalized * normalized;
    return sign * curved;
}

bool isWiredWheel(Uint16 vendor, Uint16 product) {
    // DragonRise Wired Wheel. The Linux xpad driver deliberately exposes this
    // device as a standard Xbox pad, so the VID/PID is the reliable way to
    // preserve wheel-specific steering response.
    return vendor == 0x0079 && product == 0x189c;
}

float wheelAxisWithDeadzone(float value) {
    value = std::clamp(value, -1.0f, 1.0f);
    constexpr float dead = 0.025f;
    if (std::abs(value) <= dead) {
        return 0.0f;
    }
    const float sign = value < 0.0f ? -1.0f : 1.0f;
    return sign * (std::abs(value) - dead) / (1.0f - dead);
}

float signedPedalUnit(float value) {
    const float normalized = std::clamp((value + 1.0f) * 0.5f, 0.0f, 1.0f);
    return normalized < 0.025f ? 0.0f : (normalized - 0.025f) / 0.975f;
}

float normalizedSdlAxis(Sint16 value) {
    return std::clamp(static_cast<float>(value) / 32767.0f, -1.0f, 1.0f);
}

float normalizeRaylibTrigger(float raw, bool& signedRange) {
    raw = std::clamp(raw, -1.0f, 1.0f);
    if (raw < -0.50f) {
        signedRange = true;
    }
    const float normalized = signedRange ? std::clamp((raw + 1.0f) * 0.5f, 0.0f, 1.0f) : std::clamp(raw, 0.0f, 1.0f);
    return normalized < 0.035f ? 0.0f : (normalized - 0.035f) / 0.965f;
}

float triggerValue(int gamepad, int axis, bool& signedRange) {
    return normalizeRaylibTrigger(GetGamepadAxisMovement(gamepad, axis), signedRange);
}

float canonicalBrake(float leftTrigger, bool bHeld) {
    return bHeld ? 1.0f : std::clamp(leftTrigger, 0.0f, 1.0f);
}

Input3D canonicalPlayerInput(Input3D input) {
    input.brake = canonicalBrake(input.brake, input.bHeld);
    return input;
}

bool controllerContractAudit() {
    bool zeroBased = false;
    const float zeroReleased = normalizeRaylibTrigger(0.0f, zeroBased);
    const float zeroPressed = normalizeRaylibTrigger(1.0f, zeroBased);
    bool signedRange = false;
    const float signedReleased = normalizeRaylibTrigger(-1.0f, signedRange);
    const float signedHalf = normalizeRaylibTrigger(0.0f, signedRange);
    const float signedPressed = normalizeRaylibTrigger(1.0f, signedRange);
    std::array<Input3D, 5> bSequence{};
    bSequence[1].bHeld = true;
    bSequence[2].bHeld = true;
    const std::array<float, 5> expectedBrake = {0.0f, 1.0f, 1.0f, 0.0f, 0.0f};
    bool bReleaseClears = true;
    for (size_t i = 0; i < bSequence.size(); ++i) {
        bReleaseClears = bReleaseClears && canonicalPlayerInput(bSequence[i]).brake == expectedBrake[i];
    }
    const bool steeringCurve = axisWithDeadzone(0.10f) == 0.0f && axisWithDeadzone(0.18f) < 0.015f &&
                               axisWithDeadzone(0.30f) > 0.045f && axisWithDeadzone(0.30f) < 0.060f &&
                               axisWithDeadzone(0.60f) > 0.23f && axisWithDeadzone(0.60f) < 0.27f &&
                               axisWithDeadzone(0.90f) > 0.70f && axisWithDeadzone(1.0f) == 1.0f &&
                               std::abs(axisWithDeadzone(-0.60f) + axisWithDeadzone(0.60f)) < 0.0001f;
    const bool wheelProfile = isWiredWheel(0x0079, 0x189c) && !isWiredWheel(0x045e, 0x028e) &&
                              wheelAxisWithDeadzone(0.02f) == 0.0f && wheelAxisWithDeadzone(1.0f) == 1.0f &&
                              wheelAxisWithDeadzone(-1.0f) == -1.0f && wheelAxisWithDeadzone(0.50f) > 0.48f &&
                              wheelAxisWithDeadzone(0.50f) < 0.50f && signedPedalUnit(-1.0f) == 0.0f &&
                              signedPedalUnit(1.0f) == 1.0f && signedPedalUnit(0.0f) > 0.48f &&
                              signedPedalUnit(0.0f) < 0.50f &&
                              wheelAxisWithDeadzone(normalizedSdlAxis(2048)) > 0.035f;
    return steeringCurve && wheelProfile && canonicalBrake(0.0f, false) == 0.0f &&
           std::abs(canonicalBrake(0.20f, false) - 0.20f) < 0.0001f &&
           std::abs(canonicalBrake(0.55f, false) - 0.55f) < 0.0001f && canonicalBrake(1.0f, false) == 1.0f &&
           canonicalBrake(0.0f, true) == 1.0f && canonicalBrake(1.0f, true) == 1.0f && bReleaseClears &&
           zeroReleased == 0.0f && zeroPressed == 1.0f && signedReleased == 0.0f && signedHalf > 0.45f &&
           signedHalf < 0.55f && signedPressed == 1.0f;
}

float sdlAxisUnit(Sint16 value) {
    const float f = normalizedSdlAxis(value);
    return std::abs(f) < 0.08f ? 0.0f : std::clamp(f, -1.0f, 1.0f);
}

float sdlTriggerUnit(Sint16 value) {
    if (value <= 0) {
        return 0.0f;
    }
    return std::clamp(static_cast<float>(value) / 32767.0f, 0.0f, 1.0f);
}

float rawJoystickAxis(SDL_Joystick* joystick, int axis) {
    if (!joystick || axis < 0 || axis >= SDL_GetNumJoystickAxes(joystick)) {
        return 0.0f;
    }
    return sdlAxisUnit(SDL_GetJoystickAxis(joystick, axis));
}

bool rawJoystickButton(SDL_Joystick* joystick, int button) {
    return joystick && button >= 0 && button < SDL_GetNumJoystickButtons(joystick) && SDL_GetJoystickButton(joystick, button);
}

class ControllerReader {
public:
    explicit ControllerReader(bool sdlFallbackReady) : sdlFallbackReady_(sdlFallbackReady) {}

    ~ControllerReader() {
        close();
    }

    void shutdown() { close(); }

    bool available() {
        if (IsGamepadAvailable(0)) {
            return true;
        }
        refresh();
        return !pads_.empty() || !joysticks_.empty();
    }

    Input3D read() {
        updateSdlState();
        refresh();
        Input3D input;
        if (!pads_.empty() || !joysticks_.empty()) {
            mergeSdl(input);
        } else if (IsGamepadAvailable(0)) {
            input = readRaylib();
        }
        // Preserve physical trigger presses as menu edges before brake
        // canonicalization folds the controller's B button into braking.
        input.triggerLeft = input.brake > 0.55f;
        input.triggerRight = input.throttle > 0.55f;
        input.brake = canonicalBrake(input.brake, input.bHeld);
        input.automaticShift = false;
        return edgeFiltered(input);
    }

    void printSnapshot() {
        refresh();
        if (IsGamepadAvailable(0)) {
            std::cout << "raylib controller: " << GetGamepadName(0) << " steer=" << GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_X)
                      << " lt=" << triggerValue(0, GAMEPAD_AXIS_LEFT_TRIGGER, raylibLeftTriggerSigned_)
                      << " rt=" << triggerValue(0, GAMEPAD_AXIS_RIGHT_TRIGGER, raylibRightTriggerSigned_)
                      << " rb=" << IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_TRIGGER_1)
                      << " a=" << IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_FACE_DOWN) << "\n";
        }
        for (SDL_Gamepad* pad : pads_) {
            const bool wheel = isWiredWheel(SDL_GetGamepadVendor(pad), SDL_GetGamepadProduct(pad));
            std::cout << "sdl " << (wheel ? "wheel" : "gamepad") << ": " << SDL_GetGamepadName(pad)
                      << " vid_pid=" << std::hex << SDL_GetGamepadVendor(pad) << ":" << SDL_GetGamepadProduct(pad)
                      << std::dec << " steer=" << sdlAxisUnit(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFTX))
                      << " lt=" << sdlTriggerUnit(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFT_TRIGGER))
                      << " rt=" << sdlTriggerUnit(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER))
                      << " rb=" << SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER)
                      << " a=" << SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_SOUTH) << "\n";
        }
        for (SDL_Joystick* joystick : joysticks_) {
            const bool wheel = isWiredWheel(SDL_GetJoystickVendor(joystick), SDL_GetJoystickProduct(joystick));
            std::cout << "sdl " << (wheel ? "wheel" : "joystick") << ": " << SDL_GetJoystickName(joystick)
                      << " vid_pid=" << std::hex << SDL_GetJoystickVendor(joystick) << ":" << SDL_GetJoystickProduct(joystick)
                      << std::dec << " axes=" << SDL_GetNumJoystickAxes(joystick)
                      << " buttons=" << SDL_GetNumJoystickButtons(joystick) << " steer=" << rawJoystickAxis(joystick, 0)
                      << " lt=" << rawJoystickAxis(joystick, 2) << " rt=" << rawJoystickAxis(joystick, 5)
                      << " rb=" << rawJoystickButton(joystick, 5) << " a=" << rawJoystickButton(joystick, 0) << "\n";
        }
        if (!IsGamepadAvailable(0) && pads_.empty() && joysticks_.empty()) {
            std::cout << "controller: none\n";
        }
    }

private:
    Input3D readRaylib() {
        Input3D input;
        if (IsGamepadAvailable(0)) {
            input.steer = axisWithDeadzone(GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_X));
            input.throttle = triggerValue(0, GAMEPAD_AXIS_RIGHT_TRIGGER, raylibRightTriggerSigned_);
            input.brake = triggerValue(0, GAMEPAD_AXIS_LEFT_TRIGGER, raylibLeftTriggerSigned_);
            input.a = IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_FACE_DOWN);
            input.bHeld = IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_FACE_RIGHT);
            input.start = IsGamepadButtonDown(0, GAMEPAD_BUTTON_MIDDLE_RIGHT);
            input.back = IsGamepadButtonDown(0, GAMEPAD_BUTTON_MIDDLE_LEFT);
            input.left = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_LEFT) || input.steer < -kMenuSteerThreshold;
            input.right = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_RIGHT) || input.steer > kMenuSteerThreshold;
            input.up = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_UP);
            input.down = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_DOWN);
            const float dpadSteer = (IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_RIGHT) ? 1.0f : 0.0f) -
                                    (IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_FACE_LEFT) ? 1.0f : 0.0f);
            if (std::abs(dpadSteer) > std::abs(input.steer)) {
                input.steer = dpadSteer;
            }
            input.pageLeft = IsGamepadButtonDown(0, GAMEPAD_BUTTON_LEFT_TRIGGER_1);
            input.pageRight = IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_TRIGGER_1);
            input.shiftDown = input.pageLeft;
            input.shiftUp = input.pageRight;
        } else {
            raylibLeftTriggerSigned_ = false;
            raylibRightTriggerSigned_ = false;
        }
        return input;
    }

    Input3D edgeFiltered(const Input3D& current) {
        const auto pressed = [](bool now, bool before) { return now && !before; };
        Input3D out = current;
        out.a = pressed(current.a, previousDigital_.a);
        out.b = current.b || pressed(current.bHeld, previousDigital_.bHeld);
        out.start = pressed(current.start, previousDigital_.start);
        out.back = pressed(current.back, previousDigital_.back);
        out.left = pressed(current.left, previousDigital_.left);
        out.right = pressed(current.right, previousDigital_.right);
        out.up = pressed(current.up, previousDigital_.up);
        out.down = pressed(current.down, previousDigital_.down);
        out.pageLeft = pressed(current.pageLeft, previousDigital_.pageLeft);
        out.pageRight = pressed(current.pageRight, previousDigital_.pageRight);
        out.triggerLeft = pressed(current.triggerLeft, previousDigital_.triggerLeft);
        out.triggerRight = pressed(current.triggerRight, previousDigital_.triggerRight);
        out.shiftDown = pressed(current.shiftDown, previousDigital_.shiftDown);
        out.shiftUp = pressed(current.shiftUp, previousDigital_.shiftUp);
        out.quit = current.quit || (current.start && current.back);
        previousDigital_ = current;
        return out;
    }

    void updateSdlState() {
        if (!sdlFallbackReady_) {
            return;
        }
        SDL_PumpEvents();
        SDL_UpdateGamepads();
        SDL_UpdateJoysticks();
    }

    void refresh() {
        if (!sdlFallbackReady_) {
            return;
        }

        std::erase_if(pads_, [](SDL_Gamepad* pad) {
            if (SDL_GamepadConnected(pad)) {
                return false;
            }
            SDL_CloseGamepad(pad);
            return true;
        });
        std::erase_if(joysticks_, [](SDL_Joystick* joystick) {
            if (SDL_JoystickConnected(joystick)) {
                return false;
            }
            SDL_CloseJoystick(joystick);
            return true;
        });

        int count = 0;
        SDL_JoystickID* pads = SDL_GetGamepads(&count);
        for (int i = 0; pads && i < count; ++i) {
            const SDL_JoystickID id = pads[i];
            const bool alreadyOpen = std::any_of(pads_.begin(), pads_.end(), [id](SDL_Gamepad* pad) {
                return SDL_GetGamepadID(pad) == id;
            });
            if (!alreadyOpen) {
                if (SDL_Gamepad* pad = SDL_OpenGamepad(id)) {
                    pads_.push_back(pad);
                }
            }
        }
        SDL_free(pads);

        SDL_JoystickID* joysticks = SDL_GetJoysticks(&count);
        for (int i = 0; joysticks && i < count; ++i) {
            const SDL_JoystickID id = joysticks[i];
            if (SDL_IsGamepad(id)) {
                continue;
            }
            const bool alreadyOpen = std::any_of(joysticks_.begin(), joysticks_.end(), [id](SDL_Joystick* joystick) {
                return SDL_GetJoystickID(joystick) == id;
            });
            if (!alreadyOpen) {
                if (SDL_Joystick* joystick = SDL_OpenJoystick(id)) {
                    joysticks_.push_back(joystick);
                }
            }
        }
        SDL_free(joysticks);
    }

    void close() {
        for (SDL_Gamepad* pad : pads_) {
            SDL_CloseGamepad(pad);
        }
        for (SDL_Joystick* joystick : joysticks_) {
            SDL_CloseJoystick(joystick);
        }
        pads_.clear();
        joysticks_.clear();
        previousDigital_ = {};
        raylibLeftTriggerSigned_ = false;
        raylibRightTriggerSigned_ = false;
    }

    void mergeSdl(Input3D& input) {
        const auto mergeSteering = [&input](float steer) {
            if (std::abs(steer) > std::abs(input.steer)) {
                input.steer = steer;
            }
        };
        for (SDL_Gamepad* pad : pads_) {
            const bool wheel = isWiredWheel(SDL_GetGamepadVendor(pad), SDL_GetGamepadProduct(pad));
            const float rawSteer = normalizedSdlAxis(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFTX));
            mergeSteering(wheel ? wheelAxisWithDeadzone(rawSteer) : axisWithDeadzone(rawSteer));
            input.throttle = std::max(input.throttle, sdlTriggerUnit(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)));
            input.brake = std::max(input.brake, sdlTriggerUnit(SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFT_TRIGGER)));
            input.a = input.a || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_SOUTH);
            input.bHeld = input.bHeld || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_EAST);
            input.start = input.start || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_START);
            input.back = input.back || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_BACK);
            input.left = input.left || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_LEFT);
            input.right = input.right || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_RIGHT);
            input.up = input.up || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_UP);
            input.down = input.down || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_DOWN);
            input.pageLeft = input.pageLeft || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_LEFT_SHOULDER);
            input.pageRight = input.pageRight || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER);
            input.shiftDown = input.shiftDown || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_LEFT_SHOULDER);
            input.shiftUp = input.shiftUp || SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER);
            const float dpadSteer = (SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_RIGHT) ? 1.0f : 0.0f) -
                                    (SDL_GetGamepadButton(pad, SDL_GAMEPAD_BUTTON_DPAD_LEFT) ? 1.0f : 0.0f);
            if (std::abs(dpadSteer) > std::abs(input.steer)) {
                input.steer = dpadSteer;
            }
        }
        for (SDL_Joystick* joystick : joysticks_) {
            const bool wheel = isWiredWheel(SDL_GetJoystickVendor(joystick), SDL_GetJoystickProduct(joystick));
            const float rawSteer = rawJoystickAxis(joystick, 0);
            mergeSteering(wheel ? wheelAxisWithDeadzone(rawSteer) : axisWithDeadzone(rawSteer));
            const float throttle = rawJoystickAxis(joystick, 5);
            const float brake = rawJoystickAxis(joystick, 2);
            input.throttle = std::max(input.throttle, wheel ? signedPedalUnit(throttle) : std::max(0.0f, throttle));
            input.brake = std::max(input.brake, wheel ? signedPedalUnit(brake) : std::max(0.0f, brake));
            input.a = input.a || rawJoystickButton(joystick, 0);
            input.back = input.back || rawJoystickButton(joystick, 6);
            input.start = input.start || rawJoystickButton(joystick, 7);
            input.pageLeft = input.pageLeft || rawJoystickButton(joystick, 4);
            input.pageRight = input.pageRight || rawJoystickButton(joystick, 5);
            input.shiftDown = input.shiftDown || rawJoystickButton(joystick, 4);
            input.shiftUp = input.shiftUp || rawJoystickButton(joystick, 5);
            input.bHeld = input.bHeld || rawJoystickButton(joystick, 1);
            input.left = input.left || rawJoystickButton(joystick, 11);
            input.right = input.right || rawJoystickButton(joystick, 12);
            input.up = input.up || rawJoystickButton(joystick, 13);
            input.down = input.down || rawJoystickButton(joystick, 14);
        }
        input.left = input.left || input.steer < -kMenuSteerThreshold;
        input.right = input.right || input.steer > kMenuSteerThreshold;
    }

    std::vector<SDL_Gamepad*> pads_;
    std::vector<SDL_Joystick*> joysticks_;
    Input3D previousDigital_{};
    bool sdlFallbackReady_ = false;
    bool raylibLeftTriggerSigned_ = false;
    bool raylibRightTriggerSigned_ = false;
};

Input3D readInput(ControllerReader& controller) {
    return controller.read();
}

enum class ContactCause3D { None, Barrier, Vehicle };
enum class AiRaceIntent3D { None, Pass, Defend };

struct AiPaceCornerZone {
    int apexSample = 0;
    int entryStartSample = 0;
    int exitEndSample = 0;
};

std::string_view contactCauseName(ContactCause3D cause) {
    switch (cause) {
        case ContactCause3D::Barrier: return "barrier";
        case ContactCause3D::Vehicle: return "vehicle";
        default: return "none";
    }
}

struct Kart3D : ArcadeVehicleState {
    KartSpec3D spec;
    ArcadeVehicleConfig tuning;
    ArcadeVehicleTelemetry telemetry;
    std::string racer;
    float progress = 0.0f;
    float previousProgress = 0.0f;
    int nearest = 0;
    int lap = 0;
    float lane = 0.0f;
    float aiTempo = 1.0f;
    float aiLineTarget = 0.0f;
    float aiGridLane = 0.0f;
    float aiLaunchThrottleScale = 1.0f;
    float aiLaunchDuration = 0.0f;
    float aiLaunchElapsed = 0.0f;
    float aiStuckTimer = 0.0f;
    int aiRecoveryResetCount = 0;
    float aiCommandSteer = 0.0f;
    float aiCommandLineTarget = 0.0f;
    float aiCommandLineProgress = 0.0f;
    float aiCommandTargetSpeed = 0.0f;
    float aiCommandThrottle = 0.0f;
    float aiCommandBrake = 0.0f;
    bool aiCommandDrsPlanActive = false;
    bool aiFullThrottleOptimal = false;
    float aiFlatCommitTimer = 0.0f;
    bool aiRoadRecoveryConstraint = false;
    bool aiCollisionBrakeConstraint = false;
    int aiCollisionTargetIndex = -1;
    bool aiProximityAvoidanceConstraint = false;
    int aiProximityAvoidanceTargetIndex = -1;
    float aiTrafficTimeToCollision = std::numeric_limits<float>::max();
    float aiTrafficRequiredDeceleration = 0.0f;
    AiRaceIntent3D aiRaceIntent = AiRaceIntent3D::None;
    float aiRaceLaneOffset = 0.0f;
    float aiRaceDesiredLaneOffset = 0.0f;
    float aiRaceCommitTimer = 0.0f;
    float aiRaceCooldownTimer = 0.0f;
    int aiRaceTargetIndex = -1;
    int aiRaceDefendedLap = -100;
    bool drsAvailable = false;
    bool drsActive = false;
    int drsLastDetectionLap = -1;
    float drsLastDetectionTime = -1.0f;
    float ghostTimer = 0.0f;
    Vec2 previousRenderPos{};
    float previousRenderElevation = 0.0f;
    float previousRenderHeading = 0.0f;
    float previousRenderProgress = 0.0f;
    float contactImpulse = 0.0f;
    ContactCause3D contactCause = ContactCause3D::None;
    bool barrierContact = false;
    bool vehicleContact = false;
};

struct Particle3D {
    Vec2 pos;
    Vec2 vel;
    float elevation = 0.0f;
    float life = 0.0f;
    float maxLife = 1.0f;
    float size = 1.0f;
    Color color = WHITE;
};

enum class AuditDriver { NoBrake, Brake, Attack };

struct AuditResult3D {
    const char* name = "";
    float score = 0.0f;
    float maxSpeed = 0.0f;
    float averageSpeed = 0.0f;
    float maxOffroad = 0.0f;
    float maxOffroadPhase = 0.0f;
    float maxDriftCharge = 0.0f;
    float maxSlip = 0.0f;
    float minGroundClearance = std::numeric_limits<float>::max();
    float maxAirTime = 0.0f;
    int progressJumps = 0;
    int contacts = 0;
    int offroadFrames = 0;
    int boostFrames = 0;
    int driftFrames = 0;
    int brakeDriftFrames = 0;
    int brakeFrames = 0;
    int poweredExitFrames = 0;
    int landings = 0;
    int lap = 0;
};

struct RaceAuditResult3D {
    float playerScore = 0.0f;
    float topAiScore = 0.0f;
    float tailAiScore = 0.0f;
    float spread = 0.0f;
    float maxOverlap = 0.0f;
    float maxRoadViolation = 0.0f;
    float minGroundClearance = std::numeric_limits<float>::max();
    float validatedLapSeconds = 0.0f;
    float contactBeginningsPerLap = 0.0f;
    int overtakes = 0;
    int contacts = 0;
    int progressJumps = 0;
    int overlapFrames = 0;
    int roadViolationFrames = 0;
    int playerBest = kKartCount;
    int playerWorst = 1;
    int playerFinal = kKartCount;
};

struct RacecraftAuditResult3D {
    int contactBeginnings = 0;
    int clearPhysicsFlatFrames = 0;
    int unnecessaryPhysicsFlatBrakeFrames = 0;
    int unnecessaryPhysicsFlatLiftFrames = 0;
    int canonicalLineFrames = 0;
    int offCanonicalLineTargetFrames = 0;
    int collisionConstraintFrames = 0;
    float minimumClearPhysicsFlatThrottle = 1.0f;
    float maximumLineTargetErrorMeters = 0.0f;
    float maxRoadViolationMeters = 0.0f;
};

struct AiPaceAuditResult3D {
    float launchLapSeconds = 0.0f;
    float lapSeconds = 0.0f;
    float distance = 0.0f;
    float finalPhase = 0.0f;
    float averageSpeed = 0.0f;
    float maxSpeed = 0.0f;
    float maxRoadViolation = 0.0f;
    float maxRoadViolationPhase = 0.0f;
    float maxRoadViolationSpeed = 0.0f;
    float maxRoadViolationCurvature = 0.0f;
    float maxRoadViolationLane = 0.0f;
    float maxRoadViolationPlannedLane = 0.0f;
    float maxRoadViolationHeadingError = 0.0f;
    float maxRoadViolationSteer = 0.0f;
    float maxRoadViolationTargetSpeed = 0.0f;
    float maxProgressStep = 0.0f;
    int roadViolationFrames = 0;
    int driftFrames = 0;
    int brakeDriftFrames = 0;
    int brakeFrames = 0;
    int poweredExitFrames = 0;
    int contactFrames = 0;
    int contacts = 0;
    int landings = 0;
    int progressJumps = 0;
    int physicallyFlatCorners = 0;
    int flatCornersTakenFlat = 0;
    std::array<float, 10> splitSeconds{};
};

struct MonzaOptimizationCandidate {
    AiTimeTrialProfile profile =
        aiTimeTrialProfile(TrackLayoutId::Monza);
    std::array<float, 24> laneOffsetsMeters =
        kMonzaOptimizedLineOffsetsMeters;
};

struct MonzaOptimizationReplay {
    float seconds = std::numeric_limits<float>::max();
    float maximumRoadViolationMeters = 0.0f;
    int barrierContacts = 0;
    int progressJumps = 0;
    bool completed = false;
};

struct CollisionAuditResult3D {
    const char* name = "";
    float maxOverlap = 0.0f;
    float strikerSpeedBeforeContact = 0.0f;
    float targetSpeedBeforeContact = 0.0f;
    float strikerSpeedAfterContact = 0.0f;
    float targetSpeedAfterContact = 0.0f;
    float maxContactImpulse = 0.0f;
    int overlapFrames = 0;
    int contactFrames = 0;
    bool vehicleTelemetry = false;
};

struct KartContact3D {
    bool touching = false;
    Vec2 normal{1.0f, 0.0f};
    float penetration = 0.0f;
};

float contactHalfLength(const Kart3D& kart) {
    return kart.spec.length * 0.50f;
}

float contactHalfWidth(const Kart3D& kart) {
    return kart.spec.width * 0.50f;
}

float roadSurfaceHalfWidth(const TrackPoint3D& point) {
    return point.width * kRoadSurfaceRatio;
}

float roadCenterLimit(const Kart3D& kart, const TrackPoint3D& point) {
    return std::max(0.0f, roadSurfaceHalfWidth(point) - contactHalfWidth(kart) - kRoadLaneInset);
}

float roadEdgeViolation(const Kart3D& kart, const TrackPoint3D& point) {
    const float lane = dot(kart.pos - point.pos, point.normal);
    return std::max(0.0f, std::abs(lane) - roadCenterLimit(kart, point));
}

struct MetricCircuitEnvelope3D {
    float asphaltOuter = 0.0f;
    float curbOuter = 0.0f;
    float runoffOuter = 0.0f;
    float barrierInnerFace = 0.0f;
    float barrierCenter = 0.0f;
};

enum class DrivingSurface3D : std::uint8_t {
    Road,
    Curb,
    AsphaltRunoff,
    Gravel,
    Grass,
};

struct DrivingSurfaceResponse3D {
    ArcadeSurface physics;
    DrivingSurface3D kind = DrivingSurface3D::Road;
    float offTrackCoverage = 0.0f;
};

MetricCircuitEnvelope3D metricCircuitEnvelope(const TrackPoint3D& point) {
    const float units = kTrackSimulationUnitsPerMeter;
    const float asphalt = roadSurfaceHalfWidth(point);
    const float barrierCenter = asphalt + kMetricBarrierOffsetMeters * units;
    return {asphalt,
            asphalt + kMetricCurbWidthMeters * units,
            asphalt + kMetricRunoffWidthMeters * units,
            barrierCenter - kMetricBarrierThicknessMeters * units * 0.5f,
            barrierCenter};
}

float activeRendererWheelGroundClearance(const Kart3D& kart) {
    const float wheelRadius = std::max(0.50f, kart.spec.height * kRenderScale * 0.46f);
    const float travel = std::max(wheelRadius * 0.30f, 0.18f);
    const float suspension = std::clamp(kart.suspensionCompression, 0.0f, 1.0f);
    const float pitchLoad = std::clamp(kart.bodyPitch * 2.8f, -0.22f, 0.22f);
    const float rollLoad = std::clamp(kart.bodyRoll * 2.2f, -0.22f, 0.22f);
    const std::array<float, 4> compression = {
        std::clamp(0.16f + suspension + pitchLoad + rollLoad, 0.0f, 1.0f),
        std::clamp(0.16f + suspension + pitchLoad - rollLoad, 0.0f, 1.0f),
        std::clamp(0.16f + suspension - pitchLoad + rollLoad, 0.0f, 1.0f),
        std::clamp(0.16f + suspension - pitchLoad - rollLoad, 0.0f, 1.0f),
    };
    float averageBottom = 0.0f;
    for (float value : compression) {
        averageBottom += (0.48f - value) * travel;
    }
    averageBottom /= static_cast<float>(compression.size());
    // The active renderer lowers the Formula car root by this average wheel-bottom
    // offset while grounded, leaving the tire contact plane on the track.
    const float rendererRootCorrection = -averageBottom;
    return rendererRootCorrection + averageBottom;
}

float kartMass(const Kart3D& kart) {
    const float footprint = kart.spec.width * kart.spec.length;
    return std::clamp(0.72f + footprint / 2100.0f + kart.spec.height / 75.0f, 1.15f, 2.15f);
}

float inverseKartMass(const Kart3D& kart) {
    return 1.0f / kartMass(kart);
}

float projectedKartExtent(const Kart3D& kart, Vec2 axis) {
    const Vec2 forward = fromAngle(kart.heading);
    const Vec2 right{-forward.y, forward.x};
    return std::abs(dot(axis, forward)) * contactHalfLength(kart) + std::abs(dot(axis, right)) * contactHalfWidth(kart);
}

KartContact3D kartContact(const Kart3D& a, const Kart3D& b) {
    const Vec2 af = fromAngle(a.heading);
    const Vec2 ar{-af.y, af.x};
    const Vec2 bf = fromAngle(b.heading);
    const Vec2 br{-bf.y, bf.x};
    const Vec2 delta = b.pos - a.pos;
    const std::array<Vec2, 4> axes = {af, ar, bf, br};

    KartContact3D contact;
    contact.touching = true;
    contact.penetration = std::numeric_limits<float>::max();

    for (Vec2 axis : axes) {
        axis = normalize(axis);
        const float projectedDistance = std::abs(dot(delta, axis));
        const float overlap = projectedKartExtent(a, axis) + projectedKartExtent(b, axis) - projectedDistance;
        if (overlap <= 0.0f) {
            return {};
        }
        if (overlap < contact.penetration) {
            contact.penetration = overlap;
            contact.normal = dot(delta, axis) < 0.0f ? axis * -1.0f : axis;
        }
    }

    if (lengthSq(delta) < 0.0001f) {
        contact.normal = af;
    }
    return contact;
}

void drawQuad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Color color) {
    DrawTriangle3D(a, b, c, color);
    DrawTriangle3D(a, c, d, color);
}

void gradientVertex(Vector3 v, Color color) {
    rlColor4ub(color.r, color.g, color.b, color.a);
    rlVertex3f(v.x, v.y, v.z);
}

void drawGradientQuad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Color ca, Color cb, Color cc, Color cd) {
    rlBegin(RL_TRIANGLES);
    gradientVertex(a, ca);
    gradientVertex(b, cb);
    gradientVertex(c, cc);
    gradientVertex(a, ca);
    gradientVertex(c, cc);
    gradientVertex(d, cd);
    rlEnd();
    rlColor4ub(255, 255, 255, 255);
}

void drawFlatOval(Vector3 pos, float radiusX, float radiusZ, float height, Color color, int segments = 48) {
    rlPushMatrix();
    rlTranslatef(pos.x, pos.y, pos.z);
    rlScalef(radiusX, 1.0f, radiusZ);
    DrawCylinder({0.0f, 0.0f, 0.0f}, 1.0f, 1.0f, height, segments, color);
    rlPopMatrix();
}

void drawGradientOval(Vector3 pos, float radiusX, float radiusZ, Color center, Color edge, int segments = 72) {
    rlBegin(RL_TRIANGLES);
    for (int i = 0; i < segments; ++i) {
        const float a0 = static_cast<float>(i) / static_cast<float>(segments) * kTwoPi;
        const float a1 = static_cast<float>(i + 1) / static_cast<float>(segments) * kTwoPi;
        gradientVertex(pos, center);
        gradientVertex({pos.x + std::cos(a0) * radiusX, pos.y, pos.z + std::sin(a0) * radiusZ}, edge);
        gradientVertex({pos.x + std::cos(a1) * radiusX, pos.y, pos.z + std::sin(a1) * radiusZ}, edge);
    }
    rlEnd();
    rlColor4ub(255, 255, 255, 255);
}

void drawLocalBox(Vector3 pos, Vector3 size, Color color) {
    DrawCubeV(pos, size, color);
}

void drawLocalEllipsoid(Vector3 pos, Vector3 radius, Color color) {
    rlPushMatrix();
    rlTranslatef(pos.x, pos.y, pos.z);
    rlScalef(radius.x, radius.y, radius.z);
    DrawSphere({0.0f, 0.0f, 0.0f}, 1.0f, color);
    rlPopMatrix();
}

void drawLocalTaperedBox(Vector3 pos, Vector3 size, float frontScale, float rearScale, Color color) {
    const float y0 = pos.y - size.y * 0.5f;
    const float y1 = pos.y + size.y * 0.5f;
    const float zf = pos.z + size.z * 0.5f;
    const float zr = pos.z - size.z * 0.5f;
    const float xf = size.x * 0.5f * frontScale;
    const float xr = size.x * 0.5f * rearScale;

    const Vector3 fbl{pos.x - xf, y0, zf};
    const Vector3 fbr{pos.x + xf, y0, zf};
    const Vector3 ftl{pos.x - xf, y1, zf};
    const Vector3 ftr{pos.x + xf, y1, zf};
    const Vector3 rbl{pos.x - xr, y0, zr};
    const Vector3 rbr{pos.x + xr, y0, zr};
    const Vector3 rtl{pos.x - xr, y1, zr};
    const Vector3 rtr{pos.x + xr, y1, zr};

    drawQuad(ftl, ftr, rtr, rtl, shade(color, 1.04f));
    drawQuad(fbl, rbl, rbr, fbr, shade(color, 0.70f));
    drawQuad(fbl, ftl, rtl, rbl, shade(color, 0.86f));
    drawQuad(fbr, rbr, rtr, ftr, shade(color, 0.78f));
    drawQuad(fbl, fbr, ftr, ftl, shade(color, 1.08f));
    drawQuad(rbl, rtl, rtr, rbr, shade(color, 0.82f));
}

void drawLocalWedge(Vector3 pos, Vector3 size, float frontTopScale, Color color) {
    const float x0 = pos.x - size.x * 0.5f;
    const float x1 = pos.x + size.x * 0.5f;
    const float y0 = pos.y - size.y * 0.5f;
    const float yRear = pos.y + size.y * 0.5f;
    const float yFront = y0 + size.y * std::clamp(frontTopScale, 0.10f, 1.0f);
    const float zf = pos.z + size.z * 0.5f;
    const float zr = pos.z - size.z * 0.5f;

    const Vector3 fbl{x0, y0, zf};
    const Vector3 fbr{x1, y0, zf};
    const Vector3 ftl{x0, yFront, zf};
    const Vector3 ftr{x1, yFront, zf};
    const Vector3 rbl{x0, y0, zr};
    const Vector3 rbr{x1, y0, zr};
    const Vector3 rtl{x0, yRear, zr};
    const Vector3 rtr{x1, yRear, zr};

    drawQuad(ftl, ftr, rtr, rtl, shade(color, 1.10f));
    drawQuad(fbl, rbl, rbr, fbr, shade(color, 0.70f));
    drawQuad(fbl, ftl, rtl, rbl, shade(color, 0.86f));
    drawQuad(fbr, rbr, rtr, ftr, shade(color, 0.78f));
    drawQuad(fbl, fbr, ftr, ftl, shade(color, 1.02f));
    drawQuad(rbl, rtl, rtr, rbr, shade(color, 0.92f));
}

void drawLocalWheel(float x, float z, float radius, float width, Color tire, Color hub, float spinDeg, float steerDeg, bool front) {
    rlPushMatrix();
    rlTranslatef(x, radius, z);
    if (front) {
        rlRotatef(steerDeg, 0.0f, 1.0f, 0.0f);
    }
    DrawCylinderEx({-width * 0.5f, 0.0f, 0.0f}, {width * 0.5f, 0.0f, 0.0f}, radius, radius, 20, tire);
    DrawCylinderEx({-width * 0.54f, 0.0f, 0.0f}, {width * 0.54f, 0.0f, 0.0f}, radius * 0.46f, radius * 0.46f, 12, hub);
    for (int i = 0; i < 8; ++i) {
        const float a = (spinDeg + static_cast<float>(i) * 45.0f) * DEG2RAD;
        const float cy = std::sin(a) * radius * 0.92f;
        const float cz = std::cos(a) * radius * 0.92f;
        rlPushMatrix();
        rlTranslatef(0.0f, cy, cz);
        rlRotatef(-spinDeg + static_cast<float>(i) * 12.0f, 1.0f, 0.0f, 0.0f);
        DrawCubeV({0.0f, 0.0f, 0.0f}, {width * 1.12f, radius * 0.11f, radius * 0.24f}, shade(tire, 1.22f));
        rlPopMatrix();
    }
    for (int i = 0; i < 5; ++i) {
        const float a = (spinDeg + static_cast<float>(i) * 72.0f) * DEG2RAD;
        DrawCylinderEx({-width * 0.58f, 0.0f, 0.0f}, {-width * 0.60f, std::sin(a) * radius * 0.38f, std::cos(a) * radius * 0.38f},
                       radius * 0.035f, radius * 0.035f, 6, shade(hub, 1.25f));
        DrawCylinderEx({width * 0.58f, 0.0f, 0.0f}, {width * 0.60f, std::sin(a) * radius * 0.38f, std::cos(a) * radius * 0.38f},
                       radius * 0.035f, radius * 0.035f, 6, shade(hub, 1.25f));
    }
    rlPopMatrix();
}

void drawSkyGradient() {
    const int w = GetScreenWidth();
    const int h = GetScreenHeight();
    constexpr int kBands = 36;
    for (int i = 0; i < kBands; ++i) {
        const float t = static_cast<float>(i) / static_cast<float>(kBands - 1);
        const int y0 = i * h / kBands;
        const int y1 = (i + 1) * h / kBands + 1;
        DrawRectangle(0, y0, w, y1 - y0, mix(Color{69, 189, 237, 255}, Color{177, 238, 244, 255}, t));
    }
}

float offroadReachForZone(int zone) {
    switch (zone) {
        case 1:
        case 5:
            return 154.0f;
        case 3:
            return 132.0f;
        case 4:
            return 224.0f;
        default:
            return 196.0f;
    }
}

float hardBoundaryLaneLimit(const Kart3D& kart, const TrackPoint3D& point) {
    if (point.metricCircuit) {
        const MetricCircuitEnvelope3D envelope = metricCircuitEnvelope(point);
        return std::max(0.0f, envelope.barrierInnerFace - projectedKartExtent(kart, point.normal));
    }
    const bool metricSpaWidth = point.width > 260.0f;
    const float shoulder = metricSpaWidth ? 0.75f * kTrackSimulationUnitsPerMeter
                                          : std::min(42.0f, offroadReachForZone(point.zone) * 0.22f);
    return roadCenterLimit(kart, point) + shoulder - kHardBoundaryInset * 0.20f;
}

Color naturalSurfaceColor(int zone) {
    return baseZoneMaterial(zone).natural;
}

Color surfaceColorAt(const TrackPoint3D& point, float lane) {
    const float half = point.width * 0.5f;
    const float roadHalf = roadSurfaceHalfWidth(point);
    const float absLane = std::abs(lane);
    const Color natural = point.natural;
    const float crown = smoothstep(absLane / std::max(roadHalf, 1.0f));
    const float shoulderT = smoothstep((absLane - roadHalf) / std::max(half - roadHalf, 1.0f));
    const float wildT = smoothstep((absLane - half) / std::max(offroadReachForZone(point.zone) * 0.94f, 1.0f));
    Color base = mix(shade(point.road, 0.92f), shade(point.road, 0.72f), crown * 0.62f);
    base = mix(base, point.shoulder, shoulderT * 0.92f);
    base = mix(base, natural, wildT * 0.96f);

    const float grain = 0.5f + 0.5f * std::sin(point.progress * 0.018f + lane * 0.047f + static_cast<float>(point.zone) * 1.7f);
    const float broad = 0.5f + 0.5f * std::sin(point.progress * 0.0041f - lane * 0.013f);
    return shade(base, 0.972f + grain * 0.026f + broad * 0.022f);
}

std::array<float, 17> surfaceCuts(const TrackPoint3D& point) {
    const float half = point.width * 0.5f;
    const float reach = offroadReachForZone(point.zone);
    return {-half - reach,
            -half - reach * 0.68f,
            -half - reach * 0.42f,
            -half - reach * 0.20f,
            -half - reach * 0.04f,
            -half * 0.82f,
            -half * 0.54f,
            -half * 0.26f,
            0.0f,
            half * 0.26f,
            half * 0.54f,
            half * 0.82f,
            half + reach * 0.04f,
            half + reach * 0.20f,
            half + reach * 0.42f,
            half + reach * 0.68f,
            half + reach};
}

Vector3 terrainSurfacePoint(const Track3D& track, const TrackPoint3D& point, float lane) {
    Vector3 result = track.roadPoint(point, lane);
    if (isMetricCircuit(track.layout())) {
        return result;
    }
    const float half = point.width * 0.5f;
    const float reach = offroadReachForZone(point.zone);
    const float blendStart = half + reach * 0.20f;
    const float blendEnd = half + reach;
    const float blend = smoothstep((std::abs(lane) - blendStart) / std::max(1.0f, blendEnd - blendStart));
    const float terrainEdgeElevation = kTerrainSurfaceY;
    result.y = lerp(result.y, terrainEdgeElevation, blend);
    return result;
}

class Game3D {
public:
    enum class Mode { Loading, Garage, Race, Pause, Results };

    explicit Game3D(bool enableAudio = true)
        : specs_(makeKartSpecs()),
          racers_(makeRacers()),
          raceRandom_(
              enableAudio
                  ? std::random_device{}()
                  : 0x4f524745u) {
        renderer_.initialize();
        if (enableAudio) {
            audio_.initialize();
        }
        buildParticleTexture();
        loadMenuTextures();
        buildTrackRenderer();
        resetRace();
    }

    ~Game3D() {
        shutdown();
    }

    void shutdown() {
        audio_.shutdown();
        if (IsWindowReady()) {
            trackRenderer_.unload();
            if (IsTextureValid(particleTexture_)) {
                UnloadTexture(particleTexture_);
                particleTexture_ = {};
            }
            if (IsTextureValid(loadingScreenTexture_)) {
                UnloadTexture(loadingScreenTexture_);
                loadingScreenTexture_ = {};
            }
            if (IsTextureValid(garageBackgroundTexture_)) {
                UnloadTexture(garageBackgroundTexture_);
                garageBackgroundTexture_ = {};
            }
            renderer_.shutdown();
        }
    }

    [[nodiscard]] arcade_render::AuthoredAssetAuditResult auditAuthoredAssets() const {
        return renderer_.auditAuthoredAssets();
    }

    void update(float dt, const Input3D& input, bool hasController) {
        presentationTime_ += dt;
        if (mode_ == Mode::Loading) {
            loadingTime_ += dt;
            updateAudio(dt, input, false);
            if (loadingTime_ >= kLoadingScreenSeconds || input.a || input.start) {
                mode_ = Mode::Garage;
                selectionStage_ = formula_forge::ui::SelectionStage::Mode;
            }
            return;
        }

        if (mode_ == Mode::Garage) {
            updateGarage(input, hasController);
            updateGarageCamera(dt);
            updateAudio(dt, input, false);
            return;
        }

        if (mode_ == Mode::Pause) {
            updatePause(input);
            updateAudio(dt, input, false);
            return;
        }
        if (mode_ == Mode::Results) {
            updateResults(input);
            updateAudio(dt, input, false);
            return;
        }
        if (input.start) {
            mode_ = Mode::Pause;
            pauseAction_ = formula_forge::ui::PauseAction::Resume;
            return;
        }

        if (raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Countdown) {
            const auto raceInputs = currentRaceInputs();
            raceFlow_->update(dt, raceInputs);
            raceTime_ = static_cast<float>(raceFlow_->raceTimeSeconds());
            if (raceFlow_->phase() == ArcadeRacePhase::Racing) {
                countdownGoTimer_ = 0.72f;
            }
            updateCamera(dt);
            updateAudio(dt, input, false);
            return;
        }
        countdownGoTimer_ = std::max(0.0f, countdownGoTimer_ - dt);
        if (input.back) {
            resetPlayerToTrack();
        }

        Input3D playerInput = raceFinished_ ? Input3D{} : input;
        updatePlayer(karts_[0], playerInput, dt);
        for (int i = 1; i < activeKartCount(); ++i) {
            updateAi(karts_[static_cast<size_t>(i)], dt, i);
        }
        if (!isTimeTrial() && kMonzaRacecraftExperiment &&
            track_.layout() == TrackLayoutId::Monza) {
            applyMonzaSlipstream(dt);
        }
        if (!isTimeTrial()) {
            solveKartContacts();
        }
        updateParticles(dt);
        if (raceFlow_) {
            const auto raceInputs = currentRaceInputs();
            raceFlow_->update(dt, raceInputs);
            raceTime_ = static_cast<float>(raceFlow_->raceTimeSeconds());
            updateDrsDetectionLine();
            for (const ArcadeRaceEvent& event : raceFlow_->events()) {
                if (event.racerIndex == 0 && event.type == ArcadeRaceEventType::LapCompleted) {
                    lastLapTime_ = std::max(0.0f, static_cast<float>(event.raceTimeSeconds) - lapStartTime_);
                    bestLapTime_ = hasBestLap_ ? std::min(bestLapTime_, lastLapTime_) : lastLapTime_;
                    hasBestLap_ = true;
                    lapStartTime_ = static_cast<float>(event.raceTimeSeconds);
                }
            }
            for (int i = 0; i < activeKartCount(); ++i) {
                karts_[static_cast<size_t>(i)].lap = static_cast<int>(raceFlow_->racer(static_cast<size_t>(i)).completedLaps);
            }
        }
        updateRaceOrder();
        updateFinishState();
        updateCamera(dt);
        updateAudio(dt, playerInput, !raceFinished_);
    }

    void render(float fps, bool hasController, const char* capturePath = nullptr, float interpolation = 1.0f) {
        BeginDrawing();
        if (mode_ == Mode::Loading) {
            ClearBackground(Color{3, 3, 7, 255});
            const bool hasLoadingArtwork = IsTextureValid(loadingScreenTexture_);
            if (hasLoadingArtwork) {
                // Match the artwork to the active render target. On high-DPI and
                // offscreen capture backends the framebuffer can differ from the
                // logical window size, which otherwise compresses the cars into
                // only part of the loading screen.
                const float screenWidth = static_cast<float>(std::max(1, GetRenderWidth()));
                const float screenHeight = static_cast<float>(std::max(1, GetRenderHeight()));
                const float screenAspect = screenWidth / screenHeight;
                const float textureWidth = static_cast<float>(loadingScreenTexture_.width);
                const float textureHeight = static_cast<float>(loadingScreenTexture_.height);
                const float textureAspect = textureWidth / textureHeight;
                Rectangle source{0.0f, 0.0f, textureWidth, textureHeight};
                if (screenAspect > textureAspect) {
                    source.height = textureWidth / screenAspect;
                    source.y = (textureHeight - source.height) * 0.5f;
                } else {
                    source.width = textureHeight * screenAspect;
                    source.x = (textureWidth - source.width) * 0.5f;
                }
                DrawTexturePro(loadingScreenTexture_, source,
                               {0.0f, 0.0f, screenWidth, screenHeight},
                               {0.0f, 0.0f}, 0.0f, WHITE);
            }
            formula_forge::ui::LoadingScreenViewModel loading;
            loading.progress = std::clamp(loadingTime_ / kLoadingScreenSeconds, 0.0f, 1.0f);
            loading.presentationTimeSeconds = presentationTime_;
            loading.statusText = loading.progress < 0.72f ? "BUILDING THE STARTING GRID" : "READY TO RACE";
            loading.cinematicBackground = hasLoadingArtwork;
            formula_forge::ui::DrawLoadingScreen(loading);
            if (capturePath) {
                rlDrawRenderBatchActive();
                TakeScreenshot(capturePath);
            }
            EndDrawing();
            return;
        }
        renderAlpha_ = std::clamp(interpolation, 0.0f, 1.0f);
        const Camera simulationCamera = camera_;
        if (mode_ == Mode::Race || mode_ == Mode::Pause || mode_ == Mode::Results) {
            camera_ = raceTcam(renderAlpha_);
        }
        const bool garageBackdrop = mode_ == Mode::Garage && IsTextureValid(garageBackgroundTexture_);
        ClearBackground(garageBackdrop ? Color{3, 3, 6, 255} : Color{91, 196, 232, 255});
        if (garageBackdrop) {
            const float width = static_cast<float>(std::max(1, GetRenderWidth()));
            const float height = static_cast<float>(std::max(1, GetRenderHeight()));
            const float textureWidth = static_cast<float>(garageBackgroundTexture_.width);
            const float textureHeight = static_cast<float>(garageBackgroundTexture_.height);
            const float screenAspect = width / height;
            const float textureAspect = textureWidth / textureHeight;
            Rectangle source{0.0f, 0.0f, textureWidth, textureHeight};
            if (screenAspect > textureAspect) {
                source.height = textureWidth / screenAspect;
                source.y = (textureHeight - source.height) * 0.5f;
            } else {
                source.width = textureHeight * screenAspect;
                source.x = (textureWidth - source.width) * 0.5f;
            }
            DrawTexturePro(garageBackgroundTexture_, source, {0.0f, 0.0f, width, height},
                           {0.0f, 0.0f}, 0.0f, WHITE);
        } else {
            drawSkyGradient();
        }
        arcade_render::DirectionalLightFog lighting;
        lighting.cameraPosition = camera_.position;
        lighting.fogStart = isMetricCircuit(track_.layout()) ? 10000.0f : 74.0f;
        lighting.fogEnd = isMetricCircuit(track_.layout()) ? 12000.0f : 235.0f;
        lighting.exposure = 1.0f;
        if (mode_ == Mode::Garage) {
            // Neutral, menu-only key light keeps every livery color readable
            // while the authored garage supplies the red atmosphere.
            lighting.sunDirection = {-0.24f, 0.92f, -0.31f};
            lighting.sunColor = {255, 246, 232, 255};
            lighting.skyAmbient = {188, 194, 207, 255};
            lighting.groundAmbient = {118, 92, 94, 255};
            lighting.fogColor = {8, 4, 7, 255};
            lighting.exposure = 1.46f;
        }
        renderer_.setLighting(lighting);
        BeginMode3D(camera_);
        rlDisableBackfaceCulling();
        const bool drawCircuitWorld = mode_ != Mode::Garage;
        const bool authoredTrackDrawn = drawCircuitWorld &&
                                        renderer_.drawAuthoredTrack(static_cast<size_t>(track_.layout()));
        if (drawCircuitWorld && !authoredTrackDrawn) {
            drawEnvironment();
        }
        rlEnableBackfaceCulling();
        if (drawCircuitWorld && !authoredTrackDrawn) {
            drawTrack();
            drawProps();
        }
        drawParticles();
        drawKarts();
        EndMode3D();
        // Keep the dense world pass from sharing a near-capacity rlgl batch
        // with the menu/HUD primitives that must remain complete and crisp.
        rlDrawRenderBatchActive();
        drawSpeedFx();
        drawHud(fps, hasController);
        if (capturePath) {
            rlDrawRenderBatchActive();
            TakeScreenshot(capturePath);
        }
        EndDrawing();
        camera_ = simulationCamera;
    }

    void startRace() {
        activateSelectedMap();
        resetRace();
        assignAiLaunchProfiles();
        mode_ = Mode::Race;
        pauseAction_ = formula_forge::ui::PauseAction::Resume;
        resultsAction_ = formula_forge::ui::ResultsAction::Replay;
    }

    void selectTimeTrialForCapture() {
        selectedSession_ = formula_forge::ui::GameModeOption::TimeTrial;
        resetRace();
        syncGaragePreview();
    }

    bool runTimeTrialAudit() {
        auto press = [&](const Input3D& input) {
            update(kFixedDt, input, true);
            update(kFixedDt, Input3D{}, true);
        };
        Input3D confirm;
        confirm.a = true;
        press(confirm);  // Skip loading.
        Input3D next;
        next.right = true;
        press(next);     // Race -> Time Trial.
        press(confirm);  // Car.
        Input3D back;
        back.back = true;
        press(back);
        const bool backReturnedHome = selectionStage_ == formula_forge::ui::SelectionStage::Mode && mode_ == Mode::Garage;
        press(confirm);  // Car again.
        press(confirm);  // Map and laps.
        press(confirm);  // Start.

        const bool selectionFlow = selectedSession_ == formula_forge::ui::GameModeOption::TimeTrial &&
                                   selectedMap_ == 0 && selectionStage_ == formula_forge::ui::SelectionStage::Map &&
                                   mode_ == Mode::Race && backReturnedHome;

        std::array<Vec2, kKartCount - 1> parkedOpponents{};
        for (int i = 1; i < kKartCount; ++i) {
            parkedOpponents[static_cast<size_t>(i - 1)] = karts_[static_cast<size_t>(i)].pos;
        }
        const float startScore = playerRaceScoreForCapture();
        const float targetDistance = track_.totalLength() * 1.08f;
        const int maxFrames = static_cast<int>(1000.0f / kFixedDt);
        int frames = 0;
        float speedSum = 0.0f;
        int offroadFrames = 0;
        float maxRoadViolation = 0.0f;
        float maxRoadViolationProgress = 0.0f;
        float laneUsageSum = 0.0f;
        float steerUsageSum = 0.0f;
        int saturatedSteerFrames = 0;
        int barrierImpacts = 0;
        std::array<int, 10> offroadBySector{};
        std::array<int, 10> framesBySector{};
        while (playerRaceScoreForCapture() - startScore < targetDistance && frames < maxFrames && mode_ == Mode::Race) {
            const Input3D driveInput = scriptedInput();
            const float priorContact = karts_[0].contactTimer;
            update(kFixedDt, driveInput, true);
            speedSum += length(karts_[0].vel);
            const float laneLimit = std::max(1.0f, roadCenterLimit(karts_[0], track_.sample(karts_[0].progress)));
            laneUsageSum += std::abs(karts_[0].lane) / laneLimit;
            steerUsageSum += std::abs(driveInput.steer);
            saturatedSteerFrames += std::abs(driveInput.steer) > 0.95f ? 1 : 0;
            barrierImpacts += priorContact <= 0.001f && karts_[0].contactTimer > 0.05f ? 1 : 0;
            const float violation = roadEdgeViolation(karts_[0], track_.sample(karts_[0].progress));
            if (violation > maxRoadViolation) {
                maxRoadViolation = violation;
                maxRoadViolationProgress = karts_[0].progress;
            }
            offroadFrames += violation > 1.0f ? 1 : 0;
            const int sector = std::clamp(static_cast<int>(karts_[0].progress / track_.totalLength() * 10.0f), 0, 9);
            ++framesBySector[static_cast<size_t>(sector)];
            offroadBySector[static_cast<size_t>(sector)] += violation > 1.0f ? 1 : 0;
            ++frames;
        }

        bool opponentsParked = true;
        for (int i = 1; i < kKartCount; ++i) {
            opponentsParked = opponentsParked &&
                              lengthSq(karts_[static_cast<size_t>(i)].pos - parkedOpponents[static_cast<size_t>(i - 1)]) < 0.0001f;
        }
        const float distance = playerRaceScoreForCapture() - startScore;
        const bool soloFlow = raceFlow_ && raceFlow_->racerCount() == 1;
        const bool infinite = raceFlow_ && raceFlow_->config().infiniteLaps && targetLaps() == kInfiniteLaps;
        const bool timingValid = hasBestLap_ && bestLapTime_ > 20.0f && lastLapTime_ > 20.0f &&
                                 bestLapTime_ <= lastLapTime_ + 0.001f;
        const float offroadRatio = static_cast<float>(offroadFrames) / std::max(1, frames);
        const float averageSpeedKph = speedSum / std::max(1, frames) / kTrackSimulationUnitsPerMeter * 3.6f;
        const bool staysActive = mode_ == Mode::Race && !raceFinished_ && resultCount_ == 0;
        const bool ok = selectionFlow && frames < maxFrames && distance >= targetDistance && soloFlow && infinite && timingValid &&
                        staysActive && opponentsParked && playerPosition_ == 1 && offroadRatio < 0.08f && barrierImpacts <= 12;
        std::cout << "time-trial-audit frames=" << frames << " distance=" << distance
                  << " completed_laps=" << karts_[0].lap << " racers=" << (raceFlow_ ? raceFlow_->racerCount() : 0)
                  << " last_lap_s=" << lastLapTime_ << " best_lap_s=" << bestLapTime_
                  << " avg_kph=" << averageSpeedKph << " offroad_ratio=" << offroadRatio
                  << " lane_usage=" << laneUsageSum / std::max(1, frames)
                  << " steer_usage=" << steerUsageSum / std::max(1, frames)
                  << " steer_saturation=" << static_cast<float>(saturatedSteerFrames) / std::max(1, frames)
                  << " barrier_impacts=" << barrierImpacts
                  << " max_road_violation_m=" << maxRoadViolation / kTrackSimulationUnitsPerMeter
                  << " max_violation_phase=" << maxRoadViolationProgress / track_.totalLength()
                  << " selected=" << selectionFlow << " solo=" << soloFlow << " infinite=" << infinite << " parked=" << opponentsParked
                  << " active=" << staysActive << " sectors=";
        for (size_t i = 0; i < offroadBySector.size(); ++i) {
            std::cout << (i == 0 ? "" : ",")
                      << static_cast<float>(offroadBySector[i]) / std::max(1, framesBySector[i]);
        }
        std::cout << " ok=" << ok << "\n";
        return ok;
    }

    bool runGridAlignmentAudit() {
        selectedSession_ = formula_forge::ui::GameModeOption::Race;
        float maxSlotPositionErrorMeters = 0.0f;
        float maxHeadingErrorDegrees = 0.0f;
        float maxElevationErrorMeters = 0.0f;
        float maxPlayerStartDistanceMeters = 0.0f;
        float expectedPlayerStartDistanceMeters = 0.0f;
        bool playerLastOnEveryGrid = true;
        bool gridClearOnEveryTrack = true;
        bool fullUniqueFieldOnEveryTrack = true;

        for (int map = 0; map < static_cast<int>(kMaps.size()); ++map) {
            selectedMap_ = map;
            startRace();
            fullUniqueFieldOnEveryTrack =
                fullUniqueFieldOnEveryTrack && karts_.size() == static_cast<size_t>(kKartCount);
            std::array<int, kKartCount> liveryCounts{};
            for (const Kart3D& kart : karts_) {
                if (kart.spec.bodyStyle < 0 || kart.spec.bodyStyle >= kKartCount) {
                    fullUniqueFieldOnEveryTrack = false;
                    continue;
                }
                ++liveryCounts[static_cast<size_t>(kart.spec.bodyStyle)];
            }
            fullUniqueFieldOnEveryTrack =
                fullUniqueFieldOnEveryTrack &&
                std::all_of(liveryCounts.begin(), liveryCounts.end(), [](int count) { return count == 1; });

            float longestCar = 0.0f;
            float widestCar = 0.0f;
            for (const KartSpec3D& spec : specs_) {
                longestCar = std::max(longestCar, spec.length);
                widestCar = std::max(widestCar, spec.width);
            }
            const float unitsPerMeter = isMetricCircuit(track_.layout()) ? kTrackSimulationUnitsPerMeter : 1.0f;
            const float firstRowInsetMeters = longestCar / unitsPerMeter * 0.5f + kGridFirstRowClearanceMeters;
            // Keep this independent of the runtime helper: these constants
            // mirror the authored starting_grid_slots mesh contract.
            const float slotSpacingMeters =
                longestCar / unitsPerMeter +
                (track_.layout() ==
                         TrackLayoutId::Monza
                     ? 12.0f
                     : kGridSlotGapMeters);
            expectedPlayerStartDistanceMeters =
                std::max(expectedPlayerStartDistanceMeters,
                         firstRowInsetMeters + static_cast<float>(kKartCount - 1) * slotSpacingMeters);
            const float columnOffset = std::max(widestCar * 0.95f, 2.0f * unitsPerMeter);
            std::array<float, kKartCount> distanceBehindStartMeters{};
            for (int i = 0; i < kKartCount; ++i) {
                const int gridSlot = i == 0 ? kKartCount - 1 : i - 1;
                const float expectedProgress = track_.startProgress() - firstRowInsetMeters -
                                               static_cast<float>(gridSlot) * slotSpacingMeters;
                const TrackPoint3D expectedPoint = track_.sample(expectedProgress);
                const Kart3D& kart = karts_[static_cast<size_t>(i)];
                const float expectedLane = std::clamp(runtimeGridSideForSlot(gridSlot) * columnOffset,
                                                      -roadCenterLimit(kart, expectedPoint),
                                                      roadCenterLimit(kart, expectedPoint));
                const Vec2 expectedPosition = expectedPoint.pos + expectedPoint.normal * expectedLane;
                maxSlotPositionErrorMeters = std::max(
                    maxSlotPositionErrorMeters, length(kart.pos - expectedPosition) / unitsPerMeter);
                maxHeadingErrorDegrees = std::max(
                    maxHeadingErrorDegrees, std::abs(wrapAngle(kart.heading - angleOf(expectedPoint.tangent))) * RAD2DEG);
                maxElevationErrorMeters = std::max(
                    maxElevationErrorMeters,
                    std::abs(kart.elevation - bankedElevation(expectedPoint, expectedLane)) / unitsPerMeter);
                const TrackProjection3D actualProjection = track_.projectNear(kart.pos, kart.nearest, 6);
                distanceBehindStartMeters[static_cast<size_t>(gridSlot)] =
                    -signedDistanceToLoop(track_.startProgress(), actualProjection.progress, track_.totalLength());
            }

            maxPlayerStartDistanceMeters = std::max(maxPlayerStartDistanceMeters,
                                                    distanceBehindStartMeters.back());
            for (int slot = 1; slot < kKartCount; ++slot) {
                playerLastOnEveryGrid = playerLastOnEveryGrid &&
                                        distanceBehindStartMeters[static_cast<size_t>(slot)] >
                                            distanceBehindStartMeters[static_cast<size_t>(slot - 1)];
            }
            playerLastOnEveryGrid = playerLastOnEveryGrid && playerPosition_ == kKartCount;

            for (int a = 0; a < kKartCount; ++a) {
                for (int b = a + 1; b < kKartCount; ++b) {
                    gridClearOnEveryTrack = gridClearOnEveryTrack &&
                                            !kartContact(karts_[static_cast<size_t>(a)],
                                                         karts_[static_cast<size_t>(b)]).touching;
                }
            }
        }

        // Exercise every possible player selection once: each must replace
        // that livery's AI entry while retaining the complete 11-car field.
        for (int selected = 0; selected < kKartCount; ++selected) {
            selectedCar_ = selected;
            selectedMap_ = 0;
            startRace();
            std::array<int, kKartCount> liveryCounts{};
            for (const Kart3D& kart : karts_) {
                if (kart.spec.bodyStyle >= 0 && kart.spec.bodyStyle < kKartCount) {
                    ++liveryCounts[static_cast<size_t>(kart.spec.bodyStyle)];
                } else {
                    fullUniqueFieldOnEveryTrack = false;
                }
            }
            fullUniqueFieldOnEveryTrack =
                fullUniqueFieldOnEveryTrack &&
                std::all_of(liveryCounts.begin(), liveryCounts.end(), [](int count) { return count == 1; }) &&
                karts_[0].spec.bodyStyle == selected;
        }

        const bool slotsAligned = maxSlotPositionErrorMeters < 0.05f &&
                                  maxHeadingErrorDegrees < 0.05f &&
                                  maxElevationErrorMeters < 0.01f;
        const bool compactGrid =
            maxPlayerStartDistanceMeters < expectedPlayerStartDistanceMeters + 0.25f;
        const bool ok = slotsAligned && compactGrid && playerLastOnEveryGrid &&
                        gridClearOnEveryTrack && fullUniqueFieldOnEveryTrack;
        std::cout << "grid-alignment-audit tracks=" << kMaps.size()
                  << " max_slot_error_m=" << maxSlotPositionErrorMeters
                  << " max_heading_error_deg=" << maxHeadingErrorDegrees
                  << " max_elevation_error_m=" << maxElevationErrorMeters
                  << " player_start_distance_m=" << maxPlayerStartDistanceMeters
                  << " player_last=" << playerLastOnEveryGrid
                  << " grid_clear=" << gridClearOnEveryTrack
                  << " unique_liveries=" << fullUniqueFieldOnEveryTrack
                  << " ok=" << ok << "\n";
        return ok;
    }

    void selectMapForCapture(int index) {
        selectedMap_ = std::clamp(index, 0, static_cast<int>(kMaps.size()) - 1);
        activateSelectedMap();
        resetRace();
        syncGaragePreview();
    }

    void showMapSelectionForCapture(int index) {
        selectMapForCapture(index);
        mode_ = Mode::Garage;
        selectionStage_ = formula_forge::ui::SelectionStage::Map;
        updateGarageCamera(1.0f);
    }

    void resetAgentSession() {
        selectedSession_ = formula_forge::ui::GameModeOption::Race;
        selectedCar_ = 0;
        selectedRacer_ = 0;
        selectedMap_ = 0;
        selectedLapOption_ = 0;
        selectionStage_ = formula_forge::ui::SelectionStage::Mode;
        pauseAction_ = formula_forge::ui::PauseAction::Resume;
        resultsAction_ = formula_forge::ui::ResultsAction::Replay;
        loadingTime_ = 0.0f;
        presentationTime_ = 0.0f;
        garageSpin_ = 0.0f;
        mode_ = Mode::Loading;
        activateSelectedMap();
        resetRace();
        syncGaragePreview();
    }

    std::string agentStateJson(std::uint64_t frame) const {
        static constexpr std::array<std::string_view, 5> kModeNames = {
            "loading", "garage", "race", "pause", "results"};
        static constexpr std::array<std::string_view, 3> kStageNames = {
            "mode", "car", "map"};
        static constexpr std::array<std::string_view, 4> kPhaseNames = {
            "grid", "countdown", "racing", "finished"};
        const Kart3D& player = karts_[0];
        const TrackPoint3D point = track_.sample(player.progress);
        const float unitsPerMeter = isMetricCircuit(track_.layout()) ? kTrackSimulationUnitsPerMeter : 1.0f;
        const float speedKphScale = speedKphPerSimulationUnit(track_.layout());
        const float speedKph = std::max(0.0f, player.telemetry.forwardSpeed) * speedKphScale;
        const float roadClearance = (roadCenterLimit(player, point) - std::abs(player.lane)) / unitsPerMeter;
        const float barrierClearance = (hardBoundaryLaneLimit(player, point) - std::abs(player.lane)) / unitsPerMeter;
        const float lapProgress = raceLapProgress(player) / std::max(track_.totalLength(), 1.0f);
        const ArcadeRacePhase phase = raceFlow_ ? raceFlow_->phase() : ArcadeRacePhase::Grid;
        const ArcadeRacerRaceState* raceState = raceFlow_ ? &raceFlow_->racer(0) : nullptr;

        std::ostringstream out;
        out.setf(std::ios::fixed);
        out.precision(4);
        out << "{\"frame\":" << frame << ",\"sim_time_s\":" << static_cast<double>(frame) * kFixedDt
            << ",\"screen\":" << agent_play::jsonString(kModeNames[static_cast<size_t>(mode_)])
            << ",\"selection_stage\":" << agent_play::jsonString(kStageNames[static_cast<size_t>(selectionStage_)])
            << ",\"selected\":{\"session\":"
            << agent_play::jsonString(selectedSession_ == formula_forge::ui::GameModeOption::Race ? "race" : "time_trial")
            << ",\"driver\":" << agent_play::jsonString(racers_[static_cast<size_t>(selectedRacer_)])
            << ",\"car\":" << agent_play::jsonString(specs_[static_cast<size_t>(selectedCar_)].name)
            << ",\"map\":" << agent_play::jsonString(selectedMap().name)
            << ",\"laps\":" << targetLaps() << "}"
            << ",\"race\":{\"phase\":" << agent_play::jsonString(kPhaseNames[static_cast<size_t>(phase)])
            << ",\"countdown_s\":" << (raceFlow_ ? raceFlow_->countdownRemainingSeconds() : 0.0f)
            << ",\"time_s\":" << raceTime_ << ",\"lap\":" << std::max(0, player.lap + 1)
            << ",\"lap_progress\":" << lapProgress << ",\"position\":" << playerPosition_
            << ",\"racers\":" << activeKartCount() << ",\"finished\":" << (raceFinished_ ? "true" : "false")
            << ",\"wrong_way\":" << (raceState && raceState->wrongWay ? "true" : "false") << "}"
            << ",\"car\":{\"speed_kph\":" << speedKph
            << ",\"speed_normalized\":" << player.telemetry.normalizedSpeed
            << ",\"position_m\":[" << player.pos.x / unitsPerMeter << "," << player.pos.y / unitsPerMeter << "]"
            << ",\"heading_rad\":" << player.heading << ",\"yaw_rate\":" << player.yawRate
            << ",\"slip_angle_rad\":" << player.slipAngle << ",\"steer\":" << player.steerSmoothed
            << ",\"engine_load\":" << player.engineLoad << ",\"brake_load\":" << player.brakeLoad
            << ",\"gear\":" << player.gear << ",\"engine_rpm\":"
            << player.engineRpmNormalized * player.tuning.redlineRpm
            << ",\"rpm_normalized\":" << player.engineRpmNormalized
            << ",\"shift_remaining_s\":" << player.shiftTimer
            << ",\"shift_rejected\":" << (player.shiftRejectTimer > 0.0f ? "true" : "false")
            << ",\"engine_brake_g\":" << player.engineBrakingApplied * speedKphScale /
                                               (3.6f * kStandardGravityMetersPerSecondSquared)
            << ",\"aero_drag_g\":" << player.aerodynamicDragApplied * speedKphScale /
                                             (3.6f * kStandardGravityMetersPerSecondSquared)
            << ",\"rolling_g\":" << player.rollingResistanceApplied * speedKphScale /
                                           (3.6f * kStandardGravityMetersPerSecondSquared)
            << ",\"tire_longitudinal_usage\":" << player.tireLongitudinalUsage
            << ",\"lane_m\":" << player.lane / unitsPerMeter
            << ",\"road_edge_clearance_m\":" << roadClearance
            << ",\"barrier_clearance_m\":" << barrierClearance
            << ",\"on_road\":" << (roadClearance >= 0.0f ? "true" : "false")
            << ',' << agent_play::contactTelemetryJson(player.barrierContact, player.vehicleContact,
                                                        player.contactImpulse, contactCauseName(player.contactCause))
            << ",\"grounded\":" << (player.grounded ? "true" : "false")
            << ",\"elevation_m\":" << player.elevation / unitsPerMeter << "}"
            << ",\"nearby_cars\":[";
        bool first = true;
        for (int i = 1; i < activeKartCount(); ++i) {
            const Kart3D& other = karts_[static_cast<size_t>(i)];
            const float relativeProgress = signedDistanceToLoop(player.progress, other.progress, track_.totalLength()) / unitsPerMeter;
            if (std::abs(relativeProgress) > 150.0f) {
                continue;
            }
            if (!first) out << ',';
            first = false;
            out << "{\"driver\":" << agent_play::jsonString(other.racer)
                << ",\"relative_progress_m\":" << relativeProgress
                << ",\"lane_m\":" << other.lane / unitsPerMeter
                << ",\"speed_kph\":" << std::max(0.0f, other.telemetry.forwardSpeed) * speedKphScale << '}';
        }
        out << "]}";
        return out.str();
    }

    void showResultsCapture() {
        selectedSession_ = formula_forge::ui::GameModeOption::Race;
        static constexpr std::array<int, kKartCount> kCaptureOrder = {1, 0, 4, 2, 5, 3, 7, 6, 9, 8, 10};
        static constexpr std::array<float, kKartCount> kCaptureTimes = {
            101.42f, 103.87f, 106.15f, 108.74f, 111.26f, 115.90f,
            118.35f, 121.08f, 124.44f, 127.91f, 131.62f};
        resultCount_ = kKartCount;
        for (int i = 0; i < kKartCount; ++i) {
            results_[static_cast<size_t>(i)] = {kCaptureOrder[static_cast<size_t>(i)], i + 1,
                                                kCaptureTimes[static_cast<size_t>(i)], std::max(1, targetLaps())};
        }
        mode_ = Mode::Results;
        resultsAction_ = formula_forge::ui::ResultsAction::Replay;
    }

    void setupSectionTour(float phase, int variant) {
        resetRace();
        mode_ = Mode::Race;
        particles_.clear();
        raceTime_ = phase * 18.0f;

        const float baseProgress = wrapDistance(track_.totalLength() * phase, track_.totalLength());
        // Keep the capture-only field close enough to read as an active race
        // in screenshots while retaining safe longitudinal separation.
        static constexpr std::array<float, kKartCount> kProgressOffset = {
            0.0f, 15.0f, 24.0f, 34.0f, 45.0f, 57.0f, 69.0f, 82.0f, 96.0f, 111.0f, 127.0f};
        static constexpr std::array<float, kKartCount> kLaneOffset = {
            0.0f, -20.0f, 20.0f, -8.0f, 8.0f, 0.0f, -16.0f, 16.0f, -4.0f, 4.0f, 12.0f};

        for (int i = 0; i < kKartCount; ++i) {
            Kart3D& kart = karts_[static_cast<size_t>(i)];
            const float progress = wrapDistance(baseProgress + kProgressOffset[static_cast<size_t>(i)] +
                                                    static_cast<float>((variant * (i + 3)) % 5) * 0.5f,
                                                track_.totalLength());
            const TrackPoint3D point = track_.sample(progress);
            const float lane = std::clamp(kLaneOffset[static_cast<size_t>(i)], -roadCenterLimit(kart, point), roadCenterLimit(kart, point));
            kart.pos = point.pos + point.normal * lane;
            kart.heading = angleOf(point.tangent) + static_cast<float>((i % 3) - 1) * 0.018f;
            kart.vel = point.tangent * (i == 0 ? 104.0f : 82.0f + static_cast<float>((i * 7) % 20));
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.progress = track_.pointAtIndex(kart.nearest).progress;
            kart.previousProgress = kart.progress;
            kart.previousRenderPos = kart.pos;
            kart.previousRenderElevation = kart.elevation;
            kart.previousRenderHeading = kart.heading;
            kart.previousRenderProgress = kart.progress;
            kart.lap = 0;
            kart.lane = lane;
            kart.elevation = bankedElevation(point, lane);
            kart.verticalSpeed = 0.0f;
            kart.grounded = true;
            kart.airborneTime = 0.0f;
            kart.bodyPitch = std::atan(point.grade);
            kart.bodyRoll = 0.0f;
            kart.ghostTimer = 3.0f;
            kart.contactTimer = 0.0f;
            kart.drifting = false;
            kart.boostTimer = i == 0 && variant % 3 == 1 ? 0.35f : 0.0f;
            kart.driftCharge = 0.0f;
            // Section tours begin at racing speed in the middle of a lap;
            // launch personalities only belong to a real standing start.
            kart.aiLaunchElapsed = kart.aiLaunchDuration;
            kart.steerSmoothed = (variant % 2 == 0 ? -0.18f : 0.18f) * std::clamp(point.curvature * 7.0f, 0.0f, 1.0f);
        }

        if (raceFlow_) {
            const auto inputs = currentRaceInputs();
            for (int i = 0; i < activeKartCount(); ++i) {
                raceFlow_->rebaseRacerSample(static_cast<size_t>(i), inputs[static_cast<size_t>(i)]);
            }
            raceFlow_->beginRace();
        }
        updateRaceOrder();
        const Kart3D& player = karts_[0];
        const TrackPoint3D ground = track_.sample(player.progress);
        const TrackPoint3D future = track_.sample(player.progress + 150.0f);
        const Vec2 view = normalize(lerp(fromAngle(player.heading), future.tangent, 0.35f));
        const Vec2 side = ground.normal * (variant % 2 == 0 ? 24.0f : -16.0f);
        const float groundY = bankedElevation(ground, player.lane);
        camera_.position = toWorld(player.pos - view * 190.0f + side, groundY + 82.0f);
        camera_.target = toWorld(player.pos + view * 122.0f + ground.normal * 6.0f, groundY + 13.0f);
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = 60.0f;
        camera_.projection = CAMERA_PERSPECTIVE;
    }

    Input3D scriptedInput() const {
        const Kart3D& player = karts_[0];
        Input3D input = auditInput(AuditDriver::Attack, player);
        float nearestTraffic = std::numeric_limits<float>::max();
        float passingSide = 0.0f;
        for (int i = 1; i < activeKartCount(); ++i) {
            const Kart3D& other = karts_[static_cast<size_t>(i)];
            const float ahead = progressAhead(player.progress, other.progress, track_.totalLength());
            if (ahead > 8.0f && ahead < 190.0f && std::abs(other.lane - player.lane) < 52.0f && ahead < nearestTraffic) {
                nearestTraffic = ahead;
                passingSide = other.lane >= 0.0f ? -1.0f : 1.0f;
            }
        }
        if (passingSide != 0.0f) {
            const TrackPoint3D future = track_.sample(player.progress + 145.0f);
            const TrackPoint3D apex = track_.sample(player.progress + 240.0f);
            if (std::max(future.curvature, apex.curvature) < 0.038f) {
                const float passingLane = passingSide * std::max(0.0f, roadCenterLimit(player, future) * 0.68f);
                input.steer = aiSteerForProgress(player, 0, passingLane);
            }
        }
        return input;
    }

    Mode mode() const { return mode_; }

    bool runHandlingAudit() {
        track_.rebuild(TrackLayoutId::Monza);
        const ArcadeVehicleConfig formulaTuning = selectedTrackTuning(specs_[0]);
        const KartSpec3D& referenceSpec = specs_[0];
        const bool specField = std::all_of(specs_.begin(), specs_.end(), [&](const KartSpec3D& spec) {
            return spec.maxSpeed == referenceSpec.maxSpeed && spec.accel == referenceSpec.accel &&
                   spec.brake == referenceSpec.brake && spec.grip == referenceSpec.grip &&
                   spec.drift == referenceSpec.drift && spec.width == referenceSpec.width &&
                   spec.length == referenceSpec.length && spec.height == referenceSpec.height;
        });
        const ArcadeSurface road;
        struct BrakingDistanceResult {
            float startKph = 0.0f;
            float targetKph = 0.0f;
            float distanceMeters = 0.0f;
            float seconds = 0.0f;
        };
        const auto brakingDistance = [&](float startKph, float targetKph) {
            ArcadeVehicleState state;
            state.grounded = true;
            state.vel = {startKph / 3.6f * kTrackSimulationUnitsPerMeter, 0.0f};
            state.forwardSpeed = length(state.vel);
            syncArcadeTransmissionToSpeed(state, formulaTuning);
            ArcadeVehicleControl control;
            control.brake = 1.0f;
            const Vec2 start = state.pos;
            int frames = 0;
            constexpr int kMaxBrakingFrames = static_cast<int>(12.0f / kFixedDt);
            const float targetSpeed = targetKph / 3.6f * kTrackSimulationUnitsPerMeter;
            while (frames < kMaxBrakingFrames && state.forwardSpeed > std::max(2.0f, targetSpeed)) {
                stepArcadeVehicle(state, formulaTuning, control, road, kFixedDt);
                ++frames;
            }
            return BrakingDistanceResult{startKph, targetKph,
                                         length(state.pos - start) / kTrackSimulationUnitsPerMeter,
                                         static_cast<float>(frames) * kFixedDt};
        };
        const std::array<BrakingDistanceResult, 3> brakingDistances = {
            brakingDistance(300.0f, 100.0f),
            brakingDistance(200.0f, 80.0f),
            brakingDistance(100.0f, 0.0f),
        };
        const auto coastEndSpeed = [&](float startKph, float seconds, bool aeroOnly) {
            ArcadeVehicleConfig coastTuning = formulaTuning;
            if (aeroOnly) {
                coastTuning.engineBrakingAcceleration = 0.0f;
                coastTuning.rollingResistance = 0.0f;
            }
            ArcadeVehicleState state;
            state.grounded = true;
            state.vel = {startKph / 3.6f * kTrackSimulationUnitsPerMeter, 0.0f};
            state.forwardSpeed = length(state.vel);
            syncArcadeTransmissionToSpeed(state, coastTuning);
            ArcadeVehicleControl coastControl;
            coastControl.automaticShift = false;
            for (int frame = 0; frame < static_cast<int>(seconds / kFixedDt); ++frame) {
                stepArcadeVehicle(state, coastTuning, coastControl, road, kFixedDt);
            }
            return state.forwardSpeed / kTrackSimulationUnitsPerMeter * 3.6f;
        };
        constexpr std::array<float, 3> kCoastStartKph = {300.0f, 200.0f, 100.0f};
        std::array<float, 3> coastEndKph{};
        std::array<float, 3> aeroOnlyLossKph{};
        for (size_t index = 0; index < kCoastStartKph.size(); ++index) {
            coastEndKph[index] = coastEndSpeed(kCoastStartKph[index], 3.0f, false);
            aeroOnlyLossKph[index] = kCoastStartKph[index] - coastEndSpeed(kCoastStartKph[index], 1.0f, true);
        }
        ArcadeVehicleState straightLine;
        straightLine.grounded = true;
        ArcadeVehicleControl fullThrottle;
        fullThrottle.throttle = 1.0f;
        float zeroToOneHundredSeconds = 0.0f;
        float zeroToTwoHundredSeconds = 0.0f;
        constexpr int kStraightLineFrames = static_cast<int>(35.0f / kFixedDt);
        for (int frame = 0; frame < kStraightLineFrames; ++frame) {
            stepArcadeVehicle(straightLine, formulaTuning, fullThrottle, road, kFixedDt);
            const float elapsed = static_cast<float>(frame + 1) * kFixedDt;
            const float speedKph = straightLine.forwardSpeed / kTrackSimulationUnitsPerMeter * 3.6f;
            if (zeroToOneHundredSeconds <= 0.0f && speedKph >= 100.0f) {
                zeroToOneHundredSeconds = elapsed;
            }
            if (zeroToTwoHundredSeconds <= 0.0f && speedKph >= 200.0f) {
                zeroToTwoHundredSeconds = elapsed;
            }
        }
        const float terminalSpeedKph = straightLine.forwardSpeed / kTrackSimulationUnitsPerMeter * 3.6f;
        track_.rebuild(TrackLayoutId::Monza);
        const float mechanicalGripG = formulaTuning.lateralGripAcceleration /
                                      (kTrackSimulationUnitsPerMeter * kStandardGravityMetersPerSecondSquared);
        const float highSpeedGripG = mechanicalGripG * (1.0f + formulaTuning.downforceGripGain);

        int namedBrakingCorners = 0;
        float lowestNamedCornerSpeedKph = terminalSpeedKph;
        const auto monzaTurns = trackTurnExpectations(TrackLayoutId::Monza);
        for (const TrackTurnExpectation& turn : monzaTurns) {
            float peakCurvaturePerMeter = 0.0f;
            const float centerProgress = turn.lapFraction * track_.totalLength();
            for (int offset = -4; offset <= 4; ++offset) {
                const float progress = centerProgress + static_cast<float>(offset) * 8.0f;
                const Vec2 before = track_.sample(progress - 8.0f).tangent;
                const Vec2 after = track_.sample(progress + 8.0f).tangent;
                peakCurvaturePerMeter = std::max(peakCurvaturePerMeter,
                                                 std::abs(wrapAngle(angleOf(after) - angleOf(before))) / 16.0f);
            }
            const float baseAcceleration = formulaTuning.lateralGripAcceleration / kTrackSimulationUnitsPerMeter;
            const float maxSpeedMetersPerSecond = formulaTuning.maxForwardSpeed / kTrackSimulationUnitsPerMeter;
            const float downforceTerm = baseAcceleration * formulaTuning.downforceGripGain /
                                        (maxSpeedMetersPerSecond * maxSpeedMetersPerSecond);
            const float speedSquaredDenominator = peakCurvaturePerMeter - downforceTerm;
            const float cornerSpeedMetersPerSecond = speedSquaredDenominator > 0.00001f
                                                         ? std::sqrt(baseAcceleration / speedSquaredDenominator)
                                                         : maxSpeedMetersPerSecond;
            const float cornerSpeedKph = std::min(terminalSpeedKph, cornerSpeedMetersPerSecond * 3.6f);
            lowestNamedCornerSpeedKph = std::min(lowestNamedCornerSpeedKph, cornerSpeedKph);
            namedBrakingCorners += cornerSpeedKph < terminalSpeedKph * 0.84f ? 1 : 0;
        }

        const AuditResult3D noBrake = simulateAuditDriver(AuditDriver::NoBrake, 75.0f);
        const AuditResult3D brake = simulateAuditDriver(AuditDriver::Brake, 75.0f);
        const AuditResult3D attack = simulateAuditDriver(AuditDriver::Attack, 75.0f);

        struct CornerBenchmarkSpec {
            const char* name = "";
            TrackLayoutId layout = TrackLayoutId::Monza;
            float lapFraction = 0.0f;
            float approachMeters = 0.0f;
            float brakeLeadMeters = 0.0f;
            float targetKph = 0.0f;
            float initialKph = 0.0f;
            bool expectedFlat = false;
        };
        struct CornerBenchmarkResult {
            float entryKph = 0.0f;
            float minimumKph = std::numeric_limits<float>::max();
            float exitKph = 0.0f;
            float maxOffroadMeters = 0.0f;
            int contacts = 0;
            int minimumGear = 8;
        };
        const auto cornerBenchmark = [&](const CornerBenchmarkSpec& spec, bool useBrakes) {
            track_.rebuild(spec.layout);
            const float unitsPerMeter = kTrackSimulationUnitsPerMeter;
            const float cornerProgress = spec.lapFraction * track_.totalLength();
            const float startProgress = cornerProgress - spec.approachMeters;
            const TrackPoint3D start = track_.sample(startProgress);
            Kart3D kart;
            kart.spec = specs_[0];
            kart.tuning = selectedTrackTuning(kart.spec);
            kart.racer = racers_[0];
            kart.pos = start.pos;
            kart.heading = angleOf(start.tangent);
            kart.vel = start.tangent * (spec.initialKph / 3.6f * unitsPerMeter);
            syncArcadeTransmissionToSpeed(kart, kart.tuning);
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.progress = track_.pointAtIndex(kart.nearest).progress;
            kart.previousProgress = kart.progress;
            kart.elevation = bankedElevation(start, 0.0f);
            kart.grounded = true;

            CornerBenchmarkResult result;
            float traveledMeters = 0.0f;
            bool entrySampled = false;
            bool exitSampled = false;
            const float entryDistance = spec.approachMeters - 25.0f;
            const float cornerEndDistance = spec.approachMeters + 65.0f;
            const float exitDistance = spec.approachMeters + 120.0f;
            constexpr int kMaxCornerFrames = static_cast<int>(20.0f / kFixedDt);
            for (int frame = 0; frame < kMaxCornerFrames && traveledMeters < exitDistance; ++frame) {
                const float beforeProgress = kart.progress;
                const float beforeContact = kart.contactTimer;
                Input3D input = auditInput(AuditDriver::Attack, kart);
                const float speedKph = length(kart.vel) / unitsPerMeter * 3.6f;
                const float distanceToCornerMeters = spec.approachMeters - traveledMeters;
                if (useBrakes) {
                    const bool brakingZone = distanceToCornerMeters <= spec.brakeLeadMeters &&
                                             distanceToCornerMeters > 8.0f && speedKph > spec.targetKph;
                    input.brake = brakingZone ? 1.0f : 0.0f;
                    input.throttle = brakingZone ||
                                             (distanceToCornerMeters <= 8.0f && traveledMeters < cornerEndDistance)
                                         ? 0.0f
                                         : 1.0f;
                } else {
                    input.brake = 0.0f;
                    input.throttle = 1.0f;
                }
                updatePlayer(kart, input, kFixedDt);
                const TrackPoint3D center = track_.sample(kart.progress);
                traveledMeters += std::max(0.0f,
                                           signedDistanceToLoop(beforeProgress, kart.progress, track_.totalLength()));
                const float currentKph = length(kart.vel) / unitsPerMeter * 3.6f;
                if (!entrySampled && traveledMeters >= entryDistance) {
                    result.entryKph = currentKph;
                    entrySampled = true;
                }
                if (traveledMeters >= entryDistance && traveledMeters <= cornerEndDistance) {
                    result.minimumKph = std::min(result.minimumKph, currentKph);
                    result.minimumGear = std::min(result.minimumGear, kart.gear);
                }
                if (!exitSampled && traveledMeters >= exitDistance) {
                    result.exitKph = currentKph;
                    exitSampled = true;
                }
                result.maxOffroadMeters = std::max(result.maxOffroadMeters,
                                                   roadEdgeViolation(kart, center) / unitsPerMeter);
                result.contacts += beforeContact <= 0.001f && kart.contactTimer > 0.05f ? 1 : 0;
            }
            if (result.minimumKph == std::numeric_limits<float>::max()) {
                result.minimumKph = 0.0f;
            }
            if (!exitSampled) {
                result.exitKph = length(kart.vel) / unitsPerMeter * 3.6f;
            }
            return result;
        };
        const std::array<CornerBenchmarkSpec, 5> cornerSpecs = {{
            {"monza_t1", TrackLayoutId::Monza, 0.056f, 190.0f, 92.0f, 88.0f, 300.0f},
            {"monza_lesmo1", TrackLayoutId::Monza, 0.347f, 210.0f, 165.0f, 70.0f, 265.0f},
            {"suzuka_t1", TrackLayoutId::Suzuka, 0.097f, 240.0f, 225.0f, 90.0f, 285.0f},
            {"suzuka_degner", TrackLayoutId::Suzuka, 0.347f, 185.0f, 120.0f, 120.0f, 270.0f},
            {"suzuka_130r", TrackLayoutId::Suzuka, 0.819f, 260.0f, 0.0f, 297.0f, 305.0f, true},
        }};
        std::array<CornerBenchmarkResult, cornerSpecs.size()> flatCorners{};
        std::array<CornerBenchmarkResult, cornerSpecs.size()> brakedCorners{};
        for (size_t i = 0; i < cornerSpecs.size(); ++i) {
            flatCorners[i] = cornerBenchmark(cornerSpecs[i], false);
            brakedCorners[i] = cornerBenchmark(cornerSpecs[i], true);
        }
        track_.rebuild(TrackLayoutId::Monza);
        const bool controlledRoad = attack.offroadFrames < 280 &&
                                    attack.maxOffroad <= 2.1f * kTrackSimulationUnitsPerMeter;
        const bool noBrakeConsequences = noBrake.offroadFrames > 30 || noBrake.maxOffroad > 5.0f;
        const bool groundClear = std::abs(noBrake.minGroundClearance) <= 0.03f && std::abs(brake.minGroundClearance) <= 0.03f &&
                                 std::abs(attack.minGroundClearance) <= 0.03f;
        const bool stable = noBrake.progressJumps == 0 && brake.progressJumps == 0 && attack.progressJumps == 0;
        const bool moving = attack.score > 700.0f;
        const float measuredLapSeconds = attack.score > 1.0f ? 75.0f * track_.totalLength() / attack.score : 999.0f;
        const bool inputContract = controllerContractAudit();
        const bool formulaCornering = attack.brakeFrames > 100 && attack.poweredExitFrames > 100 &&
                                      attack.driftFrames == 0 && attack.maxSlip < 0.14f &&
                                      attack.score > brake.score * 0.98f;
        const bool formulaPerformance = terminalSpeedKph >= 305.0f && terminalSpeedKph <= 330.0f &&
                                        zeroToOneHundredSeconds >= 2.5f && zeroToOneHundredSeconds <= 3.0f &&
                                        zeroToTwoHundredSeconds >= 5.5f && zeroToTwoHundredSeconds <= 7.0f;
        const float yawEffectiveHighSpeedGripG = highSpeedGripG * formulaTuning.tireLimitedYawScale;
        const bool formulaGrip = mechanicalGripG >= 1.6f && mechanicalGripG <= 2.0f &&
                                 yawEffectiveHighSpeedGripG >= 4.6f && yawEffectiveHighSpeedGripG <= 5.1f &&
                                 namedBrakingCorners >= 6 && lowestNamedCornerSpeedKph < 150.0f;
        const bool progressiveBraking = brakingDistances[0].distanceMeters >= 55.0f &&
                                        brakingDistances[0].distanceMeters <= 105.0f &&
                                        brakingDistances[1].distanceMeters >= 30.0f &&
                                        brakingDistances[1].distanceMeters <= 75.0f &&
                                        brakingDistances[2].distanceMeters >= 14.0f &&
                                        brakingDistances[2].distanceMeters <= 32.0f &&
                                        brakingDistances[2].seconds >= 1.35f;
        const bool naturalCoast = coastEndKph[0] >= 245.0f && coastEndKph[0] <= 280.0f &&
                                  coastEndKph[1] >= 165.0f && coastEndKph[1] <= 192.0f &&
                                  coastEndKph[2] >= 72.0f && coastEndKph[2] <= 96.0f &&
                                  aeroOnlyLossKph[0] > aeroOnlyLossKph[1] * 1.8f &&
                                  aeroOnlyLossKph[1] > aeroOnlyLossKph[2] * 2.8f;
        bool namedCornerProof = true;
        for (size_t i = 0; i < cornerSpecs.size(); ++i) {
            if (cornerSpecs[i].expectedFlat) {
                namedCornerProof = namedCornerProof && flatCorners[i].minimumKph >= 285.0f &&
                                   flatCorners[i].maxOffroadMeters <= 1.50f && flatCorners[i].contacts == 0 &&
                                   flatCorners[i].minimumGear == 8;
            } else {
                namedCornerProof = namedCornerProof &&
                                   brakedCorners[i].entryKph + 12.0f < flatCorners[i].entryKph &&
                                   brakedCorners[i].maxOffroadMeters + 0.25f < flatCorners[i].maxOffroadMeters &&
                                   brakedCorners[i].contacts == 0 &&
                                   brakedCorners[i].exitKph > brakedCorners[i].minimumKph + 8.0f;
            }
        }

        track_.rebuild(TrackLayoutId::Suzuka);
        float peak130rCurvaturePerMeter = 0.0f;
        for (float phase = 0.795f; phase <= 0.8501f; phase += 0.0005f) {
            const TrackPoint3D point = track_.sample(phase * track_.totalLength());
            const float curvatureSpanMeters = 16.0f * track_.totalLength() /
                                              static_cast<float>(track_.sampleCount());
            peak130rCurvaturePerMeter = std::max(peak130rCurvaturePerMeter,
                                                 point.curvature / curvatureSpanMeters);
        }
        const bool smooth130rGeometry = peak130rCurvaturePerMeter >= 0.00250f &&
                                        peak130rCurvaturePerMeter <= 0.00445f;

        bool formulaGearMap = true;
        bool formulaGripMap = true;
        bool formulaDynamicsMap = true;
        int formulaGearChecks = 0;
        int formulaGripChecks = 0;
        int formulaDynamicsChecks = 0;
        float maximumCornerGripScale = 1.0f;
        float minimumYawRateMargin = std::numeric_limits<float>::max();
        for (TrackLayoutId layout : {TrackLayoutId::Spa, TrackLayoutId::Suzuka, TrackLayoutId::Silverstone,
                                     TrackLayoutId::Monza, TrackLayoutId::Interlagos,
                                     TrackLayoutId::Shanghai, TrackLayoutId::Bahrain,
                                     TrackLayoutId::Sepang,
                                     TrackLayoutId::Cota, TrackLayoutId::Istanbul,
                                     TrackLayoutId::Hockenheim, TrackLayoutId::Buddh}) {
            track_.rebuild(layout);
            const ArcadeVehicleConfig layoutTuning = selectedTrackTuning(specs_[0]);
            for (const FormulaCornerTarget& target : formulaCornerTargets(layout)) {
                const float targetSpeed = target.speedKph / speedKphPerSimulationUnit(layout);
                ArcadeVehicleState transmissionState;
                transmissionState.grounded = true;
                const float transmissionStartKph = target.fullThrottle
                                                       ? std::max(30.0f, target.speedKph - 100.0f)
                                                       : 318.0f;
                transmissionState.vel = {transmissionStartKph / speedKphPerSimulationUnit(layout), 0.0f};
                transmissionState.forwardSpeed = length(transmissionState.vel);
                syncArcadeTransmissionToSpeed(transmissionState, layoutTuning);
                ArcadeVehicleControl transmissionControl;
                transmissionControl.throttle = target.fullThrottle ? 1.0f : 0.0f;
                transmissionControl.brake = target.fullThrottle ? 0.0f : 1.0f;
                for (int frame = 0; frame < static_cast<int>(12.0f / kFixedDt); ++frame) {
                    const bool targetReached = target.fullThrottle
                                                   ? transmissionState.forwardSpeed >= targetSpeed
                                                   : transmissionState.forwardSpeed <= targetSpeed;
                    if (targetReached) {
                        break;
                    }
                    stepArcadeVehicle(transmissionState, layoutTuning, transmissionControl, road, kFixedDt);
                }
                const int mappedGear = transmissionState.gear;
                formulaGearMap = formulaGearMap && std::abs(mappedGear - target.gear) <= 1;
                if (layout == TrackLayoutId::Suzuka && std::string_view(target.name) == "130R") {
                    formulaGearMap = formulaGearMap && mappedGear == 8;
                }
                ++formulaGearChecks;

                Kart3D dynamicsCalibrationKart;
                dynamicsCalibrationKart.spec = specs_[0];
                dynamicsCalibrationKart.tuning = layoutTuning;
                dynamicsCalibrationKart.progress = target.lapFraction * track_.totalLength();
                const TrackPoint3D dynamicsPoint = track_.sample(dynamicsCalibrationKart.progress);
                dynamicsCalibrationKart.vel = dynamicsPoint.tangent * targetSpeed;
                const float dynamicsGripScale = formulaCornerGripScale(dynamicsCalibrationKart, dynamicsPoint);
                const float curvatureSpanMeters = 16.0f * track_.totalLength() /
                                                  static_cast<float>(track_.sampleCount());
                const float targetSpeedMetersPerSecond = target.speedKph / 3.6f;
                const float requiredYawRate = targetSpeedMetersPerSecond *
                                              dynamicsPoint.curvature / curvatureSpanMeters;
                ArcadeVehicleState dynamicsState;
                dynamicsState.grounded = true;
                dynamicsState.vel = {targetSpeed, 0.0f};
                dynamicsState.forwardSpeed = targetSpeed;
                syncArcadeTransmissionToSpeed(dynamicsState, layoutTuning);
                ArcadeSurface dynamicsSurface;
                dynamicsSurface.grip = dynamicsGripScale;
                ArcadeVehicleControl dynamicsControl;
                dynamicsControl.steer = 1.0f;
                dynamicsControl.throttle = target.fullThrottle ? 1.0f : 0.25f;
                float realizedYawRate = 0.0f;
                for (int frame = 0; frame < static_cast<int>(1.5f / kFixedDt); ++frame) {
                    stepArcadeVehicle(dynamicsState, layoutTuning, dynamicsControl, dynamicsSurface, kFixedDt);
                    if (frame >= static_cast<int>(0.5f / kFixedDt)) {
                        realizedYawRate = std::max(realizedYawRate, std::abs(dynamicsState.yawRate));
                    }
                }
                const float yawRateMargin = realizedYawRate - requiredYawRate;
                minimumYawRateMargin = std::min(minimumYawRateMargin, yawRateMargin);
                formulaDynamicsMap = formulaDynamicsMap && yawRateMargin >= -0.02f;
                if (yawRateMargin < -0.02f) {
                    std::cout << "handling-map-yaw-failure track="
                              << aiCircuitProfile(layout).name
                              << " corner=" << target.name
                              << " phase=" << target.lapFraction
                              << " target_kph=" << target.speedKph
                              << " required_yaw=" << requiredYawRate
                              << " realized_yaw=" << realizedYawRate
                              << " margin=" << yawRateMargin << "\n";
                }
                ++formulaDynamicsChecks;

                for (float phaseOffset = -0.014f; phaseOffset <= 0.0141f; phaseOffset += 0.002f) {
                    Kart3D calibrationKart;
                    calibrationKart.spec = specs_[0];
                    calibrationKart.tuning = layoutTuning;
                    calibrationKart.progress = wrapDistance((target.lapFraction + phaseOffset) * track_.totalLength(),
                                                            track_.totalLength());
                    const TrackPoint3D point = track_.sample(calibrationKart.progress);
                    calibrationKart.vel = point.tangent * (target.speedKph / 3.6f * kTrackSimulationUnitsPerMeter);
                    const float scale = formulaCornerGripScale(calibrationKart, point);
                    maximumCornerGripScale = std::max(maximumCornerGripScale, scale);
                    const float curvatureSpanMeters = 16.0f * track_.totalLength() /
                                                      static_cast<float>(track_.sampleCount());
                    const float curvaturePerMeter = point.curvature / curvatureSpanMeters;
                    const float speedMetersPerSecond = target.speedKph / 3.6f;
                    const float normalizedSpeed = speedMetersPerSecond /
                                                  (layoutTuning.maxForwardSpeed / kTrackSimulationUnitsPerMeter);
                    const float availableAcceleration = layoutTuning.lateralGripAcceleration /
                                                            kTrackSimulationUnitsPerMeter *
                                                        layoutTuning.tireLimitedYawScale *
                                                        (1.0f + layoutTuning.downforceGripGain * normalizedSpeed * normalizedSpeed) *
                                                        scale;
                    const float requiredAcceleration = speedMetersPerSecond * speedMetersPerSecond * curvaturePerMeter;
                    formulaGripMap = formulaGripMap && availableAcceleration + 0.01f >= requiredAcceleration;
                    if (availableAcceleration + 0.01f < requiredAcceleration) {
                        std::cout << "handling-map-grip-failure track="
                                  << aiCircuitProfile(layout).name
                                  << " corner=" << target.name
                                  << " phase=" << target.lapFraction + phaseOffset
                                  << " target_kph=" << target.speedKph
                                  << " available_mps2=" << availableAcceleration
                                  << " required_mps2=" << requiredAcceleration << "\n";
                    }
                    ++formulaGripChecks;
                }
            }
        }
        track_.rebuild(TrackLayoutId::Monza);
        const Kart3D& cameraKart = karts_[0];
        const Camera tcam = raceTcam(1.0f);
        const Vector3 cameraKartPosition = toWorld(cameraKart.pos, cameraKart.elevation);
        const Vec2 cameraPlanarOffset{tcam.position.x - cameraKartPosition.x,
                                      tcam.position.z - cameraKartPosition.z};
        const Vec2 cameraViewPlanar{tcam.target.x - tcam.position.x,
                                    tcam.target.z - tcam.position.z};
        const float speedVibrationTolerance = 0.012f * kTrackSimulationUnitsPerMeter * kRenderScale;
        const bool fixedTcam = std::abs(length(cameraPlanarOffset) -
                                        kTcamBackMeters * kTrackSimulationUnitsPerMeter * kRenderScale) <
                                    speedVibrationTolerance &&
                                std::abs((tcam.position.y - cameraKartPosition.y) -
                                         kTcamHeightMeters * kTrackSimulationUnitsPerMeter * kRenderScale) <
                                    speedVibrationTolerance &&
                                dot(normalize(cameraViewPlanar), fromAngle(cameraKart.heading)) > 0.999f &&
                                std::abs(tcam.fovy - kTcamFovDegrees) < 0.001f;
        const bool ok = controlledRoad && noBrakeConsequences && groundClear && stable && moving &&
                        inputContract && formulaCornering && formulaPerformance && formulaGrip &&
                        progressiveBraking && naturalCoast && namedCornerProof && smooth130rGeometry &&
                        formulaGearMap && formulaGripMap && formulaDynamicsMap && fixedTcam && specField;

        auto print = [](const AuditResult3D& r) {
            std::cout << r.name << "_score=" << r.score << " lap=" << r.lap << " avg=" << r.averageSpeed << " max=" << r.maxSpeed
                      << " contacts=" << r.contacts << " offroad_frames=" << r.offroadFrames << " max_offroad=" << r.maxOffroad
                      << " max_offroad_phase=" << r.maxOffroadPhase
                      << " max_drift_charge=" << r.maxDriftCharge
                      << " max_slip=" << r.maxSlip << " brake_drift_frames=" << r.brakeDriftFrames
                      << " brake_frames=" << r.brakeFrames << " powered_exit_frames=" << r.poweredExitFrames
                      << " min_ground_clearance=" << r.minGroundClearance << " progress_jumps=" << r.progressJumps
                      << " max_airtime=" << r.maxAirTime << " landings=" << r.landings
                      << " drift_frames=" << r.driftFrames << " boost_frames=" << r.boostFrames << " ";
        };
        std::cout << "handling-audit ";
        print(noBrake);
        print(brake);
        print(attack);
        std::cout << "controlled_road=" << controlledRoad << " no_brake_consequences=" << noBrakeConsequences
                  << " ground_clear=" << groundClear << " stable=" << stable << " moving=" << moving
                  << " measured_lap_s=" << measuredLapSeconds
                  << " formula_cornering=" << formulaCornering
                  << " terminal_kph=" << terminalSpeedKph
                  << " zero_to_100_s=" << zeroToOneHundredSeconds
                  << " zero_to_200_s=" << zeroToTwoHundredSeconds
                  << " mechanical_grip_g=" << mechanicalGripG
                  << " high_speed_grip_g=" << highSpeedGripG
                  << " yaw_effective_high_speed_grip_g=" << yawEffectiveHighSpeedGripG
                  << " named_braking_corners=" << namedBrakingCorners << "/" << monzaTurns.size()
                  << " lowest_named_corner_kph=" << lowestNamedCornerSpeedKph
                  << " formula_performance=" << formulaPerformance << " formula_grip=" << formulaGrip
                  << " progressive_braking=" << progressiveBraking;
        std::cout << " coast_3s_kph=" << coastEndKph[0] << "," << coastEndKph[1] << "," << coastEndKph[2]
                  << " aero_1s_loss_kph=" << aeroOnlyLossKph[0] << "," << aeroOnlyLossKph[1] << ","
                  << aeroOnlyLossKph[2] << " natural_coast=" << naturalCoast;
        for (const BrakingDistanceResult& result : brakingDistances) {
            std::cout << " brake_" << result.startKph << "_to_" << result.targetKph
                      << "_m=" << result.distanceMeters << " brake_s=" << result.seconds;
        }
        for (size_t i = 0; i < cornerSpecs.size(); ++i) {
            const auto printCorner = [&](const char* modeName, const CornerBenchmarkResult& result) {
                std::cout << " " << cornerSpecs[i].name << "_" << modeName
                          << "={entry:" << result.entryKph << ",min:" << result.minimumKph
                          << ",exit:" << result.exitKph << ",offroad_m:" << result.maxOffroadMeters
                          << ",contacts:" << result.contacts << ",min_gear:" << result.minimumGear << "}";
            };
            printCorner("flat", flatCorners[i]);
            printCorner("braked", brakedCorners[i]);
        }
        std::cout << " named_corner_proof=" << namedCornerProof
                  << " peak_130r_curvature_per_m=" << peak130rCurvaturePerMeter
                  << " smooth_130r_geometry=" << smooth130rGeometry
                  << " formula_gear_checks=" << formulaGearChecks << " formula_gear_map=" << formulaGearMap
                  << " formula_grip_checks=" << formulaGripChecks << " formula_grip_map=" << formulaGripMap
                  << " formula_dynamics_checks=" << formulaDynamicsChecks
                  << " formula_dynamics_map=" << formulaDynamicsMap
                  << " min_yaw_rate_margin=" << minimumYawRateMargin
                  << " max_corner_grip_scale=" << maximumCornerGripScale
                  << " fixed_tcam=" << fixedTcam
                  << " spec_field=" << specField
                  << " input_contract=" << inputContract
                  << "\n";
        return ok;
    }

    bool runRacecraftAudit(int mapIndex = 2) {
        selectMapForCapture(mapIndex);
        float auditProgress = 0.0f;
        float straightSeverity =
            std::numeric_limits<float>::max();
        for (int sample = 0; sample < 256; ++sample) {
            const float progress =
                track_.totalLength() *
                static_cast<float>(sample) / 256.0f;
            const float severity = std::max({
                std::abs(smoothedSignedCurvature(progress)),
                std::abs(smoothedSignedCurvature(
                    progress + 45.0f)),
                std::abs(smoothedSignedCurvature(
                    progress + 95.0f)),
                std::abs(smoothedSignedCurvature(
                    progress + 175.0f))});
            if (severity < straightSeverity) {
                straightSeverity = severity;
                auditProgress = progress;
            }
        }
        setupSectionTour(auditProgress / track_.totalLength(), 3);

        // Put one opponent in the player's tow so the audit exercises the
        // longitudinal collision constraint against a human-driven car too.
        Kart3D& player = karts_[0];
        Kart3D& challenger = karts_[1];
        const float auditUnitsPerMeter = isMetricCircuit(track_.layout()) ? kTrackSimulationUnitsPerMeter : 1.0f;
        const float challengerProgress = wrapDistance(player.progress - 28.0f, track_.totalLength());
        const TrackPoint3D challengerPoint = track_.sample(challengerProgress);
        challenger.pos = challengerPoint.pos + challengerPoint.normal * player.lane;
        challenger.heading = angleOf(challengerPoint.tangent);
        challenger.vel = challengerPoint.tangent * (length(player.vel) + 2.2f * auditUnitsPerMeter);
        challenger.nearest = track_.nearestIndex(challenger.pos);
        challenger.progress = challengerProgress;
        challenger.previousProgress = challenger.progress;
        challenger.lane = player.lane;
        challenger.elevation = bankedElevation(challengerPoint, challenger.lane);
        challenger.previousRenderPos = challenger.pos;
        challenger.previousRenderElevation = challenger.elevation;
        challenger.previousRenderHeading = challenger.heading;
        challenger.previousRenderProgress = challenger.progress;

        RacecraftAuditResult3D result;
        std::array<float, kKartCount> previousContact{};
        std::array<float, kKartCount> maxRoadViolationByKart{};
        std::array<int, kKartCount> roadViolationFramesByKart{};
        std::array<int, kKartCount> contactBeginningsByKart{};
        int maxRoadViolationKart = -1;
        float maxRoadViolationProgress = 0.0f;
        float maxRoadViolationSpeedKph = 0.0f;
        float maxRoadViolationHeadingError = 0.0f;
        bool maxRoadViolationVehicleContact = false;
        AiRaceIntent3D maxRoadViolationIntent =
            AiRaceIntent3D::None;
        float maxRoadViolationRaceOffsetMeters = 0.0f;
        float maxRoadViolationTargetLaneMeters = 0.0f;
        float maxRoadViolationPlannedLaneMeters = 0.0f;
        float maxRoadViolationThrottle = 0.0f;
        float maxRoadViolationBrake = 0.0f;
        for (int i = 0; i < kKartCount; ++i) {
            previousContact[static_cast<size_t>(i)] = karts_[static_cast<size_t>(i)].contactTimer;
        }

        constexpr int kAuditFrames = static_cast<int>(22.0f / kFixedDt);
        const float unitsPerMeter = auditUnitsPerMeter;
        for (int frame = 0; frame < kAuditFrames; ++frame) {
            updatePlayer(karts_[0], scriptedInput(), kFixedDt);
            for (int i = 1; i < activeKartCount(); ++i) {
                updateAi(karts_[static_cast<size_t>(i)], kFixedDt, i);
            }
            solveKartContacts();

            for (int i = 1; i < activeKartCount(); ++i) {
                const Kart3D& kart = karts_[static_cast<size_t>(i)];
                const float lineTargetErrorMeters =
                    std::abs(
                        kart.aiCommandLineTarget -
                        racingLaneForProgress(
                            kart, kart.aiCommandLineProgress)) /
                    unitsPerMeter;
                const bool cleanAirCanonicalTarget =
                    kart.aiRaceIntent ==
                        AiRaceIntent3D::None &&
                    !kart.aiProximityAvoidanceConstraint &&
                    std::abs(kart.aiRaceLaneOffset) <=
                        0.001f * unitsPerMeter;
                if (cleanAirCanonicalTarget) {
                    ++result.canonicalLineFrames;
                    result.offCanonicalLineTargetFrames +=
                        lineTargetErrorMeters > 0.001f
                            ? 1
                            : 0;
                    result.maximumLineTargetErrorMeters =
                        std::max(
                            result
                                .maximumLineTargetErrorMeters,
                            lineTargetErrorMeters);
                }
                result.collisionConstraintFrames +=
                    kart.aiCollisionBrakeConstraint ? 1 : 0;
                const float auditTopSpeed =
                    kart.tuning.maxForwardSpeed +
                    (kart.aiCommandDrsPlanActive
                         ? drsTopSpeedExtra()
                         : 0.0f);
                const bool terminalPlanNow =
                    plannedAiSpeed(
                        kart.aiCommandLineProgress,
                        kart.aiCommandDrsPlanActive) >=
                        auditTopSpeed * 0.99f &&
                    plannedAiSpeed(
                        kart.aiCommandLineProgress +
                            30.0f,
                        kart.aiCommandDrsPlanActive) >=
                        auditTopSpeed * 0.99f;
                if (terminalPlanNow &&
                    kart.aiCommandTargetSpeed >=
                        auditTopSpeed * 0.99f &&
                    !kart.aiCollisionBrakeConstraint &&
                    !kart.aiRoadRecoveryConstraint &&
                    roadEdgeViolation(
                        kart,
                        track_.sample(kart.progress)) <=
                        0.10f * unitsPerMeter) {
                    ++result.clearPhysicsFlatFrames;
                    result.minimumClearPhysicsFlatThrottle =
                        std::min(
                            result.minimumClearPhysicsFlatThrottle,
                            kart.aiCommandThrottle);
                    result.unnecessaryPhysicsFlatBrakeFrames +=
                        kart.aiCommandBrake > 0.005f ? 1 : 0;
                    result.unnecessaryPhysicsFlatLiftFrames +=
                        kart.aiCommandThrottle < 0.995f ? 1 : 0;
                }
                if (previousContact[static_cast<size_t>(i)] <= 0.001f && kart.contactTimer > 0.05f) {
                    ++result.contactBeginnings;
                    ++contactBeginningsByKart[static_cast<size_t>(i)];
                }
                previousContact[static_cast<size_t>(i)] = kart.contactTimer;
                const TrackPoint3D center = track_.sample(kart.progress);
                const float roadViolationMeters = roadEdgeViolation(kart, center) / unitsPerMeter;
                maxRoadViolationByKart[static_cast<size_t>(i)] =
                    std::max(maxRoadViolationByKart[static_cast<size_t>(i)], roadViolationMeters);
                roadViolationFramesByKart[static_cast<size_t>(i)] += roadViolationMeters > 2.6f ? 1 : 0;
                if (roadViolationMeters > result.maxRoadViolationMeters) {
                    result.maxRoadViolationMeters = roadViolationMeters;
                    maxRoadViolationKart = i;
                    maxRoadViolationProgress = kart.progress;
                    maxRoadViolationSpeedKph =
                        length(kart.vel) / unitsPerMeter * 3.6f;
                    maxRoadViolationHeadingError =
                        std::abs(wrapAngle(kart.heading - angleOf(center.tangent))) * RAD2DEG;
                    maxRoadViolationVehicleContact = kart.vehicleContact;
                    maxRoadViolationIntent =
                        kart.aiRaceIntent;
                    maxRoadViolationRaceOffsetMeters =
                        kart.aiRaceLaneOffset /
                        unitsPerMeter;
                    maxRoadViolationTargetLaneMeters =
                        kart.aiCommandLineTarget /
                        unitsPerMeter;
                    maxRoadViolationPlannedLaneMeters =
                        plannedAiLane(kart.progress) /
                        unitsPerMeter;
                    maxRoadViolationThrottle =
                        kart.aiCommandThrottle;
                    maxRoadViolationBrake =
                        kart.aiCommandBrake;
                }
            }
        }

        const int maxRoadViolationFrames =
            *std::max_element(roadViolationFramesByKart.begin(), roadViolationFramesByKart.end());
        const bool fullFieldRunoffControlled =
            activeKartCount() > 6 && result.maxRoadViolationMeters <= 6.0f &&
            maxRoadViolationFrames <= static_cast<int>(2.0f / kFixedDt);
        const bool controlled = result.contactBeginnings <= 30 &&
                                (result.maxRoadViolationMeters <= 2.6f ||
                                 fullFieldRunoffControlled);
        const bool canonicalLineCommitment =
            result.canonicalLineFrames >= 600 &&
            result.offCanonicalLineTargetFrames == 0 &&
            result.maximumLineTargetErrorMeters <=
                0.001f;
        const bool sampledFlatSequence = result.clearPhysicsFlatFrames >= 30;
        const bool observedFlatCommitment =
            sampledFlatSequence &&
            result.unnecessaryPhysicsFlatBrakeFrames <
                result.clearPhysicsFlatFrames / 100 &&
            result.unnecessaryPhysicsFlatLiftFrames <
                result.clearPhysicsFlatFrames / 15;
        const bool flatCommitment =
            track_.layout() != TrackLayoutId::Monza ||
            !sampledFlatSequence ||
            observedFlatCommitment;
        const bool ok =
            canonicalLineCommitment && controlled && flatCommitment;
        std::cout << "race-line-audit map=" << mapIndex
                  << " clear_flat_frames=" << result.clearPhysicsFlatFrames
                  << " unnecessary_flat_brakes="
                  << result.unnecessaryPhysicsFlatBrakeFrames
                  << " unnecessary_flat_lifts="
                  << result.unnecessaryPhysicsFlatLiftFrames
                  << " min_clear_flat_throttle="
                  << result.minimumClearPhysicsFlatThrottle
                  << " canonical_line_frames="
                  << result.canonicalLineFrames
                  << " off_canonical_targets="
                  << result.offCanonicalLineTargetFrames
                  << " max_line_target_error_m="
                  << result.maximumLineTargetErrorMeters
                  << " collision_constraint_frames="
                  << result.collisionConstraintFrames
                  << " contacts=" << result.contactBeginnings
                  << " road_violation_m=" << result.maxRoadViolationMeters
                  << " road_violation_kart=" << maxRoadViolationKart
                  << " road_violation_phase=" << maxRoadViolationProgress / track_.totalLength()
                  << " road_violation_kph=" << maxRoadViolationSpeedKph
                  << " road_violation_heading_deg=" << maxRoadViolationHeadingError
                  << " road_violation_contact=" << maxRoadViolationVehicleContact
                  << " road_violation_intent="
                  << static_cast<int>(
                         maxRoadViolationIntent)
                  << " road_violation_offset_m="
                  << maxRoadViolationRaceOffsetMeters
                  << " road_violation_target_lane_m="
                  << maxRoadViolationTargetLaneMeters
                  << " road_violation_planned_lane_m="
                  << maxRoadViolationPlannedLaneMeters
                  << " road_violation_throttle="
                  << maxRoadViolationThrottle
                  << " road_violation_brake="
                  << maxRoadViolationBrake
                  << " road_violation_frames=" << maxRoadViolationFrames
                  << " controlled=" << controlled
                  << " canonical_line_commitment="
                  << canonicalLineCommitment
                  << " flat_commitment=" << flatCommitment
                  << " per_kart_road=";
        for (int i = 1; i < kKartCount; ++i) {
            std::cout << (i == 1 ? "" : ",") << i << ":"
                      << maxRoadViolationByKart[static_cast<size_t>(i)] << "/"
                      << roadViolationFramesByKart[static_cast<size_t>(i)] << "/"
                      << contactBeginningsByKart[static_cast<size_t>(i)];
        }
        std::cout << " ok=" << ok << "\n";
        return ok;
    }

    bool runAllTrackRaceLineAudit() {
        bool ok = true;
        for (int mapIndex = 0;
             mapIndex < static_cast<int>(kMaps.size());
             ++mapIndex) {
            ok = runRacecraftAudit(mapIndex) && ok;
        }
        return ok;
    }

    bool runMonzaRaceStartFlatAudit() {
        selectMapForCapture(3);
        startRace();

        int flatFrames = 0;
        int brakeFrames = 0;
        int collisionBrakeFrames = 0;
        int liftFrames = 0;
        int collisionLiftFrames = 0;
        int launchFrames = 0;
        int launchBrakeFrames = 0;
        int launchLiftFrames = 0;
        int launchCollisionBrakeFrames = 0;
        int launchContactBeginnings = 0;
        int approachPassIntentFrames = 0;
        int contactBeginnings = 0;
        float minimumThrottle = 1.0f;
        float maximumBrake = 0.0f;
        float maximumPreLineLaneTargetErrorMeters =
            0.0f;
        float firstLaunchBrakeDistanceMeters = 0.0f;
        float firstLaunchBrakeGhostSeconds = 0.0f;
        float firstLaunchBrakeLaneMeters = 0.0f;
        float firstLaunchBrakeTargetLaneMeters = 0.0f;
        float firstLaunchBrakeSpeedKph = 0.0f;
        bool capturedFirstLaunchBrake = false;
        float maximumRoadViolationMeters = 0.0f;
        std::array<float, kKartCount> previousContact{};
        std::array<float, kKartCount>
            firstApproachBrakeDistanceMeters{};
        std::array<float, kKartCount>
            firstApproachBrakeSpeedKph{};
        std::array<float, kKartCount>
            firstApproachBrakeTargetKph{};
        std::array<float, kKartCount>
            firstApproachBrakeLaneMeters{};
        std::array<float, kKartCount>
            firstApproachBrakeTargetLaneMeters{};
        std::array<float, kKartCount>
            firstApproachBrakeAheadMeters{};
        std::array<int, kKartCount>
            firstApproachBrakeAheadIndex{};
        std::array<int, kKartCount>
            firstApproachBrakeIntent{};
        std::array<int, kKartCount>
            firstApproachCollisionTarget{};
        std::array<int, kKartCount>
            firstApproachRaceTarget{};
        std::array<float, kKartCount>
            firstApproachDesiredOffsetMeters{};
        firstApproachBrakeAheadIndex.fill(-1);
        firstApproachCollisionTarget.fill(-1);
        firstApproachRaceTarget.fill(-1);
        std::array<int, kKartCount>
            approachBrakeFrames{};
        std::array<int, kKartCount>
            approachCollisionBrakeFrames{};
        std::array<int, kKartCount>
            approachRecoveryBrakeFrames{};
        firstApproachBrakeDistanceMeters.fill(
            std::numeric_limits<float>::max());
        for (int index = 0;
             index < activeKartCount(); ++index) {
            previousContact[static_cast<size_t>(index)] =
                karts_[static_cast<size_t>(index)].contactTimer;
        }
        constexpr int kAuditFrames =
            static_cast<int>(30.0f / kFixedDt);
        for (int frame = 0; frame < kAuditFrames; ++frame) {
            update(kFixedDt, scriptedInput(), true);
            if (raceFlow_ &&
                raceFlow_->phase() !=
                    ArcadeRacePhase::Racing) {
                continue;
            }
            for (int index = 1;
                 index < activeKartCount(); ++index) {
                const Kart3D& kart =
                    karts_[static_cast<size_t>(index)];
                const bool contactBegan =
                    previousContact[
                        static_cast<size_t>(index)] <=
                        0.001f &&
                    kart.contactTimer > 0.05f;
                if (contactBegan) {
                    ++contactBeginnings;
                }
                previousContact[static_cast<size_t>(index)] =
                    kart.contactTimer;
                const float startLineDistanceMeters =
                    static_cast<float>(
                        raceFlow_->racer(
                            static_cast<size_t>(index))
                            .continuousTrackProgress) *
                    track_.totalLength();
                if (startLineDistanceMeters >= 0.0f &&
                    startLineDistanceMeters <
                        900.0f &&
                    kart.aiRaceIntent ==
                        AiRaceIntent3D::Pass) {
                    ++approachPassIntentFrames;
                }
                if (startLineDistanceMeters >= -100.0f &&
                    startLineDistanceMeters <
                        900.0f &&
                    kart.aiCommandTargetSpeed > 0.0f &&
                    kart.aiCommandBrake > 0.005f) {
                    ++approachBrakeFrames[
                        static_cast<size_t>(index)];
                    approachCollisionBrakeFrames[
                        static_cast<size_t>(index)] +=
                        kart.aiCollisionBrakeConstraint
                            ? 1
                            : 0;
                    approachRecoveryBrakeFrames[
                        static_cast<size_t>(index)] +=
                        kart.aiRoadRecoveryConstraint
                            ? 1
                            : 0;
                    if (firstApproachBrakeDistanceMeters[
                            static_cast<size_t>(index)] ==
                        std::numeric_limits<float>::max()) {
                        firstApproachBrakeDistanceMeters[
                            static_cast<size_t>(index)] =
                            startLineDistanceMeters;
                        firstApproachBrakeSpeedKph[
                            static_cast<size_t>(index)] =
                            length(kart.vel) *
                            speedKphPerSimulationUnit(
                                track_.layout());
                        firstApproachBrakeTargetKph[
                            static_cast<size_t>(index)] =
                            kart.aiCommandTargetSpeed *
                            speedKphPerSimulationUnit(
                                track_.layout());
                        firstApproachBrakeLaneMeters[
                            static_cast<size_t>(index)] =
                            kart.lane /
                            kTrackSimulationUnitsPerMeter;
                        firstApproachBrakeTargetLaneMeters[
                            static_cast<size_t>(index)] =
                            kart.aiCommandLineTarget /
                            kTrackSimulationUnitsPerMeter;
                        firstApproachBrakeIntent[
                            static_cast<size_t>(index)] =
                            static_cast<int>(
                                kart.aiRaceIntent);
                        firstApproachCollisionTarget[
                            static_cast<size_t>(index)] =
                            kart.aiCollisionTargetIndex;
                        firstApproachRaceTarget[
                            static_cast<size_t>(index)] =
                            kart.aiRaceTargetIndex;
                        firstApproachDesiredOffsetMeters[
                            static_cast<size_t>(index)] =
                            kart.aiRaceDesiredLaneOffset /
                            kTrackSimulationUnitsPerMeter;
                        float closestAhead =
                            std::numeric_limits<float>::max();
                        for (int otherIndex = 0;
                             otherIndex <
                                 activeKartCount();
                             ++otherIndex) {
                            if (otherIndex == index) {
                                continue;
                            }
                            const Kart3D& other =
                                karts_[static_cast<size_t>(
                                    otherIndex)];
                            const float ahead =
                                progressAhead(
                                    kart.progress,
                                    other.progress,
                                    track_.totalLength());
                            if (ahead < closestAhead) {
                                closestAhead = ahead;
                                firstApproachBrakeAheadIndex[
                                    static_cast<size_t>(
                                        index)] =
                                    otherIndex;
                            }
                        }
                        firstApproachBrakeAheadMeters[
                            static_cast<size_t>(index)] =
                            closestAhead;
                    }
                }
                if (startLineDistanceMeters < 60.0f &&
                    contactBegan) {
                    ++launchContactBeginnings;
                }
                if (startLineDistanceMeters < 50.0f &&
                    kart.aiCommandTargetSpeed > 0.0f) {
                    ++launchFrames;
                    if (!capturedFirstLaunchBrake &&
                        kart.aiCommandBrake > 0.005f) {
                        capturedFirstLaunchBrake = true;
                        firstLaunchBrakeDistanceMeters =
                            startLineDistanceMeters;
                        firstLaunchBrakeGhostSeconds =
                            kart.ghostTimer;
                        firstLaunchBrakeLaneMeters =
                            kart.lane /
                            kTrackSimulationUnitsPerMeter;
                        firstLaunchBrakeTargetLaneMeters =
                            kart.aiCommandLineTarget /
                            kTrackSimulationUnitsPerMeter;
                        firstLaunchBrakeSpeedKph =
                            length(kart.vel) *
                            speedKphPerSimulationUnit(
                                track_.layout());
                    }
                    launchBrakeFrames +=
                        kart.aiCommandBrake > 0.005f
                            ? 1
                            : 0;
                    launchLiftFrames +=
                        kart.aiCommandThrottle < 0.995f
                            ? 1
                            : 0;
                    launchCollisionBrakeFrames +=
                        kart.aiCollisionBrakeConstraint &&
                                kart.aiCommandBrake > 0.005f
                            ? 1
                            : 0;
                    if (startLineDistanceMeters <
                        -120.0f) {
                        maximumPreLineLaneTargetErrorMeters =
                            std::max(
                                maximumPreLineLaneTargetErrorMeters,
                                std::abs(
                                    kart.aiCommandLineTarget -
                                    kart.aiGridLane) /
                                    kTrackSimulationUnitsPerMeter);
                    }
                }
                const TrackPoint3D center =
                    track_.sample(kart.progress);
                maximumRoadViolationMeters =
                    std::max(
                        maximumRoadViolationMeters,
                        roadEdgeViolation(kart, center) /
                            kTrackSimulationUnitsPerMeter);
                const float auditTopSpeed =
                    kart.tuning.maxForwardSpeed +
                    (kart.aiCommandDrsPlanActive
                         ? drsTopSpeedExtra()
                         : 0.0f);
                const bool terminalPlanNow =
                    plannedAiSpeed(
                        kart.aiCommandLineProgress,
                        kart.aiCommandDrsPlanActive) >=
                        auditTopSpeed * 0.99f &&
                    plannedAiSpeed(
                        kart.aiCommandLineProgress +
                            30.0f,
                        kart.aiCommandDrsPlanActive) >=
                        auditTopSpeed * 0.99f;
                if (!terminalPlanNow ||
                    kart.aiCommandTargetSpeed <= 0.0f ||
                    kart.aiCommandTargetSpeed <
                        auditTopSpeed * 0.99f ||
                    kart.aiCollisionBrakeConstraint ||
                    kart.aiRoadRecoveryConstraint ||
                    roadEdgeViolation(kart, center) >
                        0.10f *
                            kTrackSimulationUnitsPerMeter) {
                    continue;
                }
                ++flatFrames;
                minimumThrottle =
                    std::min(minimumThrottle,
                             kart.aiCommandThrottle);
                maximumBrake =
                    std::max(maximumBrake,
                             kart.aiCommandBrake);
                if (kart.aiCommandThrottle < 0.995f) {
                    ++liftFrames;
                    collisionLiftFrames +=
                        kart.aiCollisionBrakeConstraint ? 1 : 0;
                }
                if (kart.aiCommandBrake > 0.005f) {
                    ++brakeFrames;
                    collisionBrakeFrames +=
                        kart.aiCollisionBrakeConstraint ? 1 : 0;
                }
            }
        }

        const bool ok =
            flatFrames >= 600 &&
            brakeFrames < flatFrames / 66 &&
            liftFrames < flatFrames / 15 &&
            launchFrames >= 500 &&
            launchBrakeFrames <
                launchFrames / 20 &&
            launchLiftFrames >= 120 &&
            launchLiftFrames < launchFrames / 2 &&
            launchCollisionBrakeFrames ==
                launchBrakeFrames &&
            approachPassIntentFrames >= 120 &&
            launchContactBeginnings == 0 &&
            maximumPreLineLaneTargetErrorMeters <
                0.01f &&
            contactBeginnings <= 20 &&
            maximumRoadViolationMeters <= 5.0f;
        std::cout
            << "monza-race-start-flat-audit"
            << " flat_frames=" << flatFrames
            << " brake_frames=" << brakeFrames
            << " collision_brake_frames="
            << collisionBrakeFrames
            << " lift_frames=" << liftFrames
            << " collision_lift_frames="
            << collisionLiftFrames
            << " launch_frames=" << launchFrames
            << " launch_brake_frames="
            << launchBrakeFrames
            << " launch_lift_frames="
            << launchLiftFrames
            << " launch_collision_brake_frames="
            << launchCollisionBrakeFrames
            << " approach_pass_frames="
            << approachPassIntentFrames
            << " launch_contacts="
            << launchContactBeginnings
            << " preline_lane_error_m="
            << maximumPreLineLaneTargetErrorMeters
            << " first_launch_brake_distance_m="
            << firstLaunchBrakeDistanceMeters
            << " first_launch_brake_ghost_s="
            << firstLaunchBrakeGhostSeconds
            << " first_launch_brake_lane_m="
            << firstLaunchBrakeLaneMeters
            << " first_launch_brake_target_lane_m="
            << firstLaunchBrakeTargetLaneMeters
            << " first_launch_brake_speed_kph="
            << firstLaunchBrakeSpeedKph
            << " min_throttle=" << minimumThrottle
            << " max_brake=" << maximumBrake
            << " contacts=" << contactBeginnings
            << " road_violation_m="
            << maximumRoadViolationMeters
            << " approach_brakes=";
        for (int index = 1;
             index < activeKartCount(); ++index) {
            const float firstDistance =
                firstApproachBrakeDistanceMeters[
                    static_cast<size_t>(index)];
            std::cout
                << (index == 1 ? "" : ",")
                << index << ":"
                << (std::isfinite(firstDistance) &&
                            firstDistance <
                                std::numeric_limits<float>::max()
                        ? firstDistance
                        : -1.0f)
                << "/"
                << approachBrakeFrames[
                       static_cast<size_t>(index)]
                << "/"
                << approachCollisionBrakeFrames[
                       static_cast<size_t>(index)]
                << "/"
                << approachRecoveryBrakeFrames[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachBrakeSpeedKph[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachBrakeTargetKph[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachBrakeLaneMeters[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachBrakeTargetLaneMeters[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachBrakeAheadMeters[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachBrakeAheadIndex[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachBrakeIntent[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachCollisionTarget[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachRaceTarget[
                       static_cast<size_t>(index)]
                << "/"
                << firstApproachDesiredOffsetMeters[
                       static_cast<size_t>(index)];
        }
        std::cout
            << " ok=" << ok << "\n";
        return ok;
    }

    bool runMonzaCompetitionAudit(int auditLaps = 2) {
        const auto lapOption = std::find(
            kLapOptions.begin(), kLapOptions.end(),
            auditLaps);
        if (lapOption == kLapOptions.end() ||
            auditLaps == kInfiniteLaps) {
            std::cerr
                << "monza-competition-audit invalid_laps="
                << auditLaps << "\n";
            return false;
        }
        selectedLapOption_ = static_cast<int>(
            std::distance(kLapOptions.begin(), lapOption));
        selectMapForCapture(3);
        startRace();
        raceFlow_->beginRace();

        std::array<float, kKartCount> previousContact{};
        for (int index = 0; index < kKartCount; ++index) {
            previousContact[static_cast<size_t>(index)] =
                karts_[static_cast<size_t>(index)]
                    .contactTimer;
        }
        const auto rankOf = [&](int kartIndex) {
            const ArcadeRacerRaceState& racer =
                raceFlow_->racer(
                    static_cast<size_t>(kartIndex));
            int rank = 1;
            for (int otherIndex = 0;
                 otherIndex < kKartCount; ++otherIndex) {
                if (otherIndex == kartIndex) {
                    continue;
                }
                const ArcadeRacerRaceState& other =
                    raceFlow_->racer(
                        static_cast<size_t>(otherIndex));
                const bool otherAhead =
                    other.finished != racer.finished
                        ? other.finished
                        : (racer.finished
                               ? other.finishOrder <
                                     racer.finishOrder
                               : other.continuousTrackProgress >
                                     racer.continuousTrackProgress +
                                         0.000001);
                if (otherAhead) {
                    ++rank;
                }
            }
            return rank;
        };

        const int initialPlayerRank = rankOf(0);
        int bestPlayerRank = initialPlayerRank;
        int previousPlayerRank = initialPlayerRank;
        int playerPasses = 0;
        int contactBeginnings = 0;
        int playerContactBeginnings = 0;
        float firstPlayerContactPhase = -1.0f;
        float firstPlayerContactSpeedBeforeKph = 0.0f;
        float firstPlayerContactSpeedAfterKph = 0.0f;
        float previousPlayerSpeedKph =
            length(karts_[0].vel) *
            speedKphPerSimulationUnit(track_.layout());
        int passIntentFrames = 0;
        int defendIntentFrames = 0;
        int collisionConstraintFrames = 0;
        int proximityAvoidanceFrames = 0;
        int playerAvoidanceFrames = 0;
        int drsAvailableFrames = 0;
        int drsActiveFrames = 0;
        std::array<int, kKartCount>
            passIntentFramesByKart{};
        std::array<int, kKartCount>
            drsActiveFramesByKart{};
        std::array<int, kKartCount>
            drsAvailableFramesByKart{};
        std::array<float, kKartCount>
            maximumDrsSpeedKphByKart{};
        std::array<float, kKartCount>
            maximumClosedSpeedKphByKart{};
        std::array<float, kKartCount>
            maximumRaceOffsetByKart{};
        std::array<float, kKartCount>
            maximumRoadViolationByKart{};
        float maximumRoadViolationMeters = 0.0f;
        int maximumRoadViolationKart = -1;
        float maximumRoadViolationPhase = 0.0f;
        float maximumRoadViolationLaneMeters = 0.0f;
        float maximumRoadViolationTargetLaneMeters = 0.0f;
        float maximumRoadViolationRaceOffsetMeters = 0.0f;
        AiRaceIntent3D maximumRoadViolationIntent =
            AiRaceIntent3D::None;
        float maximumRoadViolationSpeedKph = 0.0f;
        bool maximumRoadViolationVehicleContact = false;
        float maximumRoadViolationHeadingErrorDegrees = 0.0f;
        float maximumRoadViolationSteer = 0.0f;
        float maximumRoadViolationThrottle = 0.0f;
        float maximumRoadViolationBrake = 0.0f;
        bool maximumRoadViolationCollisionConstraint =
            false;
        float maximumOverlap = 0.0f;
        float maximumContactImpulse = 0.0f;
        float elapsedSeconds = 0.0f;
        bool finished = false;
        const int maximumFrames = static_cast<int>(
            (120.0f * static_cast<float>(auditLaps) +
             120.0f) /
            kFixedDt);
        for (int frame = 0;
             frame < maximumFrames; ++frame) {
            for (int index = 0;
                 index < activeKartCount(); ++index) {
                updateAi(
                    karts_[static_cast<size_t>(index)],
                    kFixedDt, index, true);
            }
            applyMonzaSlipstream(kFixedDt);
            solveKartContacts();
            const auto raceInputs =
                currentRaceInputs();
            raceFlow_->update(kFixedDt, raceInputs);
            updateDrsDetectionLine();
            for (int index = 0;
                 index < activeKartCount(); ++index) {
                karts_[static_cast<size_t>(index)].lap =
                    static_cast<int>(
                        raceFlow_->racer(
                            static_cast<size_t>(index))
                            .completedLaps);
            }
            maximumOverlap =
                std::max(maximumOverlap,
                         maxKartOverlap());
            elapsedSeconds =
                static_cast<float>(frame + 1) *
                kFixedDt;

            for (int index = 0;
                 index < activeKartCount(); ++index) {
                const Kart3D& kart =
                    karts_[static_cast<size_t>(index)];
                if (previousContact[
                        static_cast<size_t>(index)] <=
                        0.001f &&
                    kart.contactTimer > 0.05f) {
                    ++contactBeginnings;
                    playerContactBeginnings +=
                        index == 0 ? 1 : 0;
                    if (index == 0 &&
                        firstPlayerContactPhase <
                            0.0f) {
                        firstPlayerContactPhase =
                            kart.progress /
                            track_.totalLength();
                        firstPlayerContactSpeedBeforeKph =
                            previousPlayerSpeedKph;
                        firstPlayerContactSpeedAfterKph =
                            length(kart.vel) *
                            speedKphPerSimulationUnit(
                                track_.layout());
                    }
                }
                previousContact[
                    static_cast<size_t>(index)] =
                    kart.contactTimer;
                const TrackPoint3D center =
                    track_.sample(kart.progress);
                const float roadViolationMeters =
                    roadEdgeViolation(kart, center) /
                    kTrackSimulationUnitsPerMeter;
                maximumRoadViolationByKart[
                    static_cast<size_t>(index)] =
                    std::max(
                        maximumRoadViolationByKart[
                            static_cast<size_t>(index)],
                        roadViolationMeters);
                if (roadViolationMeters >
                    maximumRoadViolationMeters) {
                    maximumRoadViolationMeters =
                        roadViolationMeters;
                    maximumRoadViolationKart = index;
                    maximumRoadViolationPhase =
                        kart.progress /
                        track_.totalLength();
                    maximumRoadViolationLaneMeters =
                        kart.lane /
                        kTrackSimulationUnitsPerMeter;
                    maximumRoadViolationTargetLaneMeters =
                        kart.aiCommandLineTarget /
                        kTrackSimulationUnitsPerMeter;
                    maximumRoadViolationRaceOffsetMeters =
                        kart.aiRaceLaneOffset /
                        kTrackSimulationUnitsPerMeter;
                    maximumRoadViolationIntent =
                        kart.aiRaceIntent;
                    maximumRoadViolationSpeedKph =
                        length(kart.vel) *
                        speedKphPerSimulationUnit(
                            track_.layout());
                    maximumRoadViolationVehicleContact =
                        kart.vehicleContact;
                    maximumRoadViolationHeadingErrorDegrees =
                        wrapAngle(
                            angleOf(center.tangent) -
                            kart.heading) *
                        RAD2DEG;
                    maximumRoadViolationSteer =
                        kart.aiCommandSteer;
                    maximumRoadViolationThrottle =
                        kart.aiCommandThrottle;
                    maximumRoadViolationBrake =
                        kart.aiCommandBrake;
                    maximumRoadViolationCollisionConstraint =
                        kart.aiCollisionBrakeConstraint;
                }
                maximumContactImpulse =
                    std::max(maximumContactImpulse,
                             kart.contactImpulse);
                passIntentFrames +=
                    kart.aiRaceIntent ==
                            AiRaceIntent3D::Pass
                        ? 1
                        : 0;
                passIntentFramesByKart[
                    static_cast<size_t>(index)] +=
                    kart.aiRaceIntent ==
                            AiRaceIntent3D::Pass
                        ? 1
                        : 0;
                maximumRaceOffsetByKart[
                    static_cast<size_t>(index)] =
                    std::max(
                        maximumRaceOffsetByKart[
                            static_cast<size_t>(index)],
                        std::abs(
                            kart.aiRaceLaneOffset) /
                            kTrackSimulationUnitsPerMeter);
                defendIntentFrames +=
                    kart.aiRaceIntent ==
                            AiRaceIntent3D::Defend
                        ? 1
                        : 0;
                collisionConstraintFrames +=
                    kart.aiCollisionBrakeConstraint ? 1
                                                    : 0;
                proximityAvoidanceFrames +=
                    kart.aiProximityAvoidanceConstraint
                        ? 1
                        : 0;
                playerAvoidanceFrames +=
                    kart.aiProximityAvoidanceConstraint &&
                            kart.aiProximityAvoidanceTargetIndex ==
                                0 &&
                            index != 0
                        ? 1
                        : 0;
                drsAvailableFrames +=
                    kart.drsAvailable ? 1 : 0;
                drsAvailableFramesByKart[
                    static_cast<size_t>(index)] +=
                    kart.drsAvailable ? 1 : 0;
                drsActiveFrames +=
                    kart.drsActive ? 1 : 0;
                drsActiveFramesByKart[
                    static_cast<size_t>(index)] +=
                    kart.drsActive ? 1 : 0;
                const float speedKph =
                    length(kart.vel) *
                    speedKphPerSimulationUnit(
                        track_.layout());
                std::array<float, kKartCount>&
                    speedPeaks =
                        kart.drsActive
                            ? maximumDrsSpeedKphByKart
                            : maximumClosedSpeedKphByKart;
                speedPeaks[
                    static_cast<size_t>(index)] =
                    std::max(
                        speedPeaks[
                            static_cast<size_t>(index)],
                        speedKph);
            }
            previousPlayerSpeedKph =
                length(karts_[0].vel) *
                speedKphPerSimulationUnit(
                    track_.layout());

            const int playerRank = rankOf(0);
            if (playerRank < previousPlayerRank) {
                playerPasses +=
                    previousPlayerRank - playerRank;
            }
            previousPlayerRank = playerRank;
            bestPlayerRank =
                std::min(bestPlayerRank, playerRank);

            finished = raceFlow_->racer(0).finished;
            if (finished) {
                break;
            }
        }

        const int finalPlayerRank = rankOf(0);
        const uint32_t playerFinishPosition =
            raceFlow_->racer(0).finishOrder;
        int recoveryResets = 0;
        int slowLaunches = 0;
        int normalLaunches = 0;
        for (const Kart3D& kart : karts_) {
            recoveryResets += kart.aiRecoveryResetCount;
        }
        for (int index = 1;
             index < activeKartCount(); ++index) {
            if (karts_[static_cast<size_t>(index)]
                    .aiLaunchDuration > 0.0f) {
                ++slowLaunches;
            } else {
                ++normalLaunches;
            }
        }
        int winnerIndex = 0;
        for (int index = 1; index < kKartCount;
             ++index) {
            if (raceScore(
                    karts_[static_cast<size_t>(index)]) >
                raceScore(karts_[static_cast<size_t>(
                    winnerIndex)])) {
                winnerIndex = index;
            }
        }
        const bool competitive =
            initialPlayerRank == kKartCount &&
            elapsedSeconds <=
                90.0f * static_cast<float>(auditLaps);
        const bool playerContactControlled =
            playerContactBeginnings <= auditLaps &&
            (firstPlayerContactPhase < 0.0f ||
             firstPlayerContactSpeedAfterKph >=
                 firstPlayerContactSpeedBeforeKph *
                     0.985f);
        const bool controlled =
            contactBeginnings <=
                // Pace variation creates more harmless wheel-to-wheel
                // touches; the overlap and reset limits below remain the
                // authoritative safety constraints.
                24 * auditLaps &&
            maximumRoadViolationMeters <=
                kMetricCurbWidthMeters + 0.08f &&
            maximumOverlap <= 0.15f &&
            playerContactControlled &&
            recoveryResets == 0;
        const bool racecraftObserved =
            passIntentFrames >= 120 &&
            defendIntentFrames >= 30 &&
            drsActiveFrames >= 120 &&
            proximityAvoidanceFrames >= 30 &&
            playerAvoidanceFrames >= 1;
        int eligibleAiCars = 0;
        int activeDrsAiCars = 0;
        bool drsSpeedBenefitObserved = false;
        for (int index = 1;
             index < activeKartCount(); ++index) {
            if (drsAvailableFramesByKart[
                    static_cast<size_t>(index)] >=
                120) {
                ++eligibleAiCars;
                activeDrsAiCars +=
                    drsActiveFramesByKart[
                        static_cast<size_t>(index)] >=
                            60
                        ? 1
                        : 0;
            }
            const float baseTopSpeedKph =
                karts_[static_cast<size_t>(index)]
                    .tuning.maxForwardSpeed *
                speedKphPerSimulationUnit(
                    track_.layout());
            drsSpeedBenefitObserved =
                drsSpeedBenefitObserved ||
                maximumDrsSpeedKphByKart[
                    static_cast<size_t>(index)] >=
                    baseTopSpeedKph + 20.0f;
        }
        const bool aiDrsObserved =
            eligibleAiCars > 0 &&
            activeDrsAiCars == eligibleAiCars &&
            drsSpeedBenefitObserved;
        const bool launchProfilesObserved =
            slowLaunches > 0 &&
            normalLaunches > 0;
        const bool ok = finished && competitive &&
                        controlled && racecraftObserved &&
                        launchProfilesObserved &&
                        aiDrsObserved;
        std::cout
            << "monza-competition-audit"
            << " laps=" << auditLaps
            << " seconds=" << elapsedSeconds
            << " initial_player_pos="
            << initialPlayerRank
            << " best_player_pos=" << bestPlayerRank
            << " final_player_pos="
            << finalPlayerRank
            << " player_finish_pos="
            << playerFinishPosition
            << " player_passes=" << playerPasses
            << " recovery_resets="
            << recoveryResets
            << " winner=" << winnerIndex
            << " contacts=" << contactBeginnings
            << " player_contacts="
            << playerContactBeginnings
            << " player_contact_controlled="
            << playerContactControlled
            << " first_player_contact_phase="
            << firstPlayerContactPhase
            << " first_player_contact_kph="
            << firstPlayerContactSpeedBeforeKph
            << "->"
            << firstPlayerContactSpeedAfterKph
            << " road_violation_m="
            << maximumRoadViolationMeters
            << " road_violation_kart="
            << maximumRoadViolationKart
            << " road_violation_phase="
            << maximumRoadViolationPhase
            << " road_violation_lane_m="
            << maximumRoadViolationLaneMeters
            << " road_violation_target_lane_m="
            << maximumRoadViolationTargetLaneMeters
            << " road_violation_offset_m="
            << maximumRoadViolationRaceOffsetMeters
            << " road_violation_intent="
            << static_cast<int>(
                   maximumRoadViolationIntent)
            << " road_violation_kph="
            << maximumRoadViolationSpeedKph
            << " road_violation_vehicle_contact="
            << maximumRoadViolationVehicleContact
            << " road_violation_heading_error_deg="
            << maximumRoadViolationHeadingErrorDegrees
            << " road_violation_steer="
            << maximumRoadViolationSteer
            << " road_violation_throttle="
            << maximumRoadViolationThrottle
            << " road_violation_brake="
            << maximumRoadViolationBrake
            << " road_violation_collision_constraint="
            << maximumRoadViolationCollisionConstraint
            << " max_overlap=" << maximumOverlap
            << " max_contact_impulse="
            << maximumContactImpulse
            << " pass_intent_frames="
            << passIntentFrames
            << " defend_intent_frames="
            << defendIntentFrames
            << " collision_constraint_frames="
            << collisionConstraintFrames
            << " proximity_avoidance_frames="
            << proximityAvoidanceFrames
            << " player_avoidance_frames="
            << playerAvoidanceFrames
            << " drs_available_frames="
            << drsAvailableFrames
            << " drs_active_frames="
            << drsActiveFrames
            << " slow_launches="
            << slowLaunches
            << " normal_launches="
            << normalLaunches
            << " eligible_ai_drs="
            << eligibleAiCars
            << " active_ai_drs="
            << activeDrsAiCars
            << " drs_speed_benefit="
            << drsSpeedBenefitObserved
            << " competitive=" << competitive
            << " controlled=" << controlled
            << " racecraft=" << racecraftObserved
            << " finished=" << finished
            << " scores=";
        for (int index = 0; index < kKartCount;
             ++index) {
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << raceScore(karts_[static_cast<size_t>(
                       index)])
                << "/"
                << karts_[static_cast<size_t>(index)]
                       .lane /
                       kTrackSimulationUnitsPerMeter;
        }
        std::cout << " pass_by_kart=";
        for (int index = 0; index < kKartCount;
             ++index) {
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << passIntentFramesByKart[
                       static_cast<size_t>(index)]
                << "/"
                << maximumRaceOffsetByKart[
                       static_cast<size_t>(index)];
        }
        std::cout << " drs_by_kart=";
        for (int index = 0; index < kKartCount;
             ++index) {
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << drsActiveFramesByKart[
                       static_cast<size_t>(index)];
        }
        std::cout << " drs_available_by_kart=";
        for (int index = 0;
             index < kKartCount; ++index) {
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << drsAvailableFramesByKart[
                       static_cast<size_t>(index)];
        }
        std::cout << " launch_by_kart=";
        for (int index = 0;
             index < kKartCount; ++index) {
            const Kart3D& kart =
                karts_[static_cast<size_t>(index)];
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << kart.aiLaunchThrottleScale
                << "/"
                << kart.aiLaunchDuration;
        }
        std::cout << " speed_closed_drs_by_kart=";
        for (int index = 0;
             index < kKartCount; ++index) {
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << maximumClosedSpeedKphByKart[
                       static_cast<size_t>(index)]
                << "/"
                << maximumDrsSpeedKphByKart[
                       static_cast<size_t>(index)];
        }
        std::cout << " resets=";
        for (int index = 0; index < kKartCount;
             ++index) {
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << karts_[static_cast<size_t>(index)]
                       .aiRecoveryResetCount;
        }
        std::cout << " road_by_kart=";
        for (int index = 0; index < kKartCount;
             ++index) {
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << maximumRoadViolationByKart[
                       static_cast<size_t>(index)];
        }
        std::cout << " finish_by_kart=";
        for (int index = 0; index < kKartCount;
             ++index) {
            const ArcadeRacerRaceState& racer =
                raceFlow_->racer(
                    static_cast<size_t>(index));
            std::cout
                << (index == 0 ? "" : ",")
                << index << ":"
                << racer.finishOrder << "/"
                << racer.finishTimeSeconds;
        }
        std::cout << " ok=" << ok << "\n";
        return ok;
    }

    bool runRaceAudit() {
        startRace();
        RaceAuditResult3D result;
        std::array<float, kKartCount> previousScores{};
        std::array<float, kKartCount> maxRoadViolationByKart{};
        std::array<int, kKartCount> roadViolationFramesByKart{};
        double lapStartProgress = 0.0;
        bool lapClockStarted = false;
        for (int i = 0; i < kKartCount; ++i) {
            previousScores[static_cast<size_t>(i)] = raceScore(karts_[static_cast<size_t>(i)]);
        }

        constexpr int frames = static_cast<int>(80.0f / kFixedDt);
        for (int frame = 0; frame < frames; ++frame) {
            std::array<float, kKartCount> beforeContact{};
            std::array<float, kKartCount> beforeProgress{};
            for (int i = 0; i < kKartCount; ++i) {
                beforeContact[static_cast<size_t>(i)] = karts_[static_cast<size_t>(i)].contactTimer;
                beforeProgress[static_cast<size_t>(i)] = karts_[static_cast<size_t>(i)].progress;
            }

            update(kFixedDt, scriptedInput(), true);
            if (raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Racing) {
                const double progress = raceFlow_->racer(0).continuousTrackProgress;
                if (!lapClockStarted) {
                    lapClockStarted = true;
                    lapStartProgress = progress;
                } else if (result.validatedLapSeconds <= 0.0f && progress - lapStartProgress >= 1.0) {
                    result.validatedLapSeconds = static_cast<float>(raceFlow_->raceTimeSeconds());
                }
            }

            std::array<std::pair<float, int>, kKartCount> order{};
            for (int i = 0; i < kKartCount; ++i) {
                const Kart3D& kart = karts_[static_cast<size_t>(i)];
                const float progressDelta = signedDistanceToLoop(beforeProgress[static_cast<size_t>(i)], kart.progress, track_.totalLength());
                if (progressDelta < -40.0f || progressDelta > 90.0f) {
                    ++result.progressJumps;
                }
                if (i == 0 && beforeContact[0] <= 0.001f && kart.contactTimer > 0.05f) {
                    ++result.contacts;
                }
                const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
                const float roadViolation = roadEdgeViolation(kart, center);
                result.maxRoadViolation = std::max(result.maxRoadViolation, roadViolation);
                maxRoadViolationByKart[static_cast<size_t>(i)] = std::max(maxRoadViolationByKart[static_cast<size_t>(i)], roadViolation);
                if (roadViolation > 0.01f) {
                    ++result.roadViolationFrames;
                    ++roadViolationFramesByKart[static_cast<size_t>(i)];
                }
                result.minGroundClearance = std::min(result.minGroundClearance, activeRendererWheelGroundClearance(kart));
                const float score = raceScore(kart);
                order[static_cast<size_t>(i)] = {score, i};
            }

            for (int a = 0; a < kKartCount; ++a) {
                for (int b = a + 1; b < kKartCount; ++b) {
                    const float before = previousScores[static_cast<size_t>(a)] - previousScores[static_cast<size_t>(b)];
                    const float after = orderScore(order, a) - orderScore(order, b);
                    if (std::abs(before) > 6.0f && std::abs(after) > 6.0f && before * after < 0.0f) {
                        ++result.overtakes;
                    }
                }
            }

            for (int i = 0; i < kKartCount; ++i) {
                previousScores[static_cast<size_t>(i)] = orderScore(order, i);
            }
            const float overlap = maxKartOverlap();
            result.maxOverlap = std::max(result.maxOverlap, overlap);
            if (overlap > 1.25f) {
                ++result.overlapFrames;
            }
            result.playerBest = std::min(result.playerBest, playerPosition_);
            result.playerWorst = std::max(result.playerWorst, playerPosition_);
        }

        std::array<float, kKartCount> finalScores{};
        for (int i = 0; i < kKartCount; ++i) {
            finalScores[static_cast<size_t>(i)] = raceScore(karts_[static_cast<size_t>(i)]);
        }
        result.playerScore = finalScores[0];
        result.topAiScore = finalScores[1];
        result.tailAiScore = finalScores[1];
        for (int i = 1; i < kKartCount; ++i) {
            result.topAiScore = std::max(result.topAiScore, finalScores[static_cast<size_t>(i)]);
            result.tailAiScore = std::min(result.tailAiScore, finalScores[static_cast<size_t>(i)]);
        }
        result.spread = std::max(result.topAiScore, result.playerScore) - std::min(result.tailAiScore, result.playerScore);
        result.playerFinal = playerPosition_;
        if (lapClockStarted && raceFlow_) {
            const double lapsDriven = std::max(1.0, raceFlow_->racer(0).continuousTrackProgress - lapStartProgress);
            result.contactBeginningsPerLap = static_cast<float>(static_cast<double>(result.contacts) / lapsDriven);
        }

        const bool stable = result.progressJumps == 0;
        const bool challenging = result.topAiScore > result.playerScore + 3000.0f && result.tailAiScore > result.playerScore + 2000.0f;
        const bool competitiveField = result.topAiScore - result.tailAiScore < 2200.0f && result.overtakes >= 8;
        const bool cleanEnough = result.contactBeginningsPerLap <= 20.0f;
        const bool separated = result.maxOverlap < 2.0f && result.overlapFrames < 4;
        const bool shoulderControlled = result.maxRoadViolation <= 42.0f && result.roadViolationFrames < 15500;
        const bool groundClear = std::abs(result.minGroundClearance) <= 0.03f;
        const bool referenceLap = result.validatedLapSeconds >= 45.0f && result.validatedLapSeconds <= 62.0f;
        const bool ok = shoulderControlled && groundClear && stable && challenging && competitiveField && cleanEnough && separated && referenceLap;

        std::cout << "race-audit player=" << result.playerScore << " top_ai=" << result.topAiScore << " tail_ai=" << result.tailAiScore
                  << " spread=" << result.spread << " overtakes=" << result.overtakes << " contacts=" << result.contacts
                  << " progress_jumps=" << result.progressJumps << " player_pos=" << result.playerFinal << " best=" << result.playerBest
                  << " worst=" << result.playerWorst << " stable=" << stable << " challenging=" << challenging
                  << " competitive_field=" << competitiveField << " clean=" << cleanEnough << " separated=" << separated
                  << " shoulder_controlled=" << shoulderControlled << " ground_clear=" << groundClear
                  << " validated_lap_s=" << result.validatedLapSeconds << " reference_lap=" << referenceLap
                  << " contacts_per_lap=" << result.contactBeginningsPerLap
                  << " max_road_violation=" << result.maxRoadViolation
                  << " road_violation_frames=" << result.roadViolationFrames << " min_ground_clearance=" << result.minGroundClearance
                  << " max_overlap=" << result.maxOverlap << " overlap_frames=" << result.overlapFrames << " scores=";
        for (int i = 0; i < kKartCount; ++i) {
            const Kart3D& kart = karts_[static_cast<size_t>(i)];
            std::cout << (i == 0 ? "" : ",") << i << ":" << finalScores[static_cast<size_t>(i)] << "/" << kart.lap << "/"
                      << static_cast<int>(kart.progress);
        }
        std::cout << " road_by_kart=";
        for (int i = 0; i < kKartCount; ++i) {
            std::cout << (i == 0 ? "" : ",") << i << ":" << maxRoadViolationByKart[static_cast<size_t>(i)] << "/"
                      << roadViolationFramesByKart[static_cast<size_t>(i)];
        }
        std::cout << "\n";
        return ok;
    }

    bool runAiPhysicsParityAudit() {
        track_.rebuild(TrackLayoutId::Monza);
        resetRace();
        const ArcadeVehicleConfig& playerTuning = karts_[0].tuning;
        const ArcadeVehicleConfig& aiTuning = karts_[1].tuning;
        const auto same = [](float a, float b) { return std::abs(a - b) <= 0.00001f; };
        const bool identicalTuning = same(playerTuning.maxForwardSpeed, aiTuning.maxForwardSpeed) &&
                                     same(playerTuning.engineAcceleration, aiTuning.engineAcceleration) &&
                                     same(playerTuning.launchAccelerationBonus, aiTuning.launchAccelerationBonus) &&
                                     same(playerTuning.brakeDeceleration, aiTuning.brakeDeceleration) &&
                                     same(playerTuning.lateralGripAcceleration, aiTuning.lateralGripAcceleration) &&
                                     same(playerTuning.downforceGripGain, aiTuning.downforceGripGain) &&
                                     same(playerTuning.steerResponse, aiTuning.steerResponse) &&
                                     same(playerTuning.brakeReleaseResponse, aiTuning.brakeReleaseResponse) &&
                                     same(playerTuning.rollingResistance, aiTuning.rollingResistance) &&
                                     same(playerTuning.aerodynamicDrag, aiTuning.aerodynamicDrag);

        ArcadeVehicleState playerLaunch;
        ArcadeVehicleState aiLaunch;
        ArcadeVehicleControl launchControl;
        launchControl.throttle = 1.0f;
        launchControl.automaticShift = true;
        ArcadeSurface road;
        float playerHundredKphSeconds = 0.0f;
        float aiHundredKphSeconds = 0.0f;
        constexpr int kLaunchFrames = static_cast<int>(6.0f / kFixedDt);
        for (int frame = 0; frame < kLaunchFrames; ++frame) {
            stepArcadeVehicle(playerLaunch, playerTuning, launchControl, road, kFixedDt);
            stepArcadeVehicle(aiLaunch, aiTuning, launchControl, road, kFixedDt);
            const float elapsed = static_cast<float>(frame + 1) * kFixedDt;
            if (playerHundredKphSeconds <= 0.0f &&
                playerLaunch.forwardSpeed * speedKphPerSimulationUnit(track_.layout()) >= 100.0f) {
                playerHundredKphSeconds = elapsed;
            }
            if (aiHundredKphSeconds <= 0.0f &&
                aiLaunch.forwardSpeed * speedKphPerSimulationUnit(track_.layout()) >= 100.0f) {
                aiHundredKphSeconds = elapsed;
            }
        }
        const float speedDelta = std::abs(playerLaunch.forwardSpeed - aiLaunch.forwardSpeed);
        const float distanceDelta = std::abs(playerLaunch.distanceTravelled - aiLaunch.distanceTravelled);
        const bool identicalLaunch = playerHundredKphSeconds > 0.0f &&
                                     same(playerHundredKphSeconds, aiHundredKphSeconds) &&
                                     speedDelta <= 0.00001f && distanceDelta <= 0.00001f;
        const bool ok = identicalTuning && identicalLaunch;
        std::cout << "ai-physics-parity identical_tuning=" << identicalTuning
                  << " player_0_100_s=" << playerHundredKphSeconds
                  << " ai_0_100_s=" << aiHundredKphSeconds
                  << " speed_delta=" << speedDelta << " distance_delta=" << distanceDelta
                  << " max_speed=" << aiTuning.maxForwardSpeed
                  << " engine_acceleration=" << aiTuning.engineAcceleration
                  << " launch_bonus=" << aiTuning.launchAccelerationBonus
                  << " brake_deceleration=" << aiTuning.brakeDeceleration
                  << " lateral_grip=" << aiTuning.lateralGripAcceleration
                  << " ok=" << ok << "\n";
        return ok;
    }

    bool runMonzaMinimumTimeAudit() {
        selectedSession_ =
            formula_forge::ui::GameModeOption::TimeTrial;
        const AiTimeTrialProfile baselineProfile =
            aiTimeTrialProfile(TrackLayoutId::Monza);
        MonzaOptimizationCandidate best;
        best.profile = baselineProfile;
        MonzaOptimizationReplay bestReplay =
            replayMonzaOptimizationCandidate(best);
        const float baselineReplaySeconds =
            bestReplay.seconds;
        const auto cleanReplay =
            [](const MonzaOptimizationReplay& replay) {
                return replay.completed &&
                       replay.progressJumps == 0 &&
                       replay.barrierContacts == 0 &&
                       replay.maximumRoadViolationMeters <= 1.50f;
            };
        const auto betterReplay =
            [&](const MonzaOptimizationReplay& candidate,
                const MonzaOptimizationReplay& incumbent) {
                const bool candidateClean =
                    cleanReplay(candidate);
                const bool incumbentClean =
                    cleanReplay(incumbent);
                if (candidateClean != incumbentClean) {
                    return candidateClean;
                }
                if (!candidateClean) {
                    if (!candidate.completed ||
                        candidate.progressJumps != 0 ||
                        candidate.barrierContacts != 0) {
                        return false;
                    }
                    if (!incumbent.completed ||
                        incumbent.progressJumps != 0 ||
                        incumbent.barrierContacts != 0) {
                        return true;
                    }
                    if (candidate.maximumRoadViolationMeters <
                        incumbent.maximumRoadViolationMeters -
                            0.001f) {
                        return true;
                    }
                    return std::abs(
                               candidate
                                   .maximumRoadViolationMeters -
                               incumbent
                                   .maximumRoadViolationMeters) <=
                               0.001f &&
                           candidate.seconds <
                               incumbent.seconds -
                                   kFixedDt * 0.25f;
                }
                if (candidate.seconds <
                    incumbent.seconds - kFixedDt * 0.25f) {
                    return true;
                }
                return std::abs(candidate.seconds -
                                incumbent.seconds) <=
                           kFixedDt * 0.25f &&
                       candidate.maximumRoadViolationMeters <
                           incumbent.maximumRoadViolationMeters;
            };
        const auto printImprovement =
            [&](int evaluation,
                const MonzaOptimizationCandidate& candidate,
                const MonzaOptimizationReplay& replay) {
                std::cout
                    << "monza-minimum-search evaluation="
                    << evaluation
                    << " lap_s=" << replay.seconds
                    << " road_violation_m="
                    << replay.maximumRoadViolationMeters
                    << " span="
                    << candidate.profile.smoothingSpan
                    << " road_fraction="
                    << candidate.profile.roadFraction
                    << " speed_reserve="
                    << candidate.profile.speedReserve
                    << " brake_fraction="
                    << candidate.profile.brakePlanningFraction
                    << " lookahead="
                    << candidate.profile.lookaheadBaseMeters
                    << "/"
                    << candidate.profile.lookaheadSpeedSeconds
                    << "/"
                    << candidate.profile.lookaheadMaximumMeters
                    << " gains="
                    << candidate.profile.headingGain
                    << "/"
                    << candidate.profile.crossTrackGain
                    << "\n";
                std::cout.flush();
            };

        int evaluations = 1;
        printImprovement(evaluations, best, bestReplay);

        // First search the global line construction variables. These change
        // the entire geometric trajectory rather than merely retuning the
        // follower around the existing line.
        for (int span = 1; span <= 8; ++span) {
            for (int fractionStep = 10;
                 fractionStep <= 19; ++fractionStep) {
                MonzaOptimizationCandidate candidate = best;
                candidate.profile.smoothingSpan = span;
                candidate.profile.roadFraction =
                    static_cast<float>(fractionStep) * 0.05f;
                const MonzaOptimizationReplay replay =
                    replayMonzaOptimizationCandidate(candidate);
                ++evaluations;
                if (betterReplay(replay, bestReplay)) {
                    best = candidate;
                    bestReplay = replay;
                    printImprovement(
                        evaluations, best, bestReplay);
                }
            }
        }

        // Coordinate descent on the exact closed-loop replay. Step sizes are
        // reduced after each complete pass so the final answer is resolved at
        // the 120 Hz lap-time granularity rather than at a coarse hand-tuned
        // profile.
        std::array<float, 8> steps = {
            0.04f, 0.08f, 4.0f, 0.04f,
            6.0f, 0.12f, 0.12f, 0.0f};
        for (int pass = 0; pass < 4; ++pass) {
            for (int parameter = 0;
                 parameter < 7; ++parameter) {
                for (float direction : {-1.0f, 1.0f}) {
                    MonzaOptimizationCandidate candidate = best;
                    AiTimeTrialProfile& profile =
                        candidate.profile;
                    switch (parameter) {
                        case 0:
                            profile.speedReserve = std::clamp(
                                profile.speedReserve +
                                    direction * steps[0],
                                0.94f, 1.12f);
                            break;
                        case 1:
                            profile.brakePlanningFraction =
                                std::clamp(
                                    profile.brakePlanningFraction +
                                        direction * steps[1],
                                    0.35f, 0.88f);
                            break;
                        case 2:
                            profile.lookaheadBaseMeters =
                                std::clamp(
                                    profile.lookaheadBaseMeters +
                                        direction * steps[2],
                                    6.0f, 30.0f);
                            break;
                        case 3:
                            profile.lookaheadSpeedSeconds =
                                std::clamp(
                                    profile.lookaheadSpeedSeconds +
                                        direction * steps[3],
                                    0.08f, 0.45f);
                            break;
                        case 4:
                            profile.lookaheadMaximumMeters =
                                std::clamp(
                                    profile.lookaheadMaximumMeters +
                                        direction * steps[4],
                                    24.0f, 76.0f);
                            break;
                        case 5:
                            profile.headingGain = std::clamp(
                                profile.headingGain +
                                    direction * steps[5],
                                0.45f, 1.40f);
                            break;
                        default:
                            profile.crossTrackGain =
                                std::clamp(
                                    profile.crossTrackGain +
                                        direction * steps[6],
                                    0.35f, 1.30f);
                            break;
                    }
                    const MonzaOptimizationReplay replay =
                        replayMonzaOptimizationCandidate(
                            candidate);
                    ++evaluations;
                    if (betterReplay(replay, bestReplay)) {
                        best = candidate;
                        bestReplay = replay;
                        printImprovement(
                            evaluations, best, bestReplay);
                    }
                }
            }
            for (int parameter = 0;
                 parameter < 7; ++parameter) {
                steps[static_cast<size_t>(parameter)] *=
                    0.5f;
            }
        }

        // Finally perturb 24 spatial control points on the line itself.
        // Interpolation keeps the path continuous; every candidate is clamped
        // to the authored road/runoff envelope before the exact replay.
        for (float laneStepMeters : {1.0f, 0.5f, 0.25f}) {
            for (size_t knot = 0;
                 knot < best.laneOffsetsMeters.size(); ++knot) {
                for (float direction : {-1.0f, 1.0f}) {
                    MonzaOptimizationCandidate candidate = best;
                    candidate.laneOffsetsMeters[knot] =
                        std::clamp(
                            candidate.laneOffsetsMeters[knot] +
                                direction * laneStepMeters,
                            -3.0f, 3.0f);
                    const MonzaOptimizationReplay replay =
                        replayMonzaOptimizationCandidate(
                            candidate);
                    ++evaluations;
                    if (betterReplay(replay, bestReplay)) {
                        best = candidate;
                        bestReplay = replay;
                        printImprovement(
                            evaluations, best, bestReplay);
                    }
                }
            }
        }

        // Deterministic multi-knot perturbations test combinations that
        // one-coordinate-at-a-time descent cannot reach.
        std::mt19937 generator(1205793);
        std::uniform_int_distribution<int> knotDistribution(
            0,
            static_cast<int>(
                best.laneOffsetsMeters.size()) -
                1);
        std::normal_distribution<float> lanePerturbation(
            0.0f, 0.30f);
        for (int iteration = 0; iteration < 96; ++iteration) {
            MonzaOptimizationCandidate candidate = best;
            for (int perturbation = 0;
                 perturbation < 4; ++perturbation) {
                const size_t knot = static_cast<size_t>(
                    knotDistribution(generator));
                candidate.laneOffsetsMeters[knot] =
                    std::clamp(
                        candidate.laneOffsetsMeters[knot] +
                            lanePerturbation(generator),
                        -3.0f, 3.0f);
            }
            const MonzaOptimizationReplay replay =
                replayMonzaOptimizationCandidate(candidate);
            ++evaluations;
            if (betterReplay(replay, bestReplay)) {
                best = candidate;
                bestReplay = replay;
                printImprovement(
                    evaluations, best, bestReplay);
            }
        }
        for (size_t knot = 0;
             knot < best.laneOffsetsMeters.size(); ++knot) {
            for (float direction : {-1.0f, 1.0f}) {
                MonzaOptimizationCandidate candidate = best;
                candidate.laneOffsetsMeters[knot] =
                    std::clamp(
                        candidate.laneOffsetsMeters[knot] +
                            direction * 0.125f,
                        -3.0f, 3.0f);
                const MonzaOptimizationReplay replay =
                    replayMonzaOptimizationCandidate(candidate);
                ++evaluations;
                if (betterReplay(replay, bestReplay)) {
                    best = candidate;
                    bestReplay = replay;
                    printImprovement(
                        evaluations, best, bestReplay);
                }
            }
        }

        const MonzaOptimizationReplay verificationA =
            replayMonzaOptimizationCandidate(best);
        const MonzaOptimizationReplay verificationB =
            replayMonzaOptimizationCandidate(best);
        const bool deterministic =
            verificationA.completed &&
            verificationB.completed &&
            std::abs(verificationA.seconds -
                     verificationB.seconds) <
                kFixedDt * 0.25f &&
            std::abs(
                verificationA.maximumRoadViolationMeters -
                verificationB.maximumRoadViolationMeters) <
                0.001f;
        const bool ok =
            deterministic &&
            cleanReplay(verificationA) &&
            cleanReplay(verificationB);
        std::cout
            << "monza-minimum-time-audit"
            << " hz=120"
            << " evaluations=" << evaluations
            << " baseline_s=" << baselineReplaySeconds
            << " minimum_s=" << verificationA.seconds
            << " repeat_s=" << verificationB.seconds
            << " road_violation_m="
            << verificationA.maximumRoadViolationMeters
            << " barrier_contacts="
            << verificationA.barrierContacts
            << " progress_jumps="
            << verificationA.progressJumps
            << " span=" << best.profile.smoothingSpan
            << " road_fraction="
            << best.profile.roadFraction
            << " speed_reserve="
            << best.profile.speedReserve
            << " brake_fraction="
            << best.profile.brakePlanningFraction
            << " lookahead="
            << best.profile.lookaheadBaseMeters
            << "/"
            << best.profile.lookaheadSpeedSeconds
            << "/"
            << best.profile.lookaheadMaximumMeters
            << " gains="
            << best.profile.headingGain
            << "/" << best.profile.crossTrackGain
            << " deterministic=" << deterministic
            << " ok=" << ok << "\n";
        std::cout << "monza-minimum-line-offsets-m";
        for (float offset : best.laneOffsetsMeters) {
            std::cout << " " << offset;
        }
        std::cout << "\n";
        return ok;
    }

    float simulateSoloAiRacePaceLap(
        int kartIndex, int sampleLap) {
        const float startProgress =
            track_.startProgress();
        const TrackPoint3D start =
            track_.sample(startProgress);
        Kart3D kart;
        kart.spec = specs_[0];
        kart.tuning =
            selectedTrackTuning(kart.spec);
        kart.racer = racers_[0];
        kart.pos = start.pos;
        kart.heading = angleOf(start.tangent);
        kart.elevation =
            bankedElevation(start, 0.0f);
        kart.grounded = true;
        kart.nearest =
            track_.nearestIndex(kart.pos);
        kart.progress =
            track_.pointAtIndex(kart.nearest)
                .progress;
        kart.previousProgress = kart.progress;
        kart.lap = sampleLap;
        kart.ghostTimer = 300.0f;
        float lapProgress = 0.0f;
        int completedLaps = 0;
        int flyingLapStartFrame = 0;
        constexpr int kMaximumFrames =
            static_cast<int>(
                240.0f / kFixedDt);
        for (int frame = 0;
             frame < kMaximumFrames; ++frame) {
            const float beforeProgress =
                kart.progress;
            updateAi(
                kart, kFixedDt, kartIndex,
                false, true);
            const float progressStep =
                signedDistanceToLoop(
                    beforeProgress,
                    kart.progress,
                    track_.totalLength());
            if (progressStep >= -40.0f &&
                progressStep <= 90.0f) {
                lapProgress += progressStep;
            }
            if (lapProgress <
                track_.totalLength()) {
                continue;
            }
            lapProgress -= track_.totalLength();
            ++completedLaps;
            kart.lap = sampleLap + completedLaps;
            if (completedLaps == 1) {
                flyingLapStartFrame =
                    frame + 1;
            } else {
                return static_cast<float>(
                           frame + 1 -
                           flyingLapStartFrame) *
                       kFixedDt;
            }
        }
        return 0.0f;
    }

    bool runAiRacePaceAudit(
        TrackLayoutId layout =
            TrackLayoutId::Monza) {
        selectedSession_ =
            formula_forge::ui::GameModeOption::
                TimeTrial;
        particles_.clear();
        track_.rebuild(layout);
        Kart3D planKart;
        planKart.spec = specs_[0];
        planKart.tuning =
            selectedTrackTuning(planKart.spec);
        buildAiLapPlan(planKart);
        std::array<float, kKartCount> laps{};
        float total = 0.0f;
        float minimum =
            std::numeric_limits<float>::max();
        float maximum = 0.0f;
        for (int index = 0;
             index < kKartCount; ++index) {
            laps[static_cast<size_t>(index)] =
                simulateSoloAiRacePaceLap(
                    index, index + 1);
            total +=
                laps[static_cast<size_t>(index)];
            minimum = std::min(
                minimum,
                laps[static_cast<size_t>(index)]);
            maximum = std::max(
                maximum,
                laps[static_cast<size_t>(index)]);
        }
        const float mean =
            total /
            static_cast<float>(kKartCount);
        float variance = 0.0f;
        for (float lap : laps) {
            const float delta = lap - mean;
            variance += delta * delta;
        }
        const float standardDeviation =
            std::sqrt(
                variance /
                static_cast<float>(kKartCount));
        const float demonstratedOptimal =
            layout == TrackLayoutId::Monza
                ? kMonzaPeakSoloLapSeconds
                : aiCircuitProfile(layout)
                      .baselineLapSeconds;
        const float target =
            demonstratedOptimal *
            kAiRaceOptimalLapRatio;
        const float ratio =
            mean /
            std::max(0.001f,
                     demonstratedOptimal);
        const bool complete =
            minimum > 0.0f;
        const bool targetPace =
            std::abs(mean - target) <=
            target * 0.0125f;
        const bool variable =
            maximum - minimum >=
            0.05f;
        const bool ok =
            complete && targetPace && variable;
        std::cout
            << "ai-race-pace-audit"
            << " track="
            << aiCircuitProfile(layout).name
            << " optimal_s="
            << demonstratedOptimal
            << " target_s=" << target
            << " mean_s=" << mean
            << " ratio=" << ratio
            << " stddev_s="
            << standardDeviation
            << " min_s=" << minimum
            << " max_s=" << maximum
            << " corners="
            << aiPaceCornerZones_.size()
            << " laps=";
        for (size_t index = 0;
             index < laps.size(); ++index) {
            std::cout
                << (index == 0 ? "" : ",")
                << laps[index];
        }
        std::cout << " ok=" << ok << "\n";
        return ok;
    }

    bool runAiPaceAudit(TrackLayoutId layout = TrackLayoutId::Monza) {
        selectedSession_ =
            formula_forge::ui::GameModeOption::TimeTrial;
        particles_.clear();
        track_.rebuild(layout);
        const AiCircuitProfile profile = aiCircuitProfile(layout);
        const float startProgress = track_.startProgress();
        const TrackPoint3D start = track_.sample(startProgress);
        Kart3D kart;
        kart.spec = specs_[0];
        kart.tuning = selectedTrackTuning(kart.spec);
        kart.racer = racers_[0];
        kart.pos = start.pos;
        kart.heading = angleOf(start.tangent);
        kart.elevation = bankedElevation(start, 0.0f);
        kart.grounded = true;
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.progress = track_.pointAtIndex(kart.nearest).progress;
        kart.previousProgress = kart.progress;
        kart.aiTempo = 1.110f;
        kart.ghostTimer = 60.0f;
        buildAiLapPlan(kart);

        AiPaceAuditResult3D result;
        float cumulativeProgress = 0.0f;
        float lapProgress = 0.0f;
        int completedLaps = 0;
        int flyingLapStartFrame = 0;
        float speedSum = 0.0f;
        int framesDriven = 0;
        std::array<float, 10> sectorSpeedSum{};
        std::array<float, 10> sectorMinSpeed{};
        std::array<float, 10> sectorTargetSpeedSum{};
        std::array<float, 10> sectorMaxRoadViolation{};
        std::array<int, 10> sectorFrames{};
        std::array<int, 10> sectorContactFrames{};
        std::array<bool, 12> flatCornerVisited{};
        std::array<float, 12> flatCornerMinimumThrottle{};
        std::array<float, 12> flatCornerMaximumBrake{};
        constexpr size_t kMaximumAuditedTurns = 24;
        std::array<float, kMaximumAuditedTurns> turnMinimumSpeed{};
        std::array<float, kMaximumAuditedTurns> turnMinimumTargetSpeed{};
        std::array<float, kMaximumAuditedTurns> turnMinimumThrottle{};
        std::array<float, kMaximumAuditedTurns> turnMaximumBrake{};
        std::array<float, kMaximumAuditedTurns> turnMaximumLineError{};
        constexpr float kAscariTraceStart = 0.55f;
        constexpr float kAscariTraceEnd = 0.66f;
        constexpr size_t kAscariTraceBins = 22;
        std::array<float, kAscariTraceBins> ascariMinimumThrottle{};
        std::array<float, kAscariTraceBins> ascariMaximumBrake{};
        std::array<float, kAscariTraceBins> ascariMinimumSpeed{};
        std::array<float, kAscariTraceBins> ascariMinimumTarget{};
        std::array<float, kAscariTraceBins> ascariMaximumLineError{};
        std::array<int, kAscariTraceBins> ascariFlatFrames{};
        std::array<int, kAscariTraceBins> ascariFrames{};
        float ascariSectionMinimumThrottle = 1.0f;
        float ascariSectionMaximumBrake = 0.0f;
        int ascariSectionFrames = 0;
        sectorMinSpeed.fill(std::numeric_limits<float>::max());
        flatCornerMinimumThrottle.fill(1.0f);
        turnMinimumSpeed.fill(std::numeric_limits<float>::max());
        turnMinimumTargetSpeed.fill(std::numeric_limits<float>::max());
        turnMinimumThrottle.fill(1.0f);
        ascariMinimumThrottle.fill(1.0f);
        ascariMinimumSpeed.fill(std::numeric_limits<float>::max());
        ascariMinimumTarget.fill(std::numeric_limits<float>::max());
        bool hasBraked = false;
        constexpr int kMaxFrames = static_cast<int>(400.0f / kFixedDt);
        for (int frame = 0; frame < kMaxFrames; ++frame) {
            const float beforeProgress = kart.progress;
            const float beforeContact = kart.contactTimer;
            const bool wasGrounded = kart.grounded;
            updateAi(kart, kFixedDt, 1, false);
            const float progressStep = signedDistanceToLoop(beforeProgress, kart.progress, track_.totalLength());
            result.maxProgressStep = std::max(result.maxProgressStep, std::abs(progressStep));
            if (progressStep < -40.0f || progressStep > 90.0f) {
                ++result.progressJumps;
            } else {
                cumulativeProgress += progressStep;
                lapProgress += progressStep;
            }
            for (size_t split = 0; split < result.splitSeconds.size(); ++split) {
                if (completedLaps == 1 && result.splitSeconds[split] <= 0.0f &&
                    lapProgress >= track_.totalLength() * (static_cast<float>(split + 1) / 10.0f)) {
                    result.splitSeconds[split] = static_cast<float>(frame + 1 - flyingLapStartFrame) * kFixedDt;
                }
            }
            const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
            const float roadViolation = roadEdgeViolation(kart, center);
            if (roadViolation > result.maxRoadViolation) {
                result.maxRoadViolation = roadViolation;
                result.maxRoadViolationPhase = kart.progress / track_.totalLength();
                result.maxRoadViolationSpeed = length(kart.vel);
                result.maxRoadViolationCurvature = center.curvature;
                result.maxRoadViolationLane = kart.lane;
                result.maxRoadViolationPlannedLane =
                    plannedAiLane(kart.progress);
                result.maxRoadViolationHeadingError = wrapAngle(angleOf(center.tangent) - kart.heading);
                result.maxRoadViolationSteer = kart.aiCommandSteer;
                result.maxRoadViolationTargetSpeed = kart.aiCommandTargetSpeed;
            }
            result.roadViolationFrames += roadViolation > 0.01f ? 1 : 0;
            result.driftFrames += kart.drifting ? 1 : 0;
            result.brakeDriftFrames += kart.brakeLoad > 0.20f && std::abs(kart.slipAngle) > 0.14f ? 1 : 0;
            if (kart.aiCommandBrake > 0.20f) {
                ++result.brakeFrames;
                hasBraked = true;
            }
            if (hasBraked && kart.aiCommandBrake < 0.05f && kart.aiCommandThrottle > 0.80f) {
                ++result.poweredExitFrames;
            }
            result.contactFrames += kart.contactTimer > 0.01f ? 1 : 0;
            result.contacts += beforeContact <= 0.001f && kart.contactTimer > 0.05f ? 1 : 0;
            result.landings += !wasGrounded && kart.grounded ? 1 : 0;
            if (completedLaps == 1) {
                const float phase = kart.progress / track_.totalLength();
                const auto corners = formulaCornerTargets(track_.layout());
                for (size_t cornerIndex = 0; cornerIndex < corners.size(); ++cornerIndex) {
                    const FormulaCornerTarget& corner = corners[cornerIndex];
                    if (!corner.fullThrottle) {
                        continue;
                    }
                    float phaseDistance = std::abs(phase - corner.lapFraction);
                    phaseDistance = std::min(phaseDistance, 1.0f - phaseDistance);
                    if (phaseDistance <= 0.0035f) {
                        flatCornerVisited[cornerIndex] = true;
                        flatCornerMinimumThrottle[cornerIndex] =
                            std::min(flatCornerMinimumThrottle[cornerIndex], kart.aiCommandThrottle);
                        flatCornerMaximumBrake[cornerIndex] =
                            std::max(flatCornerMaximumBrake[cornerIndex], kart.aiCommandBrake);
                    }
                }
                const auto turns =
                    trackTurnExpectations(track_.layout());
                for (size_t turnIndex = 0;
                     turnIndex < std::min(turns.size(),
                                         kMaximumAuditedTurns);
                     ++turnIndex) {
                    float phaseDistance = std::abs(
                        phase - turns[turnIndex].lapFraction);
                    phaseDistance = std::min(
                        phaseDistance, 1.0f - phaseDistance);
                    if (phaseDistance > 0.0035f) {
                        continue;
                    }
                    turnMinimumSpeed[turnIndex] =
                        std::min(turnMinimumSpeed[turnIndex],
                                 length(kart.vel));
                    turnMinimumTargetSpeed[turnIndex] =
                        std::min(turnMinimumTargetSpeed[turnIndex],
                                 kart.aiCommandTargetSpeed);
                    turnMinimumThrottle[turnIndex] =
                        std::min(turnMinimumThrottle[turnIndex],
                                 kart.aiCommandThrottle);
                    turnMaximumBrake[turnIndex] =
                        std::max(turnMaximumBrake[turnIndex],
                                 kart.aiCommandBrake);
                    turnMaximumLineError[turnIndex] =
                        std::max(turnMaximumLineError[turnIndex],
                                 std::abs(
                                     kart.lane -
                                     plannedAiLane(kart.progress)));
                }
                if (track_.layout() == TrackLayoutId::Monza &&
                    phase >= kAscariTraceStart &&
                    phase < kAscariTraceEnd) {
                    const size_t bin = std::min(
                        kAscariTraceBins - 1,
                        static_cast<size_t>(
                            (phase - kAscariTraceStart) /
                            (kAscariTraceEnd -
                             kAscariTraceStart) *
                            static_cast<float>(
                                kAscariTraceBins)));
                    ascariMinimumThrottle[bin] =
                        std::min(ascariMinimumThrottle[bin],
                                 kart.aiCommandThrottle);
                    ascariMaximumBrake[bin] =
                        std::max(ascariMaximumBrake[bin],
                                 kart.aiCommandBrake);
                    ascariMinimumSpeed[bin] =
                        std::min(ascariMinimumSpeed[bin],
                                 length(kart.vel));
                    ascariMinimumTarget[bin] =
                        std::min(ascariMinimumTarget[bin],
                                 kart.aiCommandTargetSpeed);
                    ascariMaximumLineError[bin] =
                        std::max(
                            ascariMaximumLineError[bin],
                            std::abs(
                                kart.lane -
                                plannedAiLane(kart.progress)));
                    ascariFlatFrames[bin] +=
                        kart.aiFullThrottleOptimal ? 1 : 0;
                    ++ascariFrames[bin];
                }
                // Audit boundaries come from the authored Monza turn
                // catalogue.  They are validation only; the controller never
                // sees these phases.
                if (track_.layout() == TrackLayoutId::Monza &&
                    phase >= 0.583f &&
                    phase <= 0.632f) {
                    ascariSectionMinimumThrottle =
                        std::min(ascariSectionMinimumThrottle,
                                 kart.aiCommandThrottle);
                    ascariSectionMaximumBrake =
                        std::max(ascariSectionMaximumBrake,
                                 kart.aiCommandBrake);
                    ++ascariSectionFrames;
                }
            }
            const float speed = length(kart.vel);
            const int sector = std::clamp(static_cast<int>(lapProgress / track_.totalLength() * 10.0f), 0, 9);
            sectorSpeedSum[static_cast<size_t>(sector)] += speed;
            sectorTargetSpeedSum[static_cast<size_t>(sector)] += kart.aiCommandTargetSpeed;
            sectorMaxRoadViolation[static_cast<size_t>(sector)] =
                std::max(sectorMaxRoadViolation[static_cast<size_t>(sector)], roadViolation);
            sectorMinSpeed[static_cast<size_t>(sector)] = std::min(sectorMinSpeed[static_cast<size_t>(sector)], speed);
            ++sectorFrames[static_cast<size_t>(sector)];
            sectorContactFrames[static_cast<size_t>(sector)] += kart.contactTimer > 0.01f ? 1 : 0;
            speedSum += speed;
            framesDriven = frame + 1;
            result.maxSpeed = std::max(result.maxSpeed, speed);
            if (lapProgress >= track_.totalLength()) {
                lapProgress -= track_.totalLength();
                ++completedLaps;
                if (completedLaps == 1) {
                    result.launchLapSeconds = static_cast<float>(frame + 1) * kFixedDt;
                    flyingLapStartFrame = frame + 1;
                    result.splitSeconds.fill(0.0f);
                    sectorSpeedSum.fill(0.0f);
                    sectorMinSpeed.fill(std::numeric_limits<float>::max());
                    sectorTargetSpeedSum.fill(0.0f);
                    sectorMaxRoadViolation.fill(0.0f);
                    sectorFrames.fill(0);
                    sectorContactFrames.fill(0);
                } else {
                    result.lapSeconds = static_cast<float>(frame + 1 - flyingLapStartFrame) * kFixedDt;
                    result.averageSpeed = speedSum / static_cast<float>(frame + 1);
                    break;
                }
            }
        }
        particles_.clear();
        result.distance = cumulativeProgress;
        result.finalPhase = kart.progress / track_.totalLength();
        result.averageSpeed = framesDriven > 0 ? speedSum / static_cast<float>(framesDriven) : 0.0f;

        const auto corners = formulaCornerTargets(track_.layout());
        const float auditTopSpeedExtra =
            isTimeTrial() ? drsTopSpeedExtra() : 0.0f;
        const float auditMaximumSpeed =
            kart.tuning.maxForwardSpeed +
            auditTopSpeedExtra;
        for (size_t cornerIndex = 0; cornerIndex < corners.size(); ++cornerIndex) {
            const FormulaCornerTarget& corner = corners[cornerIndex];
            if (!corner.fullThrottle) {
                continue;
            }
            const float cornerProgress = corner.lapFraction * track_.totalLength();
            const bool physicallyFlat =
                physicalCornerSpeed(
                    kart, cornerProgress,
                    auditTopSpeedExtra) >=
                auditMaximumSpeed * 0.990f;
            if (!physicallyFlat) {
                continue;
            }
            ++result.physicallyFlatCorners;
            result.flatCornersTakenFlat += flatCornerVisited[cornerIndex] &&
                                                   flatCornerMinimumThrottle[cornerIndex] >= 0.80f &&
                                                   flatCornerMaximumBrake[cornerIndex] <= 0.05f
                                               ? 1
                                               : 0;
        }

        std::vector<float> trackCurvatures;
        trackCurvatures.reserve(track_.samples().size());
        for (const TrackPoint3D& point : track_.samples()) {
            trackCurvatures.push_back(point.curvature);
        }
        std::sort(trackCurvatures.begin(), trackCurvatures.end());
        const float medianTrackCurvature = trackCurvatures[trackCurvatures.size() / 2];
        const float p90TrackCurvature = trackCurvatures[trackCurvatures.size() * 9 / 10];
        const float maxTrackCurvature = trackCurvatures.back();

        // The benchmark is the fastest clean lap demonstrated by this exact
        // controller and vehicle simulation. A deterministic solo replay must
        // retain at least 99.5% of that physics-validated performance; faster
        // clean laps are always accepted.
        constexpr float kMinimumTheoreticalPerformance = 0.995f;
        const bool targetPace = result.lapSeconds > 0.0f &&
                                result.lapSeconds <=
                                    aiLapTheoreticalSeconds_ /
                                            kMinimumTheoreticalPerformance +
                                        kFixedDt &&
                                result.launchLapSeconds > 0.0f;
        const bool physicalPath = result.progressJumps == 0 && result.maxProgressStep <= profile.maximumProgressStep &&
                                  result.maxRoadViolation <= profile.maximumRoadViolationMeters *
                                                                         kTrackSimulationUnitsPerMeter &&
                                  result.roadViolationFrames < 4500 && result.contacts == 0;
        const bool usesFlatCorners =
            result.physicallyFlatCorners > 0 &&
            result.flatCornersTakenFlat ==
                result.physicallyFlatCorners;
        bool physicsValidatedFlatSections = true;
        if (track_.layout() == TrackLayoutId::Monza) {
            constexpr size_t kValidatedFlatTurnCount = 5;
            for (size_t turnIndex = 0;
                 turnIndex < kValidatedFlatTurnCount; ++turnIndex) {
                const float turnProgress =
                    trackTurnExpectations(
                        track_.layout())[turnIndex]
                        .lapFraction *
                    track_.totalLength();
                if (!isPhysicsValidatedFlatProgress(
                        turnProgress, isTimeTrial())) {
                    continue;
                }
                physicsValidatedFlatSections =
                    physicsValidatedFlatSections &&
                    turnMinimumThrottle[turnIndex] >= 0.995f &&
                    turnMaximumBrake[turnIndex] <= 0.005f;
            }
        }
        const bool formulaRacecraft = result.averageSpeed > 500.0f && result.brakeFrames > 200 &&
                                      result.poweredExitFrames > 1000 && result.driftFrames == 0 &&
                                      result.brakeDriftFrames < profile.maximumBrakeDriftFrames;
        const bool ascariFlat =
            track_.layout() != TrackLayoutId::Monza ||
            (ascariSectionFrames > 0 &&
             ascariSectionMinimumThrottle >= 0.995f &&
             ascariSectionMaximumBrake <= 0.005f);
        const bool ascariDrsPlan =
            track_.layout() == TrackLayoutId::Monza &&
            isTimeTrial() &&
            kDrsTopSpeedExtraKph > 0.0f &&
            ascariSectionFrames > 0;
        const bool ok = targetPace && physicalPath && usesFlatCorners &&
                        physicsValidatedFlatSections &&
                        formulaRacecraft &&
                        (ascariFlat || ascariDrsPlan);
        std::cout << "ai-pace-audit track=" << profile.name
                  << " launch_lap_s=" << result.launchLapSeconds
                  << " planned_lap_s=" << aiLapTheoreticalSeconds_
                  << " model_lap_s=" << aiLapModelSeconds_
                  << " race_plan_s=" << aiRacePlanSeconds_
                  << " race_drs_plan_s="
                  << aiRaceDrsPlanSeconds_
                  << " race_drs_ratio="
                  << aiRaceDrsPlanSeconds_ /
                         std::max(0.001f,
                                  aiLapModelSeconds_)
                  << " pace_corners="
                  << aiPaceCornerZones_.size()
                  << " benchmark_ratio="
                  << result.lapSeconds /
                         std::max(0.001f, aiLapTheoreticalSeconds_)
                  << " line_span=" << aiLapSelectedSmoothingSpan_
                  << " line_fraction=" << aiLapSelectedRoadFraction_
                  << " flying_lap_s=" << result.lapSeconds << " distance=" << result.distance
                  << " final_phase=" << result.finalPhase << " avg_speed=" << result.averageSpeed
                  << " max_speed=" << result.maxSpeed << " max_road_violation=" << result.maxRoadViolation
                  << " max_road_violation_phase=" << result.maxRoadViolationPhase
                  << " max_road_violation_speed=" << result.maxRoadViolationSpeed
                  << " max_road_violation_curvature=" << result.maxRoadViolationCurvature
                  << " max_road_violation_lane=" << result.maxRoadViolationLane
                  << " max_road_violation_planned_lane="
                  << result.maxRoadViolationPlannedLane
                  << " max_road_violation_heading_error=" << result.maxRoadViolationHeadingError
                  << " max_road_violation_steer=" << result.maxRoadViolationSteer
                  << " max_road_violation_target_speed=" << result.maxRoadViolationTargetSpeed
                  << " road_violation_frames=" << result.roadViolationFrames << " drift_frames=" << result.driftFrames
                  << " brake_drift_frames=" << result.brakeDriftFrames
                  << " brake_frames=" << result.brakeFrames << " powered_exit_frames=" << result.poweredExitFrames
                  << " contacts=" << result.contacts << " contact_frames=" << result.contactFrames
                  << " landings=" << result.landings << " max_progress_step=" << result.maxProgressStep
                  << " progress_jumps=" << result.progressJumps << " max_track_curvature=" << maxTrackCurvature
                  << " flat_corners=" << result.flatCornersTakenFlat << "/" << result.physicallyFlatCorners
                  << " median_track_curvature=" << medianTrackCurvature << " p90_track_curvature=" << p90TrackCurvature
                  << " target_pace=" << targetPace
                  << " physical_path=" << physicalPath << " uses_flat_corners=" << usesFlatCorners
                  << " physics_validated_flat="
                  << physicsValidatedFlatSections
                  << " formula_racecraft=" << formulaRacecraft
                  << " ascari_flat=" << ascariFlat
                  << " ascari_drs_plan="
                  << ascariDrsPlan
                  << " ascari_throttle_min="
                  << ascariSectionMinimumThrottle
                  << " ascari_brake_max="
                  << ascariSectionMaximumBrake
                  << " ok=" << ok << "\n";
        std::cout << "ai-pace-splits";
        for (size_t i = 0; i < result.splitSeconds.size(); ++i) {
            std::cout << " " << (i + 1) * 10 << ":" << result.splitSeconds[i];
        }
        std::cout << "\n";
        std::cout << "ai-pace-sectors";
        for (size_t i = 0; i < sectorFrames.size(); ++i) {
            const float average = sectorFrames[i] > 0 ? sectorSpeedSum[i] / static_cast<float>(sectorFrames[i]) : 0.0f;
            const float averageTarget = sectorFrames[i] > 0
                                            ? sectorTargetSpeedSum[i] / static_cast<float>(sectorFrames[i])
                                            : 0.0f;
            const float minimum = sectorFrames[i] > 0 ? sectorMinSpeed[i] : 0.0f;
            std::cout << " " << (i + 1) * 10 << ":" << average << "/" << minimum << "/"
                      << averageTarget << "/" << sectorMaxRoadViolation[i] << "/" << sectorContactFrames[i];
        }
        std::cout << "\n";
        std::cout << "ai-pace-turns";
        const float kphPerUnit =
            speedKphPerSimulationUnit(track_.layout());
        const auto turns = trackTurnExpectations(track_.layout());
        for (size_t turnIndex = 0;
             turnIndex < std::min(turns.size(),
                                 kMaximumAuditedTurns);
             ++turnIndex) {
            const TrackTurnExpectation& turn = turns[turnIndex];
            const float progress =
                turn.lapFraction * track_.totalLength();
            std::cout << " " << turn.landmark
                      << "={physical_kph:"
                      << physicalCornerSpeed(kart, progress) *
                             kphPerUnit
                      << ",path_kph:"
                      << plannedAiTheoreticalSpeed(progress) *
                             kphPerUnit
                      << ",target_kph:"
                      << turnMinimumTargetSpeed[turnIndex] *
                             kphPerUnit
                      << ",actual_kph:"
                      << turnMinimumSpeed[turnIndex] *
                             kphPerUnit
                      << ",throttle:"
                      << turnMinimumThrottle[turnIndex]
                      << ",brake:"
                      << turnMaximumBrake[turnIndex]
                      << ",line_error_m:"
                      << turnMaximumLineError[turnIndex] /
                             kTrackSimulationUnitsPerMeter
                      << ",planned_lane_m:"
                      << plannedAiLane(progress) /
                             kTrackSimulationUnitsPerMeter
                      << "}";
        }
        std::cout << "\n";
        if (track_.layout() == TrackLayoutId::Monza) {
            std::cout << "ai-ascari-trace";
            for (size_t bin = 0;
                 bin < kAscariTraceBins; ++bin) {
                const float phase =
                    kAscariTraceStart +
                    (static_cast<float>(bin) + 0.5f) *
                        (kAscariTraceEnd -
                         kAscariTraceStart) /
                        static_cast<float>(
                            kAscariTraceBins);
                std::cout
                    << " " << phase
                    << "={speed:"
                    << (ascariFrames[bin] > 0
                            ? ascariMinimumSpeed[bin] *
                                  kphPerUnit
                            : 0.0f)
                    << ",target:"
                    << (ascariFrames[bin] > 0
                            ? ascariMinimumTarget[bin] *
                                  kphPerUnit
                            : 0.0f)
                    << ",throttle:"
                    << ascariMinimumThrottle[bin]
                    << ",brake:"
                    << ascariMaximumBrake[bin]
                    << ",flat_frames:"
                    << ascariFlatFrames[bin] << "/"
                    << ascariFrames[bin]
                    << ",line_error_m:"
                    << ascariMaximumLineError[bin] /
                           kTrackSimulationUnitsPerMeter
                    << "}";
            }
            std::cout << "\n";
        }
        std::cout << "ai-flat-corners";
        for (size_t cornerIndex = 0; cornerIndex < corners.size(); ++cornerIndex) {
            const FormulaCornerTarget& corner = corners[cornerIndex];
            if (!corner.fullThrottle) {
                continue;
            }
            const float cornerProgress =
                corner.lapFraction * track_.totalLength();
            const float auditHalfWindow =
                0.0035f * track_.totalLength();
            const float minimumPlannedRatio = std::min({
                plannedAiTheoreticalSpeed(cornerProgress -
                                          auditHalfWindow),
                plannedAiTheoreticalSpeed(cornerProgress),
                plannedAiTheoreticalSpeed(cornerProgress +
                                          auditHalfWindow)}) /
                std::max(1.0f, kart.tuning.maxForwardSpeed);
            const float physicalRatio =
                physicalCornerSpeed(kart, cornerProgress) /
                std::max(1.0f, kart.tuning.maxForwardSpeed);
            std::cout << " " << corner.name
                      << "={physical:" << physicalRatio
                      << ",planned_window:" << minimumPlannedRatio
                      << ",throttle:"
                      << flatCornerMinimumThrottle[cornerIndex]
                      << ",brake:"
                      << flatCornerMaximumBrake[cornerIndex] << "}";
        }
        std::cout << "\n";
        return ok;
    }

    bool runCollisionAudit() {
        track_.rebuild(TrackLayoutId::Monza);
        const CollisionAuditResult3D rearEnd = simulateCollisionScenario("rear_end", 0);
        const CollisionAuditResult3D headOn = simulateCollisionScenario("head_on", 1);
        const CollisionAuditResult3D sideSwipe = simulateCollisionScenario("side_swipe", 2);
        const bool rearOk = rearEnd.contactFrames > 0 && rearEnd.maxOverlap < 1.25f && rearEnd.overlapFrames == 0 &&
                            rearEnd.vehicleTelemetry && rearEnd.maxContactImpulse > 0.0f;
        const bool headOk = headOn.contactFrames > 0 && headOn.maxOverlap < 1.25f && headOn.overlapFrames == 0 &&
                            headOn.vehicleTelemetry && headOn.maxContactImpulse > 0.0f;
        const bool sideOk = sideSwipe.contactFrames > 0 && sideSwipe.maxOverlap < 1.25f && sideSwipe.overlapFrames == 0 &&
                            sideSwipe.vehicleTelemetry && sideSwipe.maxContactImpulse > 0.0f;
        const bool sideMomentumPreserved =
            sideSwipe.strikerSpeedAfterContact >=
                sideSwipe.strikerSpeedBeforeContact * 0.985f &&
            sideSwipe.targetSpeedAfterContact >=
                sideSwipe.targetSpeedBeforeContact * 0.985f;
        Kart3D light;
        Kart3D heavy;
        light.spec = specs_[1];
        heavy.spec = specs_[3];
        const float invLight = inverseKartMass(light);
        const float invHeavy = inverseKartMass(heavy);
        const float lightResponseFirst = invLight / (invLight + invHeavy);
        const float lightResponseSecond = invLight / (invHeavy + invLight);
        const float massRatio = kartMass(heavy) / kartMass(light);
        const bool massComparable = massRatio >= 0.94f && massRatio <= 1.06f;
        const bool roleSymmetric = std::abs(lightResponseFirst - lightResponseSecond) < 0.000001f;
        light.progress = 400.0f;
        heavy.progress = 400.0f;
        light.elevation = 0.0f;
        heavy.elevation = kContactVerticalWindow + 0.5f;
        light.ghostTimer = 0.0f;
        heavy.ghostTimer = 0.0f;
        const bool jumpClears = !shouldTestKartContact(light, heavy);

        float maxBarrierWidthStepMeters = 0.0f;
        float minCurbWidthMeters = std::numeric_limits<float>::max();
        float minRunoffBeyondCurbMeters = std::numeric_limits<float>::max();
        float minBarrierBeyondRunoffMeters = std::numeric_limits<float>::max();
        float maxBoundaryContractError = 0.0f;
        bool envelopeOrdered = true;
        constexpr std::array<TrackLayoutId, 12> kMetricLayouts = {
            TrackLayoutId::Spa, TrackLayoutId::Suzuka, TrackLayoutId::Silverstone,
            TrackLayoutId::Monza, TrackLayoutId::Interlagos, TrackLayoutId::Shanghai,
            TrackLayoutId::Bahrain, TrackLayoutId::Sepang,
            TrackLayoutId::Cota, TrackLayoutId::Istanbul, TrackLayoutId::Hockenheim,
            TrackLayoutId::Buddh};
        for (TrackLayoutId layout : kMetricLayouts) {
            track_.rebuild(layout);
            Kart3D contractKart;
            contractKart.spec = specs_[0];
            for (int i = 0; i < track_.sampleCount(); ++i) {
                const TrackPoint3D& point = track_.pointAtIndex(i);
                const TrackPoint3D& next = track_.pointAtIndex(i + 1);
                contractKart.heading = angleOf(point.tangent);
                const MetricCircuitEnvelope3D envelope = metricCircuitEnvelope(point);
                const MetricCircuitEnvelope3D nextEnvelope = metricCircuitEnvelope(next);
                const float expectedBoundary = envelope.barrierInnerFace - projectedKartExtent(contractKart, point.normal);
                maxBoundaryContractError = std::max(maxBoundaryContractError,
                                                    std::abs(hardBoundaryLaneLimit(contractKart, point) - expectedBoundary));
                maxBarrierWidthStepMeters = std::max(maxBarrierWidthStepMeters,
                                                     std::abs(nextEnvelope.barrierInnerFace - envelope.barrierInnerFace) /
                                                         kTrackSimulationUnitsPerMeter);
                minCurbWidthMeters = std::min(minCurbWidthMeters,
                                              (envelope.curbOuter - envelope.asphaltOuter) /
                                                  kTrackSimulationUnitsPerMeter);
                minRunoffBeyondCurbMeters = std::min(minRunoffBeyondCurbMeters,
                                                     (envelope.runoffOuter - envelope.curbOuter) /
                                                         kTrackSimulationUnitsPerMeter);
                minBarrierBeyondRunoffMeters = std::min(minBarrierBeyondRunoffMeters,
                                                        (envelope.barrierInnerFace - envelope.runoffOuter) /
                                                            kTrackSimulationUnitsPerMeter);
                envelopeOrdered = envelopeOrdered && envelope.asphaltOuter < envelope.curbOuter &&
                                  envelope.curbOuter < envelope.runoffOuter &&
                                  envelope.runoffOuter < envelope.barrierInnerFace &&
                                  envelope.barrierInnerFace < envelope.barrierCenter;
            }
        }
        const bool widthTransitions = maxBarrierWidthStepMeters < 0.20f && maxBoundaryContractError < 0.001f;
        const bool footprintExact = std::abs(contactHalfWidth(light) - light.spec.width * 0.5f) < 0.001f &&
                                    std::abs(contactHalfLength(light) - light.spec.length * 0.5f) < 0.001f;

        track_.rebuild(TrackLayoutId::Spa);
        const TrackPoint3D traversalPoint = track_.sample(3200.0f);
        const MetricCircuitEnvelope3D traversalEnvelope = metricCircuitEnvelope(traversalPoint);
        const auto laneDoesNotCollide = [&](float lane) {
            Kart3D kart;
            kart.spec = specs_[0];
            kart.heading = angleOf(traversalPoint.tangent);
            kart.vel = traversalPoint.tangent * 120.0f;
            kart.pos = traversalPoint.pos + traversalPoint.normal * lane;
            kart.progress = traversalPoint.progress;
            kart.nearest = track_.nearestIndex(kart.pos);
            const Vec2 beforePosition = kart.pos;
            const Vec2 beforeVelocity = kart.vel;
            constrainToTrack(kart);
            return length(kart.pos - beforePosition) < 0.001f && length(kart.vel - beforeVelocity) < 0.001f &&
                   kart.contactTimer <= 0.001f && !kart.barrierContact;
        };
        const float curbCenter = (traversalEnvelope.asphaltOuter + traversalEnvelope.curbOuter) * 0.5f;
        const float runoffCenter = (traversalEnvelope.curbOuter + traversalEnvelope.runoffOuter) * 0.5f;
        const bool curbsDriveable = laneDoesNotCollide(curbCenter) && laneDoesNotCollide(-curbCenter);
        const bool runoffDriveable = laneDoesNotCollide(runoffCenter) && laneDoesNotCollide(-runoffCenter);

        Kart3D onsetKart;
        onsetKart.spec = specs_[0];
        onsetKart.heading = angleOf(traversalPoint.tangent);
        onsetKart.vel = traversalPoint.tangent * 80.0f + traversalPoint.normal * 20.0f;
        onsetKart.progress = traversalPoint.progress;
        onsetKart.nearest = track_.nearestIndex(traversalPoint.pos);
        const float onsetLimit = hardBoundaryLaneLimit(onsetKart, traversalPoint);
        onsetKart.pos = traversalPoint.pos + traversalPoint.normal * (onsetLimit - 0.25f);
        constrainToTrack(onsetKart);
        const bool beforeBarrierClear = !onsetKart.barrierContact && onsetKart.contactTimer <= 0.001f;
        onsetKart.pos = traversalPoint.pos + traversalPoint.normal * (onsetLimit + 0.25f);
        constrainToTrack(onsetKart);
        const bool visibleBarrierOnset = beforeBarrierClear && onsetKart.barrierContact && onsetKart.contactTimer > 0.05f;

        Kart3D directKart;
        directKart.spec = specs_[0];
        directKart.heading = angleOf(traversalPoint.normal);
        directKart.vel = traversalPoint.normal * 160.0f;
        directKart.progress = traversalPoint.progress;
        directKart.nearest = track_.nearestIndex(traversalPoint.pos);
        const float directLimit = hardBoundaryLaneLimit(directKart, traversalPoint);
        directKart.pos = traversalPoint.pos + traversalPoint.normal * (directLimit + 2.0f);
        constrainToTrack(directKart);
        const float directStopSpeed = length(directKart.vel);
        const bool directBarrierStops = directKart.barrierContact && directStopSpeed < 5.0f &&
                                        directKart.contactCause == ContactCause3D::Barrier &&
                                        !directKart.vehicleContact && directKart.contactImpulse > 0.0f;

        Kart3D wallKart;
        wallKart.spec = specs_[0];
        wallKart.tuning = selectedTrackTuning(wallKart.spec);
        const TrackPoint3D wallPoint = track_.sample(2600.0f);
        const float wallLimit = hardBoundaryLaneLimit(wallKart, wallPoint);
        wallKart.pos = wallPoint.pos + wallPoint.normal * (wallLimit + 6.0f);
        wallKart.heading = angleOf(normalize(wallPoint.tangent + wallPoint.normal * 0.25f));
        wallKart.vel = wallPoint.tangent * 140.0f + wallPoint.normal * 35.0f;
        wallKart.progress = wallPoint.progress;
        wallKart.previousProgress = wallPoint.progress;
        wallKart.nearest = track_.nearestIndex(wallKart.pos);
        const float wallSpeedBefore = length(wallKart.vel);
        const float wallHeadingBefore = wallKart.heading;
        constrainToTrack(wallKart);
        const float wallRetention = length(wallKart.vel) / wallSpeedBefore;
        const float wallForwardSpeed = dot(wallKart.vel, wallPoint.tangent);
        const bool wallGlances = wallRetention > 0.82f && wallForwardSpeed > 118.0f &&
                                 dot(wallKart.vel, wallPoint.normal) <= 0.0f &&
                                 std::abs(wrapAngle(wallKart.heading - wallHeadingBefore)) < 0.001f;

        Kart3D shoulderKart;
        shoulderKart.spec = specs_[0];
        shoulderKart.tuning = selectedTrackTuning(shoulderKart.spec);
        shoulderKart.tuning.engineAcceleration = 0.0f;
        shoulderKart.tuning.launchAccelerationBonus = 0.0f;
        shoulderKart.tuning.gravity = 0.0f;
        const TrackPoint3D shoulderPoint = track_.sample(3200.0f);
        shoulderKart.progress = shoulderPoint.progress;
        shoulderKart.previousProgress = shoulderPoint.progress;
        shoulderKart.pos = shoulderPoint.pos + shoulderPoint.normal * (roadCenterLimit(shoulderKart, shoulderPoint) + 8.0f);
        shoulderKart.heading = angleOf(shoulderPoint.tangent);
        shoulderKart.elevation = bankedElevation(shoulderPoint, roadCenterLimit(shoulderKart, shoulderPoint) + 8.0f);
        shoulderKart.grounded = true;
        shoulderKart.nearest = track_.nearestIndex(shoulderKart.pos);
        Input3D heldThrottle;
        heldThrottle.throttle = 1.0f;
        for (int frame = 0; frame < static_cast<int>(3.0f / kFixedDt); ++frame) {
            integrateKart(shoulderKart, heldThrottle, kFixedDt);
        }
        const TrackPoint3D finalShoulderPoint = track_.sample(shoulderKart.progress);
        const bool noAutomaticRecovery = roadEdgeViolation(shoulderKart, finalShoulderPoint) > 5.0f &&
                                         shoulderKart.ghostTimer <= 0.001f;

        track_.rebuild(TrackLayoutId::Monza);
        const TrackPoint3D slowStart = track_.sample(track_.startProgress());
        Kart3D slowKart;
        slowKart.spec = specs_[0];
        slowKart.tuning = selectedTrackTuning(slowKart.spec);
        slowKart.pos = slowStart.pos + slowStart.normal * roadSurfaceHalfWidth(slowStart);
        slowKart.heading = angleOf(slowStart.tangent);
        slowKart.vel = slowStart.tangent * 8.0f;
        slowKart.progress = slowStart.progress;
        slowKart.previousProgress = slowStart.progress;
        slowKart.nearest = track_.nearestIndex(slowKart.pos);
        slowKart.elevation = bankedElevation(slowStart, roadSurfaceHalfWidth(slowStart));
        slowKart.grounded = true;
        float maxSlowPhysicsClearance = 0.0f;
        float maxSlowRenderContactError = 0.0f;
        Input3D coastInput;
        for (int frame = 0; frame < static_cast<int>(3.0f / kFixedDt); ++frame) {
            integrateKart(slowKart, coastInput, kFixedDt);
            const TrackPoint3D slowGround = track_.sample(slowKart.progress);
            const float lane = dot(slowKart.pos - slowGround.pos, slowGround.normal);
            const float physicsGround = bankedElevation(slowGround, lane);
            maxSlowPhysicsClearance = std::max(maxSlowPhysicsClearance,
                                               std::abs(slowKart.elevation - physicsGround));
            const float renderedTireContact = slowKart.elevation * kRenderScale + authoredRoadSurfaceLift(track_.layout());
            const float renderedRoadSurface = physicsGround * kRenderScale +
                                              kMetricRoadSurfaceOffsetMeters * kTrackSimulationUnitsPerMeter * kRenderScale;
            maxSlowRenderContactError = std::max(maxSlowRenderContactError,
                                                 std::abs(renderedTireContact - renderedRoadSurface));
        }
        const bool lowSpeedTiresGrounded = slowKart.grounded && maxSlowPhysicsClearance < 0.001f &&
                                           maxSlowRenderContactError < 0.001f;

        const auto surfaceSample = [&](float progress, float side) {
            const TrackPoint3D point = track_.sample(progress);
            Kart3D kart;
            kart.spec = specs_[0];
            kart.tuning = selectedTrackTuning(kart.spec);
            kart.progress = progress;
            kart.lane = side * (roadSurfaceHalfWidth(point) +
                                kMetricCurbWidthMeters * kTrackSimulationUnitsPerMeter +
                                contactHalfWidth(kart) + 0.50f * kTrackSimulationUnitsPerMeter);
            kart.pos = point.pos + point.normal * kart.lane;
            kart.heading = angleOf(point.tangent);
            kart.vel = point.tangent * 300.0f;
            return std::pair{kart, drivingSurfaceFor(kart, point)};
        };
        auto [pavedKart, pavedSurface] = surfaceSample(300.0f, 1.0f);
        auto [grassKart, grassSurface] = surfaceSample(800.0f, 1.0f);
        auto [gravelKart, gravelSurface] = surfaceSample(1500.0f, 1.0f);
        const bool runoffKindsMatch = pavedSurface.kind == DrivingSurface3D::AsphaltRunoff &&
                                      grassSurface.kind == DrivingSurface3D::Grass &&
                                      gravelSurface.kind == DrivingSurface3D::Gravel;
        const bool looseSurfacePenalty = pavedSurface.physics.maxSpeed <= 0.87f &&
                                         grassSurface.physics.maxSpeed <= 0.53f &&
                                         grassSurface.physics.rollingResistance >= 8.4f &&
                                         gravelSurface.physics.maxSpeed <= 0.63f &&
                                         gravelSurface.physics.rollingResistance >= 6.9f;

        ArcadeVehicleControl surfaceThrottle;
        surfaceThrottle.throttle = 1.0f;
        ArcadeVehicleState pavedRun = pavedKart;
        ArcadeVehicleState grassRun = grassKart;
        ArcadeVehicleState gravelRun = gravelKart;
        const ArcadeVehicleConfig surfaceTuning = selectedTrackTuning(specs_[0]);
        for (int frame = 0; frame < static_cast<int>(4.0f / kFixedDt); ++frame) {
            stepArcadeVehicle(pavedRun, surfaceTuning, surfaceThrottle, pavedSurface.physics, kFixedDt);
            stepArcadeVehicle(grassRun, surfaceTuning, surfaceThrottle, grassSurface.physics, kFixedDt);
            stepArcadeVehicle(gravelRun, surfaceTuning, surfaceThrottle, gravelSurface.physics, kFixedDt);
        }
        const float grassSpeedRatio = length(grassRun.vel) / std::max(1.0f, length(pavedRun.vel));
        const float gravelSpeedRatio = length(gravelRun.vel) / std::max(1.0f, length(pavedRun.vel));
        const bool offRoadActuallySlows = grassSpeedRatio < 0.70f && gravelSpeedRatio < 0.78f;

        const TrackPoint3D groundContractPoint = track_.sample(1500.0f);
        const float groundTransition = roadSurfaceHalfWidth(groundContractPoint) +
                                       kMetricRunoffWidthMeters * kTrackSimulationUnitsPerMeter;
        const float groundOuter = roadSurfaceHalfWidth(groundContractPoint) +
                                  kMetricTerrainReachMeters * kTrackSimulationUnitsPerMeter;
        const float transitionGroundStep = std::abs(
            metricGroundElevation(groundContractPoint, groundTransition - 0.01f) -
            metricGroundElevation(groundContractPoint, groundTransition + 0.01f));
        const float outerGroundStep = std::abs(
            metricGroundElevation(groundContractPoint, groundOuter - 0.01f) -
            metricGroundElevation(groundContractPoint, groundOuter + 0.01f));
        const bool terrainGroundContinuous = transitionGroundStep < 0.01f && outerGroundStep < 0.01f;

        selectedSession_ = formula_forge::ui::GameModeOption::Race;
        selectedMap_ = 3;
        startRace();
        bool gridClear = true;
        bool renderStateInitialized = true;
        bool playerStartsLast = playerPosition_ == kKartCount;
        float initialGridOverlap = 0.0f;
        const float playerGridScore = raceScore(karts_[0]);
        for (int i = 0; i < kKartCount; ++i) {
            const Kart3D& kart = karts_[static_cast<size_t>(i)];
            renderStateInitialized = renderStateInitialized &&
                                     lengthSq(kart.previousRenderPos - kart.pos) < 0.000001f &&
                                     std::abs(kart.previousRenderElevation - kart.elevation) < 0.000001f &&
                                     std::abs(wrapAngle(kart.previousRenderHeading - kart.heading)) < 0.000001f;
            if (i > 0) {
                playerStartsLast = playerStartsLast && playerGridScore < raceScore(kart);
            }
        }
        for (int a = 0; a < kKartCount; ++a) {
            for (int b = a + 1; b < kKartCount; ++b) {
                const KartContact3D contact = kartContact(karts_[static_cast<size_t>(a)],
                                                         karts_[static_cast<size_t>(b)]);
                if (contact.touching) {
                    gridClear = false;
                    initialGridOverlap = std::max(initialGridOverlap, contact.penetration);
                }
            }
        }
        while (raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Countdown) {
            update(kFixedDt, Input3D{}, true);
        }
        float minimumGreenGhost = std::numeric_limits<float>::max();
        for (const Kart3D& kart : karts_) {
            minimumGreenGhost = std::min(minimumGreenGhost, kart.ghostTimer);
        }
        const float launchStartProgress = karts_[0].progress;
        int launchVehicleContactFrames = 0;
        float launchMaxOverlap = 0.0f;
        Input3D launchInput;
        launchInput.throttle = 1.0f;
        for (int frame = 0; frame < static_cast<int>(3.0f / kFixedDt); ++frame) {
            update(kFixedDt, launchInput, true);
            launchVehicleContactFrames += karts_[0].vehicleContact ? 1 : 0;
            for (int a = 0; a < kKartCount; ++a) {
                for (int b = a + 1; b < kKartCount; ++b) {
                    const KartContact3D contact = kartContact(karts_[static_cast<size_t>(a)],
                                                             karts_[static_cast<size_t>(b)]);
                    if (contact.touching) {
                        launchMaxOverlap = std::max(launchMaxOverlap, contact.penetration);
                    }
                }
            }
        }
        const float launchDistanceMeters =
            signedDistanceToLoop(launchStartProgress, karts_[0].progress, track_.totalLength());
        const bool cleanLaunch = gridClear && renderStateInitialized && playerStartsLast &&
                                 minimumGreenGhost <= 0.001f &&
                                 launchVehicleContactFrames == 0 && launchMaxOverlap < 0.05f &&
                                 launchDistanceMeters > 2.0f;
        const bool rearPushes = rearEnd.strikerSpeedAfterContact > 100.0f && rearEnd.targetSpeedAfterContact > 47.0f;
        const bool ok = rearOk && headOk && sideOk && sideMomentumPreserved &&
                        massComparable && roleSymmetric && jumpClears && wallGlances &&
                        noAutomaticRecovery && rearPushes && envelopeOrdered && widthTransitions && footprintExact &&
                        curbsDriveable && runoffDriveable && visibleBarrierOnset && directBarrierStops &&
                        lowSpeedTiresGrounded && runoffKindsMatch && looseSurfacePenalty &&
                        offRoadActuallySlows && terrainGroundContinuous && cleanLaunch;

        auto print = [](const CollisionAuditResult3D& r) {
            std::cout << r.name << "_max_overlap=" << r.maxOverlap << " " << r.name << "_overlap_frames=" << r.overlapFrames << " "
                      << r.name << "_contact_frames=" << r.contactFrames << " "
                      << r.name << "_impulse=" << r.maxContactImpulse << " "
                      << r.name << "_striker_speed_before=" << r.strikerSpeedBeforeContact << " "
                      << r.name << "_target_speed_before=" << r.targetSpeedBeforeContact << " "
                      << r.name << "_striker_speed=" << r.strikerSpeedAfterContact << " "
                      << r.name << "_target_speed=" << r.targetSpeedAfterContact << " "
                      << r.name << "_vehicle_telemetry=" << r.vehicleTelemetry << " ";
        };
        std::cout << "collision-audit ";
        print(rearEnd);
        print(headOn);
        print(sideSwipe);
        std::cout << "rear_ok=" << rearOk << " head_ok=" << headOk << " side_ok=" << sideOk
                  << " side_momentum_preserved=" << sideMomentumPreserved
                  << " mass_comparable=" << massComparable << " mass_ratio=" << massRatio
                  << " role_symmetric=" << roleSymmetric << " jump_clears=" << jumpClears
                  << " rear_striker_speed=" << rearEnd.strikerSpeedAfterContact
                  << " rear_target_speed=" << rearEnd.targetSpeedAfterContact << " rear_pushes=" << rearPushes
                  << " wall_retention=" << wallRetention << " wall_forward=" << wallForwardSpeed << " wall_glances=" << wallGlances
                  << " direct_stop_speed=" << directStopSpeed << " direct_barrier_stops=" << directBarrierStops
                  << " curbs_driveable=" << curbsDriveable << " runoff_driveable=" << runoffDriveable
                  << " visible_barrier_onset=" << visibleBarrierOnset << " footprint_exact=" << footprintExact
                  << " envelope_ordered=" << envelopeOrdered << " min_curb_width_m=" << minCurbWidthMeters
                  << " min_runoff_beyond_curb_m=" << minRunoffBeyondCurbMeters
                  << " min_barrier_beyond_runoff_m=" << minBarrierBeyondRunoffMeters
                  << " max_barrier_width_step_m=" << maxBarrierWidthStepMeters
                  << " boundary_contract_error=" << maxBoundaryContractError
                  << " low_speed_physics_clearance=" << maxSlowPhysicsClearance
                  << " low_speed_render_contact_error=" << maxSlowRenderContactError
                  << " low_speed_tires_grounded=" << lowSpeedTiresGrounded
                  << " runoff_kinds_match=" << runoffKindsMatch
                  << " loose_surface_penalty=" << looseSurfacePenalty
                  << " grass_speed_ratio=" << grassSpeedRatio
                  << " gravel_speed_ratio=" << gravelSpeedRatio
                  << " offroad_actually_slows=" << offRoadActuallySlows
                  << " terrain_ground_continuous=" << terrainGroundContinuous
                  << " terrain_transition_step=" << transitionGroundStep
                  << " terrain_outer_step=" << outerGroundStep
                  << " grid_clear=" << gridClear << " initial_grid_overlap=" << initialGridOverlap
                  << " grid_render_initialized=" << renderStateInitialized
                  << " player_starts_last=" << playerStartsLast
                  << " green_ghost_s=" << minimumGreenGhost
                  << " launch_vehicle_contact_frames=" << launchVehicleContactFrames
                  << " launch_max_overlap=" << launchMaxOverlap
                  << " launch_distance_m=" << launchDistanceMeters
                  << " clean_launch=" << cleanLaunch
                  << " no_automatic_recovery=" << noAutomaticRecovery << "\n";
        return ok;
    }

    bool runSpaControlAudit() {
        track_.rebuild(TrackLayoutId::Spa);
        const TrackCatalogEntry* spaCatalog = catalogEntryForLayout(TrackLayoutId::Spa);
        if (spaCatalog == nullptr) {
            std::cout << "spa-control-audit missing_catalog=1 ok=0\n";
            return false;
        }
        const ArcadeVehicleConfig tuning = selectedTrackTuning(specs_[0]);
        const ArcadeSurface road;
        const float simulationUnits = kTrackSimulationUnitsPerMeter;

        const auto movingKart = [&](float speedScale) {
            ArcadeVehicleState kart;
            kart.vel = {tuning.maxForwardSpeed * speedScale, 0.0f};
            kart.grounded = true;
            syncArcadeTransmissionToSpeed(kart, tuning);
            return kart;
        };

        ArcadeVehicleState gentle = movingKart(0.70f);
        ArcadeVehicleControl gentleControl;
        gentleControl.steer = axisWithDeadzone(0.20f);
        gentleControl.throttle = 0.35f;
        for (int frame = 0; frame < static_cast<int>(1.0f / kFixedDt); ++frame) {
            stepArcadeVehicle(gentle, tuning, gentleControl, road, kFixedDt);
        }
        const float gentleLateralMeters = std::abs(gentle.pos.y) / simulationUnits;

        ArcadeVehicleState fullLock = movingKart(0.70f);
        ArcadeVehicleControl fullLockControl;
        fullLockControl.steer = 1.0f;
        fullLockControl.throttle = 0.35f;
        for (int frame = 0; frame < static_cast<int>(1.0f / kFixedDt); ++frame) {
            stepArcadeVehicle(fullLock, tuning, fullLockControl, road, kFixedDt);
        }
        const float fullLockHeading = std::abs(fullLock.heading);

        ArcadeVehicleState braked = movingKart(0.72f);
        const float initialSpeed = length(braked.vel);
        ArcadeVehicleControl brakeControl;
        brakeControl.steer = 0.70f;
        brakeControl.brake = 1.0f;
        float peakBrakeSlip = 0.0f;
        float peakBrakeYaw = 0.0f;
        for (int frame = 0; frame < static_cast<int>(0.40f / kFixedDt); ++frame) {
            stepArcadeVehicle(braked, tuning, brakeControl, road, kFixedDt);
            peakBrakeSlip = std::max(peakBrakeSlip, std::abs(braked.slipAngle));
            peakBrakeYaw = std::max(peakBrakeYaw, std::abs(braked.yawRate));
        }
        const float brakeHeadingRotation = std::abs(braked.heading);
        const float releaseSpeedRatio = length(braked.vel) / initialSpeed;

        std::array<float, 3> brakeRotation{};
        std::array<float, 3> brakeSpeed{};
        std::array<float, 3> brakeLateralMeters{};
        constexpr std::array<float, 3> kBrakeLevels = {0.25f, 0.60f, 1.0f};
        for (size_t level = 0; level < kBrakeLevels.size(); ++level) {
            ArcadeVehicleState modulation = movingKart(0.72f);
            ArcadeVehicleControl modulationControl;
            modulationControl.steer = 0.70f;
            modulationControl.brake = kBrakeLevels[level];
            for (int frame = 0; frame < static_cast<int>(0.30f / kFixedDt); ++frame) {
                stepArcadeVehicle(modulation, tuning, modulationControl, road, kFixedDt);
            }
            brakeRotation[level] = std::abs(modulation.heading);
            brakeSpeed[level] = length(modulation.vel);
            brakeLateralMeters[level] = std::abs(modulation.pos.y) / simulationUnits;
        }

        ArcadeVehicleState trailBrake = movingKart(0.72f);
        ArcadeVehicleControl trailControl;
        trailControl.automaticShift = false;
        trailControl.steer = 0.70f;
        float trailPeakSlip = 0.0f;
        float trailMinimumYaw = 0.0f;
        constexpr std::array<float, 3> kTrailBrakeLevels = {0.90f, 0.55f, 0.20f};
        for (float brakeLevel : kTrailBrakeLevels) {
            trailControl.brake = brakeLevel;
            for (int frame = 0; frame < static_cast<int>(0.20f / kFixedDt); ++frame) {
                stepArcadeVehicle(trailBrake, tuning, trailControl, road, kFixedDt);
                trailPeakSlip = std::max(trailPeakSlip, std::abs(trailBrake.slipAngle));
                trailMinimumYaw = std::min(trailMinimumYaw, trailBrake.yawRate);
            }
        }
        const float trailHeading = std::abs(trailBrake.heading);
        const float trailLateralMeters = std::abs(trailBrake.pos.y) / simulationUnits;

        ArcadeVehicleState powered = braked;
        ArcadeVehicleState coast = braked;
        ArcadeVehicleState aligned = braked;
        const float releaseSpeed = length(braked.vel);
        aligned.heading = angleOf(aligned.vel);
        aligned.yawRate = 0.0f;
        aligned.brakeSlip = 0.0f;
        aligned.slipAngle = 0.0f;
        aligned.steerSmoothed = 0.0f;
        const Vec2 releasePos = braked.pos;
        const Vec2 releaseLeft{-std::sin(braked.heading), std::cos(braked.heading)};
        ArcadeVehicleControl powerControl;
        powerControl.steer = 0.20f;
        powerControl.throttle = 1.0f;
        ArcadeVehicleControl coastControl = powerControl;
        coastControl.throttle = 0.0f;
        ArcadeVehicleControl alignedControl;
        alignedControl.throttle = 1.0f;
        float poweredSpeedAtPointTwo = releaseSpeed;
        float alignedSpeedAtPointTwo = releaseSpeed;
        for (int frame = 0; frame < static_cast<int>(0.45f / kFixedDt); ++frame) {
            stepArcadeVehicle(powered, tuning, powerControl, road, kFixedDt);
            stepArcadeVehicle(coast, tuning, coastControl, road, kFixedDt);
            stepArcadeVehicle(aligned, tuning, alignedControl, road, kFixedDt);
            if (frame == static_cast<int>(0.20f / kFixedDt) - 1) {
                poweredSpeedAtPointTwo = length(powered.vel);
                alignedSpeedAtPointTwo = length(aligned.vel);
            }
        }

        const float poweredLateralMeters = std::abs(dot(powered.pos - releasePos, releaseLeft)) / simulationUnits;
        const float coastLateralMeters = std::abs(dot(coast.pos - releasePos, releaseLeft)) / simulationUnits;
        const float poweredSeparationMeters = length(powered.pos - coast.pos) / simulationUnits;
        const float poweredAdditionalRotation = std::abs(wrapAngle(powered.heading - braked.heading));
        const float poweredSpeedGainMetersPerSecond = (poweredSpeedAtPointTwo - releaseSpeed) / simulationUnits;
        const float alignedSpeedGainMetersPerSecond = (alignedSpeedAtPointTwo - releaseSpeed) / simulationUnits;
        const float catchSlip = std::abs(powered.slipAngle);
        const float catchYaw = std::abs(powered.yawRate);
        const float coastSlip = std::abs(coast.slipAngle);
        const float coastYaw = std::abs(coast.yawRate);
        const float poweredCatchSpeed = length(powered.vel);
        const float coastCatchSpeed = length(coast.vel);

        powerControl.steer = 0.0f;
        powerControl.throttle = 0.80f;
        for (int frame = 0; frame < static_cast<int>(0.55f / kFixedDt); ++frame) {
            stepArcadeVehicle(powered, tuning, powerControl, road, kFixedDt);
        }

        const float renderedLapLength = track_.totalLength() * trackProgressRenderScale(track_.layout());
        const float expectedRenderedLapLength =
            spaCatalog->targetLengthMeters * kTrackSimulationUnitsPerMeter * kRenderScale;
        const bool renderedScaleValid = std::abs(renderedLapLength - expectedRenderedLapLength) < 0.5f;
        const bool steeringProgressive = gentleLateralMeters < 1.5f && fullLockHeading > 0.25f;
        const bool stableFormulaBraking = peakBrakeSlip < 0.08f && peakBrakeYaw < 0.90f &&
                                          brakeHeadingRotation > 0.05f && brakeHeadingRotation < 0.24f &&
                                          releaseSpeedRatio > 0.65f && releaseSpeedRatio < 0.76f;
        const bool brakeModulates = brakeSpeed[0] > brakeSpeed[1] && brakeSpeed[1] > brakeSpeed[2] &&
                                    brakeRotation[0] > 0.075f && brakeRotation[1] > 0.075f &&
                                    brakeRotation[1] >= brakeRotation[0] * 0.80f &&
                                    brakeRotation[2] > 0.025f && brakeRotation[2] < brakeRotation[1] * 0.65f &&
                                    brakeLateralMeters[1] >= brakeLateralMeters[0] * 0.70f;
        const bool trailBrakeWorks = trailHeading > 0.10f && trailLateralMeters > 0.55f &&
                                     trailPeakSlip < 0.08f && trailMinimumYaw > -0.01f;
        const bool poweredExit = catchSlip <= 0.06f && catchYaw < 0.55f &&
                                 poweredLateralMeters < 3.0f && poweredSeparationMeters < 2.0f &&
                                 poweredCatchSpeed > coastCatchSpeed && poweredAdditionalRotation < 0.35f &&
                                 poweredSpeedGainMetersPerSecond > 0.5f &&
                                 poweredSpeedGainMetersPerSecond <= alignedSpeedGainMetersPerSecond + 0.50f &&
                                 powered.brakeLoad < 0.01f;
        const bool ok = renderedScaleValid && steeringProgressive && stableFormulaBraking && brakeModulates &&
                        trailBrakeWorks && poweredExit;
        std::cout << "spa-control-audit rendered_lap=" << renderedLapLength
                  << " gentle_lateral_m=" << gentleLateralMeters << " full_lock_heading=" << fullLockHeading
                  << " brake_peak_slip=" << peakBrakeSlip << " brake_peak_yaw=" << peakBrakeYaw
                  << " brake_heading=" << brakeHeadingRotation << " brake_speed_ratio=" << releaseSpeedRatio
                  << " brake_modulation=" << brakeRotation[0] << "," << brakeRotation[1] << "," << brakeRotation[2]
                  << " brake_lateral_m=" << brakeLateralMeters[0] << "," << brakeLateralMeters[1] << "," << brakeLateralMeters[2]
                  << " brake_speeds=" << brakeSpeed[0] << "," << brakeSpeed[1] << "," << brakeSpeed[2]
                  << " trail={heading:" << trailHeading << ",lateral_m:" << trailLateralMeters
                  << ",peak_slip:" << trailPeakSlip << ",min_yaw:" << trailMinimumYaw << "}"
                  << " catch_slip=" << catchSlip << "/" << coastSlip << " catch_yaw=" << catchYaw << "/" << coastYaw
                  << " catch_lateral_m=" << poweredLateralMeters << "/" << coastLateralMeters
                  << " catch_separation_m=" << poweredSeparationMeters << " catch_rotation=" << poweredAdditionalRotation
                  << " catch_speed=" << poweredCatchSpeed << "/" << coastCatchSpeed
                  << " launch_gain_mps=" << poweredSpeedGainMetersPerSecond << "/" << alignedSpeedGainMetersPerSecond
                  << " recovery_slip=" << std::abs(powered.slipAngle) << " recovery_yaw=" << std::abs(powered.yawRate)
                  << " recovery_load=" << powered.brakeLoad
                  << " rendered_scale=" << renderedScaleValid << " steering=" << steeringProgressive
                  << " stable_formula_braking=" << stableFormulaBraking << " brake_modulates=" << brakeModulates
                  << " trail_brake_works=" << trailBrakeWorks
                  << " powered_exit=" << poweredExit << " ok=" << ok << "\n";
        return ok;
    }

    float playerRaceScoreForCapture() const {
        return raceFlow_ ? static_cast<float>(raceFlow_->racer(0).continuousTrackProgress * static_cast<double>(track_.totalLength()))
                         : raceScore(karts_[0]);
    }

    float lapLengthForCapture() const { return track_.totalLength(); }
    bool showingResultsForCapture() const { return mode_ == Mode::Results; }
    bool showingGarageForCapture() const { return mode_ == Mode::Garage; }

    bool runTerrainAudit() const {
        constexpr float kGradientLimitDegrees = 40.0f;
        const formula_forge::TrackGradientAudit result = formula_forge::AuditTrackGradients(trackRenderSamples(), kGradientLimitDegrees);
        float maxCenterlineGradient = 0.0f;
        for (const TrackPoint3D& point : track_.samples()) {
            maxCenterlineGradient = std::max(maxCenterlineGradient, std::atan(std::abs(point.grade)) * RAD2DEG);
        }
        const bool ok = result.trianglesAboveLimit == 0 && result.maxGradientDegrees <= kGradientLimitDegrees;
        std::cout << "terrain-audit max_gradient_deg=" << result.maxGradientDegrees
                  << " max_centerline_gradient_deg=" << maxCenterlineGradient
                  << " max_core_gradient_deg=" << result.maxCoreGradientDegrees
                  << " max_road_gradient_deg=" << result.maxRoadGradientDegrees
                  << " max_terrain_gradient_deg=" << result.maxTerrainGradientDegrees
                  << " max_segment_gradient_deg=" << result.maxSegmentGradientDegrees
                  << " max_join_gradient_deg=" << result.maxJoinGradientDegrees
                  << " max_gradient_phase=" << result.progress / (track_.totalLength() * kRenderScale)
                  << " max_gradient_lane=" << result.lane << " triangles_above_40=" << result.trianglesAboveLimit
                  << " core_triangles_above_40=" << result.coreTrianglesAboveLimit
                  << " road_triangles_above_40=" << result.roadTrianglesAboveLimit
                  << " terrain_triangles_above_40=" << result.terrainTrianglesAboveLimit
                  << " segment_triangles_above_40=" << result.segmentTrianglesAboveLimit
                  << " join_triangles_above_40=" << result.joinTrianglesAboveLimit
                  << " ok=" << ok << "\n";
        std::cout << "terrain-audit-bins";
        for (size_t i = 0; i < formula_forge::TrackGradientAudit::kPhaseBinCount; ++i) {
            if (result.phaseTrianglesAboveLimit[i] > 0) {
                std::cout << " " << i << ":" << result.phaseMaxGradientDegrees[i] << "/"
                          << result.phaseTrianglesAboveLimit[i];
            }
        }
        std::cout << "\n";
        return ok;
    }

private:
    void updateAudio(float, const Input3D&, bool driving) {
        ArcadeAudioInput audioInput;
        if (driving && !karts_.empty()) {
            audioInput.shiftAlert = playerShiftRecommended();
        }
        audio_.update(audioInput);
    }

    void buildParticleTexture() {
        constexpr int size = 64;
        Image image = GenImageColor(size, size, BLANK);
        for (int y = 0; y < size; ++y) {
            for (int x = 0; x < size; ++x) {
                const float dx = (static_cast<float>(x) + 0.5f) / size * 2.0f - 1.0f;
                const float dy = (static_cast<float>(y) + 0.5f) / size * 2.0f - 1.0f;
                const float radius = std::sqrt(dx * dx + dy * dy);
                const float alpha = std::pow(std::clamp(1.0f - radius, 0.0f, 1.0f), 1.65f);
                ImageDrawPixel(&image, x, y, {255, 255, 255, static_cast<unsigned char>(alpha * 235.0f)});
            }
        }
        particleTexture_ = LoadTextureFromImage(image);
        UnloadImage(image);
        SetTextureFilter(particleTexture_, TEXTURE_FILTER_BILINEAR);
    }

    void loadMenuTextures() {
        loadingScreenTexture_ = LoadTexture(
            "assets/ui/formula_forge_loading/formula_forge_loading.png");
        if (IsTextureValid(loadingScreenTexture_)) {
            SetTextureFilter(loadingScreenTexture_, TEXTURE_FILTER_BILINEAR);
        }
        garageBackgroundTexture_ = LoadTexture(
            "assets/ui/formula_garage/formula_garage_background.png");
        if (IsTextureValid(garageBackgroundTexture_)) {
            SetTextureFilter(garageBackgroundTexture_, TEXTURE_FILTER_BILINEAR);
        }
    }

    std::vector<ArcadeRacerInput> currentRaceInputs() const {
        std::vector<ArcadeRacerInput> inputs(static_cast<size_t>(activeKartCount()));
        for (int i = 0; i < activeKartCount(); ++i) {
            const Kart3D& kart = karts_[static_cast<size_t>(i)];
            const TrackPoint3D trackPoint = track_.sample(kart.progress);
            inputs[static_cast<size_t>(i)].normalizedTrackProgress = raceLapProgress(kart) / track_.totalLength();
            inputs[static_cast<size_t>(i)].forwardAlignment = dot(fromAngle(kart.heading), trackPoint.tangent);
        }
        return inputs;
    }

    std::vector<formula_forge::TrackRenderSample> trackRenderSamples() const {
        std::vector<formula_forge::TrackRenderSample> samples;
        samples.reserve(track_.samples().size());
        for (const TrackPoint3D& point : track_.samples()) {
            const Vector3 center = lift(track_.roadPoint(point, 0.0f), kTrackSurfaceLift);
            const Vector3 lanePoint = lift(track_.roadPoint(point, 1.0f), kTrackSurfaceLift);
            Vector3 lateral = sub(lanePoint, center);
            lateral.y = 0.0f;
            const float magnitude = std::sqrt(lateral.x * lateral.x + lateral.z * lateral.z);
            lateral = magnitude > 0.0001f ? mul(lateral, 1.0f / magnitude) : Vector3{1.0f, 0.0f, 0.0f};
            samples.push_back({center, lateral, point.width * 0.5f * kRenderScale,
                               point.progress * trackProgressRenderScale(track_.layout()), point.road,
                               point.shoulder, point.natural, point.zone, point.bank * kRenderScale,
                               isMetricCircuit(track_.layout()) ? 0.68f : 1.0f,
                               isMetricCircuit(track_.layout())
                                   ? point.elevation * kRenderScale
                                   : kTerrainSurfaceY,
                               isMetricCircuit(track_.layout())
                                   ? point.elevation * kRenderScale - 0.40f
                                   : kTerrainSurfaceY,
                               isMetricCircuit(track_.layout()) ? 65.0f : 0.0f,
                               isMetricCircuit(track_.layout())});
        }
        return samples;
    }

    void buildTrackRenderer() {
        const std::vector<formula_forge::TrackRenderSample> samples = trackRenderSamples();
        trackRenderer_.build(samples, renderer_.worldShader());
    }

    const MapSpec3D& selectedMap() const { return kMaps[static_cast<size_t>(selectedMap_)]; }

    bool isTimeTrial() const { return selectedSession_ == formula_forge::ui::GameModeOption::TimeTrial; }
    int activeKartCount() const { return isTimeTrial() ? 1 : kKartCount; }

    bool playerShiftRecommended() const {
        if (karts_.empty()) {
            return false;
        }
        const Kart3D& player = karts_[0];
        constexpr float kShiftAlertLead = 0.06f;
        return player.shiftTimer <= 0.0f &&
               player.gear < static_cast<int>(player.tuning.gearRedlineSpeedRatios.size()) &&
               player.engineRpmNormalized >= player.tuning.automaticUpshiftRpm - kShiftAlertLead;
    }
    ArcadeVehicleConfig selectedTrackTuning(const KartSpec3D& spec) const {
        ArcadeVehicleConfig tuning = tuningForSpec(spec);
        const float kphPerUnit = speedKphPerSimulationUnit(track_.layout());
        const float metricKphPerUnit = 3.6f / kTrackSimulationUnitsPerMeter;
        const float targetTopSpeedKph = std::clamp(318.0f + (spec.maxSpeed - 198.0f) * 0.55f, 305.0f, 330.0f);
        const float accelerationScale = std::pow(spec.accel / 258.0f, 0.22f);
        const float brakingScale = std::pow(spec.brake / 214.0f, 0.25f);
        tuning.maxForwardSpeed = targetTopSpeedKph / kphPerUnit;
        tuning.engineAcceleration = 190.0f * metricKphPerUnit / kphPerUnit * accelerationScale;
        tuning.launchAccelerationBonus = 5.0f * metricKphPerUnit / kphPerUnit * accelerationScale;
        tuning.brakeDeceleration = 4.65f * kStandardGravityMetersPerSecondSquared * 3.6f /
                                   kphPerUnit * brakingScale;
        tuning.brakeLowSpeedScale = 0.28f;
        tuning.brakeFullEffectSpeed = 0.72f;
        tuning.brakeSpeedCurveExponent = 2.0f;
        tuning.rollingResistance = 3.2f * metricKphPerUnit / kphPerUnit;
        tuning.aerodynamicDrag = 0.0000265f * kphPerUnit / metricKphPerUnit;
        tuning.engineBrakingAcceleration = 0.20f * kStandardGravityMetersPerSecondSquared * 3.6f /
                                            kphPerUnit;
        tuning.maxSteerLowSpeed = 0.32f;
        tuning.maxSteerHighSpeed = 0.075f;
        tuning.maxYawRateLowSpeed = 1.55f;
        tuning.maxYawRateHighSpeed = isMetricCircuit(track_.layout()) ? 1.20f : 0.42f;
        tuning.brakeLoadResponse = 20.0f;
        tuning.brakeReleaseResponse = 24.0f;
        tuning.brakeOversteerMinSpeed = tuning.maxForwardSpeed * 0.18f;
        tuning.brakeOversteerFullSpeed = tuning.maxForwardSpeed;
        tuning.brakeOversteerSteerThreshold = 0.18f;
        tuning.brakeOversteerYawGain = 0.24f;
        tuning.brakeYawLimitScale = 1.03f;
        tuning.brakeOversteerSlip = 0.035f;
        tuning.brakeSlipResponse = 14.0f;
        tuning.brakeSlipRecovery = 24.0f;
        tuning.throttleCatchStrength = 0.0f;
        tuning.accelerationGripUsageScale = 0.82f;
        tuning.lateralGripAcceleration = 1.78f * kStandardGravityMetersPerSecondSquared * 3.6f /
                                         kphPerUnit * spec.grip;
        if (isMetricCircuit(track_.layout())) {
            tuning.downforceGripGain = 1.65f;
            tuning.tireLimitedYawScale = 0.97f;
            tuning.automaticBrakingDownshiftRpm = 0.88f;
            tuning.downshiftOverrevRpm = 1.00f;
            tuning.manualDownshiftOverrevRpm = 1.08f;
            tuning.gearRedlineSpeedRatios = {0.225f, 0.280f, 0.400f, 0.550f, 0.700f, 0.840f, 0.940f, 1.060f};
        } else {
            tuning.downforceGripGain = 1.20f;
            tuning.tireLimitedYawScale = 0.88f;
        }
        tuning.combinedGripExponent = 2.20f;
        tuning.combinedGripFloor = 0.30f;
        tuning.trailBrakeTurnInGain = 0.16f;
        tuning.steerResponse *= 0.90f;
        tuning.steerReturnResponse *= 1.08f;
        return tuning;
    }
    std::string sessionEventName() const {
        return isTimeTrial() ? std::string(selectedMap().name) + " TIME TRIAL" : selectedMap().eventName;
    }

    void activateSelectedMap() {
        if (track_.layout() == selectedMap().layout) {
            return;
        }
        track_.rebuild(selectedMap().layout);
        buildTrackRenderer();
    }

    void updateGarage(const Input3D& input, bool hasController) {
        garageSpin_ += kFixedDt;
        const int previousMap = selectedMap_;
        const int horizontal = (input.right || input.pageRight || input.triggerRight ? 1 : 0) -
                               (input.left || input.pageLeft || input.triggerLeft ? 1 : 0);
        const int vertical = (input.down ? 1 : 0) - (input.up ? 1 : 0);
        const auto wrapChoice = [](int& value, int count, int direction) {
            if (direction != 0 && count > 0) {
                value = (value + direction + count) % count;
            }
        };
        switch (selectionStage_) {
            case formula_forge::ui::SelectionStage::Mode:
                if (horizontal != 0 || vertical != 0) {
                    selectedSession_ = selectedSession_ == formula_forge::ui::GameModeOption::Race
                                           ? formula_forge::ui::GameModeOption::TimeTrial
                                           : formula_forge::ui::GameModeOption::Race;
                    selectedLapOption_ = isTimeTrial() ? kLapOptionCount - 1 : 0;
                }
                break;
            case formula_forge::ui::SelectionStage::Car:
                wrapChoice(selectedCar_, static_cast<int>(specs_.size()), horizontal);
                break;
            case formula_forge::ui::SelectionStage::Map:
                wrapChoice(selectedMap_, static_cast<int>(kMaps.size()), horizontal);
                wrapChoice(selectedLapOption_, kLapOptionCount, vertical);
                break;
        }
        if (selectedMap_ != previousMap) {
            activateSelectedMap();
            resetRace();
        }
        syncGaragePreview();

        if (input.b || input.back) {
            if (selectionStage_ == formula_forge::ui::SelectionStage::Map) {
                selectionStage_ = formula_forge::ui::SelectionStage::Car;
            } else if (selectionStage_ == formula_forge::ui::SelectionStage::Car) {
                selectionStage_ = formula_forge::ui::SelectionStage::Mode;
            }
            return;
        }
        if ((input.a || input.start) && hasController) {
            if (selectionStage_ == formula_forge::ui::SelectionStage::Map) {
                startRace();
            } else if (selectionStage_ == formula_forge::ui::SelectionStage::Mode) {
                selectionStage_ = formula_forge::ui::SelectionStage::Car;
            } else {
                selectionStage_ = formula_forge::ui::SelectionStage::Map;
            }
        }
    }

    void syncGaragePreview() {
        if (karts_.empty()) {
            return;
        }
        Kart3D& preview = karts_[0];
        preview.spec = specs_[static_cast<size_t>(selectedCar_)];
        preview.tuning = selectedTrackTuning(preview.spec);
        preview.racer = racers_[static_cast<size_t>(selectedRacer_)];
    }

    void goHome() {
        mode_ = Mode::Garage;
        selectionStage_ = formula_forge::ui::SelectionStage::Mode;
        pauseAction_ = formula_forge::ui::PauseAction::Resume;
        resultsAction_ = formula_forge::ui::ResultsAction::Replay;
        resultCount_ = 0;
        resetRace();
        syncGaragePreview();
    }

    void updatePause(const Input3D& input) {
        if (input.back || input.b || input.start) {
            mode_ = Mode::Race;
            return;
        }
        const int direction = (input.down || input.right ? 1 : 0) - (input.up || input.left ? 1 : 0);
        if (direction != 0) {
            const int count = 3;
            pauseAction_ = static_cast<formula_forge::ui::PauseAction>(
                (static_cast<int>(pauseAction_) + direction + count) % count);
        }
        if (!input.a) {
            return;
        }
        switch (pauseAction_) {
            case formula_forge::ui::PauseAction::Resume:
                mode_ = Mode::Race;
                break;
            case formula_forge::ui::PauseAction::Restart:
                startRace();
                break;
            case formula_forge::ui::PauseAction::Home:
                goHome();
                break;
            default:
                mode_ = Mode::Race;
                break;
        }
    }

    void updateResults(const Input3D& input) {
        if (input.left || input.up) {
            resultsAction_ = formula_forge::ui::ResultsAction::Replay;
        }
        if (input.right || input.down) {
            resultsAction_ = formula_forge::ui::ResultsAction::Home;
        }
        if (input.b || input.back) {
            goHome();
            return;
        }
        if (input.a || input.start) {
            if (resultsAction_ == formula_forge::ui::ResultsAction::Replay) {
                startRace();
            } else {
                goHome();
            }
        }
    }

    void updateGarageCamera(float dt) {
        (void)dt;
        const TrackPoint3D start = track_.sample(track_.startProgress() + 52.0f);
        const KartSpec3D& previewSpec = specs_[static_cast<size_t>(selectedCar_)];
        const float orbit = std::sin(garageSpin_ * 0.32f) * 3.0f;
        const float cameraDistance = std::max(105.0f, previewSpec.length * 1.55f);
        const float cameraSide = std::max(18.0f, previewSpec.width * 0.55f);
        const float cameraHeight = std::max(30.0f, previewSpec.height * 1.70f);
        const float targetHeight = std::max(10.0f, previewSpec.height * 0.90f);
        camera_.position = toWorld(start.pos - start.tangent * cameraDistance +
                                       start.normal * (cameraSide + orbit),
                                   bankedElevation(start, cameraSide) + cameraHeight);
        camera_.target = toWorld(start.pos + start.tangent * 4.0f,
                                 bankedElevation(start, 0.0f) + targetHeight);
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = 44.0f;
        camera_.projection = CAMERA_PERSPECTIVE;
    }

    void resetRace() {
        karts_.clear();
        const float startProgress = track_.startProgress();
        float longestCar = 0.0f;
        float widestCar = 0.0f;
        for (const KartSpec3D& spec : specs_) {
            longestCar = std::max(longestCar, spec.length);
            widestCar = std::max(widestCar, spec.width);
        }
        const float unitsPerMeter = isMetricCircuit(track_.layout()) ? kTrackSimulationUnitsPerMeter : 1.0f;
        // Track progress is measured in meters even though vehicle dimensions
        // and lateral positions use simulation units.
        const float firstRowInsetMeters = longestCar / unitsPerMeter * 0.5f + kGridFirstRowClearanceMeters;
        const float rowSpacingMeters =
            longestCar / unitsPerMeter +
            gridSlotGapMeters(track_.layout());
        const float columnOffset = std::max(widestCar * 0.95f, 2.0f * unitsPerMeter);
        for (int i = 0; i < kKartCount; ++i) {
            Kart3D kart;
            int specIndex = selectedCar_;
            if (i > 0) {
                // Fill the AI field from every unselected entry, so the
                // player's chosen livery is replaced rather than duplicated.
                specIndex = i - 1;
                if (specIndex >= selectedCar_) {
                    ++specIndex;
                }
            }
            kart.spec = specs_[static_cast<size_t>(specIndex)];
            kart.tuning = selectedTrackTuning(kart.spec);
            kart.racer = racers_[static_cast<size_t>(i == 0 ? selectedRacer_ : i)];
            // The player always takes the final grid slot. AI indices retain
            // their stable simulation identities while filling slots 1-10.
            const int gridSlot = isTimeTrial() ? 0 : (i == 0 ? kKartCount - 1 : i - 1);
            const float stagger = isTimeTrial() && i == 0
                                      ? startProgress
                                      : startProgress - firstRowInsetMeters -
                                            static_cast<float>(gridSlot) * rowSpacingMeters;
            const TrackPoint3D grid = track_.sample(stagger);
            const float lane = isTimeTrial() && i == 0
                                   ? 0.0f
                                   : std::clamp(runtimeGridSideForSlot(gridSlot) * columnOffset,
                                                -roadCenterLimit(kart, grid), roadCenterLimit(kart, grid));
            kart.pos = grid.pos + grid.normal * lane;
            kart.heading = angleOf(grid.tangent);
            kart.vel = {};
            kart.elevation = bankedElevation(grid, lane);
            kart.verticalSpeed = 0.0f;
            kart.grounded = true;
            kart.nearest = track_.nearestIndex(kart.pos);
            kart.progress = track_.pointAtIndex(kart.nearest).progress;
            kart.previousProgress = kart.progress;
            kart.previousRenderPos = kart.pos;
            kart.previousRenderElevation = kart.elevation;
            kart.previousRenderHeading = kart.heading;
            kart.previousRenderProgress = kart.progress;
            kart.lap = -1;
            kart.lane = lane;
            kart.aiGridLane = lane;
            kart.aiTempo = 1.110f - static_cast<float>(std::max(0, i - 1)) * 0.006f;
            kart.drsAvailable = isTimeTrial();
            kart.drsActive = isTimeTrial();
            kart.ghostTimer = 0.0f;
            karts_.push_back(kart);
        }
        if (!karts_.empty()) {
            buildAiLapPlan(karts_[0]);
        }
        particles_.clear();
        raceTime_ = 0.0f;
        lapStartTime_ = 0.0f;
        lastLapTime_ = 0.0f;
        bestLapTime_ = 0.0f;
        hasBestLap_ = false;
        finishTime_ = 0.0f;
        countdownGoTimer_ = 0.0f;
        raceFinished_ = false;
        resultCount_ = 0;
        playerPosition_ = isTimeTrial() ? 1 : activeKartCount();
        ArcadeRaceConfig raceConfig;
        raceConfig.lapCount = static_cast<uint32_t>(std::max(1, targetLaps()));
        raceConfig.infiniteLaps = targetLaps() == kInfiniteLaps;
        raceConfig.countdownSeconds = 3.0f;
        if (isMetricCircuit(track_.layout())) {
            raceConfig.checkpointGates = {{0.0f, 0.0f}, {0.10f, 0.10f}, {0.21f, 0.21f}, {0.32f, 0.32f},
                                          {0.43f, 0.43f}, {0.54f, 0.54f}, {0.65f, 0.65f}, {0.76f, 0.76f},
                                          {0.87f, 0.87f}};
        } else {
            raceConfig.checkpointGates = {{0.0f, 0.0f}, {0.18f, 0.18f}, {0.38f, 0.38f},
                                          {0.58f, 0.58f}, {0.78f, 0.78f}};
        }
        raceFlow_ = std::make_unique<ArcadeRaceFlow>(raceConfig, static_cast<size_t>(activeKartCount()));
        const auto inputs = currentRaceInputs();
        raceFlow_->update(0.0f, inputs);
        raceFlow_->beginCountdown();
        updateRaceOrder();
        const Vector3 focus = track_.roadPoint(track_.sample(startProgress), 0.0f);
        camera_.position = add(focus, {0.0f, 5.0f, -16.0f});
        camera_.target = focus;
        camera_.up = {0.0f, 1.0f, 0.0f};
        camera_.fovy = 60.0f;
        camera_.projection = CAMERA_PERSPECTIVE;
        previousCamera_ = camera_;
    }

    void assignAiLaunchProfiles() {
        if (isTimeTrial()) {
            return;
        }
        std::bernoulli_distribution slowStart(
            0.40);
        std::normal_distribution<float>
            slowThrottle(0.72f, 0.07f);
        std::normal_distribution<float>
            slowDuration(1.35f, 0.25f);
        for (int index = 1;
             index < activeKartCount(); ++index) {
            Kart3D& kart =
                karts_[static_cast<size_t>(index)];
            kart.aiLaunchElapsed = 0.0f;
            if (!slowStart(raceRandom_)) {
                kart.aiLaunchThrottleScale = 1.0f;
                kart.aiLaunchDuration = 0.0f;
                continue;
            }
            kart.aiLaunchThrottleScale =
                std::clamp(
                    slowThrottle(raceRandom_),
                    0.55f, 0.88f);
            kart.aiLaunchDuration =
                std::clamp(
                    slowDuration(raceRandom_),
                    0.80f, 2.10f);
        }
    }

    void updateProgress(Kart3D& kart) {
        const float oldRaceProgress = progressAhead(track_.startProgress(), kart.progress, track_.totalLength());
        kart.previousProgress = kart.progress;
        if (isMetricCircuit(track_.layout())) {
            const TrackProjection3D projection = track_.projectNear(kart.pos, kart.nearest, 6);
            kart.progress = projection.progress;
            kart.nearest = projection.nearest;
            kart.lane = projection.lane;
        } else {
            kart.nearest = track_.nearestIndexNear(kart.pos, kart.nearest, 4);
            const TrackPoint3D& center = track_.pointAtIndex(kart.nearest);
            kart.progress = center.progress;
            kart.lane = dot(kart.pos - center.pos, center.normal);
        }
        const float newRaceProgress = progressAhead(track_.startProgress(), kart.progress, track_.totalLength());
        if (oldRaceProgress > track_.totalLength() * 0.70f && newRaceProgress < track_.totalLength() * 0.30f) {
            ++kart.lap;
        } else if (oldRaceProgress < track_.totalLength() * 0.30f && newRaceProgress > track_.totalLength() * 0.70f &&
                   kart.lap > -1) {
            --kart.lap;
        }
    }

    float drsTopSpeedExtra() const {
        return kDrsTopSpeedExtraKph /
               speedKphPerSimulationUnit(track_.layout());
    }

    float effectiveTopSpeed(const Kart3D& kart) const {
        return kart.tuning.maxForwardSpeed +
               (kart.drsActive ? drsTopSpeedExtra() : 0.0f);
    }

    void updateDrsDetectionLine() {
        if (!raceFlow_) {
            return;
        }
        if (isTimeTrial()) {
            for (Kart3D& kart : karts_) {
                kart.drsAvailable = true;
            }
            return;
        }

        struct DetectionCrossing {
            int index = -1;
            int lap = -1;
        };
        std::array<DetectionCrossing, kKartCount> crossings{};
        int crossingCount = 0;
        const float detectionTime =
            static_cast<float>(raceFlow_->raceTimeSeconds());
        for (int index = 0; index < activeKartCount();
             ++index) {
            Kart3D& kart =
                karts_[static_cast<size_t>(index)];
            const double continuous =
                raceFlow_->racer(
                    static_cast<size_t>(index))
                    .continuousTrackProgress;
            if (continuous < 0.0) {
                continue;
            }
            const int detectionLap =
                static_cast<int>(
                    std::floor(continuous + 0.000001));
            if (detectionLap <=
                kart.drsLastDetectionLap) {
                continue;
            }
            kart.drsLastDetectionLap = detectionLap;
            kart.drsLastDetectionTime = detectionTime;
            crossings[static_cast<size_t>(
                crossingCount++)] = {index, detectionLap};
        }

        for (int crossingIndex = 0;
             crossingIndex < crossingCount;
             ++crossingIndex) {
            const DetectionCrossing crossing =
                crossings[static_cast<size_t>(
                    crossingIndex)];
            Kart3D& kart =
                karts_[static_cast<size_t>(
                    crossing.index)];
            const double kartProgress =
                raceFlow_->racer(
                    static_cast<size_t>(
                        crossing.index))
                    .continuousTrackProgress;
            float nearestGapSeconds =
                std::numeric_limits<float>::max();
            for (int otherIndex = 0;
                 otherIndex < activeKartCount();
                 ++otherIndex) {
                if (otherIndex == crossing.index) {
                    continue;
                }
                const Kart3D& other =
                    karts_[static_cast<size_t>(
                        otherIndex)];
                if (other.drsLastDetectionLap !=
                    crossing.lap ||
                    other.drsLastDetectionTime >
                        kart.drsLastDetectionTime +
                            kFixedDt * 0.5f) {
                    continue;
                }
                const double otherProgress =
                    raceFlow_->racer(
                        static_cast<size_t>(
                            otherIndex))
                        .continuousTrackProgress;
                const float gapSeconds =
                    kart.drsLastDetectionTime -
                    other.drsLastDetectionTime;
                const bool crossedEarlier =
                    gapSeconds > kFixedDt * 0.5f;
                if (!crossedEarlier &&
                    otherProgress <= kartProgress) {
                    continue;
                }
                nearestGapSeconds =
                    std::min(nearestGapSeconds,
                             std::max(0.0f,
                                      gapSeconds));
            }
            kart.drsAvailable =
                nearestGapSeconds <=
                kDrsDetectionMaximumGapSeconds +
                    kFixedDt;
            // Each detection result arms a new lap; the driver must open it
            // again. AI drivers do that automatically on their next update.
            kart.drsActive = false;
        }
    }

    void updatePlayer(Kart3D& kart, const Input3D& input, float dt) {
        const Input3D canonical =
            canonicalPlayerInput(input);
        if (isTimeTrial()) {
            kart.drsAvailable = true;
            kart.drsActive = canonical.brake <= 0.01f;
        } else if (canonical.brake > 0.01f) {
            kart.drsActive = false;
        } else if (input.a && kart.drsAvailable) {
            kart.drsActive = true;
        }
        integrateKart(kart, canonical, dt);
    }

    float raceLapProgress(const Kart3D& kart) const {
        return progressAhead(track_.startProgress(), kart.progress, track_.totalLength());
    }

    float raceScore(const Kart3D& kart) const { return static_cast<float>(kart.lap) * track_.totalLength() + raceLapProgress(kart); }

    int targetLaps() const {
        return kLapOptions[static_cast<size_t>(selectedLapOption_)];
    }

    const char* lapOptionText(int index) const {
        const int laps = kLapOptions[static_cast<size_t>(index)];
        switch (laps) {
            case 2:
                return "2";
            case 5:
                return "5";
            case 10:
                return "10";
            default:
                return "INF";
        }
    }

    void updateFinishState() {
        const int laps = targetLaps();
        if (isTimeTrial() && laps == kInfiniteLaps) {
            return;
        }
        const bool validatedFinish = raceFlow_ && raceFlow_->racer(0).finished;
        const bool legacyFinish = !raceFlow_ && laps != kInfiniteLaps && karts_[0].lap >= laps;
        if (!raceFinished_ && (validatedFinish || legacyFinish)) {
            raceFinished_ = true;
            finishTime_ = validatedFinish ? static_cast<float>(raceFlow_->racer(0).finishTimeSeconds) : raceTime_;
            karts_[0].vel *= 0.35f;
            karts_[0].boostTimer = 0.0f;
            karts_[0].drifting = false;
            if (isTimeTrial()) {
                buildTimeTrialResult();
            } else {
                buildRaceResults();
            }
            mode_ = Mode::Results;
        }
    }

    void buildTimeTrialResult() {
        resultCount_ = 1;
        results_[0] = {0, 1, finishTime_, std::max(1, targetLaps())};
        resultsAction_ = formula_forge::ui::ResultsAction::Replay;
    }

    void buildRaceResults() {
        const int winningLaps = std::max(1, targetLaps());
        std::array<std::pair<float, int>, kKartCount> projected{};
        for (int i = 0; i < kKartCount; ++i) {
            float time = finishTime_;
            if (raceFlow_) {
                const ArcadeRacerRaceState& state = raceFlow_->racer(static_cast<size_t>(i));
                if (state.finished && state.finishTimeSeconds >= 0.0) {
                    time = static_cast<float>(state.finishTimeSeconds);
                } else {
                    const float progress = static_cast<float>(std::max(0.0, state.validatedRaceProgress));
                    const float elapsedPerLap = raceTime_ / std::max(0.55f, progress);
                    const float expectedLap = std::clamp(elapsedPerLap, 38.0f, 72.0f);
                    const float remainingLaps = std::max(0.0f, static_cast<float>(winningLaps) - progress);
                    time = std::max(finishTime_ + 0.8f + static_cast<float>(i) * 0.21f,
                                    raceTime_ + remainingLaps * expectedLap);
                }
            } else if (i > 0) {
                time += 1.2f + static_cast<float>(i) * 0.8f;
            }
            projected[static_cast<size_t>(i)] = {time, i};
        }
        std::sort(projected.begin(), projected.end(), [](const auto& a, const auto& b) {
            return a.first == b.first ? a.second < b.second : a.first < b.first;
        });
        resultCount_ = kKartCount;
        for (int place = 0; place < kKartCount; ++place) {
            results_[static_cast<size_t>(place)] = {
                projected[static_cast<size_t>(place)].second,
                place + 1,
                projected[static_cast<size_t>(place)].first,
                winningLaps,
            };
        }
    }

    static float orderScore(const std::array<std::pair<float, int>, kKartCount>& order, int kartIndex) {
        for (const auto& entry : order) {
            if (entry.second == kartIndex) {
                return entry.first;
            }
        }
        return 0.0f;
    }

    float smoothedSignedCurvature(float progress) const {
        return track_.sample(progress - 54.0f).signedCurvature * 0.18f + track_.sample(progress).signedCurvature * 0.64f +
               track_.sample(progress + 54.0f).signedCurvature * 0.18f;
    }

    float racingLaneForProgress(const Kart3D& kart, float progress) const {
        const TrackPoint3D point = track_.sample(progress);
        if (isMetricCircuit(track_.layout())) {
            return plannedAiLane(progress);
        }
        const float phase = progressAhead(track_.startProgress(), progress, track_.totalLength()) / track_.totalLength();
        const float target = sampleWrappedProfile(kAttackingReferenceLane, phase);
        return std::clamp(target, -hardBoundaryLaneLimit(kart, point) + 5.0f, hardBoundaryLaneLimit(kart, point) - 5.0f);
    }

    float referenceAiSpeed(const Kart3D& kart, float progress) const {
        const float phase = progressAhead(track_.startProgress(), progress, track_.totalLength()) / track_.totalLength();
        const float carScale = kart.spec.maxSpeed / specs_[0].maxSpeed;
        return sampleWrappedProfile(kAttackingReferenceSpeed, phase) * carScale * kart.aiTempo;
    }

    float physicalSpeedForCurvature(const Kart3D& kart, const TrackPoint3D& point,
                                    float curvaturePerMeter, float lane = 0.0f,
                                    int searchIterations = 14,
                                    float topSpeedExtra = 0.0f) const {
        const float speedLimit =
            kart.tuning.maxForwardSpeed +
            std::max(0.0f, topSpeedExtra);
        if (curvaturePerMeter <= 0.00001f) {
            return speedLimit;
        }

        const float maxSpeedMetersPerSecond =
            speedLimit /
            kTrackSimulationUnitsPerMeter;
        const float baseMaxSpeedMetersPerSecond =
            kart.tuning.maxForwardSpeed /
            kTrackSimulationUnitsPerMeter;
        float lowerSpeed = 0.0f;
        float upperSpeed = maxSpeedMetersPerSecond;
        for (int iteration = 0; iteration < searchIterations; ++iteration) {
            const float candidateSpeed = (lowerSpeed + upperSpeed) * 0.5f;
            const float normalizedSpeed =
                candidateSpeed /
                std::max(1.0f,
                         baseMaxSpeedMetersPerSecond);
            Kart3D predictedKart = kart;
            predictedKart.progress = point.progress;
            predictedKart.lane = lane;
            predictedKart.vel = point.tangent * (candidateSpeed * kTrackSimulationUnitsPerMeter);
            const float surfaceGrip = formulaCornerGripScale(predictedKart, point);
            const float longitudinalUsage = std::clamp(
                kart.tuning.engineAcceleration * kart.tuning.accelerationGripUsageScale /
                    std::max(1.0f, kart.tuning.brakeDeceleration),
                0.0f, 1.0f);
            const float gripPower = std::max(1.1f, kart.tuning.combinedGripExponent);
            const float gripRemaining = std::max(0.0f, 1.0f - std::pow(longitudinalUsage, gripPower));
            const float combinedGrip = std::max(kart.tuning.combinedGripFloor,
                                                std::pow(gripRemaining, 1.0f / gripPower));
            const float downforceGrip = 1.0f + kart.tuning.downforceGripGain * normalizedSpeed * normalizedSpeed;
            const float availableAcceleration = kart.tuning.lateralGripAcceleration /
                                                    kTrackSimulationUnitsPerMeter *
                                                surfaceGrip * downforceGrip * combinedGrip *
                                                kart.tuning.tireLimitedYawScale;
            const float requiredAcceleration = candidateSpeed * candidateSpeed * curvaturePerMeter;
            const float yawLimit = lerp(kart.tuning.maxYawRateLowSpeed,
                                        kart.tuning.maxYawRateHighSpeed,
                                        std::clamp(normalizedSpeed, 0.0f, 1.0f));
            const float requiredYawRate = candidateSpeed * curvaturePerMeter;
            const bool withinTires = requiredAcceleration <= availableAcceleration * 0.985f;
            const bool withinSteering = requiredYawRate <= yawLimit * 0.985f;
            if (withinTires && withinSteering) {
                lowerSpeed = candidateSpeed;
            } else {
                upperSpeed = candidateSpeed;
            }
        }
        return lowerSpeed * kTrackSimulationUnitsPerMeter;
    }

    float physicalCornerSpeed(
        const Kart3D& kart, float progress,
        float topSpeedExtra = 0.0f) const {
        const TrackPoint3D point = track_.sample(progress);
        const float sampleSpacingMeters = track_.totalLength() / static_cast<float>(track_.sampleCount());
        const float curvaturePerMeter = point.curvature / std::max(0.01f, 16.0f * sampleSpacingMeters);
        return physicalSpeedForCurvature(
            kart, point, curvaturePerMeter, 0.0f,
            14, topSpeedExtra);
    }

    struct AiLapEvaluation {
        float seconds = std::numeric_limits<float>::max();
        std::vector<float> speeds;
        std::vector<float> cornerSpeeds;
    };

    AiLapEvaluation evaluateAiLapTrajectory(const Kart3D& kart,
                                            const std::vector<float>& lanes,
                                            bool accelerationEnvelope = true,
                                            float speedReserve = 0.995f,
                                            float brakePlanningFraction = 0.88f,
                                            float topSpeedExtra = 0.0f) const {
        const int count = track_.sampleCount();
        const float speedLimit =
            kart.tuning.maxForwardSpeed +
            std::max(0.0f, topSpeedExtra);
        std::vector<Vec2> positions(static_cast<size_t>(count));
        std::vector<Vec2> tangents(static_cast<size_t>(count));
        std::vector<float> segmentLengths(static_cast<size_t>(count));
        for (int i = 0; i < count; ++i) {
            const TrackPoint3D& point = track_.pointAtIndex(i);
            positions[static_cast<size_t>(i)] =
                point.pos + point.normal * lanes[static_cast<size_t>(i)];
        }
        for (int i = 0; i < count; ++i) {
            const int previous = (i - 3 + count) % count;
            const int next = (i + 3) % count;
            tangents[static_cast<size_t>(i)] =
                normalize(positions[static_cast<size_t>(next)] -
                          positions[static_cast<size_t>(previous)]);
            segmentLengths[static_cast<size_t>(i)] =
                length(positions[static_cast<size_t>((i + 1) % count)] -
                       positions[static_cast<size_t>(i)]);
        }

        AiLapEvaluation evaluation;
        evaluation.speeds.resize(static_cast<size_t>(count),
                                 speedLimit);
        for (int i = 0; i < count; ++i) {
            constexpr int curvatureSpan = 8;
            const int before = (i - curvatureSpan + count) % count;
            const int after = (i + curvatureSpan) % count;
            const float signedTurn =
                wrapAngle(angleOf(tangents[static_cast<size_t>(after)]) -
                          angleOf(tangents[static_cast<size_t>(before)]));
            float pathSpanMeters = 0.0f;
            for (int offset = -curvatureSpan; offset < curvatureSpan; ++offset) {
                const int segment = (i + offset + count) % count;
                pathSpanMeters +=
                    segmentLengths[static_cast<size_t>(segment)] /
                    kTrackSimulationUnitsPerMeter;
            }
            const float curvaturePerMeter =
                std::abs(signedTurn) / std::max(0.01f, pathSpanMeters);
            const TrackPoint3D& point = track_.pointAtIndex(i);
            evaluation.speeds[static_cast<size_t>(i)] =
                std::min(speedLimit,
                         physicalSpeedForCurvature(
                             kart, point, curvaturePerMeter,
                             lanes[static_cast<size_t>(i)], 9,
                             topSpeedExtra) *
                             speedReserve);
        }
        evaluation.cornerSpeeds = evaluation.speeds;

        // A minimum-time spatial profile must be reachable in both directions:
        // backward passes establish the latest possible braking, while forward
        // passes cap acceleration away from each apex.
        const float planningDeceleration =
            kart.tuning.brakeDeceleration * brakePlanningFraction;
        for (int pass = 0; pass < 4; ++pass) {
            for (int i = count - 1; i >= 0; --i) {
                const int next = (i + 1) % count;
                const float nextSpeed =
                    evaluation.speeds[static_cast<size_t>(next)];
                const float brakingLimit = std::sqrt(
                    nextSpeed * nextSpeed +
                    2.0f * planningDeceleration *
                        segmentLengths[static_cast<size_t>(i)]);
                evaluation.speeds[static_cast<size_t>(i)] =
                    std::min(evaluation.speeds[static_cast<size_t>(i)],
                             brakingLimit);
            }
            if (accelerationEnvelope) {
                for (int i = 0; i < count; ++i) {
                    const int next = (i + 1) % count;
                    const float speed =
                        evaluation.speeds[static_cast<size_t>(i)];
                    const float netAcceleration = std::max(
                        1.0f,
                        kart.tuning.engineAcceleration * 0.88f -
                            kart.tuning.rollingResistance -
                            speed * speed *
                                kart.tuning.aerodynamicDrag);
                    const float accelerationLimit = std::sqrt(
                        speed * speed +
                        2.0f * netAcceleration *
                            segmentLengths[static_cast<size_t>(i)]);
                    evaluation.speeds[static_cast<size_t>(next)] =
                        std::min(
                            evaluation.speeds[static_cast<size_t>(next)],
                            accelerationLimit);
                }
            }
        }

        evaluation.seconds = 0.0f;
        for (int i = 0; i < count; ++i) {
            const int next = (i + 1) % count;
            evaluation.seconds +=
                2.0f * segmentLengths[static_cast<size_t>(i)] /
                std::max(1.0f,
                         evaluation.speeds[static_cast<size_t>(i)] +
                             evaluation.speeds[static_cast<size_t>(next)]);
        }
        return evaluation;
    }

    MonzaOptimizationReplay replayMonzaOptimizationCandidate(
        const MonzaOptimizationCandidate& candidate) {
        particles_.clear();
        track_.rebuild(TrackLayoutId::Monza);
        aiOptimizationProfileActive_ = true;
        aiOptimizationProfile_ = candidate.profile;
        aiOptimizationLaneOffsetsMeters_ =
            candidate.laneOffsetsMeters;

        const float startProgress = track_.startProgress();
        const TrackPoint3D start =
            track_.sample(startProgress);
        Kart3D kart;
        kart.spec = specs_[0];
        kart.tuning = selectedTrackTuning(kart.spec);
        kart.racer = racers_[0];
        kart.pos = start.pos;
        kart.heading = angleOf(start.tangent);
        kart.elevation = bankedElevation(start, 0.0f);
        kart.grounded = true;
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.progress =
            track_.pointAtIndex(kart.nearest).progress;
        kart.previousProgress = kart.progress;
        kart.aiTempo = 1.110f;
        kart.ghostTimer = 300.0f;
        buildAiLapPlan(kart);

        MonzaOptimizationReplay result;
        float lapProgress = 0.0f;
        int completedLaps = 0;
        int flyingLapStartFrame = 0;
        bool previousBarrierContact = false;
        constexpr int kMaximumFrames =
            static_cast<int>(240.0f / kFixedDt);
        for (int frame = 0;
             frame < kMaximumFrames; ++frame) {
            const float beforeProgress = kart.progress;
            updateAi(kart, kFixedDt, 1, false);
            const float progressStep = signedDistanceToLoop(
                beforeProgress, kart.progress,
                track_.totalLength());
            if (progressStep < -40.0f ||
                progressStep > 90.0f) {
                if (completedLaps >= 1) {
                    ++result.progressJumps;
                }
            } else {
                lapProgress += progressStep;
            }
            if (completedLaps >= 1) {
                const TrackPoint3D center =
                    track_.sample(kart.progress);
                result.maximumRoadViolationMeters =
                    std::max(
                        result.maximumRoadViolationMeters,
                        roadEdgeViolation(kart, center) /
                            kTrackSimulationUnitsPerMeter);
                if (!previousBarrierContact &&
                    kart.barrierContact) {
                    ++result.barrierContacts;
                }
            }
            previousBarrierContact = kart.barrierContact;
            if (lapProgress < track_.totalLength()) {
                continue;
            }
            lapProgress -= track_.totalLength();
            ++completedLaps;
            if (completedLaps == 1) {
                flyingLapStartFrame = frame + 1;
                result.maximumRoadViolationMeters = 0.0f;
                result.barrierContacts = 0;
                result.progressJumps = 0;
                previousBarrierContact = kart.barrierContact;
            } else {
                result.seconds =
                    static_cast<float>(
                        frame + 1 - flyingLapStartFrame) *
                    kFixedDt;
                result.completed = true;
                break;
            }
        }
        aiOptimizationProfileActive_ = false;
        aiOptimizationLaneOffsetsMeters_.fill(0.0f);
        return result;
    }

    AiTimeTrialProfile activeAiTimeTrialProfile(
        TrackLayoutId layout) const {
        if (aiOptimizationProfileActive_ &&
            layout == TrackLayoutId::Monza) {
            return aiOptimizationProfile_;
        }
        return aiTimeTrialProfile(layout);
    }

    float aiPlanSeconds(
        const std::vector<float>& speeds) const {
        if (speeds.size() != aiLapLanePlan_.size() ||
            speeds.empty()) {
            return 0.0f;
        }
        float seconds = 0.0f;
        for (size_t index = 0;
             index < speeds.size(); ++index) {
            const size_t next =
                (index + 1) % speeds.size();
            const TrackPoint3D& point =
                track_.pointAtIndex(
                    static_cast<int>(index));
            const TrackPoint3D& nextPoint =
                track_.pointAtIndex(
                    static_cast<int>(next));
            const Vec2 position =
                point.pos +
                point.normal *
                    aiLapLanePlan_[index];
            const Vec2 nextPosition =
                nextPoint.pos +
                nextPoint.normal *
                    aiLapLanePlan_[next];
            seconds +=
                2.0f * length(nextPosition - position) /
                std::max(1.0f,
                         speeds[index] + speeds[next]);
        }
        return seconds;
    }

    std::vector<float> buildAiRacePacePlan(
        const std::vector<float>& controlSpeeds,
        const std::vector<float>& modeledSpeeds,
        float topSpeed,
        float& modeledRaceSeconds) const {
        if (controlSpeeds.size() !=
                modeledSpeeds.size() ||
            controlSpeeds.empty()) {
            modeledRaceSeconds = 0.0f;
            return controlSpeeds;
        }
        const float optimalSeconds =
            aiPlanSeconds(modeledSpeeds);
        const float targetSeconds =
            optimalSeconds *
            kAiRaceControllerPlanRatio;
        const auto adjustedModel =
            [&](float reduction) {
                std::vector<float> adjusted =
                    modeledSpeeds;
                for (size_t index = 0;
                     index < adjusted.size();
                     ++index) {
                    const float speedRatio =
                        modeledSpeeds[index] /
                        std::max(1.0f, topSpeed);
                    const float cornerWeight =
                        1.0f -
                        smoothstep(std::clamp(
                            (speedRatio - 0.88f) /
                                0.11f,
                            0.0f, 1.0f));
                    adjusted[index] *=
                        1.0f -
                        reduction * cornerWeight;
                }
                return adjusted;
            };
        float lowReduction = 0.0f;
        float highReduction = 0.12f;
        for (int iteration = 0;
             iteration < 24; ++iteration) {
            const float candidate =
                (lowReduction + highReduction) *
                0.5f;
            const float seconds =
                aiPlanSeconds(
                    adjustedModel(candidate));
            if (seconds < targetSeconds) {
                lowReduction = candidate;
            } else {
                highReduction = candidate;
            }
        }
        const float reduction =
            (lowReduction + highReduction) * 0.5f;
        const std::vector<float> raceModel =
            adjustedModel(reduction);
        modeledRaceSeconds =
            aiPlanSeconds(raceModel);
        std::vector<float> raceControl =
            controlSpeeds;
        for (size_t index = 0;
             index < raceControl.size(); ++index) {
            const float speedRatio =
                modeledSpeeds[index] /
                std::max(1.0f, topSpeed);
            const float cornerWeight =
                1.0f -
                smoothstep(std::clamp(
                    (speedRatio - 0.88f) /
                        0.11f,
                    0.0f, 1.0f));
            raceControl[index] *=
                1.0f -
                reduction * cornerWeight;
        }
        return raceControl;
    }

    void buildAiPaceCornerZones(
        const std::vector<float>& modeledSpeeds,
        float topSpeed) {
        aiPaceCornerZones_.clear();
        const int count =
            static_cast<int>(modeledSpeeds.size());
        if (count < 32) {
            return;
        }
        constexpr int kMinimumWindowSamples = 8;
        constexpr int kMinimumSeparationSamples = 24;
        std::vector<int> candidates;
        for (int index = 0; index < count;
             ++index) {
            const float speed =
                modeledSpeeds[
                    static_cast<size_t>(index)];
            if (speed >= topSpeed * 0.985f) {
                continue;
            }
            bool localMinimum = true;
            float shoulderSpeed = speed;
            for (int offset = 1;
                 offset <= kMinimumWindowSamples;
                 ++offset) {
                const float before =
                    modeledSpeeds[
                        static_cast<size_t>(
                            (index - offset +
                             count) %
                            count)];
                const float after =
                    modeledSpeeds[
                        static_cast<size_t>(
                            (index + offset) %
                            count)];
                localMinimum =
                    localMinimum &&
                    speed <= before &&
                    speed <= after;
                shoulderSpeed =
                    std::max(
                        shoulderSpeed,
                        std::max(before, after));
            }
            if (localMinimum &&
                shoulderSpeed - speed >=
                    topSpeed * 0.012f) {
                candidates.push_back(index);
            }
        }
        for (int candidate : candidates) {
            if (!aiPaceCornerZones_.empty()) {
                AiPaceCornerZone& previous =
                    aiPaceCornerZones_.back();
                if (candidate -
                        previous.apexSample <
                    kMinimumSeparationSamples) {
                    if (modeledSpeeds[
                            static_cast<size_t>(
                                candidate)] <
                        modeledSpeeds[
                            static_cast<size_t>(
                                previous.apexSample)]) {
                        previous.apexSample =
                            candidate;
                    }
                    continue;
                }
            }
            aiPaceCornerZones_.push_back(
                {candidate, candidate, candidate});
        }
        if (aiPaceCornerZones_.size() > 1) {
            AiPaceCornerZone& first =
                aiPaceCornerZones_.front();
            const AiPaceCornerZone& last =
                aiPaceCornerZones_.back();
            if (first.apexSample + count -
                    last.apexSample <
                kMinimumSeparationSamples) {
                if (modeledSpeeds[
                        static_cast<size_t>(
                            last.apexSample)] <
                    modeledSpeeds[
                        static_cast<size_t>(
                            first.apexSample)]) {
                    first.apexSample =
                        last.apexSample;
                }
                aiPaceCornerZones_.pop_back();
            }
        }
        std::sort(
            aiPaceCornerZones_.begin(),
            aiPaceCornerZones_.end(),
            [](const AiPaceCornerZone& lhs,
               const AiPaceCornerZone& rhs) {
                return lhs.apexSample <
                       rhs.apexSample;
            });
        if (aiPaceCornerZones_.empty()) {
            return;
        }
        const auto forwardSamples =
            [count](int from, int to) {
                return (to - from + count) %
                       count;
            };
        for (size_t zoneIndex = 0;
             zoneIndex < aiPaceCornerZones_.size();
             ++zoneIndex) {
            AiPaceCornerZone& zone =
                aiPaceCornerZones_[zoneIndex];
            const int previousApex =
                aiPaceCornerZones_[
                    (zoneIndex +
                     aiPaceCornerZones_.size() -
                     1) %
                    aiPaceCornerZones_.size()]
                    .apexSample;
            const int nextApex =
                aiPaceCornerZones_[
                    (zoneIndex + 1) %
                    aiPaceCornerZones_.size()]
                    .apexSample;
            float entryMaximum = -1.0f;
            const int entrySpan =
                forwardSamples(
                    previousApex,
                    zone.apexSample);
            zone.entryStartSample =
                previousApex;
            for (int offset = 1;
                 offset < entrySpan; ++offset) {
                const int sample =
                    (previousApex + offset) %
                    count;
                const float speed =
                    modeledSpeeds[
                        static_cast<size_t>(sample)];
                if (speed >= entryMaximum) {
                    entryMaximum = speed;
                    zone.entryStartSample =
                        sample;
                }
            }
            float exitMaximum = -1.0f;
            const int exitSpan =
                forwardSamples(
                    zone.apexSample, nextApex);
            zone.exitEndSample = nextApex;
            for (int offset = exitSpan - 1;
                 offset > 0; --offset) {
                const int sample =
                    (zone.apexSample + offset) %
                    count;
                const float speed =
                    modeledSpeeds[
                        static_cast<size_t>(sample)];
                if (speed >= exitMaximum) {
                    exitMaximum = speed;
                    zone.exitEndSample = sample;
                }
            }
        }
    }

    void buildAiLapPlan(const Kart3D& kart) {
        aiLapPlanLayout_ = track_.layout();
        aiLapSpeedPlan_.clear();
        aiLapDrsSpeedPlan_.clear();
        aiRaceSpeedPlan_.clear();
        aiRaceDrsSpeedPlan_.clear();
        aiLapTheoreticalSpeedPlan_.clear();
        aiLapDrsTheoreticalSpeedPlan_.clear();
        aiLapLanePlan_.clear();
        aiPaceCornerZones_.clear();
        aiLapTheoreticalSeconds_ = 0.0f;
        aiLapModelSeconds_ = 0.0f;
        aiRacePlanSeconds_ = 0.0f;
        aiRaceDrsPlanSeconds_ = 0.0f;
        if (!isMetricCircuit(track_.layout())) {
            return;
        }

        const int count = track_.sampleCount();
        const AiTimeTrialProfile profile =
            activeAiTimeTrialProfile(track_.layout());
        aiLapLanePlan_.assign(static_cast<size_t>(count), 0.0f);

        const auto smoothedCandidate =
            [&](int smoothingSpan, float roadFraction) {
                std::vector<float> lanes(static_cast<size_t>(count), 0.0f);
                std::vector<float> nextLane(static_cast<size_t>(count), 0.0f);
                std::vector<Vec2> path(static_cast<size_t>(count));
                for (int iteration = 0; iteration < 120; ++iteration) {
                    for (int i = 0; i < count; ++i) {
                        const TrackPoint3D& point =
                            track_.pointAtIndex(i);
                        path[static_cast<size_t>(i)] =
                            point.pos +
                            point.normal *
                                lanes[static_cast<size_t>(i)];
                    }
                    for (int i = 0; i < count; ++i) {
                        const int before =
                            (i - smoothingSpan + count) % count;
                        const int after =
                            (i + smoothingSpan) % count;
                        const TrackPoint3D& point =
                            track_.pointAtIndex(i);
                        const Vec2 chordMidpoint =
                            (path[static_cast<size_t>(before)] +
                             path[static_cast<size_t>(after)]) *
                            0.5f;
                        const float laneLimit = std::max(
                            0.0f,
                            roadCenterLimit(kart, point) *
                                roadFraction);
                        const float desiredLane = std::clamp(
                            dot(chordMidpoint - point.pos,
                                point.normal),
                            -laneLimit, laneLimit);
                        nextLane[static_cast<size_t>(i)] = lerp(
                            lanes[static_cast<size_t>(i)],
                            desiredLane, 0.16f);
                    }
                    lanes.swap(nextLane);
                }
                return lanes;
            };

        aiLapLanePlan_ = smoothedCandidate(
            profile.smoothingSpan, profile.roadFraction);
        if (track_.layout() == TrackLayoutId::Monza) {
            const std::array<float, 24>& lineOffsetsMeters =
                aiOptimizationProfileActive_
                    ? aiOptimizationLaneOffsetsMeters_
                    : kMonzaOptimizedLineOffsetsMeters;
            const float knotCount = static_cast<float>(
                lineOffsetsMeters.size());
            for (int i = 0; i < count; ++i) {
                const float coordinate =
                    static_cast<float>(i) /
                    static_cast<float>(count) * knotCount;
                const size_t first =
                    static_cast<size_t>(
                        std::floor(coordinate)) %
                    lineOffsetsMeters.size();
                const size_t second =
                    (first + 1) %
                    lineOffsetsMeters.size();
                const float offsetMeters = lerp(
                    lineOffsetsMeters[first],
                    lineOffsetsMeters[second],
                    coordinate - std::floor(coordinate));
                const TrackPoint3D& point =
                    track_.pointAtIndex(i);
                const float laneLimit =
                    roadCenterLimit(kart, point) *
                    profile.roadFraction;
                aiLapLanePlan_[static_cast<size_t>(i)] =
                    std::clamp(
                        aiLapLanePlan_[static_cast<size_t>(i)] +
                            offsetMeters *
                                kTrackSimulationUnitsPerMeter,
                        -laneLimit, laneLimit);
            }
        }
        AiLapEvaluation modelPlan =
            evaluateAiLapTrajectory(kart, aiLapLanePlan_);
        aiLapTheoreticalSpeedPlan_ =
            modelPlan.cornerSpeeds;
        AiLapEvaluation drsModelPlan =
            evaluateAiLapTrajectory(
                kart, aiLapLanePlan_, true, 0.995f,
                0.88f, drsTopSpeedExtra());
        aiLapDrsTheoreticalSpeedPlan_ =
            drsModelPlan.cornerSpeeds;
        const bool drsBaseline = isTimeTrial();
        aiLapModelSeconds_ =
            drsBaseline ? drsModelPlan.seconds
                        : modelPlan.seconds;
        aiLapTheoreticalSeconds_ =
            drsBaseline ? drsModelPlan.seconds
                        : profile.benchmarkLapSeconds;
        aiLapSelectedSmoothingSpan_ =
            profile.smoothingSpan;
        aiLapSelectedRoadFraction_ =
            profile.roadFraction;
        AiLapEvaluation controlPlan =
            evaluateAiLapTrajectory(
                kart, aiLapLanePlan_, false, profile.speedReserve,
                profile.brakePlanningFraction);
        aiLapSpeedPlan_ = std::move(controlPlan.speeds);
        AiLapEvaluation drsControlPlan =
            evaluateAiLapTrajectory(
                kart, aiLapLanePlan_, false,
                std::min(profile.speedReserve,
                         1.000f),
                profile.brakePlanningFraction,
                drsTopSpeedExtra());
        aiLapDrsSpeedPlan_ =
            std::move(drsControlPlan.speeds);
        aiRaceSpeedPlan_ =
            buildAiRacePacePlan(
                aiLapSpeedPlan_, modelPlan.speeds,
                kart.tuning.maxForwardSpeed,
                aiRacePlanSeconds_);
        aiRaceDrsSpeedPlan_ =
            buildAiRacePacePlan(
                aiLapDrsSpeedPlan_,
                drsModelPlan.speeds,
                kart.tuning.maxForwardSpeed +
                    drsTopSpeedExtra(),
                aiRaceDrsPlanSeconds_);
        buildAiPaceCornerZones(
            modelPlan.speeds,
            kart.tuning.maxForwardSpeed);
    }

    float sampleAiSpeedPlan(
        const std::vector<float>& plan,
        float progress) const {
        if (plan.empty() ||
            aiLapPlanLayout_ != track_.layout()) {
            return 0.0f;
        }
        const float coordinate = wrapDistance(progress, track_.totalLength()) /
                                 track_.totalLength() * static_cast<float>(plan.size());
        const size_t first = static_cast<size_t>(std::floor(coordinate)) % plan.size();
        const size_t second = (first + 1) % plan.size();
        return lerp(plan[first], plan[second],
                    coordinate - std::floor(coordinate));
    }

    float plannedAiSpeed(float progress,
                         bool drs) const {
        return sampleAiSpeedPlan(
            drs ? aiLapDrsSpeedPlan_
                : aiLapSpeedPlan_,
            progress);
    }

    float plannedAiSpeed(float progress) const {
        return plannedAiSpeed(progress,
                              isTimeTrial());
    }

    float deterministicAiCornerNormal(
        int kartIndex, int lap, int cornerIndex,
        int channel) const {
        uint32_t state =
            0x9e3779b9u ^
            (static_cast<uint32_t>(kartIndex + 1) *
             0x85ebca6bu) ^
            (static_cast<uint32_t>(
                 std::max(0, lap) + 1) *
             0xc2b2ae35u) ^
            (static_cast<uint32_t>(cornerIndex + 1) *
             0x27d4eb2fu) ^
            (static_cast<uint32_t>(channel + 1) *
             0x165667b1u) ^
            (static_cast<uint32_t>(
                 track_.layout()) *
             0xd3a2646cu);
        const auto mix = [](uint32_t value) {
            value ^= value >> 16;
            value *= 0x7feb352du;
            value ^= value >> 15;
            value *= 0x846ca68bu;
            value ^= value >> 16;
            return value;
        };
        const uint32_t first = mix(state);
        const uint32_t second =
            mix(state ^ 0xa511e9b3u);
        const float firstUniform =
            (static_cast<float>(
                 first & 0x00ffffffu) +
             1.0f) /
            16777217.0f;
        const float secondUniform =
            (static_cast<float>(
                 second & 0x00ffffffu) +
             1.0f) /
            16777217.0f;
        constexpr float kTwoPi =
            6.28318530717958647692f;
        const float gaussian =
            std::sqrt(
                -2.0f *
                std::log(firstUniform)) *
            std::cos(kTwoPi * secondUniform);
        // Retain the normal shape while excluding pathological tails that
        // would turn modest race variation into an unsafe missed corner.
        return std::clamp(gaussian,
                          -2.5f, 2.5f);
    }

    float plannedAiRaceSpeed(
        const Kart3D& kart, int kartIndex) const {
        const std::vector<float>& racePlan =
            kart.drsActive
                ? aiRaceDrsSpeedPlan_
                : aiRaceSpeedPlan_;
        const std::vector<float>& optimalPlan =
            kart.drsActive
                ? aiLapDrsSpeedPlan_
                : aiLapSpeedPlan_;
        float target =
            sampleAiSpeedPlan(
                racePlan, kart.progress);
        const int count =
            static_cast<int>(racePlan.size());
        if (count <= 0 ||
            aiPaceCornerZones_.empty()) {
            return target;
        }
        const float coordinate =
            wrapDistance(
                kart.progress,
                track_.totalLength()) /
            track_.totalLength() *
            static_cast<float>(count);
        const int currentSample =
            static_cast<int>(
                std::floor(coordinate)) %
            count;
        const auto forwardSamples =
            [count](int from, int to) {
                return (to - from + count) %
                       count;
            };
        for (size_t cornerIndex = 0;
             cornerIndex <
             aiPaceCornerZones_.size();
             ++cornerIndex) {
            const AiPaceCornerZone& zone =
                aiPaceCornerZones_[cornerIndex];
            const int entryLength =
                forwardSamples(
                    zone.entryStartSample,
                    zone.apexSample);
            const int entryPosition =
                forwardSamples(
                    zone.entryStartSample,
                    currentSample);
            bool entry = entryLength > 0 &&
                         entryPosition <=
                             entryLength;
            const int exitLength =
                forwardSamples(
                    zone.apexSample,
                    zone.exitEndSample);
            const int exitPosition =
                forwardSamples(
                    zone.apexSample,
                    currentSample);
            const bool exit =
                exitLength > 0 &&
                exitPosition <= exitLength;
            if (!entry && !exit) {
                continue;
            }
            const int channel = entry ? 0 : 1;
            const int zoneLength =
                entry ? entryLength : exitLength;
            const float normal =
                deterministicAiCornerNormal(
                    kartIndex, kart.lap,
                    static_cast<int>(cornerIndex),
                    channel);
            const float sampleShift =
                normal *
                kAiCornerVariabilityStdDev *
                static_cast<float>(zoneLength);
            const float progressShift =
                sampleShift /
                static_cast<float>(count) *
                track_.totalLength();
            const float variedTarget =
                sampleAiSpeedPlan(
                    racePlan,
                    kart.progress +
                        progressShift);
            const float optimalCeiling =
                sampleAiSpeedPlan(
                    optimalPlan,
                    kart.progress);
            target = std::min(
                variedTarget,
                optimalCeiling);
            break;
        }
        return target;
    }

    float plannedAiLane(float progress) const {
        if (aiLapLanePlan_.empty() || aiLapPlanLayout_ != track_.layout()) {
            return 0.0f;
        }
        const float coordinate = wrapDistance(progress, track_.totalLength()) /
                                 track_.totalLength() * static_cast<float>(aiLapLanePlan_.size());
        const size_t first = static_cast<size_t>(std::floor(coordinate)) % aiLapLanePlan_.size();
        const size_t second = (first + 1) % aiLapLanePlan_.size();
        return lerp(aiLapLanePlan_[first], aiLapLanePlan_[second],
                    coordinate - std::floor(coordinate));
    }

    float plannedAiTheoreticalSpeed(
        float progress, bool drs) const {
        return sampleAiSpeedPlan(
            drs ? aiLapDrsTheoreticalSpeedPlan_
                : aiLapTheoreticalSpeedPlan_,
            progress);
    }

    float plannedAiTheoreticalSpeed(
        float progress) const {
        return plannedAiTheoreticalSpeed(
            progress, isTimeTrial());
    }

    Vec2 plannedAiPosition(float progress, float laneOffset = 0.0f) const {
        const TrackPoint3D point = track_.sample(progress);
        return point.pos + point.normal * (plannedAiLane(progress) + laneOffset);
    }

    bool isLinkedDirectionChangeProgress(
        float progress) const {
        constexpr float kStartMeters = -260.0f;
        constexpr float kEndMeters = 120.0f;
        constexpr float kSpacingMeters = 20.0f;
        constexpr float kMinimumHeadingChange = 0.012f;
        int previousSign = 0;
        int signChanges = 0;
        float previousHeading = angleOf(
            plannedAiPosition(progress + kStartMeters +
                              kSpacingMeters) -
            plannedAiPosition(progress + kStartMeters));
        for (float distanceMeters =
                 kStartMeters + kSpacingMeters;
             distanceMeters <= kEndMeters;
             distanceMeters += kSpacingMeters) {
            const float heading = angleOf(
                plannedAiPosition(progress +
                                  distanceMeters +
                                  kSpacingMeters) -
                plannedAiPosition(progress +
                                  distanceMeters));
            const float headingChange =
                wrapAngle(heading - previousHeading);
            previousHeading = heading;
            if (std::abs(headingChange) <
                kMinimumHeadingChange) {
                continue;
            }
            const int sign =
                headingChange < 0.0f ? -1 : 1;
            if (previousSign != 0 &&
                sign != previousSign) {
                ++signChanges;
            }
            previousSign = sign;
        }
        return signChanges >= 1;
    }

    bool isPhysicsValidatedFlatProgress(
        float progress, bool drs) const {
        if (!isMetricCircuit(track_.layout()) ||
            aiLapTheoreticalSpeedPlan_.empty()) {
            return false;
        }
        const float maximumSpeed =
            selectedTrackTuning(specs_[0]).maxForwardSpeed +
            (drs ? drsTopSpeedExtra() : 0.0f);
        constexpr float kTerminalSpeedRatio = 0.99f;
        constexpr float kNeighborhoodMeters = 60.0f;
        constexpr float kSpacingMeters = 5.0f;
        int terminalSamples = 0;
        int sampleCount = 0;
        for (float distanceMeters = -kNeighborhoodMeters;
             distanceMeters <= kNeighborhoodMeters;
             distanceMeters += kSpacingMeters) {
            terminalSamples +=
                plannedAiTheoreticalSpeed(
                    progress +
                    distanceMeters, drs) >=
                        maximumSpeed *
                            kTerminalSpeedRatio
                    ? 1
                    : 0;
            ++sampleCount;
        }
        return terminalSamples * 4 >= sampleCount * 3;
    }

    bool isPhysicsValidatedFlatProgress(
        float progress) const {
        return isPhysicsValidatedFlatProgress(
            progress, isTimeTrial());
    }

    bool isPhysicallyFlatCorner(const Kart3D& kart) const {
        if (!isMetricCircuit(track_.layout()) ||
            aiLapTheoreticalSpeedPlan_.empty()) {
            return false;
        }
        if (isPhysicsValidatedFlatProgress(
                kart.progress, kart.drsActive)) {
            return true;
        }

        // Decide only whether full throttle is optimal for this simulation
        // step.  For every point in the braking horizon, prove that the speed
        // after one powered frame can still be reduced to the physical path
        // limit.  Repeating this test at 120 Hz naturally finds the latest
        // braking point and also recognizes complexes that are flat after
        // their entry-speed reduction.  No circuit phases or real-world
        // corner labels participate in the decision.
        const float speed = length(kart.vel);
        const float netAcceleration = std::max(
            0.0f,
            kart.tuning.engineAcceleration -
                kart.tuning.rollingResistance -
                speed * speed *
                    kart.tuning.aerodynamicDrag);
        const float poweredNextFrameSpeed = std::min(
            effectiveTopSpeed(kart),
            speed + netAcceleration * kFixedDt);
        constexpr float kLimitToleranceKph = 8.0f;
        const float limitTolerance =
            kLimitToleranceKph /
            speedKphPerSimulationUnit(track_.layout());
        if (poweredNextFrameSpeed >
            plannedAiTheoreticalSpeed(
                kart.progress, kart.drsActive) +
                limitTolerance) {
            return false;
        }
        const float targetNow =
            plannedAiSpeed(kart.progress,
                           kart.drsActive);
        constexpr float kTargetTrackingToleranceKph = 10.0f;
        const float targetTrackingTolerance =
            kTargetTrackingToleranceKph /
            speedKphPerSimulationUnit(track_.layout());
        if (poweredNextFrameSpeed >
            targetNow + targetTrackingTolerance) {
            return false;
        }

        constexpr float kHorizonMeters = 260.0f;
        constexpr float kSampleSpacingMeters = 4.0f;
        const float brakingAcceleration =
            kart.tuning.brakeDeceleration *
            activeAiTimeTrialProfile(track_.layout())
                .brakePlanningFraction;
        for (float distanceMeters = kSampleSpacingMeters;
             distanceMeters <= kHorizonMeters;
             distanceMeters += kSampleSpacingMeters) {
            const float distance =
                distanceMeters *
                kTrackSimulationUnitsPerMeter;
            const float pathLimit =
                plannedAiTheoreticalSpeed(
                    kart.progress + distanceMeters,
                    kart.drsActive);
            const float latestReachableSpeed = std::sqrt(
                pathLimit * pathLimit +
                2.0f * brakingAcceleration * distance);
            if (poweredNextFrameSpeed >
                latestReachableSpeed + limitTolerance) {
                return false;
            }
        }
        return true;
    }

    float aiTargetSpeed(
        const Kart3D& kart, bool raceTraffic,
        int kartIndex) const {
        if (isMetricCircuit(track_.layout())) {
            const float planned =
                raceTraffic
                    ? plannedAiRaceSpeed(
                          kart, kartIndex)
                    : plannedAiSpeed(
                          kart.progress,
                          kart.drsActive);
            return planned >=
                           effectiveTopSpeed(kart) *
                               0.990f
                       ? std::max(
                             planned,
                             effectiveTopSpeed(kart))
                       : planned;
        }
        const float brakingAcceleration = kart.tuning.brakeDeceleration * 0.76f;
        float targetSpeed = referenceAiSpeed(kart, kart.progress);
        for (int sample = 1; sample <= 12; ++sample) {
            const float distance = static_cast<float>(sample) * 26.0f;
            const float cornerSpeed = referenceAiSpeed(kart, kart.progress + distance);
            const float reachableSpeed = std::sqrt(cornerSpeed * cornerSpeed + 2.0f * brakingAcceleration * distance);
            targetSpeed = std::min(targetSpeed, reachableSpeed);
        }
        return targetSpeed;
    }

    float monzaRaceLaneTarget(
        Kart3D& kart, int index, float dt, float baseLane,
        bool approachingTurnIn) {
        kart.aiRaceCommitTimer =
            std::max(0.0f, kart.aiRaceCommitTimer - dt);
        kart.aiRaceCooldownTimer =
            std::max(0.0f, kart.aiRaceCooldownTimer - dt);

        const float units = kTrackSimulationUnitsPerMeter;
        const float trackLength = track_.totalLength();
        const float speedMetersPerSecond =
            length(kart.vel) / units;
        const float currentCurvature =
            std::max({std::abs(smoothedSignedCurvature(
                          kart.progress)),
                      std::abs(smoothedSignedCurvature(
                          kart.progress + 55.0f)),
                      std::abs(smoothedSignedCurvature(
                          kart.progress + 125.0f))});
        const float plannedTerminalSpeed =
            aiLapSpeedPlan_.empty()
                ? kart.tuning.maxForwardSpeed
                : *std::max_element(
                      aiLapSpeedPlan_.begin(),
                      aiLapSpeedPlan_.end());
        const float theoreticalTerminalSpeed =
            aiLapTheoreticalSpeedPlan_.empty()
                ? plannedTerminalSpeed
                : *std::max_element(
                      aiLapTheoreticalSpeedPlan_.begin(),
                      aiLapTheoreticalSpeedPlan_.end());
        const bool physicsFlatPassingZone =
            isPhysicsValidatedFlatProgress(
                kart.progress) ||
            plannedAiTheoreticalSpeed(
                kart.progress) >=
                theoreticalTerminalSpeed *
                    0.985f ||
            plannedAiSpeed(kart.progress) >=
                plannedTerminalSpeed *
                    0.985f;
        const bool passingZone =
            physicsFlatPassingZone ||
            (currentCurvature < 0.075f &&
             !approachingTurnIn);

        const auto releaseIntent = [&]() {
            kart.aiRaceIntent = AiRaceIntent3D::None;
            kart.aiRaceDesiredLaneOffset = 0.0f;
            kart.aiRaceTargetIndex = -1;
            kart.aiRaceCooldownTimer =
                std::max(kart.aiRaceCooldownTimer, 0.55f);
        };

        if (kart.aiRaceIntent == AiRaceIntent3D::Pass) {
            bool targetStillRelevant = false;
            if (kart.aiRaceTargetIndex >= 0 &&
                kart.aiRaceTargetIndex < activeKartCount()) {
                const Kart3D& target =
                    karts_[static_cast<size_t>(
                        kart.aiRaceTargetIndex)];
                const float targetAhead = progressAhead(
                    kart.progress, target.progress, trackLength);
                const float targetBehind = progressAhead(
                    target.progress, kart.progress, trackLength);
                const float lateralSeparation =
                    std::abs(kart.lane - target.lane);
                const float overlapWidth =
                    std::max(kart.spec.width,
                             target.spec.width) *
                        1.5f +
                    0.12f * units;
                targetStillRelevant =
                    targetAhead < 70.0f ||
                    (targetBehind < 12.0f &&
                     lateralSeparation < overlapWidth);
                if (targetBehind > 8.0f &&
                    targetBehind < trackLength * 0.5f &&
                    lateralSeparation >= overlapWidth) {
                    targetStillRelevant = false;
                }
            }
            if (!targetStillRelevant &&
                kart.aiRaceCommitTimer <= 0.0f) {
                releaseIntent();
            } else if (!passingZone &&
                       kart.aiRaceCommitTimer <= 0.0f) {
                releaseIntent();
            }
        } else if (kart.aiRaceIntent ==
                       AiRaceIntent3D::Defend &&
                   kart.aiRaceCommitTimer <= 0.0f) {
            releaseIntent();
        }

        int nearestAheadIndex = -1;
        float nearestAhead = std::numeric_limits<float>::max();
        int nearestBehindIndex = -1;
        float nearestBehind = std::numeric_limits<float>::max();
        for (int otherIndex = 0;
             otherIndex < activeKartCount(); ++otherIndex) {
            if (otherIndex == index) {
                continue;
            }
            const Kart3D& other =
                karts_[static_cast<size_t>(otherIndex)];
            const float ahead = progressAhead(
                kart.progress, other.progress, trackLength);
            if (ahead > 0.10f && ahead < nearestAhead) {
                nearestAhead = ahead;
                nearestAheadIndex = otherIndex;
            }
            const float behind = progressAhead(
                other.progress, kart.progress, trackLength);
            if (behind > 0.10f && behind < nearestBehind) {
                nearestBehind = behind;
                nearestBehindIndex = otherIndex;
            }
        }

        if (kart.aiRaceIntent == AiRaceIntent3D::None &&
            kart.aiRaceCooldownTimer <= 0.0f && passingZone &&
            nearestAheadIndex >= 0 &&
            nearestAhead < 54.0f) {
            const Kart3D& target =
                karts_[static_cast<size_t>(nearestAheadIndex)];
            const float closingSpeed =
                speedMetersPerSecond -
                length(target.vel) / units;
            if (nearestAhead < 28.0f ||
                closingSpeed > 0.35f) {
                const TrackPoint3D decisionPoint =
                    track_.sample(
                        kart.progress + 42.0f);
                const float laneLimit =
                    std::max(0.0f,
                             roadCenterLimit(kart,
                                             decisionPoint));
                const float passSeparation =
                    std::max(kart.spec.width,
                             target.spec.width) *
                        1.5f +
                    0.12f * units;
                float bestScore =
                    -std::numeric_limits<float>::max();
                float bestOffset = 0.0f;
                const float preferredSide =
                    ((index + std::max(0, kart.lap)) %
                             2 ==
                         0)
                        ? -1.0f
                        : 1.0f;
                for (float side : {-1.0f, 1.0f}) {
                    const float candidateLane =
                        target.lane +
                        side * passSeparation;
                    if (std::abs(candidateLane) >
                        laneLimit) {
                        continue;
                    }
                    if (std::abs(
                            candidateLane - baseLane) >
                        passSeparation) {
                        continue;
                    }
                    float score =
                        (laneLimit - std::abs(candidateLane)) /
                            units +
                        std::abs(candidateLane - target.lane) /
                            units -
                        std::abs(candidateLane - baseLane) /
                            units * 2.0f;
                    if (side == preferredSide) {
                        score += 0.65f;
                    }
                    for (int otherIndex = 0;
                         otherIndex < activeKartCount();
                         ++otherIndex) {
                        if (otherIndex == index ||
                            otherIndex == nearestAheadIndex) {
                            continue;
                        }
                        const Kart3D& other =
                            karts_[static_cast<size_t>(
                                otherIndex)];
                        const float relative =
                            std::abs(signedDistanceToLoop(
                                kart.progress, other.progress,
                                trackLength));
                        if (relative < 24.0f &&
                            std::abs(other.lane -
                                     candidateLane) <
                                passSeparation) {
                            score -= 20.0f;
                        }
                    }
                    if (score > bestScore) {
                        bestScore = score;
                        bestOffset =
                            candidateLane - baseLane;
                    }
                }
                if (bestScore > -5.0f) {
                    kart.aiRaceIntent =
                        AiRaceIntent3D::Pass;
                    kart.aiRaceTargetIndex =
                        nearestAheadIndex;
                    kart.aiRaceDesiredLaneOffset =
                        bestOffset;
                    kart.aiRaceCommitTimer = 1.35f;
                }
            }
        }

        if (kart.aiRaceIntent == AiRaceIntent3D::None &&
            kart.aiRaceCooldownTimer <= 0.0f && passingZone &&
            nearestBehindIndex >= 0 &&
            nearestBehind < 20.0f &&
            kart.aiRaceDefendedLap != kart.lap &&
            index % 3 != 0) {
            const Kart3D& challenger =
                karts_[static_cast<size_t>(
                    nearestBehindIndex)];
            const float closingSpeed =
                length(challenger.vel) / units -
                speedMetersPerSecond;
            const float combinedHalfLengthMeters =
                (kart.spec.length +
                 challenger.spec.length) *
                0.50f / units;
            const float usableDefenceGap =
                nearestBehind -
                combinedHalfLengthMeters;
            const float arrivalSeconds =
                closingSpeed > 0.05f
                    ? usableDefenceGap /
                          closingSpeed
                    : std::numeric_limits<float>::max();
            if (closingSpeed > 1.1f &&
                usableDefenceGap > 8.0f &&
                arrivalSeconds > 1.50f) {
                const float challengerSide =
                    challenger.lane >= baseLane ? 1.0f : -1.0f;
                kart.aiRaceIntent =
                    AiRaceIntent3D::Defend;
                kart.aiRaceTargetIndex =
                    nearestBehindIndex;
                kart.aiRaceDesiredLaneOffset =
                    challengerSide * 1.25f * units;
                kart.aiRaceCommitTimer = 0.85f;
                kart.aiRaceDefendedLap = kart.lap;
            }
        }

        const TrackPoint3D lanePoint =
            track_.sample(kart.progress + 35.0f);
        const float laneLimit =
            std::max(0.0f,
                     roadCenterLimit(kart, lanePoint));
        kart.aiRaceDesiredLaneOffset = std::clamp(
            kart.aiRaceDesiredLaneOffset,
            -laneLimit - baseLane,
            laneLimit - baseLane);
        const float response =
            1.0f - std::exp(
                       -dt *
                           (passingZone ? 3.8f
                                        : 6.0f));
        kart.aiRaceLaneOffset = lerp(
            kart.aiRaceLaneOffset,
            kart.aiRaceDesiredLaneOffset, response);
        if (kart.aiRaceIntent == AiRaceIntent3D::None &&
            std::abs(kart.aiRaceLaneOffset) <
                0.01f * units) {
            kart.aiRaceLaneOffset = 0.0f;
        }
        return std::clamp(baseLane + kart.aiRaceLaneOffset,
                          -laneLimit, laneLimit);
    }

    float proximityAvoidanceLaneTarget(
        Kart3D& kart, int index,
        float laneTarget, bool raceTraffic,
        bool approachingTurnIn) {
        kart.aiProximityAvoidanceConstraint = false;
        kart.aiProximityAvoidanceTargetIndex = -1;
        if (!raceTraffic ||
            activeKartCount() <= 1) {
            return laneTarget;
        }

        const float units =
            isMetricCircuit(track_.layout())
                ? kTrackSimulationUnitsPerMeter
                : 1.0f;
        const float trackLength =
            track_.totalLength();
        const bool contextAwareRacecraft =
            kMonzaRacecraftExperiment &&
            track_.layout() == TrackLayoutId::Monza;
        // On a straight, look far enough ahead to establish a pass before
        // reaching the car in front.  Once committed to a corner, preserve
        // the current side and let the longitudinal controller queue behind
        // traffic rather than darting across the braking zone.
        const float predictionSeconds =
            contextAwareRacecraft
                ? (approachingTurnIn ? 0.55f : 1.20f)
                : 0.75f;
        const TrackPoint3D ownPoint =
            track_.sample(kart.progress);
        const float ownForwardSpeed =
            std::max(
                0.0f,
                dot(kart.vel,
                    ownPoint.tangent) /
                    units);
        const TrackPoint3D decisionPoint =
            track_.sample(
                kart.progress +
                ownForwardSpeed *
                    predictionSeconds);
        const float laneLimit =
            std::max(
                0.0f,
                roadCenterLimit(
                    kart, decisionPoint));
        float bestUrgency = 0.0f;
        float bestLane = laneTarget;
        int bestTarget = -1;
        bool bestAlreadyAlongside = false;

        for (int otherIndex = 0;
             otherIndex < activeKartCount();
             ++otherIndex) {
            if (otherIndex == index) {
                continue;
            }
            const Kart3D& other =
                karts_[static_cast<size_t>(
                    otherIndex)];
            const float ahead =
                progressAhead(
                    kart.progress,
                    other.progress,
                    trackLength);
            const float behind =
                progressAhead(
                    other.progress,
                    kart.progress,
                    trackLength);
            const float relativeProgress =
                ahead <= behind ? ahead : -behind;
            const TrackPoint3D otherPoint =
                track_.sample(other.progress);
            const float otherForwardSpeed =
                std::max(
                    0.0f,
                    dot(other.vel,
                        otherPoint.tangent) /
                        units);
            const float projectedRelative =
                relativeProgress +
                (otherForwardSpeed -
                 ownForwardSpeed) *
                    predictionSeconds;
            const float halfCombinedLength =
                (kart.spec.length +
                 other.spec.length) *
                0.5f / units;
            const float longitudinalClearance =
                halfCombinedLength + 1.25f;
            float minimumProjectedGap =
                std::min(
                    std::abs(relativeProgress),
                    std::abs(projectedRelative));
            if (relativeProgress *
                    projectedRelative <=
                0.0f) {
                minimumProjectedGap = 0.0f;
            }
            if (minimumProjectedGap >
                longitudinalClearance) {
                continue;
            }
            const bool alreadyAlongside =
                std::abs(relativeProgress) <=
                longitudinalClearance;
            if (contextAwareRacecraft &&
                otherIndex == 0 &&
                alreadyAlongside &&
                kart.aiRaceIntent ==
                    AiRaceIntent3D::Defend &&
                kart.aiRaceTargetIndex == 0) {
                // Once the attacking player has arrived, the defensive move
                // is over. Hold the established side instead of squeezing
                // across the player's occupied corridor.
                kart.aiRaceIntent =
                    AiRaceIntent3D::None;
                kart.aiRaceDesiredLaneOffset = 0.0f;
                kart.aiRaceTargetIndex = -1;
                kart.aiRaceCooldownTimer =
                    std::max(
                        kart.aiRaceCooldownTimer,
                        0.80f);
            }
            if (contextAwareRacecraft &&
                approachingTurnIn &&
                relativeProgress >
                    longitudinalClearance &&
                !alreadyAlongside) {
                continue;
            }

            const float ownProjectedLane =
                kart.lane +
                std::clamp(
                    dot(kart.vel,
                        ownPoint.normal) *
                        predictionSeconds,
                    -3.0f * units,
                    3.0f * units);
            const float otherVelocityLane =
                other.lane +
                std::clamp(
                    dot(other.vel,
                        otherPoint.normal) *
                        predictionSeconds,
                    -3.0f * units,
                    3.0f * units);
            const float otherProjectedLane =
                otherIndex == 0
                    ? otherVelocityLane
                    : lerp(
                          otherVelocityLane,
                          other.aiCommandLineTarget,
                          0.55f);
            const float requiredLaneGap =
                contextAwareRacecraft
                    ? (kart.spec.width +
                       other.spec.width) *
                              0.50f +
                          0.18f * units
                    : std::max(
                          kart.spec.width,
                          other.spec.width) *
                              1.5f +
                          0.10f * units;
            const float projectedLaneGap =
                std::abs(
                    ownProjectedLane -
                    otherProjectedLane);
            if (projectedLaneGap >=
                requiredLaneGap) {
                continue;
            }

            const float longitudinalUrgency =
                1.0f -
                smoothstep(std::clamp(
                    minimumProjectedGap /
                        std::max(
                            0.01f,
                            longitudinalClearance),
                    0.0f, 1.0f));
            const float lateralUrgency =
                1.0f -
                smoothstep(std::clamp(
                    projectedLaneGap /
                        std::max(
                            1.0f,
                            requiredLaneGap),
                    0.0f, 1.0f));
            const float urgency =
                std::max(
                    longitudinalUrgency,
                    lateralUrgency);
            if (urgency <= bestUrgency) {
                continue;
            }

            float selectedLane = laneTarget;
            float selectedScore =
                std::numeric_limits<float>::max();
            for (float side : {-1.0f, 1.0f}) {
                const float candidate =
                    otherProjectedLane +
                    side * requiredLaneGap;
                if (std::abs(candidate) >
                    laneLimit) {
                    continue;
                }
                float score =
                    std::abs(
                        candidate - laneTarget) /
                    units;
                const float currentSide =
                    kart.lane -
                    other.lane;
                if (std::abs(currentSide) >
                        0.05f * units &&
                    side * currentSide < 0.0f) {
                    score += 2.0f;
                }
                if (std::abs(currentSide) <=
                        0.05f * units &&
                    ((index + otherIndex) % 2 ==
                         0
                         ? side < 0.0f
                         : side > 0.0f)) {
                    score += 0.25f;
                }
                if (contextAwareRacecraft &&
                    (approachingTurnIn ||
                     alreadyAlongside) &&
                    std::abs(currentSide) >
                        0.05f * units &&
                    side * currentSide < 0.0f) {
                    score += 50.0f;
                }
                for (int thirdIndex = 0;
                     thirdIndex <
                     activeKartCount();
                     ++thirdIndex) {
                    if (thirdIndex == index ||
                        thirdIndex == otherIndex) {
                        continue;
                    }
                    const Kart3D& third =
                        karts_[static_cast<size_t>(
                            thirdIndex)];
                    const float thirdRelative =
                        std::abs(
                            signedDistanceToLoop(
                                kart.progress,
                                third.progress,
                                trackLength));
                    if (thirdRelative <
                            longitudinalClearance *
                                1.5f &&
                        std::abs(
                            third.lane -
                            candidate) <
                            requiredLaneGap) {
                        score += 20.0f;
                    }
                }
                if (score < selectedScore) {
                    selectedScore = score;
                    selectedLane = candidate;
                }
            }
            if (!std::isfinite(selectedScore)) {
                continue;
            }
            bestUrgency = urgency;
            bestLane = selectedLane;
            bestTarget = otherIndex;
            bestAlreadyAlongside =
                alreadyAlongside;
        }

        if (bestTarget < 0) {
            return laneTarget;
        }
        kart.aiProximityAvoidanceConstraint = true;
        kart.aiProximityAvoidanceTargetIndex =
            bestTarget;
        const float response =
            bestAlreadyAlongside
                ? std::max(
                      0.90f,
                      lerp(0.55f, 0.95f,
                           bestUrgency))
                : lerp(0.55f, 0.95f,
                       bestUrgency);
        return std::clamp(
            lerp(laneTarget, bestLane, response),
            -laneLimit, laneLimit);
    }

    void containMonzaKartWithinCurbs(
        Kart3D& kart) {
        const TrackPoint3D trackPoint =
            track_.sample(kart.progress);
        const float curbCenterLimit =
            roadCenterLimit(kart, trackPoint) +
            kMetricCurbWidthMeters *
                kTrackSimulationUnitsPerMeter;
        const float projectedLane =
            dot(kart.pos - trackPoint.pos,
                trackPoint.normal);
        if (std::abs(projectedLane) <=
            curbCenterLimit) {
            return;
        }
        const float side =
            projectedLane < 0.0f ? -1.0f : 1.0f;
        const float excess =
            std::abs(projectedLane) -
            curbCenterLimit;
        kart.pos -=
            trackPoint.normal * (side * excess);
        const float outwardVelocity =
            dot(kart.vel, trackPoint.normal) *
            side;
        if (outwardVelocity > 0.0f) {
            kart.vel -=
                trackPoint.normal *
                (side * outwardVelocity);
        }
        updateProgress(kart);
    }

    void updateAi(
        Kart3D& kart, float dt, int index,
        bool raceTraffic = true,
        bool useRacePace = false) {
        if (!raceTraffic || isTimeTrial()) {
            kart.drsAvailable = true;
            kart.drsActive = true;
        } else {
            kart.drsActive =
                kart.drsAvailable &&
                kart.aiCommandBrake <= 0.01f &&
                kart.brakeLoad <= 0.05f;
        }
        TrackPoint3D center = track_.sample(kart.progress);
        float speed = length(kart.vel);
        const float distanceSpeed = isMetricCircuit(track_.layout())
                                        ? speed / kTrackSimulationUnitsPerMeter
                                        : speed;
        const float pathSpeed = distanceSpeed / kRacePaceScale;
        const float steeringCorner = std::max(std::abs(smoothedSignedCurvature(kart.progress + 80.0f)),
                                              std::abs(smoothedSignedCurvature(kart.progress + 175.0f)));
        const float racecraftCorner = std::max({std::abs(smoothedSignedCurvature(kart.progress)),
                                                std::abs(smoothedSignedCurvature(kart.progress + 45.0f)),
                                                std::abs(smoothedSignedCurvature(kart.progress + 95.0f)),
                                                std::abs(smoothedSignedCurvature(kart.progress + 155.0f))});
        const bool approachingTurnIn = racecraftCorner > 0.09f;
        const float cornerLookaheadScale = lerp(1.0f, 0.62f, std::clamp((steeringCorner - 0.08f) / 0.52f, 0.0f, 1.0f));
        const float lookahead = std::clamp((86.0f + pathSpeed * 0.50f) * cornerLookaheadScale, 78.0f, 230.0f);
        const TrackPoint3D future = track_.sample(kart.progress + lookahead);
        const float racingLane = racingLaneForProgress(kart, kart.progress);
        const float lineResponse = 1.0f - std::exp(-dt * (steeringCorner > 0.12f ? 5.0f : 2.8f));
        if (isMetricCircuit(track_.layout())) {
            // The lap plan is already continuous and anticipatory. Follow its
            // current station directly; the steering controller looks ahead
            // along the same planned path.
            kart.aiLineTarget = racingLane;
        } else {
            kart.aiLineTarget = lerp(kart.aiLineTarget, racingLane, lineResponse);
        }
        float laneTarget = isMetricCircuit(track_.layout())
                               ? kart.aiLineTarget
                               : lerp(kart.aiLineTarget,
                                      racingLaneForProgress(kart, future.progress),
                                      0.72f);
        float startLineDistanceMeters =
            std::numeric_limits<float>::max();
        if (raceTraffic && raceFlow_ &&
            index >= 0 &&
            index < static_cast<int>(
                        raceFlow_->racerCount())) {
            startLineDistanceMeters =
                static_cast<float>(
                    raceFlow_->racer(
                        static_cast<size_t>(index))
                        .continuousTrackProgress) *
                track_.totalLength();
        }
        constexpr float kGridLaneHoldMeters =
            -120.0f;
        constexpr float kGridLaneReleaseMeters =
            60.0f;
        const bool leavingGrid =
            startLineDistanceMeters >= -200.0f &&
            startLineDistanceMeters <
                kGridLaneReleaseMeters;
        const bool monzaRacecraft =
            kMonzaRacecraftExperiment && raceTraffic &&
            track_.layout() == TrackLayoutId::Monza;
        if (monzaRacecraft &&
            (!leavingGrid ||
             startLineDistanceMeters >=
                 kGridLaneHoldMeters)) {
            laneTarget = monzaRaceLaneTarget(
                kart, index, dt, laneTarget,
                approachingTurnIn);
        }
        if (leavingGrid) {
            // Hold the authored grid column through the line, then blend
            // toward either the canonical line or a pass lane selected from
            // the live traffic trajectory.
            const float releaseBlend =
                smoothstep(std::clamp(
                    (startLineDistanceMeters -
                     kGridLaneHoldMeters) /
                        (kGridLaneReleaseMeters -
                         kGridLaneHoldMeters),
                    0.0f, 1.0f));
            laneTarget = lerp(
                kart.aiGridLane, laneTarget,
                releaseBlend);
            if (startLineDistanceMeters <
                kGridLaneHoldMeters) {
                kart.aiRaceIntent =
                    AiRaceIntent3D::None;
                kart.aiRaceLaneOffset = 0.0f;
                kart.aiRaceDesiredLaneOffset = 0.0f;
                kart.aiRaceTargetIndex = -1;
            }
        }
        laneTarget =
            proximityAvoidanceLaneTarget(
                kart, index, laneTarget,
                raceTraffic,
                approachingTurnIn);
        // Clean air stays on the solo minimum-time line. The Monza experiment
        // adds only a temporary offset while a pass or one-move defence is
        // committed, then converges back to this canonical trajectory.
        const float hardHalf = std::min(
            hardBoundaryLaneLimit(kart, future) - 5.0f,
            roadCenterLimit(kart, future) * 0.98f);
        if (!isMetricCircuit(track_.layout())) {
            laneTarget = std::clamp(laneTarget, -hardHalf, hardHalf);
        }
        const float currentLineLimit = roadCenterLimit(kart, center) - 1.0f;
        const float laneExcess = std::max(0.0f, std::abs(kart.lane) - currentLineLimit);
        const float recoveryUnits = isMetricCircuit(track_.layout()) ? kTrackSimulationUnitsPerMeter : 1.0f;
        if ((!monzaRacecraft &&
             speed < 5.0f * recoveryUnits) ||
            (monzaRacecraft &&
             laneExcess >
                 0.10f * recoveryUnits &&
             speed < 5.0f * recoveryUnits) ||
            (laneExcess > 0.50f * recoveryUnits &&
             speed < 12.0f * recoveryUnits)) {
            kart.aiStuckTimer += dt;
        } else {
            kart.aiStuckTimer = 0.0f;
        }
        if (kart.aiStuckTimer >= 1.25f) {
            ++kart.aiRecoveryResetCount;
            kart.pos = center.pos;
            kart.vel = center.tangent * (15.0f * recoveryUnits);
            kart.heading = angleOf(center.tangent);
            kart.lane = 0.0f;
            kart.elevation = bankedElevation(center, 0.0f);
            kart.verticalSpeed = 0.0f;
            kart.grounded = true;
            kart.barrierContact = false;
            kart.contactTimer = 0.0f;
            kart.aiStuckTimer = 0.0f;
            kart.ghostTimer = std::max(kart.ghostTimer, 1.0f);
            kart.previousRenderPos = kart.pos;
            kart.previousRenderElevation = kart.elevation;
            kart.previousRenderHeading = kart.heading;
            syncArcadeTransmissionToSpeed(kart, kart.tuning);
            return;
        }
        const float recovery = std::clamp(laneExcess / 18.0f, 0.0f, 1.0f);
        if (laneExcess > 1.0f) {
            // Preserve the validated solo controller's center-road recovery.
            // Race planning remains on the canonical line; this branch exists
            // only after the vehicle has already exceeded the road limit.
            laneTarget =
                raceTraffic
                    ? racingLaneForProgress(
                          kart, kart.progress)
                    : 0.0f;
            const float side = kart.lane < 0.0f ? -1.0f : 1.0f;
            const float outwardSpeed = dot(kart.vel, center.normal) * side;
            const float inwardTarget = std::min(12.0f * recoveryUnits,
                                                laneExcess * 0.85f);
            if (outwardSpeed > -inwardTarget) {
                const float recoveryAcceleration = kart.tuning.lateralGripAcceleration * 1.10f * recovery;
                kart.vel -= center.normal * (side * recoveryAcceleration * dt);
            }
            const Vec2 recoveryDirection = normalize(center.tangent - center.normal * (side * 0.32f));
            const float recoveryHeading = angleOf(recoveryDirection);
            kart.heading = wrapAngle(kart.heading + wrapAngle(recoveryHeading - kart.heading) *
                                                       std::clamp(dt * 4.5f * recovery, 0.0f, 1.0f));
        }

        const float activeTopSpeed =
            effectiveTopSpeed(kart);
        const bool acceptingPassTow =
            raceTraffic &&
            !kart.drsActive &&
            kart.aiRaceIntent ==
                AiRaceIntent3D::Pass;
        const float controllerTopSpeed =
            acceptingPassTow
                ? kart.tuning.maxForwardSpeed *
                      kMonzaDraftTopSpeedScale
                : (kart.drsActive
                       ? activeTopSpeed +
                             5.0f /
                                 speedKphPerSimulationUnit(
                                     track_.layout())
                       : activeTopSpeed);
        float targetSpeed =
            aiTargetSpeed(
                kart,
                raceTraffic || useRacePace,
                index) *
            (1.0f - recovery * 0.24f);
        if (acceptingPassTow &&
            targetSpeed >=
                kart.tuning.maxForwardSpeed *
                    0.99f) {
            targetSpeed =
                std::max(targetSpeed,
                         controllerTopSpeed);
        }
        if (kart.drsActive &&
            targetSpeed >=
                activeTopSpeed * 0.99f) {
            targetSpeed = std::max(
                targetSpeed,
                controllerTopSpeed);
        }
        targetSpeed = std::min(targetSpeed, controllerTopSpeed);
        const bool instantFullThrottleOptimal =
            isPhysicallyFlatCorner(kart);
        const bool belowTerminalSpeed =
            speed <
            controllerTopSpeed * 0.97f;
        constexpr float kFlatCommitTrendMeters =
            16.0f;
        constexpr float kFlatCommitTrendToleranceKph =
            2.0f;
        const float flatCommitTrendTolerance =
            kFlatCommitTrendToleranceKph /
            speedKphPerSimulationUnit(
                track_.layout());
        const bool speedEnvelopeNotFalling =
            plannedAiSpeed(
                kart.progress +
                kFlatCommitTrendMeters,
                kart.drsActive) +
                flatCommitTrendTolerance >=
            plannedAiSpeed(kart.progress,
                           kart.drsActive);
        if (instantFullThrottleOptimal &&
            belowTerminalSpeed &&
            speedEnvelopeNotFalling &&
            isLinkedDirectionChangeProgress(
                kart.progress)) {
            kart.aiFlatCommitTimer = 1.5f;
        } else {
            kart.aiFlatCommitTimer =
                std::max(0.0f,
                         kart.aiFlatCommitTimer - dt);
        }
        const bool retainedFlatCommit =
            kart.aiFlatCommitTimer > 0.0f &&
            speed <
                controllerTopSpeed &&
            isLinkedDirectionChangeProgress(
                kart.progress);
        const bool committedFlatCorner =
            instantFullThrottleOptimal ||
            retainedFlatCommit;
        kart.aiFullThrottleOptimal =
            committedFlatCorner;
        // A real driver backs out before a missed apex becomes an excursion.
        // This is a control response, not extra grip: the car still has to
        // decelerate through the shared vehicle integrator.
        const float edgeUsage = std::abs(kart.lane) /
                                std::max(1.0f, roadCenterLimit(kart, center));
        const float headingError = std::abs(wrapAngle(angleOf(center.tangent) - kart.heading));
        const float edgeInstability =
            smoothstep(std::clamp((edgeUsage - 0.76f) / 0.20f,
                                  0.0f, 1.0f));
        const float headingInstability =
            smoothstep(std::clamp((headingError - 0.14f) / 0.18f,
                                  0.0f, 1.0f));
        const float controlInstability = std::max(edgeInstability, headingInstability);
        if (!committedFlatCorner) {
            targetSpeed = std::min(targetSpeed,
                                   controllerTopSpeed * lerp(1.0f, 0.52f, controlInstability));
        }

        bool collisionSpeedConstraint = false;
        kart.aiCollisionTargetIndex = -1;
        kart.aiTrafficTimeToCollision =
            std::numeric_limits<float>::max();
        kart.aiTrafficRequiredDeceleration = 0.0f;
        if (raceTraffic && !monzaRacecraft &&
            !committedFlatCorner) {
            float followingSpeed =
                std::numeric_limits<float>::max();
            for (int i = 0; i < activeKartCount(); ++i) {
                if (i == index) {
                    continue;
                }
                const Kart3D& other =
                    karts_[static_cast<size_t>(i)];
                if (kart.ghostTimer > 0.0f ||
                    other.ghostTimer > 0.0f) {
                    continue;
                }
                const float ahead = progressAhead(
                    kart.progress, other.progress,
                    track_.totalLength());
                const float lateralGap =
                    std::min({
                        std::abs(other.lane -
                                 kart.lane),
                        std::abs(other.lane -
                                 laneTarget),
                        std::abs(
                            other.aiCommandLineTarget -
                            laneTarget)});
                const float laneOverlap =
                    (kart.spec.width +
                     other.spec.width) *
                        0.75f +
                    0.40f * recoveryUnits;
                if (ahead > 0.25f &&
                    ahead < 92.0f &&
                    lateralGap < laneOverlap) {
                    const float desiredGap =
                        approachingTurnIn ? 19.0f
                                          : 15.0f;
                    const float gapSpeedMetersPerSecond =
                        std::clamp(
                            (ahead - desiredGap) *
                                0.92f,
                            -24.0f, 24.0f);
                    const float candidateFollowingSpeed =
                        length(other.vel) +
                        gapSpeedMetersPerSecond *
                            recoveryUnits;
                    if (candidateFollowingSpeed <
                        followingSpeed) {
                        followingSpeed =
                            candidateFollowingSpeed;
                        kart.aiCollisionTargetIndex = i;
                    }
                }
            }
            collisionSpeedConstraint =
                followingSpeed < targetSpeed - 1.0f;
            targetSpeed =
                std::min(targetSpeed, followingSpeed);
        } else if (raceTraffic && monzaRacecraft) {
            float followingSpeed = std::numeric_limits<float>::max();
            for (int i = 0; i < activeKartCount(); ++i) {
                if (i == index) {
                    continue;
                }
                const Kart3D& other = karts_[static_cast<size_t>(i)];
                if (kart.ghostTimer > 0.0f ||
                    other.ghostTimer > 0.0f) {
                    continue;
                }
                const float ahead = progressAhead(
                    kart.progress, other.progress,
                    track_.totalLength());
                const float ownSpeedMetersPerSecond =
                    speed / recoveryUnits;
                const float otherSpeedMetersPerSecond =
                    length(other.vel) / recoveryUnits;
                const float maximumFollowingRange =
                    std::max(
                        55.0f,
                        ownSpeedMetersPerSecond *
                            (approachingTurnIn ? 1.45f
                                             : 1.20f));
                const TrackPoint3D otherPoint =
                    track_.sample(other.progress);
                const float otherProjectedLane =
                    i == 0
                        ? other.lane +
                              dot(other.vel,
                                  otherPoint.normal) *
                                  0.45f
                        : lerp(other.lane,
                               other.aiCommandLineTarget,
                               0.60f);
                const float ownProjectedLane =
                    lerp(kart.lane, laneTarget, 0.68f);
                const float currentLateralGap =
                    std::abs(kart.lane - other.lane);
                const float projectedLateralGap =
                    std::abs(ownProjectedLane -
                             otherProjectedLane);
                const float laneOverlap =
                    (kart.spec.width +
                     other.spec.width) *
                        0.50f +
                    0.18f * recoveryUnits;
                const float halfCombinedLengthMeters =
                    (kart.spec.length +
                     other.spec.length) *
                    0.50f / recoveryUnits;
                const float bumperGap =
                    ahead - halfCombinedLengthMeters;
                const float closingSpeed =
                    ownSpeedMetersPerSecond -
                    otherSpeedMetersPerSecond;
                const float timeToCollision =
                    closingSpeed > 0.05f
                        ? bumperGap / closingSpeed
                        : std::numeric_limits<float>::max();
                const bool passEstablished =
                    projectedLateralGap >= laneOverlap &&
                    (currentLateralGap >=
                         laneOverlap * 0.82f ||
                     timeToCollision > 0.85f);
                if (ahead > 0.25f &&
                    ahead < maximumFollowingRange &&
                    !passEstablished) {
                    float expectedLeadSpeed =
                        otherSpeedMetersPerSecond;
                    // React to braking that is physically happening, not the
                    // leader's speed target at its current station.  Copying
                    // that target backward through the pack makes every car
                    // brake for a corner earlier than the car ahead.
                    expectedLeadSpeed =
                        std::max(
                            0.0f,
                            expectedLeadSpeed -
                                other.brakeLoad *
                                    other.tuning
                                        .brakeDeceleration /
                                    recoveryUnits *
                                    0.28f);
                    const float desiredGap =
                        1.6f +
                        std::max(0.0f,
                                 closingSpeed * 0.55f) +
                        (approachingTurnIn ? 1.2f
                                           : 0.0f);
                    const float reactionDistance =
                        std::max(0.0f, closingSpeed) *
                        (approachingTurnIn ? 0.55f
                                           : 0.38f);
                    const float usableGap =
                        std::max(
                            0.0f,
                            bumperGap - desiredGap -
                                reactionDistance);
                    const float planningDeceleration =
                        kart.tuning.brakeDeceleration /
                        recoveryUnits * 0.68f;
                    const float safeSpeed =
                        std::sqrt(
                            expectedLeadSpeed *
                                    expectedLeadSpeed +
                            2.0f *
                                planningDeceleration *
                                usableGap);
                    const float gapControlSpeed =
                        expectedLeadSpeed +
                        std::clamp(
                            (bumperGap - desiredGap) *
                                0.82f,
                            -18.0f, 24.0f);
                    const float candidateFollowingSpeed =
                        std::max(
                            0.0f,
                            std::min(safeSpeed,
                                     gapControlSpeed)) *
                        recoveryUnits;
                    if (candidateFollowingSpeed <
                        followingSpeed) {
                        followingSpeed =
                            candidateFollowingSpeed;
                        kart.aiCollisionTargetIndex = i;
                        kart.aiTrafficTimeToCollision =
                            timeToCollision;
                        if (bumperGap > 0.10f) {
                            kart.aiTrafficRequiredDeceleration =
                                std::max(
                                    0.0f,
                                    (ownSpeedMetersPerSecond *
                                             ownSpeedMetersPerSecond -
                                     expectedLeadSpeed *
                                         expectedLeadSpeed) /
                                        (2.0f *
                                         bumperGap));
                        }
                    }
                }
            }
            collisionSpeedConstraint =
                followingSpeed < targetSpeed - 1.0f;
            targetSpeed = std::min(targetSpeed, followingSpeed);
        }

        Input3D ai = auditInput(AuditDriver::Attack, kart);
        ai.automaticShift = true;
        ai.steer = aiSteerForProgress(kart, index, laneTarget, false, true);
        const float speedError = speed - targetSpeed;
        const float brakeBand = std::max(12.0f, kart.tuning.maxForwardSpeed * 0.035f);
        constexpr float kTargetOverspeedToleranceKph =
            4.0f;
        const float targetOverspeedTolerance =
            kTargetOverspeedToleranceKph /
            speedKphPerSimulationUnit(
                track_.layout());
        const bool targetEnvelopeRequiresBraking =
            speedError > targetOverspeedTolerance;
        const bool terminalSpeedTarget =
            targetSpeed >= controllerTopSpeed * 0.985f;
        const bool mayBrakeForTarget =
            !committedFlatCorner ||
            collisionSpeedConstraint ||
            (targetEnvelopeRequiresBraking &&
             (!monzaRacecraft ||
              !terminalSpeedTarget));
        if (speedError > targetOverspeedTolerance &&
            mayBrakeForTarget) {
            ai.throttle = 0.0f;
            const float minimumBrake = track_.layout() == TrackLayoutId::Suzuka ? 0.38f : 0.08f;
            ai.brake = std::clamp(minimumBrake + speedError / brakeBand,
                                  minimumBrake, 1.0f);
        } else {
            const bool speedLimitedSection =
                targetSpeed < controllerTopSpeed * 0.985f;
            if (mayBrakeForTarget && speedLimitedSection &&
                speedError > -brakeBand) {
                // Feed in only the longitudinal grip the planned corner speed
                // can absorb. This is exit traction management, not cruising:
                // unrestricted sections still receive full throttle.
                ai.throttle = std::clamp(-speedError / brakeBand * 1.35f, 0.05f, 1.0f);
            } else {
                ai.throttle = 1.0f;
            }
            ai.brake = 0.0f;
        }
        if (raceTraffic && !monzaRacecraft &&
            !committedFlatCorner) {
            for (int i = 0; i < activeKartCount(); ++i) {
                if (i == index) {
                    continue;
                }
                const Kart3D& other =
                    karts_[static_cast<size_t>(i)];
                if (kart.ghostTimer > 0.0f ||
                    other.ghostTimer > 0.0f) {
                    continue;
                }
                const float ahead = progressAhead(
                    kart.progress, other.progress,
                    track_.totalLength());
                const float lateralGap = std::min(
                    std::abs(kart.lane - other.lane),
                    std::abs(
                        kart.aiCommandLineTarget -
                        other.aiCommandLineTarget));
                const bool tightSuzukaCorridor =
                    track_.layout() ==
                    TrackLayoutId::Suzuka;
                const float collisionWidth =
                    (kart.spec.width +
                     other.spec.width) *
                        (tightSuzukaCorridor ? 0.70f
                                             : 0.58f) +
                    (tightSuzukaCorridor ? 0.40f
                                         : 0.30f) *
                        recoveryUnits;
                const float closingSpeedMetersPerSecond =
                    (speed - length(other.vel)) /
                    recoveryUnits;
                const float baseEmergencyGap =
                    tightSuzukaCorridor ? 9.0f
                                        : 7.5f;
                const float closingHorizon =
                    tightSuzukaCorridor ? 1.00f
                                        : 0.90f;
                const float emergencyGap =
                    std::max(
                        baseEmergencyGap,
                        baseEmergencyGap +
                            closingSpeedMetersPerSecond *
                                closingHorizon);
                if (ahead > 0.10f &&
                    ahead < emergencyGap &&
                    lateralGap < collisionWidth) {
                    collisionSpeedConstraint = true;
                    kart.aiCollisionTargetIndex = i;
                    ai.throttle = 0.0f;
                    ai.brake = std::max(
                        ai.brake,
                        tightSuzukaCorridor ? 1.0f
                                           : 0.92f);
                }
            }
        } else if (raceTraffic && monzaRacecraft &&
                   collisionSpeedConstraint) {
            const float availableDeceleration =
                kart.tuning.brakeDeceleration /
                recoveryUnits;
            const float requiredBrakeFraction =
                kart.aiTrafficRequiredDeceleration /
                std::max(1.0f,
                         availableDeceleration);
            const bool imminentContact =
                kart.aiTrafficTimeToCollision < 0.62f;
            if (imminentContact ||
                requiredBrakeFraction > 0.78f) {
                // This is the final safety layer after predictive following.
                // Its strength follows the actual closing energy instead of
                // applying a fixed late brake to every occupied corridor.
                ai.throttle = 0.0f;
                ai.brake = std::max(
                    ai.brake,
                    std::clamp(
                        requiredBrakeFraction * 1.08f,
                        imminentContact ? 0.42f : 0.18f,
                        1.0f));
            }
        }
        bool roadRecoveryConstraint = false;
        if (laneExcess > 1.0f &&
            !committedFlatCorner) {
            roadRecoveryConstraint = true;
            ai.throttle =
                laneExcess >
                        0.75f * recoveryUnits
                    ? 0.0f
                    : std::min(ai.throttle, 0.30f);
            ai.brake = std::max(
                ai.brake,
                std::clamp(
                    laneExcess / 42.0f,
                    0.18f, 0.68f));
        }
        ai.drift = false;
        if (raceTraffic) {
            kart.aiLaunchElapsed += dt;
            if (kart.aiLaunchElapsed <
                kart.aiLaunchDuration) {
                ai.throttle = std::min(
                    ai.throttle,
                    kart.aiLaunchThrottleScale);
            }
        }
        kart.aiCommandDrsPlanActive =
            kart.drsActive;
        kart.drsActive =
            kart.drsAvailable &&
            ai.brake <= 0.01f;
        kart.aiCommandSteer = ai.steer;
        kart.aiCommandLineTarget = laneTarget;
        kart.aiCommandLineProgress = kart.progress;
        kart.aiCommandTargetSpeed = targetSpeed;
        kart.aiCommandThrottle = ai.throttle;
        kart.aiCommandBrake = ai.brake;
        kart.aiCollisionBrakeConstraint = collisionSpeedConstraint;
        kart.aiRoadRecoveryConstraint =
            roadRecoveryConstraint;
        integrateKart(kart, ai, dt);
        if (monzaRacecraft) {
            containMonzaKartWithinCurbs(kart);
        }
    }

    void applyMonzaSlipstream(float dt) {
        const float units = kTrackSimulationUnitsPerMeter;
        const float trackLength = track_.totalLength();
        std::array<float, kKartCount> draftAcceleration{};
        for (int index = 0; index < activeKartCount(); ++index) {
            const Kart3D& kart =
                karts_[static_cast<size_t>(index)];
            if (kart.brakeLoad > 0.08f ||
                length(kart.vel) <
                    28.0f * units ||
                !isPhysicsValidatedFlatProgress(
                    kart.progress)) {
                continue;
            }
            float nearestAhead =
                std::numeric_limits<float>::max();
            for (int otherIndex = 0;
                 otherIndex < activeKartCount(); ++otherIndex) {
                if (otherIndex == index) {
                    continue;
                }
                const Kart3D& other =
                    karts_[static_cast<size_t>(otherIndex)];
                const float ahead = progressAhead(
                    kart.progress, other.progress,
                    trackLength);
                const float lateralGap =
                    std::abs(kart.lane - other.lane) /
                    units;
                if (ahead > 5.0f &&
                    ahead < 68.0f &&
                    lateralGap < 2.8f) {
                    nearestAhead =
                        std::min(nearestAhead, ahead);
                }
            }
            if (!std::isfinite(nearestAhead)) {
                continue;
            }
            const float distanceStrength =
                1.0f -
                smoothstep(std::clamp(
                    (nearestAhead - 8.0f) / 60.0f,
                    0.0f, 1.0f));
            const float alignment =
                std::clamp(
                    dot(normalize(kart.vel),
                        track_.sample(kart.progress)
                            .tangent),
                    0.0f, 1.0f);
            draftAcceleration[static_cast<size_t>(index)] =
                1.80f * distanceStrength * alignment;
        }
        for (int index = 0; index < activeKartCount(); ++index) {
            Kart3D& kart =
                karts_[static_cast<size_t>(index)];
            const float acceleration =
                draftAcceleration[static_cast<size_t>(index)];
            if (acceleration <= 0.0f) {
                continue;
            }
            const TrackPoint3D point =
                track_.sample(kart.progress);
            const float draftSpeedLimit =
                kart.tuning.maxForwardSpeed *
                kMonzaDraftTopSpeedScale;
            const float forwardSpeed =
                dot(kart.vel, point.tangent);
            if (forwardSpeed >= draftSpeedLimit) {
                continue;
            }
            const float appliedAcceleration =
                std::min(
                    acceleration * units,
                    (draftSpeedLimit - forwardSpeed) /
                        std::max(dt, 0.0001f));
            kart.vel += point.tangent *
                        (appliedAcceleration * dt);
        }
    }

    Input3D auditInput(AuditDriver driver, const Kart3D& kart) const {
        const float speed = length(kart.vel);
        const float distanceSpeed = isMetricCircuit(track_.layout())
                                        ? speed / kTrackSimulationUnitsPerMeter
                                        : speed;
        const float pathSpeed = distanceSpeed / kRacePaceScale;
        const float futureDistance = isMetricCircuit(track_.layout())
                                         ? 155.0f + pathSpeed * 1.35f
                                         : 95.0f + pathSpeed * 0.88f;
        const float apexDistance = isMetricCircuit(track_.layout())
                                       ? 275.0f + pathSpeed * 0.95f
                                       : 155.0f + pathSpeed * 0.58f;
        const float immediateDistance = isMetricCircuit(track_.layout())
                                            ? 38.0f + pathSpeed * 0.18f
                                            : 24.0f + pathSpeed * 0.12f;
        const TrackPoint3D future = track_.sample(kart.progress + futureDistance);
        const TrackPoint3D apex = track_.sample(kart.progress + apexDistance);
        const TrackPoint3D immediate = track_.sample(kart.progress + immediateDistance);
        const TrackPoint3D center = isMetricCircuit(track_.layout())
                                        ? track_.sample(kart.progress)
                                        : track_.pointAtIndex(kart.nearest);
        float corner = std::max(future.curvature, apex.curvature);
        if (isMetricCircuit(track_.layout())) {
            for (float distance = 40.0f; distance <= 340.0f; distance += 20.0f) {
                corner = std::max(corner, track_.sample(kart.progress + distance).curvature);
            }
        }
        const float turnSign = apex.signedCurvature == 0.0f ? future.signedCurvature : apex.signedCurvature;
        const float recoveryInset = isMetricCircuit(track_.layout())
                                        ? 0.75f * kTrackSimulationUnitsPerMeter
                                        : 12.0f;
        const float recoveryLine = std::max(1.0f, roadCenterLimit(kart, center) - recoveryInset);
        const float laneExcess = std::max(0.0f, std::abs(kart.lane) - recoveryLine);
        float laneTarget = 0.0f;
        if (driver == AuditDriver::Attack && laneExcess <= 1.0f) {
            laneTarget = -std::copysign(6.0f, turnSign) * std::clamp(corner * 2.6f, 0.0f, 1.0f);
        }

        Input3D input;
        input.automaticShift = true;
        input.steer = aiSteerForProgress(kart, 0, laneTarget);
        if (isMetricCircuit(track_.layout())) {
            const float laneLimit = std::max(1.0f, roadCenterLimit(kart, center));
            input.steer = std::clamp(input.steer - kart.lane / laneLimit * 1.15f, -1.0f, 1.0f);
        }
        input.throttle = 1.0f;

        const float targetScale = isMetricCircuit(track_.layout())
                                      ? std::clamp((driver == AuditDriver::Attack ? 1.04f : 1.02f) - corner * 2.25f,
                                                   0.23f, 1.00f)
                                      : std::clamp((driver == AuditDriver::Attack ? 1.06f : 1.04f) - corner * 3.15f, 0.56f, 1.05f);
        const float targetSpeed = kart.tuning.maxForwardSpeed * targetScale;
        if (driver == AuditDriver::Brake || driver == AuditDriver::Attack) {
            const bool needsBrake = speed > targetSpeed + (driver == AuditDriver::Attack ? 12.0f : 7.0f) * kRacePaceScale;
            if (needsBrake) {
                const bool beforeTurn = immediate.curvature < std::max(0.10f, corner * 0.72f) &&
                                        std::abs(input.steer) < 0.82f;
                input.brake = beforeTurn
                                  ? std::clamp((speed - targetSpeed) / (42.0f * kRacePaceScale),
                                               driver == AuditDriver::Attack ? 0.18f : 0.22f, 0.90f)
                                  : 0.0f;
                input.throttle = 0.0f;
            }
        }
        if (driver != AuditDriver::NoBrake && laneExcess > 1.0f) {
            input.steer = std::clamp(aiSteerForProgress(kart, 0, 0.0f) -
                                         kart.lane / std::max(1.0f, roadCenterLimit(kart, center)) * 1.18f,
                                     -1.0f, 1.0f);
            const bool recoveryNeedsBrake = isMetricCircuit(track_.layout())
                                                ? speed > kart.tuning.maxForwardSpeed * 0.10f
                                                : speed > targetSpeed * 0.82f;
            input.throttle = recoveryNeedsBrake ? 0.0f : 0.38f;
            input.brake = recoveryNeedsBrake
                              ? std::max(input.brake,
                                         std::clamp(laneExcess /
                                                        (isMetricCircuit(track_.layout())
                                                             ? 2.0f * kTrackSimulationUnitsPerMeter
                                                             : 38.0f),
                                                    0.24f, 0.62f))
                              : 0.0f;
            input.drift = false;
        }
        input.drift = false;
        return input;
    }

    AuditResult3D simulateAuditDriver(AuditDriver driver, float seconds) {
        particles_.clear();
        const TrackPoint3D start = track_.sample(0.0f);
        Kart3D kart;
        kart.spec = specs_[0];
        kart.tuning = selectedTrackTuning(kart.spec);
        kart.racer = racers_[0];
        kart.pos = start.pos;
        kart.heading = angleOf(start.tangent);
        kart.vel = {};
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.progress = track_.pointAtIndex(kart.nearest).progress;
        kart.previousProgress = kart.progress;

        AuditResult3D result;
        result.name = driver == AuditDriver::NoBrake ? "no_brake" : (driver == AuditDriver::Brake ? "brake" : "attack");

        const int frames = static_cast<int>(seconds / kFixedDt);
        float speedSum = 0.0f;
        float cumulativeProgress = 0.0f;
        bool hasBraked = false;
        for (int frame = 0; frame < frames; ++frame) {
            const float beforeContact = kart.contactTimer;
            const float beforeProgress = kart.progress;
            const bool wasGrounded = kart.grounded;
            const Input3D input = auditInput(driver, kart);
            if (input.brake > 0.20f) {
                ++result.brakeFrames;
                hasBraked = true;
            }
            if (hasBraked && input.brake < 0.05f && input.throttle > 0.80f) {
                ++result.poweredExitFrames;
            }
            updatePlayer(kart, input, kFixedDt);
            const float progressDelta = signedDistanceToLoop(beforeProgress, kart.progress, track_.totalLength());
            if (progressDelta < -40.0f || progressDelta > 90.0f) {
                ++result.progressJumps;
            } else {
                cumulativeProgress += progressDelta;
            }
            const TrackPoint3D center = track_.pointAtIndex(kart.nearest);
            const float offroad = roadEdgeViolation(kart, center);
            const float speed = std::max(0.0f, dot(kart.vel, fromAngle(kart.heading)));
            speedSum += speed;
            result.maxSpeed = std::max(result.maxSpeed, speed);
            if (offroad > result.maxOffroad) {
                result.maxOffroad = offroad;
                result.maxOffroadPhase = kart.progress / track_.totalLength();
            }
            result.maxDriftCharge = std::max(result.maxDriftCharge, kart.driftCharge);
            result.maxSlip = std::max(result.maxSlip, std::abs(kart.slipAngle));
            result.maxAirTime = std::max(result.maxAirTime, kart.airborneTime);
            result.landings += !wasGrounded && kart.grounded ? 1 : 0;
            result.minGroundClearance = std::min(result.minGroundClearance, activeRendererWheelGroundClearance(kart));
            result.offroadFrames += offroad > 1.0f ? 1 : 0;
            result.driftFrames += kart.drifting ? 1 : 0;
            result.brakeDriftFrames += kart.brakeLoad > 0.20f && std::abs(kart.slipAngle) > 0.14f ? 1 : 0;
            result.boostFrames += kart.boostTimer > 0.0f ? 1 : 0;
            if (beforeContact <= 0.001f && kart.contactTimer > 0.05f) {
                ++result.contacts;
            }
        }
        result.score = cumulativeProgress;
        result.averageSpeed = speedSum / static_cast<float>(frames);
        result.lap = kart.lap;
        particles_.clear();
        return result;
    }

    float aiSteerForProgress(const Kart3D& kart, int index, float laneTarget,
                             bool tangentAware = false, bool opponentController = false) const {
        (void)index;
        const float speed = length(kart.vel);
        const float distanceSpeed = isMetricCircuit(track_.layout())
                                        ? speed / kTrackSimulationUnitsPerMeter
                                        : speed;
        if (opponentController && isMetricCircuit(track_.layout())) {
            const AiTimeTrialProfile profile =
                activeAiTimeTrialProfile(track_.layout());
            const float normalizedSpeed = speed / std::max(1.0f, kart.tuning.maxForwardSpeed);
            const float steerFade = smoothstep((normalizedSpeed - kart.tuning.steerFadeStart) /
                                               std::max(0.001f, 1.0f - kart.tuning.steerFadeStart));
            const float maxSteer = lerp(kart.tuning.maxSteerLowSpeed,
                                        kart.tuning.maxSteerHighSpeed, steerFade);
            if (track_.layout() == TrackLayoutId::Shanghai ||
                track_.layout() == TrackLayoutId::Sepang ||
                track_.layout() == TrackLayoutId::Cota ||
                track_.layout() == TrackLayoutId::Istanbul ||
                track_.layout() == TrackLayoutId::Hockenheim ||
                track_.layout() == TrackLayoutId::Buddh) {
                const float previewMeters =
                    std::clamp(
                        profile.lookaheadBaseMeters +
                            distanceSpeed *
                                profile.lookaheadSpeedSeconds,
                        10.0f, profile.lookaheadMaximumMeters);
                const float tangentSpanMeters = 5.0f;
                const Vec2 tangentBefore = normalize(
                    plannedAiPosition(kart.progress + previewMeters) -
                    plannedAiPosition(kart.progress + previewMeters - tangentSpanMeters));
                const Vec2 tangentAfter = normalize(
                    plannedAiPosition(kart.progress + previewMeters + tangentSpanMeters) -
                    plannedAiPosition(kart.progress + previewMeters));
                const Vec2 desiredTangent = normalize(tangentBefore + tangentAfter);
                const float signedCurvaturePerUnit =
                    wrapAngle(angleOf(tangentAfter) - angleOf(tangentBefore)) /
                    (2.0f * tangentSpanMeters * kTrackSimulationUnitsPerMeter);
                const float feedForwardSteer =
                    std::atan(kart.tuning.wheelbase * signedCurvaturePerUnit);
                const float headingError =
                    wrapAngle(angleOf(desiredTangent) - kart.heading);
                const float lateralError = laneTarget - kart.lane;
                const float crossTrackHeading = std::atan2(
                    lateralError * 1.9f,
                    std::max(5.0f * kTrackSimulationUnitsPerMeter, speed));
                const float requestedSteerAngle =
                    feedForwardSteer +
                    headingError * profile.headingGain +
                    crossTrackHeading * profile.crossTrackGain;
                return std::clamp(
                    requestedSteerAngle / std::max(0.01f, maxSteer),
                    -1.0f, 1.0f);
            }
            if (track_.layout() == TrackLayoutId::Spa || track_.layout() == TrackLayoutId::Suzuka) {
                const bool linkedEsses =
                    track_.layout() == TrackLayoutId::Suzuka;
                const float lookaheadMeters =
                    std::clamp(
                        profile.lookaheadBaseMeters +
                            distanceSpeed *
                                profile.lookaheadSpeedSeconds,
                        linkedEsses ? 8.0f : 14.0f,
                        profile.lookaheadMaximumMeters);
                const TrackPoint3D controlPoint = track_.sample(kart.progress + lookaheadMeters);
                const float lateralError = laneTarget - kart.lane;
                const float headingError = wrapAngle(angleOf(controlPoint.tangent) - kart.heading);
                const float sampleSpacingMeters = track_.totalLength() /
                                                  static_cast<float>(track_.sampleCount());
                const float signedCurvaturePerUnit = controlPoint.signedCurvature /
                                                     std::max(1.0f, 16.0f * sampleSpacingMeters *
                                                                        kTrackSimulationUnitsPerMeter);
                const float feedForwardSteer = std::atan(kart.tuning.wheelbase * signedCurvaturePerUnit);
                const float crossTrackHeading = std::atan2(
                    lateralError * 1.8f,
                    std::max(5.0f * kTrackSimulationUnitsPerMeter, speed));
                const float requestedSteerAngle =
                    feedForwardSteer +
                    headingError * profile.headingGain +
                    crossTrackHeading * profile.crossTrackGain;
                return std::clamp(requestedSteerAngle / std::max(0.01f, maxSteer), -1.0f, 1.0f);
            }
            const float lookaheadMeters = std::clamp(
                profile.lookaheadBaseMeters +
                    distanceSpeed * profile.lookaheadSpeedSeconds,
                14.0f, profile.lookaheadMaximumMeters);
            const float laneOffset = laneTarget - plannedAiLane(kart.progress);
            const float controlProgress = kart.progress + lookaheadMeters;
            const Vec2 targetPosition = plannedAiPosition(controlProgress, laneOffset);
            const Vec2 targetDirection = normalize(targetPosition - kart.pos);
            const float targetAngle = wrapAngle(angleOf(targetDirection) - kart.heading);
            const float requestedSteerAngle = std::atan2(
                2.0f * kart.tuning.wheelbase * std::sin(targetAngle),
                lookaheadMeters * kTrackSimulationUnitsPerMeter);
            return std::clamp(requestedSteerAngle / std::max(0.01f, maxSteer), -1.0f, 1.0f);
        }
        const float pathSpeed = distanceSpeed / kRacePaceScale;
        const float steeringCurvature = std::max({std::abs(smoothedSignedCurvature(kart.progress + 90.0f)),
                                                  std::abs(smoothedSignedCurvature(kart.progress + 180.0f)),
                                                  std::abs(smoothedSignedCurvature(kart.progress + 290.0f))});
        const float metricCornerHorizonScale = opponentController ? 0.30f : 0.14f;
        const float horizonScale = lerp(1.0f, isMetricCircuit(track_.layout()) ? metricCornerHorizonScale : 0.30f,
                                        std::clamp((steeringCurvature - 0.08f) / 0.48f, 0.0f, 1.0f));
        const float minimumHorizon = isMetricCircuit(track_.layout())
                                         ? (opponentController ? 48.0f : 24.0f)
                                         : 55.0f;
        const float steeringHorizon = std::clamp((128.0f + pathSpeed * 0.65f) * horizonScale,
                                                 minimumHorizon, 340.0f);
        const TrackPoint3D future = track_.sample(kart.progress + steeringHorizon);
        if (!isMetricCircuit(track_.layout())) {
            laneTarget -= std::copysign(13.0f, future.signedCurvature) *
                          std::clamp(future.curvature * 4.0f, 0.0f, 1.0f);
        }
        const Vec2 desired = future.pos + future.normal * laneTarget;
        const Vec2 forward = fromAngle(kart.heading);
        const Vec2 toTarget = normalize(desired - kart.pos);
        // Opponent pure pursuit alone points across the inside of a bend.
        // Blending in the road tangent follows the corner shape and begins
        // rotating before lane error accumulates. Audit/player steering keeps
        // the original pure-pursuit behavior.
        const Vec2 desiredDirection = tangentAware
                                          ? normalize(toTarget * 0.58f + future.tangent * 0.42f)
                                          : toTarget;
        const float steeringGain = isMetricCircuit(track_.layout()) ? 1.85f : 1.95f;
        return std::clamp(std::atan2(cross(forward, desiredDirection), dot(forward, desiredDirection)) * steeringGain,
                          -1.0f, 1.0f);
    }

    CollisionAuditResult3D simulateCollisionScenario(const char* name, int scenario) {
        resetRace();
        CollisionAuditResult3D result;
        result.name = name;

        const TrackPoint3D base = track_.sample(2600.0f + static_cast<float>(scenario) * 860.0f);
        const Vec2 forward = base.tangent;
        const Vec2 right = base.normal;
        const float heading = angleOf(forward);

        for (int i = 2; i < kKartCount; ++i) {
            TrackPoint3D park = track_.sample(5200.0f + static_cast<float>(i) * 540.0f);
            Kart3D& kart = karts_[static_cast<size_t>(i)];
            kart.pos = park.pos + park.normal * (680.0f + static_cast<float>(i) * 40.0f);
            kart.vel = {};
            kart.heading = angleOf(park.tangent);
            kart.nearest = track_.nearestIndex(kart.pos);
            updateProgress(kart);
        }

        auto place = [&](int index, Vec2 pos, float kartHeading, Vec2 vel) {
            Kart3D& kart = karts_[static_cast<size_t>(index)];
            kart.pos = pos;
            kart.heading = kartHeading;
            kart.vel = vel;
            kart.drifting = false;
            kart.boostTimer = 0.0f;
            kart.contactTimer = 0.0f;
            kart.ghostTimer = 0.0f;
            kart.elevation = bankedElevation(base, 0.0f);
            kart.verticalSpeed = 0.0f;
            kart.grounded = true;
            kart.nearest = track_.nearestIndex(kart.pos);
            updateProgress(kart);
        };

        if (scenario == 0) {
            place(0, base.pos - forward * 92.0f, heading, forward * 126.0f);
            place(1, base.pos, heading, forward * 44.0f);
        } else if (scenario == 1) {
            place(0, base.pos - forward * 88.0f, heading, forward * 98.0f);
            place(1, base.pos + forward * 88.0f, wrapAngle(heading + kPi), forward * -96.0f);
        } else {
            const float speedPerKph =
                kTrackSimulationUnitsPerMeter /
                3.6f;
            place(
                0,
                base.pos - forward * 44.0f -
                    right * 34.0f,
                heading,
                forward * (300.0f * speedPerKph) +
                    right *
                        (2.5f *
                         kTrackSimulationUnitsPerMeter));
            place(
                1,
                base.pos + forward * 8.0f +
                    right * 22.0f,
                heading,
                forward * (292.0f * speedPerKph) -
                    right *
                        (1.5f *
                         kTrackSimulationUnitsPerMeter));
        }

        constexpr int kFrames = static_cast<int>(3.2f / kFixedDt);
        bool sampledFirstContact = false;
        for (int frame = 0; frame < kFrames; ++frame) {
            for (int i = 0; i < 2; ++i) {
                Kart3D& kart = karts_[static_cast<size_t>(i)];
                kart.contactTimer = std::max(0.0f, kart.contactTimer - kFixedDt);
                kart.pos += kart.vel * kFixedDt;
                kart.vel *= std::exp(-kFixedDt * 0.08f);
                updateProgress(kart);
            }
            const float strikerSpeedBefore =
                dot(karts_[0].vel, forward);
            const float targetSpeedBefore =
                dot(karts_[1].vel, forward);
            solveKartContacts();
            if (!sampledFirstContact && (karts_[0].contactTimer > 0.05f || karts_[1].contactTimer > 0.05f)) {
                result.strikerSpeedBeforeContact =
                    strikerSpeedBefore;
                result.targetSpeedBeforeContact =
                    targetSpeedBefore;
                result.strikerSpeedAfterContact = dot(karts_[0].vel, forward);
                result.targetSpeedAfterContact = dot(karts_[1].vel, forward);
                sampledFirstContact = true;
            }
            const float overlap = maxKartOverlap();
            result.maxOverlap = std::max(result.maxOverlap, overlap);
            if (overlap > 1.25f) {
                ++result.overlapFrames;
            }
            if (karts_[0].contactTimer > 0.05f || karts_[1].contactTimer > 0.05f) {
                ++result.contactFrames;
            }
            result.maxContactImpulse = std::max({result.maxContactImpulse,
                                                 karts_[0].contactImpulse,
                                                 karts_[1].contactImpulse});
            result.vehicleTelemetry = result.vehicleTelemetry ||
                                      (karts_[0].vehicleContact && karts_[0].contactCause == ContactCause3D::Vehicle) ||
                                      (karts_[1].vehicleContact && karts_[1].contactCause == ContactCause3D::Vehicle);
        }
        return result;
    }

    float formulaCornerGripScale(const Kart3D& kart, const TrackPoint3D& point) const {
        if (!isMetricCircuit(track_.layout())) {
            return 1.0f;
        }
        const float sampleSpacingMeters = track_.totalLength() / static_cast<float>(track_.sampleCount());
        const float curvaturePerMeter = point.curvature / std::max(0.01f, 16.0f * sampleSpacingMeters);
        if (curvaturePerMeter <= 0.00001f) {
            return 1.0f;
        }

        const float phase = wrapDistance(kart.progress, track_.totalLength()) / track_.totalLength();
        const float referenceGrip = kart.tuning.lateralGripAcceleration /
                                    std::max(0.01f, kart.spec.grip) * specs_[0].grip;
        const float baseAcceleration = referenceGrip / kTrackSimulationUnitsPerMeter;
        const float maxSpeedMetersPerSecond = kart.tuning.maxForwardSpeed / kTrackSimulationUnitsPerMeter;
        const float liveSpeedMetersPerSecond = length(kart.vel) / kTrackSimulationUnitsPerMeter;
        float gripScale = 1.0f;
        for (const FormulaCornerTarget& target : formulaCornerTargets(track_.layout())) {
            float phaseDistance = std::abs(phase - target.lapFraction);
            phaseDistance = std::min(phaseDistance, 1.0f - phaseDistance);
            const float window = target.fullThrottle ? 0.032f : 0.022f;
            if (phaseDistance >= window) {
                continue;
            }
            const float targetSpeed = target.speedKph / 3.6f;
            const float speedInfluence = smoothstep(std::clamp((liveSpeedMetersPerSecond - targetSpeed * 0.55f) /
                                                                   std::max(1.0f, targetSpeed * 0.35f),
                                                               0.0f, 1.0f));
            const float normalizedSpeed = std::clamp(targetSpeed / std::max(1.0f, maxSpeedMetersPerSecond), 0.0f, 1.25f);
            const float availableAcceleration = baseAcceleration * kart.tuning.tireLimitedYawScale *
                                                (1.0f + kart.tuning.downforceGripGain * normalizedSpeed * normalizedSpeed);
            const float requiredAcceleration = targetSpeed * targetSpeed * curvaturePerMeter;
            const float targetScale = std::clamp(requiredAcceleration / std::max(0.1f, availableAcceleration) * 1.06f,
                                                 1.0f, 3.0f);
            const float coreWindow = target.fullThrottle ? 0.022f : 0.015f;
            const float influence = phaseDistance <= coreWindow
                                        ? 1.0f
                                        : 1.0f - smoothstep((phaseDistance - coreWindow) /
                                                            std::max(0.001f, window - coreWindow));
            gripScale = std::max(gripScale, lerp(1.0f, targetScale, influence * speedInfluence));
        }
        return gripScale;
    }

    DrivingSurfaceResponse3D drivingSurfaceFor(const Kart3D& kart,
                                                const TrackPoint3D& center) const {
        DrivingSurfaceResponse3D response;
        const float laneAbs = std::abs(kart.lane);
        const float halfFootprint = contactHalfWidth(kart);
        const float asphaltOuter = roadSurfaceHalfWidth(center);
        const float curbOuter = asphaltOuter + kMetricCurbWidthMeters * kTrackSimulationUnitsPerMeter;
        const float tireCoverage = smoothstep(std::clamp(
            (laneAbs + halfFootprint - asphaltOuter) / std::max(1.0f, halfFootprint * 2.0f),
            0.0f, 1.0f));
        const float looseCoverage = smoothstep(std::clamp(
            (laneAbs + halfFootprint - curbOuter) / std::max(1.0f, halfFootprint * 2.0f),
            0.0f, 1.0f));

        const float side = kart.lane < 0.0f ? -1.0f : 1.0f;
        const float sampleLaneMeters = side * (laneAbs + halfFootprint) / kTrackSimulationUnitsPerMeter;
        const float roadHalfMeters = asphaltOuter / kTrackSimulationUnitsPerMeter;
        const TrackRunoffZone* zone = metricRunoffZoneAt(track_.layout(), center.progress,
                                                         sampleLaneMeters, roadHalfMeters);
        if (looseCoverage > 0.001f) {
            if (zone == nullptr) {
                response.kind = DrivingSurface3D::Grass;
            } else {
                switch (zone->surface) {
                    case TrackRunoffSurface::Asphalt:
                        response.kind = DrivingSurface3D::AsphaltRunoff;
                        break;
                    case TrackRunoffSurface::Gravel:
                        response.kind = DrivingSurface3D::Gravel;
                        break;
                    case TrackRunoffSurface::Grass:
                        response.kind = DrivingSurface3D::Grass;
                        break;
                }
            }
        } else if (tireCoverage > 0.001f) {
            response.kind = DrivingSurface3D::Curb;
        }

        ArcadeSurface& surface = response.physics;
        const float calibratedGrip = formulaCornerGripScale(kart, center);
        surface.grip = lerp(calibratedGrip, 1.0f, tireCoverage);
        surface.acceleration = 1.0f;
        surface.rollingResistance = 1.0f;
        surface.steering = 1.0f;
        surface.maxSpeed = 1.0f;
        surface.driftCharge = lerp(1.0f, 0.48f, tireCoverage);
        surface.bumpiness = tireCoverage * 0.10f;

        // Curbs remain driveable, but every surface beyond them has a clear
        // lap-time cost. Paved runoff is forgiving; gravel and grass are not.
        surface.grip *= lerp(1.0f, 0.94f, tireCoverage);
        surface.acceleration *= lerp(1.0f, 0.96f, tireCoverage);
        surface.rollingResistance = lerp(surface.rollingResistance, 1.22f, tireCoverage);
        surface.steering *= lerp(1.0f, 0.94f, tireCoverage);

        float targetGrip = 0.50f;
        float targetAcceleration = 0.35f;
        float targetResistance = 8.5f;
        float targetSteering = 0.56f;
        float targetMaxSpeed = 0.52f;
        float targetDriftCharge = 0.0f;
        float targetBumpiness = 0.72f;
        if (response.kind == DrivingSurface3D::AsphaltRunoff) {
            targetGrip = 0.90f;
            targetAcceleration = 0.82f;
            targetResistance = 2.0f;
            targetSteering = 0.88f;
            targetMaxSpeed = 0.86f;
            targetDriftCharge = 0.20f;
            targetBumpiness = 0.14f;
        } else if (response.kind == DrivingSurface3D::Gravel) {
            targetGrip = 0.62f;
            targetAcceleration = 0.48f;
            targetResistance = 7.0f;
            targetSteering = 0.68f;
            targetMaxSpeed = 0.62f;
            targetBumpiness = 0.55f;
        }
        surface.grip = lerp(surface.grip, targetGrip, looseCoverage);
        surface.acceleration = lerp(surface.acceleration, targetAcceleration, looseCoverage);
        surface.rollingResistance = lerp(surface.rollingResistance, targetResistance, looseCoverage);
        surface.steering = lerp(surface.steering, targetSteering, looseCoverage);
        surface.maxSpeed = lerp(surface.maxSpeed, targetMaxSpeed, looseCoverage);
        surface.driftCharge = lerp(surface.driftCharge, targetDriftCharge, looseCoverage);
        surface.bumpiness = lerp(surface.bumpiness, targetBumpiness, looseCoverage);
        surface.groundElevation = bankedElevation(center, kart.lane);
        surface.groundGrade = center.grade;
        surface.launchVelocity = tireCoverage < 0.15f ? center.launchVelocity * kRacePaceScale : 0.0f;
        surface.allowsDrift = looseCoverage < 0.20f;
        response.offTrackCoverage = looseCoverage;
        return response;
    }

    void integrateKart(Kart3D& kart, const Input3D& input, float dt) {
        kart.previousRenderPos = kart.pos;
        kart.previousRenderElevation = kart.elevation;
        kart.previousRenderHeading = kart.heading;
        kart.previousRenderProgress = kart.progress;
        if (kart.contactTimer <= 0.001f) {
            kart.contactImpulse = 0.0f;
            kart.contactCause = ContactCause3D::None;
            kart.vehicleContact = false;
        }
        kart.ghostTimer = std::max(0.0f, kart.ghostTimer - dt);
        updateProgress(kart);
        const TrackPoint3D center = track_.sample(kart.progress);
        const float offroad = roadEdgeViolation(kart, center);
        const DrivingSurfaceResponse3D drivingSurface = drivingSurfaceFor(kart, center);
        const ArcadeSurface& surface = drivingSurface.physics;

        ArcadeVehicleControl control;
        control.steer = input.steer;
        control.throttle = input.throttle;
        control.brake = input.brake;
        control.forwardSpeedLimitExtra =
            kart.drsActive ? drsTopSpeedExtra() : 0.0f;
        control.drift = input.drift;
        control.shiftUpPressed = input.shiftUp;
        control.shiftDownPressed = input.shiftDown;
        control.automaticShift = input.automaticShift;
        kart.telemetry = stepArcadeVehicle(kart, kart.tuning, control, surface, dt);

        emitFx(kart, center, offroad, dt);
        updateProgress(kart);
        constrainToTrack(kart);
        updateProgress(kart);
    }

    void constrainToTrack(Kart3D& kart) {
        const TrackPoint3D center = isMetricCircuit(track_.layout())
                                        ? track_.sample(kart.progress)
                                        : track_.pointAtIndex(kart.nearest);
        const float lane = dot(kart.pos - center.pos, center.normal);
        const float driveableLimit = hardBoundaryLaneLimit(kart, center);
        if (!isMetricCircuit(track_.layout())) {
            if (std::abs(lane) <= driveableLimit) {
                return;
            }
            const float sign = lane > 0.0f ? 1.0f : -1.0f;
            const float excess = std::abs(lane) - driveableLimit;
            kart.pos -= center.normal * (sign * (excess + 0.20f));
            const float normalVelocity = dot(kart.vel, center.normal);
            if (normalVelocity * sign > 0.0f) {
                const float incomingSpeed = length(kart.vel);
                Vec2 travelTangent = center.tangent;
                if (dot(travelTangent, kart.vel) < 0.0f) {
                    travelTangent *= -1.0f;
                }
                const float alongSpeed = std::max(0.0f, dot(kart.vel, travelTangent));
                const float redirectedSpeed = std::max(alongSpeed, incomingSpeed * 0.86f);
                kart.vel = travelTangent * redirectedSpeed - center.normal * (sign * std::abs(normalVelocity) * 0.055f);
                const float incidence = std::clamp(std::abs(normalVelocity) / std::max(1.0f, incomingSpeed), 0.0f, 1.0f);
                kart.heading = angleOf(normalize(lerp(fromAngle(kart.heading), travelTangent, 0.18f + incidence * 0.30f)));
                kart.yawRate *= 0.58f;
                kart.contactTimer = std::max(kart.contactTimer, 0.18f);
                kart.contactImpulse = std::max(kart.contactImpulse, std::abs(normalVelocity) * kartMass(kart));
                kart.contactCause = ContactCause3D::Barrier;
                kart.vehicleContact = false;
            }
            kart.drifting = false;
            return;
        }
        if (std::abs(lane) <= driveableLimit) {
            const float releaseInset = isMetricCircuit(track_.layout())
                                           ? 0.45f * kTrackSimulationUnitsPerMeter
                                           : 4.0f;
            if (std::abs(lane) < driveableLimit - releaseInset) {
                kart.barrierContact = false;
            }
            return;
        }
        const float sign = lane > 0.0f ? 1.0f : -1.0f;
        const float excess = std::abs(lane) - driveableLimit;
        const float separation = 0.06f * kTrackSimulationUnitsPerMeter;
        kart.pos -= center.normal * (sign * (excess + separation));
        const float normalVelocity = dot(kart.vel, center.normal);
        if (normalVelocity * sign > 0.0f) {
            const float incomingSpeed = length(kart.vel);
            const float alongVelocity = dot(kart.vel, center.tangent);
            const float incidence = std::clamp(std::abs(normalVelocity) / std::max(1.0f, incomingSpeed), 0.0f, 1.0f);
            const float impactSeverity = incidence * incidence;
            const float tangentRetention = lerp(0.96f, 0.18f, impactSeverity);
            const float restitution = lerp(0.06f, 0.015f, incidence);
            kart.vel = center.tangent * (alongVelocity * tangentRetention) -
                       center.normal * (sign * std::abs(normalVelocity) * restitution);
            kart.yawRate *= lerp(0.92f, 0.84f, incidence);
            if (!kart.barrierContact) {
                kart.contactTimer = std::max(kart.contactTimer, 0.18f);
            }
            kart.contactImpulse = std::max(kart.contactImpulse, std::abs(normalVelocity) * kartMass(kart));
            kart.contactCause = ContactCause3D::Barrier;
            kart.vehicleContact = false;
            kart.barrierContact = true;
        }
    }

    bool shouldTestKartContact(const Kart3D& a, const Kart3D& b) const {
        if (a.ghostTimer > 0.0f || b.ghostTimer > 0.0f) {
            return false;
        }
        const float progressGap = std::abs(signedDistanceToLoop(a.progress, b.progress, track_.totalLength()));
        if (progressGap > kContactProgressWindow) {
            return false;
        }
        const float elevationA = a.elevation;
        const float elevationB = b.elevation;
        return std::abs(elevationA - elevationB) <= kContactVerticalWindow;
    }

    void solveKartContacts() {
        std::array<bool, kKartCount> moved{};
        constexpr int kContactIterations = 10;
        for (int iter = 0; iter < kContactIterations; ++iter) {
            for (int a = 0; a < kKartCount; ++a) {
                for (int b = a + 1; b < kKartCount; ++b) {
                    Kart3D& ka = karts_[static_cast<size_t>(a)];
                    Kart3D& kb = karts_[static_cast<size_t>(b)];
                    if (!shouldTestKartContact(ka, kb)) {
                        continue;
                    }
                    const KartContact3D contact = kartContact(ka, kb);
                    if (!contact.touching || contact.penetration < 0.05f) {
                        continue;
                    }

                    const Vec2 n = contact.normal;
                    const float invA = inverseKartMass(ka);
                    const float invB = inverseKartMass(kb);
                    const float invSum = invA + invB;
                    const float correctionDepth = std::max(0.0f, contact.penetration - 0.08f);
                    const Vec2 correction = n * (correctionDepth * 0.98f / invSum);
                    ka.pos -= correction * invA;
                    kb.pos += correction * invB;
                    moved[static_cast<size_t>(a)] = true;
                    moved[static_cast<size_t>(b)] = true;

                    if (iter == 0) {
                        const Vec2 relativeVelocity = kb.vel - ka.vel;
                        float resolvedImpulse = 0.0f;
                        const Vec2 forwardA = fromAngle(ka.heading);
                        const Vec2 forwardB = fromAngle(kb.heading);
                        const Vec2 averageForward =
                            normalize(forwardA + forwardB);
                        const bool sameDirection =
                            dot(forwardA, forwardB) > 0.55f;
                        const bool averageForwardValid =
                            lengthSq(averageForward) > 0.01f;
                        const bool longitudinalContact =
                            averageForwardValid &&
                            std::abs(
                                dot(n, averageForward)) >
                                0.48f;
                        Vec2 impulseNormal = n;
                        if (sameDirection &&
                            !longitudinalContact &&
                            averageForwardValid) {
                            // A wheel-to-wheel brush should cancel lateral
                            // convergence without stealing the shared forward
                            // momentum of two cars travelling together.
                            const Vec2 lateralNormal =
                                n -
                                averageForward *
                                    dot(n, averageForward);
                            if (lengthSq(lateralNormal) >
                                0.0001f) {
                                impulseNormal =
                                    normalize(lateralNormal);
                                if (dot(impulseNormal, n) <
                                    0.0f) {
                                    impulseNormal *= -1.0f;
                                }
                            }
                        }
                        const float closingSpeed =
                            dot(relativeVelocity,
                                impulseNormal);
                        if (closingSpeed < 0.0f) {
                            const float launchSpeed = 14.0f * (isMetricCircuit(track_.layout())
                                                                  ? kTrackSimulationUnitsPerMeter
                                                                  : 1.0f);
                            const bool lowSpeedContact = std::max(length(ka.vel), length(kb.vel)) < launchSpeed;
                            const float impulseScale =
                                sameDirection
                                    ? (longitudinalContact
                                           ? (lowSpeedContact
                                                  ? 0.10f
                                                  : 0.22f)
                                           : 0.52f)
                                    : 1.10f;
                            const float impulse = -impulseScale * closingSpeed / invSum;
                            resolvedImpulse = impulse;
                            ka.vel -= impulseNormal * (impulse * invA);
                            kb.vel += impulseNormal * (impulse * invB);

                            if (!sameDirection ||
                                longitudinalContact) {
                                const Vec2 tangent{
                                    -impulseNormal.y,
                                    impulseNormal.x};
                                const float tangentSpeed =
                                    dot(kb.vel - ka.vel,
                                        tangent);
                                const float tangentImpulse =
                                    std::clamp(
                                        -tangentSpeed * 0.05f /
                                            invSum,
                                        -impulse * 0.18f,
                                        impulse * 0.18f);
                                ka.vel -= tangent *
                                          (tangentImpulse *
                                           invA);
                                kb.vel += tangent *
                                          (tangentImpulse *
                                           invB);
                            }
                        }

                        // Collision impulses already dissipate relative
                        // motion. Never damp the common forward velocity on
                        // every persistent-contact frame; that made a gentle
                        // one-second brush erase roughly 38% of both cars'
                        // speed. A small one-shot loss remains for genuinely
                        // opposing impacts only.
                        if (!sameDirection &&
                            resolvedImpulse > 0.0f) {
                            ka.vel *= 0.996f;
                            kb.vel *= 0.996f;
                        }
                        ka.contactImpulse = std::max(ka.contactImpulse, resolvedImpulse);
                        kb.contactImpulse = std::max(kb.contactImpulse, resolvedImpulse);
                    }

                    ka.contactTimer = 0.26f;
                    kb.contactTimer = 0.26f;
                    ka.contactCause = ContactCause3D::Vehicle;
                    kb.contactCause = ContactCause3D::Vehicle;
                    ka.vehicleContact = true;
                    kb.vehicleContact = true;
                }
            }
        }
        for (int i = 0; i < kKartCount; ++i) {
            if (moved[static_cast<size_t>(i)]) {
                Kart3D& kart = karts_[static_cast<size_t>(i)];
                updateProgress(kart);
            }
        }
    }

    float maxKartOverlap() const {
        float maxOverlap = 0.0f;
        for (int a = 0; a < kKartCount; ++a) {
            for (int b = a + 1; b < kKartCount; ++b) {
                const Kart3D& ka = karts_[static_cast<size_t>(a)];
                const Kart3D& kb = karts_[static_cast<size_t>(b)];
                if (!shouldTestKartContact(ka, kb)) {
                    continue;
                }
                const KartContact3D contact = kartContact(ka, kb);
                if (contact.touching) {
                    maxOverlap = std::max(maxOverlap, contact.penetration);
                }
            }
        }
        return maxOverlap;
    }

    void emitFx(const Kart3D& kart, const TrackPoint3D& center, float offroad, float dt) {
        fxAccumulator_ += dt;
        if (fxAccumulator_ < 0.026f) {
            return;
        }
        fxAccumulator_ = 0.0f;
        const Vec2 forward = fromAngle(kart.heading);
        const Vec2 rear = kart.pos - forward * (kart.spec.length * 0.46f);
        const Vec2 baseVel = kart.vel * -0.10f - forward * 10.0f;
        const float rearLane = dot(rear - center.pos, center.normal);
        const float surfaceElevation = bankedElevation(center, rearLane);
        if (kart.boostTimer > 0.0f) {
            emitParticle(rear, baseVel - forward * 36.0f, surfaceElevation + 4.0f, 0.20f, 4.8f, Color{255, 181, 45, 210});
            emitParticle(rear - Vec2{-forward.y, forward.x} * 8.0f, baseVel - forward * 24.0f, surfaceElevation + 3.0f, 0.18f, 3.8f,
                         Color{244, 67, 43, 205});
        } else if (kart.drifting) {
            emitParticle(rear, baseVel, surfaceElevation + 2.5f, 0.46f, 5.5f, Color{226, 232, 219, 185});
        } else if (offroad > 2.0f && length(kart.vel) > 28.0f) {
            Color dust = mix(naturalSurfaceColor(center.zone), Color{242, 232, 194, 255}, 0.34f);
            dust.a = 184;
            emitParticle(rear, baseVel, surfaceElevation + 2.0f, 0.42f, 5.8f, dust);
        } else if (kart.contactTimer > 0.14f) {
            emitParticle(kart.pos, baseVel, surfaceElevation + 5.0f, 0.22f, 4.5f, Color{245, 231, 165, 210});
        }
    }

    void emitParticle(Vec2 pos, Vec2 vel, float elevation, float life, float size, Color color) {
        if (particles_.size() > 520) {
            particles_.erase(particles_.begin());
        }
        particles_.push_back({pos, vel, elevation, life, life, size, color});
    }

    void updateParticles(float dt) {
        for (Particle3D& p : particles_) {
            p.life -= dt;
            p.pos += p.vel * dt;
            p.vel *= std::exp(-dt * 1.8f);
            p.elevation += dt * 7.0f;
        }
        particles_.erase(std::remove_if(particles_.begin(), particles_.end(), [](const Particle3D& p) { return p.life <= 0.0f; }),
                         particles_.end());
    }

    void resetPlayerToTrack() {
        Kart3D& kart = karts_[0];
        float resetProgress = kart.progress;
        if (raceFlow_) {
            const ArcadeCheckpointResetInfo reset = raceFlow_->lastValidReset(0);
            if (reset.valid) {
                resetProgress = wrapDistance(track_.startProgress() + reset.normalizedTrackProgress * track_.totalLength(),
                                             track_.totalLength());
            }
        }
        const TrackPoint3D tp = track_.sample(resetProgress);
        kart.pos = tp.pos;
        kart.heading = angleOf(tp.tangent);
        kart.vel = tp.tangent * 34.0f;
        kart.elevation = bankedElevation(tp, 0.0f);
        kart.verticalSpeed = 0.0f;
        kart.airborneTime = 0.0f;
        kart.landingImpulse = 0.0f;
        kart.grounded = true;
        kart.nearest = track_.nearestIndex(kart.pos);
        kart.drifting = false;
        kart.boostTimer = 0.0f;
        kart.boostPower = 0.0f;
        kart.driftCharge = 0.0f;
        kart.gear = 1;
        kart.engineRpmNormalized = kart.tuning.idleRpmNormalized;
        kart.shiftTimer = 0.0f;
        kart.shiftRejectTimer = 0.0f;
        kart.contactTimer = 0.0f;
        kart.contactImpulse = 0.0f;
        kart.contactCause = ContactCause3D::None;
        kart.vehicleContact = false;
        kart.ghostTimer = 1.0f;
        updateProgress(kart);
        kart.previousRenderPos = kart.pos;
        kart.previousRenderElevation = kart.elevation;
        kart.previousRenderHeading = kart.heading;
        kart.previousRenderProgress = kart.progress;
        kart.barrierContact = false;
        if (raceFlow_) {
            const auto inputs = currentRaceInputs();
            raceFlow_->rebaseRacerSample(0, inputs[0]);
        }
    }

    void updateRaceOrder() {
        std::array<std::pair<float, int>, kKartCount> order;
        const int count = activeKartCount();
        const bool preRace = raceFlow_ &&
                             (raceFlow_->phase() == ArcadeRacePhase::Grid ||
                              raceFlow_->phase() == ArcadeRacePhase::Countdown);
        for (int i = 0; i < count; ++i) {
            const Kart3D& kart = karts_[static_cast<size_t>(i)];
            // Validated progress intentionally clamps pre-start samples to
            // zero. Use physical grid progress until lights-out so the HUD
            // correctly reports the player in the final slot.
            const float score = raceFlow_ && !preRace
                                    ? static_cast<float>(raceFlow_->racer(static_cast<size_t>(i)).validatedRaceProgress *
                                                         static_cast<double>(track_.totalLength()))
                                    : raceScore(kart);
            order[static_cast<size_t>(i)] = {score, i};
        }
        std::sort(order.begin(), order.begin() + count, [](auto a, auto b) { return a.first > b.first; });
        for (int i = 0; i < count; ++i) {
            if (order[static_cast<size_t>(i)].second == 0) {
                playerPosition_ = i + 1;
                return;
            }
        }
    }

    Camera raceTcam(float alpha) const {
        const Kart3D& player = karts_[0];
        const Vec2 renderPos = lerp(player.previousRenderPos, player.pos, alpha);
        const float renderHeading = wrapAngle(player.previousRenderHeading +
                                              wrapAngle(player.heading - player.previousRenderHeading) * alpha);
        const float renderElevation = lerp(player.previousRenderElevation, player.elevation, alpha);
        const Vec2 forward = fromAngle(renderHeading);

        // The broadcast T-cam stays rigidly attached above and just behind the
        // roll hoop. Road vibration is millimetric; there is no chase lag,
        // velocity steering, speed pullback, or dynamic lens change.
        const float speedN = std::clamp(std::max(0.0f, player.telemetry.forwardSpeed) /
                                            std::max(1.0f, player.tuning.maxForwardSpeed),
                                        0.0f, 1.0f);
        const float vibration = smoothstep(std::clamp((speedN - 0.48f) / 0.52f, 0.0f, 1.0f));
        const Vec2 right{-forward.y, forward.x};
        const float lateralVibrationMeters =
            vibration * (std::sin(raceTime_ * 83.0f) * 0.0035f + std::sin(raceTime_ * 131.0f) * 0.0015f);
        const float verticalVibrationMeters =
            vibration * (std::sin(raceTime_ * 97.0f) * 0.0055f + std::sin(raceTime_ * 149.0f) * 0.0020f);
        const Vec2 mountPos = renderPos - forward * (kTcamBackMeters * kTrackSimulationUnitsPerMeter) +
                              right * (lateralVibrationMeters * kTrackSimulationUnitsPerMeter);
        Camera camera{};
        camera.position = toWorld(mountPos,
                                  renderElevation + (kTcamHeightMeters + verticalVibrationMeters) *
                                                        kTrackSimulationUnitsPerMeter);
        camera.target = toWorld(renderPos + forward * (kTcamLookAheadMeters * kTrackSimulationUnitsPerMeter),
                                renderElevation + kTcamTargetHeightMeters * kTrackSimulationUnitsPerMeter);
        camera.up = {0.0f, 1.0f, 0.0f};
        camera.fovy = kTcamFovDegrees;
        camera.projection = CAMERA_PERSPECTIVE;
        return camera;
    }

    void updateCamera(float dt) {
        (void)dt;
        previousCamera_ = camera_;
        camera_ = raceTcam(1.0f);
    }

    void drawEnvironment() {
        if (isMetricCircuit(track_.layout())) {
            Vector3 oceanCenter = karts_.empty() ? Vector3{} : toWorld(karts_[0].pos);
            oceanCenter.y = -0.44f;
            DrawPlane(oceanCenter, {3200.0f, 3200.0f}, Color{37, 166, 192, 255});

            // Fixed island ridges make each sector feel enclosed without
            // moving with the player or collapsing elevated scenery to sea.
            const Shader environmentShader = renderer_.worldShader();
            const bool useEnvironmentShader = IsShaderValid(environmentShader);
            if (useEnvironmentShader) {
                BeginShaderMode(environmentShader);
            }
            for (int ridge = 0; ridge < 18; ++ridge) {
                const float progress = track_.totalLength() * (static_cast<float>(ridge) + 0.35f) / 18.0f;
                const TrackPoint3D point = track_.sample(progress);
                const float viewProgress = karts_.empty() ? track_.startProgress() : karts_[0].progress;
                const float courseDistance = signedDistanceToLoop(viewProgress, progress, track_.totalLength()) *
                                             trackProgressRenderScale(track_.layout());
                if (courseDistance < -kSpaRenderRearRange || courseDistance > kSpaRenderForwardRange) {
                    continue;
                }
                const float side = ridge % 2 == 0 ? -1.0f : 1.0f;
                const float lane = side * (point.width * 0.5f + 310.0f + static_cast<float>((ridge * 47) % 150));
                const Vector3 base = terrainSurfacePoint(track_, point, lane);
                const Vector3 cameraDelta = sub(base, camera_.position);
                const float distanceSq = cameraDelta.x * cameraDelta.x + cameraDelta.y * cameraDelta.y + cameraDelta.z * cameraDelta.z;
                if (distanceSq > 900.0f * 900.0f) {
                    continue;
                }
                const Vector3 along{point.tangent.x, 0.0f, point.tangent.y};
                const Vector3 outward{point.normal.x * side, 0.0f, point.normal.y * side};
                for (int mound = 0; mound < 4; ++mound) {
                    const float alongOffset = (static_cast<float>(mound) - 1.5f) * 18.0f;
                    const float outwardOffset = static_cast<float>((mound * 13 + ridge * 5) % 18);
                    const Vector3 center = add(base, add(mul(along, alongOffset), mul(outward, outwardOffset)));
                    const float height = 4.0f + static_cast<float>((ridge * 7 + mound * 5) % 6);
                    const float oceanY = -0.44f;
                    const float verticalRadius = std::max(height, (center.y - oceanY) * 0.5f + height * 0.35f);
                    const float supportedCenterY = (center.y + oceanY) * 0.5f;
                    const Color ridgeColor = (ridge + mound) % 3 == 0 ? Color{179, 160, 92, 255}
                                                                      : ((ridge + mound) % 2 == 0 ? Color{72, 133, 76, 255}
                                                                                                   : Color{91, 151, 79, 255});
                    drawLocalEllipsoid({center.x, supportedCenterY, center.z},
                                       {20.0f + mound * 3.4f, verticalRadius, 13.0f + (ridge + mound) % 7}, ridgeColor);
                }
            }
            if (useEnvironmentShader) {
                EndShaderMode();
            }
            return;
        }
        DrawPlane({0.0f, -0.44f, 0.0f}, {390.0f, 340.0f}, Color{37, 166, 192, 255});

        // One continuous island sits beneath the complete loop. Overlapping
        // terrain plates mark sectors without ever exposing a floating road.
        drawFlatOval({0.0f, -0.43f, -3.0f}, 166.0f, 130.0f, 0.16f, Color{213, 173, 91, 255}, 112);
        drawFlatOval({0.0f, -0.31f, -3.0f}, 158.0f, 122.0f, 0.10f, Color{230, 193, 108, 255}, 112);
        drawGradientOval({0.0f, -0.36f, -3.0f}, 164.0f, 128.0f, Color{227, 188, 105, 255}, Color{214, 173, 91, 255}, 112);
        drawGradientOval({0.0f, -0.31f, -3.0f}, 157.0f, 121.0f, Color{235, 199, 115, 255}, Color{224, 184, 98, 255}, 112);
        drawFlatOval({0.0f, -0.255f, -42.0f}, 148.0f, 72.0f, 0.035f, Color{237, 201, 117, 255}, 96);
        drawFlatOval({84.0f, -0.225f, 4.0f}, 70.0f, 78.0f, 0.035f, Color{218, 180, 108, 255}, 80);
        drawFlatOval({-25.0f, -0.175f, 65.0f}, 124.0f, 57.0f, 0.035f, Color{107, 157, 82, 255}, 92);
        drawFlatOval({-96.0f, -0.145f, 21.0f}, 49.0f, 61.0f, 0.035f, Color{95, 150, 79, 255}, 64);
        drawGradientOval({0.0f, -0.285f, -42.0f}, 148.0f, 72.0f, Color{244, 210, 128, 255}, Color{226, 187, 102, 255}, 96);
        drawGradientOval({84.0f, -0.235f, 4.0f}, 70.0f, 78.0f, Color{205, 165, 101, 255}, Color{229, 193, 118, 255}, 80);
        drawGradientOval({-25.0f, -0.19f, 65.0f}, 124.0f, 57.0f, Color{80, 147, 77, 255}, Color{160, 176, 99, 255}, 92);
        drawGradientOval({-96.0f, -0.16f, 21.0f}, 49.0f, 61.0f, Color{73, 139, 75, 255}, Color{187, 181, 102, 255}, 64);

        // Foam and exposed reefs make the shoreline readable in the distance.
        for (int i = 0; i < 28; ++i) {
            const float angle = kTwoPi * static_cast<float>(i) / 28.0f;
            const float x = std::cos(angle) * (157.0f + static_cast<float>(i % 3) * 1.8f);
            const float z = -3.0f + std::sin(angle) * (121.0f + static_cast<float>((i + 1) % 4));
            drawFlatOval({x, -0.37f, z}, 4.2f + static_cast<float>(i % 4) * 0.65f, 0.26f, 0.014f,
                         Color{222, 245, 231, 155}, 18);
        }

        // Permanent jungle ridge silhouettes replace isolated scenery that
        // previously appeared to pop as the road renderer culled chunks.
        for (int i = 0; i < 11; ++i) {
            const float x = -119.0f + static_cast<float>(i) * 23.0f;
            const float height = 5.0f + static_cast<float>((i * 7) % 5) * 1.1f;
            DrawSphere({x, height * 0.34f, 130.0f + std::sin(static_cast<float>(i) * 1.8f) * 4.0f}, height,
                       i % 2 == 0 ? Color{64, 121, 71, 255} : Color{78, 137, 73, 255});
        }

        DrawSphere({-116.0f, 56.0f, -86.0f}, 8.5f, Color{255, 219, 90, 255});
        for (int i = 0; i < 6; ++i) {
            DrawCubeV({-78.0f + static_cast<float>(i) * 27.0f, 45.0f + std::sin(static_cast<float>(i)) * 5.0f, -98.0f},
                      {13.0f, 2.4f, 3.0f}, Color{236, 252, 255, 205});
        }
    }

    void drawTrack() {
        const auto& samples = track_.samples();
        const float viewProgress =
            mode_ == Mode::Garage || karts_.empty() ? track_.startProgress() : karts_[0].progress;
        const auto detailVisible = [&](float progress) {
            if (isMetricCircuit(track_.layout())) {
                const float distance = signedDistanceToLoop(viewProgress, progress, track_.totalLength()) *
                                       trackProgressRenderScale(track_.layout());
                return distance >= -kSpaRenderRearRange && distance <= kSpaRenderForwardRange;
            }
            const float distance = signedDistanceToLoop(viewProgress, progress, track_.totalLength());
            return distance >= -700.0f && distance <= 2500.0f;
        };
        if (trackRenderer_.ready()) {
            const bool metricCircuit = isMetricCircuit(track_.layout());
            const float progressScale = trackProgressRenderScale(track_.layout());
            trackRenderer_.draw(viewProgress * progressScale,
                                metricCircuit ? kSpaRenderForwardRange : 260.0f,
                                metricCircuit ? kSpaRenderRearRange : 24.0f,
                                camera_.position, 0.0f);
        } else {
            constexpr int stride = 2;
            for (int i = 0; i < track_.sampleCount(); i += stride) {
            const TrackPoint3D& a = samples[static_cast<size_t>(i)];
            const TrackPoint3D& b = samples[static_cast<size_t>((i + stride) % track_.sampleCount())];
            const float halfA = a.width * 0.5f;
            const float halfB = b.width * 0.5f;
            const std::array<float, 17> cutsA = surfaceCuts(a);
            const std::array<float, 17> cutsB = surfaceCuts(b);

            for (size_t band = 0; band + 1 < cutsA.size(); ++band) {
                drawGradientQuad(lift(terrainSurfacePoint(track_, a, cutsA[band]), kTrackSurfaceLift),
                                 lift(terrainSurfacePoint(track_, b, cutsB[band]), kTrackSurfaceLift),
                                 lift(terrainSurfacePoint(track_, b, cutsB[band + 1]), kTrackSurfaceLift),
                                 lift(terrainSurfacePoint(track_, a, cutsA[band + 1]), kTrackSurfaceLift), surfaceColorAt(a, cutsA[band]),
                                 surfaceColorAt(b, cutsB[band]), surfaceColorAt(b, cutsB[band + 1]),
                                 surfaceColorAt(a, cutsA[band + 1]));
            }

            if ((a.zone == 1 || a.zone == 5) && (i / stride) % 8 == 0) {
                Color plank = shade(mix(mix(a.road, b.road, 0.5f), mix(a.shoulder, b.shoulder, 0.5f), 0.48f), 0.94f);
                plank.a = 126;
                drawQuad(lift(track_.roadPoint(a, -halfA * 0.80f), 0.050f), lift(track_.roadPoint(b, -halfB * 0.80f), 0.050f),
                         lift(track_.roadPoint(b, halfB * 0.80f), 0.050f), lift(track_.roadPoint(a, halfA * 0.80f), 0.050f), plank);
            }

            if ((i / stride) % 7 == 0) {
                for (float lane : {-28.0f, 28.0f}) {
                    Color rut = shade(surfaceColorAt(a, lane), 0.93f);
                    rut.a = 44;
                    drawQuad(lift(track_.roadPoint(a, lane - 1.3f), 0.055f), lift(track_.roadPoint(b, lane - 1.3f), 0.055f),
                             lift(track_.roadPoint(b, lane + 1.3f), 0.055f), lift(track_.roadPoint(a, lane + 1.3f), 0.055f), rut);
                }
            }

            if ((i / stride) % 47 == 0) {
                for (float side : {-1.0f, 1.0f}) {
                    const float noise = static_cast<float>((i * 31 + (side > 0.0f ? 19 : 7)) % 76);
                    const float lane = side * (a.width * 0.5f + 42.0f + noise);
                    const Vector3 pos = lift(track_.roadPoint(a, lane), 0.066f);
                    Color chip = mix(surfaceColorAt(a, lane), naturalSurfaceColor(a.zone), 0.50f);
                    if (a.zone == 3) {
                        chip = shade(chip, 0.92f);
                    }
                    chip = shade(chip, side > 0.0f ? 0.99f : 1.02f);
                    drawFlatOval(pos, 0.22f + noise * 0.003f, 0.11f + noise * 0.002f, 0.020f, chip, 10);
                }
            }
            }
        }

        const Shader detailShader = renderer_.worldShader();
        const bool useDetailShader = IsShaderValid(detailShader);
        if (useDetailShader) {
            BeginShaderMode(detailShader);
        }
        // Low sector-specific edge geometry follows the same lane boundary as
        // collision resolution. It gives every corner a stable silhouette and
        // communicates exactly how much shoulder remains available.
        const int boundaryStride = isMetricCircuit(track_.layout()) ? 3 : 10;
        for (int i = 0; i < track_.sampleCount(); i += boundaryStride) {
            const TrackPoint3D& p = samples[static_cast<size_t>(i)];
            if (!detailVisible(p.progress)) {
                continue;
            }
            const TrackPoint3D& next = samples[static_cast<size_t>((i + boundaryStride) % track_.sampleCount())];
            const float segmentLength = length(next.pos - p.pos) * kRenderScale * 1.05f;
            for (float side : {-1.0f, 1.0f}) {
                const float lane = isMetricCircuit(track_.layout())
                                       ? side * (roadSurfaceHalfWidth(p) + 14.0f)
                                       : side * (p.width * 0.5f + 18.0f);
                const Vector3 edge = track_.roadPoint(p, lane);
                rlPushMatrix();
                rlTranslatef(edge.x, edge.y + (p.zone == 2 ? 0.53f : 0.34f), edge.z);
                rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
                if (p.zone == 0) {
                    DrawCubeV({0.0f, 0.0f, 0.0f}, {0.24f, 0.30f, segmentLength}, Color{113, 76, 45, 255});
                    DrawCubeV({0.0f, -0.31f, -segmentLength * 0.42f}, {0.34f, 0.72f, 0.34f}, Color{86, 62, 42, 255});
                    DrawCubeV({0.0f, -0.31f, segmentLength * 0.42f}, {0.34f, 0.72f, 0.34f}, Color{86, 62, 42, 255});
                } else if (p.zone == 2) {
                    const Color wall = ((i / boundaryStride) % 2 == 0) ? Color{238, 116, 83, 255} : Color{242, 199, 119, 255};
                    DrawCubeV({0.0f, 0.0f, 0.0f}, {0.56f, 1.04f, segmentLength}, wall);
                    DrawCubeV({0.0f, 0.58f, 0.0f}, {0.68f, 0.16f, segmentLength}, Color{250, 226, 153, 255});
                } else {
                    const float rise = 0.58f + static_cast<float>((i / boundaryStride) % 3) * 0.12f;
                    DrawCubeV({0.0f, 0.0f, 0.0f}, {0.72f, rise, segmentLength}, Color{76, 101, 67, 255});
                    DrawCubeV({0.0f, rise * 0.48f, 0.0f}, {0.84f, 0.22f, segmentLength * 0.96f}, Color{111, 129, 75, 255});
                }
                rlPopMatrix();
            }
        }

        if (mode_ != Mode::Garage && detailVisible(track_.startProgress())) {
            const float startProgress = track_.startProgress();
            const TrackPoint3D start = track_.sample(startProgress);
            const TrackPoint3D after = track_.sample(startProgress + 10.0f);
            const float half = start.width * 0.5f;
            constexpr int kCells = 12;
            for (int cell = 0; cell < kCells; ++cell) {
                const float lane0 = lerp(-half, half, static_cast<float>(cell) / kCells);
                const float lane1 = lerp(-half, half, static_cast<float>(cell + 1) / kCells);
                const Color c = (cell % 2 == 0) ? Color{248, 246, 218, 255} : Color{30, 39, 44, 255};
                drawQuad(lift(track_.roadPoint(start, lane0), 0.095f), lift(track_.roadPoint(after, lane0), 0.095f),
                         lift(track_.roadPoint(after, lane1), 0.095f), lift(track_.roadPoint(start, lane1), 0.095f), c);
            }

            const Vector3 gate = track_.roadPoint(start, 0.0f);
            rlPushMatrix();
            rlTranslatef(gate.x, gate.y + 4.15f, gate.z);
            rlRotatef(90.0f - angleOf(start.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
            const float bannerW = start.width * kRenderScale + 3.0f;
            DrawCubeV({0.0f, 0.0f, 0.0f}, {bannerW, 0.18f, 0.28f}, Color{255, 235, 106, 255});
            for (int i = 0; i < 10; ++i) {
                const float x = -bannerW * 0.5f + (static_cast<float>(i) + 0.5f) * bannerW / 10.0f;
                DrawCubeV({x, 0.21f, 0.0f}, {bannerW / 10.2f, 0.24f, 0.34f},
                          (i % 2 == 0) ? Color{246, 246, 226, 255} : Color{26, 34, 39, 255});
            }
            DrawCubeV({-start.width * kRenderScale * 0.5f, -2.35f, 0.0f}, {0.46f, 5.1f, 0.46f}, Color{48, 130, 166, 255});
            DrawCubeV({start.width * kRenderScale * 0.5f, -2.35f, 0.0f}, {0.46f, 5.1f, 0.46f}, Color{48, 130, 166, 255});
            rlPopMatrix();
        }
        if (useDetailShader) {
            EndShaderMode();
        }
    }

    void drawProp(const Prop3D& prop) {
        const TrackPoint3D p = track_.sample(prop.progress);
        const Vector3 base = terrainSurfacePoint(track_, p, prop.side);
        const float s = prop.scale;
        if (renderer_.ready()) {
            arcade_render::TropicalPropKind kind = arcade_render::TropicalPropKind::RockCluster;
            float scaleMultiplier = 1.0f;
            switch (prop.type) {
                case Prop3D::Type::Palm:
                    kind = arcade_render::TropicalPropKind::Palm;
                    break;
                case Prop3D::Type::Rock:
                    kind = arcade_render::TropicalPropKind::RockCluster;
                    break;
                case Prop3D::Type::Cliff:
                case Prop3D::Type::Crystal:
                    kind = arcade_render::TropicalPropKind::RockCluster;
                    scaleMultiplier = prop.type == Prop3D::Type::Cliff ? 2.25f : 0.88f;
                    break;
                case Prop3D::Type::Hut:
                    kind = arcade_render::TropicalPropKind::BeachHut;
                    break;
                case Prop3D::Type::Boat:
                case Prop3D::Type::Sail:
                    kind = arcade_render::TropicalPropKind::FishingBoat;
                    scaleMultiplier = prop.type == Prop3D::Type::Sail ? 0.82f : 1.0f;
                    break;
                case Prop3D::Type::Market:
                    kind = arcade_render::TropicalPropKind::MarketStall;
                    break;
                case Prop3D::Type::Crane:
                    kind = arcade_render::TropicalPropKind::DockCrane;
                    break;
                case Prop3D::Type::Torch:
                    kind = arcade_render::TropicalPropKind::Torch;
                    break;
                case Prop3D::Type::Gate:
                case Prop3D::Type::Chevron:
                    kind = arcade_render::TropicalPropKind::TrackBanner;
                    scaleMultiplier = 0.72f;
                    break;
            }
            const uint32_t variant = static_cast<uint32_t>(std::abs(static_cast<int>(prop.progress * 0.071f))) % 97u;
            arcade_render::TropicalPropSpec spec = arcade_render::MakeTropicalPropSpec(kind, variant);
            spec.primary = prop.color;
            arcade_render::TropicalPropState state;
            state.position = lift(base, 0.025f);
            state.yawRadians = kPi * 0.5f - angleOf(p.tangent);
            state.scale = s * scaleMultiplier;
            state.windPhase = raceTime_ * 1.4f + prop.progress * 0.011f;
            renderer_.drawTropicalProp(spec, state);
            if (isMetricCircuit(track_.layout()) && prop.type == Prop3D::Type::Palm) {
                const Vector3 along{p.tangent.x, 0.0f, p.tangent.y};
                const Vector3 lateral{p.normal.x, 0.0f, p.normal.y};
                for (int tree = 0; tree < 2; ++tree) {
                    const float direction = tree == 0 ? -1.0f : 1.0f;
                    state.position = add(base, add(mul(along, direction * (3.5f + prop.scale)),
                                                   mul(lateral, direction * 1.7f)));
                    state.scale = s * (tree == 0 ? 0.70f : 0.82f);
                    state.windPhase += 0.83f + tree * 0.61f;
                    renderer_.drawTropicalProp(spec, state);
                }
            }
            return;
        }
        switch (prop.type) {
            case Prop3D::Type::Palm:
                DrawCylinderEx(base, add(base, {0.0f, 5.4f * s, 0.0f}), 0.20f * s, 0.12f * s, 9, Color{126, 82, 45, 255});
                drawLocalEllipsoid(add(base, {0.0f, 5.32f * s, 0.0f}), {0.34f * s, 0.24f * s, 0.34f * s},
                                   Color{118, 90, 46, 255});
                for (int i = 0; i < 5; ++i) {
                    rlPushMatrix();
                    rlTranslatef(base.x, base.y + 5.4f * s, base.z);
                    rlRotatef(static_cast<float>(i) * 72.0f, 0.0f, 1.0f, 0.0f);
                    rlRotatef(-12.0f, 1.0f, 0.0f, 0.0f);
                    drawLocalEllipsoid({0.0f, 0.0f, 1.22f * s}, {0.30f * s, 0.070f * s, 1.35f * s},
                                       i % 2 == 0 ? Color{39, 158, 86, 255} : Color{69, 174, 92, 255});
                    rlPopMatrix();
                }
                break;
            case Prop3D::Type::Rock:
            case Prop3D::Type::Cliff:
                drawLocalEllipsoid(add(base, {0.0f, 0.55f * s, 0.0f}), {1.12f * s, 0.66f * s, 0.92f * s}, prop.color);
                drawLocalEllipsoid(add(base, {0.58f * s, 0.96f * s, -0.18f * s}), {0.72f * s, 0.78f * s, 0.58f * s},
                                   shade(prop.color, 1.12f));
                drawLocalEllipsoid(add(base, {-0.54f * s, 0.42f * s, 0.32f * s}), {0.58f * s, 0.42f * s, 0.52f * s},
                                   shade(prop.color, 0.86f));
                break;
            case Prop3D::Type::Hut:
                drawLocalTaperedBox(add(base, {0.0f, 0.9f * s, 0.0f}), {2.8f * s, 1.8f * s, 2.4f * s}, 0.86f, 1.02f,
                                    Color{174, 91, 52, 255});
                DrawCylinder(add(base, {0.0f, 2.2f * s, 0.0f}), 0.0f, 2.1f * s, 1.45f * s, 6, Color{239, 185, 92, 255});
                DrawCubeV(add(base, {0.0f, 1.0f * s, 1.22f * s}), {0.76f * s, 0.86f * s, 0.08f * s}, Color{76, 62, 48, 255});
                break;
            case Prop3D::Type::Boat:
                rlPushMatrix();
                rlTranslatef(base.x, base.y + 0.55f * s, base.z);
                rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
                drawLocalTaperedBox({0.0f, 0.0f, 0.0f}, {3.7f * s, 0.8f * s, 1.4f * s}, 0.52f, 1.06f, prop.color);
                drawLocalEllipsoid({0.0f, 0.18f * s, 0.0f}, {1.34f * s, 0.20f * s, 0.38f * s}, shade(prop.color, 1.12f));
                DrawCubeV({0.0f, 1.0f * s, 0.0f}, {0.18f * s, 2.4f * s, 0.18f * s}, Color{81, 66, 45, 255});
                drawLocalWedge({0.8f * s, 1.5f * s, 0.0f}, {1.3f * s, 1.8f * s, 0.08f * s}, 0.18f, Color{246, 239, 186, 255});
                rlPopMatrix();
                break;
            case Prop3D::Type::Market:
                drawLocalTaperedBox(add(base, {0.0f, 0.75f * s, 0.0f}), {2.8f * s, 1.5f * s, 2.1f * s}, 0.92f, 1.02f,
                                    shade(prop.color, 0.85f));
                drawLocalWedge(add(base, {0.0f, 1.75f * s, 0.0f}), {3.2f * s, 0.42f * s, 2.5f * s}, 0.78f, prop.color);
                break;
            case Prop3D::Type::Crane:
                DrawCubeV(add(base, {0.0f, 2.1f * s, 0.0f}), {0.45f * s, 4.2f * s, 0.45f * s}, Color{92, 70, 55, 255});
                DrawCubeV(add(base, {1.7f * s, 4.1f * s, 0.0f}), {3.5f * s, 0.32f * s, 0.32f * s}, prop.color);
                break;
            case Prop3D::Type::Crystal:
                DrawCylinder(add(base, {0.0f, 1.15f * s, 0.0f}), 0.0f, 0.75f * s, 2.3f * s, 5, prop.color);
                DrawCylinder(add(base, {0.9f * s, 0.8f * s, 0.4f * s}), 0.0f, 0.45f * s, 1.6f * s, 5, shade(prop.color, 1.15f));
                break;
            case Prop3D::Type::Torch:
                DrawCylinderEx(base, add(base, {0.0f, 2.4f * s, 0.0f}), 0.12f * s, 0.10f * s, 7, Color{92, 57, 36, 255});
                DrawSphere(add(base, {0.0f, 2.72f * s, 0.0f}), 0.45f * s, Color{255, 154, 41, 255});
                break;
            case Prop3D::Type::Gate:
                break;
            case Prop3D::Type::Chevron:
                rlPushMatrix();
                rlTranslatef(base.x, base.y + 1.0f * s, base.z);
                rlRotatef(90.0f - angleOf(p.tangent) * RAD2DEG, 0.0f, 1.0f, 0.0f);
                DrawCubeV({0.0f, 0.0f, 0.0f}, {0.22f * s, 1.8f * s, 2.4f * s}, prop.color);
                DrawCubeV({0.0f, 0.0f, 0.0f}, {0.28f * s, 0.55f * s, 1.9f * s}, Color{255, 235, 114, 255});
                rlPopMatrix();
                break;
            case Prop3D::Type::Sail:
                DrawCubeV(add(base, {0.0f, 1.2f * s, 0.0f}), {0.18f * s, 2.4f * s, 0.18f * s}, Color{92, 70, 52, 255});
                drawLocalWedge(add(base, {0.65f * s, 1.8f * s, 0.0f}), {1.3f * s, 1.7f * s, 0.08f * s}, 0.16f, prop.color);
                break;
        }
    }

    bool shouldDrawRaceProp(const Prop3D& prop) const {
        if (mode_ == Mode::Garage || karts_.empty()) {
            return true;
        }
        const TrackPoint3D point = track_.sample(prop.progress);
        const Vector3 propCenter = lift(terrainSurfacePoint(track_, point, prop.side), 2.2f * prop.scale);
        const Vector3 cameraToProp = sub(propCenter, camera_.position);
        const float cameraDistanceSq = cameraToProp.x * cameraToProp.x + cameraToProp.y * cameraToProp.y + cameraToProp.z * cameraToProp.z;
        if (isMetricCircuit(track_.layout())) {
            const float courseDistance = signedDistanceToLoop(karts_[0].progress, prop.progress, track_.totalLength()) *
                                         trackProgressRenderScale(track_.layout());
            if (courseDistance < -kSpaRenderRearRange || courseDistance > kSpaRenderForwardRange) {
                return false;
            }
        }
        const float fadeSafeRange = (isMetricCircuit(track_.layout()) ? 1050.0f : 275.0f) + prop.scale * 5.0f;
        return cameraDistanceSq <= fadeSafeRange * fadeSafeRange;
    }

    void drawProps() {
        if (mode_ == Mode::Garage) {
            return;
        }
        for (const Prop3D& prop : track_.props()) {
            if (!shouldDrawRaceProp(prop)) {
                continue;
            }
            drawProp(prop);
        }
    }

    void drawDriver(const Kart3D& kart, float w, float l, float h, bool player) {
        const uint32_t hash = stableHash(kart.racer);
        static constexpr std::array<Color, 6> kSkin = {
            Color{116, 67, 43, 255},  Color{154, 94, 55, 255}, Color{191, 121, 73, 255},
            Color{218, 153, 98, 255}, Color{235, 177, 121, 255}, Color{92, 54, 41, 255},
        };
        static constexpr std::array<Color, 6> kHair = {
            Color{39, 30, 25, 255},  Color{75, 48, 31, 255}, Color{132, 83, 38, 255},
            Color{226, 174, 78, 255}, Color{35, 43, 51, 255}, Color{206, 79, 84, 255},
        };

        const Color skin = kSkin[hash % kSkin.size()];
        const Color helmet = racerColor(kart.racer);
        const Color shirt = shade(racerColor(kart.racer), 0.82f + static_cast<float>((hash >> 3) % 5) * 0.04f);
        const Color glove = shade(kart.spec.body, 0.55f);
        const bool garageIdle = mode_ == Mode::Garage && player;
        const float idle = garageIdle ? std::sin(garageSpin_ * 2.2f + static_cast<float>(hash % 11)) : std::sin(kart.progress * 0.035f);
        const float steerPose = kart.steerSmoothed * 0.22f;

        DrawCylinderEx({0.0f, h * 1.02f, -l * 0.07f}, {0.0f, h * 1.38f, -l * 0.04f}, w * 0.10f, w * 0.145f, 12, shirt);
        drawLocalEllipsoid({0.0f, h * 1.27f, -l * 0.03f}, {w * 0.155f, h * 0.17f, l * 0.095f}, shade(shirt, 1.12f));
        drawLocalBox({0.0f, h * 1.08f, -l * 0.20f}, {w * 0.45f, h * 0.17f, l * 0.12f}, Color{34, 43, 49, 255});
        DrawCylinderEx({0.0f, h * 1.42f, -l * 0.03f}, {0.0f, h * 1.54f, -l * 0.02f}, w * 0.07f, w * 0.06f, 8,
                       skin);

        const Vector3 leftShoulder{-w * 0.18f, h * 1.34f, -l * 0.01f};
        const Vector3 rightShoulder{w * 0.18f, h * 1.34f, -l * 0.01f};
        Vector3 leftHand{-w * (0.17f + steerPose), h * 1.18f, l * 0.23f};
        Vector3 rightHand{w * (0.17f - steerPose), h * 1.18f, l * 0.23f};
        if (garageIdle && (hash & 1u) == 0u) {
            rightHand = {w * 0.34f, h * (1.62f + idle * 0.12f), l * 0.06f};
        }
        DrawCylinderEx(leftShoulder, leftHand, h * 0.038f, h * 0.044f, 8, skin);
        DrawCylinderEx(rightShoulder, rightHand, h * 0.038f, h * 0.044f, 8, skin);
        drawLocalEllipsoid(leftHand, {w * 0.055f, h * 0.048f, h * 0.048f}, glove);
        drawLocalEllipsoid(rightHand, {w * 0.055f, h * 0.048f, h * 0.048f}, glove);

        DrawCylinderEx({-w * 0.21f, h * 1.16f, l * 0.25f}, {w * 0.21f, h * 1.16f, l * 0.25f}, h * 0.032f, h * 0.032f,
                       12, Color{31, 38, 44, 255});
        DrawCylinderEx({0.0f, h * 1.08f, l * 0.15f}, {0.0f, h * 1.16f, l * 0.25f}, h * 0.024f, h * 0.024f, 8,
                       Color{31, 38, 44, 255});

        drawLocalEllipsoid({0.0f, h * 1.70f + idle * h * 0.018f, -l * 0.02f}, {h * 0.25f, h * 0.29f, h * 0.25f}, helmet);
        drawLocalEllipsoid({0.0f, h * 1.66f + idle * h * 0.018f, l * 0.08f}, {h * 0.16f, h * 0.16f, h * 0.075f}, skin);
        DrawCubeV({0.0f, h * 1.71f + idle * h * 0.018f, l * 0.145f}, {w * 0.25f, h * 0.075f, h * 0.045f},
                  Color{34, 50, 60, 255});

        const int hairStyle = static_cast<int>((hash >> 4) % 4u);
        const Color hair = kHair[(hash >> 7) % kHair.size()];
        if (hairStyle == 0) {
            drawLocalEllipsoid({0.0f, h * 1.93f, -l * 0.03f}, {h * 0.18f, h * 0.08f, h * 0.20f}, hair);
        } else if (hairStyle == 1) {
            DrawCylinderEx({0.0f, h * 1.93f, -l * 0.05f}, {0.0f, h * 2.12f, -l * 0.07f}, h * 0.075f, 0.0f, 6, hair);
        } else if (hairStyle == 2) {
            DrawCubeV({0.0f, h * 1.96f, -l * 0.03f}, {w * 0.42f, h * 0.07f, l * 0.20f}, hair);
        } else {
            DrawCylinderEx({-w * 0.20f, h * 1.76f, -l * 0.08f}, {-w * 0.34f, h * 1.48f, -l * 0.11f}, h * 0.045f,
                           h * 0.030f, 7, hair);
        }
    }

    void drawKart(const Kart3D& kart, bool player) {
        const bool interpolate = mode_ != Mode::Garage;
        const float alpha = interpolate ? renderAlpha_ : 1.0f;
        const Vec2 renderPos = lerp(kart.previousRenderPos, kart.pos, alpha);
        const float renderProgress = wrapDistance(
            kart.previousRenderProgress + signedDistanceToLoop(kart.previousRenderProgress, kart.progress, track_.totalLength()) * alpha,
            track_.totalLength());
        const float renderHeading = wrapAngle(kart.previousRenderHeading + wrapAngle(kart.heading - kart.previousRenderHeading) * alpha);
        const float renderElevation = lerp(kart.previousRenderElevation, kart.elevation, alpha);
        const TrackPoint3D ground = track_.sample(renderProgress);
        const float renderLane = dot(renderPos - ground.pos, ground.normal);
        const float surfaceElevation = bankedElevation(ground, renderLane);
        const Vector3 groundSurface = toWorld(renderPos, surfaceElevation);
        const Vector3 vehicleSurface = toWorld(renderPos, renderElevation);
        const float roadSurfaceLift = authoredRoadSurfaceLift(track_.layout());
        if (renderer_.ready()) {
            const auto style = static_cast<arcade_render::FormulaBodyStyle>(kart.spec.bodyStyle % 5);
            arcade_render::FormulaVisualSpec spec = arcade_render::MakeFormulaVisualSpec(style, kart.spec.body, kart.spec.accent);
            spec.liveryVariant = static_cast<std::uint8_t>(kart.spec.bodyStyle);
            spec.glass = kart.spec.glass;
            spec.width = kart.spec.width * kRenderScale * 0.88f;
            spec.length = kart.spec.length * kRenderScale * 1.02f;
            spec.bodyHeight = kart.spec.height * kRenderScale * 0.78f;
            spec.wheelRadius = std::max(0.50f, kart.spec.height * kRenderScale * 0.46f);
            spec.wheelWidth = spec.width * 0.17f;
            spec.rideHeight = spec.bodyHeight * 0.18f;

            const uint32_t hash = stableHash(kart.racer);
            static constexpr std::array<Color, 6> kSkin = {
                Color{116, 67, 43, 255},  Color{154, 94, 55, 255}, Color{191, 121, 73, 255},
                Color{218, 153, 98, 255}, Color{235, 177, 121, 255}, Color{92, 54, 41, 255},
            };
            static constexpr std::array<Color, 6> kHair = {
                Color{39, 30, 25, 255},  Color{75, 48, 31, 255}, Color{132, 83, 38, 255},
                Color{226, 174, 78, 255}, Color{35, 43, 51, 255}, Color{206, 79, 84, 255},
            };
            spec.driver.skin = kSkin[hash % kSkin.size()];
            spec.driver.hair = kHair[(hash >> 7) % kHair.size()];
            spec.driver.shirt = shade(racerColor(kart.racer), 0.86f);
            spec.driver.headwear = racerColor(kart.racer);
            spec.driver.gloves = shade(kart.spec.body, 0.48f);
            spec.driver.headwearStyle = static_cast<arcade_render::DriverHeadwear>((hash >> 4) % 4u);
            spec.driver.variant = racerAssetVariant(kart.racer);

            arcade_render::FormulaRenderState state;
            state.position = lift(vehicleSurface, roadSurfaceLift);
            state.shadowPosition = lift(groundSurface, roadSurfaceLift + 0.005f);
            state.useGroundShadowPosition = true;
            state.headingRadians = kPi * 0.5f - renderHeading;
            const float roadPitch = kart.grounded ? -std::atan(ground.grade) : 0.0f;
            state.pitchRadians = kart.bodyPitch + roadPitch;
            state.rollRadians = kart.bodyRoll +
                                (kart.grounded ? bankRollDegrees(ground, renderLane) * DEG2RAD : 0.0f);
            if (kart.grounded) {
                // The authored car is rigid, while the terrain can curve across
                // its wheelbase and track width. Support the render root from
                // all four tire patches so no visible terrain can clip a tire.
                constexpr float kAuthoredCarLengthMeters = 4.87f;
                constexpr float kFrontAxleMeters = 1.60f;
                constexpr float kRearAxleMeters = -1.57f;
                constexpr float kHalfTrackMeters = 0.805f;
                const float carScale = spec.length / kAuthoredCarLengthMeters;
                const auto rotateContact = [&](Vector3 point) {
                    const float pitchSin = std::sin(state.pitchRadians);
                    const float pitchCos = std::cos(state.pitchRadians);
                    const float rollSin = std::sin(state.rollRadians);
                    const float rollCos = std::cos(state.rollRadians);
                    const float yawSin = std::sin(state.headingRadians);
                    const float yawCos = std::cos(state.headingRadians);
                    const Vector3 pitched{point.x,
                                          point.y * pitchCos - point.z * pitchSin,
                                          point.y * pitchSin + point.z * pitchCos};
                    const Vector3 rolled{pitched.x * rollCos - pitched.y * rollSin,
                                         pitched.x * rollSin + pitched.y * rollCos,
                                         pitched.z};
                    return Vector3{rolled.x * yawCos + rolled.z * yawSin,
                                   rolled.y,
                                   -rolled.x * yawSin + rolled.z * yawCos};
                };
                const int hint = static_cast<int>(renderProgress / track_.totalLength() *
                                                  static_cast<float>(track_.sampleCount()));
                float supportLift = 0.0f;
                for (float axle : {kRearAxleMeters, kFrontAxleMeters}) {
                    for (float side : {-kHalfTrackMeters, kHalfTrackMeters}) {
                        const Vector3 localContact{side * carScale, 0.0f, axle * carScale};
                        const Vector3 contactOffset = rotateContact(localContact);
                        const Vec2 contactPosition = renderPos +
                            Vec2{contactOffset.x / kRenderScale, contactOffset.z / kRenderScale};
                        const TrackProjection3D projection = track_.projectNear(contactPosition, hint, 12);
                        const TrackPoint3D contactGround = track_.sample(projection.progress);
                        const float renderedGroundY =
                            bankedElevation(contactGround, projection.lane) * kRenderScale + roadSurfaceLift;
                        const float renderedTireY = state.position.y + contactOffset.y;
                        supportLift = std::max(supportLift, renderedGroundY - renderedTireY);
                    }
                }
                state.position.y += supportLift + kVisualTireClearanceWorld;
            }
            state.steeringRadians = kart.steerAngle;
            state.wheelSpinRadians = kart.wheelSpin;
            const float suspension = std::clamp(kart.suspensionCompression, 0.0f, 1.0f);
            const float pitchLoad = std::clamp(kart.bodyPitch * 2.8f, -0.22f, 0.22f);
            const float rollLoad = std::clamp(kart.bodyRoll * 2.2f, -0.22f, 0.22f);
            state.suspensionCompression = {
                std::clamp(0.16f + suspension + pitchLoad + rollLoad, 0.0f, 1.0f),
                std::clamp(0.16f + suspension + pitchLoad - rollLoad, 0.0f, 1.0f),
                std::clamp(0.16f + suspension - pitchLoad + rollLoad, 0.0f, 1.0f),
                std::clamp(0.16f + suspension - pitchLoad - rollLoad, 0.0f, 1.0f),
            };
            state.speedNormalized = std::clamp(length(kart.vel) / kart.tuning.maxForwardSpeed, 0.0f, 1.25f);
            state.boostAmount = kart.boostTimer > 0.0f ? 0.55f + kart.boostPower * 0.45f : 0.0f;
            state.brakeAmount = kart.brakeLoad;
            state.dustAmount = std::clamp(roadEdgeViolation(kart, ground) / 22.0f, 0.0f, 1.0f) *
                               std::clamp(state.speedNormalized * 1.4f, 0.0f, 1.0f);
            state.airborneAmount = kart.grounded ? 0.0f : std::clamp(kart.airborneTime / 0.18f, 0.0f, 1.0f);
            state.visualTime = raceTime_ + static_cast<float>(hash & 255u) * 0.013f;
            state.damageFlash = std::clamp(kart.contactTimer / 0.22f, 0.0f, 1.0f);
            state.driverLean = std::clamp(-kart.steerSmoothed - kart.slipAngle * 0.45f, -1.0f, 1.0f);
            renderer_.drawFormulaCar(spec, state);
            (void)player;
            return;
        }
        const Vector3 base = lift(vehicleSurface, roadSurfaceLift + kKartWheelGroundClearance);
        const float w = kart.spec.width * kRenderScale;
        const float l = kart.spec.length * kRenderScale;
        const float h = kart.spec.height * kRenderScale;

        const Vector3 shadow = lift(groundSurface, kTrackSurfaceLift + 0.006f);
        rlPushMatrix();
        rlTranslatef(shadow.x, shadow.y, shadow.z);
        rlRotatef(90.0f - renderHeading * RAD2DEG, 0.0f, 1.0f, 0.0f);
        rlRotatef(kart.grounded ? bankRollDegrees(ground, renderLane) : 0.0f, 0.0f, 0.0f, 1.0f);
        DrawCylinder({0.0f, 0.0f, 0.0f}, w * 0.78f, w * 0.78f, 0.035f, 18, Color{28, 35, 37, 90});
        rlPopMatrix();

        rlPushMatrix();
        rlTranslatef(base.x, base.y, base.z);
        rlRotatef(90.0f - renderHeading * RAD2DEG, 0.0f, 1.0f, 0.0f);
        const float speed = length(kart.vel);
        const float speedT = std::clamp(speed / 150.0f, 0.0f, 1.0f);
        const float bounce = std::sin(kart.progress * 0.075f + static_cast<float>(kart.spec.bodyStyle)) * 0.045f * speedT;
        const float pitch = kart.bodyPitch * RAD2DEG;
        const float contactLift = kart.contactTimer > 0.0f ? std::max(0.0f, std::sin(kart.contactTimer * 80.0f) * 0.035f) : 0.0f;
        rlTranslatef(0.0f, std::max(0.0f, bounce) + contactLift, 0.0f);
        rlRotatef(kart.grounded ? bankRollDegrees(ground, renderLane) : 0.0f, 0.0f, 0.0f, 1.0f);
        rlRotatef(pitch, 1.0f, 0.0f, 0.0f);
        const float lean = std::clamp(kart.steerSmoothed * length(kart.vel) / 150.0f, -0.55f, 0.55f);
        rlRotatef(-lean * 8.0f, 0.0f, 0.0f, 1.0f);

        const Color body = shade(kart.spec.body, kart.contactTimer > 0.0f ? 1.24f : 1.0f);
        drawLocalTaperedBox({0.0f, h * 0.48f, -l * 0.02f}, {w * 1.10f, h * 0.60f, l * 0.94f}, 0.72f, 1.03f, body);
        drawLocalWedge({0.0f, h * 0.84f, l * 0.22f}, {w * 0.96f, h * 0.52f, l * 0.55f}, 0.34f, shade(body, 1.08f));
        drawLocalTaperedBox({0.0f, h * 0.89f, -l * 0.37f}, {w * 0.90f, h * 0.56f, l * 0.44f}, 0.94f, 0.76f, shade(body, 0.96f));
        drawLocalEllipsoid({0.0f, h * 1.14f, -l * 0.13f}, {w * 0.32f, h * 0.075f, l * 0.24f}, shade(body, 0.62f));
        drawLocalEllipsoid({0.0f, h * 1.30f, -l * 0.13f}, {w * 0.245f, h * 0.19f, l * 0.175f}, shade(kart.spec.glass, 0.84f));
        DrawCubeV({0.0f, h * 1.20f, l * 0.025f}, {w * 0.38f, h * 0.055f, l * 0.060f}, shade(kart.spec.glass, 0.58f));
        drawLocalBox({0.0f, h * 0.78f, l * 0.48f}, {w * 0.84f, h * 0.13f, l * 0.11f}, kart.spec.accent);
        drawLocalBox({0.0f, h * 0.76f, -l * 0.58f}, {w * 0.58f, h * 0.13f, l * 0.14f}, kart.spec.accent);
        DrawCylinderEx({-w * 0.40f, h * 0.42f, l * 0.56f}, {w * 0.40f, h * 0.42f, l * 0.56f}, h * 0.060f, h * 0.060f, 10,
                       shade(kart.spec.accent, 0.88f));
        DrawCylinderEx({-w * 0.34f, h * 0.40f, -l * 0.67f}, {w * 0.34f, h * 0.40f, -l * 0.67f}, h * 0.050f, h * 0.050f,
                       10, shade(kart.spec.accent, 0.78f));

        const Color fender = shade(kart.spec.body, 0.78f);
        for (float sx : {-1.0f, 1.0f}) {
            drawLocalEllipsoid({sx * w * 0.55f, h * 0.58f, l * 0.34f}, {w * 0.17f, h * 0.13f, l * 0.18f}, fender);
            drawLocalEllipsoid({sx * w * 0.55f, h * 0.56f, -l * 0.38f}, {w * 0.16f, h * 0.12f, l * 0.17f}, fender);
            drawLocalBox({sx * w * 0.51f, h * 0.38f, l * 0.04f}, {w * 0.08f, h * 0.28f, l * 0.54f}, shade(body, 0.72f));
        }

        switch (kart.spec.bodyStyle % 8) {
            case 0:
                drawLocalBox({0.0f, h * 1.58f, -l * 0.66f}, {w * 0.95f, h * 0.14f, l * 0.20f}, kart.spec.accent);
                drawLocalBox({-w * 0.42f, h * 1.30f, -l * 0.58f}, {w * 0.09f, h * 0.72f, l * 0.08f}, shade(kart.spec.body, 0.72f));
                drawLocalBox({w * 0.42f, h * 1.30f, -l * 0.58f}, {w * 0.09f, h * 0.72f, l * 0.08f}, shade(kart.spec.body, 0.72f));
                break;
            case 1:
                drawLocalBox({0.0f, h * 0.92f, l * 0.58f}, {w * 0.54f, h * 0.30f, l * 0.30f}, shade(kart.spec.body, 1.12f));
                drawLocalBox({0.0f, h * 1.72f, -l * 0.30f}, {w * 0.16f, h * 0.72f, l * 0.14f}, kart.spec.accent);
                break;
            case 2:
                for (float sx : {-1.0f, 1.0f}) {
                    drawLocalBox({sx * w * 0.34f, h * 1.74f, -l * 0.12f}, {w * 0.08f, h * 1.10f, l * 0.08f}, shade(kart.spec.accent, 0.88f));
                }
                drawLocalBox({0.0f, h * 2.18f, -l * 0.12f}, {w * 0.82f, h * 0.10f, l * 0.12f}, shade(kart.spec.accent, 0.88f));
                break;
            case 3:
                drawLocalBox({0.0f, h * 0.82f, l * 0.68f}, {w * 0.42f, h * 0.22f, l * 0.42f}, shade(kart.spec.body, 1.12f));
                drawLocalBox({0.0f, h * 1.02f, -l * 0.66f}, {w * 0.34f, h * 0.18f, l * 0.20f}, kart.spec.accent);
                break;
            case 4:
                drawLocalBox({0.0f, h * 1.34f, -l * 0.18f}, {w * 0.78f, h * 0.30f, l * 0.56f}, shade(kart.spec.body, 1.08f));
                drawLocalBox({0.0f, h * 1.72f, -l * 0.20f}, {w * 0.50f, h * 0.22f, l * 0.26f}, kart.spec.glass);
                break;
            case 5:
                drawLocalBox({-w * 0.30f, h * 0.74f, -l * 0.76f}, {w * 0.16f, h * 0.16f, l * 0.30f}, Color{45, 49, 52, 255});
                drawLocalBox({w * 0.30f, h * 0.74f, -l * 0.76f}, {w * 0.16f, h * 0.16f, l * 0.30f}, Color{45, 49, 52, 255});
                break;
            case 6:
                drawLocalBox({-w * 0.38f, h * 1.84f, -l * 0.10f}, {w * 0.08f, h * 0.10f, l * 0.72f}, kart.spec.accent);
                drawLocalBox({w * 0.38f, h * 1.84f, -l * 0.10f}, {w * 0.08f, h * 0.10f, l * 0.72f}, kart.spec.accent);
                break;
            default:
                drawLocalBox({-w * 0.46f, h * 1.12f, -l * 0.52f}, {w * 0.14f, h * 0.62f, l * 0.20f}, kart.spec.accent);
                drawLocalBox({w * 0.46f, h * 1.12f, -l * 0.52f}, {w * 0.14f, h * 0.62f, l * 0.20f}, kart.spec.accent);
                break;
        }

        const float tireR = std::max(0.42f, h * 0.48f);
        const float tireW = w * 0.32f;
        const float wheelSpin = std::fmod(-kart.progress * kRenderScale / std::max(0.01f, tireR) * RAD2DEG, 360.0f);
        const float steerDeg = kart.steerSmoothed * 24.0f;
        drawLocalWheel(-w * 0.55f, l * 0.35f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent, wheelSpin, steerDeg, true);
        drawLocalWheel(w * 0.55f, l * 0.35f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent, wheelSpin, steerDeg, true);
        drawLocalWheel(-w * 0.55f, -l * 0.38f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent, wheelSpin, 0.0f, false);
        drawLocalWheel(w * 0.55f, -l * 0.38f, tireR, tireW, Color{25, 29, 32, 255}, kart.spec.accent, wheelSpin, 0.0f, false);

        drawDriver(kart, w, l, h, player);
        if (kart.boostTimer > 0.0f) {
            DrawCylinderEx({-w * 0.22f, h * 0.42f, -l * 0.62f}, {-w * 0.22f, h * 0.42f, -l * 1.12f}, h * 0.20f, 0.0f, 8,
                           Color{255, 171, 42, 220});
            DrawCylinderEx({w * 0.22f, h * 0.42f, -l * 0.62f}, {w * 0.22f, h * 0.42f, -l * 1.12f}, h * 0.20f, 0.0f, 8,
                           Color{242, 73, 42, 205});
        }
        if (player) {
            DrawCubeV({0.0f, h * 2.35f, 0.0f}, {w * 0.55f, h * 0.08f, l * 0.08f}, Color{255, 238, 107, 255});
        }
        rlPopMatrix();
    }

    void drawKarts() {
        if (mode_ == Mode::Garage) {
            const TrackPoint3D start = track_.sample(track_.startProgress() + 52.0f);
            Kart3D preview = karts_[0];
            preview.spec = specs_[static_cast<size_t>(selectedCar_)];
            preview.racer = racers_[static_cast<size_t>(selectedRacer_)];
            preview.pos = start.pos;
            preview.heading = angleOf(start.tangent) + garageSpin_ * 0.52f;
            preview.vel = {};
            preview.progress = start.progress;
            preview.elevation = bankedElevation(start, 0.0f);
            preview.nearest = track_.nearestIndex(preview.pos);
            preview.steerSmoothed = std::sin(garageSpin_ * 1.2f) * 0.08f;
            drawKart(preview, true);
            return;
        }
        std::array<int, kKartCount> order{};
        const int count = activeKartCount();
        for (int i = 0; i < count; ++i) {
            order[static_cast<size_t>(i)] = i;
        }
        std::sort(order.begin(), order.begin() + count, [&](int a, int b) {
            return lengthSq(karts_[static_cast<size_t>(a)].pos - karts_[0].pos) >
                   lengthSq(karts_[static_cast<size_t>(b)].pos - karts_[0].pos);
        });
        for (int orderIndex = 0; orderIndex < count; ++orderIndex) {
            const int index = order[static_cast<size_t>(orderIndex)];
            if (index != 0) {
                const Kart3D& kart = karts_[static_cast<size_t>(index)];
                const TrackPoint3D ground = track_.sample(kart.progress);
                const Vector3 center = toWorld(kart.pos, bankedElevation(ground, kart.lane));
                const Vector3 offset = sub(center, camera_.position);
                const float distanceSq = offset.x * offset.x + offset.y * offset.y + offset.z * offset.z;
                // Reject only geometry effectively intersecting the camera's
                // near plane. Racing opponents must remain visible in contact.
                if (distanceSq < 1.5f * 1.5f) {
                    continue;
                }
            }
            drawKart(karts_[static_cast<size_t>(index)], index == 0);
        }
    }

    void drawParticles() {
        for (const Particle3D& p : particles_) {
            const float t = std::clamp(p.life / p.maxLife, 0.0f, 1.0f);
            Color c = p.color;
            c.a = static_cast<unsigned char>(static_cast<float>(c.a) * t);
            const float size = p.size * kRenderScale * (1.35f - t * 0.25f);
            if (IsTextureValid(particleTexture_)) {
                DrawBillboard(camera_, particleTexture_, toWorld(p.pos, p.elevation), size, c);
            } else {
                DrawSphere(toWorld(p.pos, p.elevation), size * 0.5f, c);
            }
        }
    }

    void drawSpeedFx() {
        if (mode_ == Mode::Garage || karts_.empty()) {
            return;
        }
        const Kart3D& player = karts_[0];
        const float speedN = std::clamp(std::max(0.0f, player.telemetry.forwardSpeed) /
                                            std::max(1.0f, player.tuning.maxForwardSpeed),
                                        0.0f, 1.0f);
        float amount = smoothstep(std::clamp((speedN - 0.22f) / 0.78f, 0.0f, 1.0f));
        if (player.boostTimer > 0.0f) {
            amount = std::max(amount, 0.72f + player.boostPower * 0.28f);
        }
        if (amount <= 0.01f) {
            return;
        }
        const float width = static_cast<float>(GetScreenWidth());
        const float height = static_cast<float>(GetScreenHeight());
        const Vector2 center{width * 0.5f, height * 0.43f};
        for (int i = 0; i < 30; ++i) {
            const float seed = std::fmod(static_cast<float>(i) * 0.6180339f +
                                             raceTime_ * (0.34f + amount * 0.92f + i * 0.002f),
                                         1.0f);
            const float bandSeed = std::fmod(static_cast<float>(i) * 0.381966f, 1.0f);
            const bool leftSide = (i & 1) == 0;
            const float x = width * (leftSide ? lerp(0.03f, 0.22f, bandSeed)
                                              : lerp(0.78f, 0.97f, bandSeed));
            const float y = height * lerp(0.55f, 0.96f, seed);
            const Vector2 start{x, y};
            Vector2 direction{start.x - center.x, start.y - center.y};
            const float directionLength = std::max(1.0f, std::sqrt(direction.x * direction.x + direction.y * direction.y));
            direction.x /= directionLength;
            direction.y /= directionLength;
            const float lineLength = lerp(8.0f, 76.0f, amount) * (0.50f + seed * 0.82f);
            const Vector2 end{start.x + direction.x * lineLength, start.y + direction.y * lineLength};
            const unsigned char alpha = static_cast<unsigned char>((12.0f + seed * 54.0f) * amount);
            DrawLineEx(start, end, 0.8f + amount * 1.7f, Color{231, 244, 239, alpha});
        }
    }

    void drawHud(float fps, bool hasController) {
        (void)fps;
        if (mode_ == Mode::Garage) {
            const KartSpec3D& spec = specs_[static_cast<size_t>(selectedCar_)];
            formula_forge::ui::SelectionHudViewModel view;
            view.stage = selectionStage_;
            view.selectedMode = selectedSession_;
            view.mapName = selectedMap().name;
            view.mapDescription = selectedMap().backstory;
            constexpr int kPreviewPoints = 128;
            std::array<Vec2, kPreviewPoints> previewPoints{};
            Vec2 previewMin{std::numeric_limits<float>::max(), std::numeric_limits<float>::max()};
            Vec2 previewMax{std::numeric_limits<float>::lowest(), std::numeric_limits<float>::lowest()};
            for (int i = 0; i < kPreviewPoints; ++i) {
                const float progress = track_.startProgress() +
                                       track_.totalLength() * static_cast<float>(i) / kPreviewPoints;
                const Vec2 point = track_.sample(progress).pos;
                previewPoints[static_cast<size_t>(i)] = point;
                previewMin.x = std::min(previewMin.x, point.x);
                previewMin.y = std::min(previewMin.y, point.y);
                previewMax.x = std::max(previewMax.x, point.x);
                previewMax.y = std::max(previewMax.y, point.y);
            }
            const Vec2 previewSpan{std::max(1.0f, previewMax.x - previewMin.x),
                                   std::max(1.0f, previewMax.y - previewMin.y)};
            view.coursePolylinePointCount = kPreviewPoints;
            for (int i = 0; i < kPreviewPoints; ++i) {
                const Vec2 point = previewPoints[static_cast<size_t>(i)];
                view.coursePolyline[static_cast<size_t>(i * 2)] = (point.x - previewMin.x) / previewSpan.x;
                view.coursePolyline[static_cast<size_t>(i * 2 + 1)] = (point.y - previewMin.y) / previewSpan.y;
            }
            switch (selectionStage_) {
                case formula_forge::ui::SelectionStage::Mode:
                    view.itemName = isTimeTrial() ? "TIME TRIAL" : "RACE";
                    view.itemSubtitle = isTimeTrial() ? "SOLO / HOT LAPS" : "FULL GRID / RACE DISTANCE";
                    view.backstory = isTimeTrial()
                                         ? "A clear circuit, your chosen run length, and one target: your best time."
                                         : "Race the full field over a chosen distance and fight for the podium.";
                    view.itemIndex = isTimeTrial() ? 1 : 0;
                    view.itemCount = 2;
                    break;
                case formula_forge::ui::SelectionStage::Car:
                    view.itemName = spec.name;
                    view.itemSubtitle = "SPEC LIVERY";
                    view.itemIndex = selectedCar_;
                    view.itemCount = static_cast<int>(specs_.size());
                    break;
                case formula_forge::ui::SelectionStage::Map:
                    view.itemName = selectedMap().name;
                    view.itemSubtitle = selectedMap().subtitle;
                    view.backstory = selectedMap().backstory;
                    view.itemIndex = selectedMap_;
                    view.itemCount = static_cast<int>(kMaps.size());
                    break;
            }
            view.lapOptions = kLapOptions;
            view.lapOptionCount = kLapOptionCount;
            view.selectedLapOption = selectedLapOption_;
            view.lapsAdjustable = true;
            view.presentationTimeSeconds = presentationTime_;
            view.canContinue = true;
            view.controllerConnected = hasController;
            if (selectionStage_ == formula_forge::ui::SelectionStage::Mode) {
                view.navigationHint = "D-PAD / STEER   SESSION";
                view.confirmHint = "A   SELECT";
            } else if (selectionStage_ == formula_forge::ui::SelectionStage::Car) {
                view.navigationHint = "D-PAD / STEER   CAR";
                view.confirmHint = "A   CONTINUE";
            } else {
                view.navigationHint = "LT / RT OR D-PAD / STEER   TRACK     D-PAD UP / DOWN   LAPS";
                view.confirmHint = isTimeTrial() ? "A   START TIME TRIAL" : "A   START RACE";
            }
            view.backHint = "B   BACK";
            formula_forge::ui::DrawSelectionHud(view);
        } else if (mode_ == Mode::Results) {
            formula_forge::ui::ResultsHudViewModel view;
            view.eventName = sessionEventName();
            view.rowCount = resultCount_;
            view.totalLaps = targetLaps();
            view.isTimeTrial = isTimeTrial();
            view.bestLapTimeSeconds = bestLapTime_;
            view.hasBestLap = hasBestLap_;
            view.selectedAction = resultsAction_;
            view.presentationTimeSeconds = presentationTime_;
            view.controllerConnected = hasController;
            for (int i = 0; i < resultCount_; ++i) {
                const RaceResult3D& result = results_[static_cast<size_t>(i)];
                const Kart3D& kart = karts_[static_cast<size_t>(result.kartIndex)];
                formula_forge::ui::ResultRowViewModel& row = view.rows[static_cast<size_t>(i)];
                row.position = result.position;
                row.driverName = kart.racer;
                row.vehicleName = kart.spec.name;
                row.finishTimeSeconds = result.finishTimeSeconds;
                row.lapsCompleted = result.lapsCompleted;
                row.isPlayer = result.kartIndex == 0;
            }
            formula_forge::ui::DrawResultsHud(view);
        } else {
            const Kart3D& player = karts_[0];
            const int laps = targetLaps();
            formula_forge::ui::RaceHudViewModel view;
            view.vehicleName = player.spec.name;
            view.driverName = player.racer;
            const float speedKphScale = speedKphPerSimulationUnit(track_.layout());
            view.speedKph = static_cast<int>(std::max(0.0f, player.telemetry.forwardSpeed) * speedKphScale + 0.5f);
            view.gear = player.gear;
            view.engineRpmNormalized = player.engineRpmNormalized;
            view.currentLap = laps == kInfiniteLaps ? std::max(1, player.lap + 1) : std::clamp(player.lap + 1, 1, laps);
            view.totalLaps = laps;
            view.position = playerPosition_;
            view.racerCount = activeKartCount();
            view.raceTimeSeconds = raceTime_;
            view.racerProgressCount = activeKartCount();
            view.playerProgressIndex = 0;
            view.isTimeTrial = isTimeTrial();
            view.currentLapTimeSeconds = std::max(0.0f, raceTime_ - lapStartTime_);
            view.bestLapTimeSeconds = bestLapTime_;
            view.hasBestLap = hasBestLap_;
            const float raceDistance = laps == kInfiniteLaps ? track_.totalLength() : track_.totalLength() * static_cast<float>(laps);
            for (int i = 0; i < activeKartCount(); ++i) {
                const float score = raceScore(karts_[static_cast<size_t>(i)]);
                view.racerProgress[static_cast<size_t>(i)] = laps == kInfiniteLaps
                                                                 ? raceLapProgress(karts_[static_cast<size_t>(i)]) / track_.totalLength()
                                                                 : std::clamp(score / raceDistance, 0.0f, 1.0f);
            }
            view.raceProgress = view.racerProgress[0];
            constexpr int kHudMapPoints = 128;
            std::array<Vec2, kHudMapPoints> hudMapPoints{};
            Vec2 hudMapMin{std::numeric_limits<float>::max(), std::numeric_limits<float>::max()};
            Vec2 hudMapMax{std::numeric_limits<float>::lowest(), std::numeric_limits<float>::lowest()};
            for (int i = 0; i < kHudMapPoints; ++i) {
                const float progress = track_.startProgress() +
                                       track_.totalLength() * static_cast<float>(i) / kHudMapPoints;
                const Vec2 point = track_.sample(progress).pos;
                hudMapPoints[static_cast<size_t>(i)] = point;
                hudMapMin.x = std::min(hudMapMin.x, point.x);
                hudMapMin.y = std::min(hudMapMin.y, point.y);
                hudMapMax.x = std::max(hudMapMax.x, point.x);
                hudMapMax.y = std::max(hudMapMax.y, point.y);
            }
            const Vec2 hudMapSpan{std::max(1.0f, hudMapMax.x - hudMapMin.x),
                                  std::max(1.0f, hudMapMax.y - hudMapMin.y)};
            const float hudMapScale = std::max(hudMapSpan.x, hudMapSpan.y);
            const Vec2 hudMapInset{(1.0f - hudMapSpan.x / hudMapScale) * 0.5f,
                                   (1.0f - hudMapSpan.y / hudMapScale) * 0.5f};
            view.coursePolylinePointCount = kHudMapPoints;
            view.courseProgress = raceLapProgress(player) / track_.totalLength();
            for (int i = 0; i < kHudMapPoints; ++i) {
                const Vec2 point = hudMapPoints[static_cast<size_t>(i)];
                view.coursePolyline[static_cast<size_t>(i * 2)] =
                    hudMapInset.x + (point.x - hudMapMin.x) / hudMapScale;
                view.coursePolyline[static_cast<size_t>(i * 2 + 1)] =
                    hudMapInset.y + (point.y - hudMapMin.y) / hudMapScale;
            }
            view.driftCharge = std::clamp(player.driftCharge / player.tuning.tierThreeCharge, 0.0f, 1.0f);
            view.boostCharge = std::clamp(player.boostTimer / player.tuning.tierThreeBoostDuration, 0.0f, 1.0f);
            view.presentationTimeSeconds = raceTime_;
            view.boostActive = player.boostTimer > 0.0f;
            view.drsAvailable = player.drsAvailable;
            view.drsActive = player.drsActive;
            view.shiftRecommended = playerShiftRecommended();
            view.wrongWay = raceFlow_ && raceFlow_->racer(0).wrongWay;
            view.finished = raceFinished_;
            view.controllerConnected = hasController;
            formula_forge::ui::DrawRaceHud(view);
            formula_forge::ui::CountdownHudViewModel countdown;
            countdown.visible = (raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Countdown) || countdownGoTimer_ > 0.0f;
            countdown.secondsRemaining = raceFlow_ && raceFlow_->phase() == ArcadeRacePhase::Countdown
                                             ? raceFlow_->countdownRemainingSeconds()
                                             : 0.0f;
            formula_forge::ui::DrawCountdownHud(countdown);
        }
        if (mode_ == Mode::Pause) {
            formula_forge::ui::PauseHudViewModel view;
            view.eventName = sessionEventName();
            view.currentLap = std::max(1, karts_[0].lap + 1);
            view.totalLaps = targetLaps();
            view.raceTimeSeconds = raceTime_;
            view.isTimeTrial = isTimeTrial();
            view.currentLapTimeSeconds = std::max(0.0f, raceTime_ - lapStartTime_);
            view.bestLapTimeSeconds = bestLapTime_;
            view.hasBestLap = hasBestLap_;
            view.selectedAction = pauseAction_;
            view.visible = true;
            formula_forge::ui::DrawPauseHud(view);
        }
    }

    Track3D track_;
    std::vector<float> aiLapSpeedPlan_;
    std::vector<float> aiLapDrsSpeedPlan_;
    std::vector<float> aiRaceSpeedPlan_;
    std::vector<float> aiRaceDrsSpeedPlan_;
    std::vector<float> aiLapTheoreticalSpeedPlan_;
    std::vector<float>
        aiLapDrsTheoreticalSpeedPlan_;
    std::vector<float> aiLapLanePlan_;
    std::vector<AiPaceCornerZone> aiPaceCornerZones_;
    float aiLapTheoreticalSeconds_ = 0.0f;
    float aiLapModelSeconds_ = 0.0f;
    float aiRacePlanSeconds_ = 0.0f;
    float aiRaceDrsPlanSeconds_ = 0.0f;
    int aiLapSelectedSmoothingSpan_ = 0;
    float aiLapSelectedRoadFraction_ = 0.0f;
    TrackLayoutId aiLapPlanLayout_ = TrackLayoutId::Spa;
    bool aiOptimizationProfileActive_ = false;
    AiTimeTrialProfile aiOptimizationProfile_ =
        aiTimeTrialProfile(TrackLayoutId::Monza);
    std::array<float, 24>
        aiOptimizationLaneOffsetsMeters_{};
    std::array<KartSpec3D, 11> specs_;
    std::array<std::string, kKartCount> racers_;
    std::mt19937 raceRandom_;
    std::vector<Kart3D> karts_;
    std::vector<Particle3D> particles_;
    std::unique_ptr<ArcadeRaceFlow> raceFlow_;
    arcade_render::ArcadeRender renderer_;
    ArcadeAudio audio_;
    formula_forge::TrackRenderer trackRenderer_;
    Texture2D particleTexture_{};
    Texture2D loadingScreenTexture_{};
    Texture2D garageBackgroundTexture_{};
    Camera camera_{};
    Camera previousCamera_{};
    Mode mode_ = Mode::Loading;
    formula_forge::ui::SelectionStage selectionStage_ = formula_forge::ui::SelectionStage::Mode;
    formula_forge::ui::GameModeOption selectedSession_ = formula_forge::ui::GameModeOption::Race;
    formula_forge::ui::PauseAction pauseAction_ = formula_forge::ui::PauseAction::Resume;
    formula_forge::ui::ResultsAction resultsAction_ = formula_forge::ui::ResultsAction::Replay;
    int selectedCar_ = 0;
    int selectedRacer_ = 0;
    int selectedMap_ = 0;
    int selectedLapOption_ = 0;
    int playerPosition_ = 1;
    std::array<RaceResult3D, kKartCount> results_{};
    int resultCount_ = 0;
    float raceTime_ = 0.0f;
    float finishTime_ = 0.0f;
    float lapStartTime_ = 0.0f;
    float lastLapTime_ = 0.0f;
    float bestLapTime_ = 0.0f;
    float garageSpin_ = 0.0f;
    float loadingTime_ = 0.0f;
    float presentationTime_ = 0.0f;
    float fxAccumulator_ = 0.0f;
    float renderAlpha_ = 1.0f;
    float countdownGoTimer_ = 0.0f;
    bool raceFinished_ = false;
    bool hasBestLap_ = false;
};

Input3D toGameInput(const agent_play::Input& input) {
    Input3D gameInput;
    gameInput.steer = input.steer;
    gameInput.throttle = input.throttle;
    gameInput.brake = input.brake;
    gameInput.a = input.confirm;
    gameInput.b = input.cancel;
    gameInput.start = input.pause;
    gameInput.back = input.recover;
    gameInput.left = input.left;
    gameInput.right = input.right;
    gameInput.up = input.up;
    gameInput.down = input.down;
    gameInput.pageLeft = input.pageLeft;
    gameInput.pageRight = input.pageRight;
    gameInput.shiftDown = input.shiftDown;
    gameInput.shiftUp = input.shiftUp;
    gameInput.automaticShift = false;
    return gameInput;
}

void clearMomentaryAgentInput(Input3D& input) {
    input.a = false;
    input.b = false;
    input.start = false;
    input.back = false;
    input.left = false;
    input.right = false;
    input.up = false;
    input.down = false;
    input.pageLeft = false;
    input.pageRight = false;
    input.shiftDown = false;
    input.shiftUp = false;
}

std::string safeAgentFrameName(std::string_view requested, std::uint64_t frame) {
    std::string name;
    name.reserve(std::min<size_t>(requested.size(), 80));
    for (const unsigned char ch : requested) {
        if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '_' || ch == '-') {
            name.push_back(static_cast<char>(ch));
        }
    }
    if (name.empty()) {
        name = "frame_" + std::to_string(frame);
    }
    return name + ".png";
}

int runAgentPlaySession(Game3D& game, const std::filesystem::path& captureDirectory) {
    std::error_code directoryError;
    std::filesystem::create_directories(captureDirectory, directoryError);
    if (directoryError) {
        std::cout << "{\"ok\":false,\"error\":"
                  << agent_play::jsonString("cannot create frame directory: " + directoryError.message()) << "}\n" << std::flush;
        return 1;
    }

    std::uint64_t simulationFrame = 0;
    std::cout << "{\"ok\":true,\"type\":\"ready\",\"protocol\":3,\"fixed_dt_s\":" << kFixedDt
              << ",\"frame_directory\":" << agent_play::jsonString(std::filesystem::absolute(captureDirectory).string())
              << ",\"state\":" << game.agentStateJson(simulationFrame) << "}\n" << std::flush;

    std::string line;
    while (std::getline(std::cin, line)) {
        const agent_play::ParseResult parsed = agent_play::parseCommand(line);
        if (!parsed.ok) {
            std::cout << "{\"ok\":false,\"error\":" << agent_play::jsonString(parsed.error) << "}\n" << std::flush;
            continue;
        }
        const agent_play::Command& command = parsed.command;
        const std::string id = command.requestId >= 0 ? ",\"id\":" + std::to_string(command.requestId) : std::string{};
        if (command.type == agent_play::CommandType::Quit) {
            std::cout << "{\"ok\":true" << id << ",\"type\":\"bye\"}\n" << std::flush;
            return 0;
        }
        if (command.type == agent_play::CommandType::Help) {
            std::cout
                << "{\"ok\":true" << id
                << ",\"type\":\"help\",\"commands\":{"
                   "\"state\":{},"
                   "\"step\":{\"frames\":\"1..2400\",\"render\":\"bool\",\"name\":\"optional frame basename\","
                   "\"input\":{\"steer\":\"-1..1\",\"throttle\":\"0..1\",\"brake\":\"0..1\","
                   "\"shift_up\":\"bool\",\"shift_down\":\"bool\","
                   "\"confirm\":\"bool\",\"cancel\":\"bool\",\"pause\":\"bool\",\"recover\":\"bool\","
                   "\"left\":\"bool\",\"right\":\"bool\",\"up\":\"bool\",\"down\":\"bool\","
                   "\"page_left\":\"bool\",\"page_right\":\"bool\"}},"
                   "\"frame\":{\"name\":\"optional frame basename\"},\"reset\":{},\"help\":{},\"quit\":{}},"
                   "\"notes\":[\"Analog controls are held for every requested frame.\","
                   "\"Digital controls fire on the first requested frame only.\","
                   "\"recover resets the car during a race and acts as back in menus.\"]}\n"
                << std::flush;
            continue;
        }
        if (command.type == agent_play::CommandType::Reset) {
            game.resetAgentSession();
            simulationFrame = 0;
        } else if (command.type == agent_play::CommandType::Step) {
            Input3D input = toGameInput(command.input);
            for (int i = 0; i < command.frames; ++i) {
                game.update(kFixedDt, input, true);
                ++simulationFrame;
                clearMomentaryAgentInput(input);
            }
        }

        std::string framePath;
        if (command.type == agent_play::CommandType::Frame || command.render) {
            const std::string fileName = safeAgentFrameName(command.frameName, simulationFrame);
            const std::filesystem::path path = captureDirectory / fileName;
            // raylib resolves screenshot names relative to the executable's
            // storage directory and explicitly does not accept absolute paths.
            std::error_code relativeError;
            const std::filesystem::path raylibPath =
                std::filesystem::relative(path, std::filesystem::path(GetApplicationDirectory()), relativeError);
            if (relativeError || raylibPath.empty()) {
                std::cout << "{\"ok\":false" << id << ",\"error\":"
                          << agent_play::jsonString("cannot resolve frame path: " + relativeError.message()) << "}\n"
                          << std::flush;
                continue;
            }
            game.render(120.0f, true, raylibPath.string().c_str(), 1.0f);
            framePath = std::filesystem::absolute(path).string();
        }
        std::cout << "{\"ok\":true" << id << ",\"type\":\"state\",\"state\":"
                  << game.agentStateJson(simulationFrame);
        if (!framePath.empty()) {
            std::cout << ",\"frame_path\":" << agent_play::jsonString(framePath);
        }
        std::cout << "}\n" << std::flush;
    }
    return 0;
}

}  // namespace

int runFormulaForge(int argc, char** argv) {
    if (hasArg(argc, argv, "--agent-play-audit")) {
        const bool ok = agent_play::runProtocolParserAudit();
        std::cout << "agent-play-protocol-audit commands=6 bounds=valid escaping=valid contact_schema=valid ok=" << ok << "\n";
        return ok ? 0 : 1;
    }
    if (hasArg(argc, argv, "--track-catalog-audit")) {
        return runTrackCatalogAudit() ? 0 : 1;
    }
    if (hasArg(argc, argv, "--spa-audit")) {
        return runSpaGeometryAudit() ? 0 : 1;
    }
    const bool inputAudit = hasArg(argc, argv, "--input-audit");
    if (inputAudit) {
        const bool ok = controllerContractAudit();
        std::cout << "input-audit sequence=0,1,1,0,0 trigger_ranges=valid authoritative_backend=single ok=" << ok << "\n";
        return ok ? 0 : 1;
    }
    const bool audioAudit = hasArg(argc, argv, "--audio-audit");
    if (audioAudit) {
        const ArcadeAudioAuditResult result = runArcadeAudioUnitAudit();
        std::cout << "audio-audit checks=" << result.checks << " failures=" << result.failures
                  << " silence_rms=" << result.silenceRms << " beep_rms=" << result.beepRms
                  << " held_alert_rms=" << result.heldAlertRms << " peak=" << result.peakMagnitude
                  << " deterministic_hash=" << result.deterministicHash << " ok=" << result.ok << "\n";
        return result.ok ? 0 : 1;
    }
    if (hasArg(argc, argv, "--shift-beep-preview")) {
        const bool ok = playArcadeShiftBeepPreview();
        std::cout << "shift-beep-preview device_ready=" << ok << "\n";
        return ok ? 0 : 1;
    }
    const bool raceFlowAudit = hasArg(argc, argv, "--race-flow-audit");
    if (raceFlowAudit) {
        const ArcadeRaceAuditResult result = runArcadeRaceUnitAudit();
        std::cout << "race-flow-audit checks=" << result.checks << " failures=" << result.failures
                  << " phases=" << result.phasesValid << " checkpoints=" << result.checkpointsValid
                  << " wrong_way=" << result.wrongWayValid << " finish_order=" << result.finishOrderingValid
                  << " infinite=" << result.infiniteModeValid << " discontinuity_guard=" << result.discontinuityGuardValid
                  << " ok=" << result.ok << "\n";
        return result.ok ? 0 : 1;
    }
    const bool vehicleAudit = hasArg(argc, argv, "--vehicle-audit");
    if (vehicleAudit) {
        const ArcadeVehicleAuditResult result = runArcadeVehicleUnitAudit();
        std::cout << "vehicle-audit checks=" << result.checks << " failures=" << result.failures
                  << " straight_speed=" << result.straightLineSpeed << " stop_speed=" << result.stoppedSpeed
                  << " momentum_error=" << result.momentumError << " drift_slip=" << result.driftPeakSlip
                  << " drift_boost_tier=" << result.driftBoostTier << " loose_surface_ratio=" << result.looseSurfaceSpeedRatio
                  << " shoulder_ratio=" << result.shoulderSpeedRatio
                  << " first_gear_speed=" << result.firstGearLimitedSpeed << " auto_top_gear=" << result.automaticTopGear
                  << " rejected_downshift_gear=" << result.rejectedDownshiftGear
                  << " coast_loss_low_high=" << result.lowGearCoastLoss << "/" << result.highGearCoastLoss
                  << " brake_yaw=" << result.brakeOversteerPeakYaw
                  << " brake_slip=" << result.brakeOversteerPeakSlip << " brake_recovery=" << result.brakeRecoverySlip
                  << " brake_load_2s=" << result.brakeLoadAfterRelease
                  << " jump_apex=" << result.jumpApex << " jump_airtime=" << result.jumpAirTime
                  << " landing_impulse=" << result.jumpLandingImpulse << " jump_step_error=" << result.jumpFixedStepError
                  << " jump_pitch_up=" << result.jumpNoseUpPitch << " jump_pitch_down=" << result.jumpNoseDownPitch
                  << " fixed_step_error=" << result.fixedStepPositionError << " ok=" << result.ok << "\n";
        return result.ok ? 0 : 1;
    }
    const bool assetAudit = hasArg(argc, argv, "--asset-audit");
    const bool agentPlay = hasArg(argc, argv, "--agent-play");
    const bool aiPaceAuditSpa = hasArg(argc, argv, "--ai-pace-audit-spa");
    const bool aiPaceAuditSuzuka = hasArg(argc, argv, "--ai-pace-audit-suzuka");
    const bool aiPaceAuditSilverstone = hasArg(argc, argv, "--ai-pace-audit-silverstone");
    const bool aiPaceAuditInterlagos = hasArg(argc, argv, "--ai-pace-audit-interlagos");
    const bool aiPaceAuditShanghai = hasArg(argc, argv, "--ai-pace-audit-shanghai");
    const bool aiPaceAuditBahrain = hasArg(argc, argv, "--ai-pace-audit-bahrain");
    const bool aiPaceAuditSepang = hasArg(argc, argv, "--ai-pace-audit-sepang");
    const bool aiPaceAuditCota = hasArg(argc, argv, "--ai-pace-audit-cota");
    const bool aiPaceAuditIstanbul = hasArg(argc, argv, "--ai-pace-audit-istanbul");
    const bool aiPaceAuditHockenheim = hasArg(argc, argv, "--ai-pace-audit-hockenheim");
    const bool aiPaceAuditBuddh = hasArg(argc, argv, "--ai-pace-audit-buddh");
    const bool aiRacePaceAudit =
        hasArg(argc, argv,
               "--ai-race-pace-audit");
    const bool aiPhysicsParityAudit = hasArg(argc, argv, "--ai-physics-parity-audit");
    const bool monzaMinimumTimeAudit =
        hasArg(argc, argv, "--monza-minimum-time-audit");
    const bool aiPaceAudit = hasArg(argc, argv, "--ai-pace-audit") || aiPaceAuditSpa || aiPaceAuditSuzuka ||
                             aiPaceAuditSilverstone || aiPaceAuditInterlagos || aiPaceAuditShanghai ||
                             aiPaceAuditBahrain || aiPaceAuditSepang ||
                             aiPaceAuditCota || aiPaceAuditIstanbul || aiPaceAuditHockenheim ||
                             aiPaceAuditBuddh;
    TrackLayoutId aiPaceAuditLayout = TrackLayoutId::Monza;
    if (aiPaceAuditSpa) {
        aiPaceAuditLayout = TrackLayoutId::Spa;
    } else if (aiPaceAuditSuzuka) {
        aiPaceAuditLayout = TrackLayoutId::Suzuka;
    } else if (aiPaceAuditSilverstone) {
        aiPaceAuditLayout = TrackLayoutId::Silverstone;
    } else if (aiPaceAuditInterlagos) {
        aiPaceAuditLayout = TrackLayoutId::Interlagos;
    } else if (aiPaceAuditShanghai) {
        aiPaceAuditLayout = TrackLayoutId::Shanghai;
    } else if (aiPaceAuditBahrain) {
        aiPaceAuditLayout = TrackLayoutId::Bahrain;
    } else if (aiPaceAuditSepang) {
        aiPaceAuditLayout = TrackLayoutId::Sepang;
    } else if (aiPaceAuditCota) {
        aiPaceAuditLayout = TrackLayoutId::Cota;
    } else if (aiPaceAuditIstanbul) {
        aiPaceAuditLayout = TrackLayoutId::Istanbul;
    } else if (aiPaceAuditHockenheim) {
        aiPaceAuditLayout = TrackLayoutId::Hockenheim;
    } else if (aiPaceAuditBuddh) {
        aiPaceAuditLayout = TrackLayoutId::Buddh;
    }
    const bool racecraftAuditSpa = hasArg(argc, argv, "--racecraft-audit-spa");
    const bool racecraftAuditSuzuka = hasArg(argc, argv, "--racecraft-audit-suzuka");
    const bool racecraftAuditSilverstone = hasArg(argc, argv, "--racecraft-audit-silverstone");
    const bool racecraftAuditMonza = hasArg(argc, argv, "--racecraft-audit-monza");
    const bool racecraftAuditInterlagos = hasArg(argc, argv, "--racecraft-audit-interlagos");
    const bool raceFlatAuditMonza = hasArg(argc, argv, "--race-flat-audit-monza");
    const bool monzaCompetitionAuditFiveLaps =
        hasArg(argc, argv,
               "--monza-competition-audit-5");
    const bool monzaCompetitionAuditTenLaps =
        hasArg(argc, argv,
               "--monza-competition-audit-10");
    const bool monzaCompetitionAudit =
        hasArg(argc, argv,
               "--monza-competition-audit") ||
        monzaCompetitionAuditFiveLaps ||
        monzaCompetitionAuditTenLaps;
    const bool raceLineAuditAll = hasArg(argc, argv, "--race-line-audit-all");
    const bool racecraftAudit = hasArg(argc, argv, "--racecraft-audit") || racecraftAuditSpa ||
                                racecraftAuditSuzuka || racecraftAuditSilverstone || racecraftAuditMonza ||
                                racecraftAuditInterlagos || raceFlatAuditMonza ||
                                raceLineAuditAll;
    int racecraftAuditMap = 2;
    if (racecraftAuditSpa) {
        racecraftAuditMap = 0;
    } else if (racecraftAuditSuzuka) {
        racecraftAuditMap = 1;
    } else if (racecraftAuditSilverstone) {
        racecraftAuditMap = 2;
    } else if (racecraftAuditMonza || raceFlatAuditMonza) {
        racecraftAuditMap = 3;
    } else if (racecraftAuditInterlagos) {
        racecraftAuditMap = 4;
    }
    const bool windowed = agentPlay || hasArg(argc, argv, "--windowed") || hasArg(argc, argv, "--smoke-render") || assetAudit ||
                          hasArg(argc, argv, "--diagnose-controller") || hasArg(argc, argv, "--handling-audit") ||
                          hasArg(argc, argv, "--race-audit") || racecraftAudit || monzaCompetitionAudit ||
                          aiPaceAudit || aiRacePaceAudit ||
                          aiPhysicsParityAudit ||
                          monzaMinimumTimeAudit ||
                          hasArg(argc, argv, "--time-trial-audit") ||
                          hasArg(argc, argv, "--grid-audit") ||
                          hasArg(argc, argv, "--collision-audit") ||
                          hasArg(argc, argv, "--spa-control-audit") ||
                          hasArg(argc, argv, "--terrain-audit") ||
                          hasArg(argc, argv, "--perf-audit") || hasArg(argc, argv, "--spa-perf-audit") ||
                          hasArg(argc, argv, "--capture-lap") ||
                          hasArg(argc, argv, "--capture-driven-lap") || hasArg(argc, argv, "--capture-spa-lap") ||
                          hasArg(argc, argv, "--capture-time-trial") ||
                          hasArg(argc, argv, "--capture-section-tour") || hasArg(argc, argv, "--capture-spa-tour") ||
                          hasArg(argc, argv, "--capture-suzuka-tour") ||
                          hasArg(argc, argv, "--capture-silverstone-tour") ||
                          hasArg(argc, argv, "--capture-interlagos-tour") ||
                          hasArg(argc, argv, "--capture-map-gallery");
    const bool smokeRender = hasArg(argc, argv, "--smoke-render");
    const bool capturePlaytest = hasArg(argc, argv, "--capture-playtest");
    const bool captureSpaLap = hasArg(argc, argv, "--capture-spa-lap");
    const bool captureDrivenLap = hasArg(argc, argv, "--capture-lap") || hasArg(argc, argv, "--capture-driven-lap") || captureSpaLap;
    const bool captureTimeTrial = hasArg(argc, argv, "--capture-time-trial");
    const bool captureSpaTour = hasArg(argc, argv, "--capture-spa-tour");
    const bool captureSuzukaTour = hasArg(argc, argv, "--capture-suzuka-tour");
    const bool captureSilverstoneTour = hasArg(argc, argv, "--capture-silverstone-tour");
    const bool captureInterlagosTour = hasArg(argc, argv, "--capture-interlagos-tour");
    const bool captureSectionTour = hasArg(argc, argv, "--capture-section-tour") || captureSpaTour ||
                                    captureSuzukaTour || captureSilverstoneTour || captureInterlagosTour;
    const bool captureMapGallery = hasArg(argc, argv, "--capture-map-gallery");
    const bool diagnoseController = hasArg(argc, argv, "--diagnose-controller");
    const bool handlingAudit = hasArg(argc, argv, "--handling-audit");
    const bool raceAudit = hasArg(argc, argv, "--race-audit");
    const bool timeTrialAudit = hasArg(argc, argv, "--time-trial-audit");
    const bool gridAudit = hasArg(argc, argv, "--grid-audit");
    const bool collisionAudit = hasArg(argc, argv, "--collision-audit");
    const bool spaControlAudit = hasArg(argc, argv, "--spa-control-audit");
    const bool terrainAudit = hasArg(argc, argv, "--terrain-audit");
    const bool spaPerfAudit = hasArg(argc, argv, "--spa-perf-audit");
    const bool perfAudit = hasArg(argc, argv, "--perf-audit") || spaPerfAudit;
    const bool backgroundAudit = assetAudit || handlingAudit || raceAudit || racecraftAudit ||
                                 monzaCompetitionAudit ||
                                 aiPaceAudit || aiRacePaceAudit ||
                                 aiPhysicsParityAudit || timeTrialAudit || gridAudit ||
                                 collisionAudit || spaControlAudit || terrainAudit || diagnoseController ||
                                 monzaMinimumTimeAudit;
    const std::filesystem::path launchDir = std::filesystem::current_path();
    const std::filesystem::path captureDir = launchDir / "build" / "playtest_frames";

    SetTraceLogLevel(LOG_ERROR);
    unsigned int configFlags = FLAG_WINDOW_RESIZABLE | FLAG_MSAA_4X_HINT;
    if (backgroundAudit) {
        configFlags |= FLAG_WINDOW_HIDDEN;
    }
    if (!(agentPlay || assetAudit || smokeRender || capturePlaytest || captureDrivenLap || captureTimeTrial || captureSectionTour || perfAudit)) {
        configFlags |= FLAG_VSYNC_HINT;
    }
    SetConfigFlags(configFlags);
    InitWindow(1280, 720, "Formula Forge");
    SetExitKey(KEY_NULL);
    ChangeDirectory(launchDir.string().c_str());
    formula_forge::ui::InitializeUiFont("assets/fonts/NotoSansDisplay-Bold.ttf", 72);
    formula_forge::ui::InitializeSelectionFont("assets/fonts/Lato-HeavyItalic.ttf", 72);
    SetTargetFPS(120);
    if (!windowed) {
        const int monitor = GetCurrentMonitor();
        SetWindowSize(GetMonitorWidth(monitor), GetMonitorHeight(monitor));
        ToggleFullscreen();
    }

    constexpr SDL_InitFlags kSdlInputFlags = static_cast<SDL_InitFlags>(SDL_INIT_GAMEPAD | SDL_INIT_JOYSTICK);
    const bool sdlInputReady = SDL_InitSubSystem(kSdlInputFlags);
    if (!sdlInputReady) {
        std::cerr << "SDL gamepad fallback unavailable: " << SDL_GetError() << "\n";
    }

    ControllerReader controller(sdlInputReady);
    const bool automatedRun = agentPlay || assetAudit || smokeRender || capturePlaytest || captureDrivenLap || captureTimeTrial || captureSectionTour || captureMapGallery || handlingAudit || raceAudit || racecraftAudit ||
                              monzaCompetitionAudit ||
                              aiPaceAudit || aiRacePaceAudit ||
                              aiPhysicsParityAudit || timeTrialAudit || gridAudit || collisionAudit || spaControlAudit || terrainAudit || perfAudit || diagnoseController;
    Game3D game(!automatedRun);
    bool runtimeCleaned = false;
    const auto cleanupRuntime = [&]() {
        if (runtimeCleaned) {
            return;
        }
        game.shutdown();
        formula_forge::ui::ShutdownUiFont();
        controller.shutdown();
        if (sdlInputReady) {
            SDL_QuitSubSystem(kSdlInputFlags);
        }
        CloseWindow();
        runtimeCleaned = true;
    };
    if (capturePlaytest || captureDrivenLap || captureTimeTrial || captureSectionTour || captureMapGallery || perfAudit) {
        std::filesystem::create_directories(captureDir);
    }
    if (agentPlay) {
        const int result = runAgentPlaySession(game, launchDir / "build" / "agent_play_frames");
        cleanupRuntime();
        return result;
    }
    if (assetAudit) {
        const arcade_render::AuthoredAssetAuditResult result = game.auditAuthoredAssets();
        cleanupRuntime();
        std::cout << "asset-audit cars=" << result.loadedCars << "/11"
                  << " drivers=" << result.loadedDrivers << "/1"
                  << " tracks=" << result.loadedTracks << "/12"
                  << " dimension_checks=" << result.dimensionChecks
                  << " animation_checks=" << result.animationChecks
                  << " load_failures=" << result.loadFailures
                  << " clip_failures=" << result.clipFailures
                  << " failures=" << result.failures << " ok=" << result.ok << "\n";
        return result.ok ? 0 : 1;
    }
    if (perfAudit) {
        if (spaPerfAudit) {
            game.selectMapForCapture(0);
        }
        game.startRace();
    }
    if (handlingAudit) {
        const bool ok = game.runHandlingAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (raceAudit) {
        const bool ok = game.runRaceAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (monzaCompetitionAudit) {
        const int auditLaps =
            monzaCompetitionAuditTenLaps
                ? 10
                : (monzaCompetitionAuditFiveLaps ? 5
                                                 : 2);
        const bool ok =
            game.runMonzaCompetitionAudit(auditLaps);
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (racecraftAudit) {
        const bool ok =
            raceLineAuditAll
                ? game.runAllTrackRaceLineAudit()
                : (raceFlatAuditMonza
                       ? game.runMonzaRaceStartFlatAudit()
                       : game.runRacecraftAudit(
                             racecraftAuditMap));
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (aiPaceAudit) {
        const bool ok = game.runAiPaceAudit(aiPaceAuditLayout);
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (aiRacePaceAudit) {
        const bool ok =
            game.runAiRacePaceAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (aiPhysicsParityAudit) {
        const bool ok = game.runAiPhysicsParityAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (monzaMinimumTimeAudit) {
        const bool ok = game.runMonzaMinimumTimeAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (timeTrialAudit) {
        const bool ok = game.runTimeTrialAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (gridAudit) {
        const bool ok = game.runGridAlignmentAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (captureTimeTrial) {
        game.selectTimeTrialForCapture();
        game.selectMapForCapture(0);
        game.startRace();
        const float startScore = game.playerRaceScoreForCapture();
        const float targetDistance = game.lapLengthForCapture() * 1.05f;
        int framesDriven = 0;
        constexpr int kMaxTimeTrialCaptureFrames = static_cast<int>(1000.0f / kFixedDt);
        while (game.playerRaceScoreForCapture() - startScore < targetDistance &&
               framesDriven < kMaxTimeTrialCaptureFrames) {
            game.update(kFixedDt, game.scriptedInput(), true);
            ++framesDriven;
        }
        game.render(60.0f, true, "../playtest_frames/formula_forge_time_trial.png");
        Input3D pause;
        pause.start = true;
        game.update(kFixedDt, pause, true);
        game.render(60.0f, true, "../playtest_frames/formula_forge_time_trial_pause.png");
        game.update(kFixedDt, pause, true);
        while (!game.showingResultsForCapture() && framesDriven < kMaxTimeTrialCaptureFrames) {
            game.update(kFixedDt, game.scriptedInput(), true);
            ++framesDriven;
        }
        game.render(60.0f, true, "../playtest_frames/formula_forge_time_trial_results.png");
        const float distance = game.playerRaceScoreForCapture() - startScore;
        const bool resultsShown = game.showingResultsForCapture();
        Input3D chooseHome;
        chooseHome.right = true;
        game.update(kFixedDt, chooseHome, true);
        Input3D confirmHome;
        confirmHome.a = true;
        game.update(kFixedDt, confirmHome, true);
        const bool homeWorks = game.showingGarageForCapture();
        cleanupRuntime();
        std::cout << "capture-time-trial frames=" << framesDriven
                  << " distance=" << distance << " results=" << resultsShown
                  << " home=" << homeWorks << "\n";
        return framesDriven < kMaxTimeTrialCaptureFrames && resultsShown && homeWorks ? 0 : 1;
    }
    if (collisionAudit) {
        const bool ok = game.runCollisionAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (spaControlAudit) {
        const bool ok = game.runSpaControlAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (terrainAudit) {
        const bool ok = game.runTerrainAudit();
        cleanupRuntime();
        return ok ? 0 : 1;
    }
    if (captureMapGallery) {
        for (int mapIndex = 0; mapIndex < static_cast<int>(kMaps.size()); ++mapIndex) {
            game.showMapSelectionForCapture(mapIndex);
            const std::filesystem::path path = std::filesystem::path("../playtest_frames") /
                                               TextFormat("formula_forge_map_%02d.png", mapIndex);
            game.render(60.0f, true, path.string().c_str());
        }
        cleanupRuntime();
        return 0;
    }
    if (captureSectionTour) {
        if (captureSpaTour) {
            game.selectMapForCapture(0);
        } else if (captureSuzukaTour) {
            game.selectMapForCapture(1);
        } else if (captureSilverstoneTour) {
            game.selectMapForCapture(2);
        } else if (captureInterlagosTour) {
            game.selectMapForCapture(4);
        }
        static constexpr std::array<float, 10> kTourPhases = {0.035f, 0.102f, 0.135f, 0.245f, 0.355f,
                                                              0.465f, 0.575f, 0.690f, 0.805f, 0.920f};
        const bool detailedCircuitTour = captureSilverstoneTour || captureInterlagosTour;
        const size_t tourFrameCount = detailedCircuitTour ? 72 : kTourPhases.size();
        for (size_t i = 0; i < tourFrameCount; ++i) {
            const float phase = detailedCircuitTour
                                    ? (static_cast<float>(i) + 0.5f) / static_cast<float>(tourFrameCount)
                                    : kTourPhases[i];
            game.setupSectionTour(phase, static_cast<int>(i));
            // Let the staged pack settle into live vehicle dynamics so gallery
            // frames show genuine driving telemetry instead of a static pose.
            for (int frame = 0; frame < 45; ++frame) {
                game.update(kFixedDt, game.scriptedInput(), true);
            }
            const std::filesystem::path path =
                std::filesystem::path("../playtest_frames") /
                TextFormat(captureSpaTour ? "formula_forge_spa_tour_%02d.png"
                                         : (captureSuzukaTour ? "formula_forge_suzuka_tour_%02d.png"
                                            : (captureSilverstoneTour ? "formula_forge_silverstone_tour_%03d.png"
                                               : (captureInterlagosTour ? "formula_forge_interlagos_tour_%03d.png"
                                                                        : "formula_forge_section_tour_%02d.png"))),
                           static_cast<int>(i));
            game.render(60.0f, true, path.string().c_str());
        }
        cleanupRuntime();
        return 0;
    }
    if (captureDrivenLap) {
        if (captureSpaLap) {
            game.selectMapForCapture(0);
        }
        game.startRace();
        const float startScore = game.playerRaceScoreForCapture();
        const float lapLength = game.lapLengthForCapture();
        static constexpr std::array<float, 10> kLapMilestones = {0.03f, 0.12f, 0.22f, 0.32f, 0.42f,
                                                                 0.52f, 0.62f, 0.72f, 0.84f, 0.96f};
        size_t nextCapture = 0;
        int simFrames = 0;
        float distance = 0.0f;
        const int maxFrames = static_cast<int>(1000.0f / kFixedDt);
        while ((nextCapture < kLapMilestones.size() || distance < lapLength) && simFrames < maxFrames) {
            const Input3D input = game.scriptedInput();
            game.update(kFixedDt, input, true);
            ++simFrames;
            distance = game.playerRaceScoreForCapture() - startScore;
            if (nextCapture < kLapMilestones.size() && distance >= lapLength * kLapMilestones[nextCapture]) {
                const std::filesystem::path path = std::filesystem::path("../playtest_frames") /
                                                   TextFormat("formula_forge_driven_lap_%02d.png",
                                                              static_cast<int>(nextCapture));
                game.render(60.0f, true, path.string().c_str());
                ++nextCapture;
            }
        }
        cleanupRuntime();
        std::cout << "capture-driven-lap frames=" << simFrames << " captures=" << nextCapture
                  << " distance=" << distance << " lap_length=" << lapLength << "\n";
        return nextCapture == kLapMilestones.size() && distance >= lapLength ? 0 : 1;
    }

    double previous = GetTime();
    double accumulator = 0.0;
    Input3D pendingEdges{};
    int frames = 0;
    double diagnosticStamp = GetTime();
    std::vector<float> frameTimesMs;
    if (perfAudit) {
        frameTimesMs.reserve(520);
    }

    while (!WindowShouldClose()) {
        const double frameBegin = GetTime();
        const double now = GetTime();
        accumulator += std::min(0.10, now - previous);
        previous = now;

        const Input3D sampledInput = capturePlaytest ? game.scriptedInput() : readInput(controller);
        if (sampledInput.quit) {
            break;
        }
        pendingEdges.a = pendingEdges.a || sampledInput.a;
        pendingEdges.b = pendingEdges.b || sampledInput.b;
        pendingEdges.start = pendingEdges.start || sampledInput.start;
        pendingEdges.back = pendingEdges.back || sampledInput.back;
        pendingEdges.left = pendingEdges.left || sampledInput.left;
        pendingEdges.right = pendingEdges.right || sampledInput.right;
        pendingEdges.up = pendingEdges.up || sampledInput.up;
        pendingEdges.down = pendingEdges.down || sampledInput.down;
        pendingEdges.pageLeft = pendingEdges.pageLeft || sampledInput.pageLeft;
        pendingEdges.pageRight = pendingEdges.pageRight || sampledInput.pageRight;
        pendingEdges.triggerLeft = pendingEdges.triggerLeft || sampledInput.triggerLeft;
        pendingEdges.triggerRight = pendingEdges.triggerRight || sampledInput.triggerRight;
        pendingEdges.shiftDown = pendingEdges.shiftDown || sampledInput.shiftDown;
        pendingEdges.shiftUp = pendingEdges.shiftUp || sampledInput.shiftUp;
        Input3D input = sampledInput;
        input.a = pendingEdges.a;
        input.b = pendingEdges.b;
        input.start = pendingEdges.start;
        input.back = pendingEdges.back;
        input.left = pendingEdges.left;
        input.right = pendingEdges.right;
        input.up = pendingEdges.up;
        input.down = pendingEdges.down;
        input.pageLeft = pendingEdges.pageLeft;
        input.pageRight = pendingEdges.pageRight;
        input.triggerLeft = pendingEdges.triggerLeft;
        input.triggerRight = pendingEdges.triggerRight;
        input.shiftDown = pendingEdges.shiftDown;
        input.shiftUp = pendingEdges.shiftUp;
        const bool hasController = capturePlaytest || controller.available();
        while (accumulator >= kFixedDt) {
            game.update(kFixedDt, input, hasController);
            pendingEdges = {};
            input.a = false;
            input.b = false;
            input.start = false;
            input.back = false;
            input.left = false;
            input.right = false;
            input.up = false;
            input.down = false;
            input.pageLeft = false;
            input.pageRight = false;
            input.triggerLeft = false;
            input.triggerRight = false;
            input.shiftDown = false;
            input.shiftUp = false;
            accumulator -= kFixedDt;
        }
        std::string frameCapturePath;
        if (capturePlaytest) {
            const char* captureName = frames == 20  ? "formula_forge_loading.png"
                                      : frames == 65  ? "formula_forge_mode.png"
                                      : frames == 110 ? "formula_forge_car.png"
                                      : frames == 200 ? "formula_forge_map.png"
                                      : frames == 335 ? "formula_forge_race.png"
                                      : frames == 380 ? "formula_forge_pause.png"
                                      : frames == 425 ? "formula_forge_results.png"
                                                      : nullptr;
            if (captureName) {
                frameCapturePath = (std::filesystem::path("../playtest_frames") / captureName).string();
            }
        }
        game.render(static_cast<float>(GetFPS()), hasController, frameCapturePath.empty() ? nullptr : frameCapturePath.c_str(),
                    static_cast<float>(accumulator / kFixedDt));

        if (capturePlaytest) {
            if (frames == 20) {
                Input3D confirm;
                confirm.a = true;
                game.update(kFixedDt, confirm, true);
            } else if (frames == 65) {
                Input3D confirm;
                confirm.a = true;
                game.update(kFixedDt, confirm, true);
            } else if (frames == 110) {
                Input3D confirm;
                confirm.a = true;
                game.update(kFixedDt, confirm, true);
            } else if (frames == 155) {
                Input3D nextMap;
                nextMap.right = true;
                game.update(kFixedDt, nextMap, true);
            } else if (frames == 175) {
                Input3D moreLaps;
                moreLaps.down = true;
                game.update(kFixedDt, moreLaps, true);
            } else if (frames == 200) {
                Input3D confirm;
                confirm.a = true;
                game.update(kFixedDt, confirm, true);
            } else if (frames == 335) {
                Input3D pause;
                pause.start = true;
                game.update(kFixedDt, pause, true);
            } else if (frames == 380) {
                game.showResultsCapture();
            }
        }

        if (diagnoseController && now - diagnosticStamp > 0.25) {
            controller.printSnapshot();
            diagnosticStamp = now;
        }
        if (perfAudit && frames > 30) {
            frameTimesMs.push_back(static_cast<float>((GetTime() - frameBegin) * 1000.0));
        }
        ++frames;
        if ((smokeRender && frames > 180) || (capturePlaytest && frames > 540) || (diagnoseController && frames > 900) ||
            (perfAudit && frames > 520)) {
            break;
        }
    }

    cleanupRuntime();
    if (perfAudit) {
        std::sort(frameTimesMs.begin(), frameTimesMs.end());
        const auto percentile = [&](float p) {
            if (frameTimesMs.empty()) {
                return 0.0f;
            }
            const size_t index = std::min(frameTimesMs.size() - 1, static_cast<size_t>(p * static_cast<float>(frameTimesMs.size() - 1)));
            return frameTimesMs[index];
        };
        const float p50 = percentile(0.50f);
        const float p95 = percentile(0.95f);
        const float maxFrame = frameTimesMs.empty() ? 0.0f : frameTimesMs.back();
        const bool ok = p95 <= 19.2f && maxFrame <= 34.0f;
        std::cout << "perf-audit frames=" << frameTimesMs.size() << " p50_ms=" << p50 << " p95_ms=" << p95 << " max_ms=" << maxFrame
                  << " ok=" << ok << "\n";
        return ok ? 0 : 1;
    }
    return 0;
}
