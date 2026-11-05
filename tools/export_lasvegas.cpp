#include "generated_circuit.hpp"

#include <filesystem>
#include <fstream>
#include <iomanip>

int main() {
    const TrackCatalogEntry* track = findTrackCatalogEntry(TrackLayoutId::LasVegas);
    if (track == nullptr) return 1;
    const auto samples = sampleCircuit(*track);
    GeneratedSupport support;
    buildGeneratedSupport(*track, samples, support);
    const std::filesystem::path directory("build/lasvegas");
    std::filesystem::create_directories(directory);
    std::ofstream road(directory / "road.csv");
    road << "station,x,y,z,tx,ty,half_width,bank,left_shoulder,right_shoulder\n" << std::setprecision(9);
    for (const CircuitSample& sample : samples) {
        road << sample.station << ',' << sample.sim.x / 17.0f << ',' << -sample.sim.y / 17.0f << ','
            << sample.elevation << ',' << sample.tangent.x << ',' << -sample.tangent.y << ','
            << sample.halfWidth << ',' << sample.bankSlope << ','
            << circuitShoulderMeters(*track, sample.station, true) << ','
            << circuitShoulderMeters(*track, sample.station, false) << '\n';
    }
    std::ofstream walls(directory / "barriers.csv");
    walls << "ax,ay,bx,by,bottom,top,radius\n" << std::setprecision(9);
    for (const AuthoredBarrierSegment& wall : support.barriers) {
        walls << wall.a.x / 17.0f << ',' << -wall.a.y / 17.0f << ',' << wall.b.x / 17.0f << ','
            << -wall.b.y / 17.0f << ',' << wall.bottom / 17.0f << ',' << wall.top / 17.0f << ','
            << wall.halfThickness / 17.0f << '\n';
    }
    return road && walls && samples.size() == 6144 && !support.barriers.empty() ? 0 : 1;
}
