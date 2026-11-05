#include "FFLasVegasAudit.hpp"
#include "FFRacingLine.hpp"
#include "FFSimulation.hpp"

bool PrepareLasVegasAuditLine(const FFSimulation& simulation, FFRacingLine& line) {
    if (simulation.circuit != TrackLayoutId::LasVegas) return false;
    std::vector<FFRacingTrackSample> samples;
    for (int index = 0; index < 1536; ++index) {
        const auto road = simulation.Sample(index * simulation.lapLength / 1536.0f);
        samples.push_back({road.position / 17.0f, road.tangent, road.halfWidth - 2.0f, road.halfWidth - 2.0f});
    }
    if (!line.Initialize(samples, simulation.lapLength)) return false;
    line.MinimizeCurvature(300);
    line.Rebuild(simulation.tuning, 17.0f);
    return true;
}
