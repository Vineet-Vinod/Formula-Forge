#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FFLasVegasMeshLibrary.generated.h"

class UStaticMesh;
class UMaterialInterface;

UCLASS()
class UFFLasVegasMeshLibrary : public UBlueprintFunctionLibrary {
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category = "Formula Forge|Las Vegas")
    static UStaticMesh* BuildTile(const FString& SourceFile, const FString& AssetPath,
        const TArray<UMaterialInterface*>& Materials);
};
