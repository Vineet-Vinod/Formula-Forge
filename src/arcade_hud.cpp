#include "arcade_hud.hpp"

#include <raylib.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <string>
#include <string_view>

namespace harbor::ui {
namespace {

constexpr Color kInk = {15, 30, 34, 242};
constexpr Color kInkSoft = {24, 47, 50, 224};
constexpr Color kPaper = {244, 247, 232, 255};
constexpr Color kPaperMuted = {186, 207, 194, 255};
constexpr Color kSun = {255, 205, 67, 255};
constexpr Color kCoral = {238, 79, 67, 255};
constexpr Color kAqua = {65, 203, 205, 255};
constexpr Color kLeaf = {92, 190, 113, 255};
constexpr Color kOutline = {105, 143, 139, 190};

struct Metrics {
    float width = 1280.0f;
    float height = 720.0f;
    float scale = 1.0f;
    float margin = 24.0f;
};

Metrics metrics() {
    Metrics result;
    result.width = static_cast<float>(std::max(1, GetScreenWidth()));
    result.height = static_cast<float>(std::max(1, GetScreenHeight()));
    result.scale = std::clamp(result.height / 720.0f, 0.75f, 1.75f);
    result.margin = 24.0f * result.scale;
    return result;
}

float clamp01(float value) {
    return std::clamp(value, 0.0f, 1.0f);
}

Rectangle inset(Rectangle rectangle, float amount) {
    return {rectangle.x + amount, rectangle.y + amount, std::max(0.0f, rectangle.width - amount * 2.0f),
            std::max(0.0f, rectangle.height - amount * 2.0f)};
}

void drawPanel(Rectangle bounds, Color fill, Color accent, float scale) {
    DrawRectangleRec(bounds, fill);
    DrawRectangleRec({bounds.x, bounds.y, 5.0f * scale, bounds.height}, accent);
    DrawLineEx({bounds.x, bounds.y + bounds.height}, {bounds.x + bounds.width, bounds.y + bounds.height}, 1.0f * scale,
               Fade(kOutline, 0.72f));
    DrawTriangle({bounds.x + bounds.width - 18.0f * scale, bounds.y}, {bounds.x + bounds.width, bounds.y},
                 {bounds.x + bounds.width, bounds.y + 18.0f * scale}, Fade(accent, 0.80f));
}

float fittedFontSize(std::string_view text, float preferred, float minimum, float maximumWidth) {
    const Font font = GetFontDefault();
    float size = preferred;
    const std::string owned(text);
    while (size > minimum && MeasureTextEx(font, owned.c_str(), size, 0.0f).x > maximumWidth) {
        size -= 1.0f;
    }
    const float minimumWidth = MeasureTextEx(font, owned.c_str(), minimum, 0.0f).x;
    if (minimumWidth > maximumWidth && minimumWidth > 0.0f) {
        size = std::max(6.0f, minimum * maximumWidth / minimumWidth);
    }
    return std::max(6.0f, size);
}

void drawText(std::string_view text, Vector2 position, float fontSize, Color color) {
    const std::string owned(text);
    DrawTextEx(GetFontDefault(), owned.c_str(), position, fontSize, 0.0f, color);
}

void drawFittedText(std::string_view text, Rectangle bounds, float preferred, float minimum, Color color) {
    const float fontSize = fittedFontSize(text, preferred, minimum, bounds.width);
    drawText(text, {bounds.x, bounds.y + (bounds.height - fontSize) * 0.5f}, fontSize, color);
}

void drawCenteredText(std::string_view text, Vector2 center, float fontSize, Color color) {
    const std::string owned(text);
    const Vector2 size = MeasureTextEx(GetFontDefault(), owned.c_str(), fontSize, 0.0f);
    DrawTextEx(GetFontDefault(), owned.c_str(), {center.x - size.x * 0.5f, center.y - size.y * 0.5f}, fontSize, 0.0f, color);
}

std::string formatTime(float seconds) {
    seconds = std::max(0.0f, seconds);
    const int totalHundredths = static_cast<int>(seconds * 100.0f);
    const int minutes = totalHundredths / 6000;
    const int wholeSeconds = (totalHundredths / 100) % 60;
    const int hundredths = totalHundredths % 100;
    std::array<char, 24> buffer{};
    std::snprintf(buffer.data(), buffer.size(), "%02d:%02d.%02d", minutes, wholeSeconds, hundredths);
    return buffer.data();
}

std::string lapText(int currentLap, int totalLaps) {
    std::array<char, 32> buffer{};
    if (totalLaps <= 0) {
        std::snprintf(buffer.data(), buffer.size(), "LAP %d / INF", std::max(1, currentLap));
    } else {
        std::snprintf(buffer.data(), buffer.size(), "LAP %d / %d", std::clamp(currentLap, 1, totalLaps), totalLaps);
    }
    return buffer.data();
}

void drawConnectionBanner(const Metrics& m) {
    const float height = 42.0f * m.scale;
    const Rectangle banner{0.0f, m.height - height, m.width, height};
    DrawRectangleRec(banner, Fade(kCoral, 0.96f));
    DrawRectangleRec({0.0f, banner.y, banner.width, 3.0f * m.scale}, kSun);
    drawCenteredText("CONTROLLER DISCONNECTED", {m.width * 0.5f, banner.y + banner.height * 0.5f}, 19.0f * m.scale, kPaper);
}

void drawStatRow(const char* label, float value, Rectangle bounds, Color color, float scale) {
    drawText(label, {bounds.x, bounds.y}, 15.0f * scale, kPaperMuted);
    const float labelWidth = 102.0f * scale;
    const Rectangle rail{bounds.x + labelWidth, bounds.y + 2.0f * scale, bounds.width - labelWidth, 12.0f * scale};
    DrawRectangleRec(rail, Color{8, 22, 25, 210});
    const Rectangle fill = inset(rail, 2.0f * scale);
    DrawRectangleRec({fill.x, fill.y, fill.width * clamp01(value), fill.height}, color);
    for (int tick = 1; tick < 5; ++tick) {
        const float x = fill.x + fill.width * static_cast<float>(tick) / 5.0f;
        DrawLineEx({x, fill.y}, {x, fill.y + fill.height}, 1.0f * scale, Fade(kInk, 0.65f));
    }
}

void drawRaceProgress(const RaceHudViewModel& viewModel, const Metrics& m) {
    const float width = 440.0f * m.scale;
    const Rectangle panel{(m.width - width) * 0.5f, m.margin, width, 52.0f * m.scale};
    DrawRectangleRec(panel, Fade(kInk, 0.78f));

    const std::string time = formatTime(viewModel.raceTimeSeconds);
    drawCenteredText(time, {panel.x + panel.width * 0.5f, panel.y + 13.0f * m.scale}, 16.0f * m.scale, kPaper);

    const Rectangle rail{panel.x + 24.0f * m.scale, panel.y + 34.0f * m.scale, panel.width - 48.0f * m.scale, 6.0f * m.scale};
    DrawRectangleRec(rail, Color{7, 18, 21, 240});
    DrawRectangleRec({rail.x, rail.y, rail.width * clamp01(viewModel.raceProgress), rail.height}, kSun);

    const int count = std::clamp(viewModel.racerProgressCount, 0, kMaxHudRacers);
    for (int index = 0; index < count; ++index) {
        const float progress = clamp01(viewModel.racerProgress[static_cast<size_t>(index)]);
        const Vector2 marker{rail.x + progress * rail.width, rail.y + rail.height * 0.5f};
        const bool player = index == viewModel.playerProgressIndex;
        DrawCircleV(marker, (player ? 5.0f : 3.0f) * m.scale, player ? kSun : kPaperMuted);
        if (player) {
            DrawCircleLines(static_cast<int>(marker.x), static_cast<int>(marker.y), 7.0f * m.scale, kPaper);
        }
    }
}

void drawPlacePanel(const RaceHudViewModel& viewModel, const Metrics& m) {
    const Rectangle panel{m.margin, m.margin, 184.0f * m.scale, 82.0f * m.scale};
    DrawRectangleRec(panel, Fade(kInk, 0.76f));
    drawText("PLACE", {panel.x + 13.0f * m.scale, panel.y + 10.0f * m.scale}, 15.0f * m.scale, kPaper);
    std::array<char, 20> place{};
    std::snprintf(place.data(), place.size(), "%d/%d", std::clamp(viewModel.position, 1, std::max(1, viewModel.racerCount)),
                  std::max(1, viewModel.racerCount));
    drawText(place.data(), {panel.x + 69.0f * m.scale, panel.y + 24.0f * m.scale}, 38.0f * m.scale, kPaper);
}

void drawLapPanel(const RaceHudViewModel& viewModel, const Metrics& m) {
    const float width = 184.0f * m.scale;
    const Rectangle panel{m.width - m.margin - width, m.margin, width, 82.0f * m.scale};
    DrawRectangleRec(panel, Fade(kInk, 0.76f));
    drawText("LAP", {panel.x + 15.0f * m.scale, panel.y + 10.0f * m.scale}, 15.0f * m.scale, kPaper);
    const std::string lap = lapText(viewModel.currentLap, viewModel.totalLaps);
    drawFittedText(lap.substr(4), {panel.x + 55.0f * m.scale, panel.y + 24.0f * m.scale, panel.width - 66.0f * m.scale,
                                  42.0f * m.scale},
                   34.0f * m.scale, 18.0f * m.scale, kPaper);
}

void drawRaceAlert(const RaceHudViewModel& viewModel, const Metrics& m) {
    if (!viewModel.wrongWay && !viewModel.finished) {
        return;
    }
    const bool pulseVisible = std::fmod(std::max(0.0f, viewModel.presentationTimeSeconds), 0.40f) < 0.28f;
    if (viewModel.wrongWay && !pulseVisible) {
        return;
    }

    const Rectangle banner{m.width * 0.5f - 190.0f * m.scale, 132.0f * m.scale, 380.0f * m.scale, 62.0f * m.scale};
    DrawRectangleRec(banner, viewModel.finished ? Fade(kInk, 0.96f) : Fade(kCoral, 0.95f));
    DrawRectangleLinesEx(banner, 3.0f * m.scale, kSun);
    drawCenteredText(viewModel.finished ? "FINISH!" : "WRONG WAY", {banner.x + banner.width * 0.5f, banner.y + banner.height * 0.5f},
                     30.0f * m.scale, viewModel.finished ? kSun : kPaper);
}

}  // namespace

void DrawRaceHud(const RaceHudViewModel& viewModel) {
    const Metrics m = metrics();
    drawPlacePanel(viewModel, m);
    drawRaceProgress(viewModel, m);
    drawLapPanel(viewModel, m);
    drawRaceAlert(viewModel, m);
    if (!viewModel.controllerConnected) {
        drawConnectionBanner(m);
    }
}

void DrawGarageHud(const GarageHudViewModel& viewModel) {
    const Metrics m = metrics();
    const float pulse = 0.84f + 0.16f * std::sin(viewModel.presentationTimeSeconds * 4.0f);

    const Rectangle vehiclePanel{m.margin, m.margin, 430.0f * m.scale, 104.0f * m.scale};
    drawPanel(vehiclePanel, kInk, kSun, m.scale);
    drawText("GARAGE", {vehiclePanel.x + 24.0f * m.scale, vehiclePanel.y + 12.0f * m.scale}, 15.0f * m.scale, kAqua);
    drawFittedText(viewModel.vehicleName.empty() ? "SELECT VEHICLE" : viewModel.vehicleName,
                   {vehiclePanel.x + 24.0f * m.scale, vehiclePanel.y + 35.0f * m.scale, vehiclePanel.width - 48.0f * m.scale,
                    37.0f * m.scale},
                   30.0f * m.scale, 17.0f * m.scale, kPaper);

    std::array<char, 32> vehicleIndex{};
    std::snprintf(vehicleIndex.data(), vehicleIndex.size(), "<  %02d / %02d  >", std::clamp(viewModel.vehicleIndex + 1, 1, std::max(1, viewModel.vehicleCount)),
                  std::max(1, viewModel.vehicleCount));
    drawText(vehicleIndex.data(), {vehiclePanel.x + 24.0f * m.scale, vehiclePanel.y + 80.0f * m.scale}, 15.0f * m.scale,
             kPaperMuted);
    if (!viewModel.vehicleClass.empty()) {
        const Rectangle classBounds{vehiclePanel.x + 220.0f * m.scale, vehiclePanel.y + 76.0f * m.scale,
                                    vehiclePanel.width - 244.0f * m.scale, 23.0f * m.scale};
        const float classSize = fittedFontSize(viewModel.vehicleClass, 15.0f * m.scale, 10.0f * m.scale, classBounds.width);
        const float classWidth = MeasureTextEx(GetFontDefault(), viewModel.vehicleClass.c_str(), classSize, 0.0f).x;
        drawText(viewModel.vehicleClass,
                 {classBounds.x + classBounds.width - classWidth, classBounds.y + (classBounds.height - classSize) * 0.5f}, classSize,
                 kSun);
    }

    const float driverWidth = 286.0f * m.scale;
    const Rectangle driverPanel{m.width - m.margin - driverWidth, m.margin, driverWidth, 86.0f * m.scale};
    drawPanel(driverPanel, kInk, kCoral, m.scale);
    drawText("DRIVER", {driverPanel.x + 22.0f * m.scale, driverPanel.y + 12.0f * m.scale}, 14.0f * m.scale, kPaperMuted);
    drawFittedText(viewModel.driverName.empty() ? "SELECT DRIVER" : viewModel.driverName,
                   {driverPanel.x + 22.0f * m.scale, driverPanel.y + 32.0f * m.scale, driverPanel.width - 44.0f * m.scale,
                    31.0f * m.scale},
                   25.0f * m.scale, 15.0f * m.scale, kPaper);
    std::array<char, 32> driverIndex{};
    std::snprintf(driverIndex.data(), driverIndex.size(), "<  %02d / %02d  >", std::clamp(viewModel.driverIndex + 1, 1, std::max(1, viewModel.driverCount)),
                  std::max(1, viewModel.driverCount));
    drawText(driverIndex.data(), {driverPanel.x + driverPanel.width - 106.0f * m.scale, driverPanel.y + 64.0f * m.scale},
             12.0f * m.scale, kPaperMuted);

    const Rectangle statsPanel{m.margin, m.height - 248.0f * m.scale, 330.0f * m.scale, 172.0f * m.scale};
    drawPanel(statsPanel, kInkSoft, kLeaf, m.scale);
    drawText("TUNE", {statsPanel.x + 20.0f * m.scale, statsPanel.y + 14.0f * m.scale}, 16.0f * m.scale, kPaper);
    const float rowX = statsPanel.x + 20.0f * m.scale;
    const float rowWidth = statsPanel.width - 40.0f * m.scale;
    drawStatRow("SPEED", viewModel.stats.speed, {rowX, statsPanel.y + 45.0f * m.scale, rowWidth, 16.0f * m.scale}, kCoral, m.scale);
    drawStatRow("ACCEL", viewModel.stats.acceleration, {rowX, statsPanel.y + 73.0f * m.scale, rowWidth, 16.0f * m.scale}, kSun,
                m.scale);
    drawStatRow("HANDLING", viewModel.stats.handling, {rowX, statsPanel.y + 101.0f * m.scale, rowWidth, 16.0f * m.scale}, kAqua,
                m.scale);
    drawStatRow("STRENGTH", viewModel.stats.strength, {rowX, statsPanel.y + 129.0f * m.scale, rowWidth, 16.0f * m.scale}, kLeaf,
                m.scale);

    if (!viewModel.eventName.empty()) {
        const float eventWidth = std::min(350.0f * m.scale, m.width - 2.0f * m.margin);
        const Rectangle eventBand{(m.width - eventWidth) * 0.5f, m.margin, eventWidth, 44.0f * m.scale};
        DrawRectangleRec(eventBand, Fade(kInk, 0.90f));
        drawFittedText(viewModel.eventName, inset(eventBand, 10.0f * m.scale), 18.0f * m.scale, 12.0f * m.scale, kPaper);
    }

    const int lapCount = std::clamp(viewModel.lapOptionCount, 0, static_cast<int>(viewModel.lapOptions.size()));
    const float segmentWidth = 58.0f * m.scale;
    const float gap = 6.0f * m.scale;
    const float lapsWidth = std::max(1, lapCount) * segmentWidth + std::max(0, lapCount - 1) * gap + 94.0f * m.scale;
    const Rectangle lapsPanel{(m.width - lapsWidth) * 0.5f, m.height - 68.0f * m.scale, lapsWidth, 48.0f * m.scale};
    DrawRectangleRec(lapsPanel, Fade(kInk, 0.94f));
    drawText("LAPS", {lapsPanel.x + 16.0f * m.scale, lapsPanel.y + 16.0f * m.scale}, 14.0f * m.scale, kPaperMuted);
    float segmentX = lapsPanel.x + 82.0f * m.scale;
    for (int index = 0; index < lapCount; ++index) {
        const Rectangle segment{segmentX, lapsPanel.y + 7.0f * m.scale, segmentWidth, 34.0f * m.scale};
        const bool selected = index == std::clamp(viewModel.selectedLapOption, 0, std::max(0, lapCount - 1));
        DrawRectangleRec(segment, selected ? kSun : Color{32, 61, 63, 235});
        DrawRectangleLinesEx(segment, selected ? 2.0f * m.scale : 1.0f * m.scale, selected ? kPaper : kOutline);
        std::array<char, 16> laps{};
        if (viewModel.lapOptions[static_cast<size_t>(index)] <= 0) {
            std::snprintf(laps.data(), laps.size(), "INF");
        } else {
            std::snprintf(laps.data(), laps.size(), "%d", viewModel.lapOptions[static_cast<size_t>(index)]);
        }
        drawCenteredText(laps.data(), {segment.x + segment.width * 0.5f, segment.y + segment.height * 0.5f}, 15.0f * m.scale,
                         selected ? kInk : kPaper);
        segmentX += segmentWidth + gap;
    }

    const float startWidth = 210.0f * m.scale;
    const Rectangle startPanel{m.width - m.margin - startWidth, m.height - 86.0f * m.scale, startWidth, 58.0f * m.scale};
    const bool enabled = viewModel.canStart && viewModel.controllerConnected;
    const Color startColor = enabled ? Fade(kSun, pulse) : Color{87, 98, 91, 235};
    DrawRectangleRec(startPanel, startColor);
    DrawTriangle({startPanel.x + 25.0f * m.scale, startPanel.y + 17.0f * m.scale},
                 {startPanel.x + 25.0f * m.scale, startPanel.y + 41.0f * m.scale},
                 {startPanel.x + 46.0f * m.scale, startPanel.y + 29.0f * m.scale}, enabled ? kInk : kPaperMuted);
    drawText("RACE", {startPanel.x + 65.0f * m.scale, startPanel.y + 17.0f * m.scale}, 25.0f * m.scale,
             enabled ? kInk : kPaperMuted);

    if (!viewModel.controllerConnected) {
        drawConnectionBanner(m);
    }
}

void DrawCountdownHud(const CountdownHudViewModel& viewModel) {
    if (!viewModel.visible) {
        return;
    }

    const Metrics m = metrics();
    const bool go = viewModel.secondsRemaining <= 0.0f;
    const float positiveTime = std::clamp(viewModel.secondsRemaining, 0.0f, 9.0f);
    const int count = std::max(1, static_cast<int>(std::ceil(positiveTime)));
    const float intervalProgress = go ? 1.0f : 1.0f - (positiveTime - std::floor(positiveTime));
    const float pulse = 1.0f + 0.10f * std::sin(clamp01(intervalProgress) * PI);
    const Vector2 center{m.width * 0.5f, m.height * 0.40f};
    const float radius = 74.0f * m.scale * pulse;

    DrawCircleV(center, radius, Fade(kInk, 0.86f));
    DrawRing(center, radius - 6.0f * m.scale, radius, -90.0f, -90.0f + 360.0f * clamp01(intervalProgress), 64,
             go ? kAqua : kSun);
    DrawCircleLines(static_cast<int>(center.x), static_cast<int>(center.y), radius - 15.0f * m.scale, Fade(kPaper, 0.30f));

    std::array<char, 16> text{};
    if (go) {
        std::snprintf(text.data(), text.size(), "GO!");
    } else {
        std::snprintf(text.data(), text.size(), "%d", count);
    }
    drawCenteredText(text.data(), center, (go ? 47.0f : 62.0f) * m.scale, go ? kAqua : kPaper);
}

void DrawPauseHud(const PauseHudViewModel& viewModel) {
    if (!viewModel.visible) {
        return;
    }

    const Metrics m = metrics();
    DrawRectangle(0, 0, static_cast<int>(m.width), static_cast<int>(m.height), Fade(BLACK, 0.60f));

    struct ActionEntry {
        PauseAction action;
        const char* label;
        bool visible;
    };
    const std::array<ActionEntry, 4> actions = {{{PauseAction::Resume, "RESUME", true},
                                                 {PauseAction::Restart, "RESTART", viewModel.showRestart},
                                                 {PauseAction::Garage, "GARAGE", viewModel.showGarage},
                                                 {PauseAction::Quit, "QUIT", viewModel.showQuit}}};
    const int visibleActions = static_cast<int>(std::count_if(actions.begin(), actions.end(), [](const ActionEntry& entry) {
        return entry.visible;
    }));
    const bool selectedActionVisible = std::any_of(actions.begin(), actions.end(), [&](const ActionEntry& entry) {
        return entry.visible && entry.action == viewModel.selectedAction;
    });
    const PauseAction selectedAction = selectedActionVisible ? viewModel.selectedAction : PauseAction::Resume;

    const float panelWidth = 430.0f * m.scale;
    const float panelHeight = (190.0f + static_cast<float>(visibleActions) * 48.0f) * m.scale;
    const Rectangle panel{(m.width - panelWidth) * 0.5f, (m.height - panelHeight) * 0.5f, panelWidth, panelHeight};
    drawPanel(panel, Color{14, 31, 34, 252}, kSun, m.scale);
    drawCenteredText("PAUSED", {panel.x + panel.width * 0.5f, panel.y + 42.0f * m.scale}, 34.0f * m.scale, kSun);

    if (!viewModel.eventName.empty()) {
        drawFittedText(viewModel.eventName,
                       {panel.x + 34.0f * m.scale, panel.y + 72.0f * m.scale, panel.width - 68.0f * m.scale, 25.0f * m.scale},
                       17.0f * m.scale, 12.0f * m.scale, kPaper);
    }
    const std::string lap = lapText(viewModel.currentLap, viewModel.totalLaps);
    drawText(lap, {panel.x + 34.0f * m.scale, panel.y + 108.0f * m.scale}, 15.0f * m.scale, kPaperMuted);
    const std::string time = formatTime(viewModel.raceTimeSeconds);
    const float timeWidth = MeasureTextEx(GetFontDefault(), time.c_str(), 15.0f * m.scale, 0.0f).x;
    drawText(time, {panel.x + panel.width - timeWidth - 34.0f * m.scale, panel.y + 108.0f * m.scale}, 15.0f * m.scale,
             kPaperMuted);

    float y = panel.y + 148.0f * m.scale;
    for (const ActionEntry& entry : actions) {
        if (!entry.visible) {
            continue;
        }
        const Rectangle actionBounds{panel.x + 34.0f * m.scale, y, panel.width - 68.0f * m.scale, 38.0f * m.scale};
        const bool selected = entry.action == selectedAction;
        DrawRectangleRec(actionBounds, selected ? kSun : Color{28, 54, 56, 245});
        if (selected) {
            DrawTriangle({actionBounds.x + 13.0f * m.scale, actionBounds.y + 11.0f * m.scale},
                         {actionBounds.x + 13.0f * m.scale, actionBounds.y + 27.0f * m.scale},
                         {actionBounds.x + 27.0f * m.scale, actionBounds.y + 19.0f * m.scale}, kInk);
        }
        drawText(entry.label, {actionBounds.x + 44.0f * m.scale, actionBounds.y + 10.0f * m.scale}, 18.0f * m.scale,
                 selected ? kInk : kPaper);
        y += 48.0f * m.scale;
    }
}

}  // namespace harbor::ui
