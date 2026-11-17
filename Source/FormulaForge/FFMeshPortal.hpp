#pragma once

#if WITH_EDITOR
#include "CoreMinimal.h"
#include "MeshDescription.h"

struct FFMeshPortalPlane {
    FVector3d normal;
    double distance;
};

struct FFMeshPortalVertex {
    FVector3f position;
    FVector3f normal;
    FVector3f tangent;
    float binormalSign;
    FVector4f color;
    TArray<FVector2f> uvs;
};

using FFMeshPortalPolygon = TArray<FFMeshPortalVertex>;
using FFMeshPortalVolume = TArray<FFMeshPortalPlane>;

bool FFReadMeshPortals(const FString& filename, TArray<FFMeshPortalVolume>& portals);
FFMeshPortalVertex FFInterpolatePortalVertex(const FFMeshPortalVertex& first,
    const FFMeshPortalVertex& last, double fraction);
FFMeshPortalPolygon FFClipPortalPolygon(const FFMeshPortalPolygon& polygon,
    const FFMeshPortalPlane& plane, bool inside);
double FFPortalPolygonArea(const FFMeshPortalPolygon& polygon);
int32 FFCutMeshPortals(FMeshDescription& description, const TArray<FFMeshPortalVolume>& portals,
    const TSet<FName>& materialSlots, FName replacementSlot = NAME_None);
#endif
