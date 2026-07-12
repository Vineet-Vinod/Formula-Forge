#pragma once

#include <cstdint>
#include <memory>

struct ArcadeAudioInput {
    float speedNormalized = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
    float slip = 0.0f;
    bool grounded = true;
    float landingImpulse = 0.0f;
    float deltaTime = 1.0f / 120.0f;
};

struct ArcadeAudioAuditResult {
    bool ok = false;
    int checks = 0;
    int failures = 0;
    float idleRms = 0.0f;
    float fullSpeedRms = 0.0f;
    float scrubRmsIncrease = 0.0f;
    float landingPeak = 0.0f;
    float peakMagnitude = 0.0f;
    uint64_t deterministicHash = 0;
};

// Owns a procedural stereo soundscape. All methods are safe to call when an
// audio device is unavailable, and initialize()/shutdown() are idempotent.
class ArcadeAudio {
  public:
    ArcadeAudio();
    ~ArcadeAudio();

    ArcadeAudio(const ArcadeAudio&) = delete;
    ArcadeAudio& operator=(const ArcadeAudio&) = delete;
    ArcadeAudio(ArcadeAudio&&) noexcept;
    ArcadeAudio& operator=(ArcadeAudio&&) noexcept;

    bool initialize();
    void shutdown();
    void update(const ArcadeAudioInput& input);
    void setMasterVolume(float volume);

    [[nodiscard]] bool isReady() const;

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

ArcadeAudioAuditResult runArcadeAudioUnitAudit();
