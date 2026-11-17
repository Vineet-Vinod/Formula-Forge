#include "FFSimulation.hpp"

#include <array>
#include <cmath>
#include <cstring>
#include <iostream>
#include <vector>

namespace {
template <typename T> void Append(std::vector<std::uint8_t>& bytes, const T& value) {
    const auto* first = reinterpret_cast<const std::uint8_t*>(&value);
    bytes.insert(bytes.end(), first, first + sizeof(value));
}
}

int main() {
    FFSimulation simulation(TrackLayoutId::Jeddah);
    const float station = 220.0f;
    const auto road = simulation.Sample(station);
    const float original = simulation.Ground(road.position);
    std::vector<std::uint8_t> bytes{'F','F','P','I','T','2',0,0};
    Append(bytes,std::uint32_t{3}); Append(bytes,0.0f); Append(bytes,10.0f); Append(bytes,80.0f);
    for (int index = 0; index < 3; ++index) {
        const auto sample = simulation.Sample(station - 5.0f + 5.0f * index);
        const std::array<float,9> row{sample.position.x / 17.0f,sample.position.y / 17.0f,
            sample.elevation / 17.0f - 4.0f,2.0f,sample.station,5.0f*index,
            -sample.tangent.y,sample.tangent.x,sample.bankSlope};
        Append(bytes,row);
    }
    if (!simulation.LoadPitLane(bytes)) return 1;
    simulation.vehicle.pos = road.position;
    simulation.vehicle.elevation = original;
    if (std::abs(simulation.Ground(road.position)-original)>.0001f || simulation.InPitLane()) {
        std::cerr << "Upper racing deck selected lower pit\n"; return 1;
    }
    simulation.vehicle.elevation = road.elevation - 4.0f * 17.0f;
    const float lower = simulation.pitLane.Project(road.position / 17.0f).height * 17.0f;
    if (!simulation.InPitLane() || std::abs(simulation.Ground(road.position)-lower)>.001f ||
        std::abs(simulation.VisualGround(road.position)-lower)>.001f ||
        std::abs(simulation.CurrentSurface().groundElevation-lower)>.001f ||
        std::abs(simulation.ProgressStation()-station)>.01f) {
        std::cerr << "Lower pit contact/progress lost at crossing\n"; return 1;
    }
    std::cout << "Layer-aware pit ground, visual support, surface and progress PASS\n";
}
