#include "arcade_race.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace {

constexpr float kGateEpsilon = 0.00001f;

float wrapNormalized(float value) {
    value -= std::floor(value);
    return value < 0.0f ? value + 1.0f : value;
}

float signedProgressDelta(float from, float to) {
    float delta = wrapNormalized(to) - wrapNormalized(from);
    if (delta >= 0.5f) {
        delta -= 1.0f;
    } else if (delta < -0.5f) {
        delta += 1.0f;
    }
    return delta;
}

float forwardProgressDistance(float from, float to) {
    float distance = wrapNormalized(to) - wrapNormalized(from);
    if (distance < 0.0f) {
        distance += 1.0f;
    }
    return distance;
}

float resetProgress(const ArcadeCheckpointGate& gate) {
    return gate.resetNormalizedProgress < 0.0f ? gate.normalizedProgress : gate.resetNormalizedProgress;
}

bool finiteAndInRange(float value, float low, float high) {
    return std::isfinite(value) && value >= low && value <= high;
}

int eventPriority(ArcadeRaceEventType type) {
    switch (type) {
        case ArcadeRaceEventType::CheckpointValidated:
            return 0;
        case ArcadeRaceEventType::LapCompleted:
            return 1;
        case ArcadeRaceEventType::RacerFinished:
            return 2;
        case ArcadeRaceEventType::WrongWayStarted:
            return 3;
        case ArcadeRaceEventType::WrongWayCleared:
            return 4;
    }
    return 5;
}

}  // namespace

bool isArcadeRaceConfigValid(const ArcadeRaceConfig& config) {
    if (config.checkpointGates.size() < 2 || (!config.infiniteLaps && config.lapCount == 0) ||
        !std::isfinite(config.countdownSeconds) || config.countdownSeconds < 0.0f ||
        !std::isfinite(config.maxAcceptedProgressDelta) || config.maxAcceptedProgressDelta <= 0.0f ||
        config.maxAcceptedProgressDelta >= 0.5f ||
        !finiteAndInRange(config.minimumCheckpointForwardAlignment, -1.0f, 1.0f) ||
        !finiteAndInRange(config.wrongWayEnterAlignment, -1.0f, 1.0f) ||
        !finiteAndInRange(config.wrongWayExitAlignment, -1.0f, 1.0f) ||
        config.wrongWayEnterAlignment >= config.wrongWayExitAlignment ||
        !std::isfinite(config.wrongWayMinimumProgressRate) || config.wrongWayMinimumProgressRate <= 0.0f ||
        !std::isfinite(config.wrongWayEnterSeconds) || config.wrongWayEnterSeconds < 0.0f ||
        !std::isfinite(config.wrongWayExitSeconds) || config.wrongWayExitSeconds < 0.0f) {
        return false;
    }

    const float startProgress = config.checkpointGates.front().normalizedProgress;
    float previousOffset = -1.0f;
    for (std::size_t i = 0; i < config.checkpointGates.size(); ++i) {
        const ArcadeCheckpointGate& gate = config.checkpointGates[i];
        if (!std::isfinite(gate.normalizedProgress) || gate.normalizedProgress < 0.0f ||
            gate.normalizedProgress >= 1.0f) {
            return false;
        }
        if (!std::isfinite(gate.resetNormalizedProgress) ||
            (gate.resetNormalizedProgress >= 0.0f && gate.resetNormalizedProgress >= 1.0f)) {
            return false;
        }
        const float offset = i == 0 ? 0.0f : forwardProgressDistance(startProgress, gate.normalizedProgress);
        if (offset <= previousOffset + kGateEpsilon || (i > 0 && offset >= 1.0f - kGateEpsilon)) {
            return false;
        }
        previousOffset = offset;
    }
    return true;
}

ArcadeRaceFlow::ArcadeRaceFlow(ArcadeRaceConfig config, std::size_t racerCount)
    : config_(std::move(config)), racers_(racerCount) {
    if (!isArcadeRaceConfigValid(config_)) {
        throw std::invalid_argument("invalid arcade race configuration");
    }
    if (racerCount == 0) {
        throw std::invalid_argument("an arcade race needs at least one racer");
    }
    reset();
}

void ArcadeRaceFlow::reset() {
    phase_ = ArcadeRacePhase::Grid;
    raceTimeSeconds_ = 0.0;
    countdownRemainingSeconds_ = config_.countdownSeconds;
    finishCount_ = 0;
    events_.clear();

    for (RacerRuntime& racer : racers_) {
        racer = {};
        racer.state.nextCheckpointIndex = 1;
        racer.state.lastValidCheckpointIndex = 0;
        racer.state.lastValidReset = {
            true,
            0,
            resetProgress(config_.checkpointGates.front()),
            0,
        };
    }
}

bool ArcadeRaceFlow::beginCountdown() {
    if (phase_ != ArcadeRacePhase::Grid || !allRacersInitialized()) {
        return false;
    }
    countdownRemainingSeconds_ = config_.countdownSeconds;
    phase_ = countdownRemainingSeconds_ > 0.0f ? ArcadeRacePhase::Countdown : ArcadeRacePhase::Racing;
    return true;
}

bool ArcadeRaceFlow::beginRace() {
    if ((phase_ != ArcadeRacePhase::Grid && phase_ != ArcadeRacePhase::Countdown) ||
        !allRacersInitialized()) {
        return false;
    }
    countdownRemainingSeconds_ = 0.0f;
    phase_ = ArcadeRacePhase::Racing;
    return true;
}

void ArcadeRaceFlow::finishRace() {
    if (phase_ != ArcadeRacePhase::Finished) {
        phase_ = ArcadeRacePhase::Finished;
        countdownRemainingSeconds_ = 0.0f;
    }
}

const ArcadeRacerRaceState& ArcadeRaceFlow::racer(std::size_t racerIndex) const {
    return racers_.at(racerIndex).state;
}

ArcadeCheckpointResetInfo ArcadeRaceFlow::lastValidReset(std::size_t racerIndex) const {
    return racers_.at(racerIndex).state.lastValidReset;
}

void ArcadeRaceFlow::synchronizePreRaceSample(RacerRuntime& racer, const ArcadeRacerInput& input) {
    const float progress = wrapNormalized(input.normalizedTrackProgress);
    const float startProgress = config_.checkpointGates.front().normalizedProgress;
    racer.state.sampleInitialized = true;
    racer.state.sampleDiscontinuity = false;
    racer.state.normalizedTrackProgress = progress;
    racer.state.forwardAlignment = std::clamp(input.forwardAlignment, -1.0f, 1.0f);
    racer.previousNormalizedProgress = progress;
    racer.state.continuousTrackProgress = signedProgressDelta(startProgress, progress);
    racer.continuousAtLastCheckpoint = 0.0;
    updateValidatedProgress(racer);
}

bool ArcadeRaceFlow::rebaseRacerSample(std::size_t racerIndex, const ArcadeRacerInput& input) {
    if (racerIndex >= racers_.size() || !std::isfinite(input.normalizedTrackProgress) ||
        !std::isfinite(input.forwardAlignment)) {
        return false;
    }

    RacerRuntime& racer = racers_[racerIndex];
    const float progress = wrapNormalized(input.normalizedTrackProgress);
    if (!racer.state.sampleInitialized || phase_ == ArcadeRacePhase::Grid || phase_ == ArcadeRacePhase::Countdown) {
        synchronizePreRaceSample(racer, input);
        return true;
    }

    const float lastGate = config_.checkpointGates[racer.state.lastValidCheckpointIndex].normalizedProgress;
    const float nextGate = config_.checkpointGates[racer.state.nextCheckpointIndex].normalizedProgress;
    const double segmentLength = forwardProgressDistance(lastGate, nextGate);
    const double forwardOffset = forwardProgressDistance(lastGate, progress);
    const double offset = forwardOffset <= segmentLength + kGateEpsilon
                              ? forwardOffset
                              : -static_cast<double>(forwardProgressDistance(progress, lastGate));
    racer.state.continuousTrackProgress = racer.continuousAtLastCheckpoint + offset;
    racer.previousNormalizedProgress = progress;
    racer.state.normalizedTrackProgress = progress;
    racer.state.forwardAlignment = std::clamp(input.forwardAlignment, -1.0f, 1.0f);
    racer.state.sampleDiscontinuity = false;
    updateValidatedProgress(racer);
    return true;
}

void ArcadeRaceFlow::updateValidatedProgress(RacerRuntime& racer) {
    if (racer.state.finished && !config_.infiniteLaps) {
        racer.state.validatedRaceProgress = static_cast<double>(config_.lapCount);
        return;
    }

    const std::size_t lastIndex = racer.state.lastValidCheckpointIndex;
    const std::size_t nextIndex = racer.state.nextCheckpointIndex;
    const float lastProgress = config_.checkpointGates[lastIndex].normalizedProgress;
    const float nextProgress = config_.checkpointGates[nextIndex].normalizedProgress;
    const double segmentLength = forwardProgressDistance(lastProgress, nextProgress);
    const double segmentProgress = std::clamp(
        racer.state.continuousTrackProgress - racer.continuousAtLastCheckpoint, 0.0, segmentLength);
    const float startProgress = config_.checkpointGates.front().normalizedProgress;
    const double checkpointProgress = forwardProgressDistance(startProgress, lastProgress);
    racer.state.validatedRaceProgress = static_cast<double>(racer.state.completedLaps) +
                                         checkpointProgress + segmentProgress;
}

void ArcadeRaceFlow::updateWrongWay(std::size_t racerIndex,
                                    float alignment,
                                    float progressDelta,
                                    float dt,
                                    double frameStartTime) {
    RacerRuntime& racer = racers_[racerIndex];
    ArcadeRacerRaceState& state = racer.state;
    if (state.finished || dt <= 0.0f) {
        return;
    }

    const float progressRate = progressDelta / dt;
    const bool moving = std::abs(progressRate) >= config_.wrongWayMinimumProgressRate;
    const bool wrongDirection = progressRate <= -config_.wrongWayMinimumProgressRate;
    const bool movingWhileWrongFacing = moving && alignment <= config_.wrongWayEnterAlignment;
    const bool wrongWayEvidence = wrongDirection || movingWhileWrongFacing;

    if (!state.wrongWay) {
        if (wrongWayEvidence) {
            const float priorEvidence = state.wrongWayEvidenceSeconds;
            state.wrongWayEvidenceSeconds += dt;
            if (state.wrongWayEvidenceSeconds + kGateEpsilon >= config_.wrongWayEnterSeconds) {
                const float timeToThreshold = std::clamp(
                    config_.wrongWayEnterSeconds - priorEvidence, 0.0f, dt);
                state.wrongWay = true;
                state.wrongWayEvidenceSeconds = 0.0f;
                events_.push_back({ArcadeRaceEventType::WrongWayStarted,
                                   racerIndex,
                                   state.lastValidCheckpointIndex,
                                   state.completedLaps,
                                   0,
                                   frameStartTime + timeToThreshold});
            }
        } else {
            state.wrongWayEvidenceSeconds = 0.0f;
        }
        return;
    }

    const bool recoveryEvidence = !moving ||
                                  (progressRate >= config_.wrongWayMinimumProgressRate &&
                                   alignment >= config_.wrongWayExitAlignment);
    if (!wrongWayEvidence && recoveryEvidence) {
        const float priorEvidence = state.wrongWayEvidenceSeconds;
        state.wrongWayEvidenceSeconds += dt;
        if (state.wrongWayEvidenceSeconds + kGateEpsilon >= config_.wrongWayExitSeconds) {
            const float timeToThreshold = std::clamp(
                config_.wrongWayExitSeconds - priorEvidence, 0.0f, dt);
            state.wrongWay = false;
            state.wrongWayEvidenceSeconds = 0.0f;
            events_.push_back({ArcadeRaceEventType::WrongWayCleared,
                               racerIndex,
                               state.lastValidCheckpointIndex,
                               state.completedLaps,
                               0,
                               frameStartTime + timeToThreshold});
        }
    } else {
        state.wrongWayEvidenceSeconds = 0.0f;
    }
}

void ArcadeRaceFlow::processRacer(std::size_t racerIndex,
                                  const ArcadeRacerInput& input,
                                  float dt,
                                  double frameStartTime) {
    RacerRuntime& racer = racers_[racerIndex];
    ArcadeRacerRaceState& state = racer.state;
    const float progress = wrapNormalized(input.normalizedTrackProgress);
    const float alignment = std::clamp(input.forwardAlignment, -1.0f, 1.0f);

    if (!state.sampleInitialized) {
        synchronizePreRaceSample(racer, input);
        updateWrongWay(racerIndex, alignment, 0.0f, dt, frameStartTime);
        return;
    }

    state.normalizedTrackProgress = progress;
    state.forwardAlignment = alignment;
    if (state.finished) {
        racer.previousNormalizedProgress = progress;
        return;
    }

    const float delta = signedProgressDelta(racer.previousNormalizedProgress, progress);
    const float stepStartProgress = racer.previousNormalizedProgress;
    racer.previousNormalizedProgress = progress;

    if (std::abs(delta) > config_.maxAcceptedProgressDelta) {
        state.sampleDiscontinuity = true;
        updateWrongWay(racerIndex, alignment, 0.0f, dt, frameStartTime);
        return;
    }

    state.sampleDiscontinuity = false;
    const double stepStartContinuous = state.continuousTrackProgress;
    state.continuousTrackProgress += static_cast<double>(delta);

    if (delta > kGateEpsilon && alignment >= config_.minimumCheckpointForwardAlignment) {
        float cursor = stepStartProgress;
        float remaining = delta;
        float travelled = 0.0f;

        while (remaining > kGateEpsilon && !state.finished) {
            const std::size_t checkpointIndex = state.nextCheckpointIndex;
            const float checkpointProgress = config_.checkpointGates[checkpointIndex].normalizedProgress;
            float distance = forwardProgressDistance(cursor, checkpointProgress);
            // Being stationary on a gate cannot validate it on a later frame.
            if (distance <= kGateEpsilon) {
                distance = 1.0f;
            }
            if (distance > remaining + kGateEpsilon) {
                break;
            }

            travelled += distance;
            remaining = std::max(0.0f, remaining - distance);
            cursor = checkpointProgress;
            const double crossingTime = frameStartTime + dt *
                std::clamp(static_cast<double>(travelled / delta), 0.0, 1.0);
            racer.continuousAtLastCheckpoint = stepStartContinuous + travelled;
            state.lastValidCheckpointIndex = checkpointIndex;

            if (checkpointIndex == 0) {
                ++state.completedLaps;
                state.nextCheckpointIndex = 1;
            } else {
                state.nextCheckpointIndex = (checkpointIndex + 1) % config_.checkpointGates.size();
            }
            state.lastValidReset = {
                true,
                checkpointIndex,
                resetProgress(config_.checkpointGates[checkpointIndex]),
                state.completedLaps,
            };

            events_.push_back({ArcadeRaceEventType::CheckpointValidated,
                               racerIndex,
                               checkpointIndex,
                               state.completedLaps,
                               0,
                               crossingTime});

            if (checkpointIndex == 0) {
                events_.push_back({ArcadeRaceEventType::LapCompleted,
                                   racerIndex,
                                   checkpointIndex,
                                   state.completedLaps,
                                   0,
                                   crossingTime});
                if (!config_.infiniteLaps && state.completedLaps >= config_.lapCount) {
                    state.finished = true;
                    state.wrongWay = false;
                    state.wrongWayEvidenceSeconds = 0.0f;
                    state.finishTimeSeconds = crossingTime;
                    events_.push_back({ArcadeRaceEventType::RacerFinished,
                                       racerIndex,
                                       checkpointIndex,
                                       state.completedLaps,
                                       0,
                                       crossingTime});
                }
            }
        }
    }

    updateValidatedProgress(racer);
    updateWrongWay(racerIndex, alignment, delta, dt, frameStartTime);
}

bool ArcadeRaceFlow::allRacersInitialized() const {
    return std::all_of(racers_.begin(), racers_.end(), [](const RacerRuntime& racer) {
        return racer.state.sampleInitialized;
    });
}

void ArcadeRaceFlow::sortEventsAndAssignFinishOrder() {
    std::stable_sort(events_.begin(), events_.end(), [](const ArcadeRaceEvent& a, const ArcadeRaceEvent& b) {
        if (a.raceTimeSeconds != b.raceTimeSeconds) {
            return a.raceTimeSeconds < b.raceTimeSeconds;
        }
        if (a.racerIndex != b.racerIndex) {
            return a.racerIndex < b.racerIndex;
        }
        return eventPriority(a.type) < eventPriority(b.type);
    });

    for (ArcadeRaceEvent& event : events_) {
        if (event.type != ArcadeRaceEventType::RacerFinished) {
            continue;
        }
        event.finishOrder = ++finishCount_;
        racers_[event.racerIndex].state.finishOrder = event.finishOrder;
    }
}

bool ArcadeRaceFlow::update(float dt, std::span<const ArcadeRacerInput> inputs) {
    if (!std::isfinite(dt) || dt < 0.0f || inputs.size() != racers_.size()) {
        return false;
    }
    for (const ArcadeRacerInput& input : inputs) {
        if (!std::isfinite(input.normalizedTrackProgress) || !std::isfinite(input.forwardAlignment)) {
            return false;
        }
    }

    events_.clear();
    if (phase_ == ArcadeRacePhase::Finished) {
        return true;
    }
    if (phase_ == ArcadeRacePhase::Grid) {
        for (std::size_t i = 0; i < racers_.size(); ++i) {
            synchronizePreRaceSample(racers_[i], inputs[i]);
        }
        return true;
    }

    if (phase_ == ArcadeRacePhase::Racing && dt == 0.0f) {
        for (std::size_t i = 0; i < racers_.size(); ++i) {
            if (!racers_[i].state.sampleInitialized) {
                synchronizePreRaceSample(racers_[i], inputs[i]);
            }
        }
        return true;
    }

    float racingDt = dt;
    if (phase_ == ArcadeRacePhase::Countdown) {
        if (dt < countdownRemainingSeconds_) {
            countdownRemainingSeconds_ -= dt;
            for (std::size_t i = 0; i < racers_.size(); ++i) {
                synchronizePreRaceSample(racers_[i], inputs[i]);
            }
            return true;
        }

        racingDt = std::max(0.0f, dt - countdownRemainingSeconds_);
        const float inactiveFraction = dt > 0.0f ? (dt - racingDt) / dt : 1.0f;
        countdownRemainingSeconds_ = 0.0f;
        phase_ = ArcadeRacePhase::Racing;

        for (std::size_t i = 0; i < racers_.size(); ++i) {
            RacerRuntime& racer = racers_[i];
            if (!racer.state.sampleInitialized) {
                synchronizePreRaceSample(racer, inputs[i]);
                continue;
            }
            const float delta = signedProgressDelta(racer.previousNormalizedProgress,
                                                    inputs[i].normalizedTrackProgress);
            if (std::abs(delta) > config_.maxAcceptedProgressDelta || racingDt <= 0.0f) {
                synchronizePreRaceSample(racer, inputs[i]);
                continue;
            }
            ArcadeRacerInput startInput = inputs[i];
            startInput.normalizedTrackProgress = wrapNormalized(
                racer.previousNormalizedProgress + delta * inactiveFraction);
            synchronizePreRaceSample(racer, startInput);
        }
        if (racingDt <= 0.0f) {
            return true;
        }
    }

    const double frameStartTime = raceTimeSeconds_;
    for (std::size_t i = 0; i < racers_.size(); ++i) {
        processRacer(i, inputs[i], racingDt, frameStartTime);
    }
    sortEventsAndAssignFinishOrder();

    raceTimeSeconds_ = frameStartTime + racingDt;
    if (!config_.infiniteLaps && finishCount_ == racers_.size()) {
        phase_ = ArcadeRacePhase::Finished;
        double finalFinishTime = 0.0;
        for (const RacerRuntime& racer : racers_) {
            finalFinishTime = std::max(finalFinishTime, racer.state.finishTimeSeconds);
        }
        raceTimeSeconds_ = finalFinishTime;
    }
    return true;
}

ArcadeRaceAuditResult runArcadeRaceUnitAudit() {
    ArcadeRaceAuditResult result;
    const auto check = [&result](bool condition) {
        ++result.checks;
        if (!condition) {
            ++result.failures;
        }
        return condition;
    };

    ArcadeRaceConfig invalidConfig;
    invalidConfig.checkpointGates[2].normalizedProgress = 0.2f;
    check(!isArcadeRaceConfigValid(invalidConfig));

    ArcadeRaceConfig cyclicConfig;
    cyclicConfig.checkpointGates = {{0.75f, 0.75f}, {0.0f, 0.0f}, {0.25f, 0.25f}, {0.5f, 0.5f}};
    cyclicConfig.lapCount = 1;
    cyclicConfig.countdownSeconds = 0.0f;
    check(isArcadeRaceConfigValid(cyclicConfig));
    ArcadeRaceFlow cyclicRace(cyclicConfig, 1);
    ArcadeRacerInput cyclicInput{0.75f, 1.0f};
    cyclicRace.update(0.0f, std::span<const ArcadeRacerInput>(&cyclicInput, 1));
    cyclicRace.beginRace();
    for (float progress : {0.05f, 0.3f, 0.55f, 0.8f}) {
        cyclicInput.normalizedTrackProgress = progress;
        cyclicRace.update(0.1f, std::span<const ArcadeRacerInput>(&cyclicInput, 1));
    }
    check(cyclicRace.racer(0).finished && cyclicRace.racer(0).completedLaps == 1);

    ArcadeRaceFlow missingBaselineRace(ArcadeRaceConfig{}, 1);
    check(!missingBaselineRace.beginRace() && missingBaselineRace.phase() == ArcadeRacePhase::Grid);

    ArcadeRaceConfig phaseConfig;
    phaseConfig.countdownSeconds = 1.0f;
    ArcadeRaceFlow phaseRace(phaseConfig, 1);
    const ArcadeRacerInput startSample{0.98f, 1.0f};
    check(phaseRace.phase() == ArcadeRacePhase::Grid);
    check(phaseRace.update(0.0f, std::span<const ArcadeRacerInput>(&startSample, 1)));
    check(phaseRace.racer(0).continuousTrackProgress < 0.0);
    check(phaseRace.beginCountdown());
    check(phaseRace.update(0.5f, std::span<const ArcadeRacerInput>(&startSample, 1)));
    check(phaseRace.phase() == ArcadeRacePhase::Countdown);
    check(phaseRace.update(0.5f, std::span<const ArcadeRacerInput>(&startSample, 1)));
    result.phasesValid = check(phaseRace.phase() == ArcadeRacePhase::Racing &&
                               std::abs(phaseRace.raceTimeSeconds()) < 0.000001);

    ArcadeRaceConfig checkpointConfig;
    checkpointConfig.lapCount = 2;
    checkpointConfig.countdownSeconds = 0.0f;
    ArcadeRaceFlow checkpointRace(checkpointConfig, 1);
    ArcadeRacerInput checkpointInput{0.0f, 1.0f};
    checkpointRace.update(0.0f, std::span<const ArcadeRacerInput>(&checkpointInput, 1));
    checkpointRace.beginRace();
    for (float progress : {0.3f, 0.55f}) {
        checkpointInput.normalizedTrackProgress = progress;
        checkpointRace.update(0.1f, std::span<const ArcadeRacerInput>(&checkpointInput, 1));
    }
    const ArcadeCheckpointResetInfo midpointReset = checkpointRace.lastValidReset(0);
    check(midpointReset.valid && midpointReset.checkpointIndex == 2 &&
          std::abs(midpointReset.normalizedTrackProgress - 0.5f) < 0.0001f);
    for (float progress : {0.8f, 0.05f}) {
        checkpointInput.normalizedTrackProgress = progress;
        checkpointRace.update(0.1f, std::span<const ArcadeRacerInput>(&checkpointInput, 1));
    }
    check(checkpointRace.racer(0).completedLaps == 1 && !checkpointRace.racer(0).finished);
    check(checkpointRace.racer(0).continuousTrackProgress > 1.0);
    const bool normalLapValid = checkpointRace.racer(0).nextCheckpointIndex == 1 &&
                                checkpointRace.racer(0).lastValidCheckpointIndex == 0;

    ArcadeRaceConfig shortcutConfig;
    shortcutConfig.infiniteLaps = true;
    shortcutConfig.countdownSeconds = 0.0f;
    ArcadeRaceFlow shortcutRace(shortcutConfig, 1);
    ArcadeRacerInput shortcutInput{0.8f, 1.0f};
    shortcutRace.update(0.0f, std::span<const ArcadeRacerInput>(&shortcutInput, 1));
    shortcutRace.beginRace();
    shortcutInput.normalizedTrackProgress = 0.05f;
    shortcutRace.update(0.1f, std::span<const ArcadeRacerInput>(&shortcutInput, 1));
    const bool shortcutRejected = shortcutRace.racer(0).completedLaps == 0 &&
                                  shortcutRace.racer(0).nextCheckpointIndex == 1;
    result.checkpointsValid = check(normalLapValid && shortcutRejected);

    ArcadeRaceConfig wrongWayConfig;
    wrongWayConfig.infiniteLaps = true;
    wrongWayConfig.countdownSeconds = 0.0f;
    wrongWayConfig.wrongWayEnterSeconds = 0.2f;
    wrongWayConfig.wrongWayExitSeconds = 0.1f;
    ArcadeRaceFlow wrongWayRace(wrongWayConfig, 1);
    ArcadeRacerInput wrongWayInput{0.4f, -1.0f};
    wrongWayRace.update(0.0f, std::span<const ArcadeRacerInput>(&wrongWayInput, 1));
    wrongWayRace.beginRace();
    wrongWayInput.normalizedTrackProgress = 0.1f;
    wrongWayRace.update(0.3f, std::span<const ArcadeRacerInput>(&wrongWayInput, 1));
    const double singleStepEnterTime = wrongWayRace.events().empty()
                                           ? -1.0
                                           : wrongWayRace.events().back().raceTimeSeconds;
    const bool reverseDetected = wrongWayRace.racer(0).wrongWay &&
                                 std::abs(singleStepEnterTime - 0.2) < 0.00001;
    wrongWayInput.forwardAlignment = 1.0f;
    wrongWayRace.update(0.2f, std::span<const ArcadeRacerInput>(&wrongWayInput, 1));
    const double singleStepExitTime = wrongWayRace.events().empty()
                                          ? -1.0
                                          : wrongWayRace.events().back().raceTimeSeconds;

    ArcadeRaceFlow partitionedWrongWayRace(wrongWayConfig, 1);
    ArcadeRacerInput partitionedInput{0.4f, -1.0f};
    partitionedWrongWayRace.update(0.0f, std::span<const ArcadeRacerInput>(&partitionedInput, 1));
    partitionedWrongWayRace.beginRace();
    partitionedInput.normalizedTrackProgress = 0.25f;
    partitionedWrongWayRace.update(0.15f, std::span<const ArcadeRacerInput>(&partitionedInput, 1));
    partitionedInput.normalizedTrackProgress = 0.1f;
    partitionedWrongWayRace.update(0.15f, std::span<const ArcadeRacerInput>(&partitionedInput, 1));
    const double partitionedEnterTime = partitionedWrongWayRace.events().empty()
                                            ? -1.0
                                            : partitionedWrongWayRace.events().back().raceTimeSeconds;
    partitionedInput.forwardAlignment = 1.0f;
    partitionedWrongWayRace.update(0.05f, std::span<const ArcadeRacerInput>(&partitionedInput, 1));
    partitionedWrongWayRace.update(0.05f, std::span<const ArcadeRacerInput>(&partitionedInput, 1));
    const double partitionedExitTime = partitionedWrongWayRace.events().empty()
                                           ? -1.0
                                           : partitionedWrongWayRace.events().back().raceTimeSeconds;

    ArcadeRaceFlow stationaryRace(wrongWayConfig, 1);
    ArcadeRacerInput stationaryInput{0.0f, -1.0f};
    stationaryRace.update(0.0f, std::span<const ArcadeRacerInput>(&stationaryInput, 1));
    stationaryRace.beginRace();
    stationaryRace.update(1.0f, std::span<const ArcadeRacerInput>(&stationaryInput, 1));

    result.wrongWayValid = check(reverseDetected && !wrongWayRace.racer(0).wrongWay &&
                                 !partitionedWrongWayRace.racer(0).wrongWay &&
                                 !stationaryRace.racer(0).wrongWay &&
                                 std::abs(singleStepEnterTime - partitionedEnterTime) < 0.00001 &&
                                 std::abs(singleStepExitTime - partitionedExitTime) < 0.00001);

    ArcadeRaceConfig finishConfig;
    finishConfig.lapCount = 1;
    finishConfig.countdownSeconds = 0.0f;
    ArcadeRaceFlow finishRace(finishConfig, 2);
    ArcadeRacerInput finishInputs[2] = {{0.0f, 1.0f}, {0.0f, 1.0f}};
    finishRace.update(0.0f, finishInputs);
    finishRace.beginRace();
    for (float progress : {0.3f, 0.55f, 0.8f}) {
        finishInputs[0].normalizedTrackProgress = progress;
        finishInputs[1].normalizedTrackProgress = progress;
        finishRace.update(0.1f, finishInputs);
    }
    finishInputs[0].normalizedTrackProgress = 0.02f;
    finishInputs[1].normalizedTrackProgress = 0.10f;
    finishRace.update(0.1f, finishInputs);
    result.firstPlaceFinishTime = finishRace.racer(1).finishTimeSeconds;
    result.secondPlaceFinishTime = finishRace.racer(0).finishTimeSeconds;
    result.finishOrderingValid = check(finishRace.phase() == ArcadeRacePhase::Finished &&
                                       finishRace.racer(1).finishOrder == 1 &&
                                       finishRace.racer(0).finishOrder == 2 &&
                                       result.firstPlaceFinishTime < result.secondPlaceFinishTime);

    ArcadeRaceConfig infiniteConfig;
    infiniteConfig.infiniteLaps = true;
    infiniteConfig.countdownSeconds = 0.0f;
    ArcadeRaceFlow infiniteRace(infiniteConfig, 1);
    ArcadeRacerInput infiniteInput{0.0f, 1.0f};
    infiniteRace.update(0.0f, std::span<const ArcadeRacerInput>(&infiniteInput, 1));
    infiniteRace.beginRace();
    for (float progress : {0.3f, 0.55f, 0.8f, 0.05f}) {
        infiniteInput.normalizedTrackProgress = progress;
        infiniteRace.update(0.1f, std::span<const ArcadeRacerInput>(&infiniteInput, 1));
    }
    result.infiniteModeValid = check(infiniteRace.racer(0).completedLaps == 1 &&
                                     !infiniteRace.racer(0).finished &&
                                     infiniteRace.phase() == ArcadeRacePhase::Racing);

    ArcadeRaceConfig discontinuityConfig;
    discontinuityConfig.infiniteLaps = true;
    discontinuityConfig.countdownSeconds = 0.0f;
    discontinuityConfig.maxAcceptedProgressDelta = 0.2f;
    ArcadeRaceFlow discontinuityRace(discontinuityConfig, 1);
    ArcadeRacerInput discontinuityInput{0.0f, 1.0f};
    discontinuityRace.update(0.0f, std::span<const ArcadeRacerInput>(&discontinuityInput, 1));
    discontinuityRace.beginRace();
    discontinuityInput.normalizedTrackProgress = 0.3f;
    discontinuityRace.update(0.1f, std::span<const ArcadeRacerInput>(&discontinuityInput, 1));
    result.discontinuityGuardValid = check(discontinuityRace.racer(0).sampleDiscontinuity &&
                                            discontinuityRace.racer(0).nextCheckpointIndex == 1 &&
                                            std::abs(discontinuityRace.racer(0).continuousTrackProgress) < 0.000001);

    result.ok = result.failures == 0;
    return result;
}
