#include "FFSimulation.hpp"
#include "FFCircuitGeometry.hpp"
#include "FFTrackLimits.hpp"
#include "silverstone_chapel_barriers.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace {
#include "Native/track_data/silverstone_rebuild_barriers.inc"
#include "Native/track_data/silverstone_boundaries.inc"
#include "Native/track_data/silverstone_ground.inc"

constexpr float LapLength = 5891.0f;
constexpr float Units = 17.0f;
constexpr float HalfLength = 83.6f * 0.5f;
constexpr float HalfWidth = 34.4f * 0.5f;
constexpr float Gravity = 9.80665f;
constexpr float KerbMetres = 0.85f;

struct CornerTarget {
    float phase;
    float speedKph;
    bool fullThrottle;
};

constexpr CornerTarget CornerTargets[] = {
    {0.042f, 295.0f, true}, {0.125f, 113.0f, false},
    {0.153f, 94.0f, false}, {0.315f, 156.0f, false},
    {0.347f, 114.0f, false}, {0.430f, 259.0f, true},
    {0.500f, 290.0f, true}, {0.583f, 263.0f, false},
    {0.611f, 226.0f, false}, {0.833f, 230.0f, false},
    {0.903f, 99.0f, false}, {0.945f, 171.0f, false},
};

constexpr CornerTarget MonzaTargets[] = {
    {0.10707f, 73.0f, false}, {0.17038f, 294.0f, true}, {0.31810f, 113.0f, false},
    {0.38956f, 207.0f, false}, {0.44524f, 190.0f, false}, {0.65096f, 194.0f, false},
    {0.83959f, 215.0f, false},
};
constexpr CornerTarget InterlagosTargets[] = {
    {0.097f, 110.0f, false}, {0.167f, 228.0f, false}, {0.347f, 167.0f, false},
    {0.500f, 226.0f, false}, {0.583f, 108.0f, false}, {0.667f, 88.0f, false},
    {0.720f, 206.0f, false}, {0.778f, 119.0f, false}, {0.910f, 267.0f, true},
};

ArcadeVehicleConfig SilverstoneTuning() {
    ArcadeVehicleConfig config;
    constexpr float pace = 1.405f;
    constexpr float accelerationScale = pace * pace;
    config.maxForwardSpeed = 318.0f * Units / 3.6f;
    config.engineAcceleration = 190.0f;
    config.launchAccelerationBonus = 5.0f;
    config.brakeDeceleration = 4.65f * Gravity * Units;
    config.reverseAcceleration *= accelerationScale;
    config.wheelbase = 83.6f * 0.65f;
    config.wheelRadius = 18.4f * 0.52f;
    config.driftGripAcceleration *= 1.05f * 0.96f * accelerationScale;
    config.maxSteerLowSpeed = 0.32f;
    config.maxSteerHighSpeed = 0.075f;
    config.maxYawRateLowSpeed = 1.55f;
    config.maxYawRateHighSpeed = 1.20f;
    config.steerResponse *= pace * 0.90f;
    config.steerReturnResponse *= pace * 1.08f;
    config.yawResponseGrip *= pace;
    config.yawResponseExit *= pace;
    config.lateralGripResponse *= pace;
    config.brakeLoadResponse = 20.0f;
    config.brakeReleaseResponse = 24.0f;
    config.brakeOversteerMinSpeed = config.maxForwardSpeed * 0.18f;
    config.brakeOversteerFullSpeed = config.maxForwardSpeed;
    config.brakeOversteerSteerThreshold = 0.18f;
    config.brakeOversteerYawGain = 0.24f;
    config.brakeYawLimitScale = 1.03f;
    config.brakeOversteerSlip = 0.035f;
    config.brakeSlipResponse = 14.0f;
    config.brakeSlipRecovery = 24.0f;
    config.downforceGripGain = 1.65f;
    config.tireLimitedYawScale = 0.97f;
    config.accelerationGripUsageScale = 0.82f;
    config.driftMinEntrySpeed = config.maxForwardSpeed * 2.0f;
    config.driftMinSustainSpeed = config.maxForwardSpeed * 2.0f;
    config.boostAcceleration *= accelerationScale;
    config.gravity *= accelerationScale;
    config.landingImpulseDecay *= pace;
    config.maxBodyRoll *= 0.46f;
    config.maxBodyPitch *= 0.70f;
    config.maxBrakePitch *= 0.62f;
    config.brakeLowSpeedScale = 0.28f;
    config.brakeFullEffectSpeed = 0.72f;
    config.brakeSpeedCurveExponent = 2.0f;
    config.rollingResistance = 3.2f;
    config.aerodynamicDrag = 0.0000265f;
    config.engineBrakingAcceleration = 0.20f * Gravity * Units;
    config.lateralGripAcceleration = 1.78f * Gravity * Units * 1.05f;
    config.automaticBrakingDownshiftRpm = 0.88f;
    config.downshiftOverrevRpm = 1.00f;
    config.manualDownshiftOverrevRpm = 1.08f;
    config.gearRedlineSpeedRatios = {0.225f, 0.280f, 0.400f, 0.550f, 0.700f, 0.840f, 0.940f, 1.060f};
    config.combinedGripExponent = 2.20f;
    config.combinedGripFloor = 0.30f;
    config.trailBrakeTurnInGain = 0.16f;
    return config;
}
}

void FFTrialState::Reset(float station) {
    seconds = 0.0;
    running = false;
    invalid = false;
    nextGate = 1;
    previousStation = wrapDistance(station - startStation, lapLength);
}

void FFTrialState::Step(float station, bool onTrack, bool contact, double deltaSeconds) {
    station = wrapDistance(station - startStation, lapLength);
    float movement = station - previousStation;
    if (movement > lapLength * 0.5f) movement -= lapLength;
    if (movement < -lapLength * 0.5f) movement += lapLength;
    const bool crossedStart = previousStation > lapLength - 30.0f && station < 30.0f && movement > 0.0f;
    const double fraction = crossedStart && movement > 0.001f
        ? std::clamp(static_cast<double>((lapLength - previousStation) / movement), 0.0, 1.0) : 1.0;
    if (running) {
        invalid = invalid || !onTrack || contact || movement < -0.25f || movement > 20.0f;
        if (nextGate < 12) {
            const float gate = lapLength * nextGate / 12.0f;
            if (previousStation <= gate && station >= gate && movement > 0.0f && movement <= 20.0f) {
                ++nextGate;
            }
        }
        seconds += deltaSeconds * fraction;
    }
    if (crossedStart && onTrack) {
        if (running && nextGate == 12) {
            lastSeconds = seconds;
            lastValid = !invalid;
            ++completedLaps;
            if (lastValid && (bestSeconds <= 0.0 || lastSeconds < bestSeconds)) bestSeconds = lastSeconds;
        }
        running = true;
        invalid = contact || !onTrack;
        nextGate = 1;
        seconds = deltaSeconds * (1.0 - fraction);
    }
    previousStation = station;
}

FFSimulation::FFSimulation(TrackLayoutId layout) : circuit(layout),
    track(findTrackCatalogEntry(layout)) {
    lapLength = track->targetLengthMeters;
    circuitName = track->displayName;
    trial.lapLength = lapLength;
    trial.startStation = track->startPhase * lapLength;
    if (layout == TrackLayoutId::Monza) {
        barriers.assign(FFMonzaGeometry.barriers.begin(), FFMonzaGeometry.barriers.end());
        runoff = FFMonzaGeometry.runoff;
        ground = &FFMonzaGeometry.ground;
    } else if (layout == TrackLayoutId::Interlagos) {
        barriers.assign(FFInterlagosGeometry.barriers.begin(), FFInterlagosGeometry.barriers.end());
        runoff = FFInterlagosGeometry.runoff;
        ground = &FFInterlagosGeometry.ground;
    } else {
        barriers.assign(std::begin(kSilverstoneRebuildBarriers), std::end(kSilverstoneRebuildBarriers));
        barriers.insert(barriers.end(), kSilverstoneChapelBarriers.begin(), kSilverstoneChapelBarriers.end());
        runoff = kSilverstoneSurveyRunoff;
        ground = &kSilverstoneGround;
    }
    tuning = SilverstoneTuning();
    plan = authoredCircuitPlan(track->centerline, track->centerlineScale, lapLength, Units, track->mirrorCenterlineY, 1536);
    tangents.resize(plan.size());
    curvatures.resize(plan.size());
    const int count = static_cast<int>(plan.size());
    for (int index = 0; index < count; ++index) {
        tangents[index] = normalize(plan[(index + 3) % count] - plan[(index + count - 3) % count]);
    }
    for (int index = 0; index < count; ++index) {
        curvatures[index] = std::abs(wrapAngle(angleOf(tangents[(index + 8) % count]) -
            angleOf(tangents[(index + count - 8) % count])));
    }
    Reset();
}

FFTrackProjection FFSimulation::Sample(float station) const {
    station = wrapDistance(station, lapLength);
    const float coordinate = station / lapLength * plan.size();
    const int first = static_cast<int>(coordinate) % plan.size();
    const int second = (first + 1) % plan.size();
    const float blend = coordinate - std::floor(coordinate);
    FFTrackProjection projection;
    projection.position = lerp(plan[first], plan[second], blend);
    projection.tangent = normalize(lerp(tangents[first], tangents[second], blend));
    projection.station = station;
    projection.halfWidth = sampleTrackWidthMeters(*track, station) * 0.5f;
    projection.elevation = sampleTrackElevationMeters(*track, station) * Units;
    projection.bankSlope = std::tan(sampleTrackBankDegrees(*track, station) * kPi / 180.0f);
    projection.curvature = lerp(curvatures[first], curvatures[second], blend);
    const float spacing = lapLength / plan.size();
    projection.grade = (sampleTrackElevationMeters(*track, station + spacing * 2.0f) -
        sampleTrackElevationMeters(*track, station - spacing * 2.0f)) / (4.0f * spacing);
    return projection;
}

FFTrackProjection FFSimulation::Project(Vec2 position) const {
    if (projectionCached && position.x == projectionPosition.x && position.y == projectionPosition.y) {
        return projectionResult;
    }
    float bestDistance = std::numeric_limits<float>::max();
    float station = 0.0f;
    for (std::size_t index = 0; index < plan.size(); ++index) {
        const Vec2 segment = plan[(index + 1) % plan.size()] - plan[index];
        const float blend = std::clamp(dot(position - plan[index], segment) / std::max(0.001f, lengthSq(segment)), 0.0f, 1.0f);
        const float distance = lengthSq(position - (plan[index] + segment * blend));
        if (distance < bestDistance) {
            bestDistance = distance;
            station = (index + blend) * lapLength / plan.size();
        }
    }
    FFTrackProjection projection = Sample(station);
    projection.lane = dot(position - projection.position, Vec2{-projection.tangent.y, projection.tangent.x});
    projectionPosition = position;
    projectionResult = projection;
    projectionCached = true;
    return projection;
}

float FFSimulation::Ground(Vec2 position, bool protectMainRoad) const {
    const FFTrackProjection projection = Project(position);
    const float road = projection.elevation + projection.bankSlope * projection.lane;
    const float blend = smoothstep(std::clamp((std::abs(projection.lane) / Units - projection.halfWidth) / 4.0f, 0.0f, 1.0f));
    float nativeGround = road;
    if (ground != nullptr) {
        nativeGround = lerp(road, authoredGridElevationMeters(*ground, position) * Units, blend);
    } else {
        const float transition = (projection.halfWidth + 4.0f) * Units;
        if (std::abs(projection.lane) > transition) {
            const float falloff = smoothstep(std::clamp((std::abs(projection.lane) - transition) / (32.0f * Units), 0.0f, 1.0f));
            nativeGround = projection.elevation + lerp(std::copysign(transition, projection.lane) * projection.bankSlope, 0.0f, falloff);
        }
    }
    if (protectMainRoad && std::abs(projection.lane) <= (projection.halfWidth + KerbMetres) * Units) return nativeGround;
    if (circuit == TrackLayoutId::Monza) {
        const auto surfaceHeight = driveSurface.Height(position.x / Units, -position.y / Units);
        if (surfaceHeight) return *surfaceHeight * Units;
    }
    const auto nationalHeight = nationalSurface.Height(position.x / Units, -position.y / Units);
    if (nationalHeight) return (*nationalHeight - 0.065f) * Units;
    const FFPitProjection pit = pitLane.Project(position / Units, FFPitLane::GroundBlendMetres);
    if (!pit.inside) return nativeGround;
    const float vergeBlend = smoothstep(std::clamp((std::abs(pit.lane) - pit.halfWidth) /
        FFPitLane::GroundBlendMetres, 0.0f, 1.0f));
    const float pitGround = lerp(pit.height * Units, nativeGround, vergeBlend);
    if (!protectMainRoad) return pitGround;
    const float mergeBlend = smoothstep(std::clamp(std::abs(projection.lane) / Units -
        projection.halfWidth - KerbMetres, 0.0f, 1.0f));
    return lerp(nativeGround, pitGround, mergeBlend);
}

float FFSimulation::VisualGround(Vec2 position) const {
    const auto height = driveSurface.Height(position.x / Units, -position.y / Units);
    return height ? *height * Units : Ground(position);
}

void FFSimulation::Reset(float station) {
    if (station < 0.0f) station = wrapDistance(trial.startStation - 20.0f, lapLength);
    const FFTrackProjection projection = Sample(station);
    vehicle = ArcadeVehicleState{};
    vehicle.pos = projection.position;
    vehicle.heading = angleOf(projection.tangent);
    vehicle.elevation = Ground(vehicle.pos);
    barrierContact = false;
    appliedControl = {};
    trial.Reset(projection.station);
}

float FFSimulation::GripScale(const FFTrackProjection& projection) const {
    const float curvature = projection.curvature / (16.0f * lapLength / plan.size());
    if (curvature <= 0.00001f) return 1.0f;
    float scale = 1.0f;
    const float phase = projection.station / lapLength;
    const std::span<const CornerTarget> targets = circuit == TrackLayoutId::Monza
        ? std::span<const CornerTarget>(MonzaTargets) : circuit == TrackLayoutId::Interlagos
        ? std::span<const CornerTarget>(InterlagosTargets) : std::span<const CornerTarget>(CornerTargets);
    for (const CornerTarget& target : targets) {
        float distance = std::abs(phase - target.phase);
        distance = std::min(distance, 1.0f - distance);
        const float window = target.fullThrottle ? 0.032f : 0.022f;
        if (distance >= window) continue;
        const float targetSpeed = target.speedKph / 3.6f;
        const float liveSpeed = length(vehicle.vel) / Units;
        const float speedInfluence = smoothstep(std::clamp((liveSpeed - targetSpeed * 0.55f) / (targetSpeed * 0.35f), 0.0f, 1.0f));
        const float normalizedSpeed = std::clamp(targetSpeed / (tuning.maxForwardSpeed / Units), 0.0f, 1.25f);
        const float available = tuning.lateralGripAcceleration / Units * tuning.tireLimitedYawScale *
            (1.0f + tuning.downforceGripGain * normalizedSpeed * normalizedSpeed);
        const float targetScale = std::clamp(targetSpeed * targetSpeed * curvature / available * 1.06f, 1.0f, 3.0f);
        const float core = target.fullThrottle ? 0.022f : 0.015f;
        const float influence = distance <= core ? 1.0f : 1.0f - smoothstep((distance - core) / (window - core));
        scale = std::max(scale, lerp(1.0f, targetScale, influence * speedInfluence));
    }
    return scale;
}

ArcadeSurface FFSimulation::CurrentSurface() const {
    return Surface(Project(vehicle.pos));
}

ArcadeSurface FFSimulation::Surface(const FFTrackProjection& projection) const {
    const FFPitProjection pit = pitLane.Project(vehicle.pos / Units, FFPitLane::GroundBlendMetres);
    if (pit.inside && std::abs(projection.lane) > (projection.halfWidth + KerbMetres) * Units) {
        ArcadeSurface surface;
        surface.groundElevation = Ground(vehicle.pos);
        surface.groundGrade = pit.grade;
        surface.bumpiness = 0.01f;
        return surface;
    }
    const float roadHalf = projection.halfWidth * Units;
    const float lane = std::abs(projection.lane);
    const float tires = smoothstep(std::clamp((lane + HalfWidth - roadHalf) / (HalfWidth * 2.0f), 0.0f, 1.0f));
    const float loose = smoothstep(std::clamp((lane + HalfWidth - roadHalf - KerbMetres * Units) / (HalfWidth * 2.0f), 0.0f, 1.0f));
    bool asphalt = false;
    bool gravel = false;
    if (loose > 0.001f) {
        for (const AuthoredSurfaceTriangle& triangle : runoff) {
            if (insideAuthoredSurface(vehicle.pos, triangle)) {
                asphalt = triangle.asphalt;
                gravel = !asphalt;
                break;
            }
        }
    }
    ArcadeSurface surface;
    surface.grip = lerp(GripScale(projection), 1.0f, tires) * lerp(1.0f, 0.94f, tires);
    surface.acceleration = lerp(1.0f, 0.96f, tires);
    surface.rollingResistance = lerp(1.0f, 1.22f, tires);
    surface.steering = lerp(1.0f, 0.94f, tires);
    surface.grip = lerp(surface.grip, asphalt ? 0.90f : gravel ? 0.62f : 0.50f, loose);
    surface.acceleration = lerp(surface.acceleration, asphalt ? 0.82f : gravel ? 0.48f : 0.35f, loose);
    surface.rollingResistance = lerp(surface.rollingResistance, asphalt ? 2.0f : gravel ? 7.0f : 8.5f, loose);
    surface.steering = lerp(surface.steering, asphalt ? 0.88f : gravel ? 0.68f : 0.56f, loose);
    surface.maxSpeed = lerp(1.0f, asphalt ? 0.86f : gravel ? 0.62f : 0.52f, loose);
    surface.driftCharge = lerp(lerp(1.0f, 0.48f, tires), asphalt ? 0.20f : 0.0f, loose);
    surface.bumpiness = lerp(tires * 0.10f, asphalt ? 0.14f : gravel ? 0.55f : 0.72f, loose);
    surface.groundElevation = Ground(vehicle.pos);
    surface.groundGrade = projection.grade;
    surface.allowsDrift = loose < 0.20f;
    return surface;
}

bool FFSimulation::OnTrack() const {
    const Vec2 forward = fromAngle(vehicle.heading);
    const Vec2 across{-forward.y, forward.x};
    for (std::size_t index = 0; index < FFSilverstoneTyres.size(); ++index) {
        const auto& tyre = FFSilverstoneTyres[index];
        const Vec2 centre = vehicle.pos + (forward * tyre.centreMetres.x + across * tyre.centreMetres.y) * Units;
        const Vec2 tyreForward = fromAngle(vehicle.heading + (index < 2 ? vehicle.steerAngle : 0.0f));
        const Vec2 tyreAcross{-tyreForward.y, tyreForward.x};
        if (pitTrackLimits.Touches(centre / Units, tyreAcross, tyre.halfWidthMetres)) return true;
        if (!trackLimits.Empty()) {
            if (trackLimits.Touches(centre / Units, tyreAcross, tyre.halfWidthMetres)) return true;
            continue;
        }
        const FFTrackProjection projection = Project(centre);
        if (FFTyreTouchesTrack(projection.lane / Units, projection.halfWidth,
                tyreAcross, {-projection.tangent.y, projection.tangent.x}, tyre.halfWidthMetres)) {
            return true;
        }
    }
    return false;
}

void FFSimulation::ResolveBarriers(Vec2 start) {
    Vec2 end = vehicle.pos;
    barrierContact = false;
    for (int iteration = 0; iteration < 4; ++iteration) {
        const auto hit = firstAuthoredBarrierHit(barriers, start, end,
            fromAngle(vehicle.heading), HalfLength, HalfWidth, vehicle.elevation, 0.8f * Units);
        if (!hit.hit) break;
        barrierContact = true;
        const Vec2 contact = lerp(start, end, hit.time) + hit.normal * (hit.penetration + 0.02f * Units);
        Vec2 remaining = (end - start) * (1.0f - hit.time);
        remaining -= hit.normal * std::min(0.0f, dot(remaining, hit.normal));
        start = contact;
        end = iteration == 3 ? contact : contact + remaining;
        const float normalSpeed = dot(vehicle.vel, hit.normal);
        if (normalSpeed < 0.0f) {
            const float incidence = std::clamp(-normalSpeed / std::max(1.0f, length(vehicle.vel)), 0.0f, 1.0f);
            const Vec2 tangent{-hit.normal.y, hit.normal.x};
            vehicle.vel = tangent * (dot(vehicle.vel, tangent) * lerp(0.96f, 0.18f, incidence * incidence)) -
                hit.normal * (normalSpeed * lerp(0.06f, 0.015f, incidence));
            vehicle.yawRate *= lerp(0.92f, 0.84f, incidence);
            vehicle.contactTimer = std::max(vehicle.contactTimer, 0.18f);
        }
    }
    vehicle.pos = end;
}

void FFSimulation::Step(const ArcadeVehicleControl& control, float seconds) {
    const Vec2 start = vehicle.pos;
    const auto road = Project(start);
    const bool controlled = PitProjectionForCar(road).controlled;
    const float previousSpeed = length(vehicle.vel);
    constexpr float limitSpeed = 80.0f * Units / 3.6f;
    ArcadeVehicleControl trialControl = control;
    trialControl.forwardSpeedLimitExtra = control.brake <= 0.01f ? 30.0f * Units / 3.6f : 0.0f;
    if (controlled && previousSpeed >= limitSpeed - 0.25f * Units / 3.6f) trialControl.throttle = 0.0f;
    appliedControl = trialControl;
    stepArcadeVehicle(vehicle, tuning, trialControl, Surface(road), seconds);
    ResolveBarriers(start);
    if (controlled && previousSpeed <= limitSpeed + 0.5f * Units / 3.6f && length(vehicle.vel) > limitSpeed) {
        vehicle.vel = vehicle.vel * (limitSpeed / length(vehicle.vel));
        vehicle.forwardSpeed = dot(vehicle.vel, fromAngle(vehicle.heading));
    }
    if (vehicle.grounded) vehicle.elevation = Ground(vehicle.pos);
    trial.Step(ProgressStation(), OnTrack(), barrierContact, seconds);
    if (trial.running && PitOverspeed()) trial.invalid = true;
}

bool FFSimulation::LoadNationalSurface(std::span<const std::uint8_t> bytes) {
    return nationalSurface.Load(bytes);
}

bool FFSimulation::LoadPitLane(std::span<const std::uint8_t> bytes) {
    FFPitLane loaded;
    if (!loaded.Load(bytes)) return false;
    std::vector<std::array<Vec2, 3>> triangles;
    const auto& sections = loaded.Sections();
    for (std::size_t index = 1; index < sections.size(); ++index) {
        const auto& first = sections[index - 1];
        const auto& last = sections[index];
        const Vec2 firstLeft = first.position + first.normal * first.halfWidth;
        const Vec2 firstRight = first.position - first.normal * first.halfWidth;
        const Vec2 lastLeft = last.position + last.normal * last.halfWidth;
        const Vec2 lastRight = last.position - last.normal * last.halfWidth;
        triangles.push_back({firstLeft, firstRight, lastRight});
        triangles.push_back({firstLeft, lastRight, lastLeft});
    }
    if (!pitTrackLimits.SetTriangles(triangles)) return false;
    pitLane = std::move(loaded);
    return true;
}

bool FFSimulation::LoadPitBarriers(std::span<const std::uint8_t> bytes) {
    constexpr std::array<std::uint8_t, 8> signature{'F', 'F', 'B', 'A', 'R', '1', 0, 0};
    if (bytes.size() < 12 || !std::equal(signature.begin(), signature.end(), bytes.begin())) return false;
    std::uint32_t count;
    std::memcpy(&count, bytes.data() + 8, 4);
    if (count == 0 || count > 10000 || bytes.size() != 12 + count * 28) return false;
    std::vector<AuthoredBarrierSegment> loaded;
    loaded.reserve(count + kSilverstoneChapelBarriers.size());
    for (std::uint32_t index = 0; index < count; ++index) {
        std::array<float, 7> row;
        std::memcpy(row.data(), bytes.data() + 12 + index * 28, 28);
        for (float value : row) if (!std::isfinite(value) || std::abs(value) > 200000.0f) return false;
        if (row[4] >= row[5] || row[6] <= 0.0f || row[6] > 17.0f ||
            lengthSq(Vec2{row[2] - row[0], row[3] - row[1]}) < 0.000001f) return false;
        loaded.push_back({{row[0], row[1]}, {row[2], row[3]}, row[4], row[5], row[6]});
    }
    loaded.insert(loaded.end(), kSilverstoneChapelBarriers.begin(), kSilverstoneChapelBarriers.end());
    barriers = std::move(loaded);
    return true;
}

FFPitProjection FFSimulation::PitProjectionForCar(const FFTrackProjection& road) const {
    if (std::abs(road.lane) <= (road.halfWidth + KerbMetres) * Units) return {};
    FFPitProjection pit = pitLane.Project(vehicle.pos / Units);
    if (!pit.inside) pit = pitLane.Project(vehicle.pos / Units, 3.0f);
    if (!pit.inside) return {};
    const Vec2 forward = fromAngle(vehicle.heading);
    const Vec2 across{-forward.y, forward.x};
    for (std::size_t index = 0; index < FFSilverstoneTyres.size(); ++index) {
        const auto& tyre = FFSilverstoneTyres[index];
        const Vec2 centre = vehicle.pos + (forward * tyre.centreMetres.x + across * tyre.centreMetres.y) * Units;
        const Vec2 tyreForward = fromAngle(vehicle.heading + (index < 2 ? vehicle.steerAngle : 0.0f));
        const Vec2 tyreAcross{-tyreForward.y, tyreForward.x};
        if (pitTrackLimits.Touches(centre / Units, tyreAcross, tyre.halfWidthMetres)) {
            return pit;
        }
    }
    return {};
}

bool FFSimulation::InPitLane() const {
    return PitProjectionForCar(Project(vehicle.pos)).inside;
}

float FFSimulation::PitSpeedLimitKph() const {
    return PitProjectionForCar(Project(vehicle.pos)).controlled ? 80.0f : 0.0f;
}

bool FFSimulation::PitOverspeed() const {
    return PitSpeedLimitKph() > 0.0f && length(vehicle.vel) * 3.6f / Units > 80.5f;
}

float FFSimulation::ProgressStation() const {
    const FFTrackProjection road = Project(vehicle.pos);
    const FFPitProjection pit = PitProjectionForCar(road);
    return pit.inside ? wrapDistance(pit.trackStation, lapLength) : road.station;
}

const std::vector<AuthoredBarrierSegment>& FFSimulation::Barriers() const {
    return barriers;
}

bool FFSimulation::Audit() {
    FFSimulation simulation;
    for (float station = 0.0f; station < LapLength; station += 4.0f) {
        const auto projection = simulation.Sample(station);
        const Vec2 normal{-projection.tangent.y, projection.tangent.x};
        for (float lane : {-3.0f, 0.0f, 3.0f}) {
            const Vec2 position = projection.position + normal * (lane * Units);
            const float ground = simulation.Ground(position);
            if (!std::isfinite(ground)) return false;
            if (firstAuthoredBarrierHit(simulation.barriers, position, position,
                projection.tangent, HalfLength, HalfWidth, ground, 0.8f * Units).hit) return false;
        }
    }
    int crossingChecks = 0;
    for (const auto& wall : simulation.barriers) {
        if (wall.top - wall.bottom < 0.1f * Units) continue;
        const Vec2 tangent = normalize(wall.b - wall.a);
        const Vec2 normal{-tangent.y, tangent.x};
        const Vec2 center = (wall.a + wall.b) * 0.5f;
        for (float side : {-1.0f, 1.0f}) {
            for (float speed : {15.0f, 200.0f, 348.0f}) {
                const float travel = speed / 3.6f * Units / 120.0f;
                const Vec2 start = center + normal * (side * (wall.halfThickness + HalfWidth + 0.01f * Units));
                if (!sweepAuthoredBarrier(wall, start, start - normal * (side * travel), tangent,
                    HalfLength, HalfWidth, wall.bottom, 0.8f * Units).hit) return false;
                ++crossingChecks;
            }
        }
    }
    bool resolvedContact = false;
    for (const auto& wall : simulation.barriers) {
        const Vec2 center = (wall.a + wall.b) * 0.5f;
        if (wall.top - wall.bottom < 0.5f * Units || std::abs(simulation.Ground(center) - wall.bottom) > 0.2f * Units) continue;
        const Vec2 tangent = normalize(wall.b - wall.a);
        const Vec2 normal{-tangent.y, tangent.x};
        simulation.Reset();
        simulation.vehicle.pos = center - normal * (wall.halfThickness + HalfLength + 0.10f * Units);
        simulation.vehicle.heading = angleOf(normal);
        simulation.vehicle.vel = normal * (348.0f / 3.6f * Units);
        simulation.vehicle.forwardSpeed = length(simulation.vehicle.vel);
        simulation.vehicle.elevation = simulation.Ground(simulation.vehicle.pos);
        ArcadeVehicleControl control;
        simulation.Step(control, 1.0f / 120.0f);
        resolvedContact = simulation.barrierContact && dot(simulation.vehicle.pos - center, normal) <= -wall.halfThickness - HalfLength;
        if (resolvedContact) break;
    }
    if (!resolvedContact) return false;
    FFTrialState trial;
    trial.Reset(LapLength - 1.0f);
    trial.Step(1.0f, true, false, 0.02);
    for (float station = 3.0f; station < LapLength; station += 2.0f) trial.Step(station, true, false, 0.02);
    trial.Step(1.0f, true, false, 0.02);
    if (trial.completedLaps != 1 || !trial.lastValid || trial.bestSeconds <= 0.0) return false;
    const double best = trial.bestSeconds;
    for (float station = 3.0f; station < LapLength; station += 2.0f) trial.Step(station, station < 2000.0f, false, 0.02);
    trial.Step(1.0f, true, false, 0.02);
    if (trial.lastValid || trial.bestSeconds != best) return false;
    trial.Reset(1.0f);
    trial.Step(LapLength - 1.0f, true, false, 0.02);
    if (trial.running) return false;
    simulation.Reset();
    ArcadeVehicleControl throttle;
    throttle.throttle = 1.0f;
    throttle.automaticShift = true;
    for (int frame = 0; frame < 120; ++frame) simulation.Step(throttle, 1.0f / 120.0f);
    return crossingChecks > 0 && std::isfinite(simulation.vehicle.pos.x) &&
        simulation.vehicle.forwardSpeed > 0.0f &&
        std::abs(simulation.vehicle.elevation - simulation.Ground(simulation.vehicle.pos)) < 0.01f;
}
