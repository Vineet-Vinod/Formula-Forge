#include "FFCircuitReview.h"
#include "FFPresentation.h"

#include "Camera/CameraComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "HighResScreenshot.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

AFFCircuitReviewPawn::AFFCircuitReviewPawn() {
    UCameraComponent* camera = CreateDefaultSubobject<UCameraComponent>(TEXT("ReviewCamera"));
    SetRootComponent(camera);
    camera->SetFieldOfView(90.0f);
    PrimaryActorTick.bCanEverTick = true;
}

void AFFCircuitReviewPawn::BeginPlay() {
    Super::BeginPlay();
    FVector position = FVector::ZeroVector;
    FRotator rotation = FRotator::ZeroRotator;
    FParse::Value(FCommandLine::Get(), TEXT("FFViewX="), position.X);
    FParse::Value(FCommandLine::Get(), TEXT("FFViewY="), position.Y);
    FParse::Value(FCommandLine::Get(), TEXT("FFViewZ="), position.Z);
    FParse::Value(FCommandLine::Get(), TEXT("FFViewPitch="), rotation.Pitch);
    FParse::Value(FCommandLine::Get(), TEXT("FFViewYaw="), rotation.Yaw);
    float fieldOfView = 90.0f;
    FParse::Value(FCommandLine::Get(), TEXT("FFViewFOV="), fieldOfView);
    CastChecked<UCameraComponent>(GetRootComponent())->SetFieldOfView(FMath::Clamp(fieldOfView, 30.0f, 120.0f));
    FParse::Value(FCommandLine::Get(), TEXT("FFCapture="), CapturePath);
    FParse::Value(FCommandLine::Get(), TEXT("FFCaptureDelay="), CaptureDelay);
    FScreenshotRequest::OnScreenshotRequestProcessed().AddWeakLambda(this, [this]() { Completed = true; });
    SetActorLocationAndRotation(position, rotation);
    Presentation = GetWorld()->SpawnActor<AFFPresentation>(position, FRotator::ZeroRotator);
    GetWorld()->GetFirstPlayerController()->SetViewTarget(this);
    if (!CapturePath.IsEmpty()) {
        CapturePath = FPaths::ConvertRelativePathToFull(CapturePath);
        IFileManager::Get().MakeDirectory(*FPaths::GetPath(CapturePath), true);
    }
    UE_LOG(LogTemp, Display, TEXT("Circuit visual review at %s rotation %s"), *position.ToString(), *rotation.ToString());
}

void AFFCircuitReviewPawn::Tick(float DeltaSeconds) {
    Super::Tick(DeltaSeconds);
    Elapsed += DeltaSeconds;
    Presentation->UpdateTiles(GetActorLocation(), false);
    if (!CapturePath.IsEmpty() && !Requested && Elapsed >= CaptureDelay &&
        Presentation->LoadedTiles() > 0 && !Presentation->IsStreaming()) {
        FScreenshotRequest::RequestScreenshot(CapturePath, false, false);
        Requested = true;
    }
    if (Completed && IFileManager::Get().FileExists(*CapturePath)) {
        UE_LOG(LogTemp, Display, TEXT("Circuit visual review saved: %s; %d tiles loaded"), *CapturePath, Presentation->LoadedTiles());
        FPlatformMisc::RequestExit(false);
    }
    if (Elapsed > CaptureDelay + 90.0f) {
        UE_LOG(LogTemp, Error, TEXT("Circuit review did not finish streaming or saving its screenshot"));
        FPlatformMisc::RequestExitWithStatus(false, 1);
    }
}

AFFCircuitReviewGameMode::AFFCircuitReviewGameMode() {
    DefaultPawnClass = AFFCircuitReviewPawn::StaticClass();
    HUDClass = nullptr;
}
