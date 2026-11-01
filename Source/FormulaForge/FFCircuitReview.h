#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Pawn.h"
#include "FFCircuitReview.generated.h"

class AFFPresentation;

UCLASS()
class AFFCircuitReviewPawn : public APawn {
    GENERATED_BODY()
public:
    AFFCircuitReviewPawn();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
private:
    UPROPERTY() TObjectPtr<AFFPresentation> Presentation;
    FString CapturePath;
    float Elapsed = 0.0f;
    float CaptureDelay = 10.0f;
    bool Requested = false;
    bool Completed = false;
};

UCLASS()
class AFFCircuitReviewGameMode : public AGameModeBase {
    GENERATED_BODY()
public:
    AFFCircuitReviewGameMode();
};
