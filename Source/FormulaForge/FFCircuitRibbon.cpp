#include "FFCircuitRibbon.h"

#include "generated_circuit.hpp"

#include "ProceduralMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace {
struct RibbonMesh {
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FProcMeshTangent> Tangents;
    TArray<FColor> Colors;

    void Triangle(FVector a, FVector b, FVector c, float u0, float v0, float u1, float v1, float u2, float v2) {
        FVector normal = FVector::CrossProduct(b - a, c - a).GetSafeNormal();
        if (normal.Z < 0.0f) {
            Swap(b, c);
            Swap(u1, u2);
            Swap(v1, v2);
            normal *= -1.0f;
        }
        if (normal.IsNearlyZero()) return;
        const int32 index = Vertices.Num();
        const FVector tangent = (b - a).GetSafeNormal();
        Vertices.Append({a, b, c});
        Normals.Append({normal, normal, normal});
        UVs.Append({{u0, v0}, {u1, v1}, {u2, v2}});
        Tangents.Append({FProcMeshTangent(tangent, false), FProcMeshTangent(tangent, false), FProcMeshTangent(tangent, false)});
        Colors.Append({FColor::White, FColor::White, FColor::White});
        Triangles.Append({index, index + 1, index + 2});
    }

    void Quad(FVector a, FVector b, FVector c, FVector d, float lengthMetres, float widthMetres) {
        Triangle(a, b, c, 0, 0, lengthMetres / 4.0f, 0, lengthMetres / 4.0f, widthMetres / 4.0f);
        Triangle(a, c, d, 0, 0, lengthMetres / 4.0f, widthMetres / 4.0f, 0, widthMetres / 4.0f);
    }
};

FVector World(Vec2 sim, float elevation) {
    return FVector(sim.y, -sim.x, elevation * 17.0f) * (100.0f / 17.0f);
}

UMaterialInterface* Material(const TCHAR* path) {
    if (UMaterialInterface* material = LoadObject<UMaterialInterface>(nullptr, path)) return material;
    return LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
}

UProceduralMeshComponent* Commit(AActor& owner, RibbonMesh& mesh, UMaterialInterface* material, bool shadow) {
    if (mesh.Triangles.Num() == 0) return nullptr;
    UProceduralMeshComponent* component = NewObject<UProceduralMeshComponent>(&owner);
    component->SetupAttachment(owner.GetRootComponent());
    component->SetMobility(EComponentMobility::Static);
    component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    component->SetCastShadow(shadow);
    component->CreateMeshSection(0, mesh.Vertices, mesh.Triangles, mesh.Normals, mesh.UVs, mesh.Colors, mesh.Tangents, false);
    component->SetMaterial(0, material);
    component->RegisterComponent();
    return component;
}

bool Street(const TrackCatalogEntry& track) {
    const std::string_view tag = track.environmentTag;
    return tag == "corniche" || tag == "park-street" || tag == "island" || tag == "harbour" ||
        tag == "city" || tag == "marina" || tag == "strip" || tag == "capital";
}
}

int32 BuildGeneratedRibbon(AActor& owner, const TrackCatalogEntry& track, TArray<TObjectPtr<UProceduralMeshComponent>>& ribbon) {
    const std::vector<CircuitSample> samples = sampleCircuit(track);
    if (samples.size() < 4) return 0;
    const int count = static_cast<int>(samples.size());
    const bool street = Street(track);
    RibbonMesh road, kerbRed, kerbWhite, verge, wall, ground;
    for (int index = 0; index < count; ++index) {
        const CircuitSample& first = samples[index];
        const CircuitSample& second = samples[(index + 1) % count];
        const Vec2 left{-first.tangent.y, first.tangent.x};
        const Vec2 leftNext{-second.tangent.y, second.tangent.x};
        auto side = [&](const CircuitSample& sample, Vec2 normal, float lane) {
            return World(sample.sim + normal * (lane * 17.0f), sample.elevation + sample.bankSlope * lane);
        };
        const float span = FMath::Max(1.0f, (second.station - first.station + track.targetLengthMeters) );
        const float length = FMath::Min(span, track.targetLengthMeters / count * 1.5f);
        const FVector roadLeft = side(first, left, first.halfWidth);
        const FVector roadRight = side(first, left, -first.halfWidth);
        const FVector roadLeftNext = side(second, leftNext, second.halfWidth);
        const FVector roadRightNext = side(second, leftNext, -second.halfWidth);
        road.Quad(roadLeft, roadLeftNext, roadRightNext, roadRight, length, first.halfWidth * 2.0f);
        const bool coloured = FMath::Abs(FMath::Atan2(FVector::CrossProduct(
            FVector(second.tangent.x - first.tangent.x, second.tangent.y - first.tangent.y, 0),
            FVector(first.tangent.x, first.tangent.y, 0)).Z, 1.0f)) > 0.0f;
        RibbonMesh& kerb = (static_cast<int>(first.station / 8.0f) % 2 == 0) ? kerbRed : kerbWhite;
        if (coloured) {
            kerb.Quad(side(first, left, first.halfWidth + 0.8f), side(second, leftNext, second.halfWidth + 0.8f), roadLeftNext, roadLeft, length, 0.8f);
            kerb.Quad(roadRight, roadRightNext, side(second, leftNext, -(second.halfWidth + 0.8f)), side(first, left, -(first.halfWidth + 0.8f)), length, 0.8f);
        }
        for (const bool positive : {true, false}) {
            const float sign = positive ? 1.0f : -1.0f;
            const float shoulder = FMath::Clamp(sampleTrackShoulderMeters(track, first.station, positive), 1.2f, 24.0f);
            const float inner = sign * (first.halfWidth + 0.85f);
            const float outer = sign * (first.halfWidth + 0.85f + shoulder);
            const float innerNext = sign * (second.halfWidth + 0.85f);
            const float outerNext = sign * (second.halfWidth + 0.85f + sampleTrackShoulderMeters(track, second.station, positive));
            verge.Quad(side(first, left, outer), side(second, leftNext, outerNext), side(second, leftNext, innerNext), side(first, left, inner), length, shoulder);
            const FVector base = side(first, left, outer);
            const FVector baseNext = side(second, leftNext, outerNext);
            const FVector top = base + FVector(0, 0, 90.0f);
            const FVector topNext = baseNext + FVector(0, 0, 90.0f);
            const FVector thickness = FVector(left.y, left.x, 0).GetSafeNormal() * (sign * 18.0f);
            wall.Quad(base, baseNext, topNext, top, length, 0.9f);
            wall.Quad(top, topNext, topNext + thickness, top + thickness, length, 0.25f);
        }
    }

    float minX = 1.0e9f, maxX = -1.0e9f, minY = 1.0e9f, maxY = -1.0e9f;
    for (const CircuitSample& sample : samples) {
        minX = FMath::Min(minX, sample.sim.x / 17.0f);
        maxX = FMath::Max(maxX, sample.sim.x / 17.0f);
        minY = FMath::Min(minY, -sample.sim.y / 17.0f);
        maxY = FMath::Max(maxY, -sample.sim.y / 17.0f);
    }
    constexpr float step = 36.0f;
    const int columns = FMath::Clamp(static_cast<int>((maxX - minX + 80.0f) / step), 2, 180);
    const int rows = FMath::Clamp(static_cast<int>((maxY - minY + 80.0f) / step), 2, 180);
    const float originX = minX - 40.0f;
    const float originY = minY - 40.0f;
    for (int row = 0; row < rows - 1; ++row) {
        for (int column = 0; column < columns - 1; ++column) {
            auto heightAt = [&](int c, int r) {
                const Vec2 sim{(originX + c * step) * 17.0f, -(originY + r * step) * 17.0f};
                int nearest = 0;
                float best = 1.0e12f;
                for (int index = 0; index < count; index += 4) {
                    const float distance = lengthSq(samples[index].sim - sim);
                    if (distance < best) {
                        best = distance;
                        nearest = index;
                    }
                }
                const float metres = FMath::Sqrt(best);
                float height = samples[nearest].elevation;
                if (metres > samples[nearest].halfWidth + 6.0f) height -= FMath::Min(1.5f, 0.012f * (metres - samples[nearest].halfWidth));
                return World(sim, height);
            };
            const FVector a = heightAt(column, row);
            const FVector b = heightAt(column + 1, row);
            const FVector c = heightAt(column + 1, row + 1);
            const FVector d = heightAt(column, row + 1);
            ground.Quad(a, b, c, d, step, step);
        }
    }

    TArray<uint8> bytes;
    const FString buildingPath = FPaths::ProjectContentDir() / TEXT("Generated") / UTF8_TO_TCHAR(track.contentDir.data()) / TEXT("buildings.bin");
    RibbonMesh buildings;
    if (FFileHelper::LoadFileToArray(bytes, *buildingPath) && bytes.Num() >= 12 && FMemory::Memcmp(bytes.GetData(), "FFBLD1", 6) == 0) {
        int32 cursor = 8;
        auto read = [&](auto& value) {
            if (cursor + static_cast<int32>(sizeof(value)) > bytes.Num()) return false;
            FMemory::Memcpy(&value, bytes.GetData() + cursor, sizeof(value));
            cursor += sizeof(value);
            return true;
        };
        uint32 countBuildings = 0;
        read(countBuildings);
        for (uint32 building = 0; building < countBuildings; ++building) {
            uint32 vertices = 0;
            float height = 0;
            if (!read(vertices) || !read(height) || vertices < 3 || vertices > 64) break;
            TArray<FVector2D> ring;
            for (uint32 vertex = 0; vertex < vertices; ++vertex) {
                float x = 0, y = 0;
                if (!read(x) || !read(y)) { vertices = 0; break; }
                ring.Add(FVector2D(x, y));
            }
            FVector2D centroid = FVector2D::ZeroVector;
            for (const FVector2D& point : ring) centroid += point;
            centroid /= ring.Num();
            const Vec2 sim{static_cast<float>(centroid.X) * 17.0f, -static_cast<float>(centroid.Y) * 17.0f};
            int nearest = 0;
            float best = 1.0e12f;
            for (int index = 0; index < count; index += 3) {
                const float distance = lengthSq(samples[index].sim - sim);
                if (distance < best) {
                    best = distance;
                    nearest = index;
                }
            }
            const float baseZ = samples[nearest].elevation;
            for (int32 edge = 0; edge < ring.Num(); ++edge) {
                const FVector2D a = ring[edge];
                const FVector2D b = ring[(edge + 1) % ring.Num()];
                const FVector bottomA(-100.0f * a.Y, -100.0f * a.X, baseZ * 100.0f);
                const FVector bottomB(-100.0f * b.Y, -100.0f * b.X, baseZ * 100.0f);
                const FVector topA = bottomA + FVector(0, 0, height * 100.0f);
                const FVector topB = bottomB + FVector(0, 0, height * 100.0f);
                buildings.Quad(bottomA, bottomB, topB, topA, FVector::Dist(bottomA, bottomB) / 100.0f, height);
            }
            const FVector roof(-100.0f * centroid.Y, -100.0f * centroid.X, (baseZ + height) * 100.0f);
            for (int32 edge = 1; edge < ring.Num() - 1; ++edge) {
                const FVector a(-100.0f * ring[0].Y, -100.0f * ring[0].X, roof.Z);
                const FVector b(-100.0f * ring[edge].Y, -100.0f * ring[edge].X, roof.Z);
                const FVector c(-100.0f * ring[edge + 1].Y, -100.0f * ring[edge + 1].X, roof.Z);
                buildings.Triangle(a, b, c, 0, 0, 1, 0, 1, 1);
            }
        }
    }

    UMaterialInterface* asphalt = Material(TEXT("/Game/Generated/Monza/Materials/Asphalt.Asphalt"));
    UMaterialInterface* grass = Material(TEXT("/Game/Generated/Monza/Materials/Grass.Grass"));
    UMaterialInterface* red = Material(TEXT("/Game/Generated/Monza/Materials/Red_paint.Red_paint"));
    UMaterialInterface* white = Material(TEXT("/Game/Generated/Monza/Materials/White_paint.White_paint"));
    UMaterialInterface* armco = Material(TEXT("/Game/Generated/Monza/Materials/Armco.Armco"));
    UMaterialInterface* concrete = Material(TEXT("/Game/Generated/Monza/Materials/Concrete.Concrete"));
    UMaterialInterface* vergeMaterial = street ? asphalt : grass;
    int32 sections = 0;
    auto keep = [&](UProceduralMeshComponent* component) {
        if (component == nullptr) return;
        ribbon.Add(component);
        ++sections;
    };
    keep(Commit(owner, ground, grass, false));
    keep(Commit(owner, verge, vergeMaterial, true));
    keep(Commit(owner, road, asphalt, true));
    keep(Commit(owner, kerbRed, red, true));
    keep(Commit(owner, kerbWhite, white, true));
    keep(Commit(owner, wall, armco, true));
    keep(Commit(owner, buildings, concrete, true));
    return sections;
}
