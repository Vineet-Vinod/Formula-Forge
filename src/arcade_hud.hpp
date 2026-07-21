#pragma once

#include <array>
#include <string>

namespace harbor::ui {

inline constexpr int kMaxHudRacers = 8;
inline constexpr int kMaxResultRacers = 10;
inline constexpr int kMaxCoursePolylinePoints = 192;

// Call after InitWindow and before the first frame. The default raylib font is
// retained as a fallback when the bundled face cannot be loaded.
bool InitializeUiFont(const char* fontPath, int baseSize = 64);
bool InitializeSelectionFont(const char* fontPath, int baseSize = 64);
void ShutdownUiFont();
bool IsUiFontLoaded();

struct RaceHudViewModel {
    std::string vehicleName;
    std::string driverName;
    int speedKph = 0;
    int gear = 0;
    float engineRpmNormalized = 0.0f;
    int currentLap = 1;
    int totalLaps = 2;
    int position = 1;
    int racerCount = 1;
    float raceTimeSeconds = 0.0f;
    float currentLapTimeSeconds = 0.0f;
    float bestLapTimeSeconds = 0.0f;
    float raceProgress = 0.0f;
    std::array<float, kMaxHudRacers> racerProgress{};
    int racerProgressCount = 0;
    int playerProgressIndex = 0;
    std::array<float, kMaxCoursePolylinePoints * 2> coursePolyline{};
    int coursePolylinePointCount = 0;
    float courseProgress = 0.0f;
    float driftCharge = 0.0f;
    float boostCharge = 0.0f;
    float presentationTimeSeconds = 0.0f;
    bool boostActive = false;
    bool shiftRecommended = false;
    bool wrongWay = false;
    bool finished = false;
    bool isTimeTrial = false;
    bool hasBestLap = false;
    bool controllerConnected = true;
};

struct CountdownHudViewModel {
    float secondsRemaining = 3.0f;
    bool visible = false;
};

struct LoadingScreenViewModel {
    float progress = 0.0f;
    float presentationTimeSeconds = 0.0f;
    std::string statusText = "WARMING UP THE ENGINES";
    bool cinematicBackground = false;
};

enum class SelectionStage {
    Mode,
    Car,
    Map,
};

enum class GameModeOption {
    Race,
    TimeTrial,
};

struct SelectionHudViewModel {
    SelectionStage stage = SelectionStage::Mode;
    GameModeOption selectedMode = GameModeOption::Race;
    std::string itemName;
    std::string itemSubtitle;
    std::string backstory;
    std::string mapName;
    std::string mapDescription;
    // Normalized x/y pairs. The first point marks the start and the circuit is
    // closed by the HUD when at least three points are supplied.
    std::array<float, kMaxCoursePolylinePoints * 2> coursePolyline{};
    int coursePolylinePointCount = 0;
    int itemIndex = 0;
    int itemCount = 1;
    std::array<int, 4> lapOptions = {2, 5, 10, 0};
    int lapOptionCount = 4;
    int selectedLapOption = 0;
    bool lapsAdjustable = true;
    float presentationTimeSeconds = 0.0f;
    bool canContinue = true;
    bool controllerConnected = true;
    std::string navigationHint = "LEFT / RIGHT  CHOOSE";
    std::string confirmHint = "A  SELECT";
    std::string backHint = "B  BACK";
};

enum class PauseAction {
    Resume,
    Restart,
    Home,
};

struct PauseHudViewModel {
    std::string eventName;
    int currentLap = 1;
    int totalLaps = 2;
    float raceTimeSeconds = 0.0f;
    float currentLapTimeSeconds = 0.0f;
    float bestLapTimeSeconds = 0.0f;
    PauseAction selectedAction = PauseAction::Resume;
    bool visible = false;
    bool isTimeTrial = false;
    bool hasBestLap = false;
};

struct ResultRowViewModel {
    int position = 1;
    std::string driverName;
    std::string vehicleName;
    float finishTimeSeconds = 0.0f;
    int lapsCompleted = 0;
    bool isPlayer = false;
};

enum class ResultsAction {
    Replay,
    Home,
};

struct ResultsHudViewModel {
    std::string eventName;
    std::array<ResultRowViewModel, kMaxResultRacers> rows{};
    int rowCount = 0;
    int totalLaps = 0;
    float bestLapTimeSeconds = 0.0f;
    bool isTimeTrial = false;
    bool hasBestLap = false;
    ResultsAction selectedAction = ResultsAction::Replay;
    float presentationTimeSeconds = 0.0f;
    bool controllerConnected = true;
};

void DrawRaceHud(const RaceHudViewModel& viewModel);
void DrawCountdownHud(const CountdownHudViewModel& viewModel);
void DrawLoadingScreen(const LoadingScreenViewModel& viewModel);
void DrawSelectionHud(const SelectionHudViewModel& viewModel);
void DrawPauseHud(const PauseHudViewModel& viewModel);
void DrawResultsHud(const ResultsHudViewModel& viewModel);

}  // namespace harbor::ui
