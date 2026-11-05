#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FFLasVegasNight.generated.h"

UCLASS()
class AFFLasVegasNight : public AActor {
    GENERATED_BODY()
public:
    AFFLasVegasNight();
    virtual void BeginPlay() override;
};
