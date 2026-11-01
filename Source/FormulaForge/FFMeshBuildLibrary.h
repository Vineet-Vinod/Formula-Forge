#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FFMeshBuildLibrary.generated.h"

class UStaticMesh;

UCLASS()
class UFFMeshBuildLibrary : public UBlueprintFunctionLibrary {
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category = "Formula Forge|Assets")
    static int32 SuppressGroundShadowSections(UStaticMesh* Mesh, const TArray<FName>& MaterialSlots, int32 MinimumLOD = 0);
};
