#pragma once

#include <array>
#include <string>

namespace harbor::ui {

inline constexpr int kMaxHudRacers = 8;
inline constexpr int kMaxResultRacers = 10;

// Call after InitWindow and before the first frame. The default raylib font is
// retained as a fallback when the bundled face cannot be loaded.
bool InitializeUiFont(const char* fontPath, int baseSize = 64);
void ShutdownUiFont();
bool IsUiFontLoaded();

struct VehicleStatsViewModel {
    float speed = 0.0f;
    float acceleration = 0.0f;
    float handling = 0.0f;
    float strength = 0.0f;
};

struct RaceHudViewModel {
    std::string vehicleName;
    std::string driverName;
    int speedKph = 0;
    int currentLap = 1;
    int totalLaps = 2;
    int position = 1;
    int racerCount = 1;
    float raceTimeSeconds = 0.0f;
    float raceProgress = 0.0f;
    std::array<float, kMaxHudRacers> racerProgress{};
    int racerProgressCount = 0;
    int playerProgressIndex = 0;
    float driftCharge = 0.0f;
    float boostCharge = 0.0f;
    float presentationTimeSeconds = 0.0f;
    bool boostActive = false;
    bool wrongWay = false;
    bool finished = false;
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
};

enum class SelectionStage {
    Driver,
    Car,
    Map,
    Laps,
};

struct SelectionHudViewModel {
    SelectionStage stage = SelectionStage::Driver;
    std::string itemName;
    std::string itemSubtitle;
    std::string backstory;
    std::string mapName;
    std::string mapDescription;
    VehicleStatsViewModel stats;
    int itemIndex = 0;
    int itemCount = 1;
    std::array<int, 4> lapOptions = {2, 5, 10, 0};
    int lapOptionCount = 4;
    int selectedLapOption = 0;
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
    PauseAction selectedAction = PauseAction::Resume;
    bool visible = false;
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
