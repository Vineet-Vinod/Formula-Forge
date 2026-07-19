#pragma once

#include <cstdint>
#include <string>
#include <string_view>

namespace agent_play {

enum class CommandType { State, Step, Frame, Reset, Help, Quit };

struct Input {
    float steer = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
    bool confirm = false;
    bool cancel = false;
    bool pause = false;
    bool recover = false;
    bool left = false;
    bool right = false;
    bool up = false;
    bool down = false;
    bool pageLeft = false;
    bool pageRight = false;
    bool shiftUp = false;
    bool shiftDown = false;
};

struct Command {
    CommandType type = CommandType::State;
    Input input;
    int frames = 1;
    bool render = false;
    std::string frameName;
    std::int64_t requestId = -1;
};

struct ParseResult {
    bool ok = false;
    Command command;
    std::string error;
};

ParseResult parseCommand(std::string_view line);
std::string jsonString(std::string_view text);
std::string contactTelemetryJson(bool barrierContact, bool vehicleContact, float impulse, std::string_view cause);
bool runProtocolParserAudit();

}  // namespace agent_play
