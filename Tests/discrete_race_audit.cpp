#include "FFDiscreteRace.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <numeric>
#include <string>

namespace {
bool Require(bool condition, const char* message) {
    if (!condition) std::cerr << message << '\n';
    return condition;
}
}

int main() {
    FFSimulation simulation;
    FFDiscreteRaceConfig config;
    config.trajectories = 100;
    config.cars = 4;
    FFDiscreteRace race;
    std::string error;
    if (!race.Initialize(simulation, config, error)) { std::cerr << error << '\n'; return 1; }
    bool passed = Require(race.Solver().converged && race.Solver().residual <= config.tolerance,
        "Value iteration failed its residual criterion.");
    passed &= Require(race.Lines().size() == 100 && race.Solver().minimumSeparation >= 0.30f,
        "Expected 100 distinct trajectories.");
    passed &= Require(race.Solver().slowestLap <= race.Solver().fastestLap * 1.3f,
        "Trajectory speed filter failed.");
    for (const auto& line : race.Lines()) {
        for (const auto& node : line.Nodes()) {
            passed &= Require(std::isfinite(node.speedMetresPerSecond) && node.speedMetresPerSecond > 0.0f &&
                node.offsetMetres <= node.track.leftMetres + 0.001f &&
                node.offsetMetres >= -node.track.rightMetres - 0.001f, "Invalid speed or corridor position.");
        }
    }
    // Check the minimum separation independently, across every pair.
    for (int first = 0; first < 100; ++first) {
        for (int second = first + 1; second < 100; ++second) {
            float squared = 0.0f;
            for (int sample = 0; sample < config.samples; ++sample) {
                const float difference = race.Lines()[first].Nodes()[sample].offsetMetres -
                    race.Lines()[second].Nodes()[sample].offsetMetres;
                squared += difference * difference;
            }
            passed &= Require(std::sqrt(squared / config.samples) >= 0.30f, "Duplicate trajectory pair.");
        }
    }
    FFRaceCar transition = race.Cars()[0];
    transition.speed = 10.0f;
    const Vec2 start = transition.position;
    const int target = (transition.trajectory + 1) % 100;
    passed &= Require(race.Transition(transition, target), "Low-speed line switch should be feasible.");
    passed &= Require(length(race.Position(transition, transition.station) - start) < 0.0001f,
        "Switch teleports the car at its start.");
    const float end = transition.transitionStart + transition.transitionLength;
    FFRaceCar targetCar;
    targetCar.trajectory = target;
    targetCar.target = target;
    passed &= Require(length(race.Position(transition, end) - race.Position(targetCar, end)) < 0.001f,
        "Switch does not reach its target.");
    passed &= Require(std::abs(FFDiscreteRace::Blend(0.001f)) < 0.000001f &&
        std::abs(1.0f - FFDiscreteRace::Blend(0.999f)) < 0.000001f, "Switch endpoints are not smooth.");
    FFRaceCar overspeed = race.Cars()[0];
    overspeed.speed = 200.0f;
    passed &= Require(!race.Transition(overspeed, target), "Unreachable switch accepted at excessive speed.");
    FFRaceBelief belief;
    race.UpdateBelief(belief, {}, 0.2f);
    passed &= Require(!belief.initialized, "Unseen opponent leaked into the belief.");
    const float station = simulation.trial.startStation + 700.0f;
    race.UpdateBelief(belief, {true, station, 45.0f, race.Lane(15, station)}, 0.2f);
    const float entropyBefore = std::accumulate(belief.trajectories.begin(), belief.trajectories.end(), 0.0f,
        [](float sum, float p) { return sum - p * std::log(std::max(p, 0.0000001f)); });
    const float variance = belief.stationVariance;
    race.UpdateBelief(belief, {}, 2.0f);
    const float entropyAfter = std::accumulate(belief.trajectories.begin(), belief.trajectories.end(), 0.0f,
        [](float sum, float p) { return sum - p * std::log(std::max(p, 0.0000001f)); });
    passed &= Require(std::abs(std::accumulate(belief.trajectories.begin(), belief.trajectories.end(), 0.0f) - 1.0f) < 0.00001f &&
        entropyAfter > entropyBefore && belief.stationVariance > variance &&
        std::abs(belief.station - station - 90.0f) < 0.01f, "Missing-observation prediction did not broaden/advance the belief.");
    for (int step = 0; step < 120 * 5; ++step) race.Step(1.0f / 120.0f);
    passed &= Require(race.Stats().maximumLateralRatio <= 1.0f, "Motion exceeded the lateral grip limit.");
    for (const auto& car : race.Cars()) {
        passed &= Require(std::isfinite(car.station) && std::isfinite(car.speed) && car.speed >= 0.0f &&
            std::isfinite(car.position.x) && std::isfinite(car.position.y), "Nonfinite fleet state.");
    }
    config.maximumIterations = 1;
    config.tolerance = 0.0000001f;
    FFDiscreteRace unconverged;
    config.trajectories = 4;
    config.samples = 128;
    passed &= Require(!unconverged.Initialize(simulation, config, error) && !unconverged.Solver().converged,
        "Iteration cap silently accepted an unconverged solution.");
    config.tolerance = std::numeric_limits<float>::quiet_NaN();
    passed &= Require(!unconverged.Initialize(simulation, config, error), "NaN configuration accepted.");
    std::cout << "Discrete racing audit: " << (passed ? "PASS" : "FAIL") << '\n';
    return passed ? 0 : 1;
}
