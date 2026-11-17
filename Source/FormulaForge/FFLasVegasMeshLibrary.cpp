#include "FFLasVegasMeshLibrary.h"

#include "Engine/StaticMesh.h"
#if WITH_EDITOR
#include "Native/track_catalog.hpp"
#include "AssetRegistry/AssetRegistryModule.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Materials/MaterialInterface.h"
#endif

UStaticMesh* UFFLasVegasMeshLibrary::BuildTile(const FString& sourceFile, const FString& assetPath,
        const TArray<UMaterialInterface*>& materials) {
#if WITH_EDITOR
    TArray<uint8> bytes;
    bool registeredPath = false;
    for (const TrackCatalogEntry& track : trackCatalog()) {
        FString directory = UTF8_TO_TCHAR(track.contentDir.data());
        directory.RemoveFromEnd(TEXT("/Data"));
        if (directory == TEXT("Data")) directory.Empty();
        const FString prefix = TEXT("/Game/Generated/") +
            (directory.IsEmpty() ? FString() : directory + TEXT("/"));
        registeredPath |= assetPath.StartsWith(prefix + TEXT("Track/"));
    }
    if (!registeredPath || materials.IsEmpty() ||
        !FFileHelper::LoadFileToArray(bytes, *sourceFile) || bytes.Num() < 12 ||
        FMemory::Memcmp(bytes.GetData(), "FFLVM1\0", 8) != 0) return nullptr;
    uint32 triangles = 0;
    FMemory::Memcpy(&triangles, bytes.GetData() + 8, 4);
    constexpr int32 stride = 4 + 3 * 8 * sizeof(float);
    if (triangles == 0 || triangles > 500000 || bytes.Num() != 12 + static_cast<int64>(triangles) * stride) return nullptr;

    FMeshDescription description;
    FStaticMeshAttributes attributes(description);
    attributes.Register();
    auto positions = attributes.GetVertexPositions();
    auto normals = attributes.GetVertexInstanceNormals();
    auto tangents = attributes.GetVertexInstanceTangents();
    auto signs = attributes.GetVertexInstanceBinormalSigns();
    auto uvs = attributes.GetVertexInstanceUVs();
    uvs.SetNumChannels(1);
    auto slots = attributes.GetPolygonGroupMaterialSlotNames();
    TArray<FPolygonGroupID> groups;
    for (int32 index = 0; index < materials.Num(); ++index) {
        const FPolygonGroupID group = description.CreatePolygonGroup();
        groups.Add(group);
        slots[group] = FName(*FString::Printf(TEXT("Material_%d"), index));
    }
    int32 cursor = 12;
    for (uint32 triangle = 0; triangle < triangles; ++triangle) {
        uint32 material = 0;
        FMemory::Memcpy(&material, bytes.GetData() + cursor, 4);
        cursor += 4;
        if (material >= static_cast<uint32>(groups.Num())) return nullptr;
        TArray<FVertexInstanceID, TInlineAllocator<3>> corners;
        for (int32 corner = 0; corner < 3; ++corner) {
            float data[8];
            FMemory::Memcpy(data, bytes.GetData() + cursor, sizeof(data));
            cursor += sizeof(data);
            for (float value : data) if (!FMath::IsFinite(value)) return nullptr;
            const FVertexID vertex = description.CreateVertex();
            positions[vertex] = FVector3f(data[0], data[1], data[2]);
            const FVertexInstanceID instance = description.CreateVertexInstance(vertex);
            corners.Add(instance);
            const FVector3f normal(data[3], data[4], data[5]);
            normals[instance] = normal;
            tangents[instance] = FVector3f::CrossProduct(FMath::Abs(normal.Z) > 0.9f ?
                FVector3f(0, 1, 0) : FVector3f(0, 0, 1), normal).GetSafeNormal();
            signs[instance] = 1.0f;
            uvs.Set(instance, 0, FVector2f(data[6], data[7]));
        }
        description.CreateTriangle(groups[material], corners);
    }
    UPackage* package = CreatePackage(*assetPath);
    package->FullyLoad();
    const FString name = FPackageName::GetLongPackageAssetName(assetPath);
    UStaticMesh* mesh = FindObject<UStaticMesh>(package, *name);
    const bool created = mesh == nullptr;
    if (created) mesh = NewObject<UStaticMesh>(package, *name, RF_Public | RF_Standalone);
    mesh->Modify();
    mesh->SetNumSourceModels(1);
    FMeshBuildSettings& settings = mesh->GetSourceModel(0).BuildSettings;
    settings.bRecomputeNormals = false;
    settings.bRecomputeTangents = false;
    settings.bGenerateLightmapUVs = false;
    settings.bUseFullPrecisionUVs = true;
    mesh->GetStaticMaterials().Empty();
    for (int32 index = 0; index < materials.Num(); ++index) {
        mesh->GetStaticMaterials().Add(FStaticMaterial(materials[index], slots[groups[index]]));
    }
    mesh->CreateMeshDescription(0, MoveTemp(description));
    mesh->CommitMeshDescription(0);
    mesh->SetImportVersion(EImportStaticMeshVersion::LastVersion);
    mesh->Build(false);
    mesh->MarkPackageDirty();
    if (created) FAssetRegistryModule::AssetCreated(mesh);
    return mesh;
#else
    return nullptr;
#endif
}
