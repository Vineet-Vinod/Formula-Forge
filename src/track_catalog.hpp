#pragma once

#include <span>
#include <string_view>

#include "track_layout.hpp"

// Immutable, renderer-independent source data for the real-world-inspired
// circuits. Centerlines are hand-authored plan-view controls and are normalized
// to targetLengthMeters by Track3D; elevation and width stations are in meters.
enum class CatalogCircuitId {
    Suzuka,
    Silverstone,
    Monza,
    Interlagos,
};

struct TrackWidthPoint {
    float distanceMeters = 0.0f;
    float roadWidthMeters = 12.0f;
};

struct TrackGradeSeparation {
    float firstDistanceMeters = 0.0f;
    float secondDistanceMeters = 0.0f;
    float minimumVerticalClearanceMeters = 0.0f;
};

struct TrackCatalogEntry {
    CatalogCircuitId id{};
    std::string_view displayName;
    std::string_view venueName;
    std::string_view country;
    std::string_view description;
    std::string_view environmentTag;
    float targetLengthMeters = 0.0f;
    int turnCount = 0;
    float startPhase = 0.0f;
    float nominalElevationReliefMeters = 0.0f;
    bool clockwise = true;
    std::span<const TrackControlPoint> centerline;
    std::span<const TrackElevationPoint> elevationProfile;
    std::span<const TrackWidthPoint> widthProfile;
    std::span<const TrackGradeSeparation> gradeSeparations;
};

std::span<const TrackCatalogEntry> trackCatalog() noexcept;
const TrackCatalogEntry* findTrackCatalogEntry(CatalogCircuitId id) noexcept;

float sampleTrackElevationMeters(const TrackCatalogEntry& track, float distanceMeters) noexcept;
float sampleTrackWidthMeters(const TrackCatalogEntry& track, float distanceMeters) noexcept;
