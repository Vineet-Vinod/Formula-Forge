#include "FFMeshPortal.hpp"

#if WITH_EDITOR
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "StaticMeshAttributes.h"

bool FFReadMeshPortals(const FString& filename, TArray<FFMeshPortalVolume>& portals) {
    FString text;
    TSharedPtr<FJsonObject> root;
    if (!FFileHelper::LoadFileToString(text, *filename) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(text), root) || !root.IsValid()) return false;
    const TArray<TSharedPtr<FJsonValue>>* records = nullptr;
    if (!root->TryGetArrayField(TEXT("portals"), records) || records->Num() > 512) return false;
    for (const auto& value : *records) {
        const TSharedPtr<FJsonObject>* record = nullptr;
        const TArray<TSharedPtr<FJsonValue>>* ring = nullptr;
        double bottom, top;
        if (!value->TryGetObject(record) || !(*record)->TryGetArrayField(TEXT("polygon_xy_m"), ring) ||
            ring->Num() != 4 || !(*record)->TryGetNumberField(TEXT("bottom_m"), bottom) ||
            !(*record)->TryGetNumberField(TEXT("top_m"), top) || !FMath::IsFinite(bottom) ||
            !FMath::IsFinite(top) || bottom >= top) return false;
        TArray<FVector2d> points;
        for (const auto& point : *ring) {
            const TArray<TSharedPtr<FJsonValue>>* coordinates = nullptr;
            double x, y;
            if (!point->TryGetArray(coordinates) || coordinates->Num() != 2 ||
                !(*coordinates)[0]->TryGetNumber(x) || !(*coordinates)[1]->TryGetNumber(y) ||
                !FMath::IsFinite(x) || !FMath::IsFinite(y)) return false;
            points.Add({x, y});
        }
        double orientation = 0;
        for (int32 index = 0; index < 4; ++index) {
            const FVector2d a = points[(index + 1) % 4] - points[index];
            const FVector2d b = points[(index + 2) % 4] - points[(index + 1) % 4];
            const double turn = a.X * b.Y - a.Y * b.X;
            if (FMath::Abs(turn) < 1e-10 || (orientation != 0 && turn * orientation <= 0)) return false;
            orientation = turn;
        }
        FFMeshPortalVolume volume;
        const double sign = orientation > 0 ? 1 : -1;
        for (int32 index = 0; index < 4; ++index) {
            const FVector2d first = points[index];
            const FVector2d edge = points[(index + 1) % 4] - first;
            const double factor = sign / edge.Length();
            volume.Add({FVector3d(-edge.X, edge.Y, 0) * (factor / 100.0),
                (edge.X * first.Y - edge.Y * first.X) * factor});
        }
        volume.Add({FVector3d(0, 0, 0.01), bottom});
        volume.Add({FVector3d(0, 0, -0.01), -top});
        portals.Add(MoveTemp(volume));
    }
    return true;
}

FFMeshPortalVertex FFInterpolatePortalVertex(const FFMeshPortalVertex& first,
        const FFMeshPortalVertex& last, double fraction) {
    FFMeshPortalVertex result;
    result.position = FVector3f(FMath::Lerp(FVector3d(first.position), FVector3d(last.position), fraction));
    result.normal = FMath::Lerp(first.normal, last.normal, static_cast<float>(fraction)).GetSafeNormal();
    result.tangent = FMath::Lerp(first.tangent, last.tangent, static_cast<float>(fraction)).GetSafeNormal();
    result.binormalSign = first.binormalSign;
    result.color = FMath::Lerp(first.color, last.color, static_cast<float>(fraction));
    for (int32 index = 0; index < first.uvs.Num(); ++index) {
        result.uvs.Add(FMath::Lerp(first.uvs[index], last.uvs[index], static_cast<float>(fraction)));
    }
    return result;
}

FFMeshPortalPolygon FFClipPortalPolygon(const FFMeshPortalPolygon& polygon,
        const FFMeshPortalPlane& plane, bool inside) {
    FFMeshPortalPolygon result;
    if (polygon.IsEmpty()) return result;
    const double sign = inside ? 1 : -1;
    const auto distance = [&](const FFMeshPortalVertex& vertex) {
        return sign * (FVector3d::DotProduct(plane.normal, FVector3d(vertex.position)) - plane.distance);
    };
    FFMeshPortalVertex previous = polygon.Last();
    double before = distance(previous);
    for (const FFMeshPortalVertex& current : polygon) {
        const double after = distance(current);
        if ((before >= 0) != (after >= 0)) {
            result.Add(FFInterpolatePortalVertex(previous, current, FMath::Clamp(before / (before - after), 0.0, 1.0)));
        }
        if (after >= 0) result.Add(current);
        previous = current;
        before = after;
    }
    return result;
}

double FFPortalPolygonArea(const FFMeshPortalPolygon& polygon) {
    double area = 0;
    for (int32 index = 1; index + 1 < polygon.Num(); ++index) {
        area += FVector3d::CrossProduct(FVector3d(polygon[index].position) - FVector3d(polygon[0].position),
            FVector3d(polygon[index + 1].position) - FVector3d(polygon[0].position)).Length() * 0.5;
    }
    return area;
}

int32 FFCutMeshPortals(FMeshDescription& description, const TArray<FFMeshPortalVolume>& portals,
        const TSet<FName>& materialSlots, FName replacementSlot) {
    // Unreal's remapper leaves zero-channel attributes at their previous size.
    description.TriangleAttributes().SetNumElements(description.Triangles().GetArraySize());
    FStaticMeshAttributes attributes(description);
    auto positions = attributes.GetVertexPositions();
    auto normals = attributes.GetVertexInstanceNormals();
    auto tangents = attributes.GetVertexInstanceTangents();
    auto signs = attributes.GetVertexInstanceBinormalSigns();
    auto colors = attributes.GetVertexInstanceColors();
    auto uvs = attributes.GetVertexInstanceUVs();
    auto slots = attributes.GetPolygonGroupMaterialSlotNames();
    FPolygonGroupID replacement;
    if (!replacementSlot.IsNone()) {
        for (const FPolygonGroupID group : description.PolygonGroups().GetElementIDs()) {
            if (slots[group] == replacementSlot) replacement = group;
        }
        if (replacement.GetValue() == INDEX_NONE) {
            replacement = description.CreatePolygonGroup();
            slots[replacement] = replacementSlot;
        }
    }
    int32 changed = 0;
    for (const FFMeshPortalVolume& portal : portals) {
        TArray<FTriangleID> triangles;
        for (const FTriangleID triangle : description.Triangles().GetElementIDs()) triangles.Add(triangle);
        for (const FTriangleID triangle : triangles) {
            if (!materialSlots.IsEmpty() && !materialSlots.Contains(slots[description.GetTrianglePolygonGroup(triangle)])) continue;
            if (!replacementSlot.IsNone() && description.GetTrianglePolygonGroup(triangle) == replacement) continue;
            bool separated = false;
            for (const FFMeshPortalPlane& plane : portal) {
                bool allOutside = true;
                for (const FVertexInstanceID instance : description.GetTriangleVertexInstances(triangle)) {
                    const FVector3f position = positions[description.GetVertexInstanceVertex(instance)];
                    allOutside &= FVector3d::DotProduct(plane.normal, FVector3d(position)) - plane.distance < 0;
                }
                if (allOutside) { separated = true; break; }
            }
            if (separated) continue;
            FFMeshPortalPolygon original;
            for (const FVertexInstanceID instance : description.GetTriangleVertexInstances(triangle)) {
                FFMeshPortalVertex vertex{positions[description.GetVertexInstanceVertex(instance)],
                    normals[instance], tangents[instance], signs[instance], colors[instance], {}};
                for (int32 channel = 0; channel < uvs.GetNumChannels(); ++channel) vertex.uvs.Add(uvs.Get(instance, channel));
                original.Add(MoveTemp(vertex));
            }
            FFMeshPortalPolygon remaining = original;
            TArray<FFMeshPortalPolygon> outside;
            for (const FFMeshPortalPlane& plane : portal) {
                auto piece = FFClipPortalPolygon(remaining, plane, false);
                if (piece.Num() >= 3) outside.Add(MoveTemp(piece));
                remaining = FFClipPortalPolygon(remaining, plane, true);
                if (remaining.Num() < 3) break;
            }
            if (remaining.Num() < 3 || FFPortalPolygonArea(remaining) <= 1e-9) continue;
            const FPolygonGroupID group = description.GetTrianglePolygonGroup(triangle);
            description.DeleteTriangle(triangle);
            ++changed;
            if (!replacementSlot.IsNone()) outside.Add(MoveTemp(remaining));
            for (int32 pieceIndex = 0; pieceIndex < outside.Num(); ++pieceIndex) {
                const FFMeshPortalPolygon& piece = outside[pieceIndex];
                const FPolygonGroupID outputGroup = !replacementSlot.IsNone() && pieceIndex == outside.Num() - 1 ? replacement : group;
                for (int32 index = 1; index + 1 < piece.Num(); ++index) {
                    const FFMeshPortalPolygon face{piece[0], piece[index], piece[index + 1]};
                    if (FFPortalPolygonArea(face) <= 1e-9) continue;
                    TArray<FVertexInstanceID, TInlineAllocator<3>> corners;
                    for (const FFMeshPortalVertex& vertex : face) {
                        const FVertexID id = description.CreateVertex();
                        positions[id] = vertex.position;
                        const FVertexInstanceID instance = description.CreateVertexInstance(id);
                        normals[instance] = vertex.normal;
                        tangents[instance] = vertex.tangent;
                        signs[instance] = vertex.binormalSign;
                        colors[instance] = vertex.color;
                        for (int32 channel = 0; channel < vertex.uvs.Num(); ++channel) uvs.Set(instance, channel, vertex.uvs[channel]);
                        corners.Add(instance);
                    }
                    description.CreateTriangle(outputGroup, corners);
                }
            }
        }
    }
    return changed;
}
#endif
