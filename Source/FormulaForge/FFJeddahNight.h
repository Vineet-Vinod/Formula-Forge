#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FFJeddahNight.generated.h"

class USpotLightComponent;

struct FFJeddahFixture {
    FVector positionCm;
    FVector targetCm;
    float power;
};

UCLASS()
class AFFJeddahNight : public AActor {
    GENERATED_BODY()
public:
    AFFJeddahNight();
    virtual void BeginPlay() override;
    virtual void Tick(float deltaSeconds) override;
private:
    void LoadFixtures();
    void UpdateLights();
    TArray<FFJeddahFixture> Fixtures;
    UPROPERTY(Transient)
    TArray<TObjectPtr<USpotLightComponent>> Lights;
    float LightScale = 1.0f;
};
