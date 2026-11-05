#include "FFLasVegasNight.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextureCube.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"

AFFLasVegasNight::AFFLasVegasNight() {
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    PrimaryActorTick.bCanEverTick = false;
}

void AFFLasVegasNight::BeginPlay() {
    Super::BeginPlay();
    UWorld* world = GetWorld();
    ADirectionalLight* moon = world->SpawnActor<ADirectionalLight>(FVector::ZeroVector, FRotator(-48, 126, 0));
    UDirectionalLightComponent* light = CastChecked<UDirectionalLightComponent>(moon->GetLightComponent());
    light->SetMobility(EComponentMobility::Movable);
    light->SetIntensity(.15f);
    light->SetLightColor(FLinearColor(.58f, .68f, 1.f));
    light->SetCastShadows(false);
    ASkyLight* sky = world->SpawnActor<ASkyLight>();
    USkyLightComponent* ambient = sky->GetLightComponent();
    ambient->SetMobility(EComponentMobility::Movable);
    ambient->SourceType = SLS_SpecifiedCubemap;
    ambient->SetCubemap(LoadObject<UTextureCube>(nullptr, TEXT("/Game/Generated/Environment/Daylight.Daylight")));
    ambient->SetRealTimeCapture(false);
    ambient->SetIntensity(.10f);
    ambient->SetLightColor(FLinearColor(.52f, .62f, .86f));
    ambient->SetLowerHemisphereColor(FLinearColor(.015f, .018f, .025f));
    AStaticMeshActor* dome = world->SpawnActor<AStaticMeshActor>();
    UStaticMeshComponent* sphere = dome->GetStaticMeshComponent();
    sphere->SetMobility(EComponentMobility::Movable);
    sphere->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    sphere->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Generated/LasVegas/Materials/NightSky.NightSky")));
    sphere->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    sphere->SetCastShadow(false);
    dome->SetActorScale3D(FVector(12000));
    AExponentialHeightFog* fog = world->SpawnActor<AExponentialHeightFog>();
    fog->GetComponent()->SetFogDensity(.0008f);
    fog->GetComponent()->SetFogHeightFalloff(.2f);
    fog->GetComponent()->SetFogInscatteringColor(FLinearColor(.018f, .022f, .026f));
    fog->GetComponent()->SetStartDistance(18000);
    ADirectionalLight* flood = world->SpawnActor<ADirectionalLight>(FVector::ZeroVector, FRotator(-78, 126, 0));
    UDirectionalLightComponent* floodlight = CastChecked<UDirectionalLightComponent>(flood->GetLightComponent());
    floodlight->SetMobility(EComponentMobility::Movable);
    floodlight->SetIntensity(2.4f);
    floodlight->SetLightColor(FLinearColor(1.f, .98f, .93f));
    floodlight->SetDynamicShadowDistanceMovableLight(30000);
    floodlight->SetDynamicShadowCascades(2);
    floodlight->SetCascadeDistributionExponent(3);
    floodlight->LightSourceAngle = 2.f;
    floodlight->ShadowBias = .35f;
    APostProcessVolume* post = world->SpawnActor<APostProcessVolume>();
    post->bUnbound = true;
    FPostProcessSettings& settings = post->Settings;
    settings.bOverride_AutoExposureMethod = true;
    settings.AutoExposureMethod = AEM_Manual;
    settings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
    settings.AutoExposureApplyPhysicalCameraExposure = false;
    settings.bOverride_BloomIntensity = true;
    settings.BloomIntensity = .24f;
    settings.bOverride_LensFlareIntensity = true;
    settings.LensFlareIntensity = 0;
    settings.bOverride_VignetteIntensity = true;
    settings.VignetteIntensity = .10f;
    settings.bOverride_AmbientOcclusionIntensity = true;
    settings.AmbientOcclusionIntensity = 0;
    settings.bOverride_ScreenSpaceReflectionIntensity = true;
    settings.ScreenSpaceReflectionIntensity = 0;
}
