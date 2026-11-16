#include "FFTrialHUD.hpp"
#include "FFSimulation.hpp"
#include "Native/track_catalog.hpp"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFHUDMapTest, "FormulaForge.HUD.MapHandedness",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)

bool FFHUDMapTest::RunTest(const FString& parameters) {
    for (const TrackCatalogEntry& track : trackCatalog()) {
        const FFSimulation simulation(track.id);
        const FFTrialHUD::FTrialHUDMap map(simulation);
        if (track.referenceCrossings == 0) {
            double area = 0.0;
            for (int32 index = 0; index < map.SampleCount; ++index) {
                const FVector2D first = map.Points[index];
                const FVector2D last = map.Points[(index + 1) % map.SampleCount];
                area += first.X * last.Y - last.X * first.Y;
            }
            TestTrue(FString::Printf(TEXT("%s map preserves the published race direction"),
                UTF8_TO_TCHAR(track.slug.data())), track.clockwise ? area > 0.0 : area < 0.0);
        }
        for (int32 index : {0, map.SampleCount / 4, map.SampleCount / 2}) {
            const FFTrackProjection sample = simulation.Sample(simulation.lapLength * index / map.SampleCount);
            const FVector2D marker = (FVector2D(sample.position.x, sample.position.y) - map.Centre) * map.UnitsToMap;
            TestTrue(FString::Printf(TEXT("%s marker lies on its rendered route"),
                UTF8_TO_TCHAR(track.slug.data())), marker.Equals(map.Points[index], 0.001));
        }
    }
    return true;
}
#endif
