#include "FFGame.h"
#include "FFDiscreteRace.hpp"
#include "FFPresentation.h"

#include "Camera/CameraComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/PlatformMisc.h"

bool AFormulaTrialPawn::BeginDiscreteRace() {
    if (RacingDrive || Replay || !NationalRoute.IsEmpty() ||
        FParse::Param(FCommandLine::Get(), TEXT("FFRecord")) ||
        FCString::Strstr(FCommandLine::Get(), TEXT("FFReplay=")) != nullptr) {
        UE_LOG(LogTemp, Error, TEXT("FFDiscreteRace requires its own session without recording, replay or driving audits."));
        return false;
    }
    FFDiscreteRaceConfig config;
    FParse::Value(FCommandLine::Get(), TEXT("FFRaceLines="), config.trajectories);
    FParse::Value(FCommandLine::Get(), TEXT("FFRaceCars="), config.cars);
    FParse::Value(FCommandLine::Get(), TEXT("FFRaceSeed="), config.seed);
    DiscreteRace = MakeUnique<FFDiscreteRace>();
    std::string error;
    if (!DiscreteRace->Initialize(Simulation, config, error)) {
        UE_LOG(LogTemp, Error, TEXT("Discrete race: %s"), UTF8_TO_TCHAR(error.c_str()));
        DiscreteRace.Reset();
        return false;
    }
    // Reuse the accepted car meshes. These components visualize the reduced model.
    TArray<UStaticMesh*> meshes{Body->GetStaticMesh(), FullDriver};
    for (const auto& wheel : Wheels) meshes.Add(wheel->GetStaticMesh());
    for (int car = 1; car < config.cars; ++car) {
        for (auto* mesh : meshes) {
            auto* component = NewObject<UStaticMeshComponent>(this);
            component->SetStaticMesh(mesh);
            component->SetMobility(EComponentMobility::Movable);
            component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            component->SetupAttachment(SceneRoot);
            component->RegisterComponent();
            RaceMeshes.Add(component);
        }
    }
    ChaseCamera = true;
    UE_LOG(LogTemp, Display, TEXT("DISCRETE_RACE lines=%d cars=%d iterations=%d residual=%.6f model_bytes=%llu"),
        config.trajectories, config.cars, DiscreteRace->Solver().iterations, DiscreteRace->Solver().residual,
        static_cast<unsigned long long>(DiscreteRace->Solver().bytes));
    TickDiscreteRace(0.0f);
    return true;
}

void AFormulaTrialPawn::TickDiscreteRace(float deltaSeconds) {
    if (!Paused) {
        Accumulator = FMath::Min(Accumulator + deltaSeconds, 0.1);
        while (Accumulator >= 1.0 / 120.0) {
            DiscreteRace->Step(1.0f / 120.0f);
            Accumulator -= 1.0 / 120.0;
        }
    }
    const auto& cars = DiscreteRace->Cars();
    const auto& ego = cars[0];
    auto& vehicle = Simulation.vehicle;
    vehicle.pos = ego.position * 17.0f;
    vehicle.heading = ego.heading;
    vehicle.forwardSpeed = ego.speed * 17.0f;
    vehicle.vel = fromAngle(ego.heading) * vehicle.forwardSpeed;
    vehicle.elevation = Simulation.Ground(vehicle.pos);
    vehicle.wheelSpin += ego.speed * deltaSeconds / 0.28f;
    UpdateVisual(deltaSeconds);
    for (int32 index = 1; index < static_cast<int32>(cars.size()); ++index) {
        const auto& car = cars[index];
        const FVector location(car.position.y * 100.0, -car.position.x * 100.0,
            Simulation.Ground(car.position * 17.0f) * 100.0 / 17.0);
        const FTransform transform(FRotator(0.0, FMath::RadiansToDegrees(car.heading) - 90.0, 0.0), location);
        const int32 first = (index - 1) * 6;
        RaceMeshes[first]->SetWorldTransform(transform);
        RaceMeshes[first + 1]->SetWorldTransform(FTransform(FVector(-12.0, 0.0, 54.0)) * transform);
        for (int32 wheel = 0; wheel < Wheels.Num(); ++wheel) {
            const FTransform local(FRotator(-FMath::RadiansToDegrees(vehicle.wheelSpin), 0.0, 0.0), WheelRestMounts[wheel]);
            RaceMeshes[first + wheel + 2]->SetWorldTransform(local * transform);
        }
    }
    // C switches between the usual cockpit and a wider view of nearby traffic.
    if (ChaseCamera) {
        const auto& focus = cars[cars.size() / 2];
        const Vec2 behind = focus.position - fromAngle(focus.heading) * 28.0f;
        const FVector camera(behind.y * 100.0, -behind.x * 100.0,
            Simulation.Ground(focus.position * 17.0f) * 100.0 / 17.0 + 1800.0);
        Camera->SetWorldLocationAndRotation(camera,
            FRotator(-28.0, FMath::RadiansToDegrees(focus.heading) - 90.0, 0.0));
        Camera->SetFieldOfView(85.0f);
    }
    if (Presentation) Presentation->UpdateTiles(GetActorLocation(), false);
    float stopSeconds = 0.0f;
    if (FParse::Value(FCommandLine::Get(), TEXT("FFRaceSeconds="), stopSeconds) && Elapsed >= stopSeconds) {
        UE_LOG(LogTemp, Display, TEXT("DISCRETE_RACE_RESULT switches=%d passes=%d corner_passes=%d overlaps=%d grip_ratio=%.4f"),
            DiscreteRace->Stats().switches, DiscreteRace->Stats().passes, DiscreteRace->Stats().cornerPasses,
            DiscreteRace->Stats().overlapEpisodes, DiscreteRace->Stats().maximumLateralRatio);
        FPlatformMisc::RequestExit(false);
    }
}
