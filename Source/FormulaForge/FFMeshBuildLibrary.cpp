#include "FFMeshBuildLibrary.h"

#include "Engine/StaticMesh.h"

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
