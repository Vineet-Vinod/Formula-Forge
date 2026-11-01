#pragma once

#include "CoreMinimal.h"
#include "Engine/StreamableManager.h"
#include "GameFramework/Actor.h"
#include "FFPresentation.generated.h"

class UStaticMeshComponent;

struct FFVisualTile {
    FSoftObjectPath mesh;
    FBox bounds;
    TSharedPtr<FStreamableHandle> request;
    bool building = false;
    bool crowd = false;
};

UCLASS()
class AFFPresentation : public AActor {
    GENERATED_BODY()
public:
    AFFPresentation();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Tick(float DeltaSeconds) override;
    int32 LoadedTiles() const;
    bool IsStreaming() const;
    bool UpdateTiles(FVector Position, bool Immediate);
private:
    void ConfigureDaylight();
    void UpdateRenderResolution();
    void AttachTile(int32 Index);
    void ApplyTileDetail(int32 Index, double DistanceSquared);
    TArray<FFVisualTile> Tiles;
    FVector LastPosition = FVector::ZeroVector;
    int32 ReleasedSinceCollection = 0;
    double LastCollectionSeconds = 0.0;
    bool FullDetail = false;
    bool SilverstoneTiles = false;
    FIntPoint RenderBudget = FIntPoint(1600, 900);
    FIntPoint LastViewportSize = FIntPoint::ZeroValue;
    float PresetScreenPercentage = 100.0f;
    bool LastFullscreen = false;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Components;
};
