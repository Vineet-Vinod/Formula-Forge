#pragma once

#include <cstddef>
#include <span>
#include <string_view>

#include "track_types.hpp"

// Immutable, renderer-independent source data for the real-world-inspired
// circuits. Centerlines are hand-authored plan-view controls and are normalized
// to targetLengthMeters by Track3D; elevation and width stations are in meters.
struct TrackWidthPoint {
    float distanceMeters = 0.0f;
    float roadWidthMeters = 12.0f;
};

struct TrackGradeSeparation {
    float firstDistanceMeters = 0.0f;
    float secondDistanceMeters = 0.0f;
    float minimumVerticalClearanceMeters = 0.0f;
};

// Distance from the outside of the kerb to the wall. Left is the driver's left.
struct TrackShoulderPoint {
    float distanceMeters = 0.0f;
    float leftMeters = 8.0f;
    float rightMeters = 8.0f;
};

struct TrackCatalogEntry {
    TrackLayoutId id{};
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
    float centerlineScale = 1.0f;
    bool mirrorCenterlineY = true;
    std::span<const TrackControlPoint> centerline;
    std::span<const TrackElevationPoint> elevationProfile;
    std::span<const TrackWidthPoint> widthProfile;
    std::span<const TrackBankPoint> bankProfile;
    std::span<const TrackRunoffZone> runoffProfile;
    std::span<const TrackGradeSeparation> gradeSeparations;
    std::string_view slug;
    std::string_view contentDir;
    std::string_view mapPath;
    float referenceAspect = 0.0f;
    int referenceCrossings = 0;
    bool generated = false;
    bool headingDirection = false;
    bool deckSeparation = false;
    float shoulderMeters = 8.0f;
    std::span<const TrackShoulderPoint> shoulders{};
};

std::span<const TrackCatalogEntry> trackCatalog() noexcept;
const TrackCatalogEntry* findTrackCatalogEntry(TrackLayoutId id) noexcept;

const TrackCatalogEntry* findTrackCatalogEntry(std::string_view slug) noexcept;
float sampleTrackElevationMeters(const TrackCatalogEntry& track, float distanceMeters) noexcept;
float sampleTrackWidthMeters(const TrackCatalogEntry& track, float distanceMeters) noexcept;
float sampleTrackBankDegrees(const TrackCatalogEntry& track, float distanceMeters) noexcept;
float sampleTrackShoulderMeters(const TrackCatalogEntry& track, float distanceMeters, bool left) noexcept;

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

std::span<const TrackTurnExpectation> trackTurnExpectations(TrackLayoutId id) noexcept;
TrackShapeAuditResult auditTrackCatalogShape(const TrackCatalogEntry& track) noexcept;
