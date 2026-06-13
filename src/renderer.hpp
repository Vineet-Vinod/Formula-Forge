#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <string_view>
#include <vector>

#include "core_math.hpp"

inline std::array<uint8_t, 7> glyph(char ch) {
    if (ch >= 'a' && ch <= 'z') {
        ch = static_cast<char>(ch - 'a' + 'A');
    }
    switch (ch) {
        case 'A': return {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11};
        case 'B': return {0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E};
        case 'C': return {0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E};
        case 'D': return {0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E};
        case 'E': return {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F};
        case 'F': return {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10};
        case 'G': return {0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F};
        case 'H': return {0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11};
        case 'I': return {0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E};
        case 'J': return {0x07, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0C};
        case 'K': return {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11};
        case 'L': return {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F};
        case 'M': return {0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11};
        case 'N': return {0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11};
        case 'O': return {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E};
        case 'P': return {0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10};
        case 'Q': return {0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D};
        case 'R': return {0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11};
        case 'S': return {0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E};
        case 'T': return {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04};
        case 'U': return {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E};
        case 'V': return {0x11, 0x11, 0x11, 0x11, 0x0A, 0x0A, 0x04};
        case 'W': return {0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A};
        case 'X': return {0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11};
        case 'Y': return {0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04};
        case 'Z': return {0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F};
        case '0': return {0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E};
        case '1': return {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E};
        case '2': return {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F};
        case '3': return {0x1E, 0x01, 0x01, 0x0E, 0x01, 0x01, 0x1E};
        case '4': return {0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02};
        case '5': return {0x1F, 0x10, 0x10, 0x1E, 0x01, 0x01, 0x1E};
        case '6': return {0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E};
        case '7': return {0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08};
        case '8': return {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E};
        case '9': return {0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C};
        case ':': return {0x00, 0x04, 0x04, 0x00, 0x04, 0x04, 0x00};
        case '-': return {0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00};
        case '+': return {0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00};
        case '/': return {0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10};
        case '.': return {0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C};
        case '%': return {0x19, 0x19, 0x02, 0x04, 0x08, 0x13, 0x13};
        case '<': return {0x01, 0x02, 0x04, 0x08, 0x04, 0x02, 0x01};
        case '>': return {0x10, 0x08, 0x04, 0x02, 0x04, 0x08, 0x10};
        case ' ': return {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
        default: return {0x1F, 0x11, 0x02, 0x04, 0x04, 0x00, 0x04};
    }
}

class Renderer {
public:
    Renderer(std::vector<uint32_t>& pixels, int width, int height) : pixels_(pixels), width_(width), height_(height) {}

    void clear(uint32_t color) { std::fill(pixels_.begin(), pixels_.end(), color); }

    void setPixel(int x, int y, uint32_t color) {
        if (x < 0 || y < 0 || x >= width_ || y >= height_) {
            return;
        }
        pixels_[static_cast<size_t>(y * width_ + x)] = color;
    }

    void fillRect(int x, int y, int w, int h, uint32_t color) {
        const int x0 = std::clamp(x, 0, width_);
        const int y0 = std::clamp(y, 0, height_);
        const int x1 = std::clamp(x + w, 0, width_);
        const int y1 = std::clamp(y + h, 0, height_);
        for (int yy = y0; yy < y1; ++yy) {
            auto* row = pixels_.data() + yy * width_;
            std::fill(row + x0, row + x1, color);
        }
    }

    void drawSky(uint32_t top, uint32_t horizon, uint32_t sea, int horizonY) {
        horizonY = std::clamp(horizonY, 0, height_);
        for (int y = 0; y < horizonY; ++y) {
            float t = static_cast<float>(y) / std::max(1, horizonY);
            uint8_t r = static_cast<uint8_t>(lerp((top >> 16) & 255, (horizon >> 16) & 255, t));
            uint8_t g = static_cast<uint8_t>(lerp((top >> 8) & 255, (horizon >> 8) & 255, t));
            uint8_t b = static_cast<uint8_t>(lerp(top & 255, horizon & 255, t));
            fillRect(0, y, width_, 1, rgb(r, g, b));
        }
        for (int y = horizonY; y < height_; ++y) {
            float t = static_cast<float>(y - horizonY) / std::max(1, height_ - horizonY);
            fillRect(0, y, width_, 1, shade(sea, 0.78f + 0.25f * t));
        }
    }

    void fillCircle(int cx, int cy, int radius, uint32_t color) {
        if (radius <= 0) {
            return;
        }
        const int x0 = std::max(0, cx - radius);
        const int x1 = std::min(width_ - 1, cx + radius);
        const int y0 = std::max(0, cy - radius);
        const int y1 = std::min(height_ - 1, cy + radius);
        const int r2 = radius * radius;
        for (int y = y0; y <= y1; ++y) {
            const int dy = y - cy;
            for (int x = x0; x <= x1; ++x) {
                const int dx = x - cx;
                if (dx * dx + dy * dy <= r2) {
                    pixels_[static_cast<size_t>(y * width_ + x)] = color;
                }
            }
        }
    }

    void drawLine(Vec2 a, Vec2 b, int thickness, uint32_t color) {
        const float dx = b.x - a.x;
        const float dy = b.y - a.y;
        const int steps = static_cast<int>(std::max(std::abs(dx), std::abs(dy)));
        if (steps <= 0) {
            fillCircle(static_cast<int>(a.x), static_cast<int>(a.y), std::max(1, thickness / 2), color);
            return;
        }
        const int radius = std::max(1, thickness / 2);
        for (int i = 0; i <= steps; ++i) {
            const float t = static_cast<float>(i) / steps;
            fillCircle(static_cast<int>(lerp(a.x, b.x, t)), static_cast<int>(lerp(a.y, b.y, t)), radius, color);
        }
    }

    void fillTriangle(Vec2 a, Vec2 b, Vec2 c, uint32_t color) {
        const float area = edge(a, b, c);
        if (std::abs(area) < 0.001f) {
            return;
        }
        const int minX = std::clamp(static_cast<int>(std::floor(std::min({a.x, b.x, c.x}))), 0, width_ - 1);
        const int maxX = std::clamp(static_cast<int>(std::ceil(std::max({a.x, b.x, c.x}))), 0, width_ - 1);
        const int minY = std::clamp(static_cast<int>(std::floor(std::min({a.y, b.y, c.y}))), 0, height_ - 1);
        const int maxY = std::clamp(static_cast<int>(std::ceil(std::max({a.y, b.y, c.y}))), 0, height_ - 1);
        const bool positive = area > 0.0f;
        for (int y = minY; y <= maxY; ++y) {
            for (int x = minX; x <= maxX; ++x) {
                const Vec2 p{static_cast<float>(x) + 0.5f, static_cast<float>(y) + 0.5f};
                const float w0 = edge(b, c, p);
                const float w1 = edge(c, a, p);
                const float w2 = edge(a, b, p);
                if (positive ? (w0 >= 0.0f && w1 >= 0.0f && w2 >= 0.0f)
                             : (w0 <= 0.0f && w1 <= 0.0f && w2 <= 0.0f)) {
                    pixels_[static_cast<size_t>(y * width_ + x)] = color;
                }
            }
        }
    }

    void fillQuad(Vec2 a, Vec2 b, Vec2 c, Vec2 d, uint32_t color) {
        fillTriangle(a, b, c, color);
        fillTriangle(a, c, d, color);
    }

    void drawText(int x, int y, std::string_view text, int scale, uint32_t color) {
        int cursor = x;
        for (char ch : text) {
            const auto bits = glyph(ch);
            for (int row = 0; row < 7; ++row) {
                for (int col = 0; col < 5; ++col) {
                    if (bits[row] & (1 << (4 - col))) {
                        fillRect(cursor + col * scale, y + row * scale, scale, scale, color);
                    }
                }
            }
            cursor += 6 * scale;
        }
    }

    int width() const { return width_; }
    int height() const { return height_; }

private:
    static float edge(Vec2 a, Vec2 b, Vec2 c) { return (c.x - a.x) * (b.y - a.y) - (c.y - a.y) * (b.x - a.x); }

    std::vector<uint32_t>& pixels_;
    int width_ = 0;
    int height_ = 0;
};

