#include "FFSession.h"
#include "FFGame.h"
#include "Camera/CameraActor.h"
#include "EngineUtils.h"
#include "Framework/Application/SlateApplication.h"
#include "Components/InputComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "MoviePlayer.h"
#include "TimerManager.h"
#include "UObject/UObjectGlobals.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/CoreStyle.h"

namespace {
constexpr int32 LapLimits[] = {0, 1, 3, 5, 10};
const TCHAR* Circuits[] = {TEXT("silverstone"), TEXT("monza"), TEXT("interlagos")};
const TCHAR* Titles[] = {TEXT("Silverstone"), TEXT("Monza"), TEXT("Interlagos")};
const TCHAR* Maps[] = {TEXT("/Game/Generated/SilverstonePresentation"), TEXT("/Game/Generated/Monza/Review"), TEXT("/Game/Generated/Interlagos/Review")};
}

void UFFSession::Init() {
    Super::Init();
    FCoreUObjectDelegates::PreLoadMap.AddUObject(this, &UFFSession::LoadingScreen);
#if !UE_BUILD_SHIPPING
    if (FParse::Param(FCommandLine::Get(), TEXT("FFFlowAudit")) || FParse::Param(FCommandLine::Get(), TEXT("FFMenuReview"))) Audit = MakeUnique<FFSessionAudit>(*this);
#endif
    FString circuit;
    if (FParse::Value(FCommandLine::Get(), TEXT("FFCircuit="), circuit)) {
        for (int32 index = 0; index < 3; ++index) if (circuit.Equals(Circuits[index], ESearchCase::IgnoreCase)) CircuitIndex = index;
    }
}

void UFFSession::Shutdown() {
    Audit.Reset();
    FCoreUObjectDelegates::PreLoadMap.RemoveAll(this);
    Super::Shutdown();
}

FString UFFSession::Circuit() const {
    return Circuits[CircuitIndex];
}
FString UFFSession::CircuitTitle() const {
    return Titles[CircuitIndex];
}
int32 UFFSession::LapLimit() const {
    return LapLimits[LapIndex];
}
FString UFFSession::LapLabel() const {
    return LapLimit() == 0 ? TEXT("UNLIMITED") : FString::Printf(TEXT("%d TIMED %s"), LapLimit(), LapLimit() == 1 ? TEXT("LAP") : TEXT("LAPS"));
}

void UFFSession::LoadingScreen(const FString& map) {
    if (IsRunningDedicatedServer() || !IsMoviePlayerEnabled()) return;
    FLoadingScreenAttributes loading;
    loading.bAutoCompleteWhenLoadingCompletes = true;
    loading.MinimumLoadingScreenDisplayTime = 0.5f;
    loading.WidgetLoadingScreen = SNew(SBorder)
        .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(FLinearColor(.008f, .012f, .020f))
        .HAlign(HAlign_Center).VAlign(VAlign_Center)
        [SNew(STextBlock).Text(FText::FromString(map.Contains(TEXT("Frontend")) ? TEXT("FORMULA FORGE") : TEXT("LOADING ") + CircuitTitle().ToUpper()))
            .Font(FCoreStyle::GetDefaultFontStyle("Bold", 32))
            .ColorAndOpacity(FLinearColor(.92f, .96f, 1.0f))];
    GetMoviePlayer()->SetupLoadingScreen(loading);
}

void UFFSession::Travel(const FString& map, const FString& gameMode) {
    FTimerHandle timer;
    GetWorld()->GetTimerManager().SetTimer(timer, FTimerDelegate::CreateWeakLambda(this, [this, map, gameMode]() {
        UGameplayStatics::OpenLevel(this, FName(*map), true, TEXT("game=") + gameMode);
    }), .15f, false);
}

void UFFSession::StartTrial() {
    if (Screen == EFFScreen::Loading) return;
    ResetLaps();
    Screen = EFFScreen::Loading;
    UE_LOG(LogTemp, Display, TEXT("FF_FLOW loading circuit=%s laps=%d"), *Circuit(), LapLimit());
    Travel(Maps[CircuitIndex], TEXT("/Script/FormulaForge.FormulaTrialGameMode"));
}

void UFFSession::ReturnToMenu() {
    if (Screen == EFFScreen::Loading) return;
    Screen = EFFScreen::Loading;
    Travel(TEXT("/Game/Frontend"), TEXT("/Script/FormulaForge.FormulaMenuGameMode"));
}

void UFFSession::Ready() {
    Screen = EFFScreen::Driving;
    UE_LOG(LogTemp, Display, TEXT("FF_FLOW driving circuit=%s laps=%d"), *Circuit(), LapLimit());
}

void UFFSession::Pause() {
    if (Screen != EFFScreen::Driving) return;
    Screen = EFFScreen::Paused;
    Focus = 0;
    if (auto* player = GetFirstLocalPlayerController()) {
        if (auto* pawn = Cast<AFormulaTrialPawn>(player->GetPawn())) pawn->SetSessionPaused(true);
    }
}

void UFFSession::Resume() {
    if (Screen != EFFScreen::Paused) return;
    Screen = EFFScreen::Driving;
    if (auto* player = GetFirstLocalPlayerController()) {
        if (auto* pawn = Cast<AFormulaTrialPawn>(player->GetPawn())) pawn->SetSessionPaused(false);
    }
}

void UFFSession::ResetLaps() {
    Laps.Reset();
}

void UFFSession::ObserveLap(int32 completedLaps, double seconds, bool valid) {
    if (completedLaps <= Laps.Num()) return;
    Laps.Add({seconds, valid});
    if (LapLimit() > 0 && Laps.Num() >= LapLimit()) {
        Screen = EFFScreen::Results;
        Focus = 0;
        if (auto* player = GetFirstLocalPlayerController()) {
            if (auto* pawn = Cast<AFormulaTrialPawn>(player->GetPawn())) pawn->SetSessionPaused(true);
        }
        UE_LOG(LogTemp, Display, TEXT("FF_FLOW results circuit=%s laps=%d"), *Circuit(), Laps.Num());
    }
}

int32 UFFSession::ActionCount() const {
    if (Screen == EFFScreen::Setup) return 7;
    if (Screen == EFFScreen::Paused) return 4;
    if (Screen == EFFScreen::Results) return 3;
    return 0;
}

void UFFSession::Activate(int32 action) {
    if (action < 0 || action >= ActionCount()) return;
    Focus = action;
    if (Screen == EFFScreen::Setup) {
        if (action < 3) CircuitIndex = action;
        else if (action == 3) LapIndex = (LapIndex + 4) % 5;
        else if (action == 4) LapIndex = (LapIndex + 1) % 5;
        else if (action == 5) StartTrial();
        else FPlatformMisc::RequestExit(false);
    } else if (Screen == EFFScreen::Paused) {
        if (action == 0) Resume();
        else if (action == 1) StartTrial();
        else if (action == 2) ReturnToMenu();
        else FPlatformMisc::RequestExit(false);
    } else if (Screen == EFFScreen::Results) {
        if (action == 0) StartTrial();
        else if (action == 1) ReturnToMenu();
        else FPlatformMisc::RequestExit(false);
    }
}

void AFormulaFlowController::SetupInputComponent() {
    Super::SetupInputComponent();
    bEnableClickEvents = true;
    for (const FKey& key : {EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_LeftStick_Left}) InputComponent->BindKey(key, IE_Pressed, this, &AFormulaFlowController::Left).bConsumeInput = false;
    for (const FKey& key : {EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right, EKeys::Gamepad_LeftStick_Right}) InputComponent->BindKey(key, IE_Pressed, this, &AFormulaFlowController::Right).bConsumeInput = false;
    for (const FKey& key : {EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up, EKeys::Gamepad_LeftStick_Up}) InputComponent->BindKey(key, IE_Pressed, this, &AFormulaFlowController::Up).bConsumeInput = false;
    for (const FKey& key : {EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down, EKeys::Gamepad_LeftStick_Down}) InputComponent->BindKey(key, IE_Pressed, this, &AFormulaFlowController::Down).bConsumeInput = false;
    for (const FKey& key : {EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom}) InputComponent->BindKey(key, IE_Pressed, this, &AFormulaFlowController::Confirm).bConsumeInput = false;
    InputComponent->BindKey(EKeys::Escape, IE_Pressed, this, &AFormulaFlowController::Back);
    InputComponent->BindKey(EKeys::Gamepad_FaceButton_Right, IE_Pressed, this, &AFormulaFlowController::Cancel).bConsumeInput = false;
    InputComponent->BindKey(EKeys::P, IE_Pressed, this, &AFormulaFlowController::TogglePause);
    InputComponent->BindKey(EKeys::Gamepad_Special_Right, IE_Pressed, this, &AFormulaFlowController::TogglePause);
}

void AFormulaFlowController::PlayerTick(float deltaTime) {
    Super::PlayerTick(deltaTime);
    auto* session = GetGameInstance<UFFSession>();
    const bool menu = session->Screen != EFFScreen::Driving;
    if (bShowMouseCursor != menu) {
        bShowMouseCursor = menu;
        FInputModeGameOnly mode;
        mode.SetConsumeCaptureMouseDown(false);
        SetInputMode(mode);
        FSlateApplication::Get().SetAllUserFocusToGameViewport();
    }
}

void AFormulaFlowController::MoveFocus(int32 direction) {
    auto* session = GetGameInstance<UFFSession>();
    const int32 count = session->ActionCount();
    if (count) session->Focus = (session->Focus + count + direction) % count;
}

void AFormulaFlowController::Left() {
    auto* session = GetGameInstance<UFFSession>();
    if (session->Screen == EFFScreen::Setup) session->Activate((session->CircuitIndex + 2) % 3);
    else MoveFocus(-1);
}

void AFormulaFlowController::Right() {
    auto* session = GetGameInstance<UFFSession>();
    if (session->Screen == EFFScreen::Setup) session->Activate((session->CircuitIndex + 1) % 3);
    else MoveFocus(1);
}

void AFormulaFlowController::Up() {
    auto* session = GetGameInstance<UFFSession>();
    if (session->Screen == EFFScreen::Setup) session->Activate(3);
    else MoveFocus(-1);
}

void AFormulaFlowController::Down() {
    auto* session = GetGameInstance<UFFSession>();
    if (session->Screen == EFFScreen::Setup) session->Activate(4);
    else MoveFocus(1);
}

void AFormulaFlowController::Confirm() {
    auto* session = GetGameInstance<UFFSession>();
    session->Activate(session->Screen == EFFScreen::Setup ? 5 : session->Focus);
}

void AFormulaFlowController::Back() {
    auto* session = GetGameInstance<UFFSession>();
    if (session->Screen == EFFScreen::Driving) {
        session->Pause();
    } else if (session->Screen == EFFScreen::Paused) session->Resume();
    else if (session->Screen == EFFScreen::Results) session->ReturnToMenu();
    else if (session->Screen == EFFScreen::Setup) FPlatformMisc::RequestExit(false);
}

void AFormulaFlowController::TogglePause() {
    auto* session = GetGameInstance<UFFSession>();
    if (session->Screen == EFFScreen::Paused) session->Resume();
    else session->Pause();
}

AFormulaMenuGameMode::AFormulaMenuGameMode() {
    DefaultPawnClass = nullptr;
    PlayerControllerClass = AFormulaFlowController::StaticClass();
    HUDClass = AFormulaTrialHUD::StaticClass();
}

void AFormulaFlowController::Cancel() {
    if (GetGameInstance<UFFSession>()->Screen != EFFScreen::Driving) Back();
}

void AFormulaMenuGameMode::StartPlay() {
    auto* session = GetGameInstance<UFFSession>();
    session->Screen = EFFScreen::Setup;
    session->Focus = 5;
    Super::StartPlay();
    TActorIterator<ACameraActor> camera(GetWorld());
    if (camera) session->GetFirstLocalPlayerController()->SetViewTarget(*camera);
    UE_LOG(LogTemp, Display, TEXT("FF_FLOW setup"));
}
