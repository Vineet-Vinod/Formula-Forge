#include "FFMeshBuildLibrary.h"
#include "FFMeshPortal.hpp"

#include "Engine/StaticMesh.h"
#if WITH_EDITOR
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/BufferArchive.h"
#endif

int32 UFFMeshBuildLibrary::CutTilePortals(UStaticMesh* mesh, const FString& portalFile,
        const TArray<FName>& materialSlots, bool dryRun) {
#if WITH_EDITOR
    if (mesh == nullptr || !mesh->GetPathName().StartsWith(TEXT("/Game/Generated/"))) return -1;
    TArray<FFMeshPortalVolume> portals;
    if (!FFReadMeshPortals(portalFile, portals)) return -1;
    TArray<TPair<int32, FMeshDescription>> changedLODs;
    const TSet<FName> selected(materialSlots);
    int32 changed = 0;
    for (int32 lod = 0; lod < mesh->GetNumSourceModels(); ++lod) {
        const FMeshDescription* original = mesh->GetMeshDescription(lod);
        if (original == nullptr) continue;
        FMeshDescription candidate = *original;
        const int32 count = FFCutMeshPortals(candidate, portals, selected);
        if (count == 0) continue;
        changed += count;
        changedLODs.Emplace(lod, MoveTemp(candidate));
    }
    if (dryRun || changed == 0) return changed;
    mesh->Modify();
    for (auto& entry : changedLODs) {
        FElementIDRemappings remappings;
        entry.Value.Compact(remappings);
        entry.Value.TriangleAttributes().SetNumElements(entry.Value.Triangles().GetArraySize());
        mesh->CreateMeshDescription(entry.Key, MoveTemp(entry.Value));
        mesh->CommitMeshDescription(entry.Key);
    }
    mesh->Build(false);
    mesh->MarkPackageDirty();
    return changed;
#else
    return -1;
#endif
}

int32 UFFMeshBuildLibrary::ReclassifyTilePortals(UStaticMesh* mesh, const FString& portalFile,
        const TArray<FName>& materialSlots, UMaterialInterface* replacement, bool dryRun) {
#if WITH_EDITOR
    if (mesh == nullptr || replacement == nullptr || materialSlots.IsEmpty() ||
        !mesh->GetPathName().StartsWith(TEXT("/Game/Generated/"))) return -1;
    TArray<FFMeshPortalVolume> portals;
    if (!FFReadMeshPortals(portalFile, portals)) return -1;
    const int32 existing = mesh->GetStaticMaterials().IndexOfByPredicate([&](const FStaticMaterial& material) {
        return material.MaterialInterface == replacement;
    });
    FName slot = existing == INDEX_NONE ? FName(TEXT("FFPortalAsphalt")) : mesh->GetStaticMaterials()[existing].MaterialSlotName;
    if (existing == INDEX_NONE) {
        int32 suffix = 0;
        while (mesh->GetStaticMaterials().ContainsByPredicate([&](const FStaticMaterial& material) {
            return material.MaterialSlotName == slot || material.ImportedMaterialSlotName == slot;
        })) slot = FName(*FString::Printf(TEXT("FFPortalAsphalt_%d"), ++suffix));
    }
    const TSet<FName> selected(materialSlots);
    TArray<TPair<int32, FMeshDescription>> changedLODs;
    int32 changed = 0;
    for (int32 lod = 0; lod < mesh->GetNumSourceModels(); ++lod) {
        const FMeshDescription* original = mesh->GetMeshDescription(lod);
        if (original == nullptr) continue;
        FMeshDescription candidate = *original;
        const int32 count = FFCutMeshPortals(candidate, portals, selected, slot);
        if (count == 0) continue;
        changed += count;
        changedLODs.Emplace(lod, MoveTemp(candidate));
    }
    if (dryRun || changed == 0) return changed;
    mesh->Modify();
    if (existing == INDEX_NONE) mesh->GetStaticMaterials().Add(FStaticMaterial(replacement, slot, slot));
    for (auto& entry : changedLODs) {
        FElementIDRemappings remappings;
        entry.Value.Compact(remappings);
        entry.Value.TriangleAttributes().SetNumElements(entry.Value.Triangles().GetArraySize());
        mesh->CreateMeshDescription(entry.Key, MoveTemp(entry.Value));
        mesh->CommitMeshDescription(entry.Key);
    }
    mesh->Build(false);
    mesh->MarkPackageDirty();
    return changed;
#else
    return -1;
#endif
}

bool UFFMeshBuildLibrary::ExportTile(UStaticMesh* mesh, const FString& sourceFile,
        TArray<UMaterialInterface*>& materials, int32& uvChannels, bool& hasVertexColors) {
    materials.Reset();
    uvChannels = 0;
    hasVertexColors = false;
#if WITH_EDITOR
    if (mesh == nullptr || mesh->GetNumSourceModels() == 0 || !mesh->GetPathName().StartsWith(TEXT("/Game/Generated/")) ||
        !FPaths::IsUnderDirectory(FPaths::ConvertRelativePathToFull(sourceFile), FPaths::ProjectDir() / TEXT("build"))) return false;
    const FMeshDescription* description = mesh->GetMeshDescription(0);
    if (description == nullptr || description->Triangles().Num() == 0) return false;
    const FStaticMeshConstAttributes attributes(*description);
    const auto positions = attributes.GetVertexPositions();
    const auto normals = attributes.GetVertexInstanceNormals();
    const auto uvs = attributes.GetVertexInstanceUVs();
    const auto colors = attributes.GetVertexInstanceColors();
    const auto slots = attributes.GetPolygonGroupMaterialSlotNames();
    uvChannels = uvs.GetNumChannels();
    if (uvChannels == 0) return false;
    for (const FStaticMaterial& material : mesh->GetStaticMaterials()) {
        if (material.MaterialInterface == nullptr) return false;
        materials.Add(material.MaterialInterface);
    }
    TMap<FPolygonGroupID, uint32> groups;
    for (const FPolygonGroupID group : description->PolygonGroups().GetElementIDs()) {
        const int32 index = mesh->GetStaticMaterials().IndexOfByPredicate([&](const FStaticMaterial& material) {
            return material.MaterialSlotName == slots[group] || material.ImportedMaterialSlotName == slots[group];
        });
        if (index == INDEX_NONE) return false;
        groups.Add(group, static_cast<uint32>(index));
    }
    FBufferArchive output;
    char signature[8] = {'F', 'F', 'L', 'V', 'M', '1', 0, 0};
    output.Serialize(signature, sizeof(signature));
    uint32 triangleCount = description->Triangles().Num();
    output << triangleCount;
    for (const FTriangleID triangle : description->Triangles().GetElementIDs()) {
        uint32 material = groups[description->GetTrianglePolygonGroup(triangle)];
        output << material;
        for (const FVertexInstanceID instance : description->GetTriangleVertexInstances(triangle)) {
            const FVector3f position = positions[description->GetVertexInstanceVertex(instance)];
            const FVector3f normal = normals[instance];
            const FVector2f uv = uvs.Get(instance, 0);
            float values[8] = {position.X, position.Y, position.Z, normal.X, normal.Y, normal.Z, uv.X, uv.Y};
            for (float value : values) if (!FMath::IsFinite(value)) return false;
            output.Serialize(values, sizeof(values));
            hasVertexColors |= colors[instance] != FVector4f(1.0f, 1.0f, 1.0f, 1.0f);
        }
    }
    return FFileHelper::SaveArrayToFile(output, *sourceFile);
#else
    return false;
#endif
}

int32 UFFMeshBuildLibrary::SuppressGroundShadowSections(UStaticMesh* mesh, const TArray<FName>& materialSlots, int32 minimumLOD) {
#if WITH_EDITOR
    if (mesh == nullptr) return 0;
    int32 changed = 0;
    const auto& materials = mesh->GetStaticMaterials();
    for (int32 lod = FMath::Max(0, minimumLOD); lod < mesh->GetNumLODs(); ++lod) {
        const int32 sections = mesh->GetNumSections(lod);
        for (int32 section = 0; section < sections; ++section) {
            FMeshSectionInfo info = mesh->GetSectionInfoMap().Get(lod, section);
            if (!materials.IsValidIndex(info.MaterialIndex) || !info.bCastShadow ||
                    !materialSlots.Contains(materials[info.MaterialIndex].MaterialSlotName)) continue;
            if (changed == 0) mesh->Modify();
            info.bCastShadow = false;
            mesh->GetSectionInfoMap().Set(lod, section, info);
            ++changed;
        }
    }
    if (changed != 0) mesh->PostEditChange();
    return changed;
#else
    return 0;
#endif
}
