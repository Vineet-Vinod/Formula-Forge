#include "arcade_audio.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <utility>
#include <vector>

#include <SDL3/SDL.h>

namespace {

constexpr unsigned int kSampleRate = 48000;
constexpr unsigned int kChannels = 2;
constexpr std::size_t kFramesPerBuffer = 1024;
constexpr float kPi = 3.14159265358979323846f;

float clamp01(float value) {
    return std::clamp(std::isfinite(value) ? value : 0.0f, 0.0f, 1.0f);
}

float approach(float current, float target, float response, float dt) {
    const float blend = 1.0f - std::exp(-response * dt);
    return current + (target - current) * blend;
}

struct SynthControls {
    float speed = 0.0f;
    float rpm = 0.333f;
    float shift = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
    float slip = 0.0f;
    float grounded = 1.0f;
};

class ArcadeSynth {
  public:
    void setInput(const ArcadeAudioInput& input) {
        target_.speed = clamp01(input.speedNormalized);
        target_.rpm = std::clamp(std::isfinite(input.engineRpmNormalized) ? input.engineRpmNormalized : 0.333f,
                                 0.20f, 1.10f);
        target_.shift = input.shiftActive ? 1.0f : 0.0f;
        target_.throttle = clamp01(input.throttle);
        target_.brake = clamp01(input.brake);
        target_.slip = clamp01(std::abs(input.slip));
        target_.grounded = input.grounded ? 1.0f : 0.0f;

        if (input.shiftAlert && !wasShiftAlert_) {
            shiftAlertEnvelope_ = 1.0f;
            shiftAlertPhase_ = 0.0f;
        }
        wasShiftAlert_ = input.shiftAlert;

        const float impulse = std::max(0.0f, std::isfinite(input.landingImpulse) ? input.landingImpulse : 0.0f);
        const bool landed = input.grounded && !wasGrounded_;
        if ((landed || impulse > previousLandingImpulse_ + 2.0f) && impulse > 4.0f) {
            landingEnvelope_ = std::max(landingEnvelope_, clamp01(impulse / 80.0f));
            landingPhase_ = 0.0f;
        }
        previousLandingImpulse_ = impulse;
        wasGrounded_ = input.grounded;
    }

    void render(float* stereo, std::size_t frames) {
        if (stereo == nullptr) return;

        constexpr float dt = 1.0f / static_cast<float>(kSampleRate);
        for (std::size_t frame = 0; frame < frames; ++frame) {
            controls_.speed = approach(controls_.speed, target_.speed, 5.5f, dt);
            controls_.rpm = approach(controls_.rpm, target_.rpm, 18.0f, dt);
            controls_.shift = approach(controls_.shift, target_.shift, 28.0f, dt);
            controls_.throttle = approach(controls_.throttle, target_.throttle, 11.0f, dt);
            controls_.brake = approach(controls_.brake, target_.brake, 15.0f, dt);
            controls_.slip = approach(controls_.slip, target_.slip, 18.0f, dt);
            controls_.grounded = approach(controls_.grounded, target_.grounded, 25.0f, dt);

            const float load = clamp01((controls_.throttle * 0.82f + controls_.brake * 0.18f) *
                                       (1.0f - controls_.shift * 0.88f));
            const float rpm = clamp01(controls_.rpm);
            const float engineHz = 88.0f + rpm * 330.0f;
            enginePhase_ = wrapPhase(enginePhase_ + engineHz * dt);
            firingPhase_ = wrapPhase(firingPhase_ + engineHz * (3.01f + load * 0.08f) * dt);

            const float fundamental = std::sin(2.0f * kPi * enginePhase_);
            const float second = std::sin(4.0f * kPi * enginePhase_ + 0.18f);
            const float third = std::sin(6.0f * kPi * enginePhase_ + 0.47f);
            const float firing = std::tanh(std::sin(2.0f * kPi * firingPhase_) * (1.4f + load * 1.7f));
            const float loadFlutter = 0.94f + 0.06f * std::sin(2.0f * kPi * modulationPhase_);
            modulationPhase_ = wrapPhase(modulationPhase_ + (7.0f + rpm * 13.0f) * dt);
            const float engine = (fundamental * 0.36f + second * (0.17f + load * 0.10f) +
                                  third * (0.10f + rpm * 0.06f) + firing * 0.22f) *
                                 (0.13f + load * 0.12f + rpm * 0.060f) * loadFlutter;

            const float noise = randomBipolar();
            roadNoise_ += (noise - roadNoise_) * 0.055f;
            windNoise_ += (noise - windNoise_) * 0.008f;
            scrubNoise_ += (noise - scrubNoise_) * 0.31f;
            const float road = roadNoise_ * controls_.speed * controls_.grounded * 0.090f;
            const float wind = (noise - windNoise_) * controls_.speed * controls_.speed * 0.115f;
            const float scrubAmount = clamp01(controls_.slip * 1.35f + controls_.brake * controls_.speed * 0.55f);
            const float scrub = (noise - scrubNoise_ * 0.42f) * scrubAmount * controls_.grounded * 0.12f;

            landingPhase_ = wrapPhase(landingPhase_ + 58.0f * dt);
            const float thump = std::sin(2.0f * kPi * landingPhase_) * landingEnvelope_ * 0.48f;
            landingEnvelope_ *= 0.99908f;
            if (landingEnvelope_ < 0.00001f) landingEnvelope_ = 0.0f;

            shiftAlertPhase_ = wrapPhase(shiftAlertPhase_ + 1350.0f * dt);
            const float shiftBeep = std::sin(2.0f * kPi * shiftAlertPhase_) * shiftAlertEnvelope_ * 0.82f;
            const float shiftDuck = std::clamp(shiftAlertEnvelope_ * 0.88f, 0.0f, 0.78f);
            shiftAlertEnvelope_ *= 0.99940f;
            if (shiftAlertEnvelope_ < 0.00001f) shiftAlertEnvelope_ = 0.0f;

            const float airMute = 0.72f + controls_.grounded * 0.28f;
            const float center = engine * airMute + road + wind + scrub + thump;
            const float stereoMotion = (noise - roadNoise_) * (0.008f + controls_.speed * 0.014f);
            const float baseLeft = softLimit(center + stereoMotion) * (1.0f - shiftDuck);
            const float baseRight = softLimit(center - stereoMotion) * (1.0f - shiftDuck);
            stereo[frame * 2] = std::clamp(baseLeft + shiftBeep, -0.88f, 0.88f);
            stereo[frame * 2 + 1] = std::clamp(baseRight + shiftBeep, -0.88f, 0.88f);
        }
    }

  private:
    static float wrapPhase(float phase) {
        return phase >= 1.0f ? phase - std::floor(phase) : phase;
    }

    static float softLimit(float sample) {
        return std::tanh(sample * 1.08f) * 0.88f;
    }

    float randomBipolar() {
        randomState_ = randomState_ * 1664525u + 1013904223u;
        return static_cast<float>((randomState_ >> 8) & 0x00ffffffu) * (2.0f / 16777215.0f) - 1.0f;
    }

    SynthControls target_{};
    SynthControls controls_{};
    uint32_t randomState_ = 0x5a17c9e3u;
    float enginePhase_ = 0.0f;
    float firingPhase_ = 0.0f;
    float modulationPhase_ = 0.0f;
    float landingPhase_ = 0.0f;
    float landingEnvelope_ = 0.0f;
    float shiftAlertPhase_ = 0.0f;
    float shiftAlertEnvelope_ = 0.0f;
    float previousLandingImpulse_ = 0.0f;
    float roadNoise_ = 0.0f;
    float windNoise_ = 0.0f;
    float scrubNoise_ = 0.0f;
    bool wasGrounded_ = true;
    bool wasShiftAlert_ = false;
};

struct SignalMetrics {
    float rms = 0.0f;
    float peak = 0.0f;
};

SignalMetrics measure(const std::vector<float>& samples) {
    double energy = 0.0;
    float peak = 0.0f;
    for (const float sample : samples) {
        energy += static_cast<double>(sample) * sample;
        peak = std::max(peak, std::abs(sample));
    }
    return {samples.empty() ? 0.0f : static_cast<float>(std::sqrt(energy / samples.size())), peak};
}

uint64_t hashSamples(const std::vector<float>& samples) {
    uint64_t hash = 1469598103934665603ull;
    for (float sample : samples) {
        uint32_t bits = 0;
        std::memcpy(&bits, &sample, sizeof(bits));
        for (int byte = 0; byte < 4; ++byte) {
            hash ^= (bits >> (byte * 8)) & 0xffu;
            hash *= 1099511628211ull;
        }
    }
    return hash;
}

std::vector<float> renderScenario(const ArcadeAudioInput& input, int blocks, bool landing = false) {
    ArcadeSynth synth;
    std::vector<float> output(kFramesPerBuffer * kChannels * static_cast<std::size_t>(blocks));
    std::array<float, kFramesPerBuffer * kChannels> block{};
    for (int i = 0; i < blocks; ++i) {
        ArcadeAudioInput frameInput = input;
        frameInput.landingImpulse = landing && i == 3 ? 64.0f : 0.0f;
        if (landing && i < 3) frameInput.grounded = false;
        synth.setInput(frameInput);
        synth.render(block.data(), kFramesPerBuffer);
        std::copy(block.begin(), block.end(), output.begin() + static_cast<std::ptrdiff_t>(i) * block.size());
    }
    return output;
}

}  // namespace

struct ArcadeAudio::Impl {
    SDL_AudioStream* stream = nullptr;
    ArcadeSynth synth{};
    std::array<float, kFramesPerBuffer * kChannels> samples{};
    bool ready = false;
    bool ownsAudioSubsystem = false;
    float volume = 0.72f;
};

ArcadeAudio::ArcadeAudio() : impl_(std::make_unique<Impl>()) {}
ArcadeAudio::~ArcadeAudio() { shutdown(); }
ArcadeAudio::ArcadeAudio(ArcadeAudio&& other) noexcept : impl_(std::move(other.impl_)) {}
ArcadeAudio& ArcadeAudio::operator=(ArcadeAudio&& other) noexcept {
    if (this != &other) {
        shutdown();
        impl_ = std::move(other.impl_);
    }
    return *this;
}

bool ArcadeAudio::initialize() {
    if (!impl_) impl_ = std::make_unique<Impl>();
    if (impl_->ready) return true;
    if (impl_->stream != nullptr) {
        SDL_DestroyAudioStream(impl_->stream);
        impl_->stream = nullptr;
    }

    if ((SDL_WasInit(SDL_INIT_AUDIO) & SDL_INIT_AUDIO) == 0) {
        if (!SDL_InitSubSystem(SDL_INIT_AUDIO)) return false;
        impl_->ownsAudioSubsystem = true;
    }

    SDL_AudioSpec spec{};
    spec.format = SDL_AUDIO_F32;
    spec.channels = kChannels;
    spec.freq = static_cast<int>(kSampleRate);
    impl_->stream = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, nullptr, nullptr);
    if (impl_->stream == nullptr) {
        if (impl_->ownsAudioSubsystem) SDL_QuitSubSystem(SDL_INIT_AUDIO);
        impl_->ownsAudioSubsystem = false;
        return false;
    }

    SDL_SetAudioStreamGain(impl_->stream, impl_->volume);
    for (int buffer = 0; buffer < 2; ++buffer) {
        impl_->synth.render(impl_->samples.data(), kFramesPerBuffer);
        if (!SDL_PutAudioStreamData(impl_->stream, impl_->samples.data(),
                                    static_cast<int>(sizeof(impl_->samples)))) {
            SDL_DestroyAudioStream(impl_->stream);
            impl_->stream = nullptr;
            if (impl_->ownsAudioSubsystem) SDL_QuitSubSystem(SDL_INIT_AUDIO);
            impl_->ownsAudioSubsystem = false;
            return false;
        }
    }
    if (!SDL_ResumeAudioStreamDevice(impl_->stream)) {
        SDL_DestroyAudioStream(impl_->stream);
        impl_->stream = nullptr;
        if (impl_->ownsAudioSubsystem) SDL_QuitSubSystem(SDL_INIT_AUDIO);
        impl_->ownsAudioSubsystem = false;
        return false;
    }
    impl_->ready = true;
    return true;
}

void ArcadeAudio::shutdown() {
    if (!impl_) return;
    if (impl_->stream != nullptr) {
        SDL_DestroyAudioStream(impl_->stream);
        impl_->stream = nullptr;
    }
    impl_->ready = false;
    if (impl_->ownsAudioSubsystem) SDL_QuitSubSystem(SDL_INIT_AUDIO);
    impl_->ownsAudioSubsystem = false;
}

void ArcadeAudio::update(const ArcadeAudioInput& input) {
    if (!impl_) return;
    impl_->synth.setInput(input);
    if (!impl_->ready || impl_->stream == nullptr) return;

    constexpr int bytesPerBuffer = static_cast<int>(kFramesPerBuffer * kChannels * sizeof(float));
    for (int buffer = 0; buffer < 2 && SDL_GetAudioStreamQueued(impl_->stream) < bytesPerBuffer * 2; ++buffer) {
        impl_->synth.render(impl_->samples.data(), kFramesPerBuffer);
        if (!SDL_PutAudioStreamData(impl_->stream, impl_->samples.data(), bytesPerBuffer)) {
            impl_->ready = false;
            break;
        }
    }
}

void ArcadeAudio::setMasterVolume(float volume) {
    if (!impl_) return;
    impl_->volume = clamp01(volume);
    if (impl_->ready) SDL_SetAudioStreamGain(impl_->stream, impl_->volume);
}

bool ArcadeAudio::isReady() const {
    return impl_ && impl_->ready && impl_->stream != nullptr;
}

ArcadeAudioAuditResult runArcadeAudioUnitAudit() {
    ArcadeAudioAuditResult result;
    auto check = [&](bool condition) {
        ++result.checks;
        if (!condition) ++result.failures;
        return condition;
    };

    ArcadeAudioInput idle;
    idle.throttle = 0.08f;
    const std::vector<float> idleSignal = renderScenario(idle, 18);
    const SignalMetrics idleMetrics = measure(idleSignal);
    result.idleRms = idleMetrics.rms;
    check(idleMetrics.rms > 0.015f && idleMetrics.rms < 0.20f);

    ArcadeAudioInput fast;
    fast.speedNormalized = 1.0f;
    fast.throttle = 1.0f;
    const std::vector<float> fastSignal = renderScenario(fast, 18);
    const SignalMetrics fastMetrics = measure(fastSignal);
    result.fullSpeedRms = fastMetrics.rms;
    result.peakMagnitude = fastMetrics.peak;
    check(fastMetrics.rms > idleMetrics.rms * 1.35f);
    check(fastMetrics.peak < 0.90f);

    ArcadeAudioInput grip = fast;
    grip.speedNormalized = 0.72f;
    grip.throttle = 0.55f;
    const SignalMetrics gripMetrics = measure(renderScenario(grip, 20));
    grip.slip = 0.95f;
    grip.brake = 1.0f;
    const SignalMetrics scrubMetrics = measure(renderScenario(grip, 20));
    result.scrubRmsIncrease = scrubMetrics.rms - gripMetrics.rms;
    check(result.scrubRmsIncrease > 0.018f);

    ArcadeAudioInput landing;
    landing.speedNormalized = 0.55f;
    landing.throttle = 0.3f;
    const std::vector<float> landingSignal = renderScenario(landing, 18, true);
    result.landingPeak = measure(landingSignal).peak;
    check(result.landingPeak > 0.30f);
    check(result.landingPeak < 0.90f);

    ArcadeAudioInput nearRedline = fast;
    nearRedline.engineRpmNormalized = 0.98f;
    const SignalMetrics nearRedlineMetrics = measure(renderScenario(nearRedline, 4));
    nearRedline.shiftAlert = true;
    const SignalMetrics shiftAlertMetrics = measure(renderScenario(nearRedline, 4));
    result.shiftAlertRmsIncrease = shiftAlertMetrics.rms - nearRedlineMetrics.rms;
    check(result.shiftAlertRmsIncrease > 0.12f);
    check(shiftAlertMetrics.peak < 0.90f);

    const std::vector<float> repeat = renderScenario(fast, 18);
    result.deterministicHash = hashSamples(fastSignal);
    check(result.deterministicHash == hashSamples(repeat));
    check(std::all_of(fastSignal.begin(), fastSignal.end(), [](float sample) { return std::isfinite(sample); }));

    ArcadeAudioInput invalid;
    invalid.speedNormalized = NAN;
    invalid.throttle = INFINITY;
    invalid.brake = -INFINITY;
    invalid.slip = NAN;
    invalid.landingImpulse = NAN;
    const SignalMetrics invalidMetrics = measure(renderScenario(invalid, 4));
    check(std::isfinite(invalidMetrics.rms) && invalidMetrics.peak < 0.90f);

    result.ok = result.failures == 0;
    return result;
}

bool playArcadeShiftBeepPreview() {
    ArcadeAudio audio;
    if (!audio.initialize()) {
        std::fprintf(stderr, "shift beep preview could not open audio: %s\navailable SDL audio drivers:", SDL_GetError());
        const int driverCount = SDL_GetNumAudioDrivers();
        for (int driver = 0; driver < driverCount; ++driver) {
            std::fprintf(stderr, " %s", SDL_GetAudioDriver(driver));
        }
        std::fprintf(stderr, "\n");
        return false;
    }

    ArcadeAudioInput input;
    input.speedNormalized = 0.92f;
    input.engineRpmNormalized = 0.92f;
    input.throttle = 1.0f;
    input.deltaTime = 1.0f / 120.0f;
    for (int frame = 0; frame < 120; ++frame) {
        input.shiftAlert = frame >= 12 && frame < 36;
        audio.update(input);
        SDL_Delay(8);
    }
    audio.shutdown();
    return true;
}
