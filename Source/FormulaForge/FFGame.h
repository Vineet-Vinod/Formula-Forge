#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/HUD.h"
#include "FFSimulation.hpp"
#include "FFLapRecorder.h"
#include "FFCameraMotion.hpp"
#include "FFVisualReplay.h"
#include "FFRacingStint.hpp"
#include "FFGame.generated.h"

class UCameraComponent;
class UStaticMeshComponent;
class UStaticMesh;
class AFFPresentation;

UCLASS()
class AFormulaTrialPawn : public APawn {
    GENERATED_BODY()
public:
    AFormulaTrialPawn();
    virtual ~AFormulaTrialPawn() override;
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    FFSimulation Simulation;
    bool Automatic = false;
    bool Paused = false;
    bool ChaseCamera = false;
    bool SceneReady = false;
    FString RecordingStatus() const;
    void SetSessionPaused(bool Value);
    int32 LoadedVisualTiles() const;
private:
    friend class FFLapRecorder;
    friend class FFSessionAudit;
    void ToggleRecording();
    void ResetTrial();
    void ToggleCamera();
    void ToggleAutomatic();
    void Quit();
    void DrainRenderingForExit();
    void ShiftUp();
    void ShiftDown();
    void UpdateVisual(float DeltaSeconds = 0.0f);
    float VisualPenetration(bool IncludeWheels = true, bool ForceDetailedBody = false) const;
    float WheelPenetration(int32 Index) const;
    float ComponentPenetration(const FTransform& Transform, const FVector& Minimum, const FVector& Maximum) const;
    int32 AuditVisualSupport();
    void SaveBest();
    void CaptureFinished(int32 Width, int32 Height, const TArray<FColor>& Pixels);
    UPROPERTY() TObjectPtr<USceneComponent> SceneRoot;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Body;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Driver;
    UPROPERTY() TObjectPtr<UStaticMesh> FullDriver;
    UPROPERTY() TObjectPtr<UStaticMesh> CockpitDriver;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Wheels;
    TArray<FVector> WheelRestMounts;
    TArray<FVector2D> NationalRoute;
    TArray<FBox> BodySupports;
    FBox BodySupportEnvelope = FBox(ForceInit);
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
    UPROPERTY() TObjectPtr<AFFPresentation> Presentation;
    double Accumulator = 0.0;
    double Elapsed = 0.0;
    double FrameSeconds = 0.0;
    int32 FrameCount = 0;
    int32 PendingShifts = 0;
    float CaptureDelay = 12.0f;
    float RenderedPenetration = 0.0f;
    FString BestLapPath;
    FString CapturePath;
    bool Captured = false;
    bool Capturing = false;
    bool QuitAfterCapture = false;
    bool CaptureDrive = false;
    bool RacingDrive = false;
    FFRacingLine RacingLine;
    FFRacingStint RacingStint;
    bool RacingLiveAudit = false;
    TUniquePtr<FFLapRecorder> Recorder;
    FFCameraMotion CameraMotion;
    TUniquePtr<FFVisualReplay> Replay;
};

UCLASS()
class AFormulaTrialHUD : public AHUD {
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
    virtual void NotifyHitBoxClick(FName BoxName) override;
};

UCLASS()
class AFormulaTrialGameMode : public AGameModeBase {
    GENERATED_BODY()
public:
    AFormulaTrialGameMode();
};
