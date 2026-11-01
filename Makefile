.DEFAULT_GOAL := build
.PHONY: build package run check session-check flow-check assets script-check
build:
	bash tools/unreal.sh build
assets: build
	bash tools/unreal.sh python tools/prepare_project.py
package:
	bash tools/unreal.sh package
run:
	bash tools/unreal.sh run $(ARGS)
check:
	bash tools/unreal.sh check
script-check:
	bash Tests/platform_scripts.sh
session-check:
	bash tools/unreal.sh session-check
flow-check:
	bash tools/unreal.sh run -windowed -RenderOffscreen -ForceRes -ResX=1600 -ResY=900 -FFFlowAudit -FFDrive '-ExecCmds=t.MaxFPS 30'

CPPFLAGS := -ISource/FormulaForge -ISource/FormulaForge/Native
CXXFLAGS := -std=c++20 -O2 -Wall -Wextra -Wpedantic
SIMULATION := FFSimulation FFMonzaGeometry FFInterlagosGeometry FFTrackLimits FFPitLane FFDriveSurface
NATIVE := arcade_vehicle track_catalog silverstone_chapel_barriers
OBJECTS := $(addprefix build/tests/,$(addsuffix .o,$(SIMULATION) $(NATIVE)))
-include $(OBJECTS:.o=.d)
build/tests/%.o: Source/FormulaForge/%.cpp
	mkdir -p build/tests build/tmp
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) -MMD -MP -c $< -o $@
build/tests/%.o: Source/FormulaForge/Native/%.cpp
	mkdir -p build/tests build/tmp
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) -MMD -MP -c $< -o $@
build/tests/circuit-audit: Tests/circuit_audit.cpp $(OBJECTS)
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@
build/tests/camera-audit: Tests/camera_audit.cpp Source/FormulaForge/FFCameraMotion.cpp
	mkdir -p build/tests build/tmp
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@
.PHONY: native-check
native-check: build/tests/circuit-audit build/tests/camera-audit build/tests/surface-audit
	build/tests/circuit-audit
	build/tests/camera-audit
	build/tests/surface-audit

build/tests/surface-audit: Tests/surface_audit.cpp $(OBJECTS)
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@
