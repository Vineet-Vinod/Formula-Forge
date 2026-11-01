#pragma once

#include "CoreMinimal.h"
#include "Async/Future.h"
#include "RHIGPUReadback.h"
#include "arcade_vehicle.hpp"
#include <array>
#include <atomic>

class AFormulaTrialPawn;
class FJsonObject;
class FViewport;
class IFileHandle;
class UGameViewportClient;
struct FInputKeyEventArgs;

struct FFFrameReadback {
    TUniquePtr<FRHIGPUTextureReadback> readback;
    TSharedPtr<FJsonObject> metadata;
    std::atomic<bool> submitted{false};
    std::atomic<bool> failed{false};
    std::atomic<bool> mapped{false};
    bool mapping = false;
    TArray<FColor> pixels;
    double mapSeconds = 0.0;
    int32 width = 0;
    int32 height = 0;
    bool rgba = false;
    bool packed10 = false;
};

class FFLapRecorder {
public:
    explicit FFLapRecorder(AFormulaTrialPawn& Pawn);
    ~FFLapRecorder();
    bool Start();
    void Stop(const FString& Reason);
    void BeginTick(float DeltaSeconds);
    void Step(const ArcadeVehicleControl& Control, double DeltaSeconds);
    void EndTick();
    FString Status() const;
    bool IsRecording() const;
private:
    TSharedRef<FJsonObject> Snapshot() const;
    bool WriteLine(IFileHandle& File, const TSharedRef<FJsonObject>& Record);
    bool WriteManifest(const FString& State, const FString& Reason);
    bool HasDiskBudget(uint64 AdditionalBytes) const;
    void PrepareFrame();
    bool PumpReadback(bool WaitForGPU);
    bool DrainReadbacks();
    void InputKey(const FInputKeyEventArgs& Event);
    void InputAxis(FViewport* Viewport, int32 ControllerId, FKey Key, float Value,
        float DeltaSeconds, int32 Samples, bool Gamepad);
    void WriteInput(const TSharedRef<FJsonObject>& Record);
    bool FinishFrameWrite();
    AFormulaTrialPawn& Pawn;
    UGameViewportClient* ViewportClient = nullptr;
    TUniquePtr<IFileHandle> Frames;
    TUniquePtr<IFileHandle> Inputs;
    TUniquePtr<IFileHandle> Ticks;
    TUniquePtr<IFileHandle> Steps;
    std::array<FFFrameReadback, 6> Readbacks;
    int32 ReadbackHead = 0;
    int32 ReadbackCount = 0;
    FString Directory;
    FString LastStatus;
    TArray<FKey> SampleKeys;
    double StartedAt = 0.0;
    double MaximumSeconds = 900.0;
    double SimulationSeconds = 0.0;
    float TickDelta = 0.0f;
    std::atomic<uint64> BytesWritten{0};
    TFuture<bool> FrameWrite;
    int64 TickIndex = -1;
    int64 StepIndex = 0;
    int64 TickStepBegin = 0;
    int64 FrameIndex = 0;
    int64 SavedFrames = 0;
    int64 InputIndex = 0;
    int64 RenderedFrames = 0;
    int32 InitialLaps = 0;
    int32 MaximumLaps = 1;
    bool Recording = false;
    bool QuitAfterRecord = false;
    bool Lossless = false;
};
