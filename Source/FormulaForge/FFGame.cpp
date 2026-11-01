#include "FFGame.h"
#include "FFSession.h"
#include "FFPresentation.h"
#include "FFLapRecorder.h"
#include "FFBodySupport.hpp"
#include "FFRacingStint.hpp"

#include <sstream>

#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "HighResScreenshot.h"
#include "ImageUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "ProfilingDebugging/CsvProfiler.h"
#include "RenderingThread.h"
#include "RHICommandList.h"
#include "String/LexFromString.h"

CSV_DEFINE_CATEGORY(FormulaForge, true);

namespace {
FVector WorldPosition(Vec2 position, float elevation) {
    return FVector(position.y, -position.x, elevation) * (100.0 / 17.0);
}

float ControllerSteer(float value) {
    const float absolute = FMath::Abs(value);
    if (absolute < 0.14f) return 0.0f;
    const float normalized = (absolute - 0.14f) / 0.86f;
    return FMath::Sign(value) * (0.25f * normalized + 0.75f * normalized * normalized * normalized);
}

void FinishRacingStint(const FFRacingEvaluation& result, const TCHAR* mode) {
    UE_LOG(LogTemp, Display, TEXT("RACING_STINT valid=%d outlap_s=%.9f pushlap_s=%.9f inlap_s=%.9f completed_laps=%d tracking_error_m=%.6f failure=%s mode=%s"),
        result.valid, result.lapSeconds[0], result.lapSeconds[1], result.lapSeconds[2],
        result.completedLaps, result.maximumTrackingError, UTF8_TO_TCHAR(result.failure.c_str()), mode);
    FPlatformMisc::RequestExitWithStatus(false, result.valid ? 0 : 1);
}
}

AFormulaTrialPawn::AFormulaTrialPawn() {
    PrimaryActorTick.bCanEverTick = true;
    AutoPossessPlayer = EAutoReceiveInput::Player0;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(SceneRoot);
    Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
    Body->SetupAttachment(SceneRoot);
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Driver = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Driver"));
    Driver->SetupAttachment(Body);
    Driver->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Driver->SetRelativeLocation(FVector(-12.0, 0.0, 54.0));
    for (const TCHAR* name : {TEXT("WheelFL"), TEXT("WheelFR"), TEXT("WheelRL"), TEXT("WheelRR")}) {
        UStaticMeshComponent* wheel = CreateDefaultSubobject<UStaticMeshComponent>(name);
        wheel->SetupAttachment(SceneRoot);
        wheel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Wheels.Add(wheel);
    }
    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(SceneRoot);
    Camera->SetFieldOfView(90.0f);
}

void AFormulaTrialPawn::BeginPlay() {
    Super::BeginPlay();
    FCoreDelegates::OnEnginePreExit.AddUObject(this, &AFormulaTrialPawn::DrainRenderingForExit);
    auto* session = GetGameInstance<UFFSession>();
    session->Screen = EFFScreen::Loading;
    const FString circuit = session->Circuit();
    Automatic = session->Automatic;
    const bool silverstone = circuit.IsEmpty() || circuit == TEXT("silverstone");
    const FString dataRoot = silverstone ? TEXT("Generated/Data") :
        TEXT("Generated/") + (circuit == TEXT("monza") ? FString(TEXT("Monza")) : FString(TEXT("Interlagos"))) + TEXT("/Data");
    Simulation = FFSimulation(circuit == TEXT("monza") ? TrackLayoutId::Monza :
        circuit == TEXT("interlagos") ? TrackLayoutId::Interlagos : TrackLayoutId::Silverstone);
    BestLapPath = FPaths::ProjectSavedDir() / (silverstone ? FString(TEXT("best-lap.txt")) : TEXT("best-lap-") + circuit + TEXT(".txt"));
    if (!silverstone && (FParse::Param(FCommandLine::Get(), TEXT("FFNationalPit")) ||
        FCString::Strstr(FCommandLine::Get(), TEXT("FFPitDistance=")) != nullptr ||
        FCString::Strstr(FCommandLine::Get(), TEXT("FFRacingLine=")) != nullptr)) {
        UE_LOG(LogTemp, Error, TEXT("The National pit route and recorded racing line require Silverstone."));
        FPlatformMisc::RequestExitWithStatus(false, 1);
        return;
    }
    TArray<uint8> surfaceData;
    bool surfaceLoaded = true;
    for (int part = 0; part < (silverstone ? 3 : 1); ++part) {
        const FString filename = silverstone ? FString::Printf(TEXT("drive_surface.bin.%d"), part) : TEXT("drive_surface.bin");
        TArray<uint8> bytes;
        if (!FFileHelper::LoadFileToArray(bytes, *(FPaths::ProjectContentDir() / dataRoot / filename))) {
            surfaceLoaded = false;
            break;
        }
        surfaceData.Append(bytes);
    }
    if (!surfaceLoaded ||
        !Simulation.driveSurface.Load(std::span<const uint8>(surfaceData.GetData(), surfaceData.Num()))) {
        UE_LOG(LogTemp, Error, TEXT("Missing or invalid rendered drive surface. Restore the packaged circuit content."));
        FPlatformMisc::RequestExitWithStatus(false, 1);
        return;
    }
    if (silverstone) {
        TArray<uint8> nationalSurfaceData;
        if (!FFileHelper::LoadFileToArray(nationalSurfaceData, *(FPaths::ProjectContentDir() / TEXT("Generated/Data/national_surface.bin"))) ||
            !Simulation.LoadNationalSurface(std::span<const uint8>(nationalSurfaceData.GetData(), nationalSurfaceData.Num()))) {
            UE_LOG(LogTemp, Error, TEXT("Missing or invalid National pit surface. Restore the packaged circuit data."));
            FPlatformMisc::RequestExitWithStatus(false, 1);
            return;
        }
        UE_LOG(LogTemp, Display, TEXT("Loaded %llu National pit surface triangles."),
            static_cast<unsigned long long>(Simulation.nationalSurface.Triangles().size()));
    }
    TArray<uint8> limitsData;
    if (!FFileHelper::LoadFileToArray(limitsData, *(FPaths::ProjectContentDir() / dataRoot / TEXT("track_limits.bin"))) ||
        !Simulation.trackLimits.Load(std::span<const uint8>(limitsData.GetData(), limitsData.Num()))) {
        UE_LOG(LogTemp, Error, TEXT("Missing or invalid white-line boundaries. Restore the packaged circuit content."));
        FPlatformMisc::RequestExitWithStatus(false, 1);
        return;
    }
    UE_LOG(LogTemp, Display, TEXT("Loaded %llu white-line boundary triangles."), static_cast<unsigned long long>(Simulation.trackLimits.Triangles().size()));
    if (silverstone) {
        TArray<uint8> pitData;
        TArray<uint8> pitBarriers;
        if (!FFileHelper::LoadFileToArray(pitData, *(FPaths::ProjectContentDir() / TEXT("Generated/Data/pit_lane.bin"))) ||
            !Simulation.LoadPitLane(std::span<const uint8>(pitData.GetData(), pitData.Num())) ||
            !FFileHelper::LoadFileToArray(pitBarriers, *(FPaths::ProjectContentDir() / TEXT("Generated/Data/pit_barriers.bin"))) ||
            !Simulation.LoadPitBarriers(std::span<const uint8>(pitBarriers.GetData(), pitBarriers.Num()))) {
            UE_LOG(LogTemp, Error, TEXT("Missing or invalid pit-lane data. Restore the packaged circuit data."));
            FPlatformMisc::RequestExitWithStatus(false, 1);
            return;
        }
        UE_LOG(LogTemp, Display, TEXT("Loaded %llu pit-lane sections and %llu continuous barriers."),
            static_cast<unsigned long long>(Simulation.pitLane.Sections().size()), static_cast<unsigned long long>(Simulation.Barriers().size()));
    }
    FString racingPath;
    if ((FParse::Param(FCommandLine::Get(), TEXT("FFRacingAudit")) ||
        FParse::Param(FCommandLine::Get(), TEXT("FFRacingLiveAudit"))) &&
        !FParse::Value(FCommandLine::Get(), TEXT("FFRacingLine="), racingPath)) {
        UE_LOG(LogTemp, Error, TEXT("Racing audits require FFRacingLine."));
        FPlatformMisc::RequestExitWithStatus(false, 1);
        return;
    }
    if (FParse::Value(FCommandLine::Get(), TEXT("FFRacingLine="), racingPath)) {
        if (FPaths::IsRelative(racingPath)) {
            racingPath = FPlatformMisc::GetEnvironmentVariable(TEXT("FF_REPO_ROOT")) / racingPath;
        }
        FString contents;
        if (FFileHelper::LoadFileToString(contents, *racingPath)) {
            std::istringstream input(TCHAR_TO_UTF8(*contents));
            RacingDrive = RacingLine.Load(input) && FFRacingLineMatchesTrack(RacingLine, Simulation);
        }
        if (!RacingDrive) {
            UE_LOG(LogTemp, Error, TEXT("Missing or invalid racing line: %s"), *racingPath);
            FPlatformMisc::RequestExitWithStatus(false, 1);
            return;
        }
        RacingLine.Rebuild(Simulation.tuning, 17.0f);
        Automatic = true;
        if (FParse::Param(FCommandLine::Get(), TEXT("FFRacingAudit"))) {
            FFRacingStint stint;
            stint.Reset(Simulation);
            while (stint.Step(Simulation, RacingLine, 1.0f)) {
            }
            FinishRacingStint(stint.Result(), TEXT("fast"));
            return;
        }
        RacingLiveAudit = FParse::Param(FCommandLine::Get(), TEXT("FFRacingLiveAudit"));
    }
    Body->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Generated/Car/Body.Body")));
    FullDriver = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Generated/Driver/Driver.Driver"));
    CockpitDriver = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Generated/Driver/DriverCockpit.DriverCockpit"));
    Driver->SetStaticMesh(FullDriver);
    const TCHAR* names[] = {TEXT("WheelFL"), TEXT("WheelFR"), TEXT("WheelRL"), TEXT("WheelRR")};
    FString mounts;
    FFileHelper::LoadFileToString(mounts, *(FPaths::ProjectContentDir() / TEXT("Generated/Data/wheel_mounts.csv")));
    TArray<FString> lines;
    mounts.ParseIntoArrayLines(lines);
    for (int32 index = 0; index < Wheels.Num(); ++index) {
        const FString path = FString::Printf(TEXT("/Game/Generated/Car/%s.%s"), names[index], names[index]);
        Wheels[index]->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, *path));
        if (lines.IsValidIndex(index)) {
            TArray<FString> values;
            lines[index].ParseIntoArray(values, TEXT(","));
            if (values.Num() == 3) Wheels[index]->SetRelativeLocation(FVector(FCString::Atof(*values[0]), FCString::Atof(*values[1]), FCString::Atof(*values[2])));
        }
        WheelRestMounts.Add(Wheels[index]->GetRelativeLocation());
    }
    FString supportText;
    if (FFileHelper::LoadFileToString(supportText, *(FPaths::ProjectContentDir() / TEXT("Generated/Data/body_support.csv")))) {
        TArray<FString> supports;
        supportText.ParseIntoArrayLines(supports);
        for (const FString& line : supports) {
            TArray<FString> values;
            line.ParseIntoArray(values, TEXT(","));
            if (values.Num() != 6) continue;
            BodySupports.Add(FBox(FVector(FCString::Atod(*values[0]), FCString::Atod(*values[1]), FCString::Atod(*values[2])),
                FVector(FCString::Atod(*values[3]), FCString::Atod(*values[4]), FCString::Atod(*values[5]))));
            BodySupportEnvelope += BodySupports.Last();
        }
    }
    FString saved;
    if (FFileHelper::LoadFileToString(saved, *BestLapPath)) {
        const double best = FCString::Atod(*saved);
        if (FMath::IsFinite(best) && best > 0.0) Simulation.trial.bestSeconds = best;
    }
    float station = Simulation.trial.startStation + (RacingDrive ? 0.01f : Simulation.lapLength - 20.0f);
    FParse::Value(FCommandLine::Get(), TEXT("FFStation="), station);
    Simulation.Reset(station);
    float lane = 0.0f;
    FParse::Value(FCommandLine::Get(), TEXT("FFLane="), lane);
    const auto initial = Simulation.Sample(station);
    Simulation.vehicle.pos += Vec2{-initial.tangent.y, initial.tangent.x} * lane * 17.0f;
    Simulation.vehicle.elevation = Simulation.Ground(Simulation.vehicle.pos);
    float pitDistance = 0.0f;
    if (FParse::Value(FCommandLine::Get(), TEXT("FFPitDistance="), pitDistance)) {
        float pitOffset = 0.0f;
        FParse::Value(FCommandLine::Get(), TEXT("FFPitLaneOffset="), pitOffset);
        const auto pit = Simulation.pitLane.Sample(pitDistance);
        Simulation.vehicle.pos = (pit.position + Vec2{-pit.tangent.y, pit.tangent.x} * pitOffset) * 17.0f;
        Simulation.vehicle.heading = angleOf(pit.tangent);
        Simulation.vehicle.elevation = Simulation.Ground(Simulation.vehicle.pos);
        Simulation.trial.Reset(Simulation.ProgressStation());
    }
    if (FParse::Param(FCommandLine::Get(), TEXT("FFNationalPit"))) {
        if (FCString::Strstr(FCommandLine::Get(), TEXT("FFReplay=")) != nullptr) {
            UE_LOG(LogTemp, Error, TEXT("FFNationalPit requires live simulation, not FFReplay."));
            FPlatformMisc::RequestExitWithStatus(false, 1);
            return;
        }
        FString routeText;
        if (!FFileHelper::LoadFileToString(routeText, *(FPaths::ProjectContentDir() / TEXT("Generated/Data/national_route.csv")))) {
            UE_LOG(LogTemp, Error, TEXT("FFNationalPit requires Generated/Data/national_route.csv. Restore the packaged circuit data."));
            FPlatformMisc::RequestExitWithStatus(false, 1);
            return;
        }
        TArray<FString> routeLines;
        routeText.ParseIntoArrayLines(routeLines);
        for (const FString& line : routeLines) {
            if (NationalRoute.IsEmpty() && line.TrimStartAndEnd() == TEXT("source_x,source_y")) continue;
            TArray<FString> values;
            line.ParseIntoArray(values, TEXT(","), false);
            double sourceX = 0.0;
            double sourceY = 0.0;
            if (values.Num() != 2 || !LexTryParseString(sourceX, *values[0]) || !LexTryParseString(sourceY, *values[1]) ||
                !FMath::IsFinite(sourceX) || !FMath::IsFinite(sourceY) || FMath::Abs(sourceX) > 10000.0 || FMath::Abs(sourceY) > 10000.0) {
                UE_LOG(LogTemp, Error, TEXT("Invalid FFNationalPit route row %d. Expected two finite Blender-metre coordinates."), NationalRoute.Num() + 1);
                FPlatformMisc::RequestExitWithStatus(false, 1);
                return;
            }
            const FVector2D point(sourceX * 17.0, -sourceY * 17.0);
            if (!NationalRoute.IsEmpty() && (point - NationalRoute.Last()).SizeSquared() < FMath::Square(0.001 * 17.0)) {
                UE_LOG(LogTemp, Error, TEXT("FFNationalPit route has coincident consecutive points."));
                FPlatformMisc::RequestExitWithStatus(false, 1);
                return;
            }
            NationalRoute.Add(point);
        }
        if (NationalRoute.Num() < 2) {
            UE_LOG(LogTemp, Error, TEXT("FFNationalPit requires at least two points in national_route.csv."));
            FPlatformMisc::RequestExitWithStatus(false, 1);
            return;
        }
        Simulation.vehicle.pos = {static_cast<float>(NationalRoute[0].X), static_cast<float>(NationalRoute[0].Y)};
        const FVector2D direction = NationalRoute[1] - NationalRoute[0];
        Simulation.vehicle.heading = angleOf({static_cast<float>(direction.X), static_cast<float>(direction.Y)});
        Simulation.vehicle.elevation = Simulation.Ground(Simulation.vehicle.pos);
        Simulation.trial.Reset(Simulation.ProgressStation());
        UE_LOG(LogTemp, Display, TEXT("FFNationalPit live diagnostic: %d route points, 12 m lookahead, 70 km/h bot with end braking."), NationalRoute.Num());
    }
    FParse::Value(FCommandLine::Get(), TEXT("FFCapture="), CapturePath);
    FParse::Value(FCommandLine::Get(), TEXT("FFCaptureDelay="), CaptureDelay);
    QuitAfterCapture = FParse::Param(FCommandLine::Get(), TEXT("FFQuitAfterCapture"));
    if (RacingLiveAudit) RacingStint.Reset(Simulation);
    CaptureDrive = !NationalRoute.IsEmpty() || FParse::Param(FCommandLine::Get(), TEXT("FFDrive"));
    ChaseCamera = session->ChaseCamera || FParse::Param(FCommandLine::Get(), TEXT("FFChase"));
    UpdateVisual();
    if (!CapturePath.IsEmpty()) {
        GEngine->GameViewport->OnScreenshotCaptured().AddUObject(this, &AFormulaTrialPawn::CaptureFinished);
    }
    Presentation = GetWorld()->SpawnActor<AFFPresentation>(GetActorLocation(), FRotator::ZeroRotator);
    if (FParse::Param(FCommandLine::Get(), TEXT("FFAudit"))) {
        const int32 surfacePoses = AuditVisualSupport();
        bool streaming = true;
        for (float position : {1400.0f, 2600.0f, 4500.0f}) {
            const auto sample = Simulation.Sample(position);
            streaming &= Presentation->UpdateTiles(WorldPosition(sample.position, Simulation.VisualGround(sample.position)), true);
        }
        streaming &= Presentation->UpdateTiles(GetActorLocation(), true);
        const bool passed = FFSimulation::Audit() && surfacePoses > 0 && streaming;
        const FString report = FString::Printf(TEXT("{\"passed\":%s,\"road_poses\":4419,\"rendered_surface_poses\":%d,\"visual_streaming\":%s,\"native_vehicle_core\":true}\n"), passed ? TEXT("true") : TEXT("false"), surfacePoses, streaming ? TEXT("true") : TEXT("false"));
        FFileHelper::SaveStringToFile(report, *(FPaths::ProjectSavedDir() / TEXT("simulation-audit.json")));
        FPlatformMisc::RequestExitWithStatus(false, passed ? 0 : 1);
    }
    UpdateVisual(0.0f);
    Recorder = MakeUnique<FFLapRecorder>(*this);
    if (FParse::Param(FCommandLine::Get(), TEXT("FFRecord"))) Recorder->Start();
    FString replayPath;
    if (FParse::Value(FCommandLine::Get(), TEXT("FFReplay="), replayPath)) {
        Replay = MakeUnique<FFVisualReplay>();
        if (!Replay->Load(replayPath, Simulation, ChaseCamera)) {
            UE_LOG(LogTemp, Error, TEXT("Invalid worktree visual replay file"));
            FPlatformMisc::RequestExitWithStatus(false, 1);
        } else {
            UpdateVisual(0.0f);
            if (FParse::Param(FCommandLine::Get(), TEXT("FFReplayAudit"))) {
                while (Replay->Next(Simulation, ChaseCamera)) {
                    UpdateVisual(Replay->DeltaSeconds());
                    Replay->Report(GetActorTransform(), Camera->GetComponentTransform(), VisualPenetration(true, true));
                }
                Replay.Reset();
                FPlatformMisc::RequestExit(false);
            }
        }
    }
}

AFormulaTrialPawn::~AFormulaTrialPawn() = default;

void AFormulaTrialPawn::EndPlay(const EEndPlayReason::Type reason) {
    if (Recorder) Recorder->Stop(TEXT("end_play"));
    FCoreDelegates::OnEnginePreExit.RemoveAll(this);
    if (GEngine && GEngine->GameViewport) GEngine->GameViewport->OnScreenshotCaptured().RemoveAll(this);
    Super::EndPlay(reason);
}

void AFormulaTrialPawn::ToggleRecording() {
    if (!Recorder) return;
    if (Recorder->IsRecording()) Recorder->Stop(TEXT("manual_stop"));
    else Recorder->Start();
}

FString AFormulaTrialPawn::RecordingStatus() const {
    return Recorder ? Recorder->Status() : FString();
}

int32 AFormulaTrialPawn::LoadedVisualTiles() const {
    return Presentation != nullptr ? Presentation->LoadedTiles() : 0;
}

void AFormulaTrialPawn::SetupPlayerInputComponent(UInputComponent* input) {
    Super::SetupPlayerInputComponent(input);
    input->BindKey(EKeys::F9, IE_Pressed, this, &AFormulaTrialPawn::ToggleRecording);
    input->BindKey(EKeys::R, IE_Pressed, this, &AFormulaTrialPawn::ResetTrial);
    input->BindKey(EKeys::Gamepad_FaceButton_Top, IE_Pressed, this, &AFormulaTrialPawn::ResetTrial);
    input->BindKey(EKeys::C, IE_Pressed, this, &AFormulaTrialPawn::ToggleCamera);
    input->BindKey(EKeys::Gamepad_Special_Left, IE_Pressed, this, &AFormulaTrialPawn::ToggleCamera);
    input->BindKey(EKeys::M, IE_Pressed, this, &AFormulaTrialPawn::ToggleAutomatic);
    input->BindKey(EKeys::Gamepad_FaceButton_Left, IE_Pressed, this, &AFormulaTrialPawn::ToggleAutomatic);
    input->BindKey(EKeys::E, IE_Pressed, this, &AFormulaTrialPawn::ShiftUp);
    input->BindKey(EKeys::Q, IE_Pressed, this, &AFormulaTrialPawn::ShiftDown);
    input->BindKey(EKeys::Gamepad_RightShoulder, IE_Pressed, this, &AFormulaTrialPawn::ShiftUp);
    input->BindKey(EKeys::Gamepad_LeftShoulder, IE_Pressed, this, &AFormulaTrialPawn::ShiftDown);
}

void AFormulaTrialPawn::ResetTrial() {
    auto* session = GetGameInstance<UFFSession>();
    if (session->Screen == EFFScreen::Results) {
        session->StartTrial();
        return;
    }
    session->ResetLaps();
    if (RacingLiveAudit) RacingStint.Reset(Simulation);
    else Simulation.Reset(Simulation.trial.startStation + (RacingDrive ? 0.01f : Simulation.lapLength - 20.0f));
    Accumulator = 0.0;
    PendingShifts = 0;
    UpdateVisual();
    if (Presentation != nullptr) Presentation->UpdateTiles(GetActorLocation(), true);
}

void AFormulaTrialPawn::ToggleCamera() {
    ChaseCamera = !ChaseCamera;
    GetGameInstance<UFFSession>()->ChaseCamera = ChaseCamera;
    CameraMotion.initialized = false;
}

void AFormulaTrialPawn::ToggleAutomatic() {
    Automatic = !Automatic;
    GetGameInstance<UFFSession>()->Automatic = Automatic;
}

void AFormulaTrialPawn::SetSessionPaused(bool value) {
    Paused = value;
    PendingShifts = 0;
    Accumulator = 0.0;
}

void AFormulaTrialPawn::Quit() {
    if (Recorder) Recorder->Stop(TEXT("user_exit"));
    FPlatformMisc::RequestExit(false);
}

void AFormulaTrialPawn::DrainRenderingForExit() {
    if (Recorder) Recorder->Stop(TEXT("engine_exit"));
    ENQUEUE_RENDER_COMMAND(FormulaTrialDrainBeforeExit)([](FRHICommandListImmediate& commandList) {
        commandList.SubmitAndBlockUntilGPUIdle();
    });
    FlushRenderingCommands();
}

void AFormulaTrialPawn::ShiftUp() {
    if (!Paused) PendingShifts = FMath::Clamp(PendingShifts + 1, -8, 8);
}

void AFormulaTrialPawn::ShiftDown() {
    if (!Paused) PendingShifts = FMath::Clamp(PendingShifts - 1, -8, 8);
}

void AFormulaTrialPawn::SaveBest() {
    IFileManager::Get().MakeDirectory(*FPaths::ProjectSavedDir(), true);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("%.9f\n"), Simulation.trial.bestSeconds),
        *BestLapPath);
}

void AFormulaTrialPawn::Tick(float deltaSeconds) {
    CSV_SCOPED_TIMING_STAT(FormulaForge, GameTick);
    Super::Tick(deltaSeconds);
    if (Recorder) Recorder->BeginTick(deltaSeconds);
    Elapsed += deltaSeconds;
    if (Elapsed > 5.0) { FrameSeconds += deltaSeconds; ++FrameCount; }
    APlayerController* player = Cast<APlayerController>(GetController());
    if (!SceneReady) {
        const bool nearby = Presentation && Presentation->UpdateTiles(GetActorLocation(), false);
        if (!nearby || Presentation->IsStreaming() || Elapsed < 1.0) {
            if (Recorder) Recorder->EndTick();
            return;
        }
        SceneReady = true;
        GetGameInstance<UFFSession>()->Ready();
        Accumulator = 0.0;
    }
    if (Replay) {
        if (Elapsed < 12.0) {
            if (Recorder) Recorder->EndTick();
            return;
        }
        if (!Replay->Next(Simulation, ChaseCamera, deltaSeconds)) {
            if (Recorder) Recorder->EndTick();
            Quit();
            return;
        }
        UpdateVisual(Replay->DeltaSeconds());
        Replay->Report(GetActorTransform(), Camera->GetComponentTransform(), VisualPenetration());
        if (Recorder) Recorder->EndTick();
        return;
    }
    if (!Paused && player != nullptr) {
        CSV_SCOPED_TIMING_STAT(FormulaForge, LiveSimulation);
        ArcadeVehicleControl control;
        control.steer = FMath::Clamp(ControllerSteer(player->GetInputAnalogKeyState(EKeys::Gamepad_LeftX)) +
            (player->IsInputKeyDown(EKeys::D) ? 1.0f : 0.0f) - (player->IsInputKeyDown(EKeys::A) ? 1.0f : 0.0f), -1.0f, 1.0f);
        control.throttle = FMath::Max(player->GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis), player->IsInputKeyDown(EKeys::W) ? 1.0f : 0.0f);
        control.brake = FMath::Max(player->GetInputAnalogKeyState(EKeys::Gamepad_LeftTriggerAxis),
            player->IsInputKeyDown(EKeys::S) || player->IsInputKeyDown(EKeys::SpaceBar) || player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Right) ? 1.0f : 0.0f);
        control.automaticShift = Automatic;
        if (CaptureDrive) {
            Vec2 target;
            float targetSpeed = 70.0f * 17.0f / 3.6f;
            if (!NationalRoute.IsEmpty()) {
                const FVector2D position(Simulation.vehicle.pos.x, Simulation.vehicle.pos.y);
                double nearestSquared = TNumericLimits<double>::Max();
                int32 nearestEnd = 1;
                FVector2D nearest = NationalRoute[0];
                for (int32 index = 1; index < NationalRoute.Num(); ++index) {
                    const FVector2D segment = NationalRoute[index] - NationalRoute[index - 1];
                    const double blend = FMath::Clamp(FVector2D::DotProduct(position - NationalRoute[index - 1], segment) /
                        segment.SizeSquared(), 0.0, 1.0);
                    const FVector2D projected = NationalRoute[index - 1] + segment * blend;
                    const double squared = (position - projected).SizeSquared();
                    if (squared < nearestSquared) {
                        nearestSquared = squared;
                        nearestEnd = index;
                        nearest = projected;
                    }
                }
                FVector2D routeTarget = nearest;
                double lookahead = 12.0 * 17.0;
                double remaining = 0.0;
                for (int32 index = nearestEnd; index < NationalRoute.Num(); ++index) {
                    const FVector2D start = index == nearestEnd ? nearest : NationalRoute[index - 1];
                    const FVector2D segment = NationalRoute[index] - start;
                    const double distance = segment.Size();
                    remaining += distance;
                    if (lookahead > 0.0 && distance > 0.0) {
                        routeTarget = start + segment * FMath::Min(lookahead / distance, 1.0);
                        lookahead = FMath::Max(0.0, lookahead - distance);
                    }
                }
                target = {static_cast<float>(routeTarget.X), static_cast<float>(routeTarget.Y)};
                const float remainingMetres = static_cast<float>(remaining / 17.0);
                targetSpeed = FMath::Min(targetSpeed, FMath::Sqrt(8.0f * FMath::Max(0.0f, remainingMetres - 2.0f)) * 17.0f);
                control.brake = remainingMetres <= 2.0f ? 1.0f :
                    Simulation.vehicle.forwardSpeed > targetSpeed + 0.25f * 17.0f ? 0.25f : 0.0f;
            } else {
                const auto current = Simulation.Project(Simulation.vehicle.pos);
                const auto ahead = Simulation.Sample(current.station + 35.0f);
                const auto pit = Simulation.pitLane.Project(Simulation.vehicle.pos / 17.0f);
                target = pit.inside ? Simulation.pitLane.Sample(pit.distance + 12.0f).position * 17.0f : ahead.position;
            }
            const float error = wrapAngle(angleOf(target - Simulation.vehicle.pos) - Simulation.vehicle.heading);
            control.steer = std::clamp(error * 3.0f, -1.0f, 1.0f);
            control.throttle = Simulation.vehicle.forwardSpeed < targetSpeed ? 0.5f : 0.0f;
            control.automaticShift = true;
        }
        Accumulator += deltaSeconds;
        constexpr double fixedStep = 1.0 / 120.0;
        int32 steps = 0;
        const double previousBest = Simulation.trial.bestSeconds;
        while (Accumulator >= fixedStep && steps < 120) {
            if (RacingDrive) {
                control = RacingLine.Control(Simulation.vehicle, Simulation.tuning,
                    Simulation.Project(Simulation.vehicle.pos).station, 17.0f);
            }
            control.shiftUpPressed = PendingShifts > 0;
            control.shiftDownPressed = PendingShifts < 0;
            if (PendingShifts != 0) PendingShifts += PendingShifts > 0 ? -1 : 1;
            Simulation.Step(control, fixedStep);
            if (Recorder) Recorder->Step(control, fixedStep);
            if (RacingLiveAudit && !RacingStint.Observe(Simulation, RacingLine, control, 1.0f)) {
                RacingLiveAudit = false;
                FinishRacingStint(RacingStint.Result(), TEXT("live"));
            }
            Accumulator -= fixedStep;
            ++steps;
            auto* session = GetGameInstance<UFFSession>();
            session->ObserveLap(Simulation.trial.completedLaps, Simulation.trial.lastSeconds, Simulation.trial.lastValid);
            if (session->Screen == EFFScreen::Results) {
                Accumulator = 0.0;
                break;
            }
        }
        if (Accumulator >= fixedStep) {
            Accumulator = 0.0;
            if (Simulation.trial.running) Simulation.trial.invalid = true;
        }
        if (!RacingDrive && Simulation.trial.bestSeconds != previousBest) SaveBest();
    }
    UpdateVisual(deltaSeconds);
    if (Recorder) Recorder->EndTick();
    if (!CapturePath.IsEmpty() && !Capturing && Elapsed >= CaptureDelay) {
        Capturing = true;
        FScreenshotRequest::RequestScreenshot(CapturePath, false, false);
    }
    if (Captured && QuitAfterCapture) Quit();
}

void AFormulaTrialPawn::UpdateVisual(float deltaSeconds) {
    CSV_SCOPED_TIMING_STAT(FormulaForge, VisualSupport);
    const auto& vehicle = Simulation.vehicle;
    const Vec2 forward = fromAngle(vehicle.heading);
    const Vec2 right{-forward.y, forward.x};
    TArray<float> contacts;
    for (const auto& mount : WheelRestMounts) {
        contacts.Add(Simulation.VisualGround(vehicle.pos +
            (forward * static_cast<float>(mount.X / 100.0) + right * static_cast<float>(mount.Y / 100.0)) * 17.0f));
    }
    const float front = (contacts[0] + contacts[1]) * 0.5f;
    const float rear = (contacts[2] + contacts[3]) * 0.5f;
    const float left = (contacts[0] + contacts[2]) * 0.5f;
    const float rightHeight = (contacts[1] + contacts[3]) * 0.5f;
    const float forwardSlope = (front - rear) / (3.17f * 17.0f);
    const float rightSlope = (left - rightHeight) / (1.59f * 17.0f);
    const float pitch = FMath::RadiansToDegrees(FMath::Atan(forwardSlope));
    const float roll = -FMath::RadiansToDegrees(FMath::Atan(rightSlope));
    float elevation = (front + rear) * 0.5f - forwardSlope * 0.015f * 17.0f;
    if (!vehicle.grounded) elevation += vehicle.elevation - Simulation.Ground(vehicle.pos);
    SetActorLocationAndRotation(WorldPosition(vehicle.pos, elevation + 0.002f * 17.0f),
        FRotator(pitch, FMath::RadiansToDegrees(vehicle.heading) - 90.0f, roll));
    const float bodyPitch = FMath::Clamp(FMath::RadiansToDegrees(vehicle.bodyPitch) * 0.10f, -1.0f, 1.0f);
    const float bodyRoll = FMath::Clamp(FMath::RadiansToDegrees(vehicle.bodyRoll) * 0.20f, -1.0f, 1.0f);
    Body->SetRelativeRotation(FRotator(bodyPitch, 0.0, bodyRoll));
    Driver->SetStaticMesh(ChaseCamera || CockpitDriver == nullptr ? FullDriver : CockpitDriver);
    for (int32 index = 0; index < Wheels.Num(); ++index) {
        const FVector rest = WheelRestMounts[index];
        const float plane = elevation + (forwardSlope * rest.X + rightSlope * rest.Y) * 17.0f / 100.0f;
        const double travel = vehicle.grounded ? (contacts[index] - plane) * 100.0 / 17.0 : 0.0;
        Wheels[index]->SetRelativeLocation(rest + FVector(0.0, 0.0, travel));
        Wheels[index]->SetRelativeRotation(FRotator(-FMath::RadiansToDegrees(vehicle.wheelSpin),
            index < 2 ? FMath::RadiansToDegrees(vehicle.steerAngle) : 0.0f, 0.0));
    }
    const float penetration = VisualPenetration(false);
    if (penetration > 0.0f) {
        const double lift = (penetration + 0.002f) * 100.0;
        AddActorWorldOffset(FVector(0.0, 0.0, lift));
        if (vehicle.grounded) {
            for (auto& wheel : Wheels) wheel->AddWorldOffset(FVector(0.0, 0.0, -lift));
        }
    }
    for (int32 index = 0; index < Wheels.Num(); ++index) {
        const float wheelPenetration = WheelPenetration(index);
        if (wheelPenetration > 0.0f) Wheels[index]->AddWorldOffset(FVector(0.0, 0.0, (wheelPenetration + 0.002f) * 100.0));
    }
    RenderedPenetration = VisualPenetration();
    const auto projection = Simulation.Project(vehicle.pos);
    const float roadPitch = FMath::RadiansToDegrees(FMath::Atan(projection.grade));
    const float roadRoll = -FMath::RadiansToDegrees(FMath::Atan(projection.bankSlope));
    CameraMotion.Update(GetActorLocation().Z,
        roadPitch + (pitch - roadPitch) * 0.15f,
        roadRoll + (roll - roadRoll) * 0.08f, deltaSeconds);
    const double yaw = FMath::RadiansToDegrees(vehicle.heading) - 90.0;
    // Keep the eye inside the cockpit on grades; world-height lag sinks it into the body.
    FVector cameraPosition = GetActorTransform().TransformPosition(FVector(-52.0, 0.0, 126.0));
    if (ChaseCamera) {
        cameraPosition = GetActorLocation() + FRotator(0.0, yaw, 0.0).RotateVector(FVector(-750.0, 0.0, 280.0));
        cameraPosition.Z = CameraMotion.elevation.position + 280.0;
    }
    Camera->SetWorldLocationAndRotation(cameraPosition,
        FRotator(CameraMotion.pitch.position + (ChaseCamera ? -10.0 : -3.5), yaw, CameraMotion.roll.position));
    Camera->SetFieldOfView(ChaseCamera ? 80.0f : 90.0f);
}

float AFormulaTrialPawn::ComponentPenetration(const FTransform& transform, const FVector& minimum, const FVector& maximum) const {
    std::array<FFSurfacePoint, 4> footprint{};
    const std::array<FVector, 4> corners{FVector(minimum.X, minimum.Y, minimum.Z), FVector(maximum.X, minimum.Y, minimum.Z),
        FVector(maximum.X, maximum.Y, minimum.Z), FVector(minimum.X, maximum.Y, minimum.Z)};
    for (int32 index = 0; index < 4; ++index) {
        const FVector point = transform.TransformPosition(corners[index]);
        footprint[index] = {static_cast<float>(-point.Y / 100.0), static_cast<float>(-point.X / 100.0), static_cast<float>(point.Z / 100.0)};
    }
    return Simulation.driveSurface.Penetration(footprint);
}

float AFormulaTrialPawn::WheelPenetration(int32 index) const {
    if (Wheels[index]->GetStaticMesh() == nullptr) return 0.0f;
    const FBox bounds = Wheels[index]->GetStaticMesh()->GetBoundingBox();
    const FTransform mount(FRotator(0.0, index < 2 ? FMath::RadiansToDegrees(Simulation.vehicle.steerAngle) : 0.0f, 0.0), Wheels[index]->GetRelativeLocation());
    return ComponentPenetration(mount * SceneRoot->GetComponentTransform(),
        FVector(-10.0, bounds.Min.Y, bounds.Min.Z), FVector(10.0, bounds.Max.Y, bounds.Min.Z));
}

float AFormulaTrialPawn::VisualPenetration(bool includeWheels, bool forceDetailedBody) const {
    float penetration = 0.0f;
    if (Body->GetStaticMesh() != nullptr) {
        if (BodySupports.IsEmpty()) {
            const FBox bounds = Body->GetStaticMesh()->GetBoundingBox();
            penetration = ComponentPenetration(Body->GetComponentTransform(), bounds.Min, bounds.Max);
        } else {
            const auto transform = Body->GetComponentTransform();
            const FVector scale = transform.GetScale3D();
            const auto margins = FFBodyFloorExpansion(BodySupportEnvelope.Max.Z - BodySupportEnvelope.Min.Z,
                {transform.GetUnitAxis(EAxis::X).Z, transform.GetUnitAxis(EAxis::Y).Z, transform.GetUnitAxis(EAxis::Z).Z},
                {scale.X, scale.Y, scale.Z});
            const bool needsDetailedCheck = forceDetailedBody || !margins.valid || ComponentPenetration(transform,
                BodySupportEnvelope.Min - FVector(margins.longitudinal, margins.lateral, 0.0),
                BodySupportEnvelope.Max + FVector(margins.longitudinal, margins.lateral, 0.0)) > 0.0f;
            if (needsDetailedCheck) {
                for (const auto& bounds : BodySupports) penetration = FMath::Max(penetration,
                    ComponentPenetration(transform, bounds.Min, bounds.Max));
            }
        }
    }
    if (!includeWheels) return penetration;
    for (int32 index = 0; index < Wheels.Num(); ++index) {
        penetration = FMath::Max(penetration, WheelPenetration(index));
    }
    return penetration;
}

int32 AFormulaTrialPawn::AuditVisualSupport() {
    if (Body->GetStaticMesh() == nullptr) return -1;
    for (const auto& wheel : Wheels) if (wheel->GetStaticMesh() == nullptr) return -1;
    int32 poses = 0;
    int32 candidates = 0;
    for (const auto& triangle : Simulation.driveSurface.Triangles()) {
        const auto& points = triangle.points;
        const float centreX = (points[0].positionX + points[1].positionX + points[2].positionX) / 3.0f;
        const float centreY = (points[0].positionY + points[1].positionY + points[2].positionY) / 3.0f;
        const float centreZ = (points[0].positionZ + points[1].positionZ + points[2].positionZ) / 3.0f;
        const Vec2 centre{centreX * 17.0f, -centreY * 17.0f};
        if (centreZ - Simulation.Ground(centre) / 17.0f < 0.03f || ++candidates % 8 != 0) continue;
        const float heading = angleOf(Simulation.Project(centre).tangent);
        for (float angle : {0.0f, 0.4f, -0.4f}) {
            for (const Vec2 offset : {Vec2{0.0f, 0.0f}, Vec2{1.60f, -0.815f}, Vec2{-1.57f, 0.775f}}) {
                Simulation.vehicle.heading = heading + angle;
                const Vec2 forward = fromAngle(Simulation.vehicle.heading);
                const Vec2 right{-forward.y, forward.x};
                Simulation.vehicle.pos = centre - (forward * offset.x + right * offset.y) * 17.0f;
                Simulation.vehicle.elevation = Simulation.Ground(Simulation.vehicle.pos);
                Simulation.vehicle.grounded = true;
                Simulation.vehicle.bodyPitch = angle * 0.1f;
                Simulation.vehicle.bodyRoll = angle * 0.1f;
                Simulation.vehicle.steerAngle = angle;
                Simulation.vehicle.wheelSpin = angle * 17.0f;
                UpdateVisual();
                if (VisualPenetration() > 0.001f) {
                    UE_LOG(LogTemp, Error, TEXT("Rendered surface penetration at %.3f, %.3f, heading %.4f, body %.6f, wheels %.6f %.6f %.6f %.6f"),
                        centreX, centreY, Simulation.vehicle.heading, VisualPenetration(false),
                        WheelPenetration(0), WheelPenetration(1), WheelPenetration(2), WheelPenetration(3));
                    return -1;
                }
                ++poses;
                const double supportedHeight = GetActorLocation().Z;
                Simulation.vehicle.elevation += 2.0f * 17.0f;
                UpdateVisual();
                if (FMath::Abs(GetActorLocation().Z - supportedHeight) > 0.1) return -1;
                Simulation.vehicle.elevation -= 2.0f * 17.0f;
                Simulation.vehicle.grounded = false;
                Simulation.vehicle.elevation += 0.04f * 17.0f;
                UpdateVisual();
                if (VisualPenetration() > 0.001f) return -1;
                ++poses;
            }
        }
    }
    Simulation.Reset();
    UpdateVisual();
    return poses;
}

void AFormulaTrialPawn::CaptureFinished(int32 width, int32 height, const TArray<FColor>& pixels) {
    TArray64<uint8> png;
    FImageUtils::PNGCompressImageArray(width, height, pixels, png);
    FFileHelper::SaveArrayToFile(png, *CapturePath);
    const double fps = FrameSeconds > 0.0 ? FrameCount / FrameSeconds : 0.0;
    const FString report = FString::Printf(TEXT("{\"width\":%d,\"height\":%d,\"average_fps\":%.3f,\"station_m\":%.3f,\"lane_m\":%.3f,\"visual_penetration_m\":%.6f,\"speed_kph\":%.3f,\"loaded_visual_tiles\":%d,\"barrier_contact\":%s}\n"),
        width, height, fps, Simulation.Project(Simulation.vehicle.pos).station,
        Simulation.Project(Simulation.vehicle.pos).lane / 17.0f, VisualPenetration(),
        Simulation.vehicle.forwardSpeed / 17.0f * 3.6f, Presentation != nullptr ? Presentation->LoadedTiles() : 0, Simulation.barrierContact ? TEXT("true") : TEXT("false"));
    FFileHelper::SaveStringToFile(report, *(CapturePath + TEXT(".json")));
    Captured = true;
}

AFormulaTrialGameMode::AFormulaTrialGameMode() {
    PlayerControllerClass = AFormulaFlowController::StaticClass();
    DefaultPawnClass = AFormulaTrialPawn::StaticClass();
    HUDClass = AFormulaTrialHUD::StaticClass();
}
