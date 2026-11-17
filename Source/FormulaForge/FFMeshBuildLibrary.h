#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FFMeshBuildLibrary.generated.h"

class UStaticMesh;
class UMaterialInterface;

UCLASS()
class UFFMeshBuildLibrary : public UBlueprintFunctionLibrary {
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category = "Formula Forge|Assets")
    static int32 SuppressGroundShadowSections(UStaticMesh* Mesh, const TArray<FName>& MaterialSlots, int32 MinimumLOD = 0);

    UFUNCTION(BlueprintCallable, Category = "Formula Forge|Assets")
    static bool ExportTile(UStaticMesh* Mesh, const FString& SourceFile,
        TArray<UMaterialInterface*>& Materials, int32& UVChannels, bool& HasVertexColors);

    UFUNCTION(BlueprintCallable, Category = "Formula Forge|Assets")
    static int32 CutTilePortals(UStaticMesh* Mesh, const FString& PortalFile,
        const TArray<FName>& MaterialSlots, bool DryRun = true);

    UFUNCTION(BlueprintCallable, Category = "Formula Forge|Assets")
    static int32 ReclassifyTilePortals(UStaticMesh* Mesh, const FString& PortalFile,
        const TArray<FName>& MaterialSlots, UMaterialInterface* Replacement, bool DryRun = true);
};
