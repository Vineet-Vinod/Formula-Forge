#include "FFMeshPortal.hpp"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "StaticMeshAttributes.h"
#include "StaticMeshOperations.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFMeshPortalTest, "FormulaForge.Assets.PortalClipping",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFMeshPortalTest::RunTest(const FString& parameters) {
    const FString source = FPaths::ProjectDir() / TEXT("build/tmp/portal-test.json");
    TestTrue(TEXT("Write the source-frame portal"), FFileHelper::SaveStringToFile(
        TEXT("{\"portals\":[{\"polygon_xy_m\":[[0,0],[2,0],[2,2],[0,2]],\"bottom_m\":0,\"top_m\":2}]}"), *source));
    TArray<FFMeshPortalVolume> portals;
    TestTrue(TEXT("Parse a height-qualified source-frame portal"), FFReadMeshPortals(source, portals));
    if (portals.Num() != 1) return false;
    FMeshDescription description;
    FStaticMeshAttributes attributes(description);
    attributes.Register();
    auto positions = attributes.GetVertexPositions();
    auto normals = attributes.GetVertexInstanceNormals();
    auto tangents = attributes.GetVertexInstanceTangents();
    auto signs = attributes.GetVertexInstanceBinormalSigns();
    auto colors = attributes.GetVertexInstanceColors();
    auto uvs = attributes.GetVertexInstanceUVs();
    uvs.SetNumChannels(2);
    auto slots = attributes.GetPolygonGroupMaterialSlotNames();
    const FPolygonGroupID barrier = description.CreatePolygonGroup();
    const FPolygonGroupID retained = description.CreatePolygonGroup();
    slots[barrier] = TEXT("Barrier");
    slots[retained] = TEXT("Retained");
    const auto add = [&](FPolygonGroupID group, const TArray<FVector3f>& points) {
        TArray<FVertexInstanceID> corners;
        for (const FVector3f& point : points) {
            const FVertexID vertex = description.CreateVertex();
            positions[vertex] = point;
            const FVertexInstanceID instance = description.CreateVertexInstance(vertex);
            normals[instance] = FVector3f(0, 1, 0);
            tangents[instance] = FVector3f(1, 0, 0);
            signs[instance] = -1;
            colors[instance] = FVector4f(point.X * 0.001f + 0.5f, point.Y * 0.001f + 0.5f, 0, 1);
            uvs.Set(instance, 0, FVector2f(point.X * 0.01f, point.Y * 0.01f));
            uvs.Set(instance, 1, FVector2f(point.X * 0.001f + 0.5f, point.Y * 0.001f + 0.5f));
            corners.Add(instance);
        }
        return description.CreateTriangle(group, corners);
    };
    add(barrier, {{-300, -100, 0}, {100, -100, 0}, {-300, -100, 300}});
    const FTriangleID distant = add(barrier, {{1000, 1000, 0}, {1100, 1000, 0}, {1000, 1100, 0}});
    const FTriangleID excluded = add(retained, {{-100, -100, 1}, {-50, -100, 1}, {-100, -50, 1}});
    const TSet<FName> selected{TEXT("Barrier")};
    FMeshDescription painted = description;
    TestEqual(TEXT("Only the intersecting wall is split"), FFCutMeshPortals(description, portals, selected), 1);
    TestTrue(TEXT("Distant triangle retains its identity"), description.Triangles().IsValid(distant));
    TestTrue(TEXT("Excluded material retains its identity"), description.Triangles().IsValid(excluded));
    TestEqual(TEXT("Baked AO UV channel retained"), uvs.GetNumChannels(), 2);
    for (const FTriangleID triangle : description.Triangles().GetElementIDs()) {
        FVector3d centroid = FVector3d::ZeroVector;
        for (const FVertexInstanceID instance : description.GetTriangleVertexInstances(triangle)) {
            const FVector3f point = positions[description.GetVertexInstanceVertex(instance)];
            centroid += FVector3d(point) / 3.0;
            const FVector2f expected(point.X * 0.001f + 0.5f, point.Y * 0.001f + 0.5f);
            TestTrue(TEXT("UV1 survives interpolation"), uvs.Get(instance, 1).Equals(expected, 1e-5f));
            TestTrue(TEXT("Vertex color survives interpolation"), colors[instance].Equals(FVector4f(expected.X, expected.Y, 0, 1), 1e-5f));
            TestEqual(TEXT("Tangent handedness retained"), signs[instance], -1.0f);
        }
        if (description.GetTrianglePolygonGroup(triangle) == barrier) {
            bool inside = true;
            for (const auto& plane : portals[0]) {
                inside &= FVector3d::DotProduct(plane.normal, centroid) - plane.distance > 1e-7;
            }
            TestFalse(TEXT("No wall face remains inside the portal"), inside);
        }
    }
    TestEqual(TEXT("Material correction splits the same finite domain"),
        FFCutMeshPortals(painted, portals, selected, TEXT("Asphalt")), 1);
    const FStaticMeshConstAttributes paintedAttributes(painted);
    const auto paintedSlots = paintedAttributes.GetPolygonGroupMaterialSlotNames();
    bool hasAsphalt = false;
    for (const FPolygonGroupID group : painted.PolygonGroups().GetElementIDs()) {
        hasAsphalt |= paintedSlots[group] == TEXT("Asphalt") && painted.GetPolygonGroupTriangles(group).Num() > 0;
    }
    TestTrue(TEXT("Inside faces become asphalt instead of a hole"), hasAsphalt);
    TestEqual(TEXT("Reclassification retains UV1"), paintedAttributes.GetVertexInstanceUVs().GetNumChannels(), 2);
    const auto compactAndCheck = [&](FMeshDescription& mesh) {
        FElementIDRemappings remappings;
        mesh.Compact(remappings);
        mesh.TriangleAttributes().SetNumElements(mesh.Triangles().GetArraySize());
        TSet<FTriangleID> seen;
        int32 references = 0;
        for (const FPolygonID polygon : mesh.Polygons().GetElementIDs()) {
            for (const FTriangleID triangle : mesh.GetPolygonTriangles(polygon)) {
                ++references;
                TestTrue(TEXT("Compacted polygon references an existing triangle"), mesh.Triangles().IsValid(triangle));
                TestFalse(TEXT("Compacted triangle belongs to only one polygon"), seen.Contains(triangle));
                seen.Add(triangle);
            }
        }
        TestEqual(TEXT("Compacted polygon wedges match the global triangle count"), references, mesh.Triangles().Num());
        TestTrue(TEXT("Static mesh unique-vertex commit pass accepts the clipped topology"),
            FStaticMeshOperations::GetUniqueVertexCount(mesh) > 0);
    };
    compactAndCheck(description);
    compactAndCheck(painted);
    const FFMeshPortalVolume secondPortal{
        {FVector3d(1, 0, 0), 1050}, {FVector3d(-1, 0, 0), -1200},
        {FVector3d(0, 1, 0), 999}, {FVector3d(0, -1, 0), -1200},
        {FVector3d(0, 0, 1), -1}, {FVector3d(0, 0, -1), -10}};
    TestEqual(TEXT("A repeated cut after compact accepts zero-channel triangle UV metadata"),
        FFCutMeshPortals(description, {secondPortal}, selected), 1);
    TestEqual(TEXT("A repeated reclassification after compact accepts the retained attribute arrays"),
        FFCutMeshPortals(painted, {secondPortal}, selected, TEXT("Asphalt")), 1);
    compactAndCheck(description);
    compactAndCheck(painted);
    return true;
}
#endif
