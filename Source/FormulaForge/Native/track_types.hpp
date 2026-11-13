#pragma once

#include <cstdint>

inline constexpr float kTrackSimulationUnitsPerMeter = 17.0f;

struct TrackControlPoint {
    float x = 0.0f;
    float y = 0.0f;
};

enum class TrackLayoutId {
    Silverstone = 2,
    Monza = 3,
    Interlagos = 4,
    Bahrain = 5,
    Jeddah = 6,
    Australia = 7,
    Japan = 8,
    China = 9,
    Canada = 10,
    Monaco = 11,
    Austria = 12,
    Spa = 13,
    Zandvoort = 14,
    Baku = 15,
    Malaysia = 16,
    Singapore = 17,
    Cota = 18,
    LasVegas = 19,
    Turkey = 20,
    Portimao = 21,
    Buddh = 22,
    Hanoi = 23,
    Hockenheim = 24,
};

struct TrackElevationPoint {
    float distanceMeters = 0.0f;
    float elevationMeters = 0.0f;
};

// Positive crossfall raises the native positive-lane edge. Source exports
// map that direction to driver RIGHT in east/north coordinates.
struct TrackBankPoint {
    float distanceMeters = 0.0f;
    float angleDegrees = 0.0f;
    float quadraticPerMeter = 0.0f;
    float edgeFadeMeters = 0.0f;
    float positiveOuterSlope = 0.0f;
    float negativeOuterSlope = 0.0f;
};

enum class TrackRunoffSurface : std::uint8_t {
    Asphalt,
    Gravel,
    Grass,
};

// Side uses the native lane sign: -1 negative, 0 both, +1 positive.
struct TrackRunoffZone {
    float startMeters = 0.0f;
    float endMeters = 0.0f;
    std::int8_t side = 0;
    TrackRunoffSurface surface = TrackRunoffSurface::Grass;
    float widthMeters = 0.0f;
};
