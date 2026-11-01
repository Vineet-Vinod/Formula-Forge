#include "FFSessionAudit.h"
#include "FFSession.h"
#include "FFGame.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "HighResScreenshot.h"
#include "Framework/Application/SlateApplication.h"
#include "Input/Events.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

FFSessionAudit::FFSessionAudit(UFFSession& session) : Session(session) {
    Started = StageStarted = FPlatformTime::Seconds();
    MenuOnly = FParse::Param(FCommandLine::Get(), TEXT("FFMenuReview"));
    Handle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateRaw(this, &FFSessionAudit::Tick), .1f);
}

FFSessionAudit::~FFSessionAudit() { FTSTicker::GetCoreTicker().RemoveTicker(Handle); }

void FFSessionAudit::Key(FKey key, EInputEvent event) {
    auto& slate = FSlateApplication::Get();
    if (key.IsGamepadKey()) {
        const auto user = FPlatformUserId::CreateFromInternalId(0);
        const auto device = FInputDeviceId::CreateFromInternalId(0);
        if (event == IE_Pressed) slate.OnControllerButtonPressed(key.GetFName(), user, device, false);
        else slate.OnControllerButtonReleased(key.GetFName(), user, device, false);
    } else {
        const FKeyEvent input(key, FModifierKeysState(), 0, false, 0, 0);
        if (event == IE_Pressed) slate.ProcessKeyDownEvent(input);
        else slate.ProcessKeyUpEvent(input);
    }
}

void FFSessionAudit::Tap(FKey key) { Key(key, IE_Pressed); Key(key, IE_Released); }

void FFSessionAudit::Capture(const TCHAR* name) {
    const FString folder = FPaths::ProjectSavedDir() / TEXT("FlowAudit");
    IFileManager::Get().MakeDirectory(*folder, true);
    FScreenshotRequest::RequestScreenshot(folder / FString::Printf(TEXT("%d-%s.png"), Circuit, name), true, false);
}

void FFSessionAudit::Advance(int32 stage) {
    Stage = stage;
    StageStarted = FPlatformTime::Seconds();
    UE_LOG(LogTemp, Display, TEXT("FF_FLOW_AUDIT pid=%u circuit=%d stage=%d"), FPlatformProcess::GetCurrentProcessId(), Circuit, Stage);
}

bool FFSessionAudit::Fail(const TCHAR* reason) {
    UE_LOG(LogTemp, Error, TEXT("FF_FLOW_AUDIT FAIL stage=%d reason=%s"), Stage, reason);
    FPlatformMisc::RequestExitWithStatus(false, 1);
    return false;
}

bool FFSessionAudit::Tick(float deltaSeconds) {
    const double now = FPlatformTime::Seconds();
    if (now - Started > 660) return Fail(TEXT("Session flow timed out"));
    if (!GEngine || !GEngine->GameViewport || !Session.GetWorld() || !Session.GetFirstLocalPlayerController()) return true;
    auto* pawn = Cast<AFormulaTrialPawn>(Session.GetFirstLocalPlayerController()->GetPawn());
    const double age = now - StageStarted;
    if (MenuOnly) {
        if (Session.Screen == EFFScreen::Setup && Stage == 0 && age > 3) {
            Capture(TEXT("setup"));
            Advance(1);
        } else if (Stage == 1 && age > 1) {
            FPlatformMisc::RequestExit(false);
            return false;
        }
        return true;
    }
    switch (Stage) {
    case 0:
        if (Session.Screen == EFFScreen::Setup && age > 2) {
            if (Session.LapLimit() != 0) return Fail(TEXT("Default must be unlimited"));
            if (Circuit == 0) InitialScreenPercentage = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->GetFloat();
            if (Circuit == 0) {
                Tap(EKeys::D);
                Tap(EKeys::A);
                Tap(EKeys::S);
                Tap(EKeys::W);
            } else Tap(Circuit == 1 ? EKeys::Gamepad_DPad_Right : EKeys::Gamepad_LeftStick_Right);
            Advance(1);
        }
        break;
    case 1:
        if (age > 1) {
            if (Session.CircuitIndex != Circuit) return Fail(TEXT("Keyboard circuit selection failed"));
            if (Circuit == 2) {
                Tap(EKeys::Gamepad_DPad_Down);
            }
            Capture(TEXT("setup"));
            Advance(2);
        }
        break;
    case 2:
        if (age > 1) {
            Tap(Circuit == 0 ? EKeys::Enter : EKeys::Gamepad_FaceButton_Bottom);
            Advance(3);
        }
        break;
    case 3:
        if (Session.Screen == EFFScreen::Driving && pawn && pawn->SceneReady) {
            if (pawn->Simulation.circuit != trackCatalog()[Circuit].id || pawn->LoadedVisualTiles() == 0) return Fail(TEXT("Wrong or empty driving world"));
            if (Circuit == 0) {
                pawn->CaptureDrive = false;
                Key(EKeys::W, IE_Pressed);
                Advance(30);
            } else Advance(4);
        }
        break;
    case 30:
        if (age > 1.2) {
            if (!pawn || pawn->Simulation.vehicle.forwardSpeed < 17) return Fail(TEXT("Keyboard W did not accelerate"));
            Key(EKeys::W, IE_Released);
            Key(EKeys::A, IE_Pressed);
            Advance(31);
        }
        break;
    case 31:
        if (age > .3) {
            if (!pawn || pawn->Simulation.vehicle.steerAngle >= -.01f) return Fail(TEXT("Keyboard A did not steer left"));
            Key(EKeys::A, IE_Released);
            Key(EKeys::D, IE_Pressed);
            Advance(32);
        }
        break;
    case 32:
        if (age > .6) {
            if (!pawn || pawn->Simulation.vehicle.steerAngle <= .01f) return Fail(TEXT("Keyboard D did not steer right"));
            Key(EKeys::D, IE_Released);
            BrakeStartSpeed = pawn->Simulation.vehicle.forwardSpeed;
            Key(EKeys::S, IE_Pressed);
            Advance(33);
        }
        break;
    case 33:
        if (age > .8) {
            if (!pawn || pawn->Simulation.vehicle.forwardSpeed >= BrakeStartSpeed) return Fail(TEXT("Keyboard S did not brake"));
            Key(EKeys::S, IE_Released);
            pawn->CaptureDrive = true;
            pawn->ResetTrial();
            Advance(4);
        }
        break;
    case 4:
        if (age > 8) {
            if (!pawn || pawn->Simulation.vehicle.forwardSpeed < 17.0f) return Fail(TEXT("Car did not drive"));
            Capture(TEXT("driving"));
            Advance(5);
        }
        break;
    case 5:
        if (age > 1) { Tap(Circuit == 1 ? EKeys::Gamepad_Special_Right : EKeys::Escape); Advance(6); }
        break;
    case 6:
        if (age > 1) {
            if (Session.Screen != EFFScreen::Paused || !pawn || !pawn->Paused) return Fail(TEXT("Escape did not pause"));
            PausedStation = pawn->Simulation.ProgressStation();
            Capture(TEXT("paused"));
            Advance(7);
        }
        break;
    case 7:
        if (age > 2) {
            if (!pawn || FMath::Abs(pawn->Simulation.ProgressStation() - PausedStation) > .001f) return Fail(TEXT("Car moved while paused"));
            Tap(Circuit == 1 ? EKeys::Gamepad_FaceButton_Bottom : EKeys::SpaceBar);
            Advance(8);
        }
        break;
    case 8:
        if (age > 2) {
            if (Session.Screen != EFFScreen::Driving) return Fail(TEXT("Resume failed"));
            if (Circuit == 2) Advance(12);
            else {
                if (Circuit == 0) Session.GetFirstLocalPlayerController()->ConsoleCommand(TEXT("r.ScreenPercentage 75"), false);
                Tap(EKeys::Escape);
                Advance(9);
            }
        }
        break;
    case 9:
        if (age > 1 && Session.Screen == EFFScreen::Paused) {
            Tap(EKeys::Right);
            Tap(EKeys::Right);
            Tap(EKeys::Enter);
            Advance(10);
        }
        break;
    case 10:
        if (Session.Screen == EFFScreen::Setup && age > 1) {
            if (Circuit == 0 && !FMath::IsNearlyEqual(IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->GetFloat(), InitialScreenPercentage)) return Fail(TEXT("Render scale leaked into the next session"));
            ++Circuit;
            Advance(0);
        }
        break;
    case 12:
        if (Session.Screen == EFFScreen::Results) {
            if (Session.Laps.Num() != 1 || Session.Laps[0].Seconds < 60 || !pawn || !pawn->Paused) return Fail(TEXT("Finite session did not finish a real timed lap"));
            Capture(TEXT("results"));
            Advance(13);
        }
        break;
    case 13:
        if (age > 2) { Session.Focus = 0; Tap(EKeys::Enter); Advance(14); }
        break;
    case 14:
        if (Session.Screen == EFFScreen::Driving && pawn && age > 2) {
            if (!Session.Laps.IsEmpty() || pawn->Simulation.trial.completedLaps != 0) return Fail(TEXT("Drive again did not reset laps"));
            Tap(EKeys::Escape);
            Advance(15);
        }
        break;
    case 15:
        if (Session.Screen == EFFScreen::Paused && age > 1) { Session.Focus = 2; Tap(EKeys::Enter); Advance(16); }
        break;
    case 16:
        if (Session.Screen == EFFScreen::Setup && age > 2) {
            Capture(TEXT("returned-menu"));
            Advance(17);
        }
        break;
    case 17:
        if (age > 2) {
            const FString result = FString::Printf(TEXT("{\"passed\":true,\"process_id\":%u,\"circuits\":3,\"real_finite_lap\":true,\"restart\":true,\"seconds\":%.3f}\n"), FPlatformProcess::GetCurrentProcessId(), now - Started);
            FFileHelper::SaveStringToFile(result, *(FPaths::ProjectSavedDir() / TEXT("FlowAudit/result.json")));
            UE_LOG(LogTemp, Display, TEXT("FF_FLOW_AUDIT PASS"));
            Tap(EKeys::Escape);
            Advance(18);
        }
        break;
    case 18:
        if (age > 3) return Fail(TEXT("Quit action did not exit"));
        break;
    }
    return true;
}
