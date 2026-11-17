#include "FFSimulation.hpp"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "usage: export-pit-support <output-directory>\n";
        return 1;
    }
    const std::filesystem::path output(argv[1]);
    for (const auto& track : trackCatalog()) {
        FFSimulation simulation(track.id);
        const auto folder = output / track.slug;
        std::filesystem::create_directories(folder);
        std::ofstream road(folder / "road.csv");
        road << "station,x,y,z,tx,ty,half_width,bank,left_shoulder,right_shoulder\n" << std::setprecision(9);
        constexpr int count = 8192;
        for (int index = 0; index < count; ++index) {
            const auto sample = simulation.Sample(track.targetLengthMeters * index / count);
            road << sample.station << ',' << sample.position.x / 17.0f << ',' << -sample.position.y / 17.0f << ','
                 << sample.elevation / 17.0f << ',' << sample.tangent.x << ',' << -sample.tangent.y << ','
                 << sample.halfWidth << ',' << sample.bankSlope << ','
                 << circuitShoulderMeters(track, sample.station, true) << ','
                 << circuitShoulderMeters(track, sample.station, false) << '\n';
        }
        std::ofstream barriers(folder / "barriers.csv");
        barriers << "ax,ay,bx,by,bottom,top,radius\n" << std::setprecision(9);
        for (const auto& wall : simulation.Barriers()) {
            barriers << wall.a.x / 17.0f << ',' << -wall.a.y / 17.0f << ',' << wall.b.x / 17.0f << ','
                     << -wall.b.y / 17.0f << ',' << wall.bottom / 17.0f << ',' << wall.top / 17.0f << ','
                     << wall.halfThickness / 17.0f << '\n';
        }
        std::ofstream metadata(folder / "catalogue.json");
        metadata << std::setprecision(9) << "{\"slug\":\"" << track.slug << "\",\"content_dir\":\"" << track.contentDir
                 << "\",\"length_m\":" << track.targetLengthMeters << ",\"start_station_m\":"
                 << track.startPhase * track.targetLengthMeters << ",\"samples\":" << count
                 << ",\"barriers\":" << simulation.Barriers().size() << "}\n";
        if (!road || !barriers || !metadata) return 1;
        std::cout << track.slug << ": " << count << " exact runtime road samples, "
                  << simulation.Barriers().size() << " existing barriers\n";
    }
}
