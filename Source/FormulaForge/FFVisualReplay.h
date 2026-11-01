#pragma once

#include "CoreMinimal.h"
#include "FFSimulation.hpp"
#include "FFReplayTimeline.hpp"

class IFileHandle;

class FFVisualReplay {
public:
    FFVisualReplay();
    ~FFVisualReplay();
    bool Load(const FString& Filename, FFSimulation& Simulation, bool& ChaseCamera);
    bool Next(FFSimulation& Simulation, bool& ChaseCamera, float RenderedDeltaSeconds = 0.0f);
    float DeltaSeconds() const;
    int32 Frame() const;
    double TimeSeconds() const;
    void Report(const FTransform& Actor, const FTransform& Camera, float Penetration);
private:
    void Apply(FFSimulation& Simulation, bool& ChaseCamera);
    TArray<FFReplayPose> Poses;
    TUniquePtr<IFileHandle> Output;
    int32 Index = -1;
    FFReplayPose Current{};
    float StepSeconds = 0.0f;
    bool Realtime = false;
};
