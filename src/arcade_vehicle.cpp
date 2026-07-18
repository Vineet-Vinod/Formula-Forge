#include "arcade_vehicle.hpp"

#include <array>
#include <algorithm>
#include <cmath>

namespace {

constexpr float kInternalStep = 1.0f / 120.0f;

float expApproach(float current, float target, float response, float dt) {
    if (response <= 0.0f) {
        return current;
    }
    return target + (current - target) * std::exp(-response * dt);
}

float signedUnit(float value) {
    return value < 0.0f ? -1.0f : 1.0f;
}

float safeRatio(float numerator, float denominator) {
    return denominator > 0.0001f ? numerator / denominator : 0.0f;
}

float speedSteerFactor(float normalizedSpeed, float fadeStart) {
    const float span = std::max(0.001f, 1.0f - fadeStart);
    return smoothstep((normalizedSpeed - fadeStart) / span);
}

void springStep(float& value, float& velocity, float target, float frequency, float damping, float dt) {
    if (frequency <= 0.0f) {
        value = target;
        velocity = 0.0f;
        return;
    }
    const float omega = kTwoPi * frequency;
    const float acceleration = (target - value) * omega * omega - 2.0f * damping * omega * velocity;
    velocity += acceleration * dt;
    value += velocity * dt;
}

int awardDriftBoost(ArcadeVehicleState& state, const ArcadeVehicleConfig& config) {
    const int tier = arcadeDriftTier(state.driftCharge, config);
    float duration = 0.0f;
    float power = 0.0f;
    if (tier == 1) {
        duration = config.tierOneBoostDuration;
        power = config.tierOneBoostPower;
    } else if (tier == 2) {
        duration = config.tierTwoBoostDuration;
        power = config.tierTwoBoostPower;
    } else if (tier == 3) {
        duration = config.tierThreeBoostDuration;
        power = config.tierThreeBoostPower;
    }
    if (tier > 0) {
        state.boostTimer = std::max(state.boostTimer, duration);
        state.boostPower = std::max(state.boostPower, power);
    }
    return tier;
}

void enterDrift(ArcadeVehicleState& state, float steer) {
    state.driftPhase = ArcadeDriftPhase::Entry;
    state.driftPhaseTime = 0.0f;
    state.driftDir = steer < 0.0f ? -1.0f : 1.0f;
    state.driftCharge = 0.0f;
    state.drifting = true;
    state.driftInputConsumed = true;
}

int exitDrift(ArcadeVehicleState& state, const ArcadeVehicleConfig& config, bool rewardBoost) {
    const int tier = rewardBoost ? awardDriftBoost(state, config) : 0;
    state.driftPhase = ArcadeDriftPhase::Exit;
    state.driftPhaseTime = 0.0f;
    state.drifting = false;
    return tier;
}

ArcadeVehicleTelemetry sampleTelemetry(const ArcadeVehicleState& state, const ArcadeVehicleConfig& config) {
    ArcadeVehicleTelemetry out;
    out.forwardSpeed = state.forwardSpeed;
    out.lateralSpeed = state.lateralSpeed;
    out.speed = length(state.vel);
    out.normalizedSpeed = std::clamp(std::abs(state.forwardSpeed) / std::max(1.0f, config.maxForwardSpeed), 0.0f, 1.5f);
    out.slipAngle = state.slipAngle;
    out.steerAngle = state.steerAngle;
    out.yawRate = state.yawRate;
    out.peakSlipAngle = std::abs(state.slipAngle);
    out.tractionUtilization = state.tractionUtilization;
    out.elevation = state.elevation;
    out.verticalSpeed = state.verticalSpeed;
    out.airborneTime = state.airborneTime;
    out.landingImpulse = state.landingImpulse;
    out.brakeLoad = state.brakeLoad;
    out.grounded = state.grounded;
    out.driftPhase = state.driftPhase;
    out.driftTier = arcadeDriftTier(state.driftCharge, config);
    out.boostActive = state.boostTimer > 0.0f;
    return out;
}

ArcadeVehicleTelemetry stepSingle(ArcadeVehicleState& state,
                                  const ArcadeVehicleConfig& config,
                                  const ArcadeVehicleControl& rawControl,
                                  const ArcadeSurface& rawSurface,
                                  float dt) {
    ArcadeVehicleControl control = rawControl;
    control.steer = std::clamp(control.steer, -1.0f, 1.0f);
    control.throttle = std::clamp(control.throttle, 0.0f, 1.0f);
    control.brake = std::clamp(control.brake, 0.0f, 1.0f);

    ArcadeSurface surface = rawSurface;
    surface.grip = std::max(0.0f, surface.grip);
    surface.acceleration = std::max(0.0f, surface.acceleration);
    surface.rollingResistance = std::max(0.0f, surface.rollingResistance);
    surface.steering = std::max(0.0f, surface.steering);
    surface.maxSpeed = std::max(0.1f, surface.maxSpeed);
    surface.driftCharge = std::max(0.0f, surface.driftCharge);
    surface.bumpiness = std::max(0.0f, surface.bumpiness);
    if (!std::isfinite(surface.groundElevation)) {
        surface.groundElevation = state.elevation;
    }
    if (!std::isfinite(surface.groundGrade)) {
        surface.groundGrade = 0.0f;
    }
    surface.launchVelocity = std::max(0.0f, surface.launchVelocity);

    const bool driftPressed = control.driftPressed || (control.drift && !state.driftInputHeld);
    state.driftInputHeld = control.drift;
    if (!control.drift) {
        state.driftInputConsumed = false;
    }

    state.contactTimer = std::max(0.0f, state.contactTimer - dt);
    state.driftCooldown = std::max(0.0f, state.driftCooldown - dt);
    state.launchCooldown = std::max(0.0f, state.launchCooldown - dt);
    state.landingImpulse = std::max(0.0f, state.landingImpulse - config.landingImpulseDecay * dt);
    state.boostTimer = std::max(0.0f, state.boostTimer - dt);
    if (state.boostTimer <= 0.0f) {
        state.boostPower = 0.0f;
    }

    Vec2 forward = fromAngle(state.heading);
    Vec2 left{-forward.y, forward.x};
    float forwardSpeed = dot(state.vel, forward);
    float lateralSpeed = dot(state.vel, left);
    const float absForwardSpeed = std::abs(forwardSpeed);
    const float normalizedSpeed = std::clamp(safeRatio(absForwardSpeed, config.maxForwardSpeed), 0.0f, 1.5f);
    const float brakeResponse = control.brake > state.brakeLoad ? config.brakeLoadResponse : config.brakeReleaseResponse;
    state.brakeLoad = expApproach(state.brakeLoad, control.brake, brakeResponse, dt);

    const float steerResponse = std::abs(control.steer) > std::abs(state.steerSmoothed) ? config.steerResponse : config.steerReturnResponse;
    state.steerSmoothed = expApproach(state.steerSmoothed, control.steer, steerResponse, dt);
    const float steerFade = speedSteerFactor(normalizedSpeed, config.steerFadeStart);
    const float maxSteer = lerp(config.maxSteerLowSpeed, config.maxSteerHighSpeed, steerFade) * surface.steering;
    state.steerAngle = state.steerSmoothed * maxSteer;

    const bool canEnterDrift = surface.allowsDrift && state.driftCooldown <= 0.0f && absForwardSpeed >= config.driftMinEntrySpeed &&
                               std::abs(state.steerSmoothed) >= config.driftEntrySteer;
    const bool driftRequested = (driftPressed || (control.drift && !state.driftInputConsumed)) && canEnterDrift;
    int boostTierAwarded = 0;

    if (state.driftPhase == ArcadeDriftPhase::Grip && driftRequested) {
        enterDrift(state, state.steerSmoothed);
    }

    state.driftPhaseTime += dt;
    if (state.driftPhase == ArcadeDriftPhase::Entry) {
        if (!control.drift || !surface.allowsDrift || absForwardSpeed < config.driftMinSustainSpeed) {
            boostTierAwarded = exitDrift(state, config, false);
        } else if (state.driftPhaseTime >= config.driftEntryDuration) {
            state.driftPhase = ArcadeDriftPhase::Sustain;
            state.driftPhaseTime = 0.0f;
            state.drifting = true;
        }
    } else if (state.driftPhase == ArcadeDriftPhase::Sustain) {
        if (!control.drift || !surface.allowsDrift || absForwardSpeed < config.driftMinSustainSpeed) {
            boostTierAwarded = exitDrift(state, config, surface.allowsDrift && absForwardSpeed >= config.driftMinSustainSpeed);
        }
    } else if (state.driftPhase == ArcadeDriftPhase::Exit && state.driftPhaseTime >= config.driftExitDuration) {
        state.driftPhase = ArcadeDriftPhase::Grip;
        state.driftPhaseTime = 0.0f;
        state.driftCooldown = config.driftReentryCooldown;
        state.driftCharge = 0.0f;
        state.drifting = false;
    }

    const float sameSteer = std::clamp(state.steerSmoothed * state.driftDir, 0.0f, 1.0f);
    const float counterSteer = std::clamp(-state.steerSmoothed * state.driftDir, 0.0f, 1.0f);
    const float yawLimit = lerp(config.maxYawRateLowSpeed, config.maxYawRateHighSpeed, std::clamp(normalizedSpeed, 0.0f, 1.0f));
    const float kinematicYaw = config.wheelbase > 0.001f ? forwardSpeed / config.wheelbase * std::tan(state.steerAngle) : 0.0f;
    float targetYawRate = std::clamp(kinematicYaw, -yawLimit, yawLimit);
    float yawResponse = config.yawResponseGrip;
    float targetSlip = 0.0f;
    float lateralResponse = config.lateralGripResponse;
    float lateralAccelerationLimit = config.lateralGripAcceleration * surface.grip;

    const float brakeFullSpeed = config.brakeOversteerFullSpeed > config.brakeOversteerMinSpeed
                                     ? config.brakeOversteerFullSpeed
                                     : config.maxForwardSpeed;
    const float brakeSpeed = smoothstep((absForwardSpeed - config.brakeOversteerMinSpeed) /
                                        std::max(1.0f, brakeFullSpeed - config.brakeOversteerMinSpeed));
    const float brakeSteer = smoothstep((std::abs(state.steerSmoothed) - config.brakeOversteerSteerThreshold) /
                                        std::max(0.01f, 1.0f - config.brakeOversteerSteerThreshold));
    const float liveBrakeLoad = config.throttleCatchStrength > 0.0f
                                    ? (control.brake > 0.01f ? control.brake : 0.0f)
                                    : state.brakeLoad;
    const float brakeOversteer = state.grounded ? liveBrakeLoad * brakeSpeed * brakeSteer : 0.0f;
    const float catchSlideSeverity = smoothstep((std::max(std::abs(state.brakeSlip), std::abs(state.slipAngle)) - 0.04f) / 0.20f);
    const float throttleCatch = state.grounded && state.driftPhase == ArcadeDriftPhase::Grip && control.brake < 0.05f
                                    ? config.throttleCatchStrength * smoothstep(control.throttle) * catchSlideSeverity
                                    : 0.0f;
    const float signedBrakeSlip = -state.steerSmoothed * config.brakeOversteerSlip * brakeOversteer;
    const float brakeSlipResponse = std::abs(signedBrakeSlip) > std::abs(state.brakeSlip)
                                        ? config.brakeSlipResponse
                                        : lerp(config.brakeSlipRecovery, config.throttleCatchSlipRecovery, throttleCatch);
    state.brakeSlip = expApproach(state.brakeSlip, signedBrakeSlip, brakeSlipResponse, dt);

    if (state.driftPhase == ArcadeDriftPhase::Grip) {
        const float brakeSlide = std::clamp(std::abs(state.brakeSlip) / std::max(0.01f, config.brakeOversteerSlip), 0.0f, 1.0f);
        const float brakeSlideDirection = state.brakeSlip < 0.0f ? 1.0f : -1.0f;
        targetSlip = state.brakeSlip * (1.0f - throttleCatch * 0.95f);
        if (liveBrakeLoad > 0.0f) {
            targetYawRate += brakeSlideDirection * config.brakeOversteerYawGain * brakeSlide * brakeSpeed;
        }
        targetYawRate = std::clamp(targetYawRate, -yawLimit * config.brakeYawLimitScale,
                                   yawLimit * config.brakeYawLimitScale);
        const float catchYawRate = std::clamp(kinematicYaw, -yawLimit, yawLimit) * (1.0f - throttleCatch * 0.78f);
        targetYawRate = lerp(targetYawRate, catchYawRate, throttleCatch * 0.96f);
        lateralResponse = lerp(config.lateralGripResponse, config.driftLateralResponse, brakeSlide * 0.86f);
        lateralResponse = lerp(lateralResponse, config.throttleCatchLateralResponse, throttleCatch);
        const float rearGripFalloff = lerp(std::max(config.brakeRearGripScale, std::pow(1.0f - brakeSlide, 3.0f)),
                                           1.0f, throttleCatch);
        lateralAccelerationLimit *= rearGripFalloff;
        yawResponse = std::max(yawResponse, config.throttleCatchYawResponse * throttleCatch);
    }

    if (state.driftPhase == ArcadeDriftPhase::Entry || state.driftPhase == ArcadeDriftPhase::Sustain) {
        const float entryBlend = state.driftPhase == ArcadeDriftPhase::Entry
                                     ? smoothstep(state.driftPhaseTime / std::max(0.001f, config.driftEntryDuration))
                                     : 1.0f;
        const float slipMagnitude = (config.driftSlipBase + config.driftSlipExtra * sameSteer) *
                                    (1.0f - config.driftCountersteerRecovery * counterSteer);
        targetSlip = -state.driftDir * slipMagnitude * entryBlend;
        const float driftYaw = state.driftDir * (config.driftYawBase + config.driftYawSpeedGain * std::clamp(normalizedSpeed, 0.0f, 1.0f)) *
                               (1.0f + sameSteer * 0.22f - counterSteer * 0.58f);
        targetYawRate = lerp(targetYawRate, driftYaw, entryBlend);
        yawResponse = config.yawResponseDrift;
        lateralResponse = lerp(config.lateralGripResponse, config.driftLateralResponse, entryBlend);
        lateralAccelerationLimit = lerp(config.lateralGripAcceleration, config.driftGripAcceleration, entryBlend) * surface.grip;
    } else if (state.driftPhase == ArcadeDriftPhase::Exit) {
        const float exitT = smoothstep(state.driftPhaseTime / std::max(0.001f, config.driftExitDuration));
        const float currentSlip = std::atan2(lateralSpeed, std::max(1.0f, absForwardSpeed));
        targetSlip = currentSlip * (1.0f - exitT);
        yawResponse = config.yawResponseExit;
        lateralResponse = lerp(config.driftLateralResponse, config.lateralGripResponse, exitT);
        lateralAccelerationLimit = lerp(config.driftGripAcceleration, config.lateralGripAcceleration, exitT) * surface.grip;
    }

    if (!state.grounded) {
        targetYawRate *= config.airControlScale;
        yawResponse = std::min(yawResponse, 4.0f);
        targetSlip = state.slipAngle;
        lateralResponse = 0.0f;
        lateralAccelerationLimit = 0.0f;
    }

    state.yawRate = expApproach(state.yawRate, targetYawRate, yawResponse, dt);
    state.heading = wrapAngle(state.heading + state.yawRate * dt);

    float longitudinalAcceleration = 0.0f;
    float driveAcceleration = 0.0f;
    if (control.brake > 0.5f && std::abs(forwardSpeed) <= 3.0f) {
        state.brakeHold = std::min(state.brakeHold + dt, 1.0f);
    } else if (control.brake <= 0.5f || std::abs(forwardSpeed) >= 6.0f) {
        state.brakeHold = 0.0f;
    }

    const float torqueReferenceSpeed = config.throttleCatchStrength > 0.0f && forwardSpeed > -2.0f
                                           ? std::max(std::max(0.0f, forwardSpeed), length(state.vel) * 0.90f)
                                           : std::max(0.0f, forwardSpeed);
    const float speedForTorque = std::clamp(safeRatio(torqueReferenceSpeed, config.maxForwardSpeed), 0.0f, 1.25f);
    const float torqueCurve = std::clamp(1.0f - 0.78f * smoothstep(speedForTorque), 0.0f, 1.0f);
    const float launchCurve = 1.0f - smoothstep(speedForTorque / 0.42f);
    if (control.throttle > 0.0f) {
        if (forwardSpeed < -2.0f) {
            driveAcceleration += control.throttle * config.brakeDeceleration;
        } else {
            driveAcceleration += control.throttle *
                                 (config.engineAcceleration * torqueCurve + config.launchAccelerationBonus * launchCurve) * surface.acceleration;
        }
    }

    if (control.brake > 0.0f) {
        if (forwardSpeed > 2.0f) {
            const bool activeDrift = state.driftPhase == ArcadeDriftPhase::Entry || state.driftPhase == ArcadeDriftPhase::Sustain;
            const float brakingScale = activeDrift ? config.driftBrakeDecelerationScale : 1.0f;
            driveAcceleration -= control.brake * config.brakeDeceleration * brakingScale;
        } else if (forwardSpeed < -2.0f || state.brakeHold >= config.reverseDelay) {
            driveAcceleration -= control.brake * config.reverseAcceleration * surface.acceleration;
        }
    }

    if (!state.grounded) {
        driveAcceleration *= config.airDriveScale;
    }
    if (driveAcceleration > 0.0f && throttleCatch > 0.0f) {
        driveAcceleration *= lerp(1.0f, config.throttleCatchDriveScale, throttleCatch);
    }

    const bool boostActive = state.boostTimer > 0.0f;
    if (boostActive && control.throttle > 0.05f && forwardSpeed > 0.0f) {
        driveAcceleration += config.boostAcceleration * (0.55f + 0.45f * state.boostPower) * surface.acceleration;
    }

    longitudinalAcceleration += driveAcceleration;
    const float resistance = config.rollingResistance * surface.rollingResistance;
    if (std::abs(forwardSpeed) > 0.001f) {
        longitudinalAcceleration -= signedUnit(forwardSpeed) * std::min(resistance, std::abs(forwardSpeed) / dt);
    }
    longitudinalAcceleration -= forwardSpeed * std::abs(forwardSpeed) * config.aerodynamicDrag;

    const float boostSpeedScale = boostActive ? 1.0f + config.boostSpeedExtraBase + config.boostSpeedExtraPower * state.boostPower : 1.0f;
    const float forwardLimit = config.maxForwardSpeed * surface.maxSpeed * boostSpeedScale;
    if (forwardSpeed > forwardLimit) {
        longitudinalAcceleration -= (forwardSpeed - forwardLimit) * config.overspeedResponse;
    }
    const float reverseLimit = config.maxReverseSpeed * surface.maxSpeed;
    if (forwardSpeed < -reverseLimit) {
        longitudinalAcceleration += (-reverseLimit - forwardSpeed) * config.overspeedResponse;
    }

    if (state.driftPhase == ArcadeDriftPhase::Entry || state.driftPhase == ArcadeDriftPhase::Sustain) {
        const float slipDemand = std::clamp(std::abs(targetSlip) / std::max(0.01f, config.driftSlipBase + config.driftSlipExtra), 0.0f, 1.0f);
        longitudinalAcceleration -= signedUnit(forwardSpeed) * (config.driftBaseDrag + config.driftAngleDrag * slipDemand);
    }

    const float desiredLateralSpeed = std::tan(targetSlip) * std::max(0.0f, forwardSpeed);
    // yawRate * speed is the centripetal acceleration needed to carry the
    // existing velocity around the turn. The correction term then controls
    // sideslip without ever rotating velocity as a shortcut.
    float lateralAcceleration = state.yawRate * forwardSpeed + (desiredLateralSpeed - lateralSpeed) * lateralResponse;
    const float gripDriveAcceleration = driveAcceleration > 0.0f
                                            ? driveAcceleration * config.accelerationGripUsageScale
                                            : driveAcceleration;
    const float longitudinalUsage = std::clamp(std::abs(gripDriveAcceleration) /
                                                   std::max(1.0f, config.brakeDeceleration),
                                               0.0f, 1.0f);
    const float combinedGripScale = std::sqrt(std::max(0.36f, 1.0f - longitudinalUsage * longitudinalUsage * 0.64f));
    lateralAccelerationLimit *= combinedGripScale;
    lateralAcceleration = std::clamp(lateralAcceleration, -lateralAccelerationLimit, lateralAccelerationLimit);

    // Forces are applied in world space. Changing heading never rotates the
    // existing velocity, so slides and impacts retain their momentum.
    state.vel += forward * (longitudinalAcceleration * dt);
    state.vel += left * (lateralAcceleration * dt);
    const Vec2 stepDelta = state.vel * dt;
    state.pos += stepDelta;
    state.distanceTravelled += length(stepDelta);
    state.wheelSpin = wrapAngle(state.wheelSpin + safeRatio(forwardSpeed * dt, std::max(0.1f, config.wheelRadius)));

    forward = fromAngle(state.heading);
    left = {-forward.y, forward.x};
    state.forwardSpeed = dot(state.vel, forward);
    state.lateralSpeed = dot(state.vel, left);
    state.slipAngle = std::atan2(state.lateralSpeed, std::max(1.0f, std::abs(state.forwardSpeed)));
    state.engineLoad = std::clamp(std::abs(driveAcceleration) / std::max(1.0f, config.engineAcceleration + config.launchAccelerationBonus), 0.0f, 1.5f);
    state.tractionUtilization = lateralAccelerationLimit > 0.001f ? std::clamp(std::abs(lateralAcceleration) / lateralAccelerationLimit, 0.0f, 1.0f) : 0.0f;

    if (state.driftPhase == ArcadeDriftPhase::Sustain) {
        const float slip = std::abs(state.slipAngle);
        const float slipWindow = std::max(0.001f, config.driftChargeMaxSlip - config.driftChargeMinSlip);
        const float lowQuality = smoothstep((slip - config.driftChargeMinSlip) / (slipWindow * 0.35f));
        const float highQuality = 1.0f - smoothstep((slip - config.driftChargeMaxSlip * 0.78f) / (slipWindow * 0.22f));
        const float chargeQuality = std::clamp(lowQuality * highQuality, 0.0f, 1.0f);
        state.driftCharge = std::min(config.tierThreeCharge * 1.25f,
                                     state.driftCharge + dt * config.driftChargeRate * surface.driftCharge * chargeQuality);
    }

    if (state.grounded && surface.launchVelocity > 0.0f && state.launchCooldown <= 0.0f && state.forwardSpeed > 24.0f) {
        state.grounded = false;
        state.airborneTime = 0.0f;
        state.elevation = surface.groundElevation + 0.01f;
        state.verticalSpeed = std::max(surface.launchVelocity, state.forwardSpeed * std::max(0.0f, surface.groundGrade));
        state.launchCooldown = config.launchCooldown;
    } else if (!state.grounded) {
        state.airborneTime += dt;
        state.verticalSpeed -= config.gravity * dt;
        state.elevation += state.verticalSpeed * dt;
        if (state.elevation <= surface.groundElevation && state.verticalSpeed <= 0.0f) {
            state.landingImpulse = std::max(state.landingImpulse, -state.verticalSpeed);
            state.elevation = surface.groundElevation;
            state.verticalSpeed = state.forwardSpeed * surface.groundGrade;
            state.grounded = true;
        }
    } else {
        state.elevation = surface.groundElevation;
        state.verticalSpeed = state.forwardSpeed * surface.groundGrade;
        state.airborneTime = 0.0f;
    }

    const float bumpPhase = state.distanceTravelled * 0.075f;
    const float landingCompression = std::clamp(state.landingImpulse * config.landingCompressionScale, 0.0f, 1.0f);
    const float suspensionTarget = (state.grounded ? surface.bumpiness * (0.5f + 0.5f * std::sin(bumpPhase)) : -0.14f) +
                                   landingCompression;
    const float accelerationPitch = std::clamp(-longitudinalAcceleration / std::max(1.0f, config.brakeDeceleration), -1.0f, 1.0f) *
                                    config.maxBodyPitch;
    const float landingPitch = std::min(config.maxLandingPitch, state.landingImpulse * config.landingPitchScale);
    const float flightPitch = std::clamp(-std::atan2(state.verticalSpeed, std::max(1.0f, std::abs(state.forwardSpeed))),
                                         -config.maxAirPitchUp, config.maxAirPitchDown);
    const float pitchTarget = state.grounded ? accelerationPitch + state.brakeLoad * config.maxBrakePitch + landingPitch : flightPitch;
    const float rollTarget = std::clamp(-lateralAcceleration / std::max(1.0f, config.lateralGripAcceleration), -1.0f, 1.0f) *
                             config.maxBodyRoll;
    springStep(state.suspensionCompression, state.suspensionVelocity, suspensionTarget, config.suspensionFrequency,
               config.suspensionDamping, dt);
    springStep(state.bodyPitch, state.bodyPitchVelocity, pitchTarget,
               state.grounded ? config.bodyFrequency : config.airPitchFrequency, config.bodyDamping, dt);
    springStep(state.bodyRoll, state.bodyRollVelocity, rollTarget, config.bodyFrequency, config.bodyDamping, dt);

    ArcadeVehicleTelemetry out = sampleTelemetry(state, config);
    out.longitudinalAcceleration = longitudinalAcceleration;
    out.lateralAcceleration = lateralAcceleration;
    out.distanceDelta = length(stepDelta);
    out.boostTierAwarded = boostTierAwarded;
    return out;
}

ArcadeVehicleState simulateScript(float dt, float seconds) {
    ArcadeVehicleConfig config;
    ArcadeVehicleState state;
    ArcadeSurface surface;
    const int frames = static_cast<int>(seconds / dt + 0.5f);
    for (int frame = 0; frame < frames; ++frame) {
        const float t = static_cast<float>(frame) * dt;
        ArcadeVehicleControl control;
        control.throttle = t < 4.2f ? 1.0f : 0.35f;
        control.steer = t < 1.0f ? 0.0f : (t < 3.0f ? 0.58f : (t < 4.0f ? -0.35f : 0.0f));
        stepArcadeVehicle(state, config, control, surface, dt);
    }
    return state;
}

struct JumpScriptResult {
    ArcadeVehicleState state;
    float apex = 0.0f;
    float airTime = 0.0f;
    float landingImpulse = 0.0f;
    float noseUpPitch = 0.0f;
    float noseDownPitch = 0.0f;
};

JumpScriptResult simulateJump(float dt) {
    ArcadeVehicleConfig config;
    ArcadeVehicleState state;
    state.vel = {132.0f, 0.0f};
    ArcadeVehicleControl control;
    control.throttle = 1.0f;
    ArcadeSurface surface;
    JumpScriptResult result;
    bool launched = false;
    for (int frame = 0; frame < static_cast<int>(2.0f / dt + 0.5f); ++frame) {
        surface.launchVelocity = frame == 0 ? 43.0f : 0.0f;
        const ArcadeVehicleTelemetry telemetry = stepArcadeVehicle(state, config, control, surface, dt);
        launched = launched || !telemetry.grounded;
        result.apex = std::max(result.apex, telemetry.elevation);
        result.airTime = std::max(result.airTime, telemetry.airborneTime);
        result.landingImpulse = std::max(result.landingImpulse, telemetry.landingImpulse);
        result.noseUpPitch = std::min(result.noseUpPitch, state.bodyPitch);
        result.noseDownPitch = std::max(result.noseDownPitch, state.bodyPitch);
        if (launched && telemetry.grounded && result.airTime > 0.1f) {
            break;
        }
    }
    result.state = state;
    return result;
}

}  // namespace

int arcadeDriftTier(float charge, const ArcadeVehicleConfig& config) {
    if (charge >= config.tierThreeCharge) {
        return 3;
    }
    if (charge >= config.tierTwoCharge) {
        return 2;
    }
    if (charge >= config.tierOneCharge) {
        return 1;
    }
    return 0;
}

ArcadeVehicleTelemetry stepArcadeVehicle(ArcadeVehicleState& state,
                                         const ArcadeVehicleConfig& config,
                                         const ArcadeVehicleControl& control,
                                         const ArcadeSurface& surface,
                                         float dt) {
    if (!(dt > 0.0f) || !std::isfinite(dt)) {
        return sampleTelemetry(state, config);
    }

    const float boundedDt = std::min(dt, 0.25f);
    const int steps = std::max(1, static_cast<int>(std::ceil(boundedDt / kInternalStep)));
    const float stepDt = boundedDt / static_cast<float>(steps);
    const float distanceBefore = state.distanceTravelled;
    ArcadeVehicleTelemetry result = sampleTelemetry(state, config);
    float peakSlipAngle = std::abs(state.slipAngle);
    int boostTierAwarded = 0;

    ArcadeVehicleControl substepControl = control;
    for (int step = 0; step < steps; ++step) {
        const ArcadeVehicleTelemetry current = stepSingle(state, config, substepControl, surface, stepDt);
        result = current;
        peakSlipAngle = std::max(peakSlipAngle, std::abs(current.slipAngle));
        boostTierAwarded = std::max(boostTierAwarded, current.boostTierAwarded);
        substepControl.driftPressed = false;
    }

    // Recompute the aggregate fields that can peak or accumulate within a
    // caller step. Most game calls are already one internal step.
    result.distanceDelta = std::max(0.0f, state.distanceTravelled - distanceBefore);
    result.peakSlipAngle = peakSlipAngle;
    result.boostTierAwarded = boostTierAwarded;
    return result;
}

ArcadeVehicleAuditResult runArcadeVehicleUnitAudit() {
    ArcadeVehicleAuditResult result;
    const ArcadeVehicleConfig config;
    const ArcadeSurface road;

    const auto check = [&result](bool condition) {
        ++result.checks;
        if (!condition) {
            ++result.failures;
        }
    };

    ArcadeVehicleState rest;
    ArcadeVehicleControl steerAtRest;
    steerAtRest.steer = 1.0f;
    for (int i = 0; i < 240; ++i) {
        stepArcadeVehicle(rest, config, steerAtRest, road, kInternalStep);
    }
    result.restHeadingError = std::abs(rest.heading);
    check(result.restHeadingError < 0.001f);
    check(length(rest.vel) < 0.001f);

    ArcadeVehicleState straight;
    ArcadeVehicleControl throttle;
    throttle.throttle = 1.0f;
    for (int i = 0; i < 720; ++i) {
        stepArcadeVehicle(straight, config, throttle, road, kInternalStep);
    }
    result.straightLineSpeed = straight.forwardSpeed;
    check(result.straightLineSpeed > config.maxForwardSpeed * 0.90f);
    check(result.straightLineSpeed < config.maxForwardSpeed * 1.03f);
    check(std::abs(straight.pos.y) < 0.01f);

    ArcadeVehicleControl brakeControl;
    brakeControl.brake = 1.0f;
    for (int i = 0; i < 240 && straight.forwardSpeed > 2.0f; ++i) {
        stepArcadeVehicle(straight, config, brakeControl, road, kInternalStep);
    }
    for (int i = 0; i < 12; ++i) {
        stepArcadeVehicle(straight, config, {}, road, kInternalStep);
    }
    result.stoppedSpeed = length(straight.vel);
    check(result.stoppedSpeed < 3.0f);

    ArcadeVehicleConfig inertialConfig = config;
    inertialConfig.rollingResistance = 0.0f;
    inertialConfig.aerodynamicDrag = 0.0f;
    inertialConfig.overspeedResponse = 0.0f;
    inertialConfig.lateralGripAcceleration = 0.0f;
    inertialConfig.lateralGripResponse = 0.0f;
    inertialConfig.yawResponseGrip = 0.0f;
    ArcadeVehicleState inertial;
    inertial.vel = {123.0f, 31.0f};
    inertial.yawRate = 0.72f;
    const Vec2 originalVelocity = inertial.vel;
    for (int i = 0; i < 120; ++i) {
        stepArcadeVehicle(inertial, inertialConfig, {}, road, kInternalStep);
    }
    result.momentumError = length(inertial.vel - originalVelocity);
    check(result.momentumError < 0.001f);
    check(std::abs(inertial.heading) > 0.60f);

    ArcadeVehicleState lowSpeedSteer;
    ArcadeVehicleState highSpeedSteer;
    lowSpeedSteer.vel = {55.0f, 0.0f};
    highSpeedSteer.vel = {190.0f, 0.0f};
    lowSpeedSteer.steerSmoothed = 1.0f;
    highSpeedSteer.steerSmoothed = 1.0f;
    stepArcadeVehicle(lowSpeedSteer, config, steerAtRest, road, kInternalStep);
    stepArcadeVehicle(highSpeedSteer, config, steerAtRest, road, kInternalStep);
    result.lowSpeedSteerAngle = lowSpeedSteer.steerAngle;
    result.highSpeedSteerAngle = highSpeedSteer.steerAngle;
    check(result.lowSpeedSteerAngle > result.highSpeedSteerAngle * 1.45f);

    ArcadeVehicleState reverse;
    for (int i = 0; i < static_cast<int>(config.reverseDelay * 0.75f / kInternalStep); ++i) {
        stepArcadeVehicle(reverse, config, brakeControl, road, kInternalStep);
    }
    check(std::abs(reverse.forwardSpeed) < 0.1f);
    for (int i = 0; i < static_cast<int>(0.65f / kInternalStep); ++i) {
        stepArcadeVehicle(reverse, config, brakeControl, road, kInternalStep);
    }
    check(reverse.forwardSpeed < -8.0f);

    ArcadeVehicleState drift;
    drift.vel = {125.0f, 0.0f};
    ArcadeVehicleControl driftControl;
    driftControl.throttle = 0.82f;
    driftControl.steer = 0.72f;
    driftControl.drift = true;
    float peakSlip = 0.0f;
    for (int i = 0; i < 205; ++i) {
        const ArcadeVehicleTelemetry telemetry = stepArcadeVehicle(drift, config, driftControl, road, kInternalStep);
        peakSlip = std::max(peakSlip, std::abs(telemetry.slipAngle));
    }
    driftControl.drift = false;
    const ArcadeVehicleTelemetry release = stepArcadeVehicle(drift, config, driftControl, road, kInternalStep);
    result.driftPeakSlip = peakSlip;
    result.driftBoostTier = release.boostTierAwarded;
    check(peakSlip > 0.08f && peakSlip < 0.60f);
    check(drift.slipAngle < 0.0f);
    check(result.driftBoostTier >= 2);
    check(drift.boostTimer > 0.5f);

    ArcadeVehicleState roadRun;
    ArcadeVehicleState looseRun;
    ArcadeSurface loose = road;
    loose.grip = 0.68f;
    loose.acceleration = 0.62f;
    loose.rollingResistance = 4.5f;
    loose.maxSpeed = 0.72f;
    loose.driftCharge = 0.25f;
    for (int i = 0; i < 600; ++i) {
        stepArcadeVehicle(roadRun, config, throttle, road, kInternalStep);
        stepArcadeVehicle(looseRun, config, throttle, loose, kInternalStep);
    }
    result.looseSurfaceSpeedRatio = safeRatio(looseRun.forwardSpeed, roadRun.forwardSpeed);
    check(result.looseSurfaceSpeedRatio > 0.45f && result.looseSurfaceSpeedRatio < 0.82f);

    ArcadeVehicleState shoulderRun;
    ArcadeVehicleState shoulderRoadRun;
    ArcadeSurface shoulder = road;
    shoulder.grip = 0.94f;
    shoulder.acceleration = 0.97f;
    shoulder.rollingResistance = 1.18f;
    shoulder.maxSpeed = 1.0f;
    for (int i = 0; i < 360; ++i) {
        stepArcadeVehicle(shoulderRoadRun, config, throttle, road, kInternalStep);
        stepArcadeVehicle(shoulderRun, config, throttle, shoulder, kInternalStep);
    }
    result.shoulderSpeedRatio = safeRatio(shoulderRun.forwardSpeed, shoulderRoadRun.forwardSpeed);
    check(result.shoulderSpeedRatio > 0.92f);

    ArcadeVehicleState brakeTurn;
    brakeTurn.vel = {150.0f, 0.0f};
    ArcadeVehicleControl brakeTurnControl;
    brakeTurnControl.throttle = 1.0f;
    brakeTurnControl.steer = 0.90f;
    brakeTurnControl.brake = 1.0f;
    for (int i = 0; i < 18; ++i) {
        const ArcadeVehicleTelemetry telemetry = stepArcadeVehicle(brakeTurn, config, brakeTurnControl, road, kInternalStep);
        result.brakeOversteerPeakYaw = std::max(result.brakeOversteerPeakYaw, std::abs(telemetry.yawRate));
        result.brakeOversteerPeakSlip = std::max(result.brakeOversteerPeakSlip, std::abs(telemetry.slipAngle));
    }
    brakeTurnControl.brake = 0.0f;
    for (int i = 0; i < 102; ++i) {
        const ArcadeVehicleTelemetry telemetry = stepArcadeVehicle(brakeTurn, config, brakeTurnControl, road, kInternalStep);
        result.brakeOversteerPeakYaw = std::max(result.brakeOversteerPeakYaw, std::abs(telemetry.yawRate));
        result.brakeOversteerPeakSlip = std::max(result.brakeOversteerPeakSlip, std::abs(telemetry.slipAngle));
    }
    ArcadeVehicleControl recoverControl;
    recoverControl.throttle = 1.0f;
    recoverControl.steer = -0.16f;
    for (int i = 0; i < 120; ++i) {
        stepArcadeVehicle(brakeTurn, config, recoverControl, road, kInternalStep);
    }
    result.brakeRecoverySlip = std::abs(brakeTurn.slipAngle);
    check(result.brakeOversteerPeakYaw > 0.45f &&
          result.brakeOversteerPeakYaw <= config.maxYawRateHighSpeed * config.brakeYawLimitScale + 0.02f);
    check(result.brakeOversteerPeakSlip > 0.02f && result.brakeOversteerPeakSlip < 0.18f);
    check(result.brakeRecoverySlip < 0.06f);

    std::array<float, 3> modulatedBrakeSpeeds{};
    constexpr std::array<float, 3> kBrakeInputs = {0.25f, 0.60f, 1.0f};
    for (size_t inputIndex = 0; inputIndex < kBrakeInputs.size(); ++inputIndex) {
        ArcadeVehicleState modulatedBrake;
        modulatedBrake.vel = {120.0f, 0.0f};
        ArcadeVehicleControl modulatedControl;
        modulatedControl.brake = kBrakeInputs[inputIndex];
        for (int i = 0; i < 60; ++i) {
            stepArcadeVehicle(modulatedBrake, config, modulatedControl, road, kInternalStep);
        }
        modulatedBrakeSpeeds[inputIndex] = std::max(0.0f, modulatedBrake.forwardSpeed);
    }
    check(modulatedBrakeSpeeds[0] > modulatedBrakeSpeeds[1] && modulatedBrakeSpeeds[1] > modulatedBrakeSpeeds[2]);

    ArcadeVehicleState brakeRelease;
    brakeRelease.vel = {90.0f, 0.0f};
    for (int i = 0; i < 30; ++i) {
        stepArcadeVehicle(brakeRelease, config, brakeControl, road, kInternalStep);
    }
    for (int i = 0; i < 240; ++i) {
        stepArcadeVehicle(brakeRelease, config, throttle, road, kInternalStep);
    }
    result.brakeLoadAfterRelease = brakeRelease.brakeLoad;
    check(result.brakeLoadAfterRelease < 0.01f);

    const JumpScriptResult jump120 = simulateJump(1.0f / 120.0f);
    const JumpScriptResult jump60 = simulateJump(1.0f / 60.0f);
    result.jumpApex = jump120.apex;
    result.jumpAirTime = jump120.airTime;
    result.jumpLandingImpulse = jump120.landingImpulse;
    result.jumpNoseUpPitch = jump120.noseUpPitch;
    result.jumpNoseDownPitch = jump120.noseDownPitch;
    result.jumpFixedStepError = std::abs(jump120.apex - jump60.apex) + std::abs(jump120.airTime - jump60.airTime);
    check(result.jumpApex > 7.0f);
    check(result.jumpAirTime > 0.70f && result.jumpAirTime < 1.25f);
    check(result.jumpLandingImpulse > 30.0f);
    check(result.jumpNoseUpPitch < -0.08f);
    check(result.jumpNoseDownPitch > 0.08f);
    check(jump120.state.grounded && jump60.state.grounded);
    check(result.jumpFixedStepError < 0.75f);

    const ArcadeVehicleState at120 = simulateScript(1.0f / 120.0f, 6.0f);
    const ArcadeVehicleState at60 = simulateScript(1.0f / 60.0f, 6.0f);
    result.fixedStepPositionError = length(at120.pos - at60.pos);
    check(result.fixedStepPositionError < 0.05f);
    check(std::abs(wrapAngle(at120.heading - at60.heading)) < 0.002f);

    result.ok = result.failures == 0;
    return result;
}
