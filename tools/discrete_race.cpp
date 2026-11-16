#include "FFDiscreteRace.hpp"

#include <algorithm>
#include <charconv>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string_view>
#include <sys/resource.h>
#include <vector>

namespace {
template<class Number>
bool Parse(std::string_view text, Number& number) {
    const auto result = std::from_chars(text.data(), text.data() + text.size(), number);
    return result.ec == std::errc{} && result.ptr == text.data() + text.size();
}

double Percentile(const std::vector<double>& sorted, double fraction) {
    return sorted[static_cast<std::size_t>(fraction * (sorted.size() - 1))];
}
}

int main(int argc, char* argv[]) {
    FFDiscreteRaceConfig config;
    float seconds = 180.0f;
    std::string_view circuit = "silverstone";
    std::filesystem::path directory = "build/discrete-race/default";
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument(argv[index]);
        if (argument == "--fixed") { config.planning = false; continue; }
        if (argument == "--synchronized") { config.synchronized = true; continue; }
        if (index + 1 >= argc) { std::cerr << "Missing value for " << argument << '\n'; return 2; }
        const std::string_view value(argv[++index]);
        bool valid = true;
        if (argument == "--lines") valid = Parse(value, config.trajectories);
        else if (argument == "--cars") valid = Parse(value, config.cars);
        else if (argument == "--samples") valid = Parse(value, config.samples);
        else if (argument == "--seed") valid = Parse(value, config.seed);
        else if (argument == "--seconds") valid = Parse(value, seconds);
        else if (argument == "--tolerance") valid = Parse(value, config.tolerance);
        else if (argument == "--iterations") valid = Parse(value, config.maximumIterations);
        else if (argument == "--dropout") valid = Parse(value, config.dropout);
        else if (argument == "--range") valid = Parse(value, config.observationRange);
        else if (argument == "--out") directory = value;
        else if (argument == "--circuit") circuit = value;
        else valid = false;
        if (!valid) { std::cerr << "Invalid argument " << argument << ' ' << value << '\n'; return 2; }
    }
    const auto* track = circuit == "silverstone" ? findTrackCatalogEntry(TrackLayoutId::Silverstone) :
        circuit == "monza" ? findTrackCatalogEntry(TrackLayoutId::Monza) :
        circuit == "interlagos" ? findTrackCatalogEntry(TrackLayoutId::Interlagos) : nullptr;
    if (!track || !std::isfinite(seconds) || seconds < 1.0f || seconds > 600.0f) {
        std::cerr << "Use silverstone/monza/interlagos and 1..600 seconds.\n";
        return 2;
    }
    FFSimulation simulation(track->id);
    FFDiscreteRace race;
    std::string error;
    const auto began = std::chrono::steady_clock::now();
    if (!race.Initialize(simulation, config, error)) {
        std::cerr << error << " Residual: " << race.Solver().residual << '\n';
        return 1;
    }
    const double setup = std::chrono::duration<double>(std::chrono::steady_clock::now() - began).count();
    std::filesystem::create_directories(directory);
    std::ofstream trajectories(directory / "trajectories.csv");
    trajectories << "line,station_m,x_m,y_m,speed_mps,lane_m\n" << std::setprecision(7);
    for (int line = 0; line < config.trajectories; ++line) {
        for (int sample = 0; sample < config.samples; ++sample) {
            const auto& node = race.Lines()[line].Nodes()[sample];
            trajectories << line << ',' << sample * race.LapLength() / config.samples << ',' << node.positionMetres.x << ','
                << node.positionMetres.y << ',' << node.speedMetresPerSecond << ',' << node.offsetMetres << '\n';
        }
    }
    std::ofstream telemetry(directory / "race.csv");
    telemetry << "time_s,car,line,target,station_m,speed_mps,x_m,y_m,heading\n" << std::setprecision(8);
    std::vector<double> frameTimes;
    const int steps = static_cast<int>(seconds * 120.0f);
    frameTimes.reserve(steps / 2);
    double frame = 0.0;
    for (int step = 0; step < steps; ++step) {
        const auto start = std::chrono::steady_clock::now();
        race.Step(1.0f / 120.0f);
        frame += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
        if (step % 2 == 1) { frameTimes.push_back(frame); frame = 0.0; }
        if (step % 8 == 0) {
            for (int index = 0; index < config.cars; ++index) {
                const auto& car = race.Cars()[index];
                telemetry << (step + 1) / 120.0f << ',' << index << ',' << car.trajectory << ',' << car.target << ',' << car.station << ','
                    << car.speed << ',' << car.position.x << ',' << car.position.y << ',' << car.heading << '\n';
            }
        }
    }
    std::sort(frameTimes.begin(), frameTimes.end());
    rusage usage{};
    getrusage(RUSAGE_SELF, &usage);
    const auto& solver = race.Solver();
    const auto& stats = race.Stats();
    std::ofstream report(directory / "summary.json");
    report << std::setprecision(9) << std::boolalpha
        << "{\n  \"circuit\": \"" << circuit << "\",\n  \"trajectories\": " << config.trajectories
        << ",\n  \"cars\": " << config.cars << ",\n  \"seed\": " << config.seed << ",\n  \"seconds\": " << seconds
        << ",\n  \"planning\": " << config.planning << ",\n  \"synchronized\": " << config.synchronized
        << ",\n  \"converged\": " << solver.converged << ",\n  \"iterations\": " << solver.iterations
        << ",\n  \"bellman_residual\": " << solver.residual << ",\n  \"minimum_line_rms_m\": " << solver.minimumSeparation
        << ",\n  \"fastest_profile_lap_s\": " << solver.fastestLap << ",\n  \"slowest_profile_lap_s\": " << solver.slowestLap
        << ",\n  \"setup_s\": " << setup << ",\n  \"model_bytes\": " << solver.bytes
        << ",\n  \"peak_rss_bytes\": " << usage.ru_maxrss * 1024L
        << ",\n  \"tick_p50_ms\": " << Percentile(frameTimes, 0.5) << ",\n  \"tick_p95_ms\": " << Percentile(frameTimes, 0.95)
        << ",\n  \"tick_p99_ms\": " << Percentile(frameTimes, 0.99) << ",\n  \"tick_max_ms\": " << frameTimes.back()
        << ",\n  \"decision_mean_ms\": " << stats.decisionMilliseconds / std::max<std::uint64_t>(1, stats.decisions)
        << ",\n  \"switches\": " << stats.switches << ",\n  \"passes\": " << stats.passes
        << ",\n  \"corner_passes\": " << stats.cornerPasses << ",\n  \"overlap_episodes\": " << stats.overlapEpisodes
        << ",\n  \"clean_passes\": " << stats.cleanPasses << ",\n  \"clean_corner_passes\": " << stats.cleanCornerPasses
        << ",\n  \"maximum_lateral_grip_ratio\": " << stats.maximumLateralRatio
        << ",\n  \"minimum_centre_distance_minus_width_m\": " << stats.minimumClearance
        << ",\n  \"observations\": " << stats.observed << ",\n  \"missed_observations\": " << stats.missed << "\n}\n";
    trajectories.close();
    telemetry.close();
    report.close();
    if (!trajectories || !telemetry || !report) { std::cerr << "Cannot write experiment output.\n"; return 1; }
    std::cout << config.trajectories << " lines, " << config.cars << " cars: " << solver.iterations << " iterations, residual "
        << solver.residual << "; tick p99/max " << Percentile(frameTimes, 0.99) << '/' << frameTimes.back()
        << " ms; peak RSS " << usage.ru_maxrss / 1024.0 << " MiB; passes/corner/overlaps "
        << stats.passes << '/' << stats.cornerPasses << '/' << stats.overlapEpisodes << "; " << directory << '\n';
    return 0;
}
