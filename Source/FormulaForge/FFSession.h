#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameModeBase.h"
#include "FFSessionAudit.h"
#include "FFSession.generated.h"

enum class EFFScreen { Setup, Loading, Driving, Paused, Results };

struct FFLapResult {
    double Seconds = 0.0;
    bool Valid = false;
};

UCLASS()
class UFFSession : public UGameInstance {
    GENERATED_BODY()
public:
    virtual void Init() override;
    virtual void Shutdown() override;
    FString Circuit() const;
    FString CircuitTitle() const;
    FString LapLabel() const;
    int32 LapLimit() const;
    void Activate(int32 Action);
    void StartTrial();
    void ReturnToMenu();
    void Pause();
    void Resume();
    void ObserveLap(int32 CompletedLaps, double Seconds, bool Valid);
    void ResetLaps();
    void Ready();
    int32 ActionCount() const;
    EFFScreen Screen = EFFScreen::Setup;
    int32 CircuitIndex = 0;
    int32 LapIndex = 0;
    int32 Focus = 0;
    TArray<FFLapResult> Laps;
    bool Automatic = false;
    bool ChaseCamera = false;
private:
    TUniquePtr<FFSessionAudit> Audit;
    void LoadingScreen(const FString& Map);
    void Travel(const FString& Map, const FString& GameMode);
};

UCLASS()
class AFormulaFlowController : public APlayerController {
    GENERATED_BODY()
public:
    virtual void SetupInputComponent() override;
    virtual void PlayerTick(float DeltaTime) override;
private:
    void Left();
    void Right();
    void Up();
    void Down();
    void MoveFocus(int32 Direction);
    void Confirm();
    void Back();
    void Cancel();
    void TogglePause();
};

UCLASS()
class AFormulaMenuGameMode : public AGameModeBase {
    GENERATED_BODY()
public:
    AFormulaMenuGameMode();
    virtual void StartPlay() override;
};
