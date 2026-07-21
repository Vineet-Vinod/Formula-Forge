#include "arcade_hud.hpp"

#include <raylib.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <string>
#include <string_view>
#include <utility>

namespace harbor::ui {
namespace {

constexpr Color kInk = {15, 30, 34, 242};
constexpr Color kPaper = {244, 247, 232, 255};
constexpr Color kPaperMuted = {186, 207, 194, 255};
constexpr Color kSun = {255, 205, 67, 255};
constexpr Color kCoral = {238, 79, 67, 255};
constexpr Color kAqua = {65, 203, 205, 255};
constexpr Color kTimingGreen = {82, 232, 132, 255};
constexpr Color kOutline = {105, 143, 139, 190};
constexpr Color kSky = {97, 203, 218, 255};
constexpr Color kSkyDeep = {35, 151, 181, 255};
constexpr Color kSand = {238, 202, 126, 255};
constexpr Color kSandShade = {214, 160, 84, 255};
constexpr Color kSea = {16, 128, 160, 255};

Font gUiFont{};
bool gUiFontLoaded = false;
Font gSelectionFont{};
bool gSelectionFontLoaded = false;

Font uiFont() {
    return gUiFontLoaded ? gUiFont : GetFontDefault();
}

class SelectionFontScope {
public:
    SelectionFontScope() : previous_(gUiFont), previousLoaded_(gUiFontLoaded) {
        if (gSelectionFontLoaded) {
            gUiFont = gSelectionFont;
            gUiFontLoaded = true;
        }
    }

    ~SelectionFontScope() {
        gUiFont = previous_;
        gUiFontLoaded = previousLoaded_;
    }

private:
    Font previous_{};
    bool previousLoaded_ = false;
};

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
    const Font font = uiFont();
    float size = preferred;
    const std::string owned(text);
    while (size > minimum && MeasureTextEx(font, owned.c_str(), size, size * 0.015f).x > maximumWidth) {
        size -= 1.0f;
    }
    const float minimumWidth = MeasureTextEx(font, owned.c_str(), minimum, minimum * 0.015f).x;
    if (minimumWidth > maximumWidth && minimumWidth > 0.0f) {
        size = std::max(6.0f, minimum * maximumWidth / minimumWidth);
    }
    return std::max(6.0f, size);
}

void drawText(std::string_view text, Vector2 position, float fontSize, Color color) {
    const std::string owned(text);
    DrawTextEx(uiFont(), owned.c_str(), position, fontSize, fontSize * 0.015f, color);
}

void drawFittedText(std::string_view text, Rectangle bounds, float preferred, float minimum, Color color) {
    const float fontSize = fittedFontSize(text, preferred, minimum, bounds.width);
    drawText(text, {bounds.x, bounds.y + (bounds.height - fontSize) * 0.5f}, fontSize, color);
}

void drawCenteredText(std::string_view text, Vector2 center, float fontSize, Color color) {
    const std::string owned(text);
    const Vector2 size = MeasureTextEx(uiFont(), owned.c_str(), fontSize, fontSize * 0.015f);
    DrawTextEx(uiFont(), owned.c_str(), {center.x - size.x * 0.5f, center.y - size.y * 0.5f}, fontSize,
               fontSize * 0.015f, color);
}

void drawBeachBackdrop(const Metrics& m, float time, bool subdued = false) {
    const Color sky = subdued ? Color{62, 145, 160, 255} : kSky;
    DrawRectangleGradientV(0, 0, static_cast<int>(m.width), static_cast<int>(m.height * 0.67f), sky, kSkyDeep);
    DrawCircleV({m.width * 0.82f, m.height * 0.19f}, 64.0f * m.scale, Fade(kSun, subdued ? 0.55f : 0.92f));

    const float seaY = m.height * 0.57f;
    DrawRectangle(0, static_cast<int>(seaY), static_cast<int>(m.width), static_cast<int>(m.height * 0.18f), kSea);
    for (int wave = -1; wave < static_cast<int>(m.width / (54.0f * m.scale)) + 2; ++wave) {
        const float phase = std::fmod(time * 18.0f, 54.0f * m.scale);
        const Vector2 center{static_cast<float>(wave) * 54.0f * m.scale + phase, seaY + 16.0f * m.scale};
        DrawRing(center, 17.0f * m.scale, 20.0f * m.scale, 195.0f, 345.0f, 18, Fade(kPaper, 0.42f));
    }

    DrawTriangle({0.0f, m.height * 0.69f}, {m.width, m.height * 0.63f}, {m.width, m.height}, kSand);
    DrawTriangle({0.0f, m.height * 0.69f}, {m.width * 0.45f, m.height * 0.665f}, {0.0f, m.height}, kSandShade);
    const float tile = 58.0f * m.scale;
    for (int row = 0; row < 7; ++row) {
        for (int column = -1; column < static_cast<int>(m.width / tile) + 2; ++column) {
            const float x = column * tile + (row % 2) * tile * 0.5f;
            const float y = m.height * 0.72f + row * 28.0f * m.scale;
            DrawCircleLines(static_cast<int>(x), static_cast<int>(y), 3.0f * m.scale, Fade(kInk, subdued ? 0.08f : 0.12f));
        }
    }
}

void drawFormulaForgeLogo(const Metrics& m, float centerY, float scaleMultiplier = 1.0f) {
    const float titleSize = 68.0f * m.scale * scaleMultiplier;
    const float formulaSize = 22.0f * m.scale * scaleMultiplier;
    drawCenteredText("FORMULA", {m.width * 0.5f + 3.0f * m.scale, centerY - 36.0f * m.scale}, formulaSize,
                     Fade(kInk, 0.68f));
    drawCenteredText("FORMULA", {m.width * 0.5f, centerY - 39.0f * m.scale}, formulaSize, kPaper);
    drawCenteredText("FORGE", {m.width * 0.5f + 5.0f * m.scale, centerY + 9.0f * m.scale}, titleSize, Fade(kInk, 0.76f));
    drawCenteredText("FORGE", {m.width * 0.5f, centerY + 3.0f * m.scale}, titleSize, kSun);
    DrawLineEx({m.width * 0.5f - 142.0f * m.scale * scaleMultiplier, centerY + 48.0f * m.scale * scaleMultiplier},
               {m.width * 0.5f + 142.0f * m.scale * scaleMultiplier, centerY + 48.0f * m.scale * scaleMultiplier},
               5.0f * m.scale, kCoral);
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
        std::snprintf(buffer.data(), buffer.size(), "LAP %d", std::max(1, currentLap));
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

void drawCourseSchematic(const SelectionHudViewModel& viewModel, Rectangle bounds, float scale) {
    DrawRectangleRec(bounds, Fade(BLACK, 0.28f));
    DrawRectangleLinesEx(bounds, 1.0f * scale, Fade(kPaper, 0.32f));

    const float waveGap = 32.0f * scale;
    for (float y = bounds.y + waveGap; y < bounds.y + bounds.height; y += waveGap) {
        for (float x = bounds.x - waveGap; x < bounds.x + bounds.width; x += waveGap * 2.0f) {
            DrawLineEx({x, y}, {x + waveGap * 0.5f, y - 3.0f * scale}, 1.0f * scale, Fade(kAqua, 0.10f));
            DrawLineEx({x + waveGap * 0.5f, y - 3.0f * scale}, {x + waveGap, y}, 1.0f * scale,
                       Fade(kAqua, 0.10f));
        }
    }

    const int count = std::clamp(viewModel.coursePolylinePointCount, 0, kMaxCoursePolylinePoints);
    if (count < 3) {
        drawCenteredText("COURSE SCHEMATIC", {bounds.x + bounds.width * 0.5f, bounds.y + bounds.height * 0.48f},
                         16.0f * scale, kPaperMuted);
        drawCenteredText("PREVIEW UNAVAILABLE", {bounds.x + bounds.width * 0.5f, bounds.y + bounds.height * 0.58f},
                         12.0f * scale, Fade(kPaperMuted, 0.72f));
        return;
    }

    float minX = 1.0f;
    float minY = 1.0f;
    float maxX = 0.0f;
    float maxY = 0.0f;
    for (int index = 0; index < count; ++index) {
        const float x = clamp01(viewModel.coursePolyline[static_cast<size_t>(index) * 2]);
        const float y = clamp01(viewModel.coursePolyline[static_cast<size_t>(index) * 2 + 1]);
        minX = std::min(minX, x);
        minY = std::min(minY, y);
        maxX = std::max(maxX, x);
        maxY = std::max(maxY, y);
    }

    const float rangeX = std::max(0.001f, maxX - minX);
    const float rangeY = std::max(0.001f, maxY - minY);
    const Rectangle drawingBounds = inset(bounds, 26.0f * scale);
    const float fitScale = std::min(drawingBounds.width / rangeX, drawingBounds.height / rangeY);
    const float fittedWidth = rangeX * fitScale;
    const float fittedHeight = rangeY * fitScale;
    const float originX = drawingBounds.x + (drawingBounds.width - fittedWidth) * 0.5f;
    const float originY = drawingBounds.y + (drawingBounds.height - fittedHeight) * 0.5f;

    std::array<Vector2, kMaxCoursePolylinePoints> points{};
    for (int index = 0; index < count; ++index) {
        const float x = clamp01(viewModel.coursePolyline[static_cast<size_t>(index) * 2]);
        const float y = clamp01(viewModel.coursePolyline[static_cast<size_t>(index) * 2 + 1]);
        // Track layouts and the world renderer share +Y. The previous HUD
        // transform subtracted Y and displayed every circuit upside down.
        points[static_cast<size_t>(index)] = {originX + (x - minX) * fitScale,
                                              originY + (y - minY) * fitScale};
    }

    const auto drawCircuitPass = [&](float thickness, Color color) {
        for (int index = 0; index < count; ++index) {
            const Vector2 from = points[static_cast<size_t>(index)];
            const Vector2 to = points[static_cast<size_t>((index + 1) % count)];
            DrawLineEx(from, to, thickness, color);
            DrawCircleV(from, thickness * 0.5f, color);
        }
    };
    drawCircuitPass(15.0f * scale, Fade(kSandShade, 0.86f));
    drawCircuitPass(11.0f * scale, kPaper);
    drawCircuitPass(5.0f * scale, kCoral);
    drawCircuitPass(2.0f * scale, Fade(kSun, 0.88f));

    const Vector2 start = points[0];
    const Vector2 next = points[1];
    const float tangentLength = std::max(0.001f, std::sqrt((next.x - start.x) * (next.x - start.x) +
                                                          (next.y - start.y) * (next.y - start.y)));
    const Vector2 normal{-(next.y - start.y) / tangentLength, (next.x - start.x) / tangentLength};
    const Vector2 gateA{start.x - normal.x * 9.0f * scale, start.y - normal.y * 9.0f * scale};
    const Vector2 gateB{start.x + normal.x * 9.0f * scale, start.y + normal.y * 9.0f * scale};
    DrawLineEx(gateA, gateB, 5.0f * scale, kInk);
    DrawLineEx(gateA, gateB, 2.0f * scale, kPaper);
    DrawCircleV(start, 5.5f * scale, kSun);
    DrawCircleLines(static_cast<int>(start.x), static_cast<int>(start.y), 8.0f * scale, kPaper);

    const bool labelLeft = start.x > bounds.x + bounds.width * 0.68f;
    const float labelWidth = 52.0f * scale;
    const float labelX = labelLeft ? start.x - labelWidth - 12.0f * scale : start.x + 12.0f * scale;
    const float labelY = std::clamp(start.y - 12.0f * scale, bounds.y + 5.0f * scale,
                                    bounds.y + bounds.height - 25.0f * scale);
    const Rectangle startLabel{labelX, labelY, labelWidth, 20.0f * scale};
    DrawRectangleRec(startLabel, kSun);
    drawCenteredText("START", {startLabel.x + startLabel.width * 0.5f, startLabel.y + startLabel.height * 0.5f},
                     10.0f * scale, kInk);
}

void drawRaceProgress(const RaceHudViewModel& viewModel, const Metrics& m) {
    const float width = 650.0f * m.scale;
    const float height = 82.0f * m.scale;
    const Rectangle panel{(m.width - width) * 0.5f, m.margin, width, height};
    DrawRectangleRec(panel, Fade(Color{4, 5, 8, 255}, 0.86f));
    DrawRectangleRec({panel.x, panel.y, panel.width, 3.0f * m.scale}, kCoral);
    DrawRectangleLinesEx(panel, 1.0f * m.scale, Fade(kPaper, 0.22f));

    const float columnWidth = panel.width / 3.0f;
    for (int column = 1; column < 3; ++column) {
        const float x = panel.x + columnWidth * static_cast<float>(column);
        DrawLineEx({x, panel.y + 12.0f * m.scale}, {x, panel.y + 61.0f * m.scale},
                   1.0f * m.scale, Fade(kPaper, 0.20f));
    }

    std::array<char, 24> lapValue{};
    if (viewModel.totalLaps <= 0) {
        std::snprintf(lapValue.data(), lapValue.size(), "%d", std::max(1, viewModel.currentLap));
    } else {
        std::snprintf(lapValue.data(), lapValue.size(), "%d / %d",
                      std::clamp(viewModel.currentLap, 1, viewModel.totalLaps), viewModel.totalLaps);
    }
    const float timer = viewModel.isTimeTrial ? viewModel.currentLapTimeSeconds : viewModel.raceTimeSeconds;
    const std::string best = viewModel.hasBestLap ? formatTime(viewModel.bestLapTimeSeconds) : "--:--.--";
    const std::array<std::string, 3> labels = {
        "LAP", viewModel.isTimeTrial ? "LAP TIME" : "RACE TIME", "BEST LAP"};
    const std::array<std::string, 3> values = {lapValue.data(), formatTime(timer), best};
    for (int column = 0; column < 3; ++column) {
        const float centerX = panel.x + columnWidth * (static_cast<float>(column) + 0.5f);
        drawCenteredText(labels[static_cast<size_t>(column)], {centerX, panel.y + 19.0f * m.scale},
                         10.0f * m.scale, column == 2 && viewModel.hasBestLap ? kTimingGreen : kPaperMuted);
        drawCenteredText(values[static_cast<size_t>(column)], {centerX, panel.y + 45.0f * m.scale},
                         column == 0 ? 24.0f * m.scale : 22.0f * m.scale,
                         column == 2 && viewModel.hasBestLap ? kTimingGreen : kPaper);
    }

    const Rectangle rail{panel.x + 18.0f * m.scale, panel.y + panel.height - 10.0f * m.scale,
                         panel.width - 36.0f * m.scale, 4.0f * m.scale};
    DrawRectangleRec(rail, Fade(BLACK, 0.82f));
    const Color progressColor = viewModel.isTimeTrial ? kAqua : kCoral;
    DrawRectangleRec({rail.x, rail.y, rail.width * clamp01(viewModel.raceProgress), rail.height}, progressColor);

    const int count = std::clamp(viewModel.racerProgressCount, 0, kMaxHudRacers);
    for (int index = 0; index < count; ++index) {
        const float progress = clamp01(viewModel.racerProgress[static_cast<size_t>(index)]);
        const Vector2 marker{rail.x + progress * rail.width, rail.y + rail.height * 0.5f};
        const bool player = index == viewModel.playerProgressIndex;
        DrawCircleV(marker, (player ? 4.5f : 2.5f) * m.scale, player ? kPaper : kPaperMuted);
        if (player) {
            DrawCircleLines(static_cast<int>(marker.x), static_cast<int>(marker.y), 6.5f * m.scale, progressColor);
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

void drawTelemetryPanel(const RaceHudViewModel& viewModel, const Metrics& m) {
    const float radius = 105.0f * m.scale;
    const Vector2 center{m.width - m.margin - radius, m.height - m.margin - radius};
    DrawCircleV(center, radius, Fade(Color{4, 5, 8, 255}, 0.88f));
    DrawCircleLines(static_cast<int>(center.x), static_cast<int>(center.y), radius, Fade(kPaper, 0.28f));

    constexpr float startAngle = 135.0f;
    constexpr float sweepAngle = 270.0f;
    const float innerRadius = radius - 14.0f * m.scale;
    const float outerRadius = radius - 6.0f * m.scale;
    DrawRing(center, innerRadius, outerRadius, startAngle, startAngle + sweepAngle, 72, Fade(kPaperMuted, 0.20f));
    DrawRing(center, innerRadius, outerRadius, startAngle + sweepAngle * 0.84f, startAngle + sweepAngle,
             18, Fade(kCoral, 0.38f));
    const float rpm = std::clamp(viewModel.engineRpmNormalized / 1.05f, 0.0f, 1.0f);
    DrawRing(center, innerRadius, outerRadius, startAngle, startAngle + sweepAngle * rpm,
             72, viewModel.shiftRecommended ? kCoral : kPaper);

    for (int tick = 0; tick <= 10; ++tick) {
        const float degrees = startAngle + sweepAngle * static_cast<float>(tick) / 10.0f;
        const float radians = degrees * DEG2RAD;
        const Vector2 direction{std::cos(radians), std::sin(radians)};
        const float tickOuter = radius - 18.0f * m.scale;
        const float tickInner = tickOuter - (tick % 2 == 0 ? 8.0f : 5.0f) * m.scale;
        DrawLineEx({center.x + direction.x * tickInner, center.y + direction.y * tickInner},
                   {center.x + direction.x * tickOuter, center.y + direction.y * tickOuter},
                   (tick % 2 == 0 ? 2.0f : 1.0f) * m.scale,
                   tick >= 9 ? kCoral : Fade(kPaper, 0.62f));
    }

    const bool pulse = std::fmod(std::max(0.0f, viewModel.presentationTimeSeconds), 0.28f) < 0.18f;
    if (viewModel.shiftRecommended && pulse) {
        drawCenteredText("SHIFT", {center.x, center.y - 62.0f * m.scale}, 13.0f * m.scale, kCoral);
    }
    const std::string gear = viewModel.gear > 0 ? std::to_string(std::clamp(viewModel.gear, 1, 8)) : "N";
    drawCenteredText("GEAR", {center.x, center.y - 37.0f * m.scale}, 9.0f * m.scale, kPaperMuted);
    drawCenteredText(gear, {center.x, center.y - 5.0f * m.scale}, 48.0f * m.scale,
                     viewModel.shiftRecommended ? kCoral : kPaper);
    const std::string speed = std::to_string(std::max(0, viewModel.speedKph));
    drawCenteredText(speed, {center.x, center.y + 42.0f * m.scale}, 27.0f * m.scale, kPaper);
    drawCenteredText("KM/H", {center.x, center.y + 66.0f * m.scale}, 9.0f * m.scale, kPaperMuted);
    drawCenteredText("RPM", {center.x, center.y + 84.0f * m.scale}, 8.0f * m.scale,
                     viewModel.shiftRecommended ? kCoral : Fade(kPaperMuted, 0.72f));
}

void drawRouteMap(const RaceHudViewModel& viewModel, const Metrics& m) {
    const int count = std::clamp(viewModel.coursePolylinePointCount, 0, kMaxCoursePolylinePoints);
    if (count < 3) {
        return;
    }

    const float width = 226.0f * m.scale;
    const float height = 184.0f * m.scale;
    const Rectangle panel{m.margin, m.height - m.margin - height, width, height};
    DrawRectangleRec(panel, Fade(Color{4, 5, 8, 255}, 0.82f));
    DrawRectangleRec({panel.x, panel.y, panel.width, 3.0f * m.scale}, kCoral);
    DrawRectangleLinesEx(panel, 1.0f * m.scale, Fade(kPaper, 0.22f));
    drawText("TRACK", {panel.x + 14.0f * m.scale, panel.y + 11.0f * m.scale}, 10.0f * m.scale, kPaperMuted);

    const Rectangle mapBounds{panel.x + 18.0f * m.scale, panel.y + 29.0f * m.scale,
                              panel.width - 34.0f * m.scale, panel.height - 42.0f * m.scale};
    std::array<Vector2, kMaxCoursePolylinePoints> points{};
    for (int index = 0; index < count; ++index) {
        const float x = clamp01(viewModel.coursePolyline[static_cast<size_t>(index) * 2]);
        const float y = clamp01(viewModel.coursePolyline[static_cast<size_t>(index) * 2 + 1]);
        points[static_cast<size_t>(index)] = {mapBounds.x + x * mapBounds.width,
                                              mapBounds.y + y * mapBounds.height};
    }

    for (int index = 0; index < count; ++index) {
        DrawLineEx(points[static_cast<size_t>(index)], points[static_cast<size_t>((index + 1) % count)],
                   6.0f * m.scale, Fade(BLACK, 0.78f));
        DrawLineEx(points[static_cast<size_t>(index)], points[static_cast<size_t>((index + 1) % count)],
                   2.5f * m.scale, Fade(kPaper, 0.72f));
    }

    const float progress = clamp01(viewModel.courseProgress);
    const float scaledProgress = progress * static_cast<float>(count);
    const int playerIndex = std::clamp(static_cast<int>(std::floor(scaledProgress)), 0, count - 1);
    const Vector2 next = points[static_cast<size_t>((playerIndex + 1) % count)];
    const Vector2 current = points[static_cast<size_t>(playerIndex)];
    const float fraction = scaledProgress - std::floor(scaledProgress);
    const Vector2 player{current.x + (next.x - current.x) * fraction,
                         current.y + (next.y - current.y) * fraction};
    const Vector2 delta{next.x - current.x, next.y - current.y};
    const float magnitude = std::max(0.001f, std::sqrt(delta.x * delta.x + delta.y * delta.y));
    const Vector2 direction{delta.x / magnitude, delta.y / magnitude};
    const Vector2 side{-direction.y, direction.x};
    const float markerSize = 8.5f * m.scale;
    DrawCircleV(player, 11.0f * m.scale, Fade(BLACK, 0.72f));
    DrawLineEx(player, {player.x + direction.x * markerSize * 1.25f,
                        player.y + direction.y * markerSize * 1.25f},
               5.0f * m.scale, kCoral);
    DrawTriangle({player.x + direction.x * markerSize, player.y + direction.y * markerSize},
                 {player.x - direction.x * markerSize * 0.55f + side.x * markerSize * 0.62f,
                  player.y - direction.y * markerSize * 0.55f + side.y * markerSize * 0.62f},
                 {player.x - direction.x * markerSize * 0.55f - side.x * markerSize * 0.62f,
                  player.y - direction.y * markerSize * 0.55f - side.y * markerSize * 0.62f},
                 kCoral);
    DrawCircleV(player, 3.5f * m.scale, kPaper);
    DrawCircleLines(static_cast<int>(player.x), static_cast<int>(player.y), 11.0f * m.scale, kPaper);
}

}  // namespace

bool InitializeUiFont(const char* fontPath, int baseSize) {
    ShutdownUiFont();
    if (fontPath == nullptr || fontPath[0] == '\0' || !FileExists(fontPath)) {
        return false;
    }
    gUiFont = LoadFontEx(fontPath, std::max(24, baseSize), nullptr, 0);
    gUiFontLoaded = gUiFont.texture.id != 0 && gUiFont.glyphCount > 0;
    if (gUiFontLoaded) {
        SetTextureFilter(gUiFont.texture, TEXTURE_FILTER_BILINEAR);
    }
    return gUiFontLoaded;
}

bool InitializeSelectionFont(const char* fontPath, int baseSize) {
    if (gSelectionFontLoaded) {
        UnloadFont(gSelectionFont);
        gSelectionFont = {};
        gSelectionFontLoaded = false;
    }
    if (fontPath == nullptr || fontPath[0] == '\0' || !FileExists(fontPath)) {
        return false;
    }
    gSelectionFont = LoadFontEx(fontPath, std::max(24, baseSize), nullptr, 0);
    gSelectionFontLoaded = gSelectionFont.texture.id != 0 && gSelectionFont.glyphCount > 0;
    if (gSelectionFontLoaded) {
        SetTextureFilter(gSelectionFont.texture, TEXTURE_FILTER_BILINEAR);
    }
    return gSelectionFontLoaded;
}

void ShutdownUiFont() {
    if (gSelectionFontLoaded) {
        UnloadFont(gSelectionFont);
    }
    gSelectionFont = {};
    gSelectionFontLoaded = false;
    if (gUiFontLoaded) {
        UnloadFont(gUiFont);
    }
    gUiFont = {};
    gUiFontLoaded = false;
}

bool IsUiFontLoaded() {
    return gUiFontLoaded;
}

void DrawRaceHud(const RaceHudViewModel& viewModel) {
    SelectionFontScope formulaFont;
    const Metrics m = metrics();
    if (!viewModel.isTimeTrial) {
        drawPlacePanel(viewModel, m);
    }
    drawRaceProgress(viewModel, m);
    drawRouteMap(viewModel, m);
    drawTelemetryPanel(viewModel, m);
    drawRaceAlert(viewModel, m);
    if (!viewModel.controllerConnected) {
        drawConnectionBanner(m);
    }
}

void DrawLoadingScreen(const LoadingScreenViewModel& viewModel) {
    const Metrics m = metrics();
    if (viewModel.cinematicBackground) {
        DrawRectangleGradientV(0, 0, static_cast<int>(m.width),
                               static_cast<int>(m.height * 0.30f),
                               Fade(BLACK, 0.78f), BLANK);
        DrawRectangleGradientV(0, static_cast<int>(m.height * 0.66f),
                               static_cast<int>(m.width),
                               static_cast<int>(m.height * 0.34f),
                               BLANK, Fade(BLACK, 0.76f));
    } else {
        drawBeachBackdrop(m, viewModel.presentationTimeSeconds);
        const float stripeWidth = 46.0f * m.scale;
        for (int stripe = -3; stripe < static_cast<int>(m.width / stripeWidth) + 4; ++stripe) {
            const float travel = std::fmod(viewModel.presentationTimeSeconds * 24.0f, stripeWidth * 2.0f);
            const float x = static_cast<float>(stripe) * stripeWidth * 2.0f + travel;
            DrawTriangle({x, 0.0f}, {x + stripeWidth, 0.0f},
                         {x - 22.0f * m.scale, m.height * 0.54f},
                         Fade(kPaper, 0.055f));
        }
    }

    const float logoY = viewModel.cinematicBackground ? m.height * 0.145f : m.height * 0.35f;
    const float logoScale = viewModel.cinematicBackground ? 0.88f : 1.18f;
    drawFormulaForgeLogo(m, logoY, logoScale);
    const float railWidth = std::min(430.0f * m.scale, m.width - 2.0f * m.margin);
    const float railY = viewModel.cinematicBackground ? m.height * 0.885f : m.height * 0.73f;
    const Rectangle rail{(m.width - railWidth) * 0.5f, railY, railWidth, 8.0f * m.scale};
    DrawRectangleRec(rail, Fade(viewModel.cinematicBackground ? BLACK : kInk, 0.62f));
    DrawRectangleRec({rail.x, rail.y, rail.width * clamp01(viewModel.progress), rail.height}, kCoral);
    DrawCircleV({rail.x + rail.width * clamp01(viewModel.progress), rail.y + rail.height * 0.5f}, 7.0f * m.scale, kSun);
    drawCenteredText(viewModel.statusText, {m.width * 0.5f, rail.y + 32.0f * m.scale},
                     15.0f * m.scale,
                     viewModel.cinematicBackground ? kPaper : kInk);
}

void DrawSelectionHud(const SelectionHudViewModel& viewModel) {
    SelectionFontScope selectionFont;
    const Metrics m = metrics();
    const bool modeStage = viewModel.stage == SelectionStage::Mode;
    const bool carStage = viewModel.stage == SelectionStage::Car;
    const bool mapStage = viewModel.stage == SelectionStage::Map;

    // The Blender-authored garage and live car remain the hero. UI surfaces
    // are deliberately compact and translucent, using the loading screen's
    // black, white, and signal-red visual language.
    DrawRectangle(0, 0, static_cast<int>(m.width), static_cast<int>(m.height), Fade(BLACK, 0.10f));
    DrawRectangleGradientV(0, 0, static_cast<int>(m.width), static_cast<int>(180.0f * m.scale),
                           Fade(BLACK, 0.76f), BLANK);

    const float brandX = 42.0f * m.scale;
    drawText("FORMULA", {brandX, 28.0f * m.scale}, 15.0f * m.scale, Fade(kPaper, 0.82f));
    drawText("FORGE", {brandX, 45.0f * m.scale}, 38.0f * m.scale, kPaper);
    DrawRectangleRec({brandX, 88.0f * m.scale, 146.0f * m.scale, 4.0f * m.scale}, kCoral);
    DrawRectangleRec({brandX + 152.0f * m.scale, 88.0f * m.scale, 34.0f * m.scale, 4.0f * m.scale},
                     Fade(kCoral, 0.38f));

    const auto drawFooter = [&]() {
        const float footerHeight = 48.0f * m.scale;
        const Rectangle footer{0.0f, m.height - footerHeight, m.width, footerHeight};
        DrawRectangleRec(footer, Fade(BLACK, 0.78f));
        DrawLineEx({0.0f, footer.y}, {m.width, footer.y}, 1.0f * m.scale, Fade(kCoral, 0.62f));
        drawText(viewModel.navigationHint, {28.0f * m.scale, footer.y + 16.0f * m.scale},
                 13.0f * m.scale, Fade(kPaper, 0.72f));
        if (!modeStage) {
            drawCenteredText(viewModel.backHint, {m.width * 0.72f, footer.y + footer.height * 0.5f},
                             13.0f * m.scale, Fade(kPaper, 0.76f));
        }
        drawCenteredText(viewModel.confirmHint,
                         {m.width - 108.0f * m.scale, footer.y + footer.height * 0.5f},
                         13.0f * m.scale, viewModel.canContinue ? kPaper : Fade(kPaper, 0.35f));
    };

    if (modeStage) {
        drawCenteredText("SELECT SESSION", {m.width * 0.5f, 55.0f * m.scale},
                         20.0f * m.scale, Fade(kPaper, 0.90f));

        struct ModeOption {
            GameModeOption mode;
            const char* name;
            const char* subtitle;
        };
        static constexpr std::array<ModeOption, 2> kModes = {{{GameModeOption::Race, "RACE", "FULL GRID"},
                                                               {GameModeOption::TimeTrial, "TIME TRIAL", "SOLO RUN"}}};
        const float cardWidth = 220.0f * m.scale;
        const float cardHeight = 72.0f * m.scale;
        const float cardGap = 14.0f * m.scale;
        const float totalWidth = cardWidth * 2.0f + cardGap;
        const float cardY = m.height - 148.0f * m.scale;
        for (size_t index = 0; index < kModes.size(); ++index) {
            const bool selected = viewModel.selectedMode == kModes[index].mode;
            const Rectangle card{(m.width - totalWidth) * 0.5f + static_cast<float>(index) * (cardWidth + cardGap),
                                 cardY, cardWidth, cardHeight};
            DrawRectangleRec(card, Fade(selected ? Color{88, 8, 12, 255} : BLACK, selected ? 0.90f : 0.70f));
            DrawRectangleLinesEx(card, selected ? 2.5f * m.scale : 1.0f * m.scale,
                                 selected ? kCoral : Fade(kPaper, 0.24f));
            if (selected) {
                DrawRectangleRec({card.x, card.y, 5.0f * m.scale, card.height}, kCoral);
            }
            drawCenteredText(kModes[index].name,
                             {card.x + card.width * 0.5f, card.y + 27.0f * m.scale},
                             22.0f * m.scale, selected ? kPaper : Fade(kPaper, 0.64f));
            drawCenteredText(kModes[index].subtitle,
                             {card.x + card.width * 0.5f, card.y + 53.0f * m.scale},
                             10.0f * m.scale, selected ? kCoral : Fade(kPaper, 0.38f));
        }
    } else if (carStage) {
        drawCenteredText("SELECT CAR", {m.width * 0.5f, 55.0f * m.scale},
                         20.0f * m.scale, Fade(kPaper, 0.90f));
        const float panelWidth = 520.0f * m.scale;
        const Rectangle panel{(m.width - panelWidth) * 0.5f, m.height - 170.0f * m.scale,
                              panelWidth, 94.0f * m.scale};
        DrawRectangleRec(panel, Fade(BLACK, 0.74f));
        DrawRectangleLinesEx(panel, 1.0f * m.scale, Fade(kPaper, 0.28f));
        DrawRectangleRec({panel.x, panel.y, panel.width, 3.0f * m.scale}, kCoral);
        drawCenteredText("<", {panel.x + 38.0f * m.scale, panel.y + panel.height * 0.5f},
                         28.0f * m.scale, Fade(kPaper, 0.78f));
        drawCenteredText(">", {panel.x + panel.width - 38.0f * m.scale, panel.y + panel.height * 0.5f},
                         28.0f * m.scale, Fade(kPaper, 0.78f));
        drawCenteredText(viewModel.itemName, {panel.x + panel.width * 0.5f, panel.y + 37.0f * m.scale},
                         31.0f * m.scale, kPaper);
        std::array<char, 32> index{};
        std::snprintf(index.data(), index.size(), "%02d / %02d", viewModel.itemIndex + 1,
                      std::max(1, viewModel.itemCount));
        drawCenteredText(index.data(), {panel.x + panel.width * 0.5f, panel.y + 72.0f * m.scale},
                         11.0f * m.scale, kCoral);
    } else if (mapStage) {
        const float panelWidth = std::min(760.0f * m.scale, m.width - 100.0f * m.scale);
        const float panelHeight = std::min(554.0f * m.scale, m.height - 112.0f * m.scale);
        const Rectangle panel{(m.width - panelWidth) * 0.5f, 44.0f * m.scale, panelWidth, panelHeight};
        DrawRectangleRec(panel, Fade(Color{4, 5, 8, 255}, 0.56f));
        DrawRectangleLinesEx(panel, 1.0f * m.scale, Fade(kPaper, 0.30f));
        DrawRectangleRec({panel.x, panel.y, panel.width, 4.0f * m.scale}, kCoral);

        std::array<char, 32> index{};
        std::snprintf(index.data(), index.size(), "%02d / %02d", viewModel.itemIndex + 1,
                      std::max(1, viewModel.itemCount));
        drawCenteredText(index.data(), {panel.x + panel.width * 0.5f, panel.y + 30.0f * m.scale},
                         11.0f * m.scale, Fade(kPaper, 0.54f));
        drawFittedText(viewModel.mapName.empty() ? viewModel.itemName : viewModel.mapName,
                       {panel.x + 42.0f * m.scale, panel.y + 39.0f * m.scale,
                        panel.width - 84.0f * m.scale, 58.0f * m.scale},
                       40.0f * m.scale, 24.0f * m.scale, kPaper);
        drawCenteredText("<", {panel.x + 32.0f * m.scale, panel.y + panel.height * 0.45f},
                         29.0f * m.scale, kCoral);
        drawCenteredText(">", {panel.x + panel.width - 32.0f * m.scale, panel.y + panel.height * 0.45f},
                         29.0f * m.scale, kCoral);

        const Rectangle schematic{panel.x + 62.0f * m.scale, panel.y + 102.0f * m.scale,
                                  panel.width - 124.0f * m.scale, panel.height - 232.0f * m.scale};
        drawCourseSchematic(viewModel, schematic, m.scale);

        const int count = std::clamp(viewModel.lapOptionCount, 0, static_cast<int>(viewModel.lapOptions.size()));
        const float optionWidth = 74.0f * m.scale;
        const float optionGap = 10.0f * m.scale;
        const float optionsWidth = count * optionWidth + std::max(0, count - 1) * optionGap;
        float x = panel.x + (panel.width - optionsWidth) * 0.5f;
        const float optionY = panel.y + panel.height - 91.0f * m.scale;
        drawCenteredText(viewModel.lapsAdjustable ? "UP / DOWN   LAPS" : "OPEN SESSION   LAPS",
                         {panel.x + panel.width * 0.5f, optionY - 18.0f * m.scale},
                         11.0f * m.scale, Fade(kPaper, 0.58f));
        for (int option = 0; option < count; ++option) {
            const bool selected = option == viewModel.selectedLapOption;
            const Rectangle optionBounds{x, optionY, optionWidth, 46.0f * m.scale};
            DrawRectangleRec(optionBounds, Fade(selected ? Color{104, 7, 12, 255} : BLACK,
                                                selected ? 0.92f : 0.54f));
            DrawRectangleLinesEx(optionBounds, selected ? 2.0f * m.scale : 1.0f * m.scale,
                                 selected ? kCoral : Fade(kPaper, 0.20f));
            std::array<char, 12> value{};
            const int laps = viewModel.lapOptions[static_cast<size_t>(option)];
            std::snprintf(value.data(), value.size(), laps <= 0 ? "INF" : "%d", laps);
            drawCenteredText(value.data(), {optionBounds.x + optionBounds.width * 0.5f,
                                            optionBounds.y + optionBounds.height * 0.5f},
                             17.0f * m.scale, selected ? kPaper : Fade(kPaper, 0.42f));
            x += optionWidth + optionGap;
        }
    }

    drawFooter();
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
    };
    const std::array<ActionEntry, 3> actions = {{{PauseAction::Resume, "RESUME"},
                                                 {PauseAction::Restart, "RESTART"},
                                                 {PauseAction::Home, "HOME"}}};
    const bool selectedActionVisible = std::any_of(actions.begin(), actions.end(), [&](const ActionEntry& entry) {
        return entry.action == viewModel.selectedAction;
    });
    const PauseAction selectedAction = selectedActionVisible ? viewModel.selectedAction : PauseAction::Resume;

    const float panelWidth = 430.0f * m.scale;
    const float panelHeight = (viewModel.isTimeTrial ? 360.0f : 334.0f) * m.scale;
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
    const float timeWidth = MeasureTextEx(uiFont(), time.c_str(), 15.0f * m.scale, 15.0f * m.scale * 0.015f).x;
    drawText(time, {panel.x + panel.width - timeWidth - 34.0f * m.scale, panel.y + 108.0f * m.scale}, 15.0f * m.scale,
             kPaperMuted);

    if (viewModel.isTimeTrial) {
        const std::string currentLapTime = "CURRENT  " + formatTime(viewModel.currentLapTimeSeconds);
        const std::string bestLapTime = viewModel.hasBestLap ? "BEST  " + formatTime(viewModel.bestLapTimeSeconds)
                                                             : "BEST  --:--.--";
        drawText(currentLapTime, {panel.x + 34.0f * m.scale, panel.y + 136.0f * m.scale},
                 13.0f * m.scale, kAqua);
        const float bestWidth = MeasureTextEx(uiFont(), bestLapTime.c_str(), 13.0f * m.scale,
                                              13.0f * m.scale * 0.015f).x;
        drawText(bestLapTime,
                 {panel.x + panel.width - bestWidth - 34.0f * m.scale, panel.y + 136.0f * m.scale},
                 13.0f * m.scale, viewModel.hasBestLap ? kTimingGreen : kPaperMuted);
    }

    float y = panel.y + (viewModel.isTimeTrial ? 171.0f : 148.0f) * m.scale;
    for (const ActionEntry& entry : actions) {
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

    drawCenteredText("BACK / B / BACKSPACE  RESUME", {panel.x + panel.width * 0.5f, panel.y + panel.height - 19.0f * m.scale},
                     12.0f * m.scale, kPaperMuted);
}

void DrawResultsHud(const ResultsHudViewModel& viewModel) {
    SelectionFontScope formulaFont;
    const Metrics m = metrics();
    DrawRectangle(0, 0, static_cast<int>(m.width), static_cast<int>(m.height), Fade(BLACK, 0.78f));
    const float pulse = 0.16f + 0.05f * std::sin(viewModel.presentationTimeSeconds * 2.1f);
    DrawCircleGradient({m.width * 0.16f, m.height * 0.18f},
                       250.0f * m.scale, Fade(kCoral, pulse), BLANK);
    DrawCircleGradient({m.width * 0.86f, m.height * 0.70f},
                       310.0f * m.scale, Fade(kCoral, pulse * 0.74f), BLANK);

    const float panelWidth = std::min(940.0f * m.scale, m.width - 2.0f * m.margin);
    const float panelHeight = std::min((viewModel.isTimeTrial ? 460.0f : 610.0f) * m.scale,
                                       m.height - 2.0f * m.margin);
    const Rectangle panel{(m.width - panelWidth) * 0.5f, (m.height - panelHeight) * 0.5f, panelWidth, panelHeight};
    DrawRectangleRec(panel, Fade(kInk, 0.97f));
    DrawRectangleRec({panel.x, panel.y, panel.width, 8.0f * m.scale}, kCoral);
    DrawTriangle({panel.x, panel.y}, {panel.x + 100.0f * m.scale, panel.y}, {panel.x, panel.y + 100.0f * m.scale},
                 Fade(kCoral, 0.90f));

    drawCenteredText(viewModel.isTimeTrial ? "TIME TRIAL COMPLETE" : "RACE COMPLETE",
                     {panel.x + panel.width * 0.5f, panel.y + 42.0f * m.scale}, 30.0f * m.scale, kPaper);
    if (!viewModel.eventName.empty()) {
        drawCenteredText(viewModel.eventName, {panel.x + panel.width * 0.5f, panel.y + 75.0f * m.scale}, 14.0f * m.scale,
                         kPaperMuted);
    }

    const float tableX = panel.x + 32.0f * m.scale;
    const float tableWidth = panel.width - 64.0f * m.scale;
    const float tableY = panel.y + (viewModel.isTimeTrial ? 190.0f : 105.0f) * m.scale;
    const float headerHeight = 30.0f * m.scale;
    if (viewModel.isTimeTrial) {
        const ResultRowViewModel* player = viewModel.rowCount > 0 ? &viewModel.rows[0] : nullptr;
        const Rectangle summary{tableX, panel.y + 105.0f * m.scale, tableWidth, 66.0f * m.scale};
        DrawRectangleRec(summary, Color{13, 17, 22, 248});
        DrawRectangleLinesEx(summary, 1.0f * m.scale, Fade(kPaper, 0.20f));
        const float half = summary.width * 0.5f;
        drawCenteredText("TOTAL TIME", {summary.x + half * 0.5f, summary.y + 17.0f * m.scale},
                         10.0f * m.scale, kPaperMuted);
        drawCenteredText(player ? formatTime(player->finishTimeSeconds) : "--:--.--",
                         {summary.x + half * 0.5f, summary.y + 43.0f * m.scale},
                         24.0f * m.scale, kPaper);
        drawCenteredText("BEST LAP", {summary.x + half * 1.5f, summary.y + 17.0f * m.scale},
                         10.0f * m.scale, viewModel.hasBestLap ? kTimingGreen : kPaperMuted);
        drawCenteredText(viewModel.hasBestLap ? formatTime(viewModel.bestLapTimeSeconds) : "--:--.--",
                         {summary.x + half * 1.5f, summary.y + 43.0f * m.scale},
                         24.0f * m.scale, viewModel.hasBestLap ? kTimingGreen : kPaper);
        DrawLineEx({summary.x + half, summary.y + 11.0f * m.scale},
                   {summary.x + half, summary.y + summary.height - 11.0f * m.scale},
                   1.0f * m.scale, Fade(kPaper, 0.18f));
    }
    DrawRectangleRec({tableX, tableY, tableWidth, headerHeight}, Color{24, 30, 38, 255});
    const float positionX = tableX + 16.0f * m.scale;
    const float driverX = tableX + 82.0f * m.scale;
    const float vehicleX = tableX + tableWidth * 0.48f;
    const float timeX = tableX + tableWidth * 0.72f;
    const float lapX = tableX + tableWidth - 72.0f * m.scale;
    drawText(viewModel.isTimeTrial ? "RUN" : "POS", {positionX, tableY + 8.0f * m.scale}, 12.0f * m.scale, kPaperMuted);
    drawText("DRIVER", {driverX, tableY + 8.0f * m.scale}, 12.0f * m.scale, kPaperMuted);
    drawText("CAR", {vehicleX, tableY + 8.0f * m.scale}, 12.0f * m.scale, kPaperMuted);
    drawText("TIME", {timeX, tableY + 8.0f * m.scale}, 12.0f * m.scale, kPaperMuted);
    drawText("LAPS", {lapX, tableY + 8.0f * m.scale}, 12.0f * m.scale, kPaperMuted);

    const int rowCount = std::clamp(viewModel.rowCount, 0, kMaxResultRacers);
    const float actionsHeight = 73.0f * m.scale;
    const float availableRowsHeight = panel.height - (tableY - panel.y) - actionsHeight - headerHeight - 12.0f * m.scale;
    const float rowHeight = std::clamp(availableRowsHeight / static_cast<float>(std::max(1, rowCount)), 30.0f * m.scale,
                                       43.0f * m.scale);
    for (int index = 0; index < rowCount; ++index) {
        const ResultRowViewModel& row = viewModel.rows[static_cast<size_t>(index)];
        const float y = tableY + headerHeight + rowHeight * static_cast<float>(index);
        const Color fill = row.isPlayer ? Color{66, 9, 14, 250}
                                        : (index % 2 == 0 ? Color{20, 25, 32, 250} : Color{26, 31, 39, 250});
        DrawRectangleRec({tableX, y, tableWidth, rowHeight - 2.0f * m.scale}, fill);
        const Color textColor = kPaper;
        std::array<char, 12> position{};
        std::snprintf(position.data(), position.size(), "%d", std::max(1, row.position));
        drawText(position.data(), {positionX, y + 9.0f * m.scale}, 17.0f * m.scale, textColor);
        drawFittedText(row.driverName, {driverX, y, vehicleX - driverX - 16.0f * m.scale, rowHeight - 2.0f * m.scale},
                       16.0f * m.scale, 11.0f * m.scale, textColor);
        drawFittedText(row.vehicleName, {vehicleX, y, timeX - vehicleX - 14.0f * m.scale, rowHeight - 2.0f * m.scale},
                       14.0f * m.scale, 10.0f * m.scale, kPaperMuted);
        drawText(formatTime(row.finishTimeSeconds), {timeX, y + 10.0f * m.scale}, 14.0f * m.scale, textColor);
        std::array<char, 32> laps{};
        if (viewModel.totalLaps > 0) {
            std::snprintf(laps.data(), laps.size(), "%d/%d", std::max(0, row.lapsCompleted), viewModel.totalLaps);
        } else {
            std::snprintf(laps.data(), laps.size(), "%d", std::max(0, row.lapsCompleted));
        }
        drawText(laps.data(), {lapX, y + 10.0f * m.scale}, 14.0f * m.scale, textColor);
    }

    const float buttonY = panel.y + panel.height - 58.0f * m.scale;
    const float buttonWidth = 180.0f * m.scale;
    const float buttonGap = 14.0f * m.scale;
    const float buttonsX = panel.x + panel.width - 2.0f * buttonWidth - buttonGap - 32.0f * m.scale;
    const std::array<std::pair<ResultsAction, const char*>, 2> actions = {{{ResultsAction::Replay, "PLAY AGAIN"},
                                                                           {ResultsAction::Home, "HOME"}}};
    for (size_t index = 0; index < actions.size(); ++index) {
        const Rectangle button{buttonsX + static_cast<float>(index) * (buttonWidth + buttonGap), buttonY, buttonWidth,
                               38.0f * m.scale};
        const bool selected = viewModel.selectedAction == actions[index].first;
        DrawRectangleRec(button, selected ? kCoral : Color{26, 31, 39, 255});
        DrawRectangleLinesEx(button, selected ? 2.0f * m.scale : 1.0f * m.scale, selected ? kPaper : kOutline);
        if (selected) {
            DrawTriangle({button.x + 14.0f * m.scale, button.y + 11.0f * m.scale},
                         {button.x + 14.0f * m.scale, button.y + 27.0f * m.scale},
                         {button.x + 27.0f * m.scale, button.y + 19.0f * m.scale}, kPaper);
        }
        drawCenteredText(actions[index].second, {button.x + button.width * 0.5f, button.y + button.height * 0.5f},
                         16.0f * m.scale, kPaper);
    }
    drawText("A  SELECT", {panel.x + 34.0f * m.scale, buttonY + 12.0f * m.scale}, 13.0f * m.scale, kPaperMuted);
    if (!viewModel.controllerConnected) {
        drawConnectionBanner(m);
    }
}

}  // namespace harbor::ui
