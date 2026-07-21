#pragma once

#include <cstddef>
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
    std::span<const TrackBankPoint> bankProfile;
    std::span<const TrackRunoffZone> runoffProfile;
    std::span<const TrackGradeSeparation> gradeSeparations;
};

std::span<const TrackCatalogEntry> trackCatalog() noexcept;
const TrackCatalogEntry* findTrackCatalogEntry(CatalogCircuitId id) noexcept;

float sampleTrackElevationMeters(const TrackCatalogEntry& track, float distanceMeters) noexcept;
float sampleTrackWidthMeters(const TrackCatalogEntry& track, float distanceMeters) noexcept;
float sampleTrackBankDegrees(const TrackCatalogEntry& track, float distanceMeters) noexcept;

enum class TrackTurnDirection : int {
    Right = -1,
    Left = 1,
};

struct TrackTurnExpectation {
    std::string_view landmark;
    float lapFraction = 0.0f;
    TrackTurnDirection direction = TrackTurnDirection::Right;
};

struct TrackShapeAuditResult {
    float aspectRatio = 0.0f;
    float signedArea = 0.0f;
    int selfIntersections = 0;
    std::size_t landmarkChecks = 0;
    std::size_t landmarkFailures = 0;
    bool aspectMatches = false;
    bool directionMatches = false;
    bool intersectionsMatch = false;

    [[nodiscard]] bool ok() const noexcept {
        return aspectMatches && directionMatches && intersectionsMatch && landmarkFailures == 0;
    }
};

std::span<const TrackTurnExpectation> trackTurnExpectations(CatalogCircuitId id) noexcept;
TrackShapeAuditResult auditTrackCatalogShape(const TrackCatalogEntry& track) noexcept;
