CXX ?= g++
BUILD_DIR := build
TARGET := $(BUILD_DIR)/harbor_karts
SRC := src/main.cpp

CXXFLAGS ?= -std=c++20 -O3 -Wall -Wextra -pedantic
CPPFLAGS ?=
LDFLAGS ?=
LDLIBS := -lX11 -lm

.PHONY: all clean run self-test

all: $(TARGET)

$(TARGET): $(SRC) | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) -o $@ $^ $(LDLIBS)

$(BUILD_DIR):
	mkdir -p $@

run: $(TARGET)
	./$(TARGET)

self-test: $(TARGET)
	./$(TARGET) --self-test

clean:
	rm -rf $(BUILD_DIR)
