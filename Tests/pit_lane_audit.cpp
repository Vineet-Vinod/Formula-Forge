#include "FFPitLane.hpp"

#include <array>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

namespace {
void Require(bool value, const char* message) {
    if (!value) { std::cerr << message << '\n'; std::exit(1); }
}
template <typename T> void Append(std::vector<std::uint8_t>& bytes, const T& value) {
    const auto* begin = reinterpret_cast<const std::uint8_t*>(&value);
    bytes.insert(bytes.end(), begin, begin + sizeof(value));
}
std::vector<std::uint8_t> Route(char version, float speed = 60.0f) {
    std::vector<std::uint8_t> bytes{'F','F','P','I','T',static_cast<std::uint8_t>(version),0,0};
    Append(bytes, std::uint32_t{3}); Append(bytes, 2.0f); Append(bytes, 8.0f);
    if (version == '2' || version == '3') Append(bytes, speed);
    for (int i = 0; i < 3; ++i) {
        const std::array<float,9> row{5.0f*i,0.0f,1.0f+0.5f*i,2.0f,
            5990.0f+10.0f*i,5.0f*i,0.0f,1.0f,0.02f};
        Append(bytes,row);
        if (version == '3') { Append(bytes, 2.0f); Append(bytes, 8.0f); }
    }
    return bytes;
}
std::vector<std::uint8_t> Overlay(bool clockwise = false) {
    std::vector<std::uint8_t> bytes{'F','F','B','A','R','2',0,0};
    Append(bytes,std::uint32_t{1}); Append(bytes,std::uint32_t{1});
    Append(bytes,std::array<float,7>{-10,8,10,8,0,1,.1f});
    Append(bytes,clockwise ? std::array<float,10>{-1,-1,-1,1,1,1,1,-1,-1,2}
                          : std::array<float,10>{-1,-1,1,-1,1,1,-1,1,-1,2});
    return bytes;
}
}
int main() {
    FFPitLane lane;
    Require(lane.Load(Route('1')), "FFPIT1 rejected");
    Require(lane.SpeedLimitKph() == 80, "Legacy limit changed");
    Require(lane.Load(Route('2')), "FFPIT2 rejected");
    Require(lane.SpeedLimitKph() == 60, "Source speed limit lost");
    const auto on = lane.Project({5,1});
    Require(on.inside && on.controlled && std::abs(on.height-1.52f)<.00001f, "Pit ground differs from encoded triangles");
    Require(FFPitLowerLayerContact(on, 6.0f, 1.6f), "Lower pit layer lost under race deck");
    Require(!FFPitLowerLayerContact(on, 6.0f, 6.0f), "Race deck snapped onto lower pit");
    Require(!FFPitLowerLayerContact(on, 2.0f, 1.6f), "Normal merge changed layer");
    Require(!FFPitLowerLayerContact({}, 6.0f, 1.6f), "Empty pit changed contact");
    Require(std::abs(on.trackStation-6000)<.001f, "Unwrapped S/F station changed");
    Require(!lane.Project({5,2.1f}).inside, "Pit footprint leaks");
    Require(lane.Project({5,2.1f},1).inside, "Ground collar missing");
    Require(!lane.Project({1,0}).controlled && lane.Sample(5).controlled, "Limit gates changed");
    Require(!lane.Load(Route('2',0)) && lane.SpeedLimitKph()==60, "Invalid metadata mutated route");
    auto truncated = Route('2'); truncated.pop_back();
    Require(!lane.Load(truncated), "Truncated route accepted");
    Require(lane.Load(Route('3')), "FFPIT3 asymmetric working lane rejected");
    const auto working = lane.Project({5,-6});
    Require(working.inside && working.controlled && std::abs(working.height-1.38f)<.00001f,
        "Working lane loses its plane height or limiter");
    Require(working.halfWidth==8 && !lane.Project({5,2.1f}).inside && !lane.Project({5,-8.1f}).inside,
        "Asymmetric support leaked outside its authored side");
    Require(lane.Project({5,-8.1f},1).inside, "Working-lane ground collar missing");
    auto narrow = Route('3');
    const float invalidExtent = 1.0f;
    std::memcpy(narrow.data()+24+36, &invalidExtent, sizeof(float));
    Require(!lane.Load(narrow) && lane.Project({5,-6}).inside, "Invalid extent mutated loaded route");
    std::ifstream legacy("Content/Generated/Data/pit_lane.bin",std::ios::binary);
    Require(legacy.good(), "Retained Silverstone fixture missing");
    std::vector<std::uint8_t> legacyBytes((std::istreambuf_iterator<char>(legacy)),{});
    Require(lane.Load(legacyBytes) && lane.SpeedLimitKph()==80 && lane.Sections().size()>2,
        "Actual Silverstone pit compatibility failed");
    const std::array<AuthoredBarrierSegment,3> original{{
        {{-5,0},{5,0},0,1,.1f}, {{-5,3},{5,3},0,1,.1f}, {{-5,0},{5,0},5,6,.1f}}};
    std::vector<AuthoredBarrierSegment> composed;
    Require(FFComposePitBarriers(Overlay(),original,composed), "Portal overlay rejected");
    Require(composed.size()==5, "Portal did not split one original and append one wall");
    Require(std::abs(composed[0].b.x+1.1f)<.0001f && std::abs(composed[1].a.x-1.1f)<.0001f,
        "Physical wall caps intrude into portal");
    Require(std::memcmp(&composed[2],&original[1],sizeof(AuthoredBarrierSegment))==0,
        "Unrelated barrier changed");
    Require(std::memcmp(&composed[3],&original[2],sizeof(AuthoredBarrierSegment))==0,
        "Overhead structure was clipped");
    const auto previous = composed;
    Require(!FFComposePitBarriers(Overlay(true),original,composed) && composed.size()==previous.size(),
        "Invalid portal accepted or changed output");
    Require(std::memcmp(composed.data(),previous.data(),previous.size()*sizeof(AuthoredBarrierSegment))==0,
        "Failed portal mutation is not atomic");
    std::cout << "Pit formats, actual Silverstone compatibility, wrapped progress, ground and portal composition pass\n";
}
