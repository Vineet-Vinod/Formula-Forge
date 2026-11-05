#pragma once

#include "CoreMinimal.h"

class UProceduralMeshComponent;
struct TrackCatalogEntry;

int32 BuildGeneratedRibbon(AActor& Owner, const TrackCatalogEntry& Track, TArray<TObjectPtr<UProceduralMeshComponent>>& Ribbon);
