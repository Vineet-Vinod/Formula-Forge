#include <iostream>
#include "authored_track_collision.hpp"
#include "track_data/monza_boundaries.inc"

int main() {
    int failures = 0;
    const auto check = [&](bool pass, const char* name) {
        std::cout << name << "=" << (pass ? "pass" : "FAIL") << '\n';
        failures += !pass;
    };
    const AuthoredBarrierSegment wall{{0,-10},{0,10},0,2,.15f};
    auto hit = sweepAuthoredBarrier(wall,{-20,0},{20,0},{1,0},2.5f,1,0,1);
    check(hit.hit && hit.time > .42f && hit.time < .44f && hit.normal.x < -.99f,"high_speed_sweep");
    check(!sweepAuthoredBarrier(wall,{-20,14},{20,14},{1,0},2.5f,1,0,1).hit,"open_endpoint");
    check(!sweepAuthoredBarrier(wall,{-20,0},{20,0},{1,0},2.5f,1,3,1).hit,"separate_elevation");
    check(!sweepAuthoredBarrier(wall,{-3,0},{-20,0},{1,0},2.5f,1,0,1).hit,"moving_away");
    hit=sweepAuthoredBarrier(wall,{-2,0},{-2,0},{1,0},2.5f,1,0,1);
    check(hit.hit && hit.penetration > .6f,"initial_overlap");
    const auto route = [&](std::initializer_list<Vec2> points, const char* name) {
        bool clear = true;
        for (auto a=points.begin(), b=a+1; b!=points.end(); ++a,++b) {
            Vec2 start{a->x*17,-a->y*17}, end{b->x*17,-b->y*17};
            const auto contact=firstAuthoredBarrierHit(kMonzaBarriers,start,end,normalize(end-start),
                2.6f*17,1.0f*17, .0022f*(a->y+b->y)*.5f*17,.8f*17);
            clear=clear&&!contact.hit;
        }
        check(clear,name);
    };
    route({{58,565},{61,610},{64,655},{67,700},{72,750}},"rettifilo_escape_open");
    route({{776.629f,1242.429f},{822.673f,1243.029f},{869.718f,1246.426f},
           {882.731f,1270.007f},{890.739f,1284.395f},{914.762f,1298.383f},{930.777f,1308.575f}},"roggia_escape_open");
    const auto blockedPit = [&](Vec2 a, Vec2 b, const char* name) {
        const Vec2 start{a.x*17,-a.y*17}, end{b.x*17,-b.y*17};
        const auto contact=firstAuthoredBarrierHit(kMonzaBarriers,start,end,normalize(end-start),
            2.6f*17,17,.0022f*a.y*17,.8f*17);
        check(contact.hit,name);
    };
    blockedPit({-37.1744f,-471.1607f},{-17.1777f,-470.7975f},"pit_entry_closed");
    blockedPit({15.0737f,144.1932f},{35.0037f,142.5211f},"pit_exit_closed");
    size_t contacted=0;
    for (const auto& barrier:kMonzaBarriers) {
        const Vec2 tangent=normalize(barrier.b-barrier.a), normal{-tangent.y,tangent.x};
        const Vec2 center=(barrier.a+barrier.b)*.5f;
        contacted += sweepAuthoredBarrier(barrier,center-normal*170,center+normal*170,
            normal,2.6f*17,17,barrier.bottom,.8f*17).hit;
    }
    check(contacted==std::size(kMonzaBarriers),"every_exported_barrier_blocks");
    return failures ? 1 : 0;
}
