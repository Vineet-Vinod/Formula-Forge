#include "FFVisualReplay.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

FFVisualReplay::FFVisualReplay() = default;
FFVisualReplay::~FFVisualReplay() = default;

bool FFVisualReplay::Load(const FString& filename, FFSimulation& simulation, bool& chase) {
    Realtime = FParse::Param(FCommandLine::Get(), TEXT("FFReplayRealtime"));
    if (Realtime && FParse::Param(FCommandLine::Get(), TEXT("FFReplayAudit"))) return false;
    const FString root = FPlatformMisc::GetEnvironmentVariable(TEXT("FF_REPO_ROOT"));
    FString path = FPaths::ConvertRelativePathToFull(filename);
    FPaths::CollapseRelativeDirectories(path);
    if (root.IsEmpty() || !path.StartsWith(root / TEXT("build/unreal/recordings/"))) return false;
    FString contents;
    if (!FFileHelper::LoadFileToString(contents, *path)) return false;
    TArray<FString> lines;
    contents.ParseIntoArrayLines(lines);
    if (lines.Num() < 2 || lines.Num() > 20000) return false;
    for (int32 line = 1; line < lines.Num(); ++line) {
        TArray<FString> fields;
        lines[line].ParseIntoArray(fields, TEXT(","), false);
        if (fields.Num() != 18 || FCString::Atoi(*fields[0]) != line - 1) return false;
        FFReplayPose pose;
        pose.frame = line - 1;
        pose.time = FCString::Atod(*fields[1]);
        pose.position = Vec2{FCString::Atof(*fields[2]), FCString::Atof(*fields[3])} * 17.0f;
        pose.elevation = FCString::Atof(*fields[4]) * 17.0f;
        pose.heading = FCString::Atof(*fields[5]);
        pose.speed = FCString::Atof(*fields[6]) * 17.0f / 3.6f;
        pose.steer = FCString::Atof(*fields[7]);
        pose.pitch = FCString::Atof(*fields[8]);
        pose.roll = FCString::Atof(*fields[9]);
        pose.gear = FCString::Atoi(*fields[10]);
        pose.rpm = FCString::Atof(*fields[11]);
        pose.grounded = FCString::Atoi(*fields[12]) != 0;
        pose.chase = FCString::Atoi(*fields[13]) != 0;
        pose.lapSeconds = FCString::Atod(*fields[14]);
        pose.invalid = FCString::Atoi(*fields[15]) != 0;
        if (!FMath::IsFinite(pose.time) || pose.time < 0.0 || (!Poses.IsEmpty() && pose.time <= Poses.Last().time)) return false;
        Poses.Add(pose);
    }
    Output.Reset(FPlatformFileManager::Get().GetPlatformFile().OpenWrite(*(FPaths::GetPath(path) / TEXT("replay-presentation.csv"))));
    if (!Output) return false;
    const FTCHARToUTF8 header(TEXT("frame,time_s,actor_pitch_deg,actor_roll_deg,actor_z_cm,camera_pitch_deg,camera_roll_deg,camera_z_cm,penetration_m,render_time_s\n"));
    if (!Output->Write(reinterpret_cast<const uint8*>(header.Get()), header.Length())) return false;
    Current = Poses[0];
    Apply(simulation, chase);
    return true;
}

bool FFVisualReplay::Next(FFSimulation& simulation, bool& chase, float renderedDeltaSeconds) {
    if (Realtime) {
        if (Index == -1) {
            Index = 0;
            Current = Poses[0];
        } else {
            if (Current.time >= Poses.Last().time) return false;
            const double previous = Current.time;
            const double time = FMath::Min(previous + FMath::Max(renderedDeltaSeconds, 0.0f), Poses.Last().time);
            while (Poses.IsValidIndex(Index + 1) && Poses[Index + 1].time <= time) ++Index;
            Current = Poses.IsValidIndex(Index + 1) ? InterpolateReplayPose(Poses[Index], Poses[Index + 1], time) : Poses.Last();
            StepSeconds = static_cast<float>(Current.time - previous);
        }
    } else {
        if (!Poses.IsValidIndex(Index + 1)) return false;
        Current = Poses[++Index];
        StepSeconds = Index > 0 ? static_cast<float>(Current.time - Poses[Index - 1].time) : 0.0f;
    }
    Apply(simulation, chase);
    return true;
}

void FFVisualReplay::Apply(FFSimulation& simulation, bool& chase) {
    const auto& pose = Current;
    auto& vehicle = simulation.vehicle;
    vehicle.pos = pose.position;
    vehicle.elevation = pose.elevation;
    vehicle.heading = pose.heading;
    vehicle.forwardSpeed = pose.speed;
    vehicle.vel = fromAngle(pose.heading) * pose.speed;
    vehicle.steerAngle = pose.steer;
    vehicle.bodyPitch = pose.pitch;
    vehicle.bodyRoll = pose.roll;
    vehicle.engineRpmNormalized = pose.rpm;
    vehicle.gear = pose.gear;
    vehicle.grounded = pose.grounded;
    vehicle.wheelSpin += pose.speed * DeltaSeconds() / simulation.tuning.wheelRadius;
    simulation.trial.seconds = pose.lapSeconds;
    simulation.trial.running = pose.lapSeconds > 0.0;
    simulation.trial.invalid = pose.invalid;
    chase = pose.chase;
}

float FFVisualReplay::DeltaSeconds() const {
    return StepSeconds;
}

int32 FFVisualReplay::Frame() const {
    return Index;
}

double FFVisualReplay::TimeSeconds() const {
    return Current.time;
}

void FFVisualReplay::Report(const FTransform& actor, const FTransform& camera, float penetration) {
    const auto actorRotation = actor.Rotator();
    const auto cameraRotation = camera.Rotator();
    const FString line = FString::Printf(TEXT("%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.9f\n"),
        Index, Current.time, actorRotation.Pitch, actorRotation.Roll, actor.GetLocation().Z,
        cameraRotation.Pitch, cameraRotation.Roll, camera.GetLocation().Z, penetration, FPlatformTime::Seconds());
    const FTCHARToUTF8 bytes(*line);
    if (!Output->Write(reinterpret_cast<const uint8*>(bytes.Get()), bytes.Length())) {
        UE_LOG(LogTemp, Error, TEXT("Visual replay report write failed"));
        FPlatformMisc::RequestExitWithStatus(false, 1);
    }
}
