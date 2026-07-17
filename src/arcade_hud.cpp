#include "arcade_hud.hpp"

#include <raylib.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

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
constexpr Color kSky = {97, 203, 218, 255};
constexpr Color kSkyDeep = {35, 151, 181, 255};
constexpr Color kSand = {238, 202, 126, 255};
constexpr Color kSandShade = {214, 160, 84, 255};
constexpr Color kSea = {16, 128, 160, 255};

Font gUiFont{};
bool gUiFontLoaded = false;

Font uiFont() {
    return gUiFontLoaded ? gUiFont : GetFontDefault();
}

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

void drawWrappedText(std::string_view text, Rectangle bounds, float fontSize, float lineHeight, Color color, int maxLines) {
    const std::string input(text);
    std::vector<std::string> lines;
    std::string line;
    size_t cursor = 0;
    while (cursor < input.size() && static_cast<int>(lines.size()) < maxLines) {
        while (cursor < input.size() && input[cursor] == ' ') {
            ++cursor;
        }
        size_t end = input.find(' ', cursor);
        if (end == std::string::npos) {
            end = input.size();
        }
        const std::string word = input.substr(cursor, end - cursor);
        const std::string candidate = line.empty() ? word : line + " " + word;
        if (!line.empty() && MeasureTextEx(uiFont(), candidate.c_str(), fontSize, fontSize * 0.015f).x > bounds.width) {
            lines.push_back(line);
            line = word;
        } else {
            line = candidate;
        }
        cursor = end;
    }
    if (!line.empty() && static_cast<int>(lines.size()) < maxLines) {
        lines.push_back(line);
    }
    for (size_t index = 0; index < lines.size(); ++index) {
        drawText(lines[index], {bounds.x, bounds.y + static_cast<float>(index) * lineHeight}, fontSize, color);
    }
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

void drawFormulaBuggyLogo(const Metrics& m, float centerY, float scaleMultiplier = 1.0f) {
    const float titleSize = 68.0f * m.scale * scaleMultiplier;
    const float formulaSize = 22.0f * m.scale * scaleMultiplier;
    drawCenteredText("FORMULA", {m.width * 0.5f + 3.0f * m.scale, centerY - 36.0f * m.scale}, formulaSize,
                     Fade(kInk, 0.68f));
    drawCenteredText("FORMULA", {m.width * 0.5f, centerY - 39.0f * m.scale}, formulaSize, kPaper);
    drawCenteredText("BUGGY", {m.width * 0.5f + 5.0f * m.scale, centerY + 9.0f * m.scale}, titleSize, Fade(kInk, 0.76f));
    drawCenteredText("BUGGY", {m.width * 0.5f, centerY + 3.0f * m.scale}, titleSize, kSun);
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

void drawCourseSchematic(const SelectionHudViewModel& viewModel, Rectangle bounds, float scale) {
    DrawRectangleRec(bounds, Fade(kInk, 0.92f));
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
        points[static_cast<size_t>(index)] = {originX + (x - minX) * fitScale,
                                              originY + (maxY - y) * fitScale};
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

void ShutdownUiFont() {
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
    const Metrics m = metrics();
    drawPlacePanel(viewModel, m);
    drawRaceProgress(viewModel, m);
    drawLapPanel(viewModel, m);
    drawRaceAlert(viewModel, m);
    if (!viewModel.controllerConnected) {
        drawConnectionBanner(m);
    }
}

void DrawLoadingScreen(const LoadingScreenViewModel& viewModel) {
    const Metrics m = metrics();
    drawBeachBackdrop(m, viewModel.presentationTimeSeconds);

    const float stripeWidth = 46.0f * m.scale;
    for (int stripe = -3; stripe < static_cast<int>(m.width / stripeWidth) + 4; ++stripe) {
        const float travel = std::fmod(viewModel.presentationTimeSeconds * 24.0f, stripeWidth * 2.0f);
        const float x = static_cast<float>(stripe) * stripeWidth * 2.0f + travel;
        DrawTriangle({x, 0.0f}, {x + stripeWidth, 0.0f}, {x - 22.0f * m.scale, m.height * 0.54f}, Fade(kPaper, 0.055f));
    }

    drawFormulaBuggyLogo(m, m.height * 0.35f, 1.18f);
    const float railWidth = std::min(430.0f * m.scale, m.width - 2.0f * m.margin);
    const Rectangle rail{(m.width - railWidth) * 0.5f, m.height * 0.73f, railWidth, 8.0f * m.scale};
    DrawRectangleRec(rail, Fade(kInk, 0.42f));
    DrawRectangleRec({rail.x, rail.y, rail.width * clamp01(viewModel.progress), rail.height}, kCoral);
    DrawCircleV({rail.x + rail.width * clamp01(viewModel.progress), rail.y + rail.height * 0.5f}, 7.0f * m.scale, kSun);
    drawCenteredText(viewModel.statusText, {m.width * 0.5f, rail.y + 32.0f * m.scale}, 15.0f * m.scale, kInk);
}

void DrawSelectionHud(const SelectionHudViewModel& viewModel) {
    const Metrics m = metrics();
    static constexpr std::array<const char*, 4> kStageNames = {"DRIVER", "CAR", "MAP", "LAPS"};
    const int stage = std::clamp(static_cast<int>(viewModel.stage), 0, 3);
    if (stage >= 2) {
        drawBeachBackdrop(m, viewModel.presentationTimeSeconds, true);
        DrawRectangle(0, 0, static_cast<int>(m.width), static_cast<int>(m.height), Fade(kInk, 0.12f));
    } else {
        DrawRectangle(0, 0, static_cast<int>(m.width), static_cast<int>(m.height), Fade(kSea, 0.10f));
    }
    const float headerHeight = 98.0f * m.scale;
    DrawRectangleRec({0.0f, 0.0f, m.width, headerHeight}, Fade(kInk, 0.93f));
    drawText("FORMULA BUGGY", {m.margin, 17.0f * m.scale}, 25.0f * m.scale, kSun);
    drawText("RACE SETUP", {m.margin, 52.0f * m.scale}, 15.0f * m.scale, kPaperMuted);

    const float stepsX = std::max(300.0f * m.scale, m.width * 0.38f);
    const float stepsWidth = m.width - stepsX - m.margin;
    const float segmentWidth = stepsWidth / 4.0f;
    for (int index = 0; index < 4; ++index) {
        const bool complete = index < stage;
        const bool current = index == stage;
        const float centerX = stepsX + segmentWidth * (static_cast<float>(index) + 0.5f);
        if (index < 3) {
            DrawLineEx({centerX + 15.0f * m.scale, 35.0f * m.scale},
                       {centerX + segmentWidth - 15.0f * m.scale, 35.0f * m.scale}, 3.0f * m.scale,
                       index < stage ? kAqua : Fade(kOutline, 0.55f));
        }
        DrawCircleV({centerX, 35.0f * m.scale}, 12.0f * m.scale, current ? kSun : (complete ? kAqua : kInkSoft));
        DrawCircleLines(static_cast<int>(centerX), static_cast<int>(35.0f * m.scale), 12.0f * m.scale,
                        current ? kPaper : kOutline);
        if (complete) {
            DrawLineEx({centerX - 5.0f * m.scale, 35.0f * m.scale}, {centerX - 1.0f * m.scale, 40.0f * m.scale},
                       2.0f * m.scale, kInk);
            DrawLineEx({centerX - 1.0f * m.scale, 40.0f * m.scale}, {centerX + 6.0f * m.scale, 30.0f * m.scale},
                       2.0f * m.scale, kInk);
        } else {
            std::array<char, 4> number{};
            std::snprintf(number.data(), number.size(), "%d", index + 1);
            drawCenteredText(number.data(), {centerX, 35.0f * m.scale}, 12.0f * m.scale, current ? kInk : kPaperMuted);
        }
        drawCenteredText(kStageNames[static_cast<size_t>(index)], {centerX, 70.0f * m.scale}, 13.0f * m.scale,
                         current ? kSun : (complete ? kPaper : kPaperMuted));
    }

    const float footerHeight = 62.0f * m.scale;
    const float contentTop = headerHeight + 22.0f * m.scale;
    const float contentBottom = m.height - footerHeight - 18.0f * m.scale;
    const float contentHeight = std::max(260.0f * m.scale, contentBottom - contentTop);
    const float gap = 20.0f * m.scale;
    const float contentWidth = m.width - m.margin * 2.0f;
    const float leftWidth = contentWidth * 0.58f;
    const Rectangle showcase{m.margin, contentTop, leftWidth, contentHeight};
    const Rectangle detail{showcase.x + showcase.width + gap, contentTop, contentWidth - leftWidth - gap, contentHeight};

    DrawRectangleRec(showcase, Fade(Color{235, 246, 228, 255}, stage < 2 ? 0.30f : 0.90f));
    DrawRectangleLinesEx(showcase, 2.0f * m.scale, Fade(kPaper, 0.62f));
    DrawRectangleRec({showcase.x, showcase.y, 7.0f * m.scale, showcase.height}, stage == 0 ? kCoral : (stage == 1 ? kSun : kAqua));

    const std::string eyebrow = stage == 0 ? "CHOOSE YOUR DRIVER" : stage == 1 ? "CHOOSE YOUR RIDE" :
                                  stage == 2 ? "CHOOSE YOUR COURSE" : "SET THE DISTANCE";
    DrawRectangleRec({showcase.x + 18.0f * m.scale, showcase.y + 14.0f * m.scale,
                      showcase.width - 36.0f * m.scale, 44.0f * m.scale}, Fade(kPaper, stage < 2 ? 0.72f : 0.0f));
    drawText(eyebrow, {showcase.x + 28.0f * m.scale, showcase.y + 24.0f * m.scale}, 16.0f * m.scale, kSea);
    std::array<char, 32> indexText{};
    std::snprintf(indexText.data(), indexText.size(), "%02d  /  %02d", std::clamp(viewModel.itemIndex + 1, 1, std::max(1, viewModel.itemCount)),
                  std::max(1, viewModel.itemCount));
    const float indexSize = 16.0f * m.scale;
    const float indexWidth = MeasureTextEx(uiFont(), indexText.data(), indexSize, indexSize * 0.015f).x;
    drawText(indexText.data(), {showcase.x + showcase.width - indexWidth - 25.0f * m.scale, showcase.y + 24.0f * m.scale},
             indexSize, kInkSoft);

    if (stage == 3) {
        const int count = std::clamp(viewModel.lapOptionCount, 0, static_cast<int>(viewModel.lapOptions.size()));
        const float optionGap = 12.0f * m.scale;
        const float optionWidth = std::min(108.0f * m.scale,
                                           (showcase.width - 56.0f * m.scale - optionGap * std::max(0, count - 1)) /
                                               static_cast<float>(std::max(1, count)));
        float x = showcase.x + (showcase.width - (optionWidth * count + optionGap * std::max(0, count - 1))) * 0.5f;
        const float y = showcase.y + showcase.height * 0.37f;
        for (int index = 0; index < count; ++index) {
            const bool selected = index == std::clamp(viewModel.selectedLapOption, 0, std::max(0, count - 1));
            const Rectangle option{x, y, optionWidth, 96.0f * m.scale};
            DrawRectangleRec(option, selected ? kSun : Fade(kInk, 0.87f));
            DrawRectangleLinesEx(option, selected ? 4.0f * m.scale : 1.0f * m.scale, selected ? kPaper : kOutline);
            std::array<char, 16> value{};
            std::snprintf(value.data(), value.size(), viewModel.lapOptions[static_cast<size_t>(index)] <= 0 ? "INF" : "%d",
                          viewModel.lapOptions[static_cast<size_t>(index)]);
            drawCenteredText(value.data(), {option.x + option.width * 0.5f, option.y + 40.0f * m.scale}, 31.0f * m.scale,
                             selected ? kInk : kPaper);
            drawCenteredText("LAPS", {option.x + option.width * 0.5f, option.y + 75.0f * m.scale}, 11.0f * m.scale,
                             selected ? kInkSoft : kPaperMuted);
            x += optionWidth + optionGap;
        }
    } else if (stage == 2) {
        const std::string name = !viewModel.mapName.empty() ? viewModel.mapName : viewModel.itemName;
        drawFittedText(name.empty() ? "SELECT COURSE" : name,
                       {showcase.x + 28.0f * m.scale, showcase.y + 68.0f * m.scale,
                        showcase.width - 56.0f * m.scale, 48.0f * m.scale},
                       34.0f * m.scale, 20.0f * m.scale, kInk);
        if (!viewModel.itemSubtitle.empty()) {
            drawFittedText(viewModel.itemSubtitle,
                           {showcase.x + 30.0f * m.scale, showcase.y + 112.0f * m.scale,
                            showcase.width - 60.0f * m.scale, 26.0f * m.scale},
                           15.0f * m.scale, 11.0f * m.scale, kCoral);
        }

        const Rectangle schematic{showcase.x + 28.0f * m.scale, showcase.y + 150.0f * m.scale,
                                  showcase.width - 56.0f * m.scale, showcase.height - 206.0f * m.scale};
        drawCourseSchematic(viewModel, schematic, m.scale);

        const float arrowY = showcase.y + showcase.height - 29.0f * m.scale;
        drawCenteredText("<", {showcase.x + 39.0f * m.scale, arrowY}, 25.0f * m.scale, kSea);
        drawCenteredText("SELECT COURSE", {showcase.x + showcase.width * 0.5f, arrowY}, 11.0f * m.scale, kInkSoft);
        drawCenteredText(">", {showcase.x + showcase.width - 39.0f * m.scale, arrowY}, 25.0f * m.scale, kSea);
    } else {
        const std::string name = stage == 2 && !viewModel.mapName.empty() ? viewModel.mapName : viewModel.itemName;
        drawFittedText(name.empty() ? kStageNames[static_cast<size_t>(stage)] : name,
                       {showcase.x + 28.0f * m.scale, showcase.y + showcase.height * 0.35f,
                        showcase.width - 56.0f * m.scale, 74.0f * m.scale},
                       54.0f * m.scale, 24.0f * m.scale, kInk);
        if (!viewModel.itemSubtitle.empty()) {
            drawText(viewModel.itemSubtitle, {showcase.x + 30.0f * m.scale, showcase.y + showcase.height * 0.35f + 76.0f * m.scale},
                     17.0f * m.scale, kCoral);
        }
        const float arrowY = showcase.y + showcase.height - 46.0f * m.scale;
        drawCenteredText("<", {showcase.x + 39.0f * m.scale, arrowY}, 28.0f * m.scale, kSea);
        drawCenteredText(">", {showcase.x + showcase.width - 39.0f * m.scale, arrowY}, 28.0f * m.scale, kSea);
    }

    drawPanel(detail, Fade(kInk, 0.96f), stage == 1 ? kSun : kCoral, m.scale);
    const char* detailTitle = stage == 0 ? "DRIVER STORY" : stage == 1 ? "RIDE PROFILE" : stage == 2 ? "COURSE NOTES" : "RACE FORMAT";
    drawText(detailTitle, {detail.x + 24.0f * m.scale, detail.y + 23.0f * m.scale}, 16.0f * m.scale, kAqua);
    const std::string description = stage == 2 ? viewModel.mapDescription : viewModel.backstory;
    drawWrappedText(description.empty() ? "Ready for a new run along the coast." : description,
                    {detail.x + 24.0f * m.scale, detail.y + 61.0f * m.scale, detail.width - 48.0f * m.scale,
                     104.0f * m.scale},
                    17.0f * m.scale, 25.0f * m.scale, kPaper, 4);
    if (stage == 1) {
        const float x = detail.x + 24.0f * m.scale;
        const float width = detail.width - 48.0f * m.scale;
        const float baseY = detail.y + detail.height - 142.0f * m.scale;
        drawStatRow("SPEED", viewModel.stats.speed, {x, baseY, width, 18.0f * m.scale}, kCoral, m.scale);
        drawStatRow("ACCEL", viewModel.stats.acceleration, {x, baseY + 30.0f * m.scale, width, 18.0f * m.scale}, kSun, m.scale);
        drawStatRow("HANDLING", viewModel.stats.handling, {x, baseY + 60.0f * m.scale, width, 18.0f * m.scale}, kAqua, m.scale);
        drawStatRow("STRENGTH", viewModel.stats.strength, {x, baseY + 90.0f * m.scale, width, 18.0f * m.scale}, kLeaf, m.scale);
    }

    const Rectangle footer{0.0f, m.height - footerHeight, m.width, footerHeight};
    DrawRectangleRec(footer, Fade(kInk, 0.96f));
    drawText(viewModel.navigationHint, {m.margin, footer.y + 21.0f * m.scale}, 15.0f * m.scale, kPaperMuted);
    if (stage > 0) {
        drawCenteredText(viewModel.backHint, {m.width * 0.64f, footer.y + footer.height * 0.5f}, 15.0f * m.scale, kPaper);
    }
    const Color confirmColor = viewModel.canContinue ? kSun : kPaperMuted;
    drawCenteredText(stage == 3 ? "A  START RACE" : viewModel.confirmHint,
                     {m.width - m.margin - 83.0f * m.scale, footer.y + footer.height * 0.5f}, 15.0f * m.scale, confirmColor);
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
    const float panelHeight = 334.0f * m.scale;
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

    float y = panel.y + 148.0f * m.scale;
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
    const Metrics m = metrics();
    drawBeachBackdrop(m, viewModel.presentationTimeSeconds, true);
    DrawRectangle(0, 0, static_cast<int>(m.width), static_cast<int>(m.height), Fade(kInk, 0.28f));

    const float panelWidth = std::min(940.0f * m.scale, m.width - 2.0f * m.margin);
    const float panelHeight = std::min(610.0f * m.scale, m.height - 2.0f * m.margin);
    const Rectangle panel{(m.width - panelWidth) * 0.5f, (m.height - panelHeight) * 0.5f, panelWidth, panelHeight};
    DrawRectangleRec(panel, Fade(kInk, 0.97f));
    DrawRectangleRec({panel.x, panel.y, panel.width, 8.0f * m.scale}, kSun);
    DrawTriangle({panel.x, panel.y}, {panel.x + 100.0f * m.scale, panel.y}, {panel.x, panel.y + 100.0f * m.scale},
                 Fade(kCoral, 0.90f));

    drawCenteredText("RACE COMPLETE", {panel.x + panel.width * 0.5f, panel.y + 42.0f * m.scale}, 30.0f * m.scale, kSun);
    if (!viewModel.eventName.empty()) {
        drawCenteredText(viewModel.eventName, {panel.x + panel.width * 0.5f, panel.y + 75.0f * m.scale}, 14.0f * m.scale,
                         kPaperMuted);
    }

    const float tableX = panel.x + 32.0f * m.scale;
    const float tableWidth = panel.width - 64.0f * m.scale;
    const float tableY = panel.y + 105.0f * m.scale;
    const float headerHeight = 30.0f * m.scale;
    DrawRectangleRec({tableX, tableY, tableWidth, headerHeight}, Color{34, 67, 69, 255});
    const float positionX = tableX + 16.0f * m.scale;
    const float driverX = tableX + 82.0f * m.scale;
    const float vehicleX = tableX + tableWidth * 0.48f;
    const float timeX = tableX + tableWidth * 0.72f;
    const float lapX = tableX + tableWidth - 72.0f * m.scale;
    drawText("POS", {positionX, tableY + 8.0f * m.scale}, 12.0f * m.scale, kPaperMuted);
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
        const Color fill = row.isPlayer ? Fade(kSun, 0.95f) : (index % 2 == 0 ? Color{23, 48, 51, 250} : Color{29, 57, 59, 250});
        DrawRectangleRec({tableX, y, tableWidth, rowHeight - 2.0f * m.scale}, fill);
        const Color textColor = row.isPlayer ? kInk : kPaper;
        std::array<char, 12> position{};
        std::snprintf(position.data(), position.size(), "%d", std::max(1, row.position));
        drawText(position.data(), {positionX, y + 9.0f * m.scale}, 17.0f * m.scale, textColor);
        drawFittedText(row.driverName, {driverX, y, vehicleX - driverX - 16.0f * m.scale, rowHeight - 2.0f * m.scale},
                       16.0f * m.scale, 11.0f * m.scale, textColor);
        drawFittedText(row.vehicleName, {vehicleX, y, timeX - vehicleX - 14.0f * m.scale, rowHeight - 2.0f * m.scale},
                       14.0f * m.scale, 10.0f * m.scale, row.isPlayer ? kInkSoft : kPaperMuted);
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
    const std::array<std::pair<ResultsAction, const char*>, 2> actions = {{{ResultsAction::Replay, "REPLAY"},
                                                                           {ResultsAction::Home, "HOME"}}};
    for (size_t index = 0; index < actions.size(); ++index) {
        const Rectangle button{buttonsX + static_cast<float>(index) * (buttonWidth + buttonGap), buttonY, buttonWidth,
                               38.0f * m.scale};
        const bool selected = viewModel.selectedAction == actions[index].first;
        DrawRectangleRec(button, selected ? kSun : Color{35, 68, 70, 255});
        DrawRectangleLinesEx(button, selected ? 2.0f * m.scale : 1.0f * m.scale, selected ? kPaper : kOutline);
        if (selected) {
            DrawTriangle({button.x + 14.0f * m.scale, button.y + 11.0f * m.scale},
                         {button.x + 14.0f * m.scale, button.y + 27.0f * m.scale},
                         {button.x + 27.0f * m.scale, button.y + 19.0f * m.scale}, kInk);
        }
        drawCenteredText(actions[index].second, {button.x + button.width * 0.5f, button.y + button.height * 0.5f},
                         16.0f * m.scale, selected ? kInk : kPaper);
    }
    drawText("A  SELECT", {panel.x + 34.0f * m.scale, buttonY + 12.0f * m.scale}, 13.0f * m.scale, kPaperMuted);
    if (!viewModel.controllerConnected) {
        drawConnectionBanner(m);
    }
}

}  // namespace harbor::ui
