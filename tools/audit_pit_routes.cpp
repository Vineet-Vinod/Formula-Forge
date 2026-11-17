#include "FFSimulation.hpp"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

namespace {
std::vector<std::uint8_t> Read(const std::filesystem::path& path) {
    std::ifstream stream(path,std::ios::binary);
    return {std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()};
}
}

int main(int argc,char* argv[]) {
    if (argc!=2) return 2;
    int failed = 0;
    int tested = 0;
    for (const auto& track : trackCatalog()) {
        const auto folder = std::filesystem::path(argv[1])/track.slug;
        if (!std::filesystem::exists(folder/"pit_lane.bin")) continue;
        FFSimulation simulation(track.id);
        if (!simulation.LoadPitLane(Read(folder/"pit_lane.bin")) ||
            !simulation.LoadPitBarriers(Read(folder/"pit_barriers.bin"))) {
            std::cerr << track.slug << ": binary load failed\n"; ++failed; continue;
        }
        const auto surface = std::filesystem::path("Content/Generated")/track.contentDir/"drive_surface.bin";
        if (std::filesystem::exists(surface) && !simulation.driveSurface.Load(Read(surface))) return 1;
        if (std::filesystem::exists(folder/"escape_surface.bin") &&
            !simulation.escapeSurface.Load(Read(folder/"escape_surface.bin"),0.0)) return 1;
        const auto& sections = simulation.pitLane.Sections();
        float maximumGroundError = 0;
        float maximumStationJump = 0;
        float previousStation = sections.front().trackStation;
        int contacts = 0;
        int active = 0;
        int inactiveControlled = 0;
        for (float distance = 3; distance<sections.back().distance-3; distance+=2) {
            const auto sample = simulation.pitLane.Sample(distance);
            simulation.vehicle.pos = sample.position*17.0f;
            simulation.vehicle.elevation = sample.height*17.0f;
            simulation.vehicle.heading = std::atan2(sample.tangent.y,sample.tangent.x);
            const auto road = simulation.Project(simulation.vehicle.pos);
            const float error = std::abs(simulation.Ground(simulation.vehicle.pos)/17.0f-sample.height);
            maximumGroundError = std::max(maximumGroundError,error);
            const auto hit = firstAuthoredBarrierHit(simulation.Barriers(),simulation.vehicle.pos,
                simulation.vehicle.pos,sample.tangent,83.6f*.5f,34.4f*.5f,
                simulation.vehicle.elevation,.8f*17.0f);
            if (hit.hit) ++contacts;
            if (simulation.InPitLane()) ++active;
            else if (sample.controlled && std::abs(road.lane)>(road.halfWidth+.85f)*17.0f) ++inactiveControlled;
            float station = simulation.ProgressStation();
            while (station<previousStation-track.targetLengthMeters*.5f) station+=track.targetLengthMeters;
            maximumStationJump = std::max(maximumStationJump,std::abs(station-previousStation));
            previousStation = station;
        }
        const bool passed = contacts==0 && maximumGroundError<.10f && inactiveControlled==0 && maximumStationJump<20;
        std::cout << "{\"slug\":\"" << track.slug << "\",\"pass\":" << (passed?"true":"false")
            << ",\"contacts\":" << contacts << ",\"active_pit_samples\":" << active
            << ",\"inactive_controlled_samples\":" << inactiveControlled
            << ",\"maximum_ground_error_m\":" << maximumGroundError
            << ",\"maximum_progress_jump_m\":" << maximumStationJump << "}\n";
        if (!passed) ++failed;
        ++tested;
    }
    if (tested==0) return 2;
    return failed==0?0:1;
}
