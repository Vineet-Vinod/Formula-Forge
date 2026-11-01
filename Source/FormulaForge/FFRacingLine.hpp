#pragma once

#include "arcade_vehicle.hpp"

#include <cstddef>
#include <istream>
#include <ostream>
#include <span>
#include <vector>

struct FFRacingTrackSample {
    Vec2 centreMetres;
    Vec2 tangent;
    float leftMetres = 5.0f;
    float rightMetres = 5.0f;
};

struct FFRacingNode {
    FFRacingTrackSample track;
    float offsetMetres = 0.0f;
    float speedScale = 1.0f;
    float surfaceGrip = 1.0f;
    Vec2 positionMetres;
    float curvature = 0.0f;
    float speedMetresPerSecond = 0.0f;
};

struct FFRacingControllerConfig {
    float lookaheadMetres = 6.0f;
    float lookaheadSeconds = 0.30f;
    float predictionSeconds = 0.06f;
    float speedGain = 2.0f;
    float lateralSafety = 0.82f;
    float brakingSafety = 0.65f;
    float accelerationFeedforward = 1.0f;
};

class FFRacingLine {
public:
    bool Initialize(std::span<const FFRacingTrackSample> samples, float lapLengthMetres);
    void MinimizeCurvature(int sweeps = 600, float distanceWeight = 0.0f);
    void Rebuild(const ArcadeVehicleConfig& tuning, float unitsPerMetre);
    ArcadeVehicleControl Control(const ArcadeVehicleState& vehicle,
        const ArcadeVehicleConfig& tuning, float stationMetres, float unitsPerMetre,
        float pace = 1.0f) const;
    Vec2 Position(float stationMetres) const;
    float Speed(float stationMetres) const;
    bool Load(std::istream& input);
    bool Save(std::ostream& output) const;
    float LapLength() const;
    std::vector<FFRacingNode>& Nodes();
    const std::vector<FFRacingNode>& Nodes() const;
    FFRacingControllerConfig controller;
private:
    float LocalCost(std::size_t index, float distanceWeight) const;
    float Curvature(std::size_t index) const;
    void UpdatePosition(std::size_t index);
    float lapLength = 0.0f;
    std::vector<FFRacingNode> nodes;
};
