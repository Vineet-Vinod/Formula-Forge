#include "FFRacingLine.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <string>

bool FFRacingLine::Initialize(std::span<const FFRacingTrackSample> samples, float lengthMetres) {
    if (samples.size() < 16 || samples.size() > 8192 || !std::isfinite(lengthMetres) || lengthMetres <= 0.0f) return false;
    std::vector<FFRacingNode> loaded;
    loaded.reserve(samples.size());
    for (const auto& sample : samples) {
        if (!std::isfinite(sample.centreMetres.x) || !std::isfinite(sample.centreMetres.y) ||
            !std::isfinite(sample.tangent.x) || !std::isfinite(sample.tangent.y) ||
            !std::isfinite(sample.leftMetres) || !std::isfinite(sample.rightMetres) ||
            sample.leftMetres < 0.0f || sample.rightMetres < 0.0f ||
            lengthSq(sample.tangent) < 0.9f || lengthSq(sample.tangent) > 1.1f) return false;
        FFRacingNode node;
        node.track = sample;
        node.positionMetres = sample.centreMetres;
        loaded.push_back(node);
    }
    nodes = std::move(loaded);
    lapLength = lengthMetres;
    return true;
}

void FFRacingLine::UpdatePosition(std::size_t index) {
    auto& node = nodes[index];
    node.offsetMetres = std::clamp(node.offsetMetres, -node.track.rightMetres, node.track.leftMetres);
    node.positionMetres = node.track.centreMetres + Vec2{-node.track.tangent.y, node.track.tangent.x} * node.offsetMetres;
}

float FFRacingLine::Curvature(std::size_t index) const {
    const Vec2 first = nodes[(index + nodes.size() - 1) % nodes.size()].positionMetres;
    const Vec2 middle = nodes[index].positionMetres;
    const Vec2 last = nodes[(index + 1) % nodes.size()].positionMetres;
    const Vec2 before = middle - first;
    const Vec2 after = last - middle;
    return 2.0f * cross(before, after) / std::max(0.001f, length(before) * length(after) * length(last - first));
}

float FFRacingLine::LocalCost(std::size_t index, float distanceWeight) const {
    float cost = 0.0f;
    for (int offset = -1; offset <= 1; ++offset) {
        const auto current = (index + nodes.size() + offset) % nodes.size();
        const float curvature = Curvature(current);
        cost += curvature * curvature;
    }
    const Vec2 current = nodes[index].positionMetres;
    cost += distanceWeight * (length(current - nodes[(index + nodes.size() - 1) % nodes.size()].positionMetres) +
        length(current - nodes[(index + 1) % nodes.size()].positionMetres));
    return cost;
}

void FFRacingLine::MinimizeCurvature(int sweeps, float distanceWeight) {
    if (nodes.empty()) return;
    if (nodes.size() > 64 && sweeps >= 100) {
        const std::size_t count = nodes.size() / 2;
        std::vector<FFRacingTrackSample> samples;
        samples.reserve(count);
        for (std::size_t index = 0; index < count; ++index) samples.push_back(nodes[index * nodes.size() / count].track);
        FFRacingLine coarse;
        coarse.Initialize(samples, lapLength);
        for (std::size_t index = 0; index < count; ++index) {
            coarse.nodes[index].offsetMetres = nodes[index * nodes.size() / count].offsetMetres;
            coarse.UpdatePosition(index);
        }
        coarse.MinimizeCurvature(sweeps, distanceWeight);
        for (std::size_t index = 0; index < nodes.size(); ++index) {
            const float coordinate = static_cast<float>(index) * count / nodes.size();
            const auto first = static_cast<std::size_t>(coordinate);
            nodes[index].offsetMetres = lerp(coarse.nodes[first].offsetMetres, coarse.nodes[(first + 1) % count].offsetMetres,
                coordinate - std::floor(coordinate));
            UpdatePosition(index);
        }
    }
    for (int sweep = 0; sweep < sweeps; ++sweep) {
        const float step = 0.2f * std::pow(0.05f, static_cast<float>(sweep) / std::max(1, sweeps - 1));
        for (std::size_t iteration = 0; iteration < nodes.size(); ++iteration) {
            const std::size_t index = sweep % 2 == 0 ? iteration : nodes.size() - 1 - iteration;
            auto& node = nodes[index];
            const float original = node.offsetMetres;
            float best = original;
            float bestCost = LocalCost(index, distanceWeight);
            const float originalCost = bestCost;
            float lowerCost = originalCost;
            float upperCost = originalCost;
            for (const float delta : {-step, step}) {
                node.offsetMetres = original + delta;
                UpdatePosition(index);
                const float cost = LocalCost(index, distanceWeight);
                if (delta < 0.0f) lowerCost = cost;
                else upperCost = cost;
                if (cost < bestCost) {
                    bestCost = cost;
                    best = node.offsetMetres;
                }
            }
            const float quadratic = lowerCost + upperCost - 2.0f * originalCost;
            if (quadratic > 0.000000000001f) {
                const float delta = std::clamp(0.5f * step * (lowerCost - upperCost) / quadratic, -step, step);
                node.offsetMetres = original + delta;
                UpdatePosition(index);
                const float cost = LocalCost(index, distanceWeight);
                if (cost < bestCost) best = node.offsetMetres;
            }
            node.offsetMetres = best;
            UpdatePosition(index);
        }
    }
}

void FFRacingLine::Rebuild(const ArcadeVehicleConfig& tuning, float unitsPerMetre) {
    if (nodes.empty()) return;
    for (std::size_t index = 0; index < nodes.size(); ++index) UpdatePosition(index);
    const float referenceSpeed = tuning.maxForwardSpeed / unitsPerMetre;
    const float maximumSpeed = referenceSpeed + 30.0f / 3.6f;
    const float lateral = tuning.lateralGripAcceleration * tuning.tireLimitedYawScale / unitsPerMetre;
    for (std::size_t index = 0; index < nodes.size(); ++index) {
        auto& node = nodes[index];
        node.curvature = Curvature(index);
        const float availableLateral = lateral * node.surfaceGrip;
        const float denominator = std::abs(node.curvature) - availableLateral * controller.lateralSafety *
            tuning.downforceGripGain / (referenceSpeed * referenceSpeed);
        const float cornerSpeed = denominator > 0.00001f
            ? std::sqrt(availableLateral * controller.lateralSafety / denominator) : maximumSpeed;
        node.speedMetresPerSecond = std::clamp(cornerSpeed * node.speedScale, 8.0f, maximumSpeed);
    }
    for (int pass = 0; pass < 3; ++pass) {
        for (std::size_t iteration = 0; iteration < nodes.size(); ++iteration) {
            const std::size_t index = nodes.size() - 1 - iteration;
            auto& current = nodes[index];
            const auto& next = nodes[(index + 1) % nodes.size()];
            const float ratio = std::clamp(current.speedMetresPerSecond / referenceSpeed /
                tuning.brakeFullEffectSpeed, 0.0f, 1.0f);
            const float brakeScale = lerp(tuning.brakeLowSpeedScale, 1.0f,
                std::pow(smoothstep(ratio), tuning.brakeSpeedCurveExponent));
            const float deceleration = tuning.brakeDeceleration / unitsPerMetre * brakeScale * controller.brakingSafety;
            const float distance = length(next.positionMetres - current.positionMetres);
            current.speedMetresPerSecond = std::min(current.speedMetresPerSecond,
                std::sqrt(next.speedMetresPerSecond * next.speedMetresPerSecond + 2.0f * deceleration * distance));
        }
        for (std::size_t index = 0; index < nodes.size(); ++index) {
            const auto& previous = nodes[(index + nodes.size() - 1) % nodes.size()];
            auto& current = nodes[index];
            const float distance = length(current.positionMetres - previous.positionMetres);
            current.speedMetresPerSecond = std::min(current.speedMetresPerSecond,
                std::sqrt(previous.speedMetresPerSecond * previous.speedMetresPerSecond +
                    2.0f * tuning.engineAcceleration / unitsPerMetre * distance));
        }
    }
}

Vec2 FFRacingLine::Position(float stationMetres) const {
    if (nodes.empty()) return {};
    const float coordinate = wrapDistance(stationMetres, lapLength) / lapLength * nodes.size();
    const std::size_t first = static_cast<std::size_t>(coordinate) % nodes.size();
    return lerp(nodes[first].positionMetres, nodes[(first + 1) % nodes.size()].positionMetres,
        coordinate - std::floor(coordinate));
}

float FFRacingLine::Speed(float stationMetres) const {
    if (nodes.empty()) return 0.0f;
    const float coordinate = wrapDistance(stationMetres, lapLength) / lapLength * nodes.size();
    const std::size_t first = static_cast<std::size_t>(coordinate) % nodes.size();
    return lerp(nodes[first].speedMetresPerSecond, nodes[(first + 1) % nodes.size()].speedMetresPerSecond,
        coordinate - std::floor(coordinate));
}

ArcadeVehicleControl FFRacingLine::Control(const ArcadeVehicleState& vehicle,
    const ArcadeVehicleConfig& tuning, float stationMetres, float unitsPerMetre, float pace) const {
    ArcadeVehicleControl control;
    if (nodes.empty()) {
        control.brake = 1.0f;
        return control;
    }
    const float speed = std::max(0.0f, vehicle.forwardSpeed / unitsPerMetre);
    const float lookahead = controller.lookaheadMetres + controller.lookaheadSeconds * speed;
    const Vec2 predictedPosition = (vehicle.pos + vehicle.vel * controller.predictionSeconds) / unitsPerMetre;
    const Vec2 target = Position(stationMetres + lookahead + speed * controller.predictionSeconds);
    const Vec2 difference = target - predictedPosition;
    const float predictedHeading = vehicle.heading + vehicle.yawRate * controller.predictionSeconds;
    const float error = wrapAngle(angleOf(difference) - predictedHeading);
    const float desiredCurvature = 2.0f * std::sin(error) / std::max(1.0f, length(difference));
    const float normalizedSpeed = std::clamp(speed * unitsPerMetre / tuning.maxForwardSpeed, 0.0f, 1.5f);
    const float fade = smoothstep((normalizedSpeed - tuning.steerFadeStart) / (1.0f - tuning.steerFadeStart));
    const float maximumSteer = lerp(tuning.maxSteerLowSpeed, tuning.maxSteerHighSpeed, fade);
    control.steer = std::clamp(std::atan(tuning.wheelbase / unitsPerMetre * desiredCurvature) / maximumSteer, -1.0f, 1.0f);
    const float targetSpeed = Speed(stationMetres + speed * 0.08f) * pace;
    const float acceleration = (targetSpeed - speed) * controller.speedGain;
    control.throttle = std::clamp(acceleration / 5.0f, 0.0f, 1.0f);
    control.brake = std::clamp(-acceleration / 20.0f, 0.0f, 1.0f);
    if (controller.accelerationFeedforward > 0.0f) {
        constexpr float differenceMetres = 5.0f;
        const float before = Speed(stationMetres - differenceMetres) * pace;
        const float after = Speed(stationMetres + differenceMetres) * pace;
        const float plannedAcceleration = (after * after - before * before) / (4.0f * differenceMetres);
        const float drag = tuning.rollingResistance / unitsPerMetre + speed * speed * unitsPerMetre * tuning.aerodynamicDrag;
        const float requestedForce = plannedAcceleration + acceleration + drag;
        const float rpmRise = smoothstep((vehicle.engineRpmNormalized - tuning.idleRpmNormalized) /
            std::max(0.01f, 0.72f - tuning.idleRpmNormalized));
        const float rpmFall = smoothstep((vehicle.engineRpmNormalized - 0.84f) / 0.22f);
        const float torque = lerp(0.72f, 0.98f, rpmRise) * lerp(1.0f, 0.78f, rpmFall);
        const auto gearIndex = static_cast<std::size_t>(std::clamp(vehicle.gear, 1, 8) - 1);
        const float drive = tuning.engineAcceleration / unitsPerMetre * torque * tuning.gearDriveScales[gearIndex];
        const float ratio = std::clamp(speed * unitsPerMetre / tuning.maxForwardSpeed / tuning.brakeFullEffectSpeed, 0.0f, 1.0f);
        const float braking = tuning.brakeDeceleration / unitsPerMetre * lerp(tuning.brakeLowSpeedScale, 1.0f,
            std::pow(smoothstep(ratio), tuning.brakeSpeedCurveExponent));
        const float throttle = std::clamp(requestedForce / std::max(0.1f, drive), 0.0f, 1.0f);
        const float brake = std::clamp(-requestedForce / std::max(0.1f, braking), 0.0f, 1.0f);
        control.throttle = lerp(control.throttle, throttle, controller.accelerationFeedforward);
        control.brake = lerp(control.brake, brake, controller.accelerationFeedforward);
    }
    const float terminalTarget = tuning.maxForwardSpeed / unitsPerMetre + 30.0f / 3.6f;
    if (targetSpeed >= terminalTarget - 0.1f && std::abs(control.steer) < 0.1f &&
        Speed(stationMetres + speed * 0.5f) * pace >= terminalTarget - 0.1f) {
        control.throttle = 1.0f;
        control.brake = 0.0f;
    }
    control.automaticShift = true;
    return control;
}

bool FFRacingLine::Save(std::ostream& output) const {
    output << std::setprecision(std::numeric_limits<float>::max_digits10);
    output << "FFRACING 3 " << nodes.size() << ' ' << lapLength << '\n';
    output << controller.lookaheadMetres << ' ' << controller.lookaheadSeconds << ' ' << controller.predictionSeconds << ' '
        << controller.speedGain << ' ' << controller.lateralSafety << ' ' << controller.brakingSafety << ' '
        << controller.accelerationFeedforward << '\n';
    for (const auto& node : nodes) {
        output << node.track.centreMetres.x << ' ' << node.track.centreMetres.y << ' '
            << node.track.tangent.x << ' ' << node.track.tangent.y << ' '
            << node.track.leftMetres << ' ' << node.track.rightMetres << ' '
            << node.offsetMetres << ' ' << node.speedScale << ' ' << node.surfaceGrip << '\n';
    }
    return static_cast<bool>(output);
}

bool FFRacingLine::Load(std::istream& input) {
    std::string signature;
    int version = 0;
    std::size_t count = 0;
    float lengthMetres = 0.0f;
    FFRacingLine loaded;
    if (!(input >> signature >> version >> count >> lengthMetres) || signature != "FFRACING" || version < 1 || version > 3 ||
        count < 16 || count > 8192) return false;
    auto& config = loaded.controller;
    if (!(input >> config.lookaheadMetres >> config.lookaheadSeconds >> config.predictionSeconds >>
        config.speedGain >> config.lateralSafety >> config.brakingSafety)) return false;
    config.accelerationFeedforward = 0.0f;
    if (version >= 2 && !(input >> config.accelerationFeedforward)) return false;
    const float values[] = {config.lookaheadMetres, config.lookaheadSeconds, config.predictionSeconds,
        config.speedGain, config.lateralSafety, config.brakingSafety, config.accelerationFeedforward};
    for (float value : values) if (!std::isfinite(value) || value < 0.0f || value > 100.0f) return false;
    if (config.lookaheadMetres < 1.0f || config.lookaheadSeconds > 2.0f || config.predictionSeconds > 0.5f ||
        config.speedGain < 0.1f || config.lateralSafety < 0.1f || config.lateralSafety > 3.0f ||
        config.brakingSafety < 0.1f || config.brakingSafety > 1.5f || config.accelerationFeedforward > 1.0f) return false;
    std::vector<FFRacingTrackSample> samples(count);
    std::vector<float> offsets(count);
    std::vector<float> scales(count);
    std::vector<float> grips(count, 1.0f);
    for (std::size_t index = 0; index < count; ++index) {
        auto& sample = samples[index];
        if (!(input >> sample.centreMetres.x >> sample.centreMetres.y >> sample.tangent.x >> sample.tangent.y >>
            sample.leftMetres >> sample.rightMetres >> offsets[index] >> scales[index]) ||
            !std::isfinite(offsets[index]) || !std::isfinite(scales[index]) || scales[index] < 0.2f || scales[index] > 3.0f ||
            offsets[index] < -sample.rightMetres - 0.001f || offsets[index] > sample.leftMetres + 0.001f) return false;
        if (version >= 3 && (!(input >> grips[index]) || !std::isfinite(grips[index]) || grips[index] < 0.1f || grips[index] > 5.0f)) return false;
    }
    std::string extra;
    if (input >> extra) return false;
    if (!loaded.Initialize(samples, lengthMetres)) return false;
    for (std::size_t index = 0; index < count; ++index) {
        loaded.nodes[index].offsetMetres = offsets[index];
        loaded.nodes[index].speedScale = scales[index];
        loaded.nodes[index].surfaceGrip = grips[index];
        loaded.UpdatePosition(index);
    }
    *this = std::move(loaded);
    return true;
}

float FFRacingLine::LapLength() const {
    return lapLength;
}

std::vector<FFRacingNode>& FFRacingLine::Nodes() {
    return nodes;
}

const std::vector<FFRacingNode>& FFRacingLine::Nodes() const {
    return nodes;
}
