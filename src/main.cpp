#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <fcntl.h>
#include <linux/joystick.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace {

constexpr int kScreenW = 960;
constexpr int kScreenH = 540;
constexpr float kPi = 3.14159265358979323846f;
constexpr float kTwoPi = 2.0f * kPi;

constexpr uint32_t rgb(uint8_t r, uint8_t g, uint8_t b) {
    return (static_cast<uint32_t>(r) << 16) | (static_cast<uint32_t>(g) << 8) |
           static_cast<uint32_t>(b);
}

uint32_t shade(uint32_t color, float amount) {
    amount = std::clamp(amount, 0.0f, 2.0f);
    uint8_t r = static_cast<uint8_t>(std::clamp(((color >> 16) & 255) * amount, 0.0f, 255.0f));
    uint8_t g = static_cast<uint8_t>(std::clamp(((color >> 8) & 255) * amount, 0.0f, 255.0f));
    uint8_t b = static_cast<uint8_t>(std::clamp((color & 255) * amount, 0.0f, 255.0f));
    return rgb(r, g, b);
}

struct Vec2 {
    float x = 0.0f;
    float y = 0.0f;

    Vec2() = default;
    Vec2(float xIn, float yIn) : x(xIn), y(yIn) {}

    Vec2 operator+(Vec2 other) const { return {x + other.x, y + other.y}; }
    Vec2 operator-(Vec2 other) const { return {x - other.x, y - other.y}; }
    Vec2 operator*(float scalar) const { return {x * scalar, y * scalar}; }
    Vec2 operator/(float scalar) const { return {x / scalar, y / scalar}; }
    Vec2& operator+=(Vec2 other) {
        x += other.x;
        y += other.y;
        return *this;
    }
    Vec2& operator-=(Vec2 other) {
        x -= other.x;
        y -= other.y;
        return *this;
    }
    Vec2& operator*=(float scalar) {
        x *= scalar;
        y *= scalar;
        return *this;
    }
};

float dot(Vec2 a, Vec2 b) { return a.x * b.x + a.y * b.y; }
float lengthSq(Vec2 v) { return dot(v, v); }
float length(Vec2 v) { return std::sqrt(lengthSq(v)); }

Vec2 normalize(Vec2 v) {
    float len = length(v);
    if (len <= 0.00001f) {
        return {1.0f, 0.0f};
    }
    return v / len;
}

Vec2 lerp(Vec2 a, Vec2 b, float t) { return a + (b - a) * t; }
float lerp(float a, float b, float t) { return a + (b - a) * t; }

float wrapProgress(float value, float total) {
    while (value < 0.0f) {
        value += total;
    }
    while (value >= total) {
        value -= total;
    }
    return value;
}

float progressAhead(float from, float to, float total) {
    float delta = to - from;
    while (delta < 0.0f) {
        delta += total;
    }
    while (delta >= total) {
        delta -= total;
    }
    return delta;
}

float wrapAngle(float angle) {
    while (angle <= -kPi) {
        angle += kTwoPi;
    }
    while (angle > kPi) {
        angle -= kTwoPi;
    }
    return angle;
}

Vec2 fromAngle(float angle) { return {std::cos(angle), std::sin(angle)}; }
float angleOf(Vec2 v) { return std::atan2(v.y, v.x); }

struct Camera {
    Vec2 pos;
    float yaw = 0.0f;
    float zoom = 0.36f;
    int screenW = kScreenW;
    int screenH = kScreenH;
    bool perspective = false;
    float height = 125.0f;
    float fov = 520.0f;
    float horizon = 210.0f;
};

struct Projection {
    Vec2 screen;
    float depth = 0.0f;
    float scale = 1.0f;
};

std::array<uint8_t, 7> glyph(char ch) {
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
        case '|': return {0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04};
        case '>': return {0x10, 0x08, 0x04, 0x02, 0x04, 0x08, 0x10};
        case '<': return {0x01, 0x02, 0x04, 0x08, 0x04, 0x02, 0x01};
        case ' ': return {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
        default: return {0x1F, 0x11, 0x02, 0x04, 0x04, 0x00, 0x04};
    }
}

class Renderer {
public:
    Renderer(uint32_t* pixels, int width, int height) : pixels_(pixels), width_(width), height_(height) {}

    int width() const { return width_; }
    int height() const { return height_; }

    void clear(uint32_t color) {
        std::fill(pixels_, pixels_ + width_ * height_, color);
    }

    void setPixel(int x, int y, uint32_t color) {
        if (x < 0 || y < 0 || x >= width_ || y >= height_) {
            return;
        }
        pixels_[y * width_ + x] = color;
    }

    void fillRect(int x, int y, int w, int h, uint32_t color) {
        int x0 = std::clamp(x, 0, width_);
        int y0 = std::clamp(y, 0, height_);
        int x1 = std::clamp(x + w, 0, width_);
        int y1 = std::clamp(y + h, 0, height_);
        for (int yy = y0; yy < y1; ++yy) {
            uint32_t* row = pixels_ + yy * width_;
            std::fill(row + x0, row + x1, color);
        }
    }

    void drawCircle(int cx, int cy, int radius, uint32_t color) {
        if (radius <= 0) {
            return;
        }
        int x0 = std::max(0, cx - radius);
        int x1 = std::min(width_ - 1, cx + radius);
        int y0 = std::max(0, cy - radius);
        int y1 = std::min(height_ - 1, cy + radius);
        int r2 = radius * radius;
        for (int y = y0; y <= y1; ++y) {
            int dy = y - cy;
            for (int x = x0; x <= x1; ++x) {
                int dx = x - cx;
                if (dx * dx + dy * dy <= r2) {
                    pixels_[y * width_ + x] = color;
                }
            }
        }
    }

    void drawLine(Vec2 a, Vec2 b, int thickness, uint32_t color) {
        float dist = length(b - a);
        int steps = std::max(1, static_cast<int>(dist / std::max(1, thickness)));
        for (int i = 0; i <= steps; ++i) {
            float t = static_cast<float>(i) / static_cast<float>(steps);
            Vec2 p = lerp(a, b, t);
            drawCircle(static_cast<int>(std::round(p.x)), static_cast<int>(std::round(p.y)), thickness, color);
        }
    }

    void fillPolygon(const std::vector<Vec2>& points, uint32_t color) {
        if (points.size() < 3) {
            return;
        }
        float minY = points[0].y;
        float maxY = points[0].y;
        for (Vec2 p : points) {
            minY = std::min(minY, p.y);
            maxY = std::max(maxY, p.y);
        }
        int y0 = std::max(0, static_cast<int>(std::floor(minY)));
        int y1 = std::min(height_ - 1, static_cast<int>(std::ceil(maxY)));
        std::vector<float> xs;
        xs.reserve(points.size());
        for (int y = y0; y <= y1; ++y) {
            float scanY = static_cast<float>(y) + 0.5f;
            xs.clear();
            for (size_t i = 0; i < points.size(); ++i) {
                Vec2 a = points[i];
                Vec2 b = points[(i + 1) % points.size()];
                if ((a.y <= scanY && b.y > scanY) || (b.y <= scanY && a.y > scanY)) {
                    float t = (scanY - a.y) / (b.y - a.y);
                    xs.push_back(lerp(a.x, b.x, t));
                }
            }
            std::sort(xs.begin(), xs.end());
            for (size_t i = 0; i + 1 < xs.size(); i += 2) {
                int x0 = std::max(0, static_cast<int>(std::ceil(xs[i])));
                int x1 = std::min(width_ - 1, static_cast<int>(std::floor(xs[i + 1])));
                if (x1 >= x0) {
                    uint32_t* row = pixels_ + y * width_;
                    std::fill(row + x0, row + x1 + 1, color);
                }
            }
        }
    }

    void drawText(int x, int y, std::string_view text, uint32_t color, int scale = 2) {
        int cursor = x;
        for (char raw : text) {
            char ch = raw;
            if (ch >= 'a' && ch <= 'z') {
                ch = static_cast<char>(ch - 'a' + 'A');
            }
            auto rows = glyph(ch);
            for (int yy = 0; yy < 7; ++yy) {
                for (int xx = 0; xx < 5; ++xx) {
                    if ((rows[yy] & (1u << (4 - xx))) != 0u) {
                        fillRect(cursor + xx * scale, y + yy * scale, scale, scale, color);
                    }
                }
            }
            cursor += 6 * scale;
        }
    }

    void drawTextCentered(int cx, int y, std::string_view text, uint32_t color, int scale = 2) {
        int width = static_cast<int>(text.size()) * 6 * scale;
        drawText(cx - width / 2, y, text, color, scale);
    }

private:
    uint32_t* pixels_ = nullptr;
    int width_ = 0;
    int height_ = 0;
};

class AppWindow {
public:
    bool open() {
        display_ = XOpenDisplay(nullptr);
        if (!display_) {
            std::cerr << "Unable to open X11 display. Set DISPLAY or run make self-test for headless checks.\n";
            return false;
        }
        screen_ = DefaultScreen(display_);
        visual_ = DefaultVisual(display_, screen_);
        depth_ = DefaultDepth(display_, screen_);
        width_ = std::max(kScreenW, DisplayWidth(display_, screen_));
        height_ = std::max(kScreenH, DisplayHeight(display_, screen_));
        window_ = XCreateSimpleWindow(display_, RootWindow(display_, screen_), 0, 0, width_, height_, 0,
                                      BlackPixel(display_, screen_), BlackPixel(display_, screen_));
        XStoreName(display_, window_, "Harbor Karts");

        XSizeHints hints{};
        hints.flags = PMinSize;
        hints.min_width = kScreenW;
        hints.min_height = kScreenH;
        XSetWMNormalHints(display_, window_, &hints);

        wmDelete_ = XInternAtom(display_, "WM_DELETE_WINDOW", False);
        XSetWMProtocols(display_, window_, &wmDelete_, 1);
        XSelectInput(display_, window_, ExposureMask | KeyPressMask | KeyReleaseMask | StructureNotifyMask);
        Atom wmState = XInternAtom(display_, "_NET_WM_STATE", False);
        Atom fullscreen = XInternAtom(display_, "_NET_WM_STATE_FULLSCREEN", False);
        XChangeProperty(display_, window_, wmState, XA_ATOM, 32, PropModeReplace,
                        reinterpret_cast<unsigned char*>(&fullscreen), 1);
        XMapWindow(display_, window_);
        gc_ = XCreateGC(display_, window_, 0, nullptr);

        pixels_.assign(width_ * height_, 0);
        image_ = XCreateImage(display_, visual_, depth_, ZPixmap, 0, reinterpret_cast<char*>(pixels_.data()),
                              width_, height_, 32, 0);
        if (!image_ || image_->bits_per_pixel != 32) {
            std::cerr << "Unsupported X11 image format; expected 32 bits per pixel.\n";
            return false;
        }
        running_ = true;
        return true;
    }

    ~AppWindow() {
        if (image_) {
            image_->data = nullptr;
            XDestroyImage(image_);
        }
        if (gc_) {
            XFreeGC(display_, gc_);
        }
        if (window_) {
            XDestroyWindow(display_, window_);
        }
        if (display_) {
            XCloseDisplay(display_);
        }
    }

    void poll(bool devKeyboard, std::array<bool, 256>& keys) {
        if (!display_) {
            return;
        }
        while (XPending(display_) > 0) {
            XEvent event{};
            XNextEvent(display_, &event);
            if (event.type == ClientMessage &&
                static_cast<Atom>(event.xclient.data.l[0]) == wmDelete_) {
                running_ = false;
            } else if (devKeyboard && (event.type == KeyPress || event.type == KeyRelease)) {
                KeySym sym = XLookupKeysym(&event.xkey, 0);
                bool down = event.type == KeyPress;
                auto setKey = [&](KeySym key, uint8_t slot) {
                    if (sym == key) {
                        keys[slot] = down;
                    }
                };
                setKey(XK_Left, 1);
                setKey(XK_Right, 2);
                setKey(XK_Up, 3);
                setKey(XK_Down, 4);
                setKey(XK_Return, 5);
                setKey(XK_space, 6);
                setKey(XK_Escape, 7);
                setKey(XK_z, 8);
                setKey(XK_x, 9);
                setKey(XK_p, 10);
                setKey(XK_r, 11);
            }
        }
    }

    bool running() const { return running_; }
    void close() { running_ = false; }

    Renderer renderer() { return Renderer(pixels_.data(), width_, height_); }

    void present() {
        image_->data = reinterpret_cast<char*>(pixels_.data());
        XPutImage(display_, window_, gc_, image_, 0, 0, 0, 0, width_, height_);
        XFlush(display_);
    }

private:
    Display* display_ = nullptr;
    int screen_ = 0;
    Visual* visual_ = nullptr;
    int depth_ = 0;
    ::Window window_ = 0;
    GC gc_ = nullptr;
    Atom wmDelete_ = 0;
    XImage* image_ = nullptr;
    std::vector<uint32_t> pixels_;
    int width_ = kScreenW;
    int height_ = kScreenH;
    bool running_ = false;
};

struct InputFrame {
    float steer = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
    bool left = false;
    bool right = false;
    bool confirm = false;
    bool back = false;
    bool start = false;
    bool select = false;
    bool quit = false;
    bool connected = false;
};

float axisWithDeadzone(float value, float deadzone = 0.18f) {
    if (std::abs(value) < deadzone) {
        return 0.0f;
    }
    float sign = value < 0.0f ? -1.0f : 1.0f;
    return sign * std::clamp((std::abs(value) - deadzone) / (1.0f - deadzone), 0.0f, 1.0f);
}

class ControllerManager {
public:
    ControllerManager() { scan(); }
    ~ControllerManager() {
        for (Device& d : devices_) {
            if (d.fd >= 0) {
                close(d.fd);
            }
        }
    }

    InputFrame poll() {
        for (Device& d : devices_) {
            d.prevButtons = d.buttons;
        }

        auto now = std::chrono::steady_clock::now();
        if (now >= nextScan_) {
            scan();
            nextScan_ = now + std::chrono::seconds(1);
        }

        js_event event{};
        for (Device& d : devices_) {
            while (read(d.fd, &event, sizeof(event)) == static_cast<ssize_t>(sizeof(event))) {
                bool initEvent = (event.type & JS_EVENT_INIT) != 0;
                uint8_t type = event.type & ~JS_EVENT_INIT;
                if (type == JS_EVENT_AXIS && event.number < d.axes.size()) {
                    if (initEvent) {
                        d.axisCenters[event.number] = event.value;
                        d.axes[event.number] = event.value;
                        continue;
                    }
                    d.axes[event.number] = event.value;
                    d.touched = true;
                } else if (type == JS_EVENT_BUTTON && event.number < d.buttons.size()) {
                    if (initEvent) {
                        continue;
                    }
                    d.buttons[event.number] = event.value != 0;
                    if (event.value != 0) {
                        d.touched = true;
                    }
                }
            }
        }

        InputFrame frame;
        Device* dev = activeDevice();
        if (!dev) {
            return frame;
        }
        frame.connected = true;

        auto axis = [&](size_t index) -> float {
            if (index >= dev->axes.size()) {
                return 0.0f;
            }
            float center = index < dev->axisCenters.size() ? static_cast<float>(dev->axisCenters[index]) : 0.0f;
            float raw = static_cast<float>(dev->axes[index]);
            float span = raw >= center ? 32767.0f - center : center + 32767.0f;
            if (span < 1.0f) {
                return 0.0f;
            }
            return std::clamp((raw - center) / span, -1.0f, 1.0f);
        };
        auto button = [&](size_t index) -> bool {
            return index < dev->buttons.size() && dev->buttons[index];
        };
        auto justPressed = [&](size_t index) -> bool {
            return index < dev->buttons.size() && index < dev->prevButtons.size() && dev->buttons[index] &&
                   !dev->prevButtons[index];
        };
        auto trigger = [&](size_t index) -> float {
            float value = axis(index);
            return value > 0.12f ? std::clamp(value, 0.0f, 1.0f) : 0.0f;
        };

        float steerAxis = axisWithDeadzone(axis(0));
        float dpadX = axisWithDeadzone(axis(6), 0.5f);
        if (std::abs(dpadX) > std::abs(steerAxis)) {
            steerAxis = dpadX;
        }
        if (button(13) || button(14)) {
            steerAxis = -1.0f;
        }
        if (button(11) || button(15)) {
            steerAxis = 1.0f;
        }
        frame.steer = std::clamp(steerAxis, -1.0f, 1.0f);

        float rt = trigger(5);
        float lt = trigger(2);
        frame.throttle = rt;
        frame.brake = lt;

        bool leftNow = frame.steer < -0.55f;
        bool rightNow = frame.steer > 0.55f;
        frame.left = leftNow && !dev->lastMenuLeft;
        frame.right = rightNow && !dev->lastMenuRight;
        dev->lastMenuLeft = leftNow;
        dev->lastMenuRight = rightNow;

        frame.confirm = justPressed(0) || justPressed(7) || justPressed(9);
        frame.back = justPressed(1) || justPressed(6) || justPressed(8);
        frame.start = justPressed(7) || justPressed(9);
        frame.select = justPressed(6) || justPressed(8);
        frame.quit = (button(6) && button(7)) || (button(8) && button(9));
        return frame;
    }

    std::string activeName() const {
        const Device* best = nullptr;
        for (const Device& d : devices_) {
            if (!best || d.touched) {
                best = &d;
            }
        }
        return best ? best->name : std::string();
    }

private:
    struct Device {
        int fd = -1;
        std::string path;
        std::string name;
        std::vector<int16_t> axes;
        std::vector<int16_t> axisCenters;
        std::vector<bool> buttons;
        std::vector<bool> prevButtons;
        bool touched = false;
        bool lastMenuLeft = false;
        bool lastMenuRight = false;
    };

    void scan() {
        for (int i = 0; i < 16; ++i) {
            std::string path = "/dev/input/js" + std::to_string(i);
            bool known = std::any_of(devices_.begin(), devices_.end(), [&](const Device& d) {
                return d.path == path;
            });
            if (known) {
                continue;
            }
            int fd = ::open(path.c_str(), O_RDONLY | O_NONBLOCK);
            if (fd < 0) {
                continue;
            }
            uint8_t axes = 0;
            uint8_t buttons = 0;
            char name[128] = {};
            ioctl(fd, JSIOCGAXES, &axes);
            ioctl(fd, JSIOCGBUTTONS, &buttons);
            if (ioctl(fd, JSIOCGNAME(sizeof(name)), name) < 0) {
                std::strncpy(name, "Linux gamepad", sizeof(name) - 1);
            }
            Device d;
            d.fd = fd;
            d.path = path;
            d.name = name;
            d.axes.assign(std::max<uint8_t>(axes, 8), 0);
            d.axisCenters.assign(std::max<uint8_t>(axes, 8), 0);
            d.buttons.assign(std::max<uint8_t>(buttons, 16), false);
            d.prevButtons = d.buttons;
            devices_.push_back(std::move(d));
        }
    }

    Device* activeDevice() {
        if (devices_.empty()) {
            return nullptr;
        }
        for (Device& d : devices_) {
            if (d.touched) {
                return &d;
            }
        }
        return &devices_.front();
    }

    std::vector<Device> devices_;
    std::chrono::steady_clock::time_point nextScan_ = std::chrono::steady_clock::now();
};

enum class Surface {
    Asphalt,
    Boardwalk,
    Tunnel,
};

struct TrackPoint {
    Vec2 pos;
    float width;
    Surface surface;
};

struct TrackSegment {
    Vec2 a;
    Vec2 b;
    float start = 0.0f;
    float length = 0.0f;
    float widthA = 300.0f;
    float widthB = 300.0f;
    Surface surface = Surface::Asphalt;
};

struct TrackQuery {
    Vec2 point;
    Vec2 tangent;
    Vec2 normal;
    float progress = 0.0f;
    float signedDistance = 0.0f;
    float distance = 0.0f;
    float halfWidth = 150.0f;
    float t = 0.0f;
    int segment = 0;
    Surface surface = Surface::Asphalt;
};

class Track {
public:
    explicit Track(int layout = 0) {
        setLayout(layout);
    }

    void setLayout(int layout) {
        layout_ = ((layout % 3) + 3) % 3;
        if (layout_ == 1) {
            name_ = "PIER SLALOM";
            points_ = {
                {{-260.0f, 1540.0f}, 280.0f, Surface::Asphalt},
                {{460.0f, 1460.0f}, 255.0f, Surface::Asphalt},
                {{760.0f, 900.0f}, 215.0f, Surface::Boardwalk},
                {{520.0f, 420.0f}, 205.0f, Surface::Boardwalk},
                {{1120.0f, 120.0f}, 205.0f, Surface::Boardwalk},
                {{1720.0f, -260.0f}, 230.0f, Surface::Asphalt},
                {{1640.0f, -920.0f}, 220.0f, Surface::Asphalt},
                {{920.0f, -1280.0f}, 205.0f, Surface::Tunnel},
                {{140.0f, -1140.0f}, 205.0f, Surface::Tunnel},
                {{-420.0f, -1500.0f}, 215.0f, Surface::Asphalt},
                {{-1060.0f, -1120.0f}, 205.0f, Surface::Boardwalk},
                {{-1740.0f, -1260.0f}, 200.0f, Surface::Boardwalk},
                {{-2280.0f, -680.0f}, 215.0f, Surface::Boardwalk},
                {{-2060.0f, -160.0f}, 205.0f, Surface::Boardwalk},
                {{-2460.0f, 360.0f}, 230.0f, Surface::Asphalt},
                {{-1960.0f, 1040.0f}, 250.0f, Surface::Asphalt},
                {{-1120.0f, 1180.0f}, 240.0f, Surface::Asphalt},
            };
        } else if (layout_ == 2) {
            name_ = "CAVEBACK RUN";
            points_ = {
                {{-220.0f, 1900.0f}, 335.0f, Surface::Asphalt},
                {{760.0f, 1780.0f}, 330.0f, Surface::Asphalt},
                {{1560.0f, 1180.0f}, 300.0f, Surface::Asphalt},
                {{2140.0f, 320.0f}, 280.0f, Surface::Asphalt},
                {{2700.0f, -360.0f}, 260.0f, Surface::Boardwalk},
                {{2300.0f, -1040.0f}, 235.0f, Surface::Boardwalk},
                {{1500.0f, -1260.0f}, 245.0f, Surface::Tunnel},
                {{620.0f, -1720.0f}, 250.0f, Surface::Tunnel},
                {{-220.0f, -1880.0f}, 260.0f, Surface::Tunnel},
                {{-840.0f, -1300.0f}, 240.0f, Surface::Asphalt},
                {{-1560.0f, -1480.0f}, 245.0f, Surface::Asphalt},
                {{-2380.0f, -840.0f}, 260.0f, Surface::Boardwalk},
                {{-2600.0f, 80.0f}, 270.0f, Surface::Boardwalk},
                {{-2060.0f, 880.0f}, 295.0f, Surface::Asphalt},
                {{-1160.0f, 1420.0f}, 315.0f, Surface::Asphalt},
            };
        } else {
            name_ = "HARBOR GP";
            points_ = {
                {{-180.0f, 1680.0f}, 320.0f, Surface::Asphalt},
                {{620.0f, 1580.0f}, 300.0f, Surface::Asphalt},
                {{1080.0f, 1180.0f}, 260.0f, Surface::Boardwalk},
                {{860.0f, 720.0f}, 220.0f, Surface::Boardwalk},
                {{1480.0f, 520.0f}, 230.0f, Surface::Boardwalk},
                {{2180.0f, 80.0f}, 260.0f, Surface::Asphalt},
                {{2300.0f, -620.0f}, 250.0f, Surface::Asphalt},
                {{1700.0f, -1160.0f}, 225.0f, Surface::Tunnel},
                {{880.0f, -1460.0f}, 230.0f, Surface::Tunnel},
                {{240.0f, -1260.0f}, 220.0f, Surface::Tunnel},
                {{-380.0f, -1680.0f}, 235.0f, Surface::Asphalt},
                {{-980.0f, -1160.0f}, 230.0f, Surface::Asphalt},
                {{-1580.0f, -1280.0f}, 215.0f, Surface::Boardwalk},
                {{-2280.0f, -680.0f}, 240.0f, Surface::Boardwalk},
                {{-2440.0f, -60.0f}, 220.0f, Surface::Boardwalk},
                {{-2080.0f, 420.0f}, 230.0f, Surface::Boardwalk},
                {{-2440.0f, 920.0f}, 255.0f, Surface::Asphalt},
                {{-1660.0f, 1460.0f}, 295.0f, Surface::Asphalt},
                {{-880.0f, 1340.0f}, 305.0f, Surface::Asphalt},
            };
        }
        build();
    }

    const std::vector<TrackSegment>& segments() const { return segments_; }
    float totalLength() const { return totalLength_; }
    const std::string& name() const { return name_; }
    float minX() const { return minX_; }
    float maxX() const { return maxX_; }
    float minY() const { return minY_; }
    float maxY() const { return maxY_; }

    TrackQuery query(Vec2 pos) const {
        TrackQuery best;
        float bestDistSq = std::numeric_limits<float>::max();
        for (size_t i = 0; i < segments_.size(); ++i) {
            const TrackSegment& s = segments_[i];
            Vec2 ab = s.b - s.a;
            float t = std::clamp(dot(pos - s.a, ab) / std::max(1.0f, dot(ab, ab)), 0.0f, 1.0f);
            Vec2 p = lerp(s.a, s.b, t);
            Vec2 diff = pos - p;
            float distSq = lengthSq(diff);
            if (distSq < bestDistSq) {
                Vec2 tangent = normalize(ab);
                Vec2 normal{-tangent.y, tangent.x};
                bestDistSq = distSq;
                best.point = p;
                best.tangent = tangent;
                best.normal = normal;
                best.progress = s.start + s.length * t;
                best.signedDistance = dot(diff, normal);
                best.distance = std::sqrt(distSq);
                best.halfWidth = lerp(s.widthA, s.widthB, t) * 0.5f;
                best.t = t;
                best.segment = static_cast<int>(i);
                best.surface = s.surface;
            }
        }
        return best;
    }

    TrackQuery sample(float progress) const {
        float p = wrapProgress(progress, totalLength_);
        for (size_t i = 0; i < segments_.size(); ++i) {
            const TrackSegment& s = segments_[i];
            if (p <= s.start + s.length || i == segments_.size() - 1) {
                float t = std::clamp((p - s.start) / std::max(1.0f, s.length), 0.0f, 1.0f);
                Vec2 tangent = normalize(s.b - s.a);
                Vec2 normal{-tangent.y, tangent.x};
                TrackQuery q;
                q.point = lerp(s.a, s.b, t);
                q.tangent = tangent;
                q.normal = normal;
                q.progress = p;
                q.halfWidth = lerp(s.widthA, s.widthB, t) * 0.5f;
                q.t = t;
                q.segment = static_cast<int>(i);
                q.surface = s.surface;
                return q;
            }
        }
        return query(points_.front().pos);
    }

private:
    void build() {
        totalLength_ = 0.0f;
        segments_.clear();
        minX_ = minY_ = std::numeric_limits<float>::max();
        maxX_ = maxY_ = -std::numeric_limits<float>::max();
        for (size_t i = 0; i < points_.size(); ++i) {
            const TrackPoint& a = points_[i];
            const TrackPoint& b = points_[(i + 1) % points_.size()];
            TrackSegment s;
            s.a = a.pos;
            s.b = b.pos;
            s.start = totalLength_;
            s.length = length(b.pos - a.pos);
            s.widthA = a.width;
            s.widthB = b.width;
            s.surface = a.surface;
            totalLength_ += s.length;
            segments_.push_back(s);
            float pad = std::max(a.width, b.width) * 0.5f + 520.0f;
            minX_ = std::min(minX_, std::min(a.pos.x, b.pos.x) - pad);
            maxX_ = std::max(maxX_, std::max(a.pos.x, b.pos.x) + pad);
            minY_ = std::min(minY_, std::min(a.pos.y, b.pos.y) - pad);
            maxY_ = std::max(maxY_, std::max(a.pos.y, b.pos.y) + pad);
        }
    }

    int layout_ = 0;
    std::string name_ = "HARBOR GP";
    std::vector<TrackPoint> points_;
    std::vector<TrackSegment> segments_;
    float totalLength_ = 1.0f;
    float minX_ = -2600.0f;
    float maxX_ = 2600.0f;
    float minY_ = -2000.0f;
    float maxY_ = 2000.0f;
};

struct Racer {
    std::string name;
    std::string role;
    uint32_t primary;
    uint32_t accent;
};

struct KartDef {
    std::string name;
    uint32_t body;
    uint32_t trim;
    float maxSpeed = 540.0f;
    float accel = 640.0f;
    float brake = 920.0f;
    float reverse = 430.0f;
    float turnRate = 2.55f;
    float grip = 9.0f;
};

std::vector<Racer> makeRacers() {
    return {
        {"CORAL ACE", "ADAPTED ROSTER", rgb(240, 86, 75), rgb(255, 214, 90)},
        {"BOLT REX", "ADAPTED ROSTER", rgb(49, 140, 240), rgb(255, 246, 128)},
        {"MARA WAVE", "ADAPTED ROSTER", rgb(40, 188, 158), rgb(255, 255, 255)},
        {"KITO DRIFT", "ADAPTED ROSTER", rgb(122, 92, 235), rgb(255, 175, 55)},
        {"LUX NOVA", "ADAPTED ROSTER", rgb(234, 78, 176), rgb(60, 240, 225)},
        {"SPROCKET", "ADAPTED ROSTER", rgb(240, 152, 54), rgb(55, 55, 60)},
        {"VEGA GLOW", "ADAPTED ROSTER", rgb(96, 220, 92), rgb(42, 70, 60)},
        {"RIPTIDE", "ADAPTED ROSTER", rgb(34, 102, 180), rgb(240, 240, 240)},
        {"FLINT MAX", "ADAPTED ROSTER", rgb(160, 102, 66), rgb(244, 210, 150)},
        {"JUNO STAR", "ADAPTED ROSTER", rgb(250, 216, 78), rgb(50, 70, 120)},
    };
}

std::vector<KartDef> makeKarts() {
    return {
        {"SAND RAIL", rgb(220, 64, 58), rgb(255, 232, 100), 548.0f, 650.0f, 930.0f, 430.0f, 2.58f, 9.1f},
        {"TIDE BUGGY", rgb(34, 143, 230), rgb(235, 250, 255), 542.0f, 675.0f, 920.0f, 420.0f, 2.65f, 8.9f},
        {"REEF ROD", rgb(36, 186, 145), rgb(245, 188, 64), 558.0f, 628.0f, 900.0f, 410.0f, 2.48f, 9.4f},
        {"DOCK DASH", rgb(128, 84, 48), rgb(250, 212, 82), 536.0f, 695.0f, 940.0f, 445.0f, 2.72f, 8.8f},
        {"SUN SKIPPER", rgb(246, 184, 42), rgb(60, 70, 86), 552.0f, 642.0f, 910.0f, 425.0f, 2.54f, 9.2f},
        {"CAVE RUNNER", rgb(90, 94, 108), rgb(80, 220, 230), 566.0f, 604.0f, 940.0f, 405.0f, 2.38f, 9.6f},
        {"PALM GT", rgb(86, 194, 88), rgb(248, 246, 220), 540.0f, 684.0f, 930.0f, 435.0f, 2.70f, 8.7f},
        {"HARBOR 8", rgb(226, 74, 168), rgb(58, 210, 230), 560.0f, 620.0f, 915.0f, 420.0f, 2.50f, 9.3f},
    };
}

struct KartState {
    Vec2 pos;
    Vec2 vel;
    float yaw = 0.0f;
    float yawVel = 0.0f;
    float progress = 0.0f;
    float lastSafeProgress = 0.0f;
    float lineOffset = 0.0f;
    int lap = 0;
    int racerIndex = 0;
    int kartIndex = 0;
    bool player = false;
    bool wrongWay = false;
    float wrongWayTimer = 0.0f;
};

struct DriveInput {
    float steer = 0.0f;
    float throttle = 0.0f;
    float brake = 0.0f;
};

void placeOnTrack(const Track& track, KartState& state, float progress, float lineOffset) {
    TrackQuery q = track.sample(progress);
    state.pos = q.point + q.normal * lineOffset;
    state.vel = q.tangent * 5.0f;
    state.yaw = angleOf(q.tangent);
    state.yawVel = 0.0f;
    state.progress = q.progress;
    state.lastSafeProgress = q.progress;
    state.lineOffset = lineOffset;
}

void applyKartPhysics(const Track& track, const KartDef& kart, KartState& state, const DriveInput& input, float dt) {
    TrackQuery before = track.query(state.pos);
    Vec2 forward = fromAngle(state.yaw);
    Vec2 right{-forward.y, forward.x};

    float roadRatio = before.distance / std::max(1.0f, before.halfWidth);
    bool onRoad = roadRatio <= 1.0f;
    bool onShoulder = roadRatio <= 1.35f;

    float gripFactor = onRoad ? 1.0f : (onShoulder ? 0.50f : 0.26f);
    float speedFactor = onRoad ? 1.0f : (onShoulder ? 0.62f : 0.34f);
    float dragFactor = onRoad ? 1.0f : (onShoulder ? 3.0f : 6.0f);
    if (onRoad) {
        float edgeLoad = std::clamp((roadRatio - 0.68f) / 0.32f, 0.0f, 1.0f);
        gripFactor *= 1.0f - edgeLoad * 0.18f;
        speedFactor *= 1.0f - edgeLoad * 0.10f;
        dragFactor *= 1.0f + edgeLoad * 0.34f;
    }
    if (before.surface == Surface::Boardwalk) {
        gripFactor *= 0.93f;
        dragFactor *= 1.04f;
    } else if (before.surface == Surface::Tunnel) {
        gripFactor *= 1.08f;
    }

    float speedForward = dot(state.vel, forward);
    float speedSide = dot(state.vel, right);
    float absSpeed = std::abs(speedForward);
    float steeringAtSpeed = std::clamp(absSpeed / 260.0f, 0.20f, 1.0f);
    float speedT = std::clamp(absSpeed / std::max(1.0f, kart.maxSpeed), 0.0f, 1.15f);
    float highSpeedUndersteer = lerp(1.10f, 0.66f, std::clamp(speedT, 0.0f, 1.0f));
    bool driftInput = input.brake > 0.22f && std::abs(input.steer) > 0.34f && speedForward > 155.0f;
    float drift = driftInput ? 1.34f : 1.0f;
    float targetYawVel = input.steer * kart.turnRate * steeringAtSpeed * highSpeedUndersteer * drift;
    if (speedForward < -20.0f) {
        targetYawVel *= -0.55f;
    }
    state.yawVel += (targetYawVel - state.yawVel) * std::clamp(8.5f * dt, 0.0f, 1.0f);
    state.yaw = wrapAngle(state.yaw + state.yawVel * dt);

    forward = fromAngle(state.yaw);
    right = {-forward.y, forward.x};
    speedForward = dot(state.vel, forward);
    speedSide = dot(state.vel, right);

    float maxSpeed = kart.maxSpeed * speedFactor;
    float engineCurve = std::clamp(1.0f - std::max(0.0f, speedForward) / std::max(1.0f, maxSpeed), 0.12f, 1.0f);
    float accel = input.throttle * kart.accel * engineCurve;
    float brake = 0.0f;
    if (input.brake > 0.01f) {
        brake = (speedForward > 24.0f) ? input.brake * kart.brake : input.brake * kart.reverse;
    }

    float rolling = 1.45f * dragFactor;
    float air = 0.0020f * speedForward * std::abs(speedForward);
    float longitudinalAccel = accel - brake - rolling * speedForward - air;
    speedForward += longitudinalAccel * dt;

    float sideGrip = kart.grip * gripFactor;
    if (drift > 1.0f) {
        sideGrip *= 0.48f;
    }
    speedSide -= speedSide * std::clamp(sideGrip * dt, 0.0f, 0.92f);
    float slipLoss = std::clamp(std::abs(speedSide) / 360.0f, 0.0f, 1.0f) * (driftInput ? 14.0f : 42.0f);
    if (speedForward > 0.0f) {
        speedForward = std::max(0.0f, speedForward - slipLoss * dt);
    }
    if (!onRoad) {
        speedSide -= speedSide * std::clamp(3.2f * dt, 0.0f, 0.85f);
    }

    state.vel = forward * speedForward + right * speedSide;
    float maxMagnitude = kart.maxSpeed * 1.18f;
    float currentSpeed = length(state.vel);
    if (currentSpeed > maxMagnitude) {
        state.vel *= maxMagnitude / currentSpeed;
    }
    state.pos += state.vel * dt;

    TrackQuery after = track.query(state.pos);
    float softLimit = after.halfWidth + 28.0f;
    float hardLimit = after.halfWidth + 88.0f;
    if (std::abs(after.signedDistance) > softLimit) {
        float sign = after.signedDistance < 0.0f ? -1.0f : 1.0f;
        Vec2 limitPoint = after.point + after.normal * (sign * softLimit);
        Vec2 correction = limitPoint - state.pos;
        state.pos += correction * 0.72f;
        Vec2 n = after.normal * sign;
        float intoWall = dot(state.vel, n);
        if (intoWall > 0.0f) {
            state.vel -= n * (intoWall * 1.55f);
            state.vel *= 0.62f;
        }
    }
    if (std::abs(after.signedDistance) > hardLimit + 180.0f) {
        placeOnTrack(track, state, state.lastSafeProgress, state.lineOffset);
    }

    float prev = state.progress;
    after = track.query(state.pos);
    float delta = after.progress - prev;
    if (delta < -track.totalLength() * 0.5f) {
        ++state.lap;
    } else if (delta > track.totalLength() * 0.5f) {
        --state.lap;
    } else if (state.player) {
        if (delta < -12.0f && length(state.vel) > 80.0f) {
            state.wrongWayTimer += dt;
        } else {
            state.wrongWayTimer = std::max(0.0f, state.wrongWayTimer - dt * 2.0f);
        }
        state.wrongWay = state.wrongWayTimer > 0.55f;
    }
    state.progress = after.progress;
    if (after.distance <= after.halfWidth * 0.82f && dot(state.vel, after.tangent) > 45.0f) {
        state.lastSafeProgress = after.progress;
    }
}

DriveInput aiInputFor(const Track& track, const KartState& state) {
    float speed = length(state.vel);
    float lookAhead = 260.0f + std::clamp(speed * 0.92f, 0.0f, 520.0f);
    TrackQuery target = track.sample(state.progress + lookAhead);
    TrackQuery nearTarget = track.sample(state.progress + lookAhead * 0.55f);
    Vec2 targetPoint = target.point + target.normal * state.lineOffset;
    Vec2 toTarget = targetPoint - state.pos;
    float angleError = wrapAngle(angleOf(toTarget) - state.yaw);
    float bend = std::abs(wrapAngle(angleOf(target.tangent) - angleOf(nearTarget.tangent)));
    DriveInput input;
    input.steer = std::clamp(angleError * 1.55f, -1.0f, 1.0f);
    input.throttle = 1.0f;
    float sharpness = std::max(std::abs(angleError), bend * 1.35f);
    if (sharpness > 0.46f && speed > 180.0f) {
        input.brake = std::clamp((sharpness - 0.40f) * 0.86f, 0.0f, 0.62f);
        input.throttle = std::clamp(0.86f - input.brake * 0.82f, 0.28f, 1.0f);
    }
    return input;
}

struct Prop {
    float progress = 0.0f;
    float offset = 0.0f;
    int type = 0;
    float scale = 1.0f;
};

std::vector<Prop> makeProps(float trackLength = 9800.0f) {
    std::vector<Prop> props = {
        {260.0f, -360.0f, 0, 1.0f}, {620.0f, 380.0f, 0, 0.9f},  {1030.0f, -320.0f, 1, 1.0f},
        {1480.0f, 330.0f, 2, 1.1f}, {2020.0f, -380.0f, 3, 1.0f}, {2500.0f, 360.0f, 0, 1.2f},
        {3060.0f, -330.0f, 4, 1.0f}, {3560.0f, 330.0f, 1, 1.0f}, {4100.0f, -360.0f, 2, 1.0f},
        {4680.0f, 380.0f, 0, 0.9f}, {5320.0f, -340.0f, 3, 1.2f}, {5860.0f, 350.0f, 4, 1.0f},
        {6460.0f, -330.0f, 1, 0.95f}, {7080.0f, 370.0f, 0, 1.1f}, {7750.0f, -360.0f, 2, 1.0f},
        {8380.0f, 360.0f, 0, 1.0f}, {9000.0f, -390.0f, 4, 1.0f}, {9630.0f, 360.0f, 1, 1.0f},
    };
    for (float p = 10100.0f; p < trackLength; p += 520.0f) {
        int type = static_cast<int>(p / 520.0f) % 5;
        float side = (static_cast<int>(p / 260.0f) % 2 == 0) ? -1.0f : 1.0f;
        props.push_back({p, side * (320.0f + std::fmod(p, 190.0f)), type, 0.85f + std::fmod(p, 180.0f) / 600.0f});
    }
    return props;
}

Vec2 project(Vec2 world, const Camera& camera) {
    Vec2 d = world - camera.pos;
    Vec2 forward = fromAngle(camera.yaw);
    Vec2 right{-forward.y, forward.x};
    return {camera.screenW * 0.5f + dot(d, right) * camera.zoom,
            camera.screenH * 0.63f - dot(d, forward) * camera.zoom};
}

void drawWorldLine(Renderer& r, Vec2 a, Vec2 b, const Camera& camera, int thickness, uint32_t color) {
    r.drawLine(project(a, camera), project(b, camera), thickness, color);
}

void drawRibbon(Renderer& r, Vec2 a, Vec2 b, float halfWidth, const Camera& camera, uint32_t color) {
    Vec2 tangent = normalize(b - a);
    Vec2 normal{-tangent.y, tangent.x};
    std::vector<Vec2> poly = {
        project(a + normal * halfWidth, camera),
        project(b + normal * halfWidth, camera),
        project(b - normal * halfWidth, camera),
        project(a - normal * halfWidth, camera),
    };
    r.fillPolygon(poly, color);
    int radius = static_cast<int>(std::ceil(halfWidth * camera.zoom));
    Vec2 sa = project(a, camera);
    Vec2 sb = project(b, camera);
    r.drawCircle(static_cast<int>(sa.x), static_cast<int>(sa.y), radius, color);
    r.drawCircle(static_cast<int>(sb.x), static_cast<int>(sb.y), radius, color);
}

uint32_t surfaceColor(Surface surface) {
    switch (surface) {
        case Surface::Boardwalk: return rgb(118, 83, 50);
        case Surface::Tunnel: return rgb(65, 69, 76);
        case Surface::Asphalt:
        default: return rgb(83, 91, 94);
    }
}

std::optional<Projection> projectGround(Vec2 world, const Camera& camera) {
    Vec2 d = world - camera.pos;
    Vec2 forward = fromAngle(camera.yaw);
    Vec2 right{-forward.y, forward.x};
    float depth = dot(d, forward);
    if (depth < 35.0f) {
        return std::nullopt;
    }
    float lateral = dot(d, right);
    float scale = camera.fov / depth;
    Projection p;
    p.depth = depth;
    p.scale = scale;
    p.screen = {camera.screenW * 0.5f + lateral * scale, camera.horizon + camera.height * scale};
    if (p.screen.x < -camera.screenW * 0.75f || p.screen.x > camera.screenW * 1.75f ||
        p.screen.y < -camera.screenH * 0.5f || p.screen.y > camera.screenH * 1.4f) {
        return std::nullopt;
    }
    return p;
}

bool perspectiveQuad(Renderer& r, const Camera& camera, Vec2 a, Vec2 b, Vec2 c, Vec2 d, uint32_t color) {
    auto pa = projectGround(a, camera);
    auto pb = projectGround(b, camera);
    auto pc = projectGround(c, camera);
    auto pd = projectGround(d, camera);
    if (!pa || !pb || !pc || !pd) {
        return false;
    }
    r.fillPolygon({pa->screen, pb->screen, pc->screen, pd->screen}, color);
    return true;
}

void drawPerspectiveBackground(Renderer& r, const Camera& camera, float animTime) {
    int horizon = static_cast<int>(camera.horizon);
    for (int y = 0; y < horizon; y += 3) {
        float t = static_cast<float>(y) / std::max(1, horizon);
        uint32_t color = rgb(static_cast<uint8_t>(35 + t * 42), static_cast<uint8_t>(116 + t * 54),
                             static_cast<uint8_t>(150 + t * 58));
        r.fillRect(0, y, r.width(), 3, color);
    }
    for (int y = horizon; y < r.height(); y += 3) {
        float t = static_cast<float>(y - horizon) / std::max(1, r.height() - horizon);
        uint32_t color = rgb(static_cast<uint8_t>(54 + t * 86), static_cast<uint8_t>(144 + t * 50),
                             static_cast<uint8_t>(166 - t * 62));
        r.fillRect(0, y, r.width(), 3, color);
    }
    r.fillRect(0, horizon - 2, r.width(), 4, rgb(225, 215, 155));
    for (int i = 0; i < 20; ++i) {
        int y = horizon + 18 + i * 24;
        int shift = static_cast<int>(std::sin(animTime * 1.2f + i * 0.7f) * 70.0f);
        r.drawLine({static_cast<float>(-80 + shift), static_cast<float>(y)},
                   {static_cast<float>(r.width() + 80 + shift), static_cast<float>(y + 12)}, 1,
                   rgb(67, 158, 178));
    }
}

void drawPerspectiveTrack(Renderer& r, const Track& track, const Camera& camera, float playerProgress) {
    constexpr float nearDist = 45.0f;
    constexpr float farDist = 4300.0f;
    constexpr float step = 58.0f;
    for (float d = farDist; d >= nearDist; d -= step) {
        TrackQuery q0 = track.sample(playerProgress + d);
        TrackQuery q1 = track.sample(playerProgress + d + step);
        float shoulder0 = q0.halfWidth + 94.0f;
        float shoulder1 = q1.halfWidth + 94.0f;
        uint32_t shoulder = q0.surface == Surface::Boardwalk ? rgb(85, 59, 38) : rgb(186, 154, 94);
        perspectiveQuad(r, camera, q0.point - q0.normal * shoulder0, q0.point + q0.normal * shoulder0,
                        q1.point + q1.normal * shoulder1, q1.point - q1.normal * shoulder1, shoulder);
        perspectiveQuad(r, camera, q0.point - q0.normal * (q0.halfWidth + 8.0f),
                        q0.point + q0.normal * (q0.halfWidth + 8.0f),
                        q1.point + q1.normal * (q1.halfWidth + 8.0f),
                        q1.point - q1.normal * (q1.halfWidth + 8.0f), rgb(52, 50, 45));
        perspectiveQuad(r, camera, q0.point - q0.normal * q0.halfWidth, q0.point + q0.normal * q0.halfWidth,
                        q1.point + q1.normal * q1.halfWidth, q1.point - q1.normal * q1.halfWidth,
                        surfaceColor(q0.surface));

        if (static_cast<int>((playerProgress + d) / 210.0f) % 2 == 0) {
            float stripe = std::min(q0.halfWidth * 0.04f, 10.0f);
            perspectiveQuad(r, camera, q0.point - q0.normal * stripe, q0.point + q0.normal * stripe,
                            q1.point + q1.normal * stripe, q1.point - q1.normal * stripe,
                            q0.surface == Surface::Tunnel ? rgb(150, 156, 158) : rgb(232, 224, 178));
        }
    }
}

void drawPerspectiveProp(Renderer& r, const Track& track, const Prop& prop, const Camera& camera) {
    TrackQuery q = track.sample(prop.progress);
    Vec2 pos = q.point + q.normal * prop.offset;
    auto projected = projectGround(pos, camera);
    if (!projected) {
        return;
    }
    int size = std::clamp(static_cast<int>(projected->scale * 46.0f * prop.scale), 3, 90);
    int x = static_cast<int>(projected->screen.x);
    int y = static_cast<int>(projected->screen.y);
    if (prop.type == 0) {
        r.fillRect(x - size / 6, y - size * 2, std::max(2, size / 3), size * 2, rgb(118, 75, 42));
        r.drawCircle(x - size / 2, y - size * 2, size / 2, rgb(56, 145, 78));
        r.drawCircle(x + size / 2, y - size * 2, size / 2, rgb(43, 128, 72));
        r.drawCircle(x, y - size * 5 / 2, size / 2, rgb(74, 166, 86));
    } else if (prop.type == 4) {
        std::vector<Vec2> boat = {{static_cast<float>(x - size * 2), static_cast<float>(y)},
                                  {static_cast<float>(x + size * 2), static_cast<float>(y)},
                                  {static_cast<float>(x + size), static_cast<float>(y - size)},
                                  {static_cast<float>(x - size), static_cast<float>(y - size)}};
        r.fillPolygon(boat, rgb(236, 230, 205));
        r.drawLine({static_cast<float>(x), static_cast<float>(y - size)},
                   {static_cast<float>(x), static_cast<float>(y - size * 3)}, std::max(1, size / 12), rgb(60, 60, 60));
    } else {
        r.drawCircle(x, y - size / 2, size / 2, prop.type == 2 ? rgb(36, 58, 68) : rgb(220, 80, 56));
    }
}

void drawPerspectiveKart(Renderer& r, const KartState& state, const KartDef& kart, const Racer& racer,
                         const Camera& camera) {
    auto projected = projectGround(state.pos, camera);
    if (!projected) {
        return;
    }
    int w = std::clamp(static_cast<int>(projected->scale * 86.0f), 18, 170);
    int h = std::clamp(static_cast<int>(projected->scale * 62.0f), 12, 128);
    int x = static_cast<int>(projected->screen.x);
    int y = static_cast<int>(projected->screen.y);
    r.drawCircle(x, y + h / 4, std::max(3, w / 2), rgb(24, 34, 38));
    std::vector<Vec2> body = {{static_cast<float>(x - w / 2), static_cast<float>(y)},
                              {static_cast<float>(x + w / 2), static_cast<float>(y)},
                              {static_cast<float>(x + w * 2 / 5), static_cast<float>(y - h)},
                              {static_cast<float>(x - w * 2 / 5), static_cast<float>(y - h)}};
    r.fillPolygon(body, kart.body);
    r.fillRect(x - w / 4, y - h * 3 / 4, w / 2, std::max(3, h / 3), shade(racer.primary, 0.76f));
    r.fillRect(x - w / 2, y - h / 6, std::max(3, w / 5), std::max(3, h / 5), rgb(16, 16, 16));
    r.fillRect(x + w * 3 / 10, y - h / 6, std::max(3, w / 5), std::max(3, h / 5), rgb(16, 16, 16));
}

void drawPlayerHood(Renderer& r, const KartDef& kart, const Racer& racer, float speed) {
    float speedT = std::clamp(speed / 560.0f, 0.0f, 1.0f);
    int w = r.width();
    int h = r.height();
    int cx = w / 2;
    int hoodTop = static_cast<int>(h - lerp(112.0f, 176.0f, speedT));
    int hoodHalf = static_cast<int>(lerp(w * 0.25f, w * 0.17f, speedT));
    std::vector<Vec2> hood = {{static_cast<float>(cx - hoodHalf), static_cast<float>(h + 28)},
                              {static_cast<float>(cx + hoodHalf), static_cast<float>(h + 28)},
                              {static_cast<float>(cx + hoodHalf * 2 / 3), static_cast<float>(hoodTop)},
                              {static_cast<float>(cx - hoodHalf * 2 / 3), static_cast<float>(hoodTop)}};
    r.fillPolygon(hood, kart.body);
    std::vector<Vec2> stripe = {{static_cast<float>(cx - hoodHalf / 5), static_cast<float>(h + 20)},
                                {static_cast<float>(cx + hoodHalf / 5), static_cast<float>(h + 20)},
                                {static_cast<float>(cx + hoodHalf / 8), static_cast<float>(hoodTop + 8)},
                                {static_cast<float>(cx - hoodHalf / 8), static_cast<float>(hoodTop + 8)}};
    r.fillPolygon(stripe, kart.trim);
    r.fillRect(cx - hoodHalf / 4, hoodTop + 14, hoodHalf / 2, 22, shade(racer.primary, 0.75f));
    if (speedT > 0.45f) {
        int wheelY = h - 32;
        r.drawCircle(cx - hoodHalf - 12, wheelY, 26, rgb(14, 14, 14));
        r.drawCircle(cx + hoodHalf + 12, wheelY, 26, rgb(14, 14, 14));
    }
}

void drawTrack(Renderer& r, const Track& track, const Camera& camera) {
    const uint32_t sand = rgb(202, 176, 115);
    const uint32_t wetSand = rgb(174, 144, 91);
    const uint32_t edge = rgb(76, 72, 62);
    for (const TrackSegment& s : track.segments()) {
        float wide = std::max(s.widthA, s.widthB) * 0.5f + 260.0f;
        drawRibbon(r, s.a, s.b, wide, camera, sand);
    }
    for (const TrackSegment& s : track.segments()) {
        float wide = std::max(s.widthA, s.widthB) * 0.5f + 76.0f;
        uint32_t shoulder = s.surface == Surface::Boardwalk ? rgb(91, 64, 41) : wetSand;
        drawRibbon(r, s.a, s.b, wide, camera, shoulder);
    }
    for (const TrackSegment& s : track.segments()) {
        float half = std::max(s.widthA, s.widthB) * 0.5f + 10.0f;
        drawRibbon(r, s.a, s.b, half, camera, edge);
    }
    for (const TrackSegment& s : track.segments()) {
        float half = std::max(s.widthA, s.widthB) * 0.5f;
        drawRibbon(r, s.a, s.b, half, camera, surfaceColor(s.surface));
    }

    for (float p = 0.0f; p < track.totalLength(); p += 155.0f) {
        TrackQuery q = track.sample(p);
        if (q.surface == Surface::Boardwalk) {
            drawWorldLine(r, q.point - q.normal * (q.halfWidth * 0.9f), q.point + q.normal * (q.halfWidth * 0.9f),
                          camera, 1, rgb(82, 58, 38));
        } else if (static_cast<int>(p / 155.0f) % 2 == 0) {
            drawWorldLine(r, q.point - q.tangent * 35.0f, q.point + q.tangent * 35.0f, camera, 2,
                          q.surface == Surface::Tunnel ? rgb(140, 148, 152) : rgb(225, 215, 170));
        }
    }

    TrackQuery start = track.sample(0.0f);
    for (int i = -3; i <= 2; ++i) {
        Vec2 center = start.point + start.normal * (i * start.halfWidth / 3.0f + start.halfWidth / 6.0f);
        uint32_t color = (i & 1) ? rgb(24, 24, 24) : rgb(240, 240, 228);
        std::vector<Vec2> cell = {
            project(center - start.normal * 24.0f - start.tangent * 22.0f, camera),
            project(center + start.normal * 24.0f - start.tangent * 22.0f, camera),
            project(center + start.normal * 24.0f + start.tangent * 22.0f, camera),
            project(center - start.normal * 24.0f + start.tangent * 22.0f, camera),
        };
        r.fillPolygon(cell, color);
    }
}

void drawProp(Renderer& r, const Track& track, const Prop& prop, const Camera& camera, float anim) {
    TrackQuery q = track.sample(prop.progress);
    Vec2 pos = q.point + q.normal * prop.offset;
    Vec2 screen = project(pos, camera);
    if (screen.x < -80.0f || screen.x > camera.screenW + 80.0f || screen.y < -80.0f ||
        screen.y > camera.screenH + 80.0f) {
        return;
    }
    int x = static_cast<int>(screen.x);
    int y = static_cast<int>(screen.y);
    int s = std::max(2, static_cast<int>(14.0f * prop.scale * camera.zoom / 0.36f));
    switch (prop.type) {
        case 0: {
            r.drawLine({static_cast<float>(x), static_cast<float>(y + s * 2)},
                       {static_cast<float>(x + s / 2), static_cast<float>(y - s)}, std::max(2, s / 3),
                       rgb(112, 72, 42));
            r.drawCircle(x - s, y - s, s, rgb(54, 142, 82));
            r.drawCircle(x + s, y - s, s, rgb(42, 126, 74));
            r.drawCircle(x, y - s * 2, s, rgb(70, 162, 84));
            break;
        }
        case 1:
            r.fillRect(x - s, y - s, s * 2, s * 2, rgb(134, 83, 42));
            r.drawLine({static_cast<float>(x - s), static_cast<float>(y)},
                       {static_cast<float>(x + s), static_cast<float>(y)}, 1, rgb(84, 52, 28));
            r.drawLine({static_cast<float>(x), static_cast<float>(y - s)},
                       {static_cast<float>(x), static_cast<float>(y + s)}, 1, rgb(84, 52, 28));
            break;
        case 2: {
            std::vector<Vec2> fin = {{static_cast<float>(x - s), static_cast<float>(y + s)},
                                     {static_cast<float>(x), static_cast<float>(y - s - static_cast<int>(std::sin(anim) * 3.0f))},
                                     {static_cast<float>(x + s), static_cast<float>(y + s)}};
            r.fillPolygon(fin, rgb(36, 58, 68));
            break;
        }
        case 3:
            r.drawCircle(x, y, s, rgb(228, 56, 48));
            r.drawCircle(x, y, std::max(1, s / 2), rgb(238, 238, 220));
            break;
        case 4: {
            std::vector<Vec2> boat = {{static_cast<float>(x - s * 2), static_cast<float>(y + s)},
                                      {static_cast<float>(x + s * 2), static_cast<float>(y + s)},
                                      {static_cast<float>(x + s), static_cast<float>(y - s)},
                                      {static_cast<float>(x - s), static_cast<float>(y - s)}};
            r.fillPolygon(boat, rgb(226, 226, 210));
            r.drawLine({static_cast<float>(x), static_cast<float>(y - s)},
                       {static_cast<float>(x), static_cast<float>(y - s * 3)}, 1, rgb(70, 70, 70));
            std::vector<Vec2> sail = {{static_cast<float>(x), static_cast<float>(y - s * 3)},
                                      {static_cast<float>(x), static_cast<float>(y - s)},
                                      {static_cast<float>(x + s * 2), static_cast<float>(y - s)}};
            r.fillPolygon(sail, rgb(250, 214, 92));
            break;
        }
        default:
            break;
    }
}

void drawKart(Renderer& r, const KartState& state, const KartDef& kart, const Racer& racer, const Camera& camera) {
    Vec2 f = fromAngle(state.yaw);
    Vec2 right{-f.y, f.x};
    float halfL = state.player ? 38.0f : 34.0f;
    float halfW = state.player ? 22.0f : 20.0f;
    Vec2 shadow = {8.0f / camera.zoom, 10.0f / camera.zoom};
    std::vector<Vec2> shadowPoly = {
        project(state.pos + shadow + f * halfL + right * halfW, camera),
        project(state.pos + shadow + f * halfL - right * halfW, camera),
        project(state.pos + shadow - f * halfL - right * halfW, camera),
        project(state.pos + shadow - f * halfL + right * halfW, camera),
    };
    r.fillPolygon(shadowPoly, rgb(28, 42, 48));

    std::vector<Vec2> body = {
        project(state.pos + f * halfL + right * halfW, camera),
        project(state.pos + f * halfL - right * halfW, camera),
        project(state.pos - f * halfL - right * halfW, camera),
        project(state.pos - f * halfL + right * halfW, camera),
    };
    r.fillPolygon(body, kart.body);

    std::vector<Vec2> nose = {
        project(state.pos + f * (halfL + 10.0f), camera),
        project(state.pos + f * 8.0f + right * (halfW * 0.82f), camera),
        project(state.pos + f * 8.0f - right * (halfW * 0.82f), camera),
    };
    r.fillPolygon(nose, kart.trim);

    std::vector<Vec2> cabin = {
        project(state.pos + f * 7.0f + right * 12.0f, camera),
        project(state.pos + f * 7.0f - right * 12.0f, camera),
        project(state.pos - f * 17.0f - right * 10.0f, camera),
        project(state.pos - f * 17.0f + right * 10.0f, camera),
    };
    r.fillPolygon(cabin, shade(racer.primary, 0.76f));

    for (float side : {-1.0f, 1.0f}) {
        for (float fore : {-22.0f, 22.0f}) {
            Vec2 wheel = state.pos + f * fore + right * (side * (halfW + 5.0f));
            Vec2 ws = project(wheel, camera);
            r.drawCircle(static_cast<int>(ws.x), static_cast<int>(ws.y), 4, rgb(18, 18, 18));
        }
    }
}

void drawMinimap(Renderer& r, const Track& track, const std::vector<KartState>& cars) {
    int x = r.width() - 184;
    int y = 18;
    int w = 154;
    int h = 112;
    r.fillRect(x - 8, y - 8, w + 16, h + 16, rgb(28, 44, 52));
    r.fillRect(x - 5, y - 5, w + 10, h + 10, rgb(40, 74, 82));
    float minX = track.minX();
    float maxX = track.maxX();
    float minY = track.minY();
    float maxY = track.maxY();
    auto mapPoint = [&](Vec2 p) -> Vec2 {
        float sx = (p.x - minX) / (maxX - minX);
        float sy = (p.y - minY) / (maxY - minY);
        return {x + sx * w, y + h - sy * h};
    };
    Vec2 prev = mapPoint(track.sample(0.0f).point);
    for (float p = 90.0f; p <= track.totalLength() + 90.0f; p += 90.0f) {
        Vec2 cur = mapPoint(track.sample(p).point);
        r.drawLine(prev, cur, 1, rgb(220, 202, 136));
        prev = cur;
    }
    for (const KartState& car : cars) {
        Vec2 mp = mapPoint(car.pos);
        r.drawCircle(static_cast<int>(mp.x), static_cast<int>(mp.y), car.player ? 4 : 2,
                     car.player ? rgb(255, 255, 255) : rgb(235, 94, 84));
    }
}

enum class Mode {
    SelectRacer,
    SelectKart,
    SelectTrack,
    Race,
};

class Game {
public:
    Game() : racers_(makeRacers()), karts_(makeKarts()), props_(makeProps(track_.totalLength())) {
        resetRace();
    }

    void update(const InputFrame& input, float dt) {
        inputConnected_ = input.connected || devKeyboard_;
        if (mode_ == Mode::SelectRacer) {
            if (input.left) {
                selectedRacer_ = (selectedRacer_ + static_cast<int>(racers_.size()) - 1) % static_cast<int>(racers_.size());
            }
            if (input.right) {
                selectedRacer_ = (selectedRacer_ + 1) % static_cast<int>(racers_.size());
            }
            if (input.confirm) {
                mode_ = Mode::SelectKart;
            }
        } else if (mode_ == Mode::SelectKart) {
            if (input.left) {
                selectedKart_ = (selectedKart_ + static_cast<int>(karts_.size()) - 1) % static_cast<int>(karts_.size());
            }
            if (input.right) {
                selectedKart_ = (selectedKart_ + 1) % static_cast<int>(karts_.size());
            }
            if (input.back) {
                mode_ = Mode::SelectRacer;
            }
            if (input.confirm) {
                mode_ = Mode::SelectTrack;
            }
        } else if (mode_ == Mode::SelectTrack) {
            if (input.left) {
                selectedTrack_ = (selectedTrack_ + 2) % 3;
                track_.setLayout(selectedTrack_);
                props_ = makeProps(track_.totalLength());
            }
            if (input.right) {
                selectedTrack_ = (selectedTrack_ + 1) % 3;
                track_.setLayout(selectedTrack_);
                props_ = makeProps(track_.totalLength());
            }
            if (input.back) {
                mode_ = Mode::SelectKart;
            }
            if (input.confirm) {
                resetRace();
                mode_ = Mode::Race;
                paused_ = false;
            }
        } else if (mode_ == Mode::Race) {
            if (input.start) {
                paused_ = !paused_;
            }
            if (paused_) {
                if (input.back) {
                    mode_ = Mode::SelectKart;
                }
                return;
            }
            if (input.select) {
                placeOnTrack(track_, cars_.front(), cars_.front().lastSafeProgress, cars_.front().lineOffset);
            }
            DriveInput playerInput{input.steer, input.throttle, input.brake};
            applyKartPhysics(track_, karts_[cars_[0].kartIndex], cars_[0], playerInput, dt);
            for (size_t i = 1; i < cars_.size(); ++i) {
                DriveInput ai = aiInputFor(track_, cars_[i]);
                applyKartPhysics(track_, karts_[cars_[i].kartIndex], cars_[i], ai, dt);
            }
            updateRacePosition();
        }
        animTime_ += dt;
    }

    void render(Renderer& r, float fps, std::string_view controllerName) {
        Camera camera = currentCamera();
        camera.screenW = r.width();
        camera.screenH = r.height();
        if (mode_ == Mode::Race) {
            camera.fov = r.height() * 0.92f;
            camera.horizon = r.height() * 0.40f;
            drawPerspectiveBackground(r, camera, animTime_);
            drawPerspectiveTrack(r, track_, camera, cars_[0].progress);
            drawPerspectiveSceneObjects(r, camera);
            drawPlayerHood(r, karts_[cars_[0].kartIndex], racers_[cars_[0].racerIndex], length(cars_[0].vel));
            drawHud(r, fps);
        } else {
            camera.zoom *= std::min(r.width() / static_cast<float>(kScreenW), r.height() / static_cast<float>(kScreenH));
            drawBackground(r, camera);
            drawTrack(r, track_, camera);
            for (const Prop& prop : props_) {
                drawProp(r, track_, prop, camera, animTime_);
            }
            for (size_t i = 1; i < cars_.size(); ++i) {
                drawKart(r, cars_[i], karts_[cars_[i].kartIndex], racers_[cars_[i].racerIndex], camera);
            }
            drawKart(r, cars_[0], karts_[cars_[0].kartIndex], racers_[cars_[0].racerIndex], camera);
            drawMenu(r, controllerName);
        }
        if (!inputConnected_) {
            drawControllerOverlay(r);
        }
    }

    void setDevKeyboard(bool enabled) {
        devKeyboard_ = enabled;
        inputConnected_ = enabled;
    }

    bool selfTest() {
        for (int layout = 0; layout < 3; ++layout) {
            selectedTrack_ = layout;
            track_.setLayout(selectedTrack_);
            props_ = makeProps(track_.totalLength());
            resetRace();
            DriveInput input;
            input.throttle = 1.0f;
            for (int i = 0; i < 720; ++i) {
                input.steer = std::sin(i * 0.018f) * 0.25f;
                applyKartPhysics(track_, karts_[cars_[0].kartIndex], cars_[0], input, 1.0f / 120.0f);
                for (size_t j = 1; j < cars_.size(); ++j) {
                    DriveInput ai = aiInputFor(track_, cars_[j]);
                    applyKartPhysics(track_, karts_[cars_[j].kartIndex], cars_[j], ai, 1.0f / 120.0f);
                }
            }
            for (const KartState& car : cars_) {
                if (!std::isfinite(car.pos.x) || !std::isfinite(car.pos.y) || !std::isfinite(car.yaw)) {
                    return false;
                }
            }
            if (track_.totalLength() < 6500.0f) {
                return false;
            }
        }
        selectedTrack_ = 0;
        track_.setLayout(selectedTrack_);
        props_ = makeProps(track_.totalLength());
        resetRace();
        return !cars_.empty() && racers_.size() == 10 && karts_.size() == 8;
    }

private:
    void resetRace() {
        cars_.clear();
        cars_.resize(8);
        std::array<float, 8> offsets = {-42.0f, 42.0f, -88.0f, 88.0f, -20.0f, 20.0f, -70.0f, 70.0f};
        for (size_t i = 0; i < cars_.size(); ++i) {
            KartState& car = cars_[i];
            car.player = i == 0;
            car.racerIndex = i == 0 ? selectedRacer_ : static_cast<int>(i % racers_.size());
            car.kartIndex = i == 0 ? selectedKart_ : static_cast<int>(i % karts_.size());
            float start = -static_cast<float>(i) * 105.0f;
            car.lap = start < 0.0f ? -1 : 0;
            placeOnTrack(track_, car, start, offsets[i]);
            car.progress = wrapProgress(start, track_.totalLength());
            car.lastSafeProgress = car.progress;
        }
        racePosition_ = 1;
    }

    Camera currentCamera() const {
        if (mode_ == Mode::Race) {
            const KartState& player = cars_.front();
            float speed = length(player.vel);
            float speedT = std::clamp(speed / 560.0f, 0.0f, 1.0f);
            Vec2 forward = fromAngle(player.yaw);
            Vec2 right{-forward.y, forward.x};
            Camera camera;
            float chaseDistance = lerp(42.0f, 350.0f, speedT);
            float lateralSway = std::clamp(dot(player.vel, right) * 0.045f, -30.0f, 30.0f);
            camera.pos = player.pos - forward * chaseDistance + right * lateralSway;
            camera.yaw = wrapAngle(player.yaw + player.yawVel * 0.08f);
            camera.perspective = true;
            camera.height = lerp(86.0f, 172.0f, speedT);
            return camera;
        }
        TrackQuery q = track_.sample(620.0f + std::sin(animTime_ * 0.25f) * 120.0f);
        Camera camera;
        camera.pos = q.point;
        camera.yaw = angleOf(q.tangent) + 0.25f * std::sin(animTime_ * 0.2f);
        camera.zoom = 0.30f;
        return camera;
    }

    void drawPerspectiveSceneObjects(Renderer& r, const Camera& camera) {
        struct Candidate {
            size_t index = 0;
            float depth = 0.0f;
        };

        std::vector<std::pair<float, const Prop*>> visibleProps;
        for (const Prop& prop : props_) {
            float ahead = progressAhead(cars_[0].progress, wrapProgress(prop.progress, track_.totalLength()),
                                        track_.totalLength());
            if (ahead > 35.0f && ahead < 4300.0f) {
                visibleProps.push_back({ahead, &prop});
            }
        }
        std::sort(visibleProps.begin(), visibleProps.end(), [](const auto& a, const auto& b) {
            return a.first > b.first;
        });
        for (const auto& item : visibleProps) {
            drawPerspectiveProp(r, track_, *item.second, camera);
        }

        std::vector<Candidate> visibleCars;
        for (size_t i = 1; i < cars_.size(); ++i) {
            auto projected = projectGround(cars_[i].pos, camera);
            if (projected) {
                visibleCars.push_back({i, projected->depth});
            }
        }
        std::sort(visibleCars.begin(), visibleCars.end(), [](const Candidate& a, const Candidate& b) {
            return a.depth > b.depth;
        });
        for (Candidate candidate : visibleCars) {
            const KartState& car = cars_[candidate.index];
            drawPerspectiveKart(r, car, karts_[car.kartIndex], racers_[car.racerIndex], camera);
        }
    }

    void drawBackground(Renderer& r, const Camera&) {
        r.clear(rgb(43, 125, 150));
        for (int y = 0; y < r.height(); y += 34) {
            int shift = static_cast<int>(std::sin(animTime_ * 0.8f + y * 0.07f) * 22.0f);
            r.drawLine({static_cast<float>(-40 + shift), static_cast<float>(y)},
                       {static_cast<float>(r.width() + 40 + shift), static_cast<float>(y + 14)}, 1,
                       rgb(54, 143, 166));
        }
    }

    void drawMenu(Renderer& r, std::string_view controllerName) {
        int w = r.width();
        int h = r.height();
        int cx = w / 2;
        r.fillRect(0, 0, w, 92, rgb(24, 38, 46));
        r.drawTextCentered(cx, 18, "HARBOR KARTS", rgb(246, 230, 152), 4);
        r.drawTextCentered(cx, 66, "ORIGINAL BEACH HARBOR RACING BASELINE", rgb(210, 226, 224), 2);

        if (mode_ == Mode::SelectRacer) {
            const Racer& racer = racers_[selectedRacer_];
            r.drawTextCentered(cx, 130, "SELECT RACER", rgb(255, 255, 255), 3);
            r.drawTextCentered(cx, 174, "<  " + racer.name + "  >", rgb(255, 236, 122), 4);
            r.drawCircle(cx, 270, 58, racer.primary);
            r.drawCircle(cx, 252, 36, racer.accent);
            r.fillRect(cx - 70, 310, 140, 22, shade(racer.primary, 0.7f));
            r.drawTextCentered(cx, 360, "COSMETIC ONLY - NO SUPER POWERS", rgb(232, 242, 234), 2);
            r.drawTextCentered(cx, 394,
                               std::to_string(selectedRacer_ + 1) + "/" + std::to_string(racers_.size()),
                               rgb(246, 230, 152), 2);
        } else {
            if (mode_ == Mode::SelectKart) {
                const KartDef& kart = karts_[selectedKart_];
                r.drawTextCentered(cx, 130, "SELECT MAXED CAR", rgb(255, 255, 255), 3);
                r.drawTextCentered(cx, 174, "<  " + kart.name + "  >", rgb(255, 236, 122), 4);
                drawGarageKart(r, cx, 282, kart);
                r.drawText(cx - 180, 360, "SPEED", rgb(232, 242, 234), 2);
                r.drawText(cx - 180, 388, "ACCEL", rgb(232, 242, 234), 2);
                r.drawText(cx - 180, 416, "GRIP", rgb(232, 242, 234), 2);
                drawFullBar(r, cx - 70, 360);
                drawFullBar(r, cx - 70, 388);
                drawFullBar(r, cx - 70, 416);
                r.drawText(cx + 158, 388, "MAX", rgb(255, 236, 122), 2);
            } else {
                r.drawTextCentered(cx, 130, "SELECT TRACK", rgb(255, 255, 255), 3);
                r.drawTextCentered(cx, 174, "<  " + track_.name() + "  >", rgb(255, 236, 122), 4);
                r.drawTextCentered(cx, 246, "TECHNICAL HARBOR LAYOUT", rgb(232, 242, 234), 2);
                r.drawTextCentered(cx, 284, "BRAKE BEFORE HAIRPINS  HIT CLEAN APEXES", rgb(255, 236, 122), 2);
                r.drawTextCentered(cx, 330, "LENGTH " + std::to_string(static_cast<int>(track_.totalLength())) + "M",
                                   rgb(166, 214, 220), 2);
            }
        }

        std::string pad = controllerName.empty() ? "NO GAMEPAD" : std::string(controllerName);
        r.drawTextCentered(cx, h - 48, "A CONFIRM  B BACK  LEFT/RIGHT CHOOSE", rgb(210, 226, 224), 2);
        r.drawTextCentered(cx, h - 24, pad, rgb(166, 214, 220), 1);
    }

    void drawGarageKart(Renderer& r, int cx, int cy, const KartDef& kart) {
        r.fillRect(cx - 92, cy - 30, 184, 58, rgb(22, 30, 34));
        r.fillRect(cx - 72, cy - 26, 144, 52, kart.body);
        std::vector<Vec2> nose = {{static_cast<float>(cx + 104), static_cast<float>(cy)},
                                  {static_cast<float>(cx + 58), static_cast<float>(cy - 29)},
                                  {static_cast<float>(cx + 58), static_cast<float>(cy + 29)}};
        r.fillPolygon(nose, kart.trim);
        r.fillRect(cx - 26, cy - 20, 48, 40, shade(kart.body, 0.62f));
        r.drawCircle(cx - 58, cy - 34, 13, rgb(12, 12, 12));
        r.drawCircle(cx + 58, cy - 34, 13, rgb(12, 12, 12));
        r.drawCircle(cx - 58, cy + 34, 13, rgb(12, 12, 12));
        r.drawCircle(cx + 58, cy + 34, 13, rgb(12, 12, 12));
    }

    void drawFullBar(Renderer& r, int x, int y) {
        r.fillRect(x, y, 210, 14, rgb(38, 54, 60));
        for (int i = 0; i < 10; ++i) {
            r.fillRect(x + i * 21 + 2, y + 2, 17, 10, rgb(86, 222, 142));
        }
    }

    void drawHud(Renderer& r, float fps) {
        const KartState& player = cars_.front();
        int speed = static_cast<int>(length(player.vel) * 0.22f);
        r.fillRect(0, 0, 420, 86, rgb(24, 38, 46));
        r.drawText(16, 14, "LAP " + std::to_string(std::max(0, player.lap + 1)) + "  POS " +
                              std::to_string(racePosition_) + "/8",
                   rgb(255, 244, 170), 2);
        r.drawText(16, 40, "SPEED " + std::to_string(speed) + "  FPS " + std::to_string(static_cast<int>(fps + 0.5f)),
                   rgb(224, 240, 236), 2);
        r.drawText(16, 66, racers_[selectedRacer_].name + " | " + karts_[selectedKart_].name, rgb(166, 214, 220), 1);
        drawMinimap(r, track_, cars_);
        if (player.wrongWay) {
            r.drawTextCentered(r.width() / 2, 96, "WRONG WAY", rgb(255, 88, 72), 4);
        }
        if (paused_) {
            r.fillRect(0, 0, r.width(), r.height(), rgb(20, 30, 36));
            r.drawTextCentered(r.width() / 2, r.height() / 2 - 62, "PAUSED", rgb(255, 244, 170), 5);
            r.drawTextCentered(r.width() / 2, r.height() / 2 + 20, "START RESUME  B GARAGE", rgb(224, 240, 236), 2);
        }
    }

    void drawControllerOverlay(Renderer& r) {
        int x = r.width() / 2 - 340;
        int y = r.height() / 2 - 73;
        r.fillRect(x, y, 680, 146, rgb(24, 38, 46));
        r.fillRect(x + 8, y + 8, 664, 130, rgb(35, 58, 66));
        r.drawTextCentered(r.width() / 2, y + 28, "CONNECT A GAMEPAD", rgb(255, 244, 170), 4);
        r.drawTextCentered(r.width() / 2, y + 86, "NORMAL PLAY IS CONTROLLER ONLY", rgb(224, 240, 236), 2);
        r.drawTextCentered(r.width() / 2, y + 114, "LINUX /DEV/INPUT/JS0 STYLE DEVICES", rgb(166, 214, 220), 1);
    }

    void updateRacePosition() {
        float playerScore = cars_[0].lap * track_.totalLength() + cars_[0].progress;
        int pos = 1;
        for (size_t i = 1; i < cars_.size(); ++i) {
            float score = cars_[i].lap * track_.totalLength() + cars_[i].progress;
            if (score > playerScore) {
                ++pos;
            }
        }
        racePosition_ = pos;
    }

    Track track_;
    std::vector<Racer> racers_;
    std::vector<KartDef> karts_;
    std::vector<KartState> cars_;
    std::vector<Prop> props_;
    Mode mode_ = Mode::SelectRacer;
    int selectedRacer_ = 0;
    int selectedKart_ = 0;
    int selectedTrack_ = 0;
    int racePosition_ = 1;
    bool paused_ = false;
    bool inputConnected_ = false;
    bool devKeyboard_ = false;
    float animTime_ = 0.0f;
};

InputFrame mergeKeyboardInput(const InputFrame& controller, const std::array<bool, 256>& keys,
                              const std::array<bool, 256>& prevKeys, bool enabled) {
    if (!enabled) {
        return controller;
    }
    InputFrame out = controller;
    out.connected = true;
    float steer = 0.0f;
    if (keys[1]) {
        steer -= 1.0f;
    }
    if (keys[2]) {
        steer += 1.0f;
    }
    if (std::abs(steer) > std::abs(out.steer)) {
        out.steer = steer;
    }
    out.throttle = std::max(out.throttle, (keys[3] || keys[6] || keys[8]) ? 1.0f : 0.0f);
    out.brake = std::max(out.brake, (keys[4] || keys[9]) ? 1.0f : 0.0f);
    out.left = out.left || (keys[1] && !prevKeys[1]);
    out.right = out.right || (keys[2] && !prevKeys[2]);
    out.confirm = out.confirm || ((keys[5] && !prevKeys[5]) || (keys[6] && !prevKeys[6]) || (keys[8] && !prevKeys[8]));
    out.back = out.back || ((keys[7] && !prevKeys[7]) || (keys[9] && !prevKeys[9]));
    out.start = out.start || (keys[10] && !prevKeys[10]);
    out.select = out.select || (keys[11] && !prevKeys[11]);
    out.quit = out.quit || (keys[7] && !prevKeys[7]);
    return out;
}

int runSelfTest() {
    Game game;
    if (!game.selfTest()) {
        std::cerr << "harbor_karts self-test failed\n";
        return 1;
    }
    std::cout << "harbor_karts self-test: ok\n";
    return 0;
}

int runGame(bool devKeyboard) {
    AppWindow window;
    if (!window.open()) {
        return 1;
    }

    ControllerManager controllers;
    Game game;
    game.setDevKeyboard(devKeyboard);
    std::array<bool, 256> keys{};
    std::array<bool, 256> prevKeys{};

    auto last = std::chrono::steady_clock::now();
    auto fpsTime = last;
    int fpsFrames = 0;
    float fps = 60.0f;
    float accumulator = 0.0f;
    constexpr float fixedDt = 1.0f / 120.0f;
    constexpr float maxFrame = 1.0f / 20.0f;

    while (window.running()) {
        auto frameStart = std::chrono::steady_clock::now();
        std::chrono::duration<float> elapsed = frameStart - last;
        last = frameStart;
        accumulator += std::min(elapsed.count(), maxFrame);

        prevKeys = keys;
        window.poll(devKeyboard, keys);
        InputFrame input = mergeKeyboardInput(controllers.poll(), keys, prevKeys, devKeyboard);
        if (input.quit) {
            window.close();
            continue;
        }

        int physicsSteps = 0;
        while (accumulator >= fixedDt && physicsSteps < 8) {
            game.update(input, fixedDt);
            accumulator -= fixedDt;
            ++physicsSteps;
        }
        if (physicsSteps == 8) {
            accumulator = 0.0f;
        }

        Renderer renderer = window.renderer();
        game.render(renderer, fps, controllers.activeName());
        window.present();

        ++fpsFrames;
        auto now = std::chrono::steady_clock::now();
        std::chrono::duration<float> fpsElapsed = now - fpsTime;
        if (fpsElapsed.count() >= 0.5f) {
            fps = fpsFrames / fpsElapsed.count();
            fpsFrames = 0;
            fpsTime = now;
        }

        auto target = frameStart + std::chrono::microseconds(16666);
        std::this_thread::sleep_until(target);
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    bool selfTest = false;
    bool devKeyboard = false;
    for (int i = 1; i < argc; ++i) {
        std::string_view arg(argv[i]);
        if (arg == "--self-test") {
            selfTest = true;
        } else if (arg == "--dev-keyboard") {
            devKeyboard = true;
        } else if (arg == "--help" || arg == "-h") {
            std::cout << "Usage: harbor_karts [--self-test] [--dev-keyboard]\n";
            return 0;
        }
    }
    if (selfTest) {
        return runSelfTest();
    }
    return runGame(devKeyboard);
}
