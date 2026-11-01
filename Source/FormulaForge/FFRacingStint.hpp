#pragma once

#include "FFRacingLine.hpp"
#include "FFSimulation.hpp"

#include <array>
#include <iosfwd>
#include <string>

struct FFRacingEvaluation {
    bool valid = false;
    std::array<double, 3> lapSeconds{};
    double simulatedSeconds = 0.0;
    float distanceMetres = 0.0f;
    float failureStation = 0.0f;
    float maximumTrackingError = 0.0f;
    int completedLaps = 0;
    std::string failure;
    double Score() const;
};

bool FFRacingLineMatchesTrack(const FFRacingLine& line, const FFSimulation& simulation);

class FFRacingStint {
public:
    void Reset(FFSimulation& simulation);
    bool Step(FFSimulation& simulation, const FFRacingLine& line, float pace,
        std::ostream* telemetry = nullptr);
    bool Observe(FFSimulation& simulation, const FFRacingLine& line,
        const ArcadeVehicleControl& control, float pace, std::ostream* telemetry = nullptr);
    const FFRacingEvaluation& Result() const;
    static void WriteTelemetryHeader(std::ostream& output);
private:
    FFTrialState validation;
    FFRacingEvaluation result;
    float previousStation = 0.01f;
    float previousProgress = 0.0f;
    int stalledSteps = 0;
    int steps = 0;
};
