#include "FFLapRecorder.h"
#include <string>
#include "FFGame.h"
#include "Camera/CameraComponent.h"
#include "Async/Async.h"
#include "Components/StaticMeshComponent.h"

#include "Dom/JsonObject.h"
#include "DynamicResolutionState.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "HAL/IConsoleManager.h"
#include "ImageUtils.h"
#include "ImageCore.h"
#include "InputKeyEventArgs.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UnrealClient.h"
#include "RenderingThread.h"
#include "ProfilingDebugging/CsvProfiler.h"
#include "RHICommandList.h"
#include "RHISurfaceDataConversion.h"

CSV_DECLARE_CATEGORY_EXTERN(FormulaForge);

namespace {
constexpr uint64 MaximumBytes = 8ull * 1024 * 1024 * 1024;
constexpr uint64 ReserveBytes = 10ull * 1024 * 1024 * 1024;

FString Json(const TSharedRef<FJsonObject>& object) {
    FString result;
    const auto writer = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&result);
    FJsonSerializer::Serialize(object, writer);
    return result;
}

TSharedRef<FJsonObject> ControlJson(const ArcadeVehicleControl& control) {
    const auto result = MakeShared<FJsonObject>();
    result->SetNumberField(TEXT("steer"), control.steer);
    result->SetNumberField(TEXT("throttle"), control.throttle);
    result->SetNumberField(TEXT("brake"), control.brake);
    result->SetBoolField(TEXT("shift_up"), control.shiftUpPressed);
    result->SetBoolField(TEXT("shift_down"), control.shiftDownPressed);
    result->SetBoolField(TEXT("automatic"), control.automaticShift);
    result->SetBoolField(TEXT("drift"), control.drift);
    result->SetBoolField(TEXT("drift_pressed"), control.driftPressed);
    result->SetNumberField(TEXT("speed_limit_extra"), control.forwardSpeedLimitExtra);
    return result;
}

TArray<TSharedPtr<FJsonValue>> VectorJson(const FVector& vector) {
    return {MakeShared<FJsonValueNumber>(vector.X), MakeShared<FJsonValueNumber>(vector.Y),
        MakeShared<FJsonValueNumber>(vector.Z)};
}
}

FFLapRecorder::FFLapRecorder(AFormulaTrialPawn& pawn) : Pawn(pawn) {
    TArray<FKey> keys;
    EKeys::GetAllKeys(keys);
    for (const FKey& key : keys) {
        if (key.IsGamepadKey()) SampleKeys.Add(key);
    }
    for (const FKey& key : {EKeys::W, EKeys::S, EKeys::A, EKeys::D, EKeys::SpaceBar,
            EKeys::Q, EKeys::E, EKeys::M, EKeys::R, EKeys::C, EKeys::P, EKeys::Escape, EKeys::F9}) {
        SampleKeys.Add(key);
    }
    FParse::Value(FCommandLine::Get(), TEXT("FFRecordSeconds="), MaximumSeconds);
    if (!FMath::IsFinite(MaximumSeconds) || MaximumSeconds <= 0.0 || MaximumSeconds > 900.0) MaximumSeconds = 900.0;
    FParse::Value(FCommandLine::Get(), TEXT("FFRecordLaps="), MaximumLaps);
    MaximumLaps = FMath::Clamp(MaximumLaps, 1, 20);
    QuitAfterRecord = FParse::Param(FCommandLine::Get(), TEXT("FFQuitAfterRecord"));
    Lossless = FParse::Param(FCommandLine::Get(), TEXT("FFRecordLossless"));
}

FFLapRecorder::~FFLapRecorder() {
    Stop(TEXT("recorder_destroyed"));
}

bool FFLapRecorder::Start() {
    if (Recording) return true;
    const FString root = FPlatformMisc::GetEnvironmentVariable(TEXT("FF_REPO_ROOT"));
    if (root.IsEmpty() || GEngine == nullptr || GEngine->GameViewport == nullptr ||
            FParse::Param(FCommandLine::Get(), TEXT("FFAudit")) ||
            FCString::Strstr(FCommandLine::Get(), TEXT("FFCapture=")) != nullptr) {
        LastStatus = TEXT("REC refused: use -FFRecord without single-shot capture or audit");
        UE_LOG(LogTemp, Error, TEXT("%s"), *LastStatus);
        return false;
    }
    Directory = root / TEXT("build/unreal/recordings") /
        (FDateTime::UtcNow().ToString(TEXT("%Y%m%d-%H%M%S")) + TEXT("-") + FGuid::NewGuid().ToString(EGuidFormats::Digits).Left(8));
    if (!IFileManager::Get().MakeDirectory(*(Directory / TEXT("frames")), true)) {
        LastStatus = TEXT("REC failed: cannot create session directory");
        return false;
    }
    BytesWritten = 0;
    if (!HasDiskBudget(0)) {
        LastStatus = TEXT("REC refused: preserve 10 GiB free disk space");
        return false;
    }
    auto& platform = FPlatformFileManager::Get().GetPlatformFile();
    Frames.Reset(platform.OpenWrite(*(Directory / TEXT("frames.jsonl"))));
    Inputs.Reset(platform.OpenWrite(*(Directory / TEXT("inputs.jsonl"))));
    Ticks.Reset(platform.OpenWrite(*(Directory / TEXT("ticks.jsonl"))));
    Steps.Reset(platform.OpenWrite(*(Directory / TEXT("steps.jsonl"))));
    if (!Frames || !Inputs || !Ticks || !Steps) {
        LastStatus = TEXT("REC failed: cannot open journals");
        Frames.Reset(); Inputs.Reset(); Ticks.Reset(); Steps.Reset();
        return false;
    }
    StartedAt = FPlatformTime::Seconds();
    SimulationSeconds = 0.0;
    TickIndex = -1;
    StepIndex = 0;
    FrameIndex = 0;
    SavedFrames = 0;
    InputIndex = 0;
    RenderedFrames = 0;
    ReadbackHead = 0;
    ReadbackCount = 0;
    for (auto& slot : Readbacks) {
        slot.readback = MakeUnique<FRHIGPUTextureReadback>(TEXT("FormulaForgeFrame"));
        slot.metadata.Reset();
        slot.submitted = false;
        slot.failed = false;
    }
    InitialLaps = Pawn.Simulation.trial.completedLaps;
    FModuleManager::Get().LoadModule(TEXT("ImageWrapper"));
    Recording = true;
    if (!WriteManifest(TEXT("recording"), TEXT(""))) {
        Stop(TEXT("manifest_write_failed"));
        return false;
    }
    ViewportClient = GEngine->GameViewport;
    ViewportClient->OnDrawn().AddRaw(this, &FFLapRecorder::PrepareFrame);
    ViewportClient->OnInputKey().AddRaw(this, &FFLapRecorder::InputKey);
    ViewportClient->OnInputAxis().AddRaw(this, &FFLapRecorder::InputAxis);
    LastStatus = Lossless ? TEXT("REC PNG, F9 stop") : TEXT("REC JPEG 98, F9 stop");
    UE_LOG(LogTemp, Display, TEXT("Lap recorder started: %s"), *Directory);
    return true;
}

void FFLapRecorder::Stop(const FString& reason) {
    if (!Recording) return;
    Recording = false;
    const bool frameSaved = DrainReadbacks();
    if (!frameSaved) FlushRenderingCommands();
    if (ViewportClient != nullptr) {
        ViewportClient->OnDrawn().RemoveAll(this);
        ViewportClient->OnInputKey().RemoveAll(this);
        ViewportClient->OnInputAxis().RemoveAll(this);
    }
    bool journalsSynced = Frames->Flush();
    journalsSynced &= Inputs->Flush();
    journalsSynced &= Ticks->Flush();
    journalsSynced &= Steps->Flush();
    const FString finalReason = !frameSaved ? TEXT("frame_write_failed") :
        !journalsSynced ? TEXT("journal_flush_failed") : reason;
    const bool saved = WriteManifest(TEXT("stopped"), finalReason);
    Frames.Reset(); Inputs.Reset(); Ticks.Reset(); Steps.Reset();
    LastStatus = saved ? TEXT("REC saved: ") + finalReason : TEXT("REC manifest write failed; journals retained");
    UE_LOG(LogTemp, Display, TEXT("Lap recorder stopped: %s, %lld frames, %lld inputs, %s"),
        *finalReason, SavedFrames, InputIndex, *Directory);
    if (QuitAfterRecord) FPlatformMisc::RequestExit(false);
}

bool FFLapRecorder::WriteLine(IFileHandle& file, const TSharedRef<FJsonObject>& record) {
    const FTCHARToUTF8 bytes(*(Json(record) + TEXT("\n")));
    if (!file.Write(reinterpret_cast<const uint8*>(bytes.Get()), bytes.Length())) return false;
    BytesWritten.fetch_add(bytes.Length());
    return true;
}

bool FFLapRecorder::WriteManifest(const FString& state, const FString& reason) {
    const auto record = MakeShared<FJsonObject>();
    record->SetNumberField(TEXT("schema_version"), 1);
    record->SetStringField(TEXT("state"), state);
    record->SetStringField(TEXT("stop_reason"), reason);
    record->SetStringField(TEXT("circuit"), FString(UTF8_TO_TCHAR(std::string(Pawn.Simulation.circuitName).c_str())).ToLower());
    record->SetStringField(TEXT("engine"), FEngineVersion::Current().ToString());
    record->SetStringField(TEXT("command_line"), FCommandLine::Get());
    record->SetBoolField(TEXT("presentation_only_replay"), FCString::Strstr(FCommandLine::Get(), TEXT("FFReplay=")) != nullptr);
    record->SetBoolField(TEXT("presentation_realtime_replay"), FParse::Param(FCommandLine::Get(), TEXT("FFReplayRealtime")));
    record->SetBoolField(TEXT("fullscreen"), GEngine->GameViewport != nullptr && GEngine->GameViewport->Viewport != nullptr &&
        GEngine->GameViewport->Viewport->IsFullscreen());
    for (const TCHAR* variable : {TEXT("r.ForwardShading"), TEXT("r.AntiAliasingMethod"), TEXT("r.MSAACount"),
            TEXT("r.ScreenPercentage"), TEXT("r.TemporalAA.HistoryScreenPercentage"), TEXT("r.TemporalAA.Quality"),
            TEXT("r.TemporalAAFilterSize"), TEXT("r.TemporalAACurrentFrameWeight"),
            TEXT("r.ViewTextureMipBias.Min"), TEXT("r.ViewTextureMipBias.Offset"),
            TEXT("r.MaxAnisotropy"), TEXT("r.DefaultBackBufferPixelFormat"), TEXT("r.DynamicRes.OperationMode"), TEXT("r.DynamicRes.MinScreenPercentage"),
            TEXT("r.DynamicRes.MaxScreenPercentage"), TEXT("r.DynamicRes.FrameTimeBudget")}) {
        record->SetNumberField(variable, IConsoleManager::Get().FindConsoleVariable(variable)->GetFloat());
    }
    record->SetStringField(TEXT("capture"), Lossless ? TEXT("lossless PNG for every drawn game viewport frame, including canvas HUD") :
        TEXT("JPEG quality 98 for every drawn game viewport frame, including canvas HUD; no frame dropping"));
    record->SetStringField(TEXT("input_scope"), TEXT("all key and axis events delivered to the game viewport, plus per-tick key states and every simulation-step control"));
    record->SetNumberField(TEXT("frames"), SavedFrames);
    record->SetNumberField(TEXT("rendered_frames"), RenderedFrames);
    record->SetNumberField(TEXT("input_events"), InputIndex);
    record->SetNumberField(TEXT("ticks"), TickIndex + 1);
    record->SetNumberField(TEXT("steps"), StepIndex);
    record->SetNumberField(TEXT("bytes_written"), static_cast<double>(BytesWritten.load()));
    record->SetNumberField(TEXT("duration_s"), FPlatformTime::Seconds() - StartedAt);
    record->SetNumberField(TEXT("maximum_bytes"), static_cast<double>(MaximumBytes));
    record->SetNumberField(TEXT("maximum_seconds"), MaximumSeconds);
    record->SetNumberField(TEXT("maximum_laps"), MaximumLaps);
    record->SetBoolField(TEXT("all_drawn_frames_saved"), RenderedFrames == SavedFrames);
    record->SetObjectField(TEXT("final_state"), Snapshot());
    const FString temporary = Directory / TEXT("session.json.tmp");
    return FFileHelper::SaveStringToFile(Json(record), *temporary, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM) &&
        IFileManager::Get().Move(*(Directory / TEXT("session.json")), *temporary, true, true);
}

bool FFLapRecorder::HasDiskBudget(uint64 additionalBytes) const {
    uint64 total = 0;
    uint64 free = 0;
    return additionalBytes <= MaximumBytes && BytesWritten.load() <= MaximumBytes - additionalBytes &&
        FPlatformMisc::GetDiskTotalAndFreeSpace(Directory, total, free) && free >= ReserveBytes + additionalBytes;
}

TSharedRef<FJsonObject> FFLapRecorder::Snapshot() const {
    const auto record = MakeShared<FJsonObject>();
    const auto& vehicle = Pawn.Simulation.vehicle;
    const auto& trial = Pawn.Simulation.trial;
    const auto projection = Pawn.Simulation.Project(vehicle.pos);
    record->SetNumberField(TEXT("tick"), TickIndex);
    record->SetNumberField(TEXT("step_end"), StepIndex);
    record->SetNumberField(TEXT("simulation_s"), SimulationSeconds);
    record->SetNumberField(TEXT("station_m"), projection.station);
    record->SetNumberField(TEXT("lane_m"), projection.lane / 17.0);
    record->SetNumberField(TEXT("speed_kph"), vehicle.forwardSpeed / 17.0 * 3.6);
    record->SetNumberField(TEXT("lateral_speed_mps"), vehicle.lateralSpeed / 17.0);
    record->SetNumberField(TEXT("heading_rad"), vehicle.heading);
    record->SetNumberField(TEXT("steer_angle_rad"), vehicle.steerAngle);
    record->SetNumberField(TEXT("gear"), vehicle.gear);
    record->SetNumberField(TEXT("rpm_normalized"), vehicle.engineRpmNormalized);
    record->SetNumberField(TEXT("body_pitch_rad"), vehicle.bodyPitch);
    record->SetNumberField(TEXT("body_roll_rad"), vehicle.bodyRoll);
    record->SetNumberField(TEXT("elevation_m"), vehicle.elevation / 17.0);
    record->SetNumberField(TEXT("vertical_speed_mps"), vehicle.verticalSpeed / 17.0);
    record->SetNumberField(TEXT("visual_penetration_m"), Pawn.RenderedPenetration);
    record->SetNumberField(TEXT("loaded_visual_tiles"), Pawn.LoadedVisualTiles());
    if (GEngine != nullptr) {
        FDynamicResolutionStateInfos resolution;
        GEngine->GetDynamicResolutionCurrentStateInfos(resolution);
        const bool dynamic = resolution.Status == EDynamicResolutionStatus::Enabled ||
            resolution.Status == EDynamicResolutionStatus::DebugForceEnabled;
        record->SetBoolField(TEXT("dynamic_resolution_active"), dynamic);
        record->SetNumberField(TEXT("primary_screen_percentage_approx"), dynamic ?
            resolution.ResolutionFractionApproximations[GDynamicPrimaryResolutionFraction] * 100.0f :
            IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))->GetFloat());
    }
    record->SetBoolField(TEXT("barrier_contact"), Pawn.Simulation.barrierContact);
    record->SetBoolField(TEXT("on_track"), Pawn.Simulation.OnTrack());
    record->SetBoolField(TEXT("grounded"), vehicle.grounded);
    record->SetBoolField(TEXT("paused"), Pawn.Paused);
    record->SetBoolField(TEXT("automatic"), Pawn.Automatic);
    record->SetBoolField(TEXT("chase_camera"), Pawn.ChaseCamera);
    record->SetBoolField(TEXT("lap_running"), trial.running);
    record->SetBoolField(TEXT("lap_invalid"), trial.invalid);
    record->SetBoolField(TEXT("pit_lane"), Pawn.Simulation.InPitLane());
    record->SetBoolField(TEXT("pit_overspeed"), Pawn.Simulation.PitOverspeed());
    record->SetNumberField(TEXT("pit_limit_kph"), Pawn.Simulation.PitSpeedLimitKph());
    record->SetNumberField(TEXT("timing_station_m"), Pawn.Simulation.ProgressStation());
    record->SetObjectField(TEXT("applied_control"), ControlJson(Pawn.Simulation.appliedControl));
    record->SetNumberField(TEXT("lap_s"), trial.seconds);
    record->SetNumberField(TEXT("completed_laps"), trial.completedLaps);
    record->SetNumberField(TEXT("next_gate"), trial.nextGate);
    record->SetNumberField(TEXT("last_lap_s"), trial.lastSeconds);
    record->SetBoolField(TEXT("last_lap_valid"), trial.lastValid);
    record->SetArrayField(TEXT("position_m"), VectorJson(FVector(vehicle.pos.x / 17.0, vehicle.pos.y / 17.0, vehicle.elevation / 17.0)));
    record->SetArrayField(TEXT("actor_position_cm"), VectorJson(Pawn.GetActorLocation()));
    const auto bodyRotation = Pawn.Body->GetRelativeRotation();
    record->SetArrayField(TEXT("body_relative_rotation_deg"), VectorJson(FVector(bodyRotation.Pitch, bodyRotation.Yaw, bodyRotation.Roll)));
    record->SetArrayField(TEXT("camera_position_cm"), VectorJson(Pawn.Camera->GetComponentLocation()));
    const auto cameraRotation = Pawn.Camera->GetComponentRotation();
    record->SetArrayField(TEXT("camera_rotation_deg"), VectorJson(FVector(cameraRotation.Pitch, cameraRotation.Yaw, cameraRotation.Roll)));
    record->SetNumberField(TEXT("camera_fov_deg"), Pawn.Camera->FieldOfView);
    if (Pawn.Replay) {
        record->SetNumberField(TEXT("replayed_frame"), Pawn.Replay->Frame());
        record->SetNumberField(TEXT("replayed_source_time_s"), Pawn.Replay->TimeSeconds());
    }
    const auto rotation = Pawn.GetActorRotation();
    record->SetArrayField(TEXT("actor_rotation_deg"), VectorJson(FVector(rotation.Pitch, rotation.Yaw, rotation.Roll)));
    return record;
}

void FFLapRecorder::BeginTick(float deltaSeconds) {
    if (!Recording) return;
    if (!PumpReadback(false)) {
        Stop(TEXT("frame_write_failed"));
        return;
    }
    ++TickIndex;
    TickDelta = deltaSeconds;
    TickStepBegin = StepIndex;
}

void FFLapRecorder::Step(const ArcadeVehicleControl& control, double deltaSeconds) {
    if (!Recording) return;
    const auto record = MakeShared<FJsonObject>();
    record->SetNumberField(TEXT("step"), StepIndex);
    record->SetNumberField(TEXT("tick"), TickIndex);
    record->SetNumberField(TEXT("simulation_s"), SimulationSeconds);
    record->SetNumberField(TEXT("dt_s"), deltaSeconds);
    record->SetObjectField(TEXT("control"), ControlJson(control));
    record->SetObjectField(TEXT("applied_control"), ControlJson(Pawn.Simulation.appliedControl));
    if (!WriteLine(*Steps, record)) {
        Stop(TEXT("step_write_failed"));
        return;
    }
    ++StepIndex;
    SimulationSeconds += deltaSeconds;
}

void FFLapRecorder::EndTick() {
    if (!Recording) return;
    const auto record = Snapshot();
    record->SetNumberField(TEXT("time_s"), FPlatformTime::Seconds() - StartedAt);
    record->SetNumberField(TEXT("dt_s"), TickDelta);
    record->SetNumberField(TEXT("step_begin"), TickStepBegin);
    record->SetNumberField(TEXT("input_end"), InputIndex);
    const auto raw = MakeShared<FJsonObject>();
    const auto* player = Cast<APlayerController>(Pawn.GetController());
    if (player != nullptr) {
        for (const FKey& key : SampleKeys) raw->SetNumberField(key.ToString(), player->GetInputAnalogKeyState(key));
    }
    record->SetObjectField(TEXT("raw_keys"), raw);
    if (!WriteLine(*Ticks, record)) Stop(TEXT("tick_write_failed"));
}

void FFLapRecorder::PrepareFrame() {
    if (!Recording) return;
    if (!PumpReadback(false)) {
        Stop(TEXT("frame_write_failed"));
        return;
    }
    double backpressureSeconds = 0.0;
    if (ReadbackCount == static_cast<int32>(Readbacks.size())) {
        const double started = FPlatformTime::Seconds();
        if (!PumpReadback(true)) {
            Stop(TEXT("gpu_readback_failed"));
            return;
        }
        backpressureSeconds = FPlatformTime::Seconds() - started;
    }
    if (!HasDiskBudget(16 * 1024 * 1024)) {
        Stop(TEXT("disk_limit"));
        return;
    }
    if (FPlatformTime::Seconds() - StartedAt >= MaximumSeconds) {
        Stop(TEXT("duration_limit"));
        return;
    }
    ++RenderedFrames;
    FFFrameReadback* slot = &Readbacks[(ReadbackHead + ReadbackCount) % Readbacks.size()];
    slot->metadata = Snapshot();
    slot->metadata->SetNumberField(TEXT("frame"), FrameIndex);
    slot->metadata->SetNumberField(TEXT("engine_frame"), GFrameCounter);
    slot->metadata->SetNumberField(TEXT("time_s"), FPlatformTime::Seconds() - StartedAt);
    slot->metadata->SetNumberField(TEXT("input_end"), InputIndex);
    slot->metadata->SetNumberField(TEXT("readback_backpressure_ms"), backpressureSeconds * 1000.0);
    slot->metadata->SetNumberField(TEXT("readback_queue_size"), ReadbackCount);
    slot->submitted = false;
    slot->failed = false;
    slot->mapped = false;
    slot->mapping = false;
    FViewport* viewport = ViewportClient->Viewport;
    ENQUEUE_RENDER_COMMAND(FormulaForgeReadbackCopy)([slot, viewport](FRHICommandListImmediate& commands) {
        const FTextureRHIRef texture = viewport->GetRenderTargetTexture();
        if (!texture.IsValid() || (texture->GetFormat() != PF_B8G8R8A8 && texture->GetFormat() != PF_R8G8B8A8 && texture->GetFormat() != PF_A2B10G10R10)) {
            UE_LOG(LogTemp, Error, TEXT("Recorder readback target invalid=%d format=%d"), !texture.IsValid(), texture.IsValid() ? static_cast<int32>(texture->GetFormat()) : -1);
            slot->failed = true;
        } else {
            const int32 width = texture->GetDesc().Extent.X;
            const int32 height = texture->GetDesc().Extent.Y;
            const bool rgba = texture->GetFormat() == PF_R8G8B8A8;
            const bool packed10 = texture->GetFormat() == PF_A2B10G10R10;
            if (slot->width != width || slot->height != height || slot->rgba != rgba || slot->packed10 != packed10) {
                slot->readback = MakeUnique<FRHIGPUTextureReadback>(TEXT("FormulaForgeFrame"));
            }
            slot->width = width;
            slot->height = height;
            slot->rgba = rgba;
            slot->packed10 = packed10;
            slot->readback->EnqueueCopy(commands, texture);
        }
        slot->submitted = true;
    });
    ++ReadbackCount;
    ++FrameIndex;
    if (Pawn.Simulation.trial.completedLaps - InitialLaps >= MaximumLaps) Stop(TEXT("lap_complete"));
}

bool FFLapRecorder::PumpReadback(bool waitForGPU) {
    CSV_SCOPED_TIMING_STAT(FormulaForge, RecorderReadback);
    if (!waitForGPU && FrameWrite.IsValid() && !FrameWrite.IsReady()) return true;
    if (ReadbackCount == 0) return FinishFrameWrite();
    auto& oldest = Readbacks[ReadbackHead];
    if (waitForGPU) {
        ENQUEUE_RENDER_COMMAND(FormulaForgeReadbackWait)([&oldest](FRHICommandListImmediate& commands) {
            oldest.readback->Wait(commands, oldest.readback->GetLastCopyGPUMask());
        });
        FlushRenderingCommands();
    }
    for (int32 offset = 0; offset < ReadbackCount; ++offset) {
        auto& slot = Readbacks[(ReadbackHead + offset) % Readbacks.size()];
        if (!slot.submitted) continue;
        if (slot.failed) return false;
        if (slot.mapping || !slot.readback->IsReady()) continue;
        const int32 width = slot.width;
        const int32 height = slot.height;
        if (width <= 0 || height <= 0 || static_cast<int64>(width) * height > 3840 * 2160) return false;
        slot.mapping = true;
        slot.pixels.SetNumUninitialized(width * height);
        ENQUEUE_RENDER_COMMAND(FormulaForgeReadbackMap)([&slot, width, height](FRHICommandListImmediate& commands) {
            const double copyStarted = FPlatformTime::Seconds();
            int32 rowPitch = 0;
            int32 bufferHeight = 0;
            const FColor* data = static_cast<const FColor*>(slot.readback->Lock(rowPitch, &bufferHeight));
            if (data != nullptr && rowPitch >= width && bufferHeight >= height) {
                if (slot.packed10) {
                    ConvertRawR10G10B10A2DataToFColor(width, height, reinterpret_cast<uint8*>(const_cast<FColor*>(data)), rowPitch * sizeof(FColor), slot.pixels.GetData());
                } else {
                    for (int32 row = 0; row < height; ++row) {
                        FMemory::Memcpy(slot.pixels.GetData() + row * width, data + row * rowPitch, width * sizeof(FColor));
                    }
                }
                for (auto& pixel : slot.pixels) {
                    pixel.A = 255;
                    if (slot.rgba) Swap(pixel.R, pixel.B);
                }
            } else {
                slot.failed = true;
            }
            if (data != nullptr) slot.readback->Unlock();
            slot.mapSeconds = FPlatformTime::Seconds() - copyStarted;
            slot.mapped = true;
        });
    }
    if (waitForGPU) FlushRenderingCommands();
    auto& slot = oldest;
    if (!slot.mapped) return !waitForGPU;
    if (slot.failed || !FinishFrameWrite()) return false;
    const int32 width = slot.width;
    const int32 height = slot.height;
    const FString extension = Lossless ? TEXT("png") : TEXT("jpg");
    const int32 quality = Lossless ? -1 : 98;
    const auto frame = slot.metadata.ToSharedRef();
    const FString filename = FString::Printf(TEXT("frames/%08lld.%s"), static_cast<int64>(frame->GetNumberField(TEXT("frame"))), *extension);
    frame->SetStringField(TEXT("image"), filename);
    frame->SetNumberField(TEXT("width"), width);
    frame->SetNumberField(TEXT("height"), height);
    frame->SetStringField(TEXT("capture_pixel_format"), slot.packed10 ? TEXT("RGB10A2") : slot.rgba ? TEXT("RGBA8") : TEXT("BGRA8"));
    frame->SetNumberField(TEXT("capture_finished_s"), FPlatformTime::Seconds() - StartedAt);
    frame->SetNumberField(TEXT("gpu_readback_cpu_ms"), slot.mapSeconds * 1000.0);
    FrameWrite = Async(EAsyncExecution::ThreadPool, [this, width, height, filename, extension, quality, frame, colors = MoveTemp(slot.pixels)]() {
        TArray64<uint8> png;
        const FImageView image(colors.GetData(), width, height);
        if (!FImageUtils::CompressImage(png, *extension, image, quality) || png.IsEmpty() ||
            !HasDiskBudget(png.Num()) || !FFileHelper::SaveArrayToFile(png, *(Directory / filename))) return false;
        BytesWritten.fetch_add(png.Num());
        frame->SetNumberField(TEXT("write_finished_s"), FPlatformTime::Seconds() - StartedAt);
        return WriteLine(*Frames, frame);
    });
    slot.metadata.Reset();
    ReadbackHead = (ReadbackHead + 1) % Readbacks.size();
    --ReadbackCount;
    return true;
}

bool FFLapRecorder::FinishFrameWrite() {
    if (!FrameWrite.IsValid()) return true;
    const bool result = FrameWrite.Get();
    FrameWrite = TFuture<bool>();
    if (result) ++SavedFrames;
    return result;
}

bool FFLapRecorder::DrainReadbacks() {
    while (ReadbackCount > 0) {
        if (!PumpReadback(true)) {
            FinishFrameWrite();
            return false;
        }
    }
    return FinishFrameWrite();
}

void FFLapRecorder::WriteInput(const TSharedRef<FJsonObject>& record) {
    if (!Recording) return;
    record->SetNumberField(TEXT("event"), InputIndex);
    record->SetNumberField(TEXT("time_s"), FPlatformTime::Seconds() - StartedAt);
    record->SetNumberField(TEXT("next_frame"), FrameIndex);
    record->SetNumberField(TEXT("after_tick"), TickIndex);
    if (!WriteLine(*Inputs, record)) {
        Stop(TEXT("input_write_failed"));
        return;
    }
    ++InputIndex;
}

void FFLapRecorder::InputKey(const FInputKeyEventArgs& event) {
    const auto record = MakeShared<FJsonObject>();
    record->SetStringField(TEXT("kind"), TEXT("key"));
    record->SetStringField(TEXT("key"), event.Key.ToString());
    record->SetNumberField(TEXT("action"), static_cast<int32>(event.Event));
    record->SetNumberField(TEXT("value"), event.AmountDepressed);
    record->SetNumberField(TEXT("controller_id"), event.ControllerId);
    record->SetNumberField(TEXT("device_id"), event.InputDevice.GetId());
    record->SetNumberField(TEXT("samples"), event.NumSamples);
    record->SetNumberField(TEXT("source_time_s"), event.EventTimestamp > 0 ?
        FPlatformTime::ToSeconds64(event.EventTimestamp) - StartedAt : -1.0);
    record->SetBoolField(TEXT("gamepad"), event.IsGamepad());
    WriteInput(record);
}

void FFLapRecorder::InputAxis(FViewport* viewport, int32 controllerId, FKey key, float value,
        float deltaSeconds, int32 samples, bool gamepad) {
    const auto record = MakeShared<FJsonObject>();
    record->SetStringField(TEXT("kind"), TEXT("axis"));
    record->SetStringField(TEXT("key"), key.ToString());
    record->SetNumberField(TEXT("value"), value);
    record->SetNumberField(TEXT("dt_s"), deltaSeconds);
    record->SetNumberField(TEXT("samples"), samples);
    record->SetNumberField(TEXT("controller_id"), controllerId);
    record->SetBoolField(TEXT("gamepad"), gamepad);
    WriteInput(record);
}

FString FFLapRecorder::Status() const {
    return Recording ? FString::Printf(TEXT("REC %lld frames / %.1f MiB, F9 stop"), FrameIndex,
        static_cast<double>(BytesWritten.load()) / (1024 * 1024)) : LastStatus;
}

bool FFLapRecorder::IsRecording() const {
    return Recording;
}
