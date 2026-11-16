#include "FFDiscreteRace.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <functional>
#include <limits>
#include <numeric>
#include <utility>

namespace {
constexpr float Units = 17.0f;
constexpr int Stride = 8;
constexpr float DecisionSeconds = 0.2f;
constexpr float DiscountSeconds = 12.0f;

float RadicalInverse(int value, int base) {
    float result = 0.0f;
    float factor = 1.0f / base;
    while (value > 0) {
        result += (value % base) * factor;
        value /= base;
        factor /= base;
    }
    return result;
}

float SignedDistance(float first, float second, float lap) {
    return wrapDistance(first - second + lap * 0.5f, lap) - lap * 0.5f;
}

float Curvature(Vec2 first, Vec2 middle, Vec2 last) {
    const Vec2 before = middle - first;
    const Vec2 after = last - middle;
    return 2.0f * std::abs(cross(before, after)) /
        std::max(0.001f, length(before) * length(after) * length(last - first));
}

float LapSeconds(const FFRacingLine& line) {
    float seconds = 0.0f;
    const auto& nodes = line.Nodes();
    for (std::size_t index = 0; index < nodes.size(); ++index) {
        const auto& next = nodes[(index + 1) % nodes.size()];
        seconds += 2.0f * length(next.positionMetres - nodes[index].positionMetres) /
            (next.speedMetresPerSecond + nodes[index].speedMetresPerSecond);
    }
    return seconds;
}
}

bool FFDiscreteRace::Initialize(const FFSimulation& simulation,
    const FFDiscreteRaceConfig& requested, std::string& error) {
    if (requested.trajectories < 4 || requested.trajectories > 256 ||
        requested.samples < 128 || requested.samples > 1024 || requested.samples % Stride != 0 ||
        requested.cars < 2 || requested.cars > 24 || requested.maximumIterations < 1 ||
        requested.maximumIterations > 5000 || !std::isfinite(requested.tolerance) ||
        requested.tolerance <= 0.0f || !std::isfinite(requested.observationRange) ||
        requested.observationRange < 10.0f || requested.observationRange > 500.0f ||
        !std::isfinite(requested.dropout) || requested.dropout < 0.0f || requested.dropout > 1.0f) {
        error = "Expected 4..256 lines, 128..1024 samples divisible by 8, 2..24 cars, valid sensor/solver limits.";
        return false;
    }
    *this = FFDiscreteRace{};
    config = requested;
    randomState = config.seed == 0 ? 1 : config.seed;
    tuning = simulation.tuning;
    lapLength = simulation.lapLength;
    acceleration = tuning.engineAcceleration / Units * 0.7f;
    braking = tuning.brakeDeceleration / Units * tuning.brakeLowSpeedScale * 0.6f;
    if (!Generate(simulation, error)) return false;
    Solve();
    if (!solver.converged) {
        error = "Value iteration reached its iteration cap before the requested Bellman residual.";
        return false;
    }
    cars.resize(config.cars);
    nextDecision.resize(config.cars);
    beliefUpdateTime.resize(config.cars, 0.0f);
    beliefs.resize(config.cars * config.cars);
    overlaps.resize(config.cars * config.cars, false);
    passContact.resize(config.cars * config.cars, false);
    ordering.resize(config.cars * config.cars, 0);
    for (int index = 0; index < config.cars; ++index) {
        auto& car = cars[index];
        car.station = simulation.trial.startStation + 300.0f - index * 18.0f;
        int best = 0;
        float difference = std::numeric_limits<float>::max();
        const float preferredLane = index % 2 == 0 ? -2.0f : 2.0f;
        for (int line = 0; line < config.trajectories; ++line) {
            const float distance = std::abs(Lane(line, car.station) - preferredLane);
            if (distance < difference) {
                best = line;
                difference = distance;
            }
        }
        car.trajectory = best;
        car.target = best;
        car.pace = 0.85f + 0.15f * RadicalInverse(index + 1, 2);
        car.speed = std::min(25.0f, lines[best].Speed(car.station) * car.pace * 0.8f);
        car.position = Position(car, car.station);
        car.heading = angleOf(Position(car, car.station + 1.0f) - car.position);
        nextDecision[index] = config.synchronized ? 0.0f : index * DecisionSeconds / config.cars;
    }
    for (auto& belief : beliefs) belief.trajectories.assign(config.trajectories, 1.0f / config.trajectories);
    solver.bytes = values.capacity() * sizeof(float) + edges.capacity() * sizeof(edges[0]) +
        cars.capacity() * sizeof(FFRaceCar) + beliefs.capacity() * sizeof(FFRaceBelief);
    for (const auto& line : lines) solver.bytes += line.Nodes().capacity() * sizeof(FFRacingNode);
    for (const auto& belief : beliefs) solver.bytes += belief.trajectories.capacity() * sizeof(float);
    return true;
}

bool FFDiscreteRace::Generate(const FFSimulation& simulation, std::string& error) {
    std::vector<FFRacingTrackSample> samples;
    samples.reserve(config.samples);
    for (int index = 0; index < config.samples; ++index) {
        const auto road = simulation.Sample(index * lapLength / config.samples);
        const float width = road.halfWidth - 1.8f;
        if (width < 1.0f) {
            error = "Track too narrow for the 1.8 m centre-to-edge margin.";
            return false;
        }
        samples.push_back({road.position / Units, road.tangent, width, width});
    }
    FFRacingLine base;
    if (!base.Initialize(samples, lapLength)) {
        error = "Invalid circuit samples.";
        return false;
    }
    base.MinimizeCurvature(300);
    base.Rebuild(tuning, Units);
    lines.reserve(config.trajectories);
    lines.push_back(base);
    solver.minimumSeparation = std::numeric_limits<float>::max();
    const float baseLap = LapSeconds(base);
    for (int attempt = 1; attempt < 12000 && static_cast<int>(lines.size()) < config.trajectories; ++attempt) {
        FFRacingLine line = base;
        const float bias = 2.0f * RadicalInverse(attempt, 2) - 1.0f;
        const float phase = 2.0f * kPi * RadicalInverse(attempt, 3);
        const float phase2 = 2.0f * kPi * RadicalInverse(attempt, 5);
        for (int index = 0; index < config.samples; ++index) {
            auto& node = line.Nodes()[index];
            const float angle = 2.0f * kPi * index / config.samples;
            const float preferred = 0.5f * bias + 0.32f * std::sin(3.0f * angle + phase) +
                0.18f * std::sin(7.0f * angle + phase2);
            const float offset = 0.35f * base.Nodes()[index].offsetMetres +
                0.65f * samples[index].leftMetres * preferred;
            node.offsetMetres = offset;
            node.track.leftMetres = std::min(samples[index].leftMetres, offset + 0.35f);
            node.track.rightMetres = std::min(samples[index].rightMetres, -offset + 0.35f);
        }
        // Narrow optimization corridors retain each line's chosen corner/straight preferences.
        line.MinimizeCurvature(70);
        for (int index = 0; index < config.samples; ++index) line.Nodes()[index].track = samples[index];
        line.Rebuild(tuning, Units);
        if (LapSeconds(line) > baseLap * 1.3f) continue;
        float closest = std::numeric_limits<float>::max();
        for (const auto& other : lines) {
            float squared = 0.0f;
            for (int index = 0; index < config.samples; ++index) {
                const float delta = line.Nodes()[index].offsetMetres - other.Nodes()[index].offsetMetres;
                squared += delta * delta;
            }
            closest = std::min(closest, std::sqrt(squared / config.samples));
        }
        if (closest < 0.30f) continue;
        solver.minimumSeparation = std::min(solver.minimumSeparation, closest);
        lines.push_back(std::move(line));
    }
    if (static_cast<int>(lines.size()) != config.trajectories) {
        error = "Could not generate the requested number of distinct fast trajectories.";
        return false;
    }
    for (int line = 0; line < config.trajectories; ++line) RebuildSpeeds(line);
    solver.fastestLap = std::numeric_limits<float>::max();
    for (const auto& line : lines) {
        const float seconds = LapSeconds(line);
        solver.fastestLap = std::min(solver.fastestLap, seconds);
        solver.slowestLap = std::max(solver.slowestLap, seconds);
    }
    return true;
}

std::size_t FFDiscreteRace::Index(int line, int sample) const {
    return static_cast<std::size_t>(line) * config.samples + sample % config.samples;
}

void FFDiscreteRace::Solve() {
    const int count = config.samples * config.trajectories;
    values.assign(count, 0.0f);
    edges.resize(count);
    std::vector<float> next(count);
    std::vector<int> candidates(config.trajectories);
    std::iota(candidates.begin(), candidates.end(), 0);
    for (int sample = 0; sample < config.samples; ++sample) {
        const float station = sample * lapLength / config.samples;
        for (int source = 0; source < config.trajectories; ++source) {
            std::sort(candidates.begin(), candidates.end(), [&](int first, int second) {
                const float a = std::abs(Lane(first, station) - Lane(source, station));
                const float b = std::abs(Lane(second, station) - Lane(source, station));
                return a == b ? first < second : a < b;
            });
            auto& actions = edges[Index(source, sample)];
            for (int action = 0; action < 9; ++action) {
                const int target = action == 0 ? source : candidates[
                    std::min(config.trajectories - 1, action * (config.trajectories - 1) / 8)];
                FFRaceCar car;
                car.trajectory = source;
                car.target = target;
                car.station = station;
                car.transitionStart = station;
                car.transitionLength = Stride * lapLength / config.samples;
                float seconds = 0.0f;
                for (int offset = 0; offset < Stride; ++offset) {
                    const float current = station + offset * lapLength / config.samples;
                    seconds += length(Position(car, current + lapLength / config.samples) - Position(car, current)) /
                        std::max(1.0f, SpeedLimit(car, current));
                }
                const float change = Lane(source, station) - Lane(target, station + car.transitionLength);
                actions[action] = {target, seconds, seconds * 0.2f - car.transitionLength * 0.04f + (source == target ? 0.0f : 0.03f + 0.01f * change * change),
                    std::exp(-seconds / DiscountSeconds)};
            }
        }
    }
    for (int iteration = 0; iteration < config.maximumIterations; ++iteration) {
        float residual = 0.0f;
        for (int line = 0; line < config.trajectories; ++line) {
            for (int sample = 0; sample < config.samples; ++sample) {
                const auto index = Index(line, sample);
                float best = -std::numeric_limits<float>::max();
                for (const auto& edge : edges[index]) {
                    best = std::max(best, -edge.cost + edge.discount * values[Index(edge.target, sample + Stride)]);
                }
                next[index] = best;
                residual = std::max(residual, std::abs(best - values[index]));
            }
        }
        values.swap(next);
        solver.iterations = iteration + 1;
        solver.residual = residual;
        if (residual <= config.tolerance) {
            solver.converged = true;
            break;
        }
    }
}

float FFDiscreteRace::Blend(float fraction) {
    const float t = std::clamp(fraction, 0.0f, 1.0f);
    return t * t * t * (10.0f + t * (-15.0f + 6.0f * t));
}

Vec2 FFDiscreteRace::Position(const FFRaceCar& car, float station) const {
    const float fraction = car.transitionLength > 0.0f ?
        Blend((station - car.transitionStart) / car.transitionLength) : 1.0f;
    return lerp(LinePosition(car.trajectory, station), LinePosition(car.target, station), fraction);
}

Vec2 FFDiscreteRace::LinePosition(int line, float station) const {
    const float coordinate = wrapDistance(station, lapLength) * config.samples / lapLength;
    const int first = static_cast<int>(coordinate) % config.samples;
    const float t = coordinate - std::floor(coordinate);
    const auto& nodes = lines[line].Nodes();
    const Vec2 a = nodes[(first + config.samples - 1) % config.samples].positionMetres;
    const Vec2 b = nodes[first].positionMetres;
    const Vec2 c = nodes[(first + 1) % config.samples].positionMetres;
    const Vec2 d = nodes[(first + 2) % config.samples].positionMetres;
    return (b * 2.0f + (c - a) * t + (a * 2.0f - b * 5.0f + c * 4.0f - d) * (t * t) +
        (b * 3.0f - a - c * 3.0f + d) * (t * t * t)) * 0.5f;
}

void FFDiscreteRace::RebuildSpeeds(int line) {
    auto& nodes = lines[line].Nodes();
    const float spacing = lapLength / config.samples;
    const float reference = tuning.maxForwardSpeed / Units;
    const float grip = tuning.lateralGripAcceleration * tuning.tireLimitedYawScale / Units * 0.65f;
    for (int sample = 0; sample < config.samples; ++sample) {
        float maximumCurvature = 0.0f;
        for (int offset = -2; offset <= 2; ++offset) {
            const float station = (sample + offset * 0.25f) * spacing;
            maximumCurvature = std::max(maximumCurvature, Curvature(LinePosition(line, station - 2.0f),
                LinePosition(line, station), LinePosition(line, station + 2.0f)));
        }
        const float denominator = maximumCurvature - grip * tuning.downforceGripGain / (reference * reference);
        const float speed = denominator > 0.00001f ? std::sqrt(grip / denominator) : reference + 30.0f / 3.6f;
        nodes[sample].speedMetresPerSecond = std::min(nodes[sample].speedMetresPerSecond, speed);
    }
    for (int pass = 0; pass < 5; ++pass) {
        for (int index = config.samples - 1; index >= 0; --index) {
            const auto& next = nodes[(index + 1) % config.samples];
            const float distance = length(next.positionMetres - nodes[index].positionMetres);
            nodes[index].speedMetresPerSecond = std::min(nodes[index].speedMetresPerSecond,
                std::sqrt(next.speedMetresPerSecond * next.speedMetresPerSecond + 2.0f * braking * 0.55f * distance));
        }
        for (int index = 0; index < config.samples; ++index) {
            const auto& previous = nodes[(index + config.samples - 1) % config.samples];
            const float distance = length(previous.positionMetres - nodes[index].positionMetres);
            nodes[index].speedMetresPerSecond = std::min(nodes[index].speedMetresPerSecond,
                std::sqrt(previous.speedMetresPerSecond * previous.speedMetresPerSecond + 2.0f * acceleration * 0.6f * distance));
        }
    }
}

float FFDiscreteRace::Metric(const FFRaceCar& car, float station) const {
    return std::max(0.2f, length(Position(car, station + 1.0f) - Position(car, station - 1.0f)) * 0.5f);
}

float FFDiscreteRace::Lane(int line, float station) const {
    const float coordinate = wrapDistance(station, lapLength) * config.samples / lapLength;
    const int first = static_cast<int>(coordinate) % config.samples;
    return lerp(lines[line].Nodes()[first].offsetMetres, lines[line].Nodes()[(first + 1) % config.samples].offsetMetres,
        coordinate - std::floor(coordinate));
}

float FFDiscreteRace::Value(int line, float station) const {
    const float coordinate = wrapDistance(station, lapLength) * config.samples / lapLength;
    const int first = static_cast<int>(coordinate) % config.samples;
    return lerp(values[Index(line, first)], values[Index(line, first + 1)], coordinate - std::floor(coordinate));
}

float FFDiscreteRace::LateralLimit(float speed) const {
    const float reference = tuning.maxForwardSpeed / Units;
    return tuning.lateralGripAcceleration * tuning.tireLimitedYawScale / Units *
        (1.0f + tuning.downforceGripGain * speed * speed / (reference * reference));
}

float FFDiscreteRace::SpeedLimit(const FFRaceCar& car, float station) const {
    const float curvature = Curvature(Position(car, station - 4.0f), Position(car, station), Position(car, station + 4.0f));
    const float reference = tuning.maxForwardSpeed / Units;
    const float grip = tuning.lateralGripAcceleration * tuning.tireLimitedYawScale / Units * 0.72f;
    const float denominator = curvature - grip * tuning.downforceGripGain / (reference * reference);
    const float corner = denominator > 0.00001f ? std::sqrt(grip / denominator) : reference + 30.0f / 3.6f;
    return std::min({corner, lines[car.trajectory].Speed(station), lines[car.target].Speed(station)}) * car.pace;
}

bool FFDiscreteRace::Transition(FFRaceCar& car, int target) const {
    if (target < 0 || target >= config.trajectories || car.trajectory != car.target) return false;
    if (target == car.trajectory) return true;
    FFRaceCar candidate = car;
    candidate.target = target;
    candidate.transitionStart = car.station;
    candidate.transitionLength = std::max(60.0f, car.speed * 2.0f);
    for (int index = 0; index <= 16; ++index) {
        const float station = car.station + candidate.transitionLength * index / 16.0f;
        const float availableSpeed = std::sqrt(std::max(0.0f, car.speed * car.speed -
            2.0f * braking * (station - car.station)));
        if (SpeedLimit(candidate, station) + 0.5f < availableSpeed) return false;
    }
    car = candidate;
    return true;
}

float FFDiscreteRace::Random() {
    randomState ^= randomState << 13;
    randomState ^= randomState >> 17;
    randomState ^= randomState << 5;
    return static_cast<float>(randomState >> 8) / 16777216.0f;
}

void FFDiscreteRace::UpdateBelief(FFRaceBelief& belief, const FFRaceObservation& observation, float seconds) const {
    if (belief.trajectories.size() != lines.size()) belief.trajectories.assign(lines.size(), 1.0f / lines.size());
    if (belief.initialized) {
        belief.station += belief.speed * seconds;
        belief.stationVariance = std::min(2500.0f, belief.stationVariance + seconds * (4.0f + belief.age * 12.0f));
        belief.age += seconds;
    }
    const float mixing = 1.0f - std::exp(-0.6f * seconds);
    for (float& probability : belief.trajectories) probability =
        (1.0f - mixing) * probability + mixing / config.trajectories;
    if (!observation.visible) return;
    if (belief.initialized) {
        const float measured = std::clamp((observation.lane - belief.lane) / std::max(0.05f, belief.age), -3.0f, 3.0f);
        belief.lateralSpeed = 0.7f * belief.lateralSpeed + 0.3f * measured;
    }
    belief.lane = observation.lane;
    if (!belief.initialized) {
        belief.station = observation.station;
        belief.speed = observation.speed;
        belief.initialized = true;
    }
    const float gain = belief.stationVariance / (belief.stationVariance + 0.64f);
    belief.station += gain * SignedDistance(observation.station, belief.station, lapLength);
    belief.stationVariance = std::max(0.1f, (1.0f - gain) * belief.stationVariance);
    belief.speed = 0.25f * belief.speed + 0.75f * observation.speed;
    belief.age = 0.0f;
    float total = 0.0f;
    for (int line = 0; line < config.trajectories; ++line) {
        const float difference = Lane(line, belief.station) - observation.lane;
        // A wide likelihood covers intermediate lane-change positions and sensor noise.
        belief.trajectories[line] *= std::exp(-0.5f * difference * difference / 0.64f) + 0.00001f;
        total += belief.trajectories[line];
    }
    for (float& probability : belief.trajectories) probability /= total;
}

void FFDiscreteRace::Observe(int observer) {
    beliefUpdateTime[observer] = elapsed;
    const auto& ego = cars[observer];
    const Vec2 forward = fromAngle(ego.heading);
    for (int opponent = 0; opponent < config.cars; ++opponent) {
        if (opponent == observer) continue;
        const auto& other = cars[opponent];
        const Vec2 delta = other.position - ego.position;
        FFRaceObservation observation;
        observation.visible = lengthSq(delta) < config.observationRange * config.observationRange &&
            dot(delta, forward) > -35.0f && Random() >= config.dropout;
        if (observation.visible) {
            observation.station = wrapDistance(other.station + (Random() - 0.5f) * 1.6f, lapLength);
            observation.speed = std::max(0.0f, other.speed + (Random() - 0.5f));
            const Vec2 tangent = normalize(LinePosition(0, other.station + 1.0f) - LinePosition(0, other.station - 1.0f));
            observation.lane = Lane(0, other.station) + dot(other.position - LinePosition(0, other.station), Vec2{-tangent.y, tangent.x}) +
                (Random() - 0.5f) * 0.6f;
            ++stats.observed;
        } else ++stats.missed;
        UpdateBelief(beliefs[observer * config.cars + opponent], observation, DecisionSeconds);
    }
}

float FFDiscreteRace::Risk(int observer, Vec2 position, float station, float future) const {
    float risk = 0.0f;
    for (int opponent = 0; opponent < config.cars; ++opponent) {
        if (opponent == observer) continue;
        const auto& belief = beliefs[observer * config.cars + opponent];
        if (!belief.initialized || belief.age > 4.0f) continue;
        const float predicted = belief.station + belief.speed * future;
        const float longitudinal = SignedDistance(predicted, station, lapLength);
        const float sigma = 3.5f + std::sqrt(belief.stationVariance) + 0.8f * future;
        if (std::abs(longitudinal) > 3.0f * sigma) continue;
        const float longitudinalRisk = std::exp(-0.5f * longitudinal * longitudinal / (sigma * sigma));
        float lateralRisk = 0.0f;
        // Stratified samples retain separate possible lines without a joint car-state tensor.
        float cumulative = belief.trajectories[0];
        int line = 0;
        for (int particle = 0; particle < 8; ++particle) {
            const float quantile = (particle + 0.5f) / 8.0f;
            while (line + 1 < config.trajectories && cumulative < quantile) cumulative += belief.trajectories[++line];
            const Vec2 expected = LinePosition(line, station);
            const Vec2 tangent = normalize(LinePosition(line, station + 1.0f) - LinePosition(line, station - 1.0f));
            const float separation = cross(tangent, position - expected) -
                std::clamp(belief.lateralSpeed * future, -2.0f, 2.0f);
            const float lateralSigma = 1.2f + 0.2f * belief.age + 0.12f * future;
            lateralRisk += std::exp(-0.5f * separation * separation / (lateralSigma * lateralSigma)) / 8.0f;
        }
        risk += longitudinalRisk * lateralRisk;
    }
    return std::min(1.0f, risk);
}

float FFDiscreteRace::FollowingSpeed(int observer) const {
    const auto& ego = cars[observer];
    float limit = 200.0f;
    for (int opponent = 0; opponent < config.cars; ++opponent) {
        if (opponent == observer) continue;
        const auto& belief = beliefs[observer * config.cars + opponent];
        if (!belief.initialized || belief.age > 2.0f) continue;
        const float predicted = belief.station + belief.speed * (elapsed - beliefUpdateTime[observer]);
        const float gap = SignedDistance(predicted, ego.station, lapLength);
        if (gap < 0.0f || gap > 100.0f) continue;
        float blocking = 0.0f;
        for (int line = 0; line < config.trajectories; ++line) {
            bool intersects = false;
            for (float future : {0.0f, 0.75f, 1.5f}) {
                const float station = ego.station + ego.speed * future;
                if (length(Position(ego, station) - LinePosition(line, station)) < 2.9f) intersects = true;
            }
            if (intersects) blocking += belief.trajectories[line];
        }
        if (blocking < 0.18f) continue;
        const float safeGap = std::max(0.0f, gap - 8.0f - 2.0f * std::sqrt(belief.stationVariance));
        const float safe = std::sqrt(belief.speed * belief.speed * 0.8f + 2.0f * braking * 0.6f * safeGap);
        limit = std::min(limit, std::min(safe, belief.speed + (safeGap - 0.7f * ego.speed) * 0.6f));
    }
    return std::max(0.0f, limit);
}

void FFDiscreteRace::Decide(int observer) {
    const auto began = std::chrono::steady_clock::now();
    Observe(observer);
    auto& ego = cars[observer];
    if (config.planning && ego.trajectory == ego.target) {
        std::array<bool, 256> considered{};
        considered[ego.trajectory] = true;
        int count = 1;
        const int sample = static_cast<int>(wrapDistance(ego.station, lapLength) * config.samples / lapLength);
        for (const auto& edge : edges[Index(ego.trajectory, sample)]) {
            if (!considered[edge.target]) {
                considered[edge.target] = true;
                ++count;
            }
        }
        std::vector<std::pair<float, int>> ranked;
        ranked.reserve(config.trajectories);
        for (int target = 0; target < config.trajectories; ++target)
            ranked.emplace_back(Value(target, ego.station + 80.0f), target);
        std::sort(ranked.begin(), ranked.end(), std::greater<>());
        for (const auto& [value, target] : ranked) {
            if (count >= 16) break;
            if (!considered[target]) {
                considered[target] = true;
                ++count;
            }
        }
        int best = ego.trajectory;
        float bestScore = -std::numeric_limits<float>::max();
        for (int target = 0; target < config.trajectories; ++target) {
            if (!considered[target]) continue;
            FFRaceCar candidate = ego;
            if (!Transition(candidate, target)) continue;
            float score = target == ego.trajectory ? 0.6f : 0.0f;
            const float initial = candidate.station;
            float discount = 1.0f;
            for (int step = 0; step < 12; ++step) {
                Move(candidate, 0.25f);
                discount = std::exp(-(step + 1) * 0.25f / DiscountSeconds);
                score -= discount * Risk(observer, candidate.position, candidate.station, (step + 1) * 0.25f) * 45.0f;
            }
            score += (candidate.station - initial) * 0.04f + discount * Value(target, candidate.station);
            if (score > bestScore) {
                bestScore = score;
                best = target;
            }
        }
        if (best != ego.trajectory && Transition(ego, best)) ++stats.switches;
    }
    stats.decisionMilliseconds += std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - began).count();
    ++stats.decisions;
}

void FFDiscreteRace::DecideAll() {
    for (int index = 0; index < config.cars; ++index) Decide(index);
}

void FFDiscreteRace::Move(FFRaceCar& car, float seconds, float followingSpeed) const {
    float target = std::min(followingSpeed, SpeedLimit(car, car.station));
    for (int lookahead = 1; lookahead <= 16; ++lookahead) {
        const float distance = lookahead * 12.0f;
        const float ahead = SpeedLimit(car, car.station + distance);
        target = std::min(target, std::sqrt(ahead * ahead + 2.0f * braking * 0.6f * distance));
    }
    const float curvature = Curvature(Position(car, car.station - 4.0f), Position(car, car.station), Position(car, car.station + 4.0f));
    const float lateralRatio = std::min(0.99f, car.speed * car.speed * curvature / LateralLimit(car.speed));
    const float gripFraction = std::sqrt(std::max(0.01f, 1.0f - lateralRatio * lateralRatio));
    const float nextSpeed = car.speed + std::clamp(target - car.speed, -braking * gripFraction * seconds,
        acceleration * gripFraction * seconds);
    car.station += (car.speed + nextSpeed) * 0.5f * seconds / Metric(car, car.station);
    car.speed = nextSpeed;
    car.position = Position(car, car.station);
    car.heading = angleOf(Position(car, car.station + 1.0f) - Position(car, car.station - 1.0f));
    if (car.trajectory != car.target && car.station >= car.transitionStart + car.transitionLength) {
        car.trajectory = car.target;
        car.transitionLength = 0.0f;
    }
}

void FFDiscreteRace::Step(float seconds) {
    if (!std::isfinite(seconds) || seconds <= 0.0f || seconds > 0.05f || cars.empty()) return;
    elapsed += seconds;
    for (int index = 0; index < config.cars; ++index) {
        if (elapsed >= nextDecision[index]) {
            Decide(index);
            nextDecision[index] += DecisionSeconds;
        }
    }
    // All observations and decisions use the same pre-motion fleet snapshot.
    for (int index = 0; index < config.cars; ++index) {
        auto& car = cars[index];
        Move(car, seconds, FollowingSpeed(index));
        const float curvature = Curvature(Position(car, car.station - 4.0f), car.position, Position(car, car.station + 4.0f));
        stats.maximumLateralRatio = std::max(stats.maximumLateralRatio, car.speed * car.speed * curvature / LateralLimit(car.speed));
    }
    for (int first = 0; first < config.cars; ++first) {
        for (int second = first + 1; second < config.cars; ++second) {
            const auto& a = cars[first];
            const auto& b = cars[second];
            const Vec2 delta = b.position - a.position;
            const Vec2 forward = fromAngle(a.heading);
            const float longitudinal = std::abs(dot(delta, forward));
            const float lateral = std::abs(cross(forward, delta));
            const bool overlap = longitudinal < 4.9f && lateral < 2.05f;
            const int index = first * config.cars + second;
            if (overlap && !overlaps[index]) ++stats.overlapEpisodes;
            overlaps[index] = overlap;
            passContact[index] = passContact[index] || overlap;
            stats.minimumClearance = std::min(stats.minimumClearance, length(delta) - 2.05f);
            const float difference = a.station - b.station;
            const int order = difference > 5.0f ? 1 : difference < -5.0f ? -1 : 0;
            if (order != 0) {
                if (ordering[index] != 0 && order != ordering[index]) {
                    ++stats.passes;
                    const bool corner = std::abs(wrapAngle(angleOf(Position(a, a.station + 12.0f) - a.position) - a.heading)) > 0.035f;
                    if (corner) ++stats.cornerPasses;
                    if (!passContact[index]) {
                        ++stats.cleanPasses;
                        if (corner) ++stats.cleanCornerPasses;
                    }
                    passContact[index] = overlap;
                }
                ordering[index] = order;
            }
        }
    }
}

const std::vector<FFRacingLine>& FFDiscreteRace::Lines() const {
    return lines;
}
const std::vector<FFRaceCar>& FFDiscreteRace::Cars() const {
    return cars;
}
const FFRaceBelief& FFDiscreteRace::Belief(int observer, int opponent) const {
    return beliefs[observer * config.cars + opponent];
}
const FFRaceSolverStats& FFDiscreteRace::Solver() const {
    return solver;
}
const FFRaceStats& FFDiscreteRace::Stats() const {
    return stats;
}
float FFDiscreteRace::LapLength() const {
    return lapLength;
}
