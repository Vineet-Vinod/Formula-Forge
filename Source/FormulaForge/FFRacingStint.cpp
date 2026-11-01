#include "FFRacingStint.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <ostream>

namespace {
constexpr float Units = 17.0f;
constexpr float LapLength = 5891.0f;
constexpr float FixedStep = 1.0f / 120.0f;
}

double FFRacingEvaluation::Score() const {
    return valid ? lapSeconds[1] : 1000000.0 + 3.0 * LapLength - distanceMetres;
}

bool FFRacingLineMatchesTrack(const FFRacingLine& line, const FFSimulation& simulation) {
    if (std::abs(line.LapLength() - LapLength) > 0.01f || line.Nodes().empty()) return false;
    for (std::size_t index = 0; index < line.Nodes().size(); ++index) {
        const auto& node = line.Nodes()[index];
        const auto sample = simulation.Sample(index * line.LapLength() / line.Nodes().size());
        if (length(node.track.centreMetres - sample.position / Units) > 0.05f ||
            dot(node.track.tangent, sample.tangent) < 0.999f) return false;
    }
    return true;
}

void FFRacingStint::Reset(FFSimulation& simulation) {
    simulation.trial = {};
    simulation.Reset(0.01f);
    validation = {};
    validation.Reset(0.01f);
    validation.running = true;
    result = {};
    previousStation = 0.01f;
    previousProgress = 0.0f;
    stalledSteps = 0;
    steps = 0;
}

void FFRacingStint::WriteTelemetryHeader(std::ostream& output) {
    output << "time_s,lap,station_m,x_m,y_m,speed_kph,target_kph,lane_m,tracking_error_m,steer,throttle,brake,gear,on_track,contact,lap_invalid\n";
}

bool FFRacingStint::Step(FFSimulation& simulation, const FFRacingLine& line, float pace, std::ostream* telemetry) {
    if (result.valid || !result.failure.empty()) return false;
    const auto projection = simulation.Project(simulation.vehicle.pos);
    const auto control = line.Control(simulation.vehicle, simulation.tuning, projection.station, Units, pace);
    simulation.Step(control, FixedStep);
    return Observe(simulation, line, control, pace, telemetry);
}

bool FFRacingStint::Observe(FFSimulation& simulation, const FFRacingLine& line,
    const ArcadeVehicleControl& control, float pace, std::ostream* telemetry) {
    if (result.valid || !result.failure.empty()) return false;
    result.simulatedSeconds += FixedStep;
    const float station = simulation.ProgressStation();
    float movement = station - previousStation;
    if (movement < -LapLength * 0.5f) movement += LapLength;
    if (movement > LapLength * 0.5f) movement -= LapLength;
    result.distanceMetres += movement;
    previousStation = station;
    const bool onTrack = simulation.OnTrack();
    validation.Step(station, onTrack, simulation.barrierContact, FixedStep);
    const float trackingError = length(simulation.vehicle.pos / Units - line.Position(station));
    result.maximumTrackingError = std::max(result.maximumTrackingError, trackingError);
    if (telemetry && steps % 4 == 0) {
        *telemetry << std::setprecision(9) << result.simulatedSeconds << ',' << result.completedLaps << ',' << station << ','
            << simulation.vehicle.pos.x / Units << ',' << simulation.vehicle.pos.y / Units << ','
            << simulation.vehicle.forwardSpeed * 3.6f / Units << ',' << line.Speed(station) * pace * 3.6f << ','
            << simulation.Project(simulation.vehicle.pos).lane / Units << ',' << trackingError << ',' << control.steer << ',' << control.throttle << ','
            << control.brake << ',' << simulation.vehicle.gear << ',' << onTrack << ',' << simulation.barrierContact << ','
            << simulation.trial.invalid << '\n';
    }
    if (validation.completedLaps > result.completedLaps) {
        result.lapSeconds[result.completedLaps] = validation.lastSeconds;
        result.completedLaps = validation.completedLaps;
        if (!validation.lastValid) result.failure = "invalid_lap";
        if (result.completedLaps >= 2 && (!simulation.trial.lastValid ||
            std::abs(simulation.trial.lastSeconds - validation.lastSeconds) > 0.0001)) {
            result.failure = "native_lap_validation_mismatch";
        }
        if (result.completedLaps == 3 && result.failure.empty()) {
            result.valid = true;
            return false;
        }
    }
    if (!onTrack) result.failure = "track_limits";
    else if (simulation.barrierContact) result.failure = "barrier_contact";
    else if (simulation.PitOverspeed()) result.failure = "pit_overspeed";
    else if (validation.invalid) result.failure = "invalid_progress";
    else if (!std::isfinite(simulation.vehicle.pos.x) || !std::isfinite(simulation.vehicle.pos.y)) result.failure = "nonfinite_state";
    if (!result.failure.empty()) {
        result.failureStation = station;
        return false;
    }
    if (result.distanceMetres - previousProgress > 0.25f) {
        stalledSteps = 0;
        previousProgress = result.distanceMetres;
    } else if (++stalledSteps > 120 * 10) {
        result.failure = "stalled";
    }
    if (++steps >= 120 * 900) result.failure = "timeout";
    if (!result.failure.empty()) result.failureStation = station;
    return result.failure.empty();
}

const FFRacingEvaluation& FFRacingStint::Result() const {
    return result;
}
