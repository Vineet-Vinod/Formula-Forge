#pragma once

#include <array>
#include <cstdint>

#include "core_math.hpp"

enum class ArcadeDriftPhase : uint8_t {
    Grip,
    Entry,
    Sustain,
    Exit,
};

struct ArcadeVehicleState {
    Vec2 pos{};
    Vec2 vel{};
    float heading = 0.0f;

    // These names intentionally match the current kart state so Kart3D can
    // inherit this type while the renderer and contact solver are migrated.
    float steerSmoothed = 0.0f;
    bool drifting = false;
    float driftDir = 1.0f;
    float driftCharge = 0.0f;
    float boostTimer = 0.0f;
    float boostPower = 0.0f;
    float brakeHold = 0.0f;
    float contactTimer = 0.0f;

    float steerAngle = 0.0f;
    float yawRate = 0.0f;
    ArcadeDriftPhase driftPhase = ArcadeDriftPhase::Grip;
    float driftPhaseTime = 0.0f;
    float driftCooldown = 0.0f;
    bool driftInputHeld = false;
    bool driftInputConsumed = false;

    float forwardSpeed = 0.0f;
    float lateralSpeed = 0.0f;
    float slipAngle = 0.0f;
    float engineLoad = 0.0f;
    int gear = 1;
    float engineRpmNormalized = 0.333f;
    float shiftTimer = 0.0f;
    float shiftRejectTimer = 0.0f;
    int queuedManualShifts = 0;
    float engineBrakingApplied = 0.0f;
    float aerodynamicDragApplied = 0.0f;
    float rollingResistanceApplied = 0.0f;
    float tireLongitudinalUsage = 0.0f;
    float tractionUtilization = 0.0f;
    float distanceTravelled = 0.0f;
    float wheelSpin = 0.0f;

    float suspensionCompression = 0.0f;
    float suspensionVelocity = 0.0f;
    float elevation = 0.0f;
    float verticalSpeed = 0.0f;
    float airborneTime = 0.0f;
    float landingImpulse = 0.0f;
    float launchCooldown = 0.0f;
    bool grounded = true;

    float brakeLoad = 0.0f;
    float brakeSlip = 0.0f;
    float bodyPitch = 0.0f;
    float bodyPitchVelocity = 0.0f;
    float bodyRoll = 0.0f;
    float bodyRollVelocity = 0.0f;
};

struct ArcadeVehicleConfig {
    float maxForwardSpeed = 200.0f;
    float maxReverseSpeed = 42.0f;
    float engineAcceleration = 96.0f;
    float launchAccelerationBonus = 34.0f;
    float brakeDeceleration = 190.0f;
    float brakeLowSpeedScale = 1.0f;
    float brakeFullEffectSpeed = 1.0f;
    float brakeSpeedCurveExponent = 1.0f;
    float reverseAcceleration = 58.0f;
    float reverseDelay = 0.22f;
    float rollingResistance = 3.8f;
    float aerodynamicDrag = 0.00038f;
    float overspeedResponse = 4.5f;
    std::array<float, 8> gearRedlineSpeedRatios = {0.352f, 0.456f, 0.560f, 0.663f, 0.767f, 0.862f, 0.953f, 1.038f};
    std::array<float, 8> gearDriveScales = {1.08f, 1.05f, 1.03f, 1.01f, 1.00f, 0.99f, 0.98f, 0.97f};
    float idleRpmNormalized = 0.333f;
    float redlineRpm = 12000.0f;
    float automaticUpshiftRpm = 0.96f;
    float automaticDownshiftRpm = 0.50f;
    float automaticBrakingDownshiftRpm = 0.50f;
    float downshiftOverrevRpm = 1.08f;
    float manualDownshiftOverrevRpm = 1.08f;
    float shiftDuration = 0.075f;
    float shiftRejectDuration = 0.28f;
    float engineBrakingAcceleration = 18.0f;
    float engineBrakingLowGearScale = 1.20f;
    float engineBrakingHighGearScale = 0.52f;

    float wheelbase = 38.0f;
    float wheelRadius = 8.0f;
    float maxSteerLowSpeed = 0.58f;
    float maxSteerHighSpeed = 0.25f;
    float steerFadeStart = 0.18f;
    float steerResponse = 9.5f;
    float steerReturnResponse = 13.0f;
    float yawResponseGrip = 8.5f;
    float yawResponseDrift = 6.0f;
    float yawResponseExit = 11.0f;
    float maxYawRateLowSpeed = 2.8f;
    float maxYawRateHighSpeed = 1.50f;

    float brakeLoadResponse = 16.0f;
    float brakeReleaseResponse = 8.0f;
    float brakeOversteerMinSpeed = 32.0f;
    float brakeOversteerFullSpeed = 0.0f;
    float brakeOversteerSteerThreshold = 0.18f;
    float brakeOversteerYawGain = 1.35f;
    float brakeYawLimitScale = 1.08f;
    float brakeOversteerSlip = 0.22f;
    float brakeSlipResponse = 10.0f;
    float brakeSlipRecovery = 12.0f;
    float throttleCatchStrength = 0.0f;
    float throttleCatchSlipRecovery = 12.0f;
    float throttleCatchYawResponse = 8.5f;
    float throttleCatchLateralResponse = 14.0f;
    float throttleCatchDriveScale = 1.0f;
    float accelerationGripUsageScale = 1.0f;
    float driftBrakeDecelerationScale = 0.62f;

    float lateralGripAcceleration = 310.0f;
    float lateralGripResponse = 14.0f;
    float downforceGripGain = 0.48f;
    float tireLimitedYawScale = 0.92f;
    float combinedGripExponent = 2.20f;
    float combinedGripFloor = 0.30f;
    float trailBrakeTurnInGain = 0.13f;
    float driftGripAcceleration = 240.0f;
    float driftLateralResponse = 3.8f;

    float driftMinEntrySpeed = 48.0f;
    float driftMinSustainSpeed = 30.0f;
    float driftEntrySteer = 0.20f;
    float driftEntryDuration = 0.12f;
    float driftExitDuration = 0.20f;
    float driftReentryCooldown = 0.10f;
    float driftSlipBase = 0.17f;
    float driftSlipExtra = 0.14f;
    float driftCountersteerRecovery = 0.58f;
    float driftYawBase = 0.95f;
    float driftYawSpeedGain = 0.55f;
    float driftBaseDrag = 3.0f;
    float driftAngleDrag = 11.0f;
    float driftChargeRate = 1.0f;
    float driftChargeMinSlip = 0.09f;
    float driftChargeMaxSlip = 0.52f;

    float tierOneCharge = 0.45f;
    float tierTwoCharge = 1.00f;
    float tierThreeCharge = 1.65f;
    float tierOneBoostDuration = 0.48f;
    float tierTwoBoostDuration = 0.78f;
    float tierThreeBoostDuration = 1.10f;
    float tierOneBoostPower = 0.35f;
    float tierTwoBoostPower = 0.65f;
    float tierThreeBoostPower = 1.0f;
    float boostAcceleration = 72.0f;
    float boostSpeedExtraBase = 0.09f;
    float boostSpeedExtraPower = 0.13f;

    float suspensionFrequency = 5.0f;
    float suspensionDamping = 0.90f;
    float bodyFrequency = 4.5f;
    float bodyDamping = 0.88f;
    float maxBodyPitch = 0.085f;
    float maxBrakePitch = 0.16f;
    float maxBodyRoll = 0.12f;
    float maxAirPitchUp = 0.34f;
    float maxAirPitchDown = 0.42f;
    float airPitchFrequency = 3.8f;
    float landingPitchScale = 0.0032f;
    float maxLandingPitch = 0.14f;

    float gravity = 94.0f;
    float airControlScale = 0.26f;
    float airDriveScale = 0.12f;
    float landingImpulseDecay = 32.0f;
    float landingCompressionScale = 0.032f;
    float launchCooldown = 0.55f;
};

struct ArcadeVehicleControl {
    float steer = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
    bool drift = false;
    // Optional explicit rising edge. Keep drift=true on the same frame.
    bool driftPressed = false;
    bool shiftUpPressed = false;
    bool shiftDownPressed = false;
    bool automaticShift = true;
};

struct ArcadeSurface {
    float grip = 1.0f;
    float acceleration = 1.0f;
    float rollingResistance = 1.0f;
    float steering = 1.0f;
    float maxSpeed = 1.0f;
    float driftCharge = 1.0f;
    float bumpiness = 0.0f;
    float groundElevation = 0.0f;
    float groundGrade = 0.0f;
    float launchVelocity = 0.0f;
    bool allowsDrift = true;
};

struct ArcadeVehicleTelemetry {
    float forwardSpeed = 0.0f;
    float lateralSpeed = 0.0f;
    float speed = 0.0f;
    float normalizedSpeed = 0.0f;
    float slipAngle = 0.0f;
    float steerAngle = 0.0f;
    float yawRate = 0.0f;
    float longitudinalAcceleration = 0.0f;
    float lateralAcceleration = 0.0f;
    float distanceDelta = 0.0f;
    float peakSlipAngle = 0.0f;
    float tractionUtilization = 0.0f;
    float elevation = 0.0f;
    float verticalSpeed = 0.0f;
    float airborneTime = 0.0f;
    float landingImpulse = 0.0f;
    float brakeLoad = 0.0f;
    int gear = 1;
    float engineRpmNormalized = 0.0f;
    float shiftRemainingSeconds = 0.0f;
    bool shiftRejected = false;
    float engineBrakingAcceleration = 0.0f;
    float aerodynamicDragAcceleration = 0.0f;
    float rollingResistanceAcceleration = 0.0f;
    float tireLongitudinalUsage = 0.0f;
    bool grounded = true;
    ArcadeDriftPhase driftPhase = ArcadeDriftPhase::Grip;
    int driftTier = 0;
    int boostTierAwarded = 0;
    bool boostActive = false;
};

struct ArcadeVehicleAuditResult {
    bool ok = false;
    int checks = 0;
    int failures = 0;
    float restHeadingError = 0.0f;
    float straightLineSpeed = 0.0f;
    float stoppedSpeed = 0.0f;
    float momentumError = 0.0f;
    float lowSpeedSteerAngle = 0.0f;
    float highSpeedSteerAngle = 0.0f;
    float driftPeakSlip = 0.0f;
    int driftBoostTier = 0;
    float looseSurfaceSpeedRatio = 0.0f;
    float shoulderSpeedRatio = 0.0f;
    float firstGearLimitedSpeed = 0.0f;
    int automaticTopGear = 0;
    int rejectedDownshiftGear = 0;
    float lowGearCoastLoss = 0.0f;
    float highGearCoastLoss = 0.0f;
    float fixedStepPositionError = 0.0f;
    float brakeOversteerPeakYaw = 0.0f;
    float brakeOversteerPeakSlip = 0.0f;
    float brakeRecoverySlip = 0.0f;
    float brakeLoadAfterRelease = 0.0f;
    float jumpApex = 0.0f;
    float jumpAirTime = 0.0f;
    float jumpLandingImpulse = 0.0f;
    float jumpNoseUpPitch = 0.0f;
    float jumpNoseDownPitch = 0.0f;
    float jumpFixedStepError = 0.0f;
};

int arcadeDriftTier(float charge, const ArcadeVehicleConfig& config);
int arcadeRecommendedGear(float absForwardSpeed, const ArcadeVehicleConfig& config);
void syncArcadeTransmissionToSpeed(ArcadeVehicleState& state, const ArcadeVehicleConfig& config);

ArcadeVehicleTelemetry stepArcadeVehicle(ArcadeVehicleState& state,
                                         const ArcadeVehicleConfig& config,
                                         const ArcadeVehicleControl& control,
                                         const ArcadeSurface& surface,
                                         float dt);

ArcadeVehicleAuditResult runArcadeVehicleUnitAudit();
