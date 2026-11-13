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
SIMULATION := FFSimulation FFMonzaGeometry FFInterlagosGeometry FFTrackLimits FFPitLane FFDriveSurface FFRacingLine FFLasVegasAudit
NATIVE := arcade_vehicle track_catalog silverstone_chapel_barriers generated_circuit
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
.PHONY: native-check circuits
native-check: build/tests/export-surfaces build/tests/export-lasvegas build/tests/lasvegas-lap-audit build/tests/circuit-audit build/tests/camera-audit build/tests/surface-audit
	build/tests/export-lasvegas
	$(LASVEGAS_PYTHON) tools/lasvegas_boundaries.py
	$(MAKE) build/tests/export-surfaces build/tests/export-lasvegas build/tests/lasvegas-lap-audit build/tests/circuit-audit build/tests/surface-audit
	build/tests/export-surfaces
	build/tests/export-lasvegas
	build/tests/circuit-audit
	build/tests/camera-audit
	build/tests/surface-audit
	build/tests/lasvegas-lap-audit
circuits:
	python3 tools/build_circuits.py
	$(MAKE) build/tests/export-surfaces
	build/tests/export-surfaces

build/tests/surface-audit: Tests/surface_audit.cpp $(OBJECTS)
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@
build/tests/export-surfaces: Tests/export_surfaces.cpp $(OBJECTS)
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/tests/export-lasvegas: tools/export_lasvegas.cpp $(OBJECTS)
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

build/tests/export-circuit-scene: tools/export_circuit_scene.cpp $(OBJECTS)
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@
build/tests/audit-circuit-lap: tools/audit_circuit_lap.cpp $(OBJECTS)
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

CIRCUIT_PYTHON ?= python3
CIRCUIT ?= japan
.PHONY: circuit-assets circuit-check
.NOTPARALLEL: circuit-assets
circuit-assets: check build build/tests/export-circuit-scene
	build/tests/export-circuit-scene $(CIRCUIT)
	$(CIRCUIT_PYTHON) tools/generate_circuit_scene.py $(CIRCUIT)
	for batch in 0 1 2 3; do \
		bash tools/unreal.sh python tools/build_circuit_scene.py -FFCircuitAssets=$(CIRCUIT) -FFTileBatch=$$batch -FFTileBatches=4 || exit $$?; \
	done
circuit-check:
	$(CIRCUIT_PYTHON) -m pytest -q Tests/test_circuit_scenes.py Tests/test_circuit_profiles.py Tests/test_circuit_recordings.py Tests/test_circuit_terrain.py Tests/test_coastal_water.py Tests/test_circuit_protection.py Tests/test_baku_architecture.py Tests/test_circuit_partition.py
	$(CIRCUIT_PYTHON) -m mypy tools/circuit*.py tools/generate_circuit_scene.py tools/review_circuit_recording.py tools/venues --ignore-missing-imports --follow-imports=silent
	$(CIRCUIT_PYTHON) -m ruff check tools/circuit*.py tools/generate_circuit_scene.py tools/build_circuit_scene.py tools/review_circuit_recording.py tools/venues Tests/test_circuit_scenes.py Tests/test_circuit_profiles.py Tests/test_circuit_recordings.py Tests/test_circuit_terrain.py Tests/test_coastal_water.py Tests/test_circuit_protection.py Tests/test_baku_architecture.py Tests/test_circuit_partition.py

.PHONY: lasvegas-assets
.NOTPARALLEL: lasvegas-assets
lasvegas-assets: check build
	$(LASVEGAS_PYTHON) tools/lasvegas_art.py
	for batch in 0 1 2 3; do \
		bash tools/unreal.sh python tools/build_lasvegas.py -FFLasVegasTileBatch=$$batch || exit $$?; \
	done
	bash tools/unreal.sh python tools/verify_lasvegas.py

LASVEGAS_PYTHON ?= python3
.PHONY: lasvegas-check
lasvegas-check:
	$(LASVEGAS_PYTHON) -m pytest -q Tests/test_lasvegas_assets.py
	$(LASVEGAS_PYTHON) -m mypy tools/lasvegas_dataclasses.py tools/lasvegas_art.py tools/lasvegas_geometry.py tools/lasvegas_boundaries.py --ignore-missing-imports --follow-imports=silent
	$(LASVEGAS_PYTHON) -m ruff check tools/lasvegas*.py tools/build_lasvegas.py tools/verify_lasvegas.py Tests/test_lasvegas_assets.py

build/tests/lasvegas-lap-audit: Tests/lasvegas_lap_audit.cpp $(OBJECTS)
	TMPDIR="$(CURDIR)/build/tmp" $(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@

.PHONY: lasvegas-flow-check
lasvegas-flow-check:
	bash tools/unreal.sh run -windowed -RenderOffscreen -ForceRes -ResX=1600 -ResY=900 -FFCircuit=lasvegas -FFFlowAudit -FFFlowCircuit=lasvegas -FFDrive -FFRecord -FFRecordSeconds=420 '-ExecCmds=t.MaxFPS 30'
