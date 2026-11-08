#include "generated_circuit.hpp"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "usage: export-circuit-scene <circuit-slug>\n";
        return 1;
    }
    const TrackCatalogEntry* track = findTrackCatalogEntry(std::string_view(argv[1]));
    if (track == nullptr || !track->generated || track->id == TrackLayoutId::LasVegas) return 1;
    const auto samples = sampleCircuit(*track);
    GeneratedSupport support;
    buildGeneratedSupport(*track, samples, support);
    const auto directory = std::filesystem::path("build/circuits") / track->slug;
    std::filesystem::create_directories(directory);
    std::ofstream metadata(directory / "catalogue.json");
    metadata << std::setprecision(9) << "{\"slug\":\"" << track->slug << "\",\"content_dir\":\""
        << track->contentDir << "\",\"length_m\":" << track->targetLengthMeters
        << ",\"start_station_m\":" << track->startPhase * track->targetLengthMeters
        << ",\"deck_separation\":" << (track->deckSeparation ? "true" : "false") << "}\n";
    std::ofstream road(directory / "road.csv");
    road << "station,x,y,z,tx,ty,half_width,bank,left_shoulder,right_shoulder\n" << std::setprecision(9);
    for (const auto& sample : samples) {
        road << sample.station << ',' << sample.sim.x / 17.0f << ',' << -sample.sim.y / 17.0f << ','
            << sample.elevation << ',' << sample.tangent.x << ',' << -sample.tangent.y << ','
            << sample.halfWidth << ',' << sample.bankSlope << ','
            << circuitShoulderMeters(*track, sample.station, true) << ','
            << circuitShoulderMeters(*track, sample.station, false) << '\n';
    }
    std::ofstream walls(directory / "barriers.csv");
    walls << "ax,ay,bx,by,bottom,top,radius\n" << std::setprecision(9);
    for (const auto& wall : support.barriers) {
        walls << wall.a.x / 17.0f << ',' << -wall.a.y / 17.0f << ',' << wall.b.x / 17.0f << ','
            << -wall.b.y / 17.0f << ',' << wall.bottom / 17.0f << ',' << wall.top / 17.0f << ','
            << wall.halfThickness / 17.0f << '\n';
    }
    std::cout << track->slug << ": " << samples.size() << " canonical road samples, "
              << support.barriers.size() << " collision segments\n";
    return metadata && road && walls && !samples.empty() ? 0 : 1;
}
