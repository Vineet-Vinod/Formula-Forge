#include "FFSession.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFSessionTest, "FormulaForge.Session.LapLimits",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)

bool FFSessionTest::RunTest(const FString& parameters) {
    auto* session = NewObject<UFFSession>();
    TestEqual(TEXT("Default session is unlimited"), session->LapLimit(), 0);
    session->Screen = EFFScreen::Driving;
    session->ObserveLap(0, 0, false);
    TestEqual(TEXT("Out-lap is excluded"), session->Laps.Num(), 0);
    for (int32 lap = 1; lap <= 12; ++lap) session->ObserveLap(lap, 80 + lap, true);
    TestTrue(TEXT("Unlimited stays driving"), session->Screen == EFFScreen::Driving);
    session->ResetLaps();
    session->LapIndex = 2;
    TestEqual(TEXT("Three-lap selection"), session->LapLimit(), 3);
    session->ObserveLap(1, 90, true);
    session->ObserveLap(1, 90, true);
    TestEqual(TEXT("Same completed lap is recorded once"), session->Laps.Num(), 1);
    session->ObserveLap(2, 88, false);
    TestTrue(TEXT("Invalid lap retained for results"), !session->Laps[1].Valid);
    TestTrue(TEXT("Session continues before the limit"), session->Screen == EFFScreen::Driving);
    session->ObserveLap(3, 89, true);
    TestTrue(TEXT("Finite session reaches results"), session->Screen == EFFScreen::Results);
    session->ResetLaps();
    TestEqual(TEXT("Restart clears session laps"), session->Laps.Num(), 0);
    return true;
}
#endif
