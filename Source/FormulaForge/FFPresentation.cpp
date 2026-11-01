#include "FFPresentation.h"
#include "FFSession.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/AssetManager.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextureCube.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "ProfilingDebugging/CsvProfiler.h"

CSV_DECLARE_CATEGORY_EXTERN(FormulaForge);

AFFPresentation::AFFPresentation() {
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = 0.2f;
}

void AFFPresentation::BeginPlay() {
    Super::BeginPlay();
    FullDetail = FParse::Param(FCommandLine::Get(), TEXT("FFFullDetail"));
    ConfigureDaylight();
    FParse::Value(FCommandLine::Get(), TEXT("ResX="), RenderBudget.X);
    FParse::Value(FCommandLine::Get(), TEXT("ResY="), RenderBudget.Y);
    RenderBudget.X = FMath::Clamp(RenderBudget.X, 320, 3840);
    RenderBudget.Y = FMath::Clamp(RenderBudget.Y, 200, 2160);
    PresetScreenPercentage = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->GetFloat();
    UpdateRenderResolution();
    const FString circuit = GetGameInstance<UFFSession>()->Circuit();
    FString visualRoot = TEXT("Generated");
    if (circuit == TEXT("monza")) visualRoot += TEXT("/Monza");
    else if (circuit == TEXT("interlagos")) visualRoot += TEXT("/Interlagos");
    SilverstoneTiles = visualRoot == TEXT("Generated");
    FString contents;
    if (!FFileHelper::LoadFileToString(contents, *(FPaths::ProjectContentDir() / visualRoot / TEXT("Data/render_tiles.csv")))) {
        UE_LOG(LogTemp, Fatal, TEXT("Missing packaged render tile manifest in %s."), *visualRoot);
        return;
    }
    TArray<FString> lines;
    contents.ParseIntoArrayLines(lines);
    for (const auto& line : lines) {
        TArray<FString> fields;
        line.ParseIntoArray(fields, TEXT(","), false);
        if (fields.Num() != 7 || (!fields[0].StartsWith(TEXT("Tile_")) && !fields[0].StartsWith(TEXT("Building_")))) {
            UE_LOG(LogTemp, Fatal, TEXT("Invalid render tile record: %s"), *line);
            return;
        }
        FFVisualTile tile;
        tile.mesh = FSoftObjectPath(FString::Printf(TEXT("/Game/%s/Track/%s.%s"), *visualRoot, *fields[0], *fields[0]));
        tile.bounds = FBox(FVector(FCString::Atod(*fields[1]), FCString::Atod(*fields[2]), FCString::Atod(*fields[3])),
            FVector(FCString::Atod(*fields[4]), FCString::Atod(*fields[5]), FCString::Atod(*fields[6])));
        tile.building = fields[0].StartsWith(TEXT("Building_"));
        tile.crowd = fields[0].StartsWith(TEXT("Building_Crowd_"));
        Tiles.Add(MoveTemp(tile));
    }
    Components.SetNum(Tiles.Num());
    UpdateTiles(GetActorLocation(), true);
}

void AFFPresentation::EndPlay(const EEndPlayReason::Type reason) {
    IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->Set(PresetScreenPercentage, ECVF_SetByConsole);
    Super::EndPlay(reason);
}

void AFFPresentation::ConfigureDaylight() {
    UWorld* world = GetWorld();
    const bool balanced = !FParse::Param(FCommandLine::Get(), TEXT("FFQuality"));
    const bool forward = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ForwardShading"))->GetInt() != 0;
    const FString circuit = GetGameInstance<UFFSession>()->Circuit();
    const bool monza = circuit.Equals(TEXT("monza"), ESearchCase::IgnoreCase);
    float skyYaw = 0.0f;
    if (circuit.Equals(TEXT("interlagos"), ESearchCase::IgnoreCase)) {
        skyYaw = 124.0f;
    } else if (monza) {
        skyYaw = 180.0f;
    }
    const FRotator sunRotation(monza ? -43.0 : -37.8, 126.0 + skyYaw, 0.0);
    ADirectionalLight* sun = world->SpawnActor<ADirectionalLight>(FVector(0.0, 0.0, 10000.0), sunRotation);
    UDirectionalLightComponent* sunlight = CastChecked<UDirectionalLightComponent>(sun->GetLightComponent());
    sunlight->SetMobility(EComponentMobility::Movable);
    sunlight->SetWorldRotation(sunRotation);
    sunlight->SetIntensity(3.6f);
    sunlight->SetLightColor(FLinearColor(1.0f, 0.99f, 0.97f));
    sunlight->SetDynamicShadowDistanceMovableLight(30000.0f);
    sunlight->SetDynamicShadowCascades(balanced ? 2 : 3);
    sunlight->SetCascadeDistributionExponent(4.0f);
    sunlight->LightSourceAngle = 0.8f;
    sunlight->ContactShadowLength = 0.015f;
    sunlight->ShadowBias = 0.35f;
    sunlight->ShadowSharpen = 0.15f;
    UE_LOG(LogTemp, Display, TEXT("Daylight sun pitch=%.2f yaw=%.2f"), sunlight->GetComponentRotation().Pitch, sunlight->GetComponentRotation().Yaw);
    ASkyLight* sky = world->SpawnActor<ASkyLight>();
    USkyLightComponent* skylight = sky->GetLightComponent();
    skylight->SetMobility(EComponentMobility::Movable);
    skylight->SourceType = SLS_SpecifiedCubemap;
    skylight->CubemapResolution = 128;
    skylight->SetRealTimeCapture(false);
    UTextureCube* daylightCube = LoadObject<UTextureCube>(nullptr, monza
        ? TEXT("/Game/Generated/Monza/Environment/ClearDaylight.ClearDaylight")
        : TEXT("/Game/Generated/Environment/Daylight.Daylight"));
    skylight->SetCubemap(daylightCube);
    skylight->SetSourceCubemapAngle(skyYaw);
    skylight->SetIntensity(0.80f);
    skylight->SetLowerHemisphereColor(FLinearColor(0.11f, 0.12f, 0.09f));
    AStaticMeshActor* dome = world->SpawnActor<AStaticMeshActor>(GetActorLocation(), FRotator::ZeroRotator);
    UStaticMeshComponent* sphere = dome->GetStaticMeshComponent();
    sphere->SetMobility(EComponentMobility::Movable);
    sphere->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    sphere->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Generated/Environment/DaylightSky.DaylightSky")));
    float skyBrightness = monza ? 0.45f : 0.65f;
    FParse::Value(FCommandLine::Get(), TEXT("FFSkyBrightness="), skyBrightness);
    if (!FMath::IsFinite(skyBrightness)) skyBrightness = monza ? 0.45f : 0.65f;
    UMaterialInstanceDynamic* skyMaterial = sphere->CreateDynamicMaterialInstance(0);
    skyMaterial->SetTextureParameterValue(TEXT("Sky"), daylightCube);
    skyMaterial->SetScalarParameterValue(TEXT("Brightness"), FMath::Clamp(skyBrightness, 0.1f, 2.0f));
    skyMaterial->SetScalarParameterValue(TEXT("Yaw"), skyYaw);
    sphere->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    sphere->SetCastShadow(false);
    dome->SetActorScale3D(FVector(12000.0));
    AExponentialHeightFog* fog = world->SpawnActor<AExponentialHeightFog>();
    fog->GetComponent()->SetFogDensity(0.0015f);
    fog->GetComponent()->SetFogInscatteringColor(FLinearColor(0.26f, 0.31f, 0.34f));
    fog->GetComponent()->SetFogHeightFalloff(0.15f);
    fog->GetComponent()->SetStartDistance(12000.0f);
    APostProcessVolume* post = world->SpawnActor<APostProcessVolume>();
    post->bUnbound = true;
    FPostProcessSettings& settings = post->Settings;
    settings.bOverride_AutoExposureMethod = true;
    settings.AutoExposureMethod = AEM_Manual;
    settings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
    settings.AutoExposureApplyPhysicalCameraExposure = false;
    settings.bOverride_AmbientOcclusionIntensity = true;
    settings.AmbientOcclusionIntensity = forward ? 0.0f : 0.55f;
    settings.bOverride_AmbientOcclusionRadius = true;
    settings.AmbientOcclusionRadius = 55.0f;
    settings.bOverride_BloomIntensity = true;
    settings.BloomIntensity = 0.04f;
    settings.bOverride_VignetteIntensity = true;
    settings.VignetteIntensity = 0.12f;
    settings.bOverride_LensFlareIntensity = true;
    settings.LensFlareIntensity = 0.0f;
    settings.bOverride_ScreenSpaceReflectionIntensity = true;
    settings.ScreenSpaceReflectionIntensity = forward || balanced ? 0.0f : 80.0f;
    settings.bOverride_ScreenSpaceReflectionQuality = true;
    settings.ScreenSpaceReflectionQuality = balanced ? 35.0f : 60.0f;
    if (balanced && !forward) {
        world->GetFirstPlayerController()->ConsoleCommand(TEXT("r.ScreenPercentage 75"), false);
        world->GetFirstPlayerController()->ConsoleCommand(TEXT("r.Shadow.MaxResolution 2048"), false);
    }
    if (FParse::Param(FCommandLine::Get(), TEXT("FFTemporal"))) {
        world->GetFirstPlayerController()->ConsoleCommand(TEXT("r.AntiAliasingMethod 2"), false);
    }
    if (FParse::Param(FCommandLine::Get(), TEXT("FFMSAA"))) {
        world->GetFirstPlayerController()->ConsoleCommand(TEXT("r.AntiAliasingMethod 3"), false);
    }
    if (FParse::Param(FCommandLine::Get(), TEXT("FFTSR"))) {
        APlayerController* player = world->GetFirstPlayerController();
        for (const TCHAR* command : {TEXT("r.AntiAliasingMethod 4"), TEXT("r.TSR.History.ScreenPercentage 100"),
                TEXT("r.TSR.History.UpdateQuality 2"), TEXT("r.TSR.RejectionAntiAliasingQuality 1"),
                TEXT("r.TSR.ReprojectionField 0"), TEXT("r.TSR.Resurrection 0"), TEXT("r.TSR.ShadingRejection.Flickering 1"),
                TEXT("r.TSR.ThinGeometryDetection 1")}) {
            player->ConsoleCommand(command, false);
        }
    }
    UE_LOG(LogTemp, Display, TEXT("Render configuration: forward=%d AA=%d MSAA=%d screen_percentage=%.1f TAA_quality=%d TAA_history=%.1f"),
        forward, IConsoleManager::Get().FindConsoleVariable(TEXT("r.AntiAliasingMethod"))->GetInt(),
        IConsoleManager::Get().FindConsoleVariable(TEXT("r.MSAACount"))->GetInt(),
        IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->GetFloat(),
        IConsoleManager::Get().FindConsoleVariable(TEXT("r.TemporalAA.Quality"))->GetInt(),
        IConsoleManager::Get().FindConsoleVariable(TEXT("r.TemporalAA.HistoryScreenPercentage"))->GetFloat());
}

void AFFPresentation::UpdateRenderResolution() {
    if (GEngine->GameViewport == nullptr || GEngine->GameViewport->Viewport == nullptr) return;
    FViewport* viewport = GEngine->GameViewport->Viewport;
    const FIntPoint size = viewport->GetSizeXY();
    const bool fullscreen = viewport->IsFullscreen();
    if (size.X <= 0 || size.Y <= 0 || (size == LastViewportSize && fullscreen == LastFullscreen)) return;
    LastViewportSize = size;
    LastFullscreen = fullscreen;
    const float scale = fullscreen ? FMath::Min(1.0f, FMath::Min(static_cast<float>(RenderBudget.X) / size.X,
        static_cast<float>(RenderBudget.Y) / size.Y)) : 1.0f;
    GetWorld()->GetFirstPlayerController()->ConsoleCommand(
        FString::Printf(TEXT("r.ScreenPercentage %.6f"), PresetScreenPercentage * scale), false);
    UE_LOG(LogTemp, Display, TEXT("Viewport %dx%d fullscreen=%d, scene percentage %.3f, render budget %dx%d"),
        size.X, size.Y, fullscreen, PresetScreenPercentage * scale, RenderBudget.X, RenderBudget.Y);
}

void AFFPresentation::AttachTile(int32 index) {
    if (Components[index] != nullptr) return;
    UStaticMesh* mesh = Cast<UStaticMesh>(Tiles[index].mesh.ResolveObject());
    if (mesh == nullptr) {
        UE_LOG(LogTemp, Error, TEXT("Could not load visual tile %s"), *Tiles[index].mesh.ToString());
        return;
    }
    UStaticMeshComponent* component = NewObject<UStaticMeshComponent>(this);
    component->SetMobility(EComponentMobility::Static);
    component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    component->SetStaticMesh(mesh);
    if (Tiles[index].crowd) component->SetCastShadow(false);
    component->SetWorldLocation(FVector::ZeroVector);
    Components[index] = component;
    ApplyTileDetail(index, Tiles[index].bounds.ComputeSquaredDistanceToPoint(LastPosition));
    component->RegisterComponent();
}

void AFFPresentation::ApplyTileDetail(int32 index, double distanceSquared) {
    if (Tiles[index].crowd) {
        const int32 current = Components[index]->GetForcedLodModel();
        const double threshold = current == 1 ? 16000.0 : current == 2 ? 12000.0 : 14000.0;
        Components[index]->SetForcedLodModel(FullDetail || distanceSquared < FMath::Square(threshold) ? 1 : 2);
        return;
    }
    if (Tiles[index].building) return;
    const double nearDistance = SilverstoneTiles ? 4000.0 : 6000.0;
    const double farDistance = SilverstoneTiles ? 14000.0 : 20000.0;
    const int32 lod = FullDetail || distanceSquared < FMath::Square(nearDistance) ? 1 :
        distanceSquared < FMath::Square(farDistance) ? 2 : 3;
    Components[index]->SetForcedLodModel(FMath::Min(lod, Components[index]->GetStaticMesh()->GetNumLODs()));
}

bool AFFPresentation::UpdateTiles(FVector position, bool immediate) {
    CSV_SCOPED_TIMING_STAT(FormulaForge, TileStreaming);
    LastPosition = position;
    TArray<int32> candidates;
    int32 pending = 0;
    bool released = false;
    for (int32 index = 0; index < Tiles.Num(); ++index) {
        FFVisualTile& tile = Tiles[index];
        const double distanceSquared = tile.bounds.ComputeSquaredDistanceToPoint(position);
        if (Components[index] != nullptr && (!tile.building || tile.crowd)) {
            ApplyTileDetail(index, distanceSquared);
        }
        const double radius = tile.building ? 180000.0 : 95000.0;
        if (tile.request && !tile.request->HasLoadCompleted()) ++pending;
        if (distanceSquared > FMath::Square(radius + 25000.0)) {
            if (Components[index] != nullptr) {
                Components[index]->DestroyComponent();
                Components[index] = nullptr;
                released = true;
                ++ReleasedSinceCollection;
            }
            if (tile.request) {
                tile.request->CancelHandle();
                tile.request.Reset();
            }
            continue;
        }
        if (Components[index] != nullptr || distanceSquared > FMath::Square(radius)) continue;
        if (immediate && distanceSquared < FMath::Square(18000.0)) {
            if (tile.request) {
                tile.request->CancelHandle();
                tile.request.Reset();
            }
            if (tile.mesh.TryLoad() != nullptr) AttachTile(index);
        } else if (!tile.request) {
            candidates.Add(index);
        }
    }
    const double now = GetWorld()->GetTimeSeconds();
    if (released && (ReleasedSinceCollection >= 12 || now - LastCollectionSeconds >= 3.0)) {
        GEngine->ForceGarbageCollection(false);
        ReleasedSinceCollection = 0;
        LastCollectionSeconds = now;
    }
    candidates.Sort([&](int32 first, int32 second) {
        return Tiles[first].bounds.ComputeSquaredDistanceToPoint(position) < Tiles[second].bounds.ComputeSquaredDistanceToPoint(position);
    });
    for (int32 index : candidates) {
        if (pending >= 2) break;
        const TWeakObjectPtr<AFFPresentation> weakThis(this);
        Tiles[index].request = UAssetManager::GetStreamableManager().RequestAsyncLoad(Tiles[index].mesh,
            FStreamableDelegate::CreateLambda([weakThis, index]() {
                if (weakThis.IsValid()) weakThis->AttachTile(index);
            }));
        ++pending;
    }
    bool nearby = false;
    for (int32 index = 0; index < Tiles.Num(); ++index) {
        if (Tiles[index].bounds.ComputeSquaredDistanceToPoint(position) >= FMath::Square(18000.0)) continue;
        nearby = true;
        if (Components[index] == nullptr) return false;
    }
    return nearby;
}

void AFFPresentation::Tick(float deltaSeconds) {
    Super::Tick(deltaSeconds);
    UpdateRenderResolution();
    const APlayerController* player = GetWorld()->GetFirstPlayerController();
    if (player != nullptr && player->GetPawn() != nullptr) {
        const FVector position = player->GetPawn()->GetActorLocation();
        UpdateTiles(position, FVector::DistSquared(position, LastPosition) > FMath::Square(30000.0));
    }
}

int32 AFFPresentation::LoadedTiles() const {
    int32 loaded = 0;
    for (const auto& component : Components) if (component != nullptr) ++loaded;
    return loaded;
}

bool AFFPresentation::IsStreaming() const {
    return Tiles.ContainsByPredicate([](const FFVisualTile& tile) {
        return tile.request && !tile.request->HasLoadCompleted();
    });
}
