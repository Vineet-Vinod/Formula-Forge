#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

enum class ArcadeRacePhase : uint8_t {
    Grid,
    Countdown,
    Racing,
    Finished,
};

enum class ArcadeRaceEventType : uint8_t {
    CheckpointValidated,
    LapCompleted,
    RacerFinished,
    WrongWayStarted,
    WrongWayCleared,
};

struct ArcadeCheckpointGate {
    float normalizedProgress = 0.0f;
    // A negative value uses normalizedProgress as the reset location.
    float resetNormalizedProgress = -1.0f;
};

struct ArcadeRaceConfig {
    // Gate zero is the start/finish line. All other gates must be strictly
    // increasing around the normalized [0, 1) track domain. The start gate
    // itself may be anywhere in that domain.
    std::vector<ArcadeCheckpointGate> checkpointGates = {
        {0.0f, 0.0f},
        {0.25f, 0.25f},
        {0.5f, 0.5f},
        {0.75f, 0.75f},
    };

    uint32_t lapCount = 3;
    bool infiniteLaps = false;
    float countdownSeconds = 3.0f;

    // Samples farther apart than this are treated as projection teleports and
    // cannot validate checkpoints. It must be in (0, 0.5).
    float maxAcceptedProgressDelta = 0.35f;
    float minimumCheckpointForwardAlignment = -0.2f;

    float wrongWayEnterAlignment = -0.4f;
    float wrongWayExitAlignment = 0.15f;
    // Movement below this many laps per second is treated as stationary.
    float wrongWayMinimumProgressRate = 0.002f;
    float wrongWayEnterSeconds = 0.65f;
    float wrongWayExitSeconds = 0.25f;
};

struct ArcadeRacerInput {
    float normalizedTrackProgress = 0.0f;
    // Dot product of kart forward and the forward track tangent, in [-1, 1].
    float forwardAlignment = 1.0f;
};

struct ArcadeCheckpointResetInfo {
    bool valid = false;
    std::size_t checkpointIndex = 0;
    float normalizedTrackProgress = 0.0f;
    uint32_t completedLaps = 0;
};

struct ArcadeRacerRaceState {
    bool sampleInitialized = false;
    bool sampleDiscontinuity = false;
    float normalizedTrackProgress = 0.0f;
    float forwardAlignment = 1.0f;

    // An unwrapped, signed track coordinate. It increases through 1.0 at a
    // forward start-line crossing and decreases while travelling backwards.
    double continuousTrackProgress = 0.0;
    // Checkpoint-bounded race distance used for ordering racers. It cannot
    // advance beyond the next checkpoint until that checkpoint is validated.
    double validatedRaceProgress = 0.0;

    uint32_t completedLaps = 0;
    std::size_t nextCheckpointIndex = 1;
    std::size_t lastValidCheckpointIndex = 0;
    ArcadeCheckpointResetInfo lastValidReset{};

    bool wrongWay = false;
    float wrongWayEvidenceSeconds = 0.0f;
    bool finished = false;
    double finishTimeSeconds = -1.0;
    uint32_t finishOrder = 0;
};

struct ArcadeRaceEvent {
    ArcadeRaceEventType type = ArcadeRaceEventType::CheckpointValidated;
    std::size_t racerIndex = 0;
    std::size_t checkpointIndex = 0;
    uint32_t completedLaps = 0;
    uint32_t finishOrder = 0;
    double raceTimeSeconds = 0.0;
};

bool isArcadeRaceConfigValid(const ArcadeRaceConfig& config);

class ArcadeRaceFlow {
  public:
    explicit ArcadeRaceFlow(ArcadeRaceConfig config, std::size_t racerCount);

    void reset();
    // Both transitions require every racer to have a baseline sample, supplied
    // by update() while on the Grid or by rebaseRacerSample().
    bool beginCountdown();
    bool beginRace();
    void finishRace();

    // Inputs are indexed exactly like racers. Returns false without changing
    // state when dt/input is invalid or the count is wrong.
    bool update(float dt, std::span<const ArcadeRacerInput> inputs);

    // Re-anchors track sampling after a teleport/respawn without treating the
    // relocation as race movement. Checkpoint and lap state are preserved.
    bool rebaseRacerSample(std::size_t racerIndex, const ArcadeRacerInput& input);

    const ArcadeRaceConfig& config() const { return config_; }
    ArcadeRacePhase phase() const { return phase_; }
    double raceTimeSeconds() const { return raceTimeSeconds_; }
    float countdownRemainingSeconds() const { return countdownRemainingSeconds_; }
    std::size_t racerCount() const { return racers_.size(); }
    uint32_t finishCount() const { return finishCount_; }

    const ArcadeRacerRaceState& racer(std::size_t racerIndex) const;
    ArcadeCheckpointResetInfo lastValidReset(std::size_t racerIndex) const;
    std::span<const ArcadeRaceEvent> events() const { return events_; }

  private:
    struct RacerRuntime {
        ArcadeRacerRaceState state{};
        float previousNormalizedProgress = 0.0f;
        double continuousAtLastCheckpoint = 0.0;
    };

    ArcadeRaceConfig config_;
    ArcadeRacePhase phase_ = ArcadeRacePhase::Grid;
    double raceTimeSeconds_ = 0.0;
    float countdownRemainingSeconds_ = 0.0f;
    uint32_t finishCount_ = 0;
    std::vector<RacerRuntime> racers_;
    std::vector<ArcadeRaceEvent> events_;

    void synchronizePreRaceSample(RacerRuntime& racer, const ArcadeRacerInput& input);
    void processRacer(std::size_t racerIndex,
                      const ArcadeRacerInput& input,
                      float dt,
                      double frameStartTime);
    void updateWrongWay(std::size_t racerIndex,
                        float alignment,
                        float signedProgressDelta,
                        float dt,
                        double frameStartTime);
    void updateValidatedProgress(RacerRuntime& racer);
    void sortEventsAndAssignFinishOrder();
    bool allRacersInitialized() const;
};

struct ArcadeRaceAuditResult {
    bool ok = false;
    int checks = 0;
    int failures = 0;
    bool phasesValid = false;
    bool checkpointsValid = false;
    bool wrongWayValid = false;
    bool finishOrderingValid = false;
    bool infiniteModeValid = false;
    bool discontinuityGuardValid = false;
    double firstPlaceFinishTime = 0.0;
    double secondPlaceFinishTime = 0.0;
};

// Deterministic, dependency-free behavioral audit. It performs no I/O and
// mutates no external state.
ArcadeRaceAuditResult runArcadeRaceUnitAudit();
