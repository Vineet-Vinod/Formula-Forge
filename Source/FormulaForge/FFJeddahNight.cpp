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
#include "Engine/SpotLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextureCube.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
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
    IConsoleVariable* injection = IConsoleManager::Get().FindConsoleVariable(TEXT("r.LightGridInjection.UseSpecializationConstants"));
    if (injection != nullptr) {
        PreviousLightInjection = injection->GetInt();
        if (PreviousLightInjection != 0) {
            // The experimental Vulkan kernel drops local lights on the supported Linux renderer.
            injection->Set(0, ECVF_SetByCode);
            RestoreLightInjection = injection->GetInt() == 0;
        }
    }
    UWorld* world = GetWorld();
    ADirectionalLight* fill = world->SpawnActor<ADirectionalLight>(FVector::ZeroVector, FRotator(-70, 126, 0));
    UDirectionalLightComponent* light = CastChecked<UDirectionalLightComponent>(fill->GetLightComponent());
    light->SetMobility(EComponentMobility::Movable);
    float fillIntensity = 1.6f;
    FParse::Value(FCommandLine::Get(), TEXT("FFJeddahFill="), fillIntensity);
    light->SetIntensity(FMath::IsFinite(fillIntensity) ? FMath::Clamp(fillIntensity, 0.0f, 4.0f) : 1.6f);
    light->SetLightColor(FLinearColor(0.80f, 0.88f, 1.0f));
    light->SetCastShadows(false);
    ASkyLight* sky = world->SpawnActor<ASkyLight>();
    USkyLightComponent* ambient = sky->GetLightComponent();
    ambient->SetMobility(EComponentMobility::Movable);
    ambient->SourceType = SLS_SpecifiedCubemap;
    ambient->SetCubemap(LoadObject<UTextureCube>(nullptr, TEXT("/Game/Generated/Jeddah/Environment/JeddahNightReflection.JeddahNightReflection")));
    ambient->SetRealTimeCapture(false);
    ambient->SetIntensity(0.80f);
    ambient->SetLightColor(FLinearColor::White);
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
    FParse::Value(FCommandLine::Get(), TEXT("FFJeddahGarageScale="), GarageLightScale);
    GarageLightScale = FMath::IsFinite(GarageLightScale) ? FMath::Clamp(GarageLightScale, 0.0f, 64.0f) : 1.0f;
    FParse::Value(FCommandLine::Get(), TEXT("FFJeddahEntryScale="), EntryLightScale);
    EntryLightScale = FMath::IsFinite(EntryLightScale) ? FMath::Clamp(EntryLightScale, 0.0f, 8.0f) : 1.0f;
    LightAuditRequested = FParse::Param(FCommandLine::Get(), TEXT("FFJeddahLightAudit"));
    LoadFixtures(TEXT("night_lights.csv"), Fixtures);
    for (int32 index = 0; index < FMath::Min(10, Fixtures.Num()); ++index) {
        ASpotLight* fixtureActor = world->SpawnActor<ASpotLight>();
        USpotLightComponent* spot = CastChecked<USpotLightComponent>(fixtureActor->GetLightComponent());
        spot->SetMobility(EComponentMobility::Movable);
        spot->bUseInverseSquaredFalloff = false;
        spot->SetIntensityUnits(ELightUnits::Unitless);
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
        Lights.Add(spot);
    }
    TArray<FFJeddahFixture> architecturalFixtures;
    LoadFixtures(TEXT("edition_lights.csv"), architecturalFixtures);
    LoadFixtures(TEXT("mosque_lights.csv"), architecturalFixtures);
    for (const FFJeddahFixture& fixture : architecturalFixtures) {
        ASpotLight* fixtureActor = world->SpawnActor<ASpotLight>();
        USpotLightComponent* spot = CastChecked<USpotLightComponent>(fixtureActor->GetLightComponent());
        spot->SetMobility(EComponentMobility::Movable);
        spot->bUseInverseSquaredFalloff = false;
        spot->SetIntensityUnits(ELightUnits::Unitless);
        spot->LightFalloffExponent = 2.0f;
        spot->SetAttenuationRadius(3500);
        spot->SetInnerConeAngle(40);
        spot->SetOuterConeAngle(65);
        spot->SetLightColor(FLinearColor(1.0f, 0.86f, 0.68f));
        spot->SetIntensity(1.8f * fixture.power);
        spot->SetCastShadows(false);
        spot->SetWorldLocation(fixture.positionCm);
        spot->SetWorldRotation((fixture.targetCm - fixture.positionCm).Rotation());
    }
    TArray<FFJeddahFixture> entryFixtures;
    LoadFixtures(TEXT("pit_entry_lights.csv"), entryFixtures);
    for (const FFJeddahFixture& fixture : entryFixtures) {
        ASpotLight* fixtureActor = world->SpawnActor<ASpotLight>();
        USpotLightComponent* spot = CastChecked<USpotLightComponent>(fixtureActor->GetLightComponent());
        spot->SetMobility(EComponentMobility::Movable);
        spot->bUseInverseSquaredFalloff = false;
        spot->SetIntensityUnits(ELightUnits::Unitless);
        spot->LightFalloffExponent = 2.0f;
        spot->SetAttenuationRadius(1400);
        spot->SetInnerConeAngle(50);
        spot->SetOuterConeAngle(80);
        spot->SetLightColor(FLinearColor(0.94f, 0.97f, 1.0f));
        spot->SetIntensity(1.8f * fixture.power * EntryLightScale);
        spot->SetCastShadows(false);
        spot->SetWorldLocation(fixture.positionCm);
        spot->SetWorldRotation((fixture.targetCm - fixture.positionCm).Rotation());
        if (LightAuditRequested) {
            UE_LOG(LogTemp, Display, TEXT("JEDDAH_LIGHT_AUDIT group=entry fixed=1 power=%.4f intensity=%.4f origin=%s target=%s"),
                fixture.power, spot->Intensity, *fixture.positionCm.ToString(), *fixture.targetCm.ToString());
        }
    }
    LoadFixtures(TEXT("pit_interior_lights.csv"), GarageFixtures);
    for (int32 index = 0; index < FMath::Min(4, GarageFixtures.Num()); ++index) {
        ASpotLight* fixtureActor = world->SpawnActor<ASpotLight>();
        USpotLightComponent* spot = CastChecked<USpotLightComponent>(fixtureActor->GetLightComponent());
        spot->SetMobility(EComponentMobility::Movable);
        spot->bUseInverseSquaredFalloff = false;
        spot->SetIntensityUnits(ELightUnits::Unitless);
        spot->LightFalloffExponent = 2.0f;
        spot->SetAttenuationRadius(1400);
        spot->SetInnerConeAngle(50);
        spot->SetOuterConeAngle(80);
        spot->SetLightColor(FLinearColor(0.94f, 0.97f, 1.0f));
        spot->SetIntensity(0);
        spot->SetCastShadows(false);
        GarageLights.Add(spot);
    }
    UpdateLights();
    UE_LOG(LogTemp, Display, TEXT("Jeddah night lighting: %d local fixtures; light-grid specializations=%d."),
        Lights.Num(), injection != nullptr ? injection->GetInt() : -1);
}

void AFFJeddahNight::EndPlay(const EEndPlayReason::Type reason) {
    if (RestoreLightInjection) {
        IConsoleVariable* injection = IConsoleManager::Get().FindConsoleVariable(TEXT("r.LightGridInjection.UseSpecializationConstants"));
        if (injection != nullptr) {
            injection->Set(PreviousLightInjection, ECVF_SetByCode);
            UE_LOG(LogTemp, Display, TEXT("Jeddah light injection restored to %d."), PreviousLightInjection);
        }
    }
    Super::EndPlay(reason);
}

void AFFJeddahNight::LoadFixtures(const TCHAR* filename, TArray<FFJeddahFixture>& fixtures) {
    TArray<FString> rows;
    const FString path = FPaths::ProjectContentDir() / TEXT("Generated/Jeddah/Data") / filename;
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
            fixtures.Add({FVector(values[0], values[1], values[2]),
                FVector(values[3], values[4], values[5]), static_cast<float>(values[6])});
        }
    }
    UE_LOG(LogTemp, Display, TEXT("Jeddah %s: %d registered fixtures."), filename, fixtures.Num());
}

void AFFJeddahNight::Tick(float deltaSeconds) {
    Super::Tick(deltaSeconds);
    UpdateLights();
}

void AFFJeddahNight::UpdateLights() {
    APlayerController* player = GetWorld()->GetFirstPlayerController();
    const FVector position = player != nullptr ? player->GetFocalLocation() : GetActorLocation();
    const bool audit = LightAuditRequested && !LightAuditLogged && GetWorld()->GetTimeSeconds() >= 2;
    if (audit) {
        UE_LOG(LogTemp, Display, TEXT("JEDDAH_LIGHT_AUDIT observer=%s possessed_pawn=%d"),
            *position.ToString(), player != nullptr && player->GetPawn() != nullptr);
    }
    const auto update = [&](const TArray<FFJeddahFixture>& fixtures,
            const TArray<TObjectPtr<USpotLightComponent>>& lights, const TCHAR* group, float scale) {
        TArray<int32> ordered;
        ordered.Reserve(fixtures.Num());
        for (int32 index = 0; index < fixtures.Num(); ++index) ordered.Add(index);
        ordered.Sort([&](int32 first, int32 last) {
            return FVector::DistSquared2D(position, fixtures[first].targetCm) <
                FVector::DistSquared2D(position, fixtures[last].targetCm);
        });
        for (int32 index = 0; index < lights.Num(); ++index) {
            const FFJeddahFixture& fixture = fixtures[ordered[index]];
            lights[index]->SetWorldLocation(fixture.positionCm);
            lights[index]->SetWorldRotation((fixture.targetCm - fixture.positionCm).Rotation());
            lights[index]->SetIntensity(1.8f * fixture.power * LightScale * scale);
            if (audit) {
                UE_LOG(LogTemp, Display, TEXT("JEDDAH_LIGHT_AUDIT group=%s source=%d power=%.4f intensity=%.4f distance_cm=%.2f origin=%s target=%s"),
                    group, ordered[index], fixture.power, lights[index]->Intensity,
                    FVector::Distance(position, fixture.positionCm),
                    *fixture.positionCm.ToString(), *fixture.targetCm.ToString());
            }
        }
    };
    update(Fixtures, Lights, TEXT("road"), 1.0f);
    update(GarageFixtures, GarageLights, TEXT("garage"), GarageLightScale);
    if (audit) LightAuditLogged = true;
}
