#include "FFTrialHUD.hpp"
#include <string>
#include "FFGame.h"
#include "FFSession.h"
#include "FFFrontend.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "GameFramework/PlayerController.h"
#include "GlobalRenderResources.h"
#include "InputCoreTypes.h"
#include "Styling/CoreStyle.h"

namespace {
const FLinearColor Ink(0.012f, 0.018f, 0.028f, 0.90f);
const FLinearColor Header(0.035f, 0.046f, 0.065f, 0.96f);
const FLinearColor Rule(0.15f, 0.19f, 0.24f, 0.80f);
const FLinearColor White(0.95f, 0.98f, 1.0f);
const FLinearColor Muted(0.57f, 0.66f, 0.75f);
const FLinearColor Mint(0.15f, 1.0f, 0.72f);
const FLinearColor Amber(1.0f, 0.66f, 0.14f);
const FLinearColor Red(1.0f, 0.19f, 0.16f);
const FLinearColor Violet(0.63f, 0.42f, 1.0f);
const FLinearColor Energy(0.80f, 0.99f, 0.16f);
const FLinearColor Dial(0.008f, 0.012f, 0.020f, 0.96f);
}

namespace FFTrialHUD {
FString TrialTime(double seconds, bool available) {
    if (!available || !FMath::IsFinite(seconds) || seconds < 0.0) {
        return TEXT("--:--.---");
    }
    const int64 milliseconds = FMath::RoundToInt64(seconds * 1000.0);
    return FString::Printf(TEXT("%02lld:%02lld.%03lld"), milliseconds / 60000,
        (milliseconds / 1000) % 60, milliseconds % 1000);
}

FVector2D FTrialHUDPainter::Pixel(FVector2D position) const {
    return position * Scale;
}

void FTrialHUDPainter::Rect(float left, float top, float width, float height, FLinearColor color) const {
    FCanvasTileItem item(Pixel({left, top}), Pixel({width, height}), color);
    item.BlendMode = SE_BLEND_Translucent;
    Canvas.DrawItem(item);
}

void FTrialHUDPainter::Triangle(FVector2D first, FVector2D second, FVector2D third, FLinearColor color) const {
    FCanvasTriangleItem item(Pixel(first), Pixel(second), Pixel(third), GWhiteTexture);
    item.SetColor(color);
    item.BlendMode = SE_BLEND_Translucent;
    Canvas.DrawItem(item);
}

void FTrialHUDPainter::Line(FVector2D start, FVector2D end, float thickness, FLinearColor color) const {
    const FVector2D direction = (end - start).GetSafeNormal();
    const FVector2D across(-direction.Y * thickness * 0.5f, direction.X * thickness * 0.5f);
    Triangle(start + across, end + across, end - across, color);
    Triangle(start + across, end - across, start - across, color);
}

void FTrialHUDPainter::Arc(FVector2D centre, float radius, float startDegrees, float sweepDegrees,
    float thickness, FLinearColor color) const {
    const int32 segments = FMath::Max(1, FMath::CeilToInt(FMath::Abs(sweepDegrees) / 6.0f));
    const float innerRadius = FMath::Max(0.0f, radius - thickness);
    FCanvasTriangleItem item(FVector2D::ZeroVector, FVector2D::ZeroVector, FVector2D::ZeroVector, GWhiteTexture);
    item.BlendMode = SE_BLEND_Translucent;
    item.TriangleList.Reset(segments * 2);
    for (int32 segment = 0; segment < segments; ++segment) {
        const float start = FMath::DegreesToRadians(startDegrees + sweepDegrees * segment / segments);
        const float end = FMath::DegreesToRadians(startDegrees + sweepDegrees * (segment + 1) / segments);
        const FVector2D first(FMath::Cos(start), FMath::Sin(start));
        const FVector2D last(FMath::Cos(end), FMath::Sin(end));
        FCanvasUVTri triangle{};
        triangle.V0_Pos = Pixel(centre + first * radius);
        triangle.V1_Pos = Pixel(centre + last * radius);
        triangle.V2_Pos = Pixel(centre + last * innerRadius);
        triangle.V0_Color = color;
        triangle.V1_Color = color;
        triangle.V2_Color = color;
        item.TriangleList.Add(triangle);
        if (innerRadius > 0.0f) {
            triangle.V1_Pos = triangle.V2_Pos;
            triangle.V2_Pos = Pixel(centre + first * innerRadius);
            item.TriangleList.Add(triangle);
        }
    }
    Canvas.DrawItem(item);
}

void FTrialHUDPainter::Panel(float left, float top, float width, float height) const {
    Rect(left, top, width, height - 14.0f, Ink);
    Rect(left, top + height - 14.0f, width - 14.0f, 14.0f, Ink);
    Triangle({left + width - 14.0f, top + height - 14.0f},
        {left + width, top + height - 14.0f}, {left + width - 14.0f, top + height}, Ink);
    Rect(left, top, width, 2.0f, Rule);
}

void FTrialHUDPainter::Text(const FString& text, float left, float top, float height, FLinearColor color,
    float alignment, float maxWidth) const {
    UFont* font = height >= 28.0f ? UEngine::GetLargeFont() : UEngine::GetMediumFont();
    if (font == nullptr) {
        return;
    }
    const float fontScale = height / FMath::Max(1.0f, font->GetMaxCharHeight());
    const float fontSize = FMath::Max(1.0f,
        FMath::RoundToFloat(font->GetLegacySlateFontInfo().Size * fontScale * Scale));
    const FSlateFontInfo fontInfo = FCoreStyle::GetDefaultFontStyle(
        height >= 18.0f ? TEXT("Bold") : TEXT("Regular"), fontSize);
    FTrialHUDTextItem item(Pixel({left, top}), FText::FromString(text), fontInfo, color);
    item.Font = font;
    FVector2D textSize = item.GetTextSize(1.0f);
    if (maxWidth > 0.0f && textSize.X > maxWidth * Scale) {
        FSlateFontInfo& fittedFont = item.SlateFontInfo.GetValue();
        fittedFont.Size = FMath::Max(1.0f, FMath::FloorToFloat(fittedFont.Size * maxWidth * Scale / textSize.X));
        textSize = item.GetTextSize(1.0f);
        while (fittedFont.Size > 1.0f && textSize.X > maxWidth * Scale) {
            fittedFont.Size -= 1.0f;
            textSize = item.GetTextSize(1.0f);
        }
    }
    item.Position.X = FMath::RoundToFloat(item.Position.X - textSize.X * alignment);
    item.Position.Y = FMath::RoundToFloat(item.Position.Y);
    item.EnableShadow(FLinearColor(0.0f, 0.0f, 0.0f, 0.65f), FVector2D(Scale, Scale));
    Canvas.DrawItem(item);
}

FTrialHUDMap::FTrialHUDMap(const FFSimulation& simulation)
    : Geometry(FVector2D::ZeroVector, FVector2D::ZeroVector, FVector2D::ZeroVector, GWhiteTexture) {
    FVector2D minimum(TNumericLimits<float>::Max(), TNumericLimits<float>::Max());
    FVector2D maximum(-TNumericLimits<float>::Max(), -TNumericLimits<float>::Max());
    for (int32 index = 0; index < SampleCount; ++index) {
        const Vec2 position = simulation.Sample(simulation.lapLength * index / SampleCount).position;
        Points[index] = FVector2D(position.x, -position.y);
        minimum.X = FMath::Min(minimum.X, Points[index].X);
        minimum.Y = FMath::Min(minimum.Y, Points[index].Y);
        maximum.X = FMath::Max(maximum.X, Points[index].X);
        maximum.Y = FMath::Max(maximum.Y, Points[index].Y);
    }
    Centre = (minimum + maximum) * 0.5;
    UnitsToMap = static_cast<float>(FMath::Min(384.0 / FMath::Max(1.0, maximum.X - minimum.X),
        252.0 / FMath::Max(1.0, maximum.Y - minimum.Y)));
    for (FVector2D& point : Points) {
        point = (point - Centre) * UnitsToMap;
    }
    const auto& sections = simulation.pitLane.Sections();
    const std::size_t stride = FMath::Max<std::size_t>(1, sections.size() / 160);
    for (std::size_t index = 0; index < sections.size(); index += stride) {
        const auto& section = sections[index];
        PitPoints.Add((FVector2D(section.position.x * 17.0f, -section.position.y * 17.0f) - Centre) * UnitsToMap);
    }
    if (!sections.empty()) {
        const auto& last = sections.back();
        PitPoints.Add((FVector2D(last.position.x * 17.0f, -last.position.y * 17.0f) - Centre) * UnitsToMap);
    }
    Geometry.BlendMode = SE_BLEND_Translucent;
}

void FTrialHUDMap::Draw(const FTrialHUDPainter& painter, FVector2D origin) {
    if (CachedOrigin != origin || CachedScale != painter.Scale) {
        CachedOrigin = origin;
        CachedScale = painter.Scale;
        Geometry.TriangleList.Reset(SampleCount * 4 + PitPoints.Num() * 2);
        for (int32 pass = 0; pass < 2; ++pass) {
            const float halfWidth = pass == 0 ? 3.5f : 1.25f;
            const FLinearColor color = pass == 0 ? White : Header;
            for (int32 index = 0; index < SampleCount; ++index) {
                const FVector2D start = Points[index] + origin;
                const FVector2D end = Points[(index + 1) % SampleCount] + origin;
                const FVector2D direction = (end - start).GetSafeNormal();
                const FVector2D across(-direction.Y * halfWidth, direction.X * halfWidth);
                AddTriangle(painter.Pixel(start + across), painter.Pixel(end + across),
                    painter.Pixel(end - across), color);
                AddTriangle(painter.Pixel(start + across), painter.Pixel(end - across),
                    painter.Pixel(start - across), color);
            }
        }
        for (int32 index = 1; index < PitPoints.Num(); ++index) {
            const FVector2D first = PitPoints[index - 1] + origin;
            const FVector2D last = PitPoints[index] + origin;
            const FVector2D direction = (last - first).GetSafeNormal();
            const FVector2D across(-direction.Y * 1.2, direction.X * 1.2);
            const FLinearColor pitColor(0.30f, 0.66f, 1.0f, 1.0f);
            AddTriangle(painter.Pixel(first + across), painter.Pixel(last + across), painter.Pixel(last - across), pitColor);
            AddTriangle(painter.Pixel(first + across), painter.Pixel(last - across), painter.Pixel(first - across), pitColor);
        }
    }
    painter.Canvas.DrawItem(Geometry);
    const FVector2D direction = (Points[1] - Points[0]).GetSafeNormal();
    const FVector2D across(-direction.Y * 7.0, direction.X * 7.0);
    painter.Line(origin + Points[0] - across, origin + Points[0] + across, 3.0f, Mint);
}

void FTrialHUDMap::AddTriangle(FVector2D first, FVector2D second, FVector2D third, FLinearColor color) {
    FCanvasUVTri triangle{};
    triangle.V0_Pos = first;
    triangle.V1_Pos = second;
    triangle.V2_Pos = third;
    triangle.V0_Color = color;
    triangle.V1_Color = color;
    triangle.V2_Color = color;
    Geometry.TriangleList.Add(triangle);
}

bool GamepadActive(const APlayerController& player, bool previous) {
    bool gamepad = previous;
    if (FMath::Abs(player.GetInputAnalogKeyState(EKeys::Gamepad_LeftX)) > 0.2f ||
        player.GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.05f ||
        player.GetInputAnalogKeyState(EKeys::Gamepad_LeftTriggerAxis) > 0.05f) {
        gamepad = true;
    }
    for (const FKey& key : {EKeys::Gamepad_Special_Right, EKeys::Gamepad_Special_Left,
        EKeys::Gamepad_FaceButton_Top, EKeys::Gamepad_FaceButton_Left, EKeys::Gamepad_FaceButton_Right,
        EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_RightShoulder}) {
        if (player.WasInputKeyJustPressed(key)) {
            gamepad = true;
        }
    }
    for (const FKey& key : {EKeys::W, EKeys::S, EKeys::A, EKeys::D, EKeys::Q, EKeys::E,
        EKeys::M, EKeys::R, EKeys::C, EKeys::P, EKeys::SpaceBar, EKeys::Escape}) {
        if (player.IsInputKeyDown(key)) {
            gamepad = false;
        }
    }
    return gamepad;
}
}

void AFormulaTrialHUD::DrawHUD() {
    Super::DrawHUD();
    auto* session = GetGameInstance<UFFSession>();
    if (Canvas && Canvas->SizeX > 0 && Canvas->SizeY > 0 && session->Screen != EFFScreen::Driving) {
        DrawFormulaFrontend(*this, *Canvas, *session);
        return;
    }
    const AFormulaTrialPawn* pawn = Cast<AFormulaTrialPawn>(GetOwningPawn());
    if (pawn == nullptr || Canvas == nullptr || Canvas->SizeX <= 0 || Canvas->SizeY <= 0) {
        return;
    }

    const float scale = FMath::Min(Canvas->SizeX / 1920.0f, Canvas->SizeY / 1080.0f);
    const float width = Canvas->SizeX / scale;
    const float height = Canvas->SizeY / scale;
    const FFSimulation& simulation = pawn->Simulation;
    const FFTrialHUD::FTrialHUDPainter painter{*Canvas, scale};
    if (!pawn->SceneReady) {
        painter.Rect(0.0f, 0.0f, width, height, FLinearColor(0.012f, 0.018f, 0.028f, 1.0f));
        painter.Rect(width * 0.5f - 160.0f, height * 0.5f - 84.0f, 320.0f, 3.0f, Mint);
        painter.Text(FString(UTF8_TO_TCHAR(std::string(simulation.circuitName).c_str())).ToUpper(), width * 0.5f, height * 0.5f - 55.0f, 48.0f, White, 0.5f);
        painter.Text(TEXT("PREPARING TIME TRIAL"), width * 0.5f, height * 0.5f + 15.0f, 18.0f, Muted, 0.5f);
        return;
    }
    const FFTrialState& trial = simulation.trial;
    const ArcadeVehicleState& vehicle = simulation.vehicle;
    const bool inPitLane = simulation.InPitLane();
    const bool pitOverspeed = inPitLane && simulation.PitOverspeed();
    static TWeakObjectPtr<AFormulaTrialHUD> inputOwner;
    static bool gamepad = false;
    if (inputOwner.Get() != this) {
        inputOwner = this;
        gamepad = false;
    }
    if (const APlayerController* player = GetOwningPlayerController()) {
        gamepad = FFTrialHUD::GamepadActive(*player, gamepad);
    }

    constexpr float margin = 40.0f;
    painter.Rect(margin, margin, 280.0f, 62.0f, Ink);
    painter.Rect(margin, margin, 280.0f, 2.0f, Rule);
    painter.Rect(margin, margin + 8.0f, 3.0f, 44.0f, Mint);
    painter.Text(TEXT("FORMULA FORGE"), margin + 16.0f, margin + 11.0f, 23.0f, White);
    painter.Text(TEXT("TIME TRIAL"), margin + 16.0f, margin + 40.0f, 14.0f, Muted);
    painter.Rect(margin, margin + 63.0f, 280.0f, 30.0f, Ink);
    painter.Text(FString(UTF8_TO_TCHAR(std::string(simulation.circuitName).c_str())).ToUpper(), margin + 16.0f, margin + 71.0f, 14.0f, Muted);
    const FString lapLabel = !trial.running ? TEXT("OUT LAP") : session->LapLimit() > 0 ?
        FString::Printf(TEXT("LAP %02d / %02d"), trial.completedLaps + 1, session->LapLimit()) :
        FString::Printf(TEXT("LAP %02d"), trial.completedLaps + 1);
    painter.Text(lapLabel,
        margin + 264.0f, margin + 69.0f, 17.0f, White, 1.0f);

    const float timingLeft = width - margin - 330.0f;
    const float timingRight = width - margin - 14.0f;
    painter.Rect(timingLeft, margin, 330.0f, 132.0f, Ink);
    painter.Rect(timingLeft, margin, 330.0f, 2.0f, Rule);
    painter.Text(TEXT("CURRENT"), timingLeft + 14.0f, margin + 16.0f, 14.0f, Muted);
    painter.Text(FFTrialHUD::TrialTime(trial.seconds, trial.running), timingRight,
        margin + 9.0f, 28.0f, trial.invalid ? Red : White, 1.0f, 208.0f);
    painter.Rect(timingLeft + 14.0f, margin + 45.0f, 302.0f, 1.0f, Rule);
    painter.Text(TEXT("BEST"), timingLeft + 14.0f, margin + 55.0f, 15.0f, Muted);
    painter.Text(FFTrialHUD::TrialTime(trial.bestSeconds, trial.bestSeconds > 0.0), timingRight,
        margin + 51.0f, 21.0f, trial.bestSeconds > 0.0 ? Mint : Muted, 1.0f);
    const bool lastInvalid = trial.lastSeconds > 0.0 && !trial.lastValid;
    painter.Text(lastInvalid ? TEXT("LAST INVALID") : TEXT("PREVIOUS"),
        timingLeft + 14.0f, margin + 83.0f, 15.0f, lastInvalid ? Red : Muted);
    painter.Text(FFTrialHUD::TrialTime(trial.lastSeconds, trial.lastSeconds > 0.0), timingRight,
        margin + 79.0f, 21.0f, lastInvalid ? Red : White, 1.0f);
    const FLinearColor validityColor = !trial.running ? Amber : trial.invalid ? Red : Mint;
    const FString validity = !trial.running ? TEXT("OUT LAP / NOT TIMING") :
        trial.invalid ? TEXT("LAP INVALID") : TEXT("LAP VALID");
    painter.Rect(timingLeft + 14.0f, margin + 113.0f, 4.0f, 10.0f, validityColor);
    painter.Text(validity, timingLeft + 26.0f, margin + 110.0f, 13.0f, validityColor);

    if (inPitLane) {
        const FLinearColor pitColor = pitOverspeed ? Red : Amber;
        const float pitLeft = width * 0.5f - 164.0f;
        painter.Rect(pitLeft, margin + 40.0f, 328.0f, 65.0f, Ink);
        painter.Rect(pitLeft, margin + 40.0f, 328.0f, 2.0f, pitColor);
        painter.Text(pitOverspeed ? TEXT("PIT LANE / SLOW DOWN") : TEXT("PIT LANE"),
            width * 0.5f, margin + 50.0f, 15.0f, pitColor, 0.5f);
        painter.Text(simulation.PitSpeedLimitKph() > 0.0f ? FString::Printf(TEXT("LIMIT  %d KM/H"),
            FMath::RoundToInt(simulation.PitSpeedLimitKph())) : TEXT("ENTRY / EXIT"),
            width * 0.5f, margin + 75.0f, 21.0f, White, 0.5f);
    }

    static TrackLayoutId mapCircuit = simulation.circuit;
    static TUniquePtr<FFTrialHUD::FTrialHUDMap> cachedMap = MakeUnique<FFTrialHUD::FTrialHUDMap>(simulation);
    if (mapCircuit != simulation.circuit) {
        cachedMap = MakeUnique<FFTrialHUD::FTrialHUDMap>(simulation);
        mapCircuit = simulation.circuit;
    }
    auto& trackMap = *cachedMap;
    const FVector2D mapOrigin(margin + 196.0f, height - margin - 190.0f);
    trackMap.Draw(painter, mapOrigin);
    FVector2D marker = (FVector2D(vehicle.pos.x, -vehicle.pos.y) - trackMap.Centre) * trackMap.UnitsToMap;
    const bool outsideMap = FMath::Abs(marker.X) > 196.0 || FMath::Abs(marker.Y) > 134.0;
    marker.X = FMath::Clamp(marker.X, -196.0, 196.0);
    marker.Y = FMath::Clamp(marker.Y, -134.0, 134.0);
    marker += mapOrigin;
    const FVector2D direction(FMath::Cos(vehicle.heading), -FMath::Sin(vehicle.heading));
    const FVector2D across(-direction.Y, direction.X);
    painter.Triangle(marker + direction * 12.0, marker - direction * 8.0 + across * 8.0,
        marker - direction * 8.0 - across * 8.0, Ink);
    painter.Triangle(marker + direction * 9.0, marker - direction * 5.0 + across * 5.0,
        marker - direction * 5.0 - across * 5.0, trial.invalid ? Red : Mint);
    if (outsideMap) {
        painter.Text(TEXT("OFF MAP"), margin + 196.0f, height - margin - 42.0f, 13.0f, Amber, 0.5f);
    }

    const float telemetryCentre = width * 0.5f;
    const float telemetryTop = height - 218.0f;
    const FVector2D energyCentre(telemetryCentre - 128.0f, telemetryTop + 91.0f);
    const FVector2D speedCentre(telemetryCentre + 128.0f, telemetryTop + 91.0f);
    painter.Rect(telemetryCentre - 60.0f, telemetryTop + 49.0f, 120.0f, 100.0f, Dial);
    painter.Arc(energyCentre, 57.0f, 0.0f, 360.0f, 57.0f, Dial);
    painter.Arc(speedCentre, 57.0f, 0.0f, 360.0f, 57.0f, Dial);
    painter.Arc(energyCentre, 63.0f, 140.0f, 260.0f, 7.0f, Dial);
    painter.Arc(energyCentre, 61.0f, 140.0f, 260.0f, 4.0f, Energy);
    painter.Arc(speedCentre, 61.0f, 140.0f, 260.0f, 2.0f, Rule);
    painter.Text(TEXT("ENERGY"), energyCentre.X, energyCentre.Y - 30.0f, 12.0f, White, 0.5f);
    painter.Text(TEXT("100%"), energyCentre.X, energyCentre.Y - 10.0f, 28.0f, Energy, 0.5f, 98.0f);

    const float normalizedRpm = FMath::Clamp(vehicle.engineRpmNormalized, 0.0f, 1.25f);
    const float rpmRange = FMath::Max(0.001f, 1.0f - simulation.tuning.idleRpmNormalized);
    const float revFill = FMath::Clamp((normalizedRpm - simulation.tuning.idleRpmNormalized) / rpmRange, 0.0f, 1.0f);
    for (int32 light = 0; light < 16; ++light) {
        const FLinearColor lightColor = light < 6 ? Mint : light < 11 ? Red : Violet;
        painter.Rect(telemetryCentre - 67.0f + light * 8.5f, telemetryTop + 36.0f, 6.0f, 5.0f,
            revFill >= (light + 1) / 16.0f ? lightColor : Rule);
    }
    painter.Text(FString::Printf(TEXT("%d RPM"), FMath::RoundToInt(normalizedRpm * simulation.tuning.redlineRpm)),
        speedCentre.X, speedCentre.Y + 23.0f, 13.0f, White, 0.5f, 96.0f);
    const bool reverse = vehicle.forwardSpeed < -1.0f;
    const bool canShiftUp = !reverse && vehicle.gear > 0 &&
        vehicle.gear < static_cast<int32>(simulation.tuning.gearRedlineSpeedRatios.size());
    if (vehicle.shiftRejectTimer > 0.0f) {
        painter.Text(TEXT("SHIFT BLOCKED"), telemetryCentre, telemetryTop + 9.0f, 13.0f, Amber, 0.5f);
    } else if (vehicle.shiftTimer > 0.0f) {
        painter.Text(TEXT("SHIFTING"), telemetryCentre, telemetryTop + 9.0f, 13.0f, Violet, 0.5f);
    } else if (normalizedRpm >= simulation.tuning.automaticUpshiftRpm) {
        painter.Text(canShiftUp ? (pawn->Automatic ? TEXT("SHIFT POINT") : TEXT("SHIFT UP")) : TEXT("HIGH RPM"),
            telemetryCentre, telemetryTop + 9.0f, 13.0f, Violet, 0.5f);
    }
    const FString gear = reverse ? TEXT("R") : vehicle.gear == 0 ? TEXT("N") : FString::FromInt(vehicle.gear);
    painter.Text(gear, telemetryCentre, telemetryTop + 55.0f, 70.0f, White, 0.5f, 74.0f);
    painter.Text(pawn->Automatic ? TEXT("AUTO") : TEXT("MANUAL"), telemetryCentre,
        telemetryTop + 134.0f, 12.0f, White, 0.5f);
    const int32 speedKph = FMath::RoundToInt(FMath::Abs(vehicle.forwardSpeed) / 17.0f * 3.6f);
    painter.Text(TEXT("KM/H"), speedCentre.X, speedCentre.Y - 35.0f, 12.0f, White, 0.5f);
    painter.Text(FString::FromInt(speedKph), speedCentre.X, speedCentre.Y - 18.0f,
        34.0f, pitOverspeed ? Red : White, 0.5f, 98.0f);
    const float throttle = FMath::Clamp(simulation.appliedControl.throttle, 0.0f, 1.0f);
    const float brake = FMath::Clamp(simulation.appliedControl.brake, 0.0f, 1.0f);
    painter.Rect(telemetryCentre - 53.0f, telemetryTop + 72.0f, 3.0f, 47.0f, Rule);
    painter.Rect(telemetryCentre + 50.0f, telemetryTop + 72.0f, 3.0f, 47.0f, Rule);
    if (throttle > 0.0f) {
        painter.Rect(telemetryCentre + 50.0f, telemetryTop + 119.0f - 47.0f * throttle,
            3.0f, 47.0f * throttle, Mint);
    }
    if (brake > 0.0f) {
        painter.Rect(telemetryCentre - 53.0f, telemetryTop + 119.0f - 47.0f * brake,
            3.0f, 47.0f * brake, Red);
    }
    painter.Text(TEXT("DEPLOYING"), telemetryCentre, telemetryTop + 159.0f, 13.0f, Energy, 0.5f);
    painter.Rect(telemetryCentre - 70.0f, telemetryTop + 181.0f, 140.0f, 4.0f, Energy);

    const FString recording = pawn->RecordingStatus();
    if (!recording.IsEmpty()) {
        painter.Rect(margin, margin + 104.0f, 280.0f, 28.0f, Ink);
        painter.Text(recording, margin + 12.0f, margin + 111.0f, 13.0f, Amber, 0.0f, 256.0f);
    }
    painter.Text(gamepad ? TEXT("START  PAUSE") : TEXT("ESC / P  PAUSE"), margin, height - 25, 12, Muted);

}

void AFormulaTrialHUD::NotifyHitBoxClick(FName boxName) {
    const FString action = boxName.ToString();
    if (action.StartsWith(TEXT("Action_"))) GetGameInstance<UFFSession>()->Activate(FCString::Atoi(*action.Mid(7)));
}
