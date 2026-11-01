#pragma once

#include "arcade_vehicle.hpp"
#include "authored_circuit_sampling.hpp"
#include "authored_track_collision.hpp"
#include "authored_circuit_ground.hpp"
#include "FFDriveSurface.hpp"
#include "FFTrackLimits.hpp"
#include "FFPitLane.hpp"
#include <vector>

struct FFTrackProjection {
    Vec2 position;
    Vec2 tangent;
    float station = 0.0f;
    float lane = 0.0f;
    float halfWidth = 7.0f;
    float elevation = 0.0f;
    float bankSlope = 0.0f;
    float curvature = 0.0f;
    float grade = 0.0f;
};

struct FFTrialState {
    float lapLength = 5891.0f;
    float startStation = 0.0f;
    double seconds = 0.0;
    double lastSeconds = 0.0;
    double bestSeconds = 0.0;
    bool running = false;
    bool invalid = false;
    bool lastValid = false;
    int nextGate = 1;
    int completedLaps = 0;
    float previousStation = 0.0f;
    void Reset(float station);
    void Step(float station, bool onTrack, bool contact, double deltaSeconds);
};

class FFSimulation {
public:
    explicit FFSimulation(TrackLayoutId layout = TrackLayoutId::Silverstone);
    void Reset(float station = -1.0f);
    void Step(const ArcadeVehicleControl& control, float seconds);
    FFTrackProjection Project(Vec2 position) const;
    FFTrackProjection Sample(float station) const;
    ArcadeSurface CurrentSurface() const;
    float Ground(Vec2 position, bool protectMainRoad = true) const;
    float VisualGround(Vec2 position) const;
    bool OnTrack() const;
    bool LoadNationalSurface(std::span<const std::uint8_t> bytes);
    bool LoadPitLane(std::span<const std::uint8_t> bytes);
    bool LoadPitBarriers(std::span<const std::uint8_t> bytes);
    bool InPitLane() const;
    float PitSpeedLimitKph() const;
    bool PitOverspeed() const;
    float ProgressStation() const;
    const std::vector<AuthoredBarrierSegment>& Barriers() const;
    static bool Audit();
    TrackLayoutId circuit;
    float lapLength;
    std::string_view circuitName;
    ArcadeVehicleState vehicle;
    ArcadeVehicleConfig tuning;
    FFTrialState trial;
    bool barrierContact = false;
    FFDriveSurface driveSurface;
    FFDriveSurface nationalSurface;
    FFTrackLimits trackLimits;
    FFPitLane pitLane;
    ArcadeVehicleControl appliedControl;
private:
    FFPitProjection PitProjectionForCar(const FFTrackProjection& road) const;
    float GripScale(const FFTrackProjection& projection) const;
    ArcadeSurface Surface(const FFTrackProjection& projection) const;
    void ResolveBarriers(Vec2 start);
    const TrackCatalogEntry* track;
    std::vector<Vec2> plan;
    std::vector<Vec2> tangents;
    std::vector<float> curvatures;
    std::vector<AuthoredBarrierSegment> barriers;
    std::span<const AuthoredSurfaceTriangle> runoff;
    const AuthoredGroundGrid* ground = nullptr;
    FFTrackLimits pitTrackLimits;
    mutable bool projectionCached = false;
    mutable Vec2 projectionPosition;
    mutable FFTrackProjection projectionResult;
};
