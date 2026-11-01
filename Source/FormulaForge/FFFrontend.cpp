#include "FFFrontend.h"
#include "FFSession.h"
#include "FFTrialHUD.hpp"
#include "track_catalog.hpp"
#include "Engine/Canvas.h"
#include "GameFramework/HUD.h"

namespace {
const FLinearColor Background(.004f, .005f, .008f, .94f);
const FLinearColor Card(.025f, .026f, .032f, .88f);
const FLinearColor White(.92f, .96f, 1.0f);
const FLinearColor Muted(.42f, .53f, .64f);
const FLinearColor Accent(.88f, .018f, .035f);
const FLinearColor Rule(.16f, .16f, .18f);

void Button(AHUD& hud, const FFTrialHUD::FTrialHUDPainter& painter, UFFSession& session,
    int32 action, const FString& text, float left, float top, float width, float height, bool primary = false) {
    float mouseX = -1.0f;
    float mouseY = -1.0f;
    hud.GetOwningPlayerController()->GetMousePosition(mouseX, mouseY);
    const FVector2D mouse(mouseX / painter.Scale, mouseY / painter.Scale);
    const bool hovered = mouse.X >= left && mouse.X <= left + width && mouse.Y >= top && mouse.Y <= top + height;
    painter.Rect(left, top, width, height, primary ? Accent : Card);
    const bool focused = session.Screen == EFFScreen::Setup ? action == 5 : session.Focus == action;
    if (focused || hovered) {
        for (float y : {top, top + height - 2}) painter.Rect(left, y, width, 2, White);
        for (float x : {left, left + width - 2}) painter.Rect(x, top, 2, height, White);
    }
    painter.Text(text, left + width * .5f, top + (height - 23) * .5f, 23, White, .5f, width - 24);
    hud.AddHitBox(painter.Pixel({left, top}), painter.Pixel({width, height}),
        FName(*FString::Printf(TEXT("Action_%d"), action)), true);
}

void Outline(const FFTrialHUD::FTrialHUDPainter& painter, const TrackCatalogEntry& track,
    FVector2D origin, FVector2D size, FLinearColor color) {
    FVector2D minimum(TNumericLimits<double>::Max(), TNumericLimits<double>::Max());
    FVector2D maximum(-TNumericLimits<double>::Max(), -TNumericLimits<double>::Max());
    for (const auto& point : track.centerline) {
        minimum.X = FMath::Min(minimum.X, double(point.x));
        minimum.Y = FMath::Min(minimum.Y, double(point.y));
        maximum.X = FMath::Max(maximum.X, double(point.x));
        maximum.Y = FMath::Max(maximum.Y, double(point.y));
    }
    const double scale = FMath::Min(size.X / FMath::Max(1.0, maximum.X - minimum.X), size.Y / FMath::Max(1.0, maximum.Y - minimum.Y));
    const auto screen = [&](const TrackControlPoint& point) {
        const FVector2D p(point.x, -point.y);
        return origin + size * .5 + (p - FVector2D((minimum.X + maximum.X) * .5, -(minimum.Y + maximum.Y) * .5)) * scale;
    };
    const size_t stride = FMath::Max(size_t(1), track.centerline.size() / 180);
    for (size_t index = 0; index < track.centerline.size(); index += stride) {
        const size_t next = index + stride < track.centerline.size() ? index + stride : 0;
        painter.Line(screen(track.centerline[index]), screen(track.centerline[next]), 4, color);
    }
    painter.Arc(screen(track.centerline.front()), 7, 0, 360, 7, White);
}
}

void DrawFormulaFrontend(AHUD& hud, UCanvas& canvas, UFFSession& session) {
    const float scale = FMath::Min(canvas.SizeX / 1920.0f, canvas.SizeY / 1080.0f);
    const float width = canvas.SizeX / scale;
    const float height = canvas.SizeY / scale;
    const float left = (width - 1680) * .5f;
    const FFTrialHUD::FTrialHUDPainter painter{canvas, scale};
    if (session.Screen != EFFScreen::Setup) painter.Rect(0, 0, width, height, Background);
    else {
        for (int32 band = 0; band < 16; ++band) {
            const float alpha = .68f * (1.0f - band / 16.0f);
            painter.Rect(0, band * 14, width, 14, FLinearColor(0, 0, 0, alpha));
            painter.Rect(0, height - (band + 1) * 14, width, 14, FLinearColor(0, 0, 0, alpha));
        }
    }
    painter.Text(TEXT("FORMULA"), left, 45, 20, White);
    painter.Text(TEXT("FORGE"), left, 70, 54, White);
    painter.Rect(left, 139, 152, 4, Accent);
    painter.Rect(left + 160, 139, 40, 4, FLinearColor(.4f, .01f, .02f));
    painter.Text(TEXT("TIME TRIAL  /  SOLO SESSION"), left + 1680, 58, 18, White, 1);
    painter.Rect(0, height - 92, width, 92, FLinearColor(0, 0, 0, .88f));
    painter.Rect(0, height - 92, width, 1, Accent);
    if (session.Screen == EFFScreen::Setup) {
        painter.Text(TEXT("KEYBOARD   A / D OR LEFT / RIGHT  CIRCUIT    W / S OR UP / DOWN  LAPS    ENTER / SPACE  DRIVE    ESC  QUIT"), left, height - 72, 16, White);
        painter.Text(TEXT("CONTROLLER   D-PAD / LEFT STICK  SELECT    A  DRIVE"), left, height - 39, 16, Muted);
    } else {
        painter.Text(TEXT("KEYBOARD   ARROWS / WASD  NAVIGATE    ENTER / SPACE  SELECT    ESC  BACK"), left, height - 72, 16, White);
        painter.Text(TEXT("CONTROLLER   D-PAD / LEFT STICK  NAVIGATE    A  SELECT    B  BACK"), left, height - 39, 16, Muted);
    }
    if (session.Screen == EFFScreen::Loading || hud.GetWorld()->GetTimeSeconds() < .4f) {
        painter.Text(TEXT("LOADING"), width * .5f, height * .5f - 65, 19, Accent, .5f);
        painter.Text(session.CircuitTitle().ToUpper(), width * .5f, height * .5f - 16, 58, White, .5f);
        painter.Text(session.LapLabel(), width * .5f, height * .5f + 70, 20, Muted, .5f);
        return;
    }
    if (session.Screen == EFFScreen::Setup) {
        const float panelX = left + 1080;
        painter.Rect(panelX, 190, 600, 724, Background);
        painter.Rect(panelX, 190, 600, 4, Accent);
        painter.Text(TEXT("CIRCUIT"), panelX + 28, 214, 15, Muted);
        const auto tracks = trackCatalog();
        for (int32 index = 0; index < 3; ++index) {
            const float x = panelX + 24 + index * 186;
            Button(hud, painter, session, index, UTF8_TO_TCHAR(tracks[index].displayName.data()), x, 253, 180, 50,
                session.CircuitIndex == index);
        }
        const auto& track = tracks[session.CircuitIndex];
        painter.Text(UTF8_TO_TCHAR(track.country.data()), panelX + 30, 333, 17, Muted);
        painter.Text(session.CircuitTitle().ToUpper(), panelX + 30, 365, 43, White);
        Outline(painter, track, {panelX + 130, 436}, {340, 204}, White);
        painter.Text(FString::Printf(TEXT("%.3f KM   /   %d CORNERS"), track.targetLengthMeters / 1000, track.turnCount), panelX + 300, 672, 18, Muted, .5f);
        painter.Rect(panelX + 28, 715, 544, 1, Rule);
        painter.Text(TEXT("TIMED LAPS"), panelX + 28, 736, 16, Muted);
        Button(hud, painter, session, 3, TEXT("-"), panelX + 218, 727, 48, 48);
        painter.Text(session.LapLabel(), panelX + 398, 742, 21, White, .5f);
        Button(hud, painter, session, 4, TEXT("+"), panelX + 528, 727, 48, 48);
        painter.Text(TEXT("Out-lap excluded. Valid laps set your best time."), panelX + 28, 792, 16, Muted);
        Button(hud, painter, session, 5, TEXT("DRIVE"), panelX + 24, 832, 552, 62, true);
        painter.Text(TEXT("YOUR CAR"), left, height - 274, 17, Muted);
        painter.Text(TEXT("FERRARI"), left, height - 242, 66, White);
        painter.Text(TEXT("W / S  THROTTLE / BRAKE    A / D  STEER    Q / E  SHIFT"), left, height - 150, 16, White);
        Button(hud, painter, session, 6, TEXT("QUIT"), left + 1550, height - 71, 130, 49);
        return;
    }
    const bool paused = session.Screen == EFFScreen::Paused;
    painter.Text(paused ? TEXT("Session paused.") : TEXT("Session complete."), left, 170, 58, White);
    painter.Text(session.CircuitTitle().ToUpper() + TEXT("  /  ") + session.LapLabel(), left, 253, 21, Accent);
    double best = 0;
    for (const auto& lap : session.Laps) if (lap.Valid && (best == 0 || lap.Seconds < best)) best = lap.Seconds;
    painter.Text(TEXT("SESSION BEST"), left, 340, 18, Muted);
    painter.Text(FFTrialHUD::TrialTime(best, best > 0), left, 382, 62, White);
    painter.Text(FString::Printf(TEXT("%d TIMED %s COMPLETED"), session.Laps.Num(), session.Laps.Num() == 1 ? TEXT("LAP") : TEXT("LAPS")), left, 470, 19, Muted);
    const int32 first = FMath::Max(0, session.Laps.Num() - 10);
    for (int32 index = first; index < session.Laps.Num(); ++index) {
        const auto& lap = session.Laps[index];
        const float y = 340 + (index - first) * 44;
        painter.Text(FString::Printf(TEXT("LAP %02d"), index + 1), left + 840, y, 20, Muted);
        painter.Text(FFTrialHUD::TrialTime(lap.Seconds, true), left + 1120, y, 23, White);
        painter.Text(lap.Valid ? TEXT("VALID") : TEXT("INVALID"), left + 1500, y, 18, lap.Valid ? Accent : Muted);
        painter.Rect(left + 840, y + 36, 840, 1, Rule);
    }
    if (paused) {
        Button(hud, painter, session, 0, TEXT("RESUME"), left, 820, 360, 76, true);
        Button(hud, painter, session, 1, TEXT("RESTART SESSION"), left + 400, 820, 400, 76);
        Button(hud, painter, session, 2, TEXT("CHANGE CIRCUIT"), left + 840, 820, 400, 76);
        Button(hud, painter, session, 3, TEXT("QUIT GAME"), left + 1280, 820, 400, 76);
    } else {
        Button(hud, painter, session, 0, TEXT("DRIVE AGAIN"), left, 820, 500, 76, true);
        Button(hud, painter, session, 1, TEXT("CHANGE CIRCUIT"), left + 590, 820, 500, 76);
        Button(hud, painter, session, 2, TEXT("QUIT GAME"), left + 1180, 820, 500, 76);
    }
}
