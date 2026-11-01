#pragma once

#include "CoreMinimal.h"
#include "CanvasItem.h"

#include <array>

class APlayerController;
class FFSimulation;
class UCanvas;

namespace FFTrialHUD {
FString TrialTime(double seconds, bool available);
bool GamepadActive(const APlayerController& player, bool previous);

struct FTrialHUDTextItem : FCanvasTextItem {
    using FCanvasTextItem::FCanvasTextItem;
    using FCanvasTextItem::GetTextSize;
};

struct FTrialHUDPainter {
    UCanvas& Canvas;
    float Scale;

    FVector2D Pixel(FVector2D position) const;
    void Rect(float left, float top, float width, float height, FLinearColor color) const;
    void Triangle(FVector2D first, FVector2D second, FVector2D third, FLinearColor color) const;
    void Line(FVector2D start, FVector2D end, float thickness, FLinearColor color) const;
    void Arc(FVector2D centre, float radius, float startDegrees, float sweepDegrees,
        float thickness, FLinearColor color) const;
    void Panel(float left, float top, float width, float height) const;
    void Text(const FString& text, float left, float top, float height, FLinearColor color,
        float alignment = 0.0f, float maxWidth = 0.0f) const;
};

struct FTrialHUDMap {
    static constexpr int32 SampleCount = 256;
    std::array<FVector2D, SampleCount> Points;
    TArray<FVector2D> PitPoints;
    FVector2D Centre;
    float UnitsToMap = 1.0f;
    FVector2D CachedOrigin = FVector2D(-1.0, -1.0);
    float CachedScale = 0.0f;
    FCanvasTriangleItem Geometry;

    explicit FTrialHUDMap(const FFSimulation& simulation);
    void Draw(const FTrialHUDPainter& painter, FVector2D origin);
    void AddTriangle(FVector2D first, FVector2D second, FVector2D third, FLinearColor color);
};
}
