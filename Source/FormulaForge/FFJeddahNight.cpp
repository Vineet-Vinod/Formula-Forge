#include "FFJeddahNight.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextureCube.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

AFFJeddahNight::AFFJeddahNight() {
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = 0.2f;
}

void AFFJeddahNight::BeginPlay() {
    Super::BeginPlay();
    UWorld* world = GetWorld();
    ADirectionalLight* fill = world->SpawnActor<ADirectionalLight>(FVector::ZeroVector, FRotator(-70, 126, 0));
    UDirectionalLightComponent* light = CastChecked<UDirectionalLightComponent>(fill->GetLightComponent());
    light->SetMobility(EComponentMobility::Movable);
    light->SetIntensity(0.45f);
    light->SetLightColor(FLinearColor(0.80f, 0.88f, 1.0f));
    light->SetCastShadows(false);
    ASkyLight* sky = world->SpawnActor<ASkyLight>();
    USkyLightComponent* ambient = sky->GetLightComponent();
    ambient->SetMobility(EComponentMobility::Movable);
    ambient->SourceType = SLS_SpecifiedCubemap;
    ambient->SetCubemap(LoadObject<UTextureCube>(nullptr, TEXT("/Game/Generated/Environment/Daylight.Daylight")));
    ambient->SetRealTimeCapture(false);
    ambient->SetIntensity(0.55f);
    ambient->SetLightColor(FLinearColor(0.58f, 0.72f, 1.0f));
    ambient->SetLowerHemisphereColor(FLinearColor(0.025f, 0.035f, 0.05f));
    AStaticMeshActor* dome = world->SpawnActor<AStaticMeshActor>();
    UStaticMeshComponent* sphere = dome->GetStaticMeshComponent();
    sphere->SetMobility(EComponentMobility::Movable);
    sphere->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    sphere->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Generated/Jeddah/Materials/JeddahNightSky.JeddahNightSky")));
    sphere->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    sphere->SetCastShadow(false);
    dome->SetActorScale3D(FVector(12000));
    AExponentialHeightFog* fog = world->SpawnActor<AExponentialHeightFog>();
    fog->GetComponent()->SetFogDensity(0.00035f);
    fog->GetComponent()->SetFogHeightFalloff(0.2f);
    fog->GetComponent()->SetFogInscatteringColor(FLinearColor(0.035f, 0.055f, 0.085f));
    fog->GetComponent()->SetStartDistance(45000);
    APostProcessVolume* post = world->SpawnActor<APostProcessVolume>();
    post->bUnbound = true;
    FPostProcessSettings& settings = post->Settings;
    settings.bOverride_AutoExposureMethod = true;
    settings.AutoExposureMethod = AEM_Manual;
    settings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
    settings.AutoExposureApplyPhysicalCameraExposure = false;
    settings.bOverride_BloomIntensity = true;
    settings.BloomIntensity = 0.35f;
    settings.bOverride_LensFlareIntensity = true;
    settings.LensFlareIntensity = 0;
    settings.bOverride_VignetteIntensity = true;
    settings.VignetteIntensity = 0.06f;
    settings.bOverride_AmbientOcclusionIntensity = true;
    settings.AmbientOcclusionIntensity = 0;
    settings.bOverride_ScreenSpaceReflectionIntensity = true;
    settings.ScreenSpaceReflectionIntensity = 0;
    FParse::Value(FCommandLine::Get(), TEXT("FFJeddahLightScale="), LightScale);
    LightScale = FMath::IsFinite(LightScale) ? FMath::Clamp(LightScale, 0.0f, 8.0f) : 1.0f;
    LoadFixtures();
    for (int32 index = 0; index < FMath::Min(10, Fixtures.Num()); ++index) {
        USpotLightComponent* spot = NewObject<USpotLightComponent>(this);
        spot->SetupAttachment(GetRootComponent());
        spot->SetMobility(EComponentMobility::Movable);
        spot->bUseInverseSquaredFalloff = false;
        spot->LightFalloffExponent = 2.0f;
        spot->SetAttenuationRadius(5800);
        spot->SetInnerConeAngle(35);
        spot->SetOuterConeAngle(72);
        spot->SetLightColor(FLinearColor(0.94f, 0.97f, 1.0f));
        spot->SetIntensity(0);
        spot->SetSourceRadius(45);
        spot->SetSoftSourceRadius(65);
        spot->SetCastShadows(index == 0);
        spot->ShadowResolutionScale = 0.5f;
        spot->ShadowBias = 0.4f;
        spot->RegisterComponent();
        Lights.Add(spot);
    }
    UpdateLights();
}

void AFFJeddahNight::LoadFixtures() {
    TArray<FString> rows;
    const FString path = FPaths::ProjectContentDir() / TEXT("Generated/Jeddah/Data/night_lights.csv");
    if (!FFileHelper::LoadFileToStringArray(rows, *path)) {
        UE_LOG(LogTemp, Error, TEXT("Missing Jeddah floodlight registration: %s"), *path);
        return;
    }
    for (int32 index = 1; index < rows.Num(); ++index) {
        TArray<FString> fields;
        rows[index].ParseIntoArray(fields, TEXT(","), false);
        if (fields.Num() != 7) continue;
        double values[7]{};
        bool valid = true;
        for (int32 field = 0; field < 7; ++field) {
            valid &= LexTryParseString(values[field], *fields[field]);
            valid &= FMath::IsFinite(values[field]) && FMath::Abs(values[field]) < 10000000;
        }
        if (valid && values[6] > 0 && values[6] <= 4) {
            Fixtures.Add({FVector(values[0], values[1], values[2]),
                FVector(values[3], values[4], values[5]), static_cast<float>(values[6])});
        }
    }
    UE_LOG(LogTemp, Display, TEXT("Jeddah floodlights: %d registered fixtures, ten local lights."), Fixtures.Num());
}

void AFFJeddahNight::Tick(float deltaSeconds) {
    Super::Tick(deltaSeconds);
    UpdateLights();
}

void AFFJeddahNight::UpdateLights() {
    APlayerController* player = GetWorld()->GetFirstPlayerController();
    if (player == nullptr || player->GetPawn() == nullptr) return;
    const FVector position = player->GetPawn()->GetActorLocation();
    TArray<int32> ordered;
    ordered.Reserve(Fixtures.Num());
    for (int32 index = 0; index < Fixtures.Num(); ++index) ordered.Add(index);
    ordered.Sort([&](int32 first, int32 last) {
        return FVector::DistSquared2D(position, Fixtures[first].targetCm) <
            FVector::DistSquared2D(position, Fixtures[last].targetCm);
    });
    for (int32 index = 0; index < Lights.Num(); ++index) {
        const FFJeddahFixture& fixture = Fixtures[ordered[index]];
        Lights[index]->SetWorldLocation(fixture.positionCm);
        Lights[index]->SetWorldRotation((fixture.targetCm - fixture.positionCm).Rotation());
        Lights[index]->SetIntensity(1.8f * fixture.power * LightScale);
    }
}
