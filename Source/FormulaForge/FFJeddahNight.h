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
    virtual void EndPlay(const EEndPlayReason::Type reason) override;
    virtual void Tick(float deltaSeconds) override;
private:
    void LoadFixtures(const TCHAR* filename, TArray<FFJeddahFixture>& fixtures);
    void UpdateLights();
    TArray<FFJeddahFixture> Fixtures;
    TArray<FFJeddahFixture> GarageFixtures;
    UPROPERTY(Transient)
    TArray<TObjectPtr<USpotLightComponent>> Lights;
    UPROPERTY(Transient)
    TArray<TObjectPtr<USpotLightComponent>> GarageLights;
    float LightScale = 1.0f;
    float GarageLightScale = 1.0f;
    bool LightAuditRequested = false;
    bool LightAuditLogged = false;
    int32 PreviousLightInjection = 1;
    bool RestoreLightInjection = false;
};
