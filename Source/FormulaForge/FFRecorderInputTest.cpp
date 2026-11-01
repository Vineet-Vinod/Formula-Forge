#include "FFGame.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "InputKeyEventArgs.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFRecorderInputTest, "FormulaForge.Recorder.InputEvents",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)

bool FFRecorderInputTest::RunTest(const FString& parameters) {
    if (GEngine == nullptr || GEngine->GameViewport == nullptr) {
        AddError(TEXT("A running game viewport is required"));
        return false;
    }
    UGameViewportClient* viewport = GEngine->GameViewport;
    auto* player = viewport->GetWorld()->GetFirstPlayerController();
    auto* pawn = player != nullptr ? Cast<AFormulaTrialPawn>(player->GetPawn()) : nullptr;
    if (pawn == nullptr || !pawn->RecordingStatus().StartsWith(TEXT("REC "))) {
        AddError(TEXT("Launch with -FFRecord and a rendered viewport"));
        return false;
    }
    const auto device = FInputDeviceId::CreateFromInternalId(0);
    for (float value : {0.08f, 0.21f, 0.0f}) {
        viewport->InputAxis(FInputKeyEventArgs(viewport->Viewport, device, EKeys::Gamepad_LeftX,
            value, 1.0f / 60.0f, 3, FPlatformTime::Cycles64()));
    }
    viewport->InputAxis(FInputKeyEventArgs(viewport->Viewport, device, EKeys::Gamepad_RightTriggerAxis,
        0.7f, 1.0f / 60.0f, 1, FPlatformTime::Cycles64()));
    for (const FKey& key : {EKeys::Gamepad_RightShoulder, EKeys::E}) {
        for (EInputEvent action : {IE_Pressed, IE_Released}) {
            viewport->InputKey(FInputKeyEventArgs(viewport->Viewport, device, key, action,
                FPlatformTime::Cycles64()));
        }
    }
    return true;
}
#endif
