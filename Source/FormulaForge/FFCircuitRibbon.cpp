#include "FFCircuitRibbon.h"

#include "generated_circuit.hpp"

#include "ProceduralMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

#include <cmath>

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
        FVector tangent = b - a;
        tangent = (tangent - normal * FVector::DotProduct(tangent, normal)).GetSafeNormal();
        if (tangent.IsNearlyZero()) tangent = FVector::CrossProduct(FVector::UpVector, normal).GetSafeNormal();
        const bool flip = FVector::DotProduct(FVector::CrossProduct(normal, tangent), c - a) < 0.0f;
        const int32 index = Vertices.Num();
        Vertices.Append({a, b, c});
        Normals.Append({normal, normal, normal});
        UVs.Append({{u0, v0}, {u1, v1}, {u2, v2}});
        Tangents.Append({FProcMeshTangent(tangent, flip), FProcMeshTangent(tangent, flip), FProcMeshTangent(tangent, flip)});
        Colors.Append({FColor::White, FColor::White, FColor::White});
        // Unreal treats clockwise as the front face. +Z is counterclockwise, so upward surfaces swap.
        if (normal.Z > 0.5f) Triangles.Append({index, index + 2, index + 1});
        else Triangles.Append({index, index + 1, index + 2});
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
    component->SetMobility(EComponentMobility::Movable);
    // Vertices are world centimetres. The presentation actor is spawned at the
    // car, so store them relative to that actor or the circuit renders in the sky.
    const FVector origin = owner.GetActorLocation();
    for (FVector& vertex : mesh.Vertices) vertex -= origin;
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

bool Gravel(const TrackCatalogEntry& track, float station, bool left) {
    for (const TrackRunoffZone& zone : track.runoffProfile) {
        if (zone.surface != TrackRunoffSurface::Gravel || zone.widthMeters <= 0.0f) continue;
        if (station < zone.startMeters || station > zone.endMeters) continue;
        if (zone.side == 0 || (zone.side > 0) == left) return true;
    }
    return false;
}

FVector SourceWorld(float x, float y, float z) {
    return World(Vec2{x * 17.0f, -y * 17.0f}, z);
}

void Cone(RibbonMesh& mesh, FVector base, float radius, float height) {
    constexpr int sides = 6;
    const FVector top = base + FVector(0, 0, height * 100.0f);
    for (int side = 0; side < sides; ++side) {
        const float a0 = 2.0f * PI * side / sides;
        const float a1 = 2.0f * PI * (side + 1) / sides;
        const FVector p0 = base + FVector(FMath::Cos(a0), FMath::Sin(a0), 0) * radius * 100.0f;
        const FVector p1 = base + FVector(FMath::Cos(a1), FMath::Sin(a1), 0) * radius * 100.0f;
        mesh.Triangle(p0, p1, top, 0, 0, 1, 0, 0.5f, 1);
    }
}
}

int32 BuildGeneratedRibbon(AActor& owner, const TrackCatalogEntry& track, TArray<TObjectPtr<UProceduralMeshComponent>>& ribbon) {
    const std::vector<CircuitSample> samples = sampleCircuit(track);
    if (samples.size() < 4) return 0;
    const int count = static_cast<int>(samples.size());
    const bool street = Street(track);
    RibbonMesh road, kerbRed, kerbWhite, verge, gravel, wall, ground, soffit, pier, trees, wheel, cabins;
    for (int index = 0; index < count; ++index) {
        const CircuitSample& first = samples[index];
        const CircuitSample& second = samples[(index + 1) % count];
        const Vec2 left{-first.tangent.y, first.tangent.x};
        const Vec2 leftNext{-second.tangent.y, second.tangent.x};
        auto side = [&](const CircuitSample& sample, Vec2 normal, float lane) {
            return World(sample.sim + normal * (lane * 17.0f), circuitSurfaceHeight(sample, lane));
        };
        const float span = FMath::Max(1.0f, (second.station - first.station + track.targetLengthMeters) );
        const float length = FMath::Min(span, track.targetLengthMeters / count * 1.5f);
        const FVector roadLeft = side(first, left, first.halfWidth);
        const FVector roadRight = side(first, left, -first.halfWidth);
        const FVector roadLeftNext = side(second, leftNext, second.halfWidth);
        const FVector roadRightNext = side(second, leftNext, -second.halfWidth);
        if (first.bankQuadratic == 0.0f && second.bankQuadratic == 0.0f) {
            road.Quad(roadLeft, roadLeftNext, roadRightNext, roadRight, length, first.halfWidth * 2.0f);
        } else {
            for (int strip = 0; strip < 8; ++strip) {
                const float high = 1.0f - static_cast<float>(strip) / 4.0f;
                const float low = high - 0.25f;
                road.Quad(side(first, left, high * first.halfWidth),
                    side(second, leftNext, high * second.halfWidth),
                    side(second, leftNext, low * second.halfWidth),
                    side(first, left, low * first.halfWidth), length, first.halfWidth / 4.0f);
            }
        }
        kerbWhite.Quad(roadLeft, roadLeftNext, side(second, leftNext, second.halfWidth - 0.28f), side(first, left, first.halfWidth - 0.28f), length, 0.28f);
        kerbWhite.Quad(side(first, left, -(first.halfWidth - 0.28f)), side(second, leftNext, -(second.halfWidth - 0.28f)), roadRightNext, roadRight, length, 0.28f);
        const bool coloured = FMath::Abs(FMath::Atan2(FVector::CrossProduct(
            FVector(second.tangent.x - first.tangent.x, second.tangent.y - first.tangent.y, 0),
            FVector(first.tangent.x, first.tangent.y, 0)).Z, 1.0f)) > 0.0f;
        RibbonMesh& kerb = (static_cast<int>(first.station / 8.0f) % 2 == 0) ? kerbRed : kerbWhite;
        const bool bankEdges = first.bankFade > 0.0f || second.bankFade > 0.0f;
        if (coloured && bankEdges) {
            const auto fractions = circuitBankEdgeFractions(first, second, .8f, .8f);
            for (const float sign : {-1.0f, 1.0f}) {
                for (std::size_t strip = 1; strip < fractions.size(); ++strip) {
                    const float lo = fractions[strip - 1] * .8f;
                    const float hi = fractions[strip] * .8f;
                    kerb.Quad(side(first, left, sign * (first.halfWidth + hi)),
                        side(second, leftNext, sign * (second.halfWidth + hi)),
                        side(second, leftNext, sign * (second.halfWidth + lo)),
                        side(first, left, sign * (first.halfWidth + lo)), length, hi - lo);
                }
            }
        } else if (coloured) {
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
            RibbonMesh& shoulderMesh = Gravel(track, first.station, positive) ? gravel : verge;
            if (bankEdges) {
                const auto fractions = circuitBankEdgeFractions(first, second, std::abs(outer - inner), std::abs(outerNext - innerNext));
                for (std::size_t strip = 1; strip < fractions.size(); ++strip) {
                    const float lo = fractions[strip - 1], hi = fractions[strip];
                    shoulderMesh.Quad(side(first, left, inner + (outer - inner) * hi),
                        side(second, leftNext, innerNext + (outerNext - innerNext) * hi),
                        side(second, leftNext, innerNext + (outerNext - innerNext) * lo),
                        side(first, left, inner + (outer - inner) * lo), length, shoulder * (hi - lo));
                }
            } else {
                shoulderMesh.Quad(side(first, left, outer), side(second, leftNext, outerNext), side(second, leftNext, innerNext), side(first, left, inner), length, shoulder);
            }
            const FVector base = side(first, left, outer);
            const FVector baseNext = side(second, leftNext, outerNext);
            const FVector top = base + FVector(0, 0, 90.0f);
            const FVector topNext = baseNext + FVector(0, 0, 90.0f);
            const Vec2 outward = left * sign;
            const FVector thickness = FVector(outward.y, -outward.x, 0).GetSafeNormal() * 18.0f;
            wall.Quad(base, baseNext, topNext, top, length, 0.9f);
            wall.Quad(top, topNext, topNext + thickness, top + thickness, length, 0.25f);
        }
    }

    struct TerrainGrid {
        float originX = 0, originY = 0, step = 4;
        int columns = 0, rows = 0;
        TArray<float> heights;
        bool valid = false;
        float Sample(float x, float y) const {
            const float col = (x - originX) / step;
            const float row = (y - originY) / step;
            if (col < 0 || row < 0 || col >= columns - 1 || row >= rows - 1) return 0;
            const int c0 = static_cast<int>(col);
            const int r0 = static_cast<int>(row);
            const float tx = col - c0;
            const float ty = row - r0;
            auto at = [&](int c, int r) { return heights[r * columns + c]; };
            return at(c0, r0) * (1 - tx) * (1 - ty) + at(c0 + 1, r0) * tx * (1 - ty)
                + at(c0, r0 + 1) * (1 - tx) * ty + at(c0 + 1, r0 + 1) * tx * ty;
        }
    } terrain;
    {
        TArray<uint8> terrainBytes;
        const FString terrainPath = FPaths::ProjectContentDir() / TEXT("Generated") / UTF8_TO_TCHAR(track.contentDir.data()) / TEXT("terrain.bin");
        if (FFileHelper::LoadFileToArray(terrainBytes, *terrainPath) && terrainBytes.Num() > 32
            && FMemory::Memcmp(terrainBytes.GetData(), "FFTRN1", 6) == 0) {
            FMemory::Memcpy(&terrain.originX, terrainBytes.GetData() + 8, 8);
            FMemory::Memcpy(&terrain.originY, terrainBytes.GetData() + 16, 8);
            FMemory::Memcpy(&terrain.step, terrainBytes.GetData() + 24, 4);
            uint32 columns = 0, rows = 0;
            FMemory::Memcpy(&columns, terrainBytes.GetData() + 28, 4);
            FMemory::Memcpy(&rows, terrainBytes.GetData() + 32, 4);
            const int64 values = static_cast<int64>(columns) * rows;
            if (columns > 1 && rows > 1 && terrainBytes.Num() >= 36 + values * 4) {
                terrain.columns = static_cast<int>(columns);
                terrain.rows = static_cast<int>(rows);
                terrain.heights.SetNum(values);
                FMemory::Memcpy(terrain.heights.GetData(), terrainBytes.GetData() + 36, values * 4);
                terrain.valid = true;
            }
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
    for (int row = 0; row < rows - 1 && !terrain.valid; ++row) {
        for (int column = 0; column < columns - 1; ++column) {
            auto heightAt = [&](int c, int r, float& metres) {
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
                metres = FMath::Sqrt(best) / 17.0f;
                return World(sim, samples[nearest].elevation - 1.0f);
            };
            float nearA = 0, nearB = 0, nearC = 0, nearD = 0;
            const FVector a = heightAt(column, row, nearA);
            const FVector b = heightAt(column + 1, row, nearB);
            const FVector c = heightAt(column + 1, row + 1, nearC);
            const FVector d = heightAt(column, row + 1, nearD);
            // Keep the sheet off the racing line. A cell over the asphalt was a ceiling.
            if (nearA < 80.0f || nearB < 80.0f || nearC < 80.0f || nearD < 80.0f) continue;
            ground.Quad(a, b, c, d, step, step);
        }
    }
    if (terrain.valid) {
        auto sourceOf = [](const CircuitSample& sample, float& x, float& y) {
            x = sample.sim.x / 17.0f;
            y = -sample.sim.y / 17.0f;
        };
        auto nearestRoads = [&](float x, float y, int& first, int& second, float& firstDistance, float& secondDistance) {
            first = second = 0;
            firstDistance = secondDistance = 1.0e12f;
            const Vec2 sim{x * 17.0f, -y * 17.0f};
            for (int index = 0; index < count; index += 2) {
                const float distance = lengthSq(samples[index].sim - sim);
                if (distance < firstDistance) {
                    second = first;
                    secondDistance = firstDistance;
                    firstDistance = distance;
                    first = index;
                } else if (distance < secondDistance) {
                    secondDistance = distance;
                    second = index;
                }
            }
            firstDistance = FMath::Sqrt(firstDistance) / 17.0f;
            secondDistance = FMath::Sqrt(secondDistance) / 17.0f;
        };
        for (int row = 0; row < terrain.rows - 1; ++row) {
            for (int column = 0; column < terrain.columns - 1; ++column) {
                const float x0 = terrain.originX + column * terrain.step;
                const float y0 = terrain.originY + row * terrain.step;
                const float x1 = x0 + terrain.step;
                const float y1 = y0 + terrain.step;
                const float cx = (x0 + x1) * 0.5f;
                const float cy = (y0 + y1) * 0.5f;
                int nearIndex = 0, otherIndex = 0;
                float nearDistance = 0, otherDistance = 0;
                nearestRoads(cx, cy, nearIndex, otherIndex, nearDistance, otherDistance);
                const CircuitSample& near = samples[nearIndex];
                float gap = FMath::Abs(near.station - samples[otherIndex].station);
                gap = FMath::Min(gap, track.targetLengthMeters - gap);
                const bool crossing = track.deckSeparation && gap > 200.0f && otherDistance < 36.0f;
                const CircuitSample& lower = !crossing || near.elevation <= samples[otherIndex].elevation
                    ? near : samples[otherIndex];
                const float lowerDistance = lower.station == near.station ? nearDistance : otherDistance;
                const float keep = lower.halfWidth + FMath::Max(
                    circuitShoulderMeters(track, lower.station, true),
                    circuitShoulderMeters(track, lower.station, false)) + 3.0f;
                if (lowerDistance < keep) continue;
                auto height = [&](int c, int r) { return terrain.heights[r * terrain.columns + c]; };
                ground.Quad(SourceWorld(x0, y0, height(column, row)), SourceWorld(x1, y0, height(column + 1, row)),
                    SourceWorld(x1, y1, height(column + 1, row + 1)), SourceWorld(x0, y1, height(column, row + 1)),
                    terrain.step, terrain.step);
            }
        }
        if (track.deckSeparation) {
            for (int index = 0; index < count; ++index) {
                const CircuitSample& first = samples[index];
                const CircuitSample& second = samples[(index + 1) % count];
                float x = 0, y = 0;
                sourceOf(first, x, y);
                const float clearance = first.elevation - terrain.Sample(x, y);
                if (clearance < 1.1f) continue;
                const Vec2 left{-first.tangent.y, first.tangent.x};
                const Vec2 leftNext{-second.tangent.y, second.tangent.x};
                auto side = [&](const CircuitSample& sample, Vec2 normal, float lane) {
                    return World(sample.sim + normal * (lane * 17.0f), circuitSurfaceHeight(sample, lane));
                };
                const FVector leftEdge = side(first, left, first.halfWidth);
                const FVector rightEdge = side(first, left, -first.halfWidth);
                const FVector leftNextEdge = side(second, leftNext, second.halfWidth);
                const FVector rightNextEdge = side(second, leftNext, -second.halfWidth);
                auto lower = [](FVector point) { return point - FVector(0, 0, 55.0f); };
                const float span = track.targetLengthMeters / count;
                soffit.Quad(lower(leftEdge), lower(leftNextEdge), lower(rightNextEdge), lower(rightEdge), span, first.halfWidth * 2.0f);
                soffit.Quad(leftEdge, leftNextEdge, lower(leftNextEdge), lower(leftEdge), span, 0.55f);
                soffit.Quad(rightNextEdge, rightEdge, lower(rightEdge), lower(rightNextEdge), span, 0.55f);
                if (clearance > 4.2f && index % 5 == 0) {
                    const float groundZ = terrain.Sample(x, y);
                    const FVector bottom = SourceWorld(x, y, groundZ);
                    const FVector top = SourceWorld(x, y, first.elevation - 0.55f);
                    const FVector along = (SourceWorld(first.tangent.x, -first.tangent.y, 0) - SourceWorld(0, 0, 0)).GetSafeNormal() * 80.0f;
                    const FVector across = (SourceWorld(first.tangent.y, first.tangent.x, 0) - SourceWorld(0, 0, 0)).GetSafeNormal() * 220.0f;
                    const FVector a = bottom - along - across;
                    const FVector b = bottom + along - across;
                    const FVector c = bottom + along + across;
                    const FVector d = bottom - along + across;
                    const FVector a2 = a + (top - bottom);
                    const FVector b2 = b + (top - bottom);
                    const FVector c2 = c + (top - bottom);
                    const FVector d2 = d + (top - bottom);
                    pier.Quad(a, b, b2, a2, 1.6f, clearance);
                    pier.Quad(b, c, c2, b2, 4.4f, clearance);
                    pier.Quad(c, d, d2, c2, 1.6f, clearance);
                    pier.Quad(d, a, a2, d2, 4.4f, clearance);
                }
            }
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
            float nearestEdge = best;
            for (const FVector2D& point : ring) {
                const Vec2 corner{static_cast<float>(point.X) * 17.0f, -static_cast<float>(point.Y) * 17.0f};
                for (int index = 0; index < count; index += 3) {
                    nearestEdge = FMath::Min(nearestEdge, lengthSq(samples[index].sim - corner));
                }
            }
            const float clearanceMetres = track.slug == "japan" ? samples[nearest].halfWidth + 4.0f : 20.0f;
            if (nearestEdge < FMath::Square(clearanceMetres * 17.0f)) continue;
            if (track.slug != "japan" && FMath::Sqrt(best) < 45.0f * 17.0f) height = FMath::Min(height, 6.0f);
            const float baseZ = terrain.valid ? terrain.Sample(static_cast<float>(centroid.X), static_cast<float>(centroid.Y)) : samples[nearest].elevation;
            for (int32 edge = 0; edge < ring.Num(); ++edge) {
                const FVector2D a = ring[edge];
                const FVector2D b = ring[(edge + 1) % ring.Num()];
                const FVector bottomA(-100.0f * a.Y, -100.0f * a.X, baseZ * 100.0f);
                const FVector bottomB(-100.0f * b.Y, -100.0f * b.X, baseZ * 100.0f);
                const FVector topA = bottomA + FVector(0, 0, height * 100.0f);
                const FVector topB = bottomB + FVector(0, 0, height * 100.0f);
                buildings.Quad(bottomA, bottomB, topB, topA, FVector::Dist(bottomA, bottomB) / 100.0f, height);
                if (track.slug == "japan" && height > 10.0f) {
                    for (int tier = 0; tier < 4; ++tier) {
                        const float z0 = baseZ + height * (0.22f + tier * 0.16f);
                        const FVector seatA = bottomA + FVector(0, 0, (z0 - baseZ) * 100.0f);
                        const FVector seatB = bottomB + FVector(0, 0, (z0 - baseZ) * 100.0f);
                        cabins.Quad(seatA, seatB, seatB + FVector(0, 0, 140.0f), seatA + FVector(0, 0, 140.0f),
                            FVector::Dist(bottomA, bottomB) / 100.0f, 1.4f);
                    }
                }
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

    TArray<uint8> landmarkBytes;
    const FString landmarkPath = FPaths::ProjectContentDir() / TEXT("Generated") / UTF8_TO_TCHAR(track.contentDir.data()) / TEXT("landmarks.bin");
    if (FFileHelper::LoadFileToArray(landmarkBytes, *landmarkPath) && landmarkBytes.Num() >= 12
        && FMemory::Memcmp(landmarkBytes.GetData(), "FFLMK1", 6) == 0) {
        int32 cursor = 8;
        auto read = [&](auto& value) {
            if (cursor + static_cast<int32>(sizeof(value)) > landmarkBytes.Num()) return false;
            FMemory::Memcpy(&value, landmarkBytes.GetData() + cursor, sizeof(value));
            cursor += sizeof(value);
            return true;
        };
        uint32 landmarkCount = 0;
        read(landmarkCount);
        for (uint32 landmark = 0; landmark < landmarkCount; ++landmark) {
            uint32 kind = 0;
            float x = 0, y = 0, radius = 0, hub = 0;
            if (!read(kind) || !read(x) || !read(y) || !read(radius) || !read(hub) || kind != 1 || radius < 4.0f) break;
            const float baseZ = terrain.valid ? terrain.Sample(x, y) : 0.0f;
            const FVector centre = SourceWorld(x, y, baseZ + hub);
            int nearIndex = 0;
            float best = 1.0e12f;
            const Vec2 sim{x * 17.0f, -y * 17.0f};
            for (int index = 0; index < count; index += 4) {
                const float distance = lengthSq(samples[index].sim - sim);
                if (distance < best) {
                    best = distance;
                    nearIndex = index;
                }
            }
            const CircuitSample& facing = samples[nearIndex];
            const FVector toward = (SourceWorld(facing.sim.x / 17.0f, -facing.sim.y / 17.0f, baseZ + hub) - centre).GetSafeNormal();
            const FVector axis = FVector::CrossProduct(toward, FVector::UpVector).GetSafeNormal();
            constexpr int segments = 20;
            for (int segment = 0; segment < segments; ++segment) {
                const float a0 = 2.0f * PI * segment / segments;
                const float a1 = 2.0f * PI * (segment + 1) / segments;
                auto rim = [&](float angle, float scale) {
                    return centre + (toward * FMath::Cos(angle) + FVector::UpVector * FMath::Sin(angle)) * (radius * scale * 100.0f);
                };
                wheel.Quad(rim(a0, 1.0f), rim(a1, 1.0f), rim(a1, 0.90f), rim(a0, 0.90f), 8.0f, 2.4f);
                if (segment % 3 == 0) {
                    const FVector spoke = rim(a0, 0.92f);
                    const FVector side = axis * 18.0f;
                    wheel.Quad(centre - side, spoke - side, spoke + side, centre + side, radius, 0.4f);
                    const FVector cabin = rim(a0, 1.04f);
                    const FVector cabinUp = FVector::UpVector * 110.0f;
                    const FVector cabinSide = axis * 90.0f;
                    cabins.Quad(cabin - cabinSide, cabin + cabinSide, cabin + cabinSide + cabinUp, cabin - cabinSide + cabinUp, 1.8f, 1.1f);
                }
            }
            const FVector footA = SourceWorld(x, y, baseZ) + axis * (radius * 55.0f);
            const FVector footB = SourceWorld(x, y, baseZ) - axis * (radius * 55.0f);
            const FVector brace = axis * 40.0f;
            wheel.Quad(footA - brace, footA + brace, centre + brace, centre - brace, radius, 0.8f);
            wheel.Quad(footB - brace, footB + brace, centre + brace, centre - brace, radius, 0.8f);
        }
    }

    UMaterialInterface* asphalt = Material(TEXT("/Game/Generated/Materials/rebuild_road_asphalt.rebuild_road_asphalt"));
    UMaterialInterface* grass = Material(TEXT("/Game/Generated/Monza/Materials/Grass.Grass"));
    UMaterialInterface* red = Material(TEXT("/Game/Generated/Monza/Materials/Red_paint.Red_paint"));
    UMaterialInterface* white = Material(TEXT("/Game/Generated/Monza/Materials/White_paint.White_paint"));
    UMaterialInterface* armco = Material(TEXT("/Game/Generated/Monza/Materials/Armco.Armco"));
    UMaterialInterface* concrete = Material(TEXT("/Game/Generated/Monza/Materials/Concrete.Concrete"));
    UMaterialInterface* gravelMaterial = Material(TEXT("/Game/Generated/Monza/Materials/Gravel.Gravel"));
    UMaterialInterface* foliage = Material(TEXT("/Game/Generated/Monza/Materials/Green_paint.Green_paint"));
    UMaterialInterface* vergeMaterial = street
        ? Material(TEXT("/Game/Generated/Materials/rebuild_runoff_asphalt.rebuild_runoff_asphalt"))
        : grass;
    int32 sections = 0;
    auto keep = [&](UProceduralMeshComponent* component) {
        if (component == nullptr) return;
        ribbon.Add(component);
        ++sections;
    };
    keep(Commit(owner, ground, grass, false));
    keep(Commit(owner, verge, vergeMaterial, false));
    keep(Commit(owner, gravel, gravelMaterial, false));
    keep(Commit(owner, road, asphalt, false));
    keep(Commit(owner, soffit, concrete, true));
    keep(Commit(owner, pier, concrete, true));
    keep(Commit(owner, kerbRed, red, true));
    keep(Commit(owner, kerbWhite, white, true));
    keep(Commit(owner, wall, armco, true));
    keep(Commit(owner, trees, foliage, false));
    keep(Commit(owner, wheel, white, true));
    keep(Commit(owner, cabins, red, true));
    keep(Commit(owner, buildings, concrete, true));
    return sections;
}
