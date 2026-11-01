#pragma once
#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "InputCoreTypes.h"
#include "Engine/EngineBaseTypes.h"

class UFFSession;

class FFSessionAudit {
public:
    explicit FFSessionAudit(UFFSession& Session);
    ~FFSessionAudit();
private:
    bool Tick(float DeltaSeconds);
    void Key(FKey Key, EInputEvent Event);
    void Tap(FKey Key);
    void Capture(const TCHAR* Name);
    void Advance(int32 Stage);
    bool Fail(const TCHAR* Reason);
    UFFSession& Session;
    FTSTicker::FDelegateHandle Handle;
    double Started = 0;
    double StageStarted = 0;
    bool MenuOnly = false;
    int32 Stage = 0;
    int32 Circuit = 0;
    float PausedStation = 0;
    float BrakeStartSpeed = 0;
    float InitialScreenPercentage = 100;
};
