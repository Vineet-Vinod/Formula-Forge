#include "agent_play_protocol.hpp"

#include <algorithm>
#include <charconv>
#include <cmath>
#include <iomanip>
#include <limits>
#include <sstream>

namespace agent_play {
namespace {

class Parser {
public:
    explicit Parser(std::string_view text) : text_(text) {}

    ParseResult parse() {
        skipSpace();
        if (!consume('{')) {
            return failure("expected a JSON object");
        }
        bool hasCommand = false;
        skipSpace();
        while (!peek('}')) {
            std::string key;
            if (!parseString(key) || !consume(':')) {
                return failure("expected an object key and value");
            }
            if (key == "cmd") {
                std::string value;
                if (!parseString(value) || !setCommand(value)) {
                    return failure("unknown or invalid cmd");
                }
                hasCommand = true;
            } else if (key == "id") {
                double value = 0.0;
                if (!parseNumber(value) || !std::isfinite(value) || std::floor(value) != value ||
                    value < 0.0 || value > static_cast<double>(std::numeric_limits<std::int64_t>::max())) {
                    return failure("id must be a non-negative integer");
                }
                result_.command.requestId = static_cast<std::int64_t>(value);
            } else if (key == "frames") {
                double value = 0.0;
                if (!parseNumber(value) || std::floor(value) != value || value < 1.0 || value > 2400.0) {
                    return failure("frames must be an integer from 1 to 2400");
                }
                result_.command.frames = static_cast<int>(value);
            } else if (key == "render") {
                if (!parseBool(result_.command.render)) {
                    return failure("render must be a boolean");
                }
            } else if (key == "name") {
                if (!parseString(result_.command.frameName) || result_.command.frameName.size() > 80) {
                    return failure("name must be a string of at most 80 characters");
                }
            } else if (key == "input") {
                if (!parseInput()) {
                    return failure(error_.empty() ? "invalid input object" : error_);
                }
            } else if (!skipValue()) {
                return failure("invalid JSON value");
            }
            skipSpace();
            if (peek('}')) {
                break;
            }
            if (!consume(',')) {
                return failure("expected ',' or '}'");
            }
        }
        if (!consume('}')) {
            return failure("unterminated JSON object");
        }
        skipSpace();
        if (position_ != text_.size()) {
            return failure("trailing data after JSON object");
        }
        if (!hasCommand) {
            return failure("missing cmd");
        }
        result_.ok = true;
        return result_;
    }

private:
    ParseResult failure(std::string message) {
        result_.ok = false;
        result_.error = std::move(message);
        return result_;
    }

    void skipSpace() {
        while (position_ < text_.size() &&
               (text_[position_] == ' ' || text_[position_] == '\t' || text_[position_] == '\r' || text_[position_] == '\n')) {
            ++position_;
        }
    }

    bool peek(char expected) {
        skipSpace();
        return position_ < text_.size() && text_[position_] == expected;
    }

    bool consume(char expected) {
        skipSpace();
        if (position_ >= text_.size() || text_[position_] != expected) {
            return false;
        }
        ++position_;
        return true;
    }

    bool parseString(std::string& output) {
        skipSpace();
        if (position_ >= text_.size() || text_[position_++] != '"') {
            return false;
        }
        output.clear();
        while (position_ < text_.size()) {
            const char ch = text_[position_++];
            if (ch == '"') {
                return true;
            }
            if (static_cast<unsigned char>(ch) < 0x20) {
                return false;
            }
            if (ch != '\\') {
                output.push_back(ch);
                continue;
            }
            if (position_ >= text_.size()) {
                return false;
            }
            const char escaped = text_[position_++];
            switch (escaped) {
                case '"': output.push_back('"'); break;
                case '\\': output.push_back('\\'); break;
                case '/': output.push_back('/'); break;
                case 'b': output.push_back('\b'); break;
                case 'f': output.push_back('\f'); break;
                case 'n': output.push_back('\n'); break;
                case 'r': output.push_back('\r'); break;
                case 't': output.push_back('\t'); break;
                default: return false;
            }
        }
        return false;
    }

    bool parseNumber(double& output) {
        skipSpace();
        if (position_ >= text_.size()) {
            return false;
        }
        const size_t beginPosition = position_;
        if (text_[position_] == '-') ++position_;
        if (position_ >= text_.size()) return false;
        if (text_[position_] == '0') {
            ++position_;
        } else if (text_[position_] >= '1' && text_[position_] <= '9') {
            while (position_ < text_.size() && text_[position_] >= '0' && text_[position_] <= '9') ++position_;
        } else {
            return false;
        }
        if (position_ < text_.size() && text_[position_] == '.') {
            ++position_;
            const size_t fractionStart = position_;
            while (position_ < text_.size() && text_[position_] >= '0' && text_[position_] <= '9') ++position_;
            if (position_ == fractionStart) return false;
        }
        if (position_ < text_.size() && (text_[position_] == 'e' || text_[position_] == 'E')) {
            ++position_;
            if (position_ < text_.size() && (text_[position_] == '+' || text_[position_] == '-')) ++position_;
            const size_t exponentStart = position_;
            while (position_ < text_.size() && text_[position_] >= '0' && text_[position_] <= '9') ++position_;
            if (position_ == exponentStart) return false;
        }
        const char* begin = text_.data() + beginPosition;
        const char* end = text_.data() + position_;
        const auto converted = std::from_chars(begin, end, output, std::chars_format::general);
        return converted.ec == std::errc{} && converted.ptr == end;
    }

    bool parseBool(bool& output) {
        skipSpace();
        if (text_.substr(position_, 4) == "true") {
            position_ += 4;
            output = true;
            return true;
        }
        if (text_.substr(position_, 5) == "false") {
            position_ += 5;
            output = false;
            return true;
        }
        return false;
    }

    bool parseUnit(float& output) {
        double value = 0.0;
        if (!parseNumber(value) || !std::isfinite(value) || value < 0.0 || value > 1.0) {
            return false;
        }
        output = static_cast<float>(value);
        return true;
    }

    bool parseSteer(float& output) {
        double value = 0.0;
        if (!parseNumber(value) || !std::isfinite(value) || value < -1.0 || value > 1.0) {
            return false;
        }
        output = static_cast<float>(value);
        return true;
    }

    bool parseInput() {
        if (!consume('{')) {
            return false;
        }
        skipSpace();
        while (!peek('}')) {
            std::string key;
            if (!parseString(key) || !consume(':')) {
                return false;
            }
            bool parsed = true;
            if (key == "steer") parsed = parseSteer(result_.command.input.steer);
            else if (key == "throttle") parsed = parseUnit(result_.command.input.throttle);
            else if (key == "brake") parsed = parseUnit(result_.command.input.brake);
            else if (key == "confirm") parsed = parseBool(result_.command.input.confirm);
            else if (key == "cancel") parsed = parseBool(result_.command.input.cancel);
            else if (key == "pause") parsed = parseBool(result_.command.input.pause);
            else if (key == "recover") parsed = parseBool(result_.command.input.recover);
            else if (key == "left") parsed = parseBool(result_.command.input.left);
            else if (key == "right") parsed = parseBool(result_.command.input.right);
            else if (key == "up") parsed = parseBool(result_.command.input.up);
            else if (key == "down") parsed = parseBool(result_.command.input.down);
            else if (key == "page_left") parsed = parseBool(result_.command.input.pageLeft);
            else if (key == "page_right") parsed = parseBool(result_.command.input.pageRight);
            else if (key == "shift_up") parsed = parseBool(result_.command.input.shiftUp);
            else if (key == "shift_down") parsed = parseBool(result_.command.input.shiftDown);
            else parsed = skipValue();
            if (!parsed) {
                error_ = "input field has the wrong type or range";
                return false;
            }
            if (consume('}')) {
                return true;
            }
            if (!consume(',')) {
                return false;
            }
        }
        return consume('}');
    }

    bool skipValue() {
        skipSpace();
        if (position_ >= text_.size()) return false;
        if (text_[position_] == '"') {
            std::string ignored;
            return parseString(ignored);
        }
        if (text_[position_] == '{') {
            consume('{');
            if (consume('}')) return true;
            while (true) {
                std::string key;
                if (!parseString(key) || !consume(':') || !skipValue()) return false;
                if (consume('}')) return true;
                if (!consume(',')) return false;
            }
        }
        if (text_[position_] == '[') {
            consume('[');
            if (consume(']')) return true;
            while (true) {
                if (!skipValue()) return false;
                if (consume(']')) return true;
                if (!consume(',')) return false;
            }
        }
        bool ignoredBool = false;
        if (parseBool(ignoredBool)) return true;
        if (text_.substr(position_, 4) == "null") {
            position_ += 4;
            return true;
        }
        double ignoredNumber = 0.0;
        return parseNumber(ignoredNumber);
    }

    bool setCommand(std::string_view command) {
        if (command == "state") result_.command.type = CommandType::State;
        else if (command == "step") result_.command.type = CommandType::Step;
        else if (command == "frame") result_.command.type = CommandType::Frame;
        else if (command == "reset") result_.command.type = CommandType::Reset;
        else if (command == "help") result_.command.type = CommandType::Help;
        else if (command == "quit") result_.command.type = CommandType::Quit;
        else return false;
        return true;
    }

    std::string_view text_;
    size_t position_ = 0;
    ParseResult result_;
    std::string error_;
};

}  // namespace

ParseResult parseCommand(std::string_view line) {
    if (line.empty() || line.size() > 65536) {
        return {false, {}, line.empty() ? "empty command" : "command exceeds 65536 bytes"};
    }
    return Parser(line).parse();
}

std::string jsonString(std::string_view text) {
    std::string output;
    output.reserve(text.size() + 2);
    output.push_back('"');
    constexpr char hex[] = "0123456789abcdef";
    for (const unsigned char ch : text) {
        switch (ch) {
            case '"': output += "\\\""; break;
            case '\\': output += "\\\\"; break;
            case '\b': output += "\\b"; break;
            case '\f': output += "\\f"; break;
            case '\n': output += "\\n"; break;
            case '\r': output += "\\r"; break;
            case '\t': output += "\\t"; break;
            default:
                if (ch < 0x20) {
                    output += "\\u00";
                    output.push_back(hex[ch >> 4]);
                    output.push_back(hex[ch & 0x0f]);
                } else {
                    output.push_back(static_cast<char>(ch));
                }
        }
    }
    output.push_back('"');
    return output;
}

std::string contactTelemetryJson(bool barrierContact, bool vehicleContact, float impulse, std::string_view cause) {
    std::ostringstream output;
    output << "\"barrier_contact\":" << (barrierContact ? "true" : "false")
           << ",\"vehicle_contact\":" << (vehicleContact ? "true" : "false")
           << ",\"contact_impulse\":" << std::fixed << std::setprecision(4) << std::max(0.0f, impulse)
           << ",\"contact_cause\":" << jsonString(cause);
    return output.str();
}

bool runProtocolParserAudit() {
    const ParseResult step = parseCommand(
        R"({"cmd":"step","id":17,"frames":120,"render":true,"input":{"steer":-0.5,"throttle":1,"brake":0.25,"confirm":true,"page_right":true,"shift_up":true,"shift_down":true}})");
    const bool stepValid = step.ok && step.command.type == CommandType::Step && step.command.requestId == 17 &&
                           step.command.frames == 120 && step.command.render && step.command.input.steer == -0.5f &&
                           step.command.input.throttle == 1.0f && step.command.input.brake == 0.25f &&
                           step.command.input.confirm && step.command.input.pageRight && step.command.input.shiftUp &&
                           step.command.input.shiftDown;
    const bool commandsValid = parseCommand(R"({"cmd":"state"})").ok && parseCommand(R"({"cmd":"frame","name":"turn_1"})").ok &&
                               parseCommand(R"({"cmd":"reset"})").ok && parseCommand(R"({"cmd":"help"})").ok &&
                               parseCommand(R"({"cmd":"quit"})").ok;
    const bool errorsValid = !parseCommand(R"({"cmd":"step","frames":0})").ok &&
                             !parseCommand(R"({"cmd":"step","input":{"steer":2}})").ok &&
                             !parseCommand(R"({"cmd":"step","input":{"shift_up":1}})").ok &&
                             !parseCommand(R"({"cmd":"step","input":{"shift_down":"true"}})").ok &&
                             !parseCommand(R"({"cmd":"unknown"})").ok && !parseCommand("not json").ok;
    const bool escapingValid = jsonString("a\n\"b") == "\"a\\n\\\"b\"";
    const bool contactTelemetryValid =
        contactTelemetryJson(false, true, 12.5f, "vehicle") ==
        "\"barrier_contact\":false,\"vehicle_contact\":true,\"contact_impulse\":12.5000,\"contact_cause\":\"vehicle\"";
    return stepValid && commandsValid && errorsValid && escapingValid && contactTelemetryValid;
}

}  // namespace agent_play
