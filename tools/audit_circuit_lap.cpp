#include "FFRacingLine.hpp"
#include "FFSimulation.hpp"

#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

int main(int argc, char* argv[]) {
    if (argc < 2 || argc > 3) {
        std::cerr << "usage: audit-circuit-lap <generated-circuit-slug> [pace=0.55]\n"
                  << "pace is the saved racing-line speed multiplier, between 0.2 and 1.0\n";
        return 2;
    }
    const TrackCatalogEntry* track = findTrackCatalogEntry(std::string_view(argv[1]));
    if (track == nullptr || !track->generated || track->id == TrackLayoutId::LasVegas) {
        std::cerr << "Expected a generated circuit other than the accepted Las Vegas circuit.\n";
        return 2;
    }
    float pace = 0.55f;
    if (argc == 3) {
        const std::string_view argument(argv[2]);
        const auto parsed = std::from_chars(argument.data(), argument.data() + argument.size(), pace);
        if (parsed.ec != std::errc{} || parsed.ptr != argument.data() + argument.size() ||
            !std::isfinite(pace) || pace < 0.2f || pace > 1.0f) {
            std::cerr << "pace must be a finite number between 0.2 and 1.0\n";
            return 2;
        }
    }

    constexpr float Units = 17.0f;
    constexpr float FixedStep = 1.0f / 120.0f;
    constexpr int MaximumSteps = 600 * 120;
    constexpr int NodeCount = 1536;
    constexpr float EdgeMargin = 2.0f;
    const std::filesystem::path dataDirectory = std::filesystem::path("Content/Generated") /
        std::string(track->contentDir);
    const std::filesystem::path outputDirectory = std::filesystem::path("build/circuits") /
        std::string(track->slug);
    std::error_code filesystemError;
    std::filesystem::create_directories(outputDirectory, filesystemError);
    if (filesystemError) {
        std::cerr << "Cannot create audit directory: " << filesystemError.message() << '\n';
        return 2;
    }
    const auto readBytes = [](const std::filesystem::path& path) {
        std::ifstream input(path, std::ios::binary);
        return std::vector<std::uint8_t>(std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>());
    };
    FFSimulation simulation(track->id);
    if (!simulation.driveSurface.Load(readBytes(dataDirectory / "drive_surface.bin")) ||
        !simulation.trackLimits.Load(readBytes(dataDirectory / "track_limits.bin"))) {
        std::cerr << track->slug << ": missing or invalid drive surface/track limits in "
                  << dataDirectory << '\n';
        return 2;
    }

    std::vector<FFRacingTrackSample> samples;
    samples.reserve(NodeCount);
    for (int index = 0; index < NodeCount; ++index) {
        const auto road = simulation.Sample(index * simulation.lapLength / NodeCount);
        if (road.halfWidth <= EdgeMargin) {
            std::cerr << track->slug << ": insufficient width for the 2 m line margin at "
                      << road.station << '\n';
            return 2;
        }
        samples.push_back({road.position / Units, road.tangent,
            road.halfWidth - EdgeMargin, road.halfWidth - EdgeMargin});
    }
    FFRacingLine line;
    if (!line.Initialize(samples, simulation.lapLength)) {
        std::cerr << track->slug << ": racing line initialization failed\n";
        return 2;
    }
    line.controller.lookaheadMetres = 4.0f;
    line.controller.lookaheadSeconds = 0.15f;
    line.controller.predictionSeconds = 0.04f;
    line.MinimizeCurvature(300);
    for (auto& node : line.Nodes()) node.speedScale = pace;
    line.Rebuild(simulation.tuning, Units);
    const auto linePath = outputDirectory / "review-line.txt";
    {
        std::ofstream output(linePath);
        if (!line.Save(output)) {
            std::cerr << "Cannot save " << linePath << '\n';
            return 2;
        }
        output.close();
        if (!output) {
            std::cerr << "Cannot finish writing " << linePath << '\n';
            return 2;
        }
    }

    const auto telemetryPath = outputDirectory / "review-lap.csv";
    std::ofstream telemetry(telemetryPath);
    if (!telemetry) {
        std::cerr << "Cannot create " << telemetryPath << '\n';
        return 2;
    }
    telemetry << "time_s,lap_time_s,completed_laps,station_m,progress_m,x_m,y_m,speed_kph,"
                 "target_kph,lane_m,tracking_error_m,elevation_m,ground_m,vertical_speed_mps,"
                 "steer,throttle,brake,gear,grounded,on_track,contact,lap_invalid\n"
              << std::setprecision(9);
    simulation.Reset();
    float previousStation = simulation.ProgressStation();
    float failureStation = previousStation;
    float progress = 0.0f;
    float maximumTrackingError = 0.0f;
    float maximumSpeedKph = 0.0f;
    float progressAtLastMotion = 0.0f;
    int stepsAtLastMotion = 0;
    int performedSteps = 0;
    bool valid = false;
    std::string failure = "timeout";
    for (int step = 0; step < MaximumSteps; ++step) {
        const auto roadBefore = simulation.Project(simulation.vehicle.pos);
        const auto control = line.Control(simulation.vehicle, simulation.tuning,
            roadBefore.station, Units);
        simulation.Step(control, FixedStep);
        performedSteps = step + 1;
        const bool finite = std::isfinite(simulation.vehicle.pos.x) &&
            std::isfinite(simulation.vehicle.pos.y) && std::isfinite(simulation.vehicle.heading) &&
            std::isfinite(simulation.vehicle.forwardSpeed) && std::isfinite(simulation.vehicle.elevation) &&
            std::isfinite(simulation.vehicle.vel.x) && std::isfinite(simulation.vehicle.vel.y);
        if (!finite) {
            failure = "nonfinite_state";
            break;
        }
        const auto road = simulation.Project(simulation.vehicle.pos);
        const float station = simulation.ProgressStation();
        float movement = station - previousStation;
        if (movement < -simulation.lapLength * 0.5f) movement += simulation.lapLength;
        if (movement > simulation.lapLength * 0.5f) movement -= simulation.lapLength;
        progress += movement;
        previousStation = station;
        failureStation = station;
        const bool onTrack = simulation.OnTrack();
        const float trackingError = length(simulation.vehicle.pos / Units - line.Position(station));
        const float speedKph = simulation.vehicle.forwardSpeed * 3.6f / Units;
        maximumTrackingError = std::max(maximumTrackingError, trackingError);
        maximumSpeedKph = std::max(maximumSpeedKph, speedKph);
        telemetry << performedSteps / 120.0 << ',' << simulation.trial.seconds << ','
                  << simulation.trial.completedLaps << ',' << station << ',' << progress << ','
                  << simulation.vehicle.pos.x / Units << ',' << simulation.vehicle.pos.y / Units << ','
                  << speedKph << ',' << line.Speed(station) * 3.6f << ',' << road.lane / Units << ','
                  << trackingError << ',' << simulation.vehicle.elevation / Units << ','
                  << simulation.Ground(simulation.vehicle.pos) / Units << ','
                  << simulation.vehicle.verticalSpeed / Units << ',' << control.steer << ','
                  << control.throttle << ',' << control.brake << ',' << simulation.vehicle.gear << ','
                  << simulation.vehicle.grounded << ',' << onTrack << ',' << simulation.barrierContact << ','
                  << simulation.trial.invalid << '\n';
        if (simulation.barrierContact) {
            failure = "barrier_contact";
            break;
        }
        if (!onTrack) {
            failure = "track_limits";
            break;
        }
        if (!simulation.vehicle.grounded || simulation.vehicle.airborneTime > 0.0f) {
            failure = "airborne";
            break;
        }
        if (simulation.trial.invalid) {
            failure = "invalid_progress";
            break;
        }
        if (simulation.trial.completedLaps >= 1) {
            valid = simulation.trial.lastValid;
            failure = valid ? "" : "invalid_lap";
            break;
        }
        if (progress - progressAtLastMotion > 0.25f) {
            progressAtLastMotion = progress;
            stepsAtLastMotion = performedSteps;
        } else if (performedSteps - stepsAtLastMotion > 10 * 120) {
            failure = "stalled";
            break;
        }
    }
    telemetry.close();
    if (!telemetry) {
        valid = false;
        failure = "telemetry_write_failed";
    }
    const auto reportPath = outputDirectory / "review-lap.json";
    std::ofstream report(reportPath);
    report << std::setprecision(9) << std::boolalpha
           << "{\n  \"slug\": \"" << track->slug << "\",\n  \"valid\": " << valid
           << ",\n  \"failure\": \"" << failure << "\",\n  \"failure_station_m\": " << failureStation
           << ",\n  \"pace\": " << pace << ",\n  \"line_nodes\": " << NodeCount
           << ",\n  \"edge_margin_m\": " << EdgeMargin << ",\n  \"fixed_step_s\": " << FixedStep
           << ",\n  \"simulated_seconds\": " << performedSteps / 120.0
           << ",\n  \"completed_laps\": " << simulation.trial.completedLaps
           << ",\n  \"lap_seconds\": " << simulation.trial.lastSeconds
           << ",\n  \"progress_m\": " << progress
           << ",\n  \"maximum_tracking_error_m\": " << maximumTrackingError
           << ",\n  \"maximum_speed_kph\": " << maximumSpeedKph
           << ",\n  \"review_line\": \"" << linePath.generic_string()
           << "\",\n  \"telemetry\": \"" << telemetryPath.generic_string() << "\"\n}\n";
    report.close();
    if (!report) {
        std::cerr << "Cannot write " << reportPath << '\n';
        return 2;
    }
    std::cout << track->slug << ": " << (valid ? "PASS" : "FAIL")
              << ", simulated " << performedSteps / 120.0 << " s, lap " << simulation.trial.lastSeconds
              << " s, maximum tracking error " << maximumTrackingError << " m";
    if (!valid) std::cout << ", " << failure << " at station " << failureStation;
    std::cout << "; line " << linePath << "; telemetry " << telemetryPath << '\n';
    return valid ? 0 : 1;
}
