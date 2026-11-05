#include "generated_circuit.hpp"

#include <filesystem>
#include <iostream>

int main() {
    int written = 0;
    for (const TrackCatalogEntry& track : trackCatalog()) {
        if (!track.generated) continue;
        const std::filesystem::path directory = std::filesystem::path("Content/Generated") / std::string(track.contentDir);
        std::filesystem::create_directories(directory);
        const std::vector<CircuitSample> samples = sampleCircuit(track);
        if (!writeGeneratedContact(track, samples, directory.string())) {
            std::cerr << track.slug << " contact export failed\n";
            return 1;
        }
        ++written;
    }
    std::cout << "exported contact surfaces for " << written << " circuits\n";
    return written == 19 ? 0 : 1;
}
