#pragma once

#include "FFRacingLine.hpp"
#include "FFSimulation.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

struct FFDiscreteRaceConfig {
    int trajectories = 100;
    int samples = 512;
    int cars = 12;
    int maximumIterations = 1200;
    float tolerance = 0.01f;
    float observationRange = 160.0f;
    float dropout = 0.12f;
    std::uint32_t seed = 7;
    bool planning = true;
    bool synchronized = false;
};

struct FFRaceCar {
    int trajectory = 0;
    int target = 0;
    float station = 0.0f;
    float speed = 0.0f;
    float transitionStart = 0.0f;
    float transitionLength = 0.0f;
    float pace = 1.0f;
    Vec2 position;
    float heading = 0.0f;
};

struct FFRaceObservation {
    bool visible = false;
    float station = 0.0f;
    float speed = 0.0f;
    float lane = 0.0f;
};

struct FFRaceBelief {
    std::vector<float> trajectories;
    float station = 0.0f;
    float speed = 0.0f;
    float stationVariance = 1.0f;
    float lane = 0.0f;
    float lateralSpeed = 0.0f;
    float age = 0.0f;
    bool initialized = false;
};

struct FFRaceSolverStats {
    int iterations = 0;
    float residual = 0.0f;
    bool converged = false;
    float minimumSeparation = 0.0f;
    float fastestLap = 0.0f;
    float slowestLap = 0.0f;
    std::size_t bytes = 0;
};

struct FFRaceStats {
    int switches = 0;
    int passes = 0;
    int cornerPasses = 0;
    int cleanPasses = 0;
    int cleanCornerPasses = 0;
    int overlapEpisodes = 0;
    int observed = 0;
    int missed = 0;
    float maximumLateralRatio = 0.0f;
    float minimumClearance = 10000.0f;
    double decisionMilliseconds = 0.0;
    std::uint64_t decisions = 0;
};

struct FFRaceEdge {
    int target = 0;
    float seconds = 0.0f;
    float cost = 0.0f;
    float discount = 0.0f;
};

class FFDiscreteRace {
public:
    bool Initialize(const FFSimulation& simulation, const FFDiscreteRaceConfig& config,
        std::string& error);
    void Step(float seconds);
    void DecideAll();
    Vec2 Position(const FFRaceCar& car, float station) const;
    float Lane(int trajectory, float station) const;
    float Value(int trajectory, float station) const;
    float LateralLimit(float speed) const;
    bool Transition(FFRaceCar& car, int target) const;
    void UpdateBelief(FFRaceBelief& belief, const FFRaceObservation& observation, float seconds) const;
    const std::vector<FFRacingLine>& Lines() const;
    const std::vector<FFRaceCar>& Cars() const;
    const FFRaceBelief& Belief(int observer, int opponent) const;
    const FFRaceSolverStats& Solver() const;
    const FFRaceStats& Stats() const;
    float LapLength() const;
    static float Blend(float fraction);
private:
    bool Generate(const FFSimulation& simulation, std::string& error);
    void Solve();
    void Observe(int observer);
    void Decide(int observer);
    void Move(FFRaceCar& car, float seconds, float followingSpeed = 200.0f) const;
    float SpeedLimit(const FFRaceCar& car, float station) const;
    float Risk(int observer, Vec2 position, float station, float future) const;
    float FollowingSpeed(int observer) const;
    float Random();
    float Metric(const FFRaceCar& car, float station) const;
    Vec2 LinePosition(int line, float station) const;
    void RebuildSpeeds(int line);
    std::size_t Index(int line, int sample) const;
    FFDiscreteRaceConfig config;
    ArcadeVehicleConfig tuning;
    float lapLength = 0.0f;
    float elapsed = 0.0f;
    float acceleration = 0.0f;
    float braking = 0.0f;
    std::uint32_t randomState = 1;
    std::vector<FFRacingLine> lines;
    std::vector<FFRaceCar> cars;
    std::vector<FFRaceBelief> beliefs;
    std::vector<float> values;
    std::vector<std::array<FFRaceEdge, 9>> edges;
    std::vector<float> nextDecision;
    std::vector<float> beliefUpdateTime;
    std::vector<bool> overlaps;
    std::vector<bool> passContact;
    std::vector<int> ordering;
    FFRaceSolverStats solver;
    FFRaceStats stats;
};
