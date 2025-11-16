# LED Ring State Flow – pimonitor

This document describes the current LED state machine for the Kano hat ring
and how it responds to service status and button presses. It is meant as a
reference for both of us when reasoning about behaviour or making changes.

---

## 1. Service State Evaluation & Data Flow

### Service Check Cycle Flow

```mermaid
flowchart TD
    Start([Monitor Loop Start]) --> CheckConfig[Check Config Changes]
    CheckConfig --> LoadServices[Load Services from Config]
    LoadServices --> CheckInterval{Time since<br/>last check >=<br/>check_interval?}
    
    CheckInterval -->|No| PollButton1[Poll Button State]
    PollButton1 --> RenderLED[Render LED Animation]
    RenderLED --> Sleep1[Sleep 0.05s]
    Sleep1 --> Start
    
    CheckInterval -->|Yes| InitStatus["Initialize service_statuses = {}"]
    InitStatus --> ServiceLoop{For each service<br/>in config}
    
    ServiceLoop -->|Next service| GetService[Get service config:<br/>name, type, target, severity]
    GetService --> CheckType{Service type?}
    
    CheckType -->|ping| PingCheck[check_ping target]
    CheckType -->|tcp| TCPCheck[check_tcp target]
    CheckType -->|http| HTTPCheck[check_http target]
    CheckType -->|systemd| SystemdCheck[check_systemd name]
    
    PingCheck --> StoreResult["Store in service_statuses:<br/>name -> {ok: bool, severity: int}"]
    TCPCheck --> StoreResult
    HTTPCheck --> StoreResult
    SystemdCheck --> StoreResult
    
    StoreResult --> ServiceLoop
    ServiceLoop -->|All checked| CalcFailed[Calculate failed_services:<br/>All names where ok == False]
    
    CalcFailed --> CalcUnsnoozed[Calculate unsnoozed_failures:<br/>failed_services - snoozed_failed_services]
    
    CalcUnsnoozed --> UpdateState[Update Display State:<br/>- Track new_failures<br/>- Update alert_active<br/>- Clear snoozed if all OK]
    
    UpdateState --> PollButton2[Poll Button State]
    PollButton2 --> RenderLED
    
    style Start fill:#e1f5e1
    style CalcFailed fill:#ffe1e1
    style CalcUnsnoozed fill:#ffe1e1
    style UpdateState fill:#e1e5ff
```

### State Variable Derivation

```mermaid
graph LR
    A["service_statuses<br/>Dict: name -> {ok, severity}"] --> B{For each service}
    B -->|ok == False| C[Add to failed_services Set]
    B -->|ok == True| D[Skip]
    C --> E[Calculate unsnoozed_failures]
    E --> F[failed_services - snoozed_failed_services]
    
    G[Button Press] --> H[Add to snoozed_failed_services Set]
    H --> E
    
    I[All Services OK] --> J[Clear both sets]
    
    style C fill:#ff6b6b
    style E fill:#ffd700
    style F fill:#ffd700
    style H fill:#9370db
```

---

## 2. LED State Decision Tree & Rendering

### Complete State Decision Tree

```mermaid
flowchart TD
    Start([Animation Frame]) --> CheckACK{ack_flash_pending<br/>== True?}
    
    CheckACK -->|Yes| ACKFrame[ACK Flash Frame<br/>All LEDs: Color 20,20,20<br/>Duration: 50ms]
    ACKFrame --> ClearACK[Set ack_flash_pending = False]
    ClearACK --> SleepACK[Sleep 0.05s]
    SleepACK --> End([End Frame])
    
    CheckACK -->|No| HasStatus{service_statuses<br/>empty?}
    HasStatus -->|Yes| SleepEmpty[Sleep 1s]
    SleepEmpty --> End
    
    HasStatus -->|No| CheckInternet{internet_ok<br/>== True?}

    CheckInternet -->|No| StateD[STATE D: Internet Down]
    StateD --> InternetWave[internet_down_animation_step<br/>Teal/blue wave]
    InternetWave --> SleepInternet[Sleep 0.05s]
    SleepInternet --> End

    CheckInternet -->|Yes| CheckAllOK{all status.ok<br/>== True?}
    
    CheckAllOK -->|Yes| StateA[STATE A: All OK]
    StateA --> GreenWave[breathing_animation_step<br/>Green travelling wave]
    GreenWave --> SleepOK[Sleep 0.05s]
    SleepOK --> End
    
    CheckAllOK -->|No| StateBC[STATE B/C: Failures Present]
    StateBC --> FailureAnim[failure_animation_step]
    FailureAnim --> SleepFail[Sleep 0.05s]
    SleepFail --> End
    
    style StateA fill:#90ee90,stroke:#006400,stroke-width:3px
    style StateBC fill:#ff6b6b,stroke:#8b0000,stroke-width:3px
    style StateD fill:#40e0d0,stroke:#008b8b,stroke-width:3px
    style ACKFrame fill:#e1e5ff,stroke:#4169e1,stroke-width:2px
    style GreenWave fill:#90ee90
    style FailureAnim fill:#ff6b6b
```

### State A: All OK - Green Wave Animation

```mermaid
flowchart TD
    Start([breathing_animation_step]) --> CheckHat{Hat available?}
    CheckHat -->|No| Return1[Return]
    CheckHat -->|Yes| CheckAnyDown{Any service<br/>ok == False?}
    
    CheckAnyDown -->|Yes| Return2[Return - Don't animate OK state]
    CheckAnyDown -->|No| UpdatePhase[Update ok_phase:<br/>ok_phase += OK_ROTATION_SPEED<br/>Wrap at 2π]
    
    UpdatePhase --> UpdateBreathing[Update breathing_phase:<br/>breathing_phase += BREATHING_SPEED<br/>Wrap at 2π]
    
    UpdateBreathing --> CalcBaseBright[Calculate base_brightness:<br/>sine wave from<br/>BREATHING_MIN to MAX]
    
    CalcBaseBright --> CalcHeadPos[Calculate head_index:<br/>head_index = ok_phase / 2π * LED_COUNT]
    
    CalcHeadPos --> LEDLoop{For each LED<br/>0 to LED_COUNT}
    
    LEDLoop -->|Next LED| CalcPhaseOffset[Calculate pos_phase:<br/>ok_phase + 2π * idx / LED_COUNT]
    CalcPhaseOffset --> CalcWave[Calculate wave:<br/>sin pos_phase + 1 / 2<br/>Range: 0.0 to 1.0]
    
    CalcWave --> MixBrightness[Calculate led_brightness:<br/>base_brightness * 0.4 + 0.6 * wave]
    
    MixBrightness --> SetLED[Set LED color:<br/>Apply brightness scale to COLOR_OK green]
    
    SetLED --> LEDLoop
    LEDLoop -->|All LEDs| ShowLED[hat.show]
    ShowLED --> Return3[Return]
    
    style Start fill:#90ee90
    style Return3 fill:#90ee90
    style CalcBaseBright fill:#e1f5e1
    style MixBrightness fill:#e1f5e1
```

### State B/C: Failure Animation - Detailed Rendering Flow

```mermaid
flowchart TD
    Start([failure_animation_step]) --> CheckHat{Hat available?}
    CheckHat -->|No| Return1[Return]
    CheckHat -->|Yes| BuildFailing[Build failing list:<br/>All services where ok == False<br/>with name and severity]
    
    BuildFailing --> CheckEmpty{failing<br/>list empty?}
    CheckEmpty -->|Yes| Return2[Return]
    
    CheckEmpty -->|No| SeparateSets[Separate into two lists:<br/>unsnoozed: name not in snoozed_failed_services<br/>snoozed: name in snoozed_failed_services]
    
    SeparateSets --> InitArrays["Initialize LED arrays:<br/>led_r = array of base_brightness<br/>led_g = array of 0<br/>led_b = array of 0<br/>Red background on all LEDs"]
    
    InitArrays --> SnoozedLoop{For each<br/>snoozed failure}
    
    SnoozedLoop -->|Next| CalcSeverity[Calculate severity:<br/>Clamp to 1-10 range]
    CalcSeverity --> CalcGradient[Calculate gradient t:<br/>t = severity - 1 / 9.0<br/>Range: 0.0 to 1.0]
    
    CalcGradient --> CalcColor["Calculate static color:<br/>r = 40 * 1.0 - t<br/>g = 0<br/>b = 80 + 80 * t<br/>Purple -> Blue gradient"]
    
    CalcColor --> SetSnoozedLED[Set LED at idx % LED_COUNT:<br/>led_r, led_g, led_b = calculated color]
    
    SetSnoozedLED --> SnoozedLoop
    SnoozedLoop -->|All snoozed| UnsnoozedLoop{For each<br/>unsnoozed failure}
    
    UnsnoozedLoop -->|Next| GetTime[Get current time: now = time.time]
    GetTime --> CalcSevNorm[Calculate sev_norm:<br/>severity / 10.0]
    
    CalcSevNorm --> CalcFreq[Calculate pulse frequency:<br/>freq = 0.4 + 1.2 * sev_norm<br/>Range: 0.4 to 1.6 Hz]
    
    CalcFreq --> CalcPhase[Calculate phase:<br/>phase = now * freq * 2π]
    
    CalcPhase --> CalcWave[Calculate wave:<br/>sin phase + 1 / 2<br/>Range: 0.0 to 1.0]
    
    CalcWave --> CalcAmplitude[Calculate amplitude:<br/>ERROR_MAX - base * 0.4 + 0.6 * sev_norm]
    
    CalcAmplitude --> CalcPulse[Calculate pulse_brightness:<br/>base + wave * amplitude]
    
    CalcPulse --> CalcOrange[Calculate orange color:<br/>r = pulse_brightness<br/>g = pulse_brightness * 0.4<br/>b = 0]
    
    CalcOrange --> SetUnsnoozedLED[Set LED at idx % LED_COUNT:<br/>led_r, led_g, led_b = orange color<br/>Overwrites red background]
    
    SetUnsnoozedLED --> UnsnoozedLoop
    UnsnoozedLoop -->|All unsnoozed| RenderLoop{For each LED<br/>0 to LED_COUNT}
    
    RenderLoop -->|Next| SetColor[hat.set_led_color idx<br/>Color led_r, led_g, led_b]
    SetColor --> RenderLoop
    
    RenderLoop -->|All LEDs| ShowLED[hat.show]
    ShowLED --> Return3[Return]
    
    style Start fill:#ff6b6b
    style InitArrays fill:#ffcccc
    style SetSnoozedLED fill:#9370db
    style SetUnsnoozedLED fill:#ffa500
    style Return3 fill:#ff6b6b
```

### State Summary Table

| State | Condition | LED Pattern | Button Effect |
|-------|-----------|-------------|---------------|
| **State A** | `failed_services == ∅`<br/>`internet_ok == True` | Green travelling wave with breathing | ACK blink only |
| **State B** | `failed_services ≠ ∅`<br/>`unsnoozed_failures ≠ ∅`<br/>`internet_ok == True` | Red background + pulsing orange (unsnoozed) + static purple/blue (snoozed) | Snooze all failures → State C |
| **State C** | `failed_services ≠ ∅`<br/>`unsnoozed_failures == ∅`<br/>`internet_ok == True` | Red background + static purple/blue only | ACK blink only |
| **State D** | `internet_ok == False` | Dark blue/cyan base with occasional soft cyan/magenta/purple “glitch” sparkles | ACK blink only (does not snooze internet-down) |
| **ACK Overlay** | `ack_flash_pending == True` | All LEDs: dim white (20,20,20) for 50ms | N/A (one frame only) |

---

## 3. State Machine & Transitions

### Complete State Machine Diagram

```mermaid
stateDiagram-v2
    [*] --> StateA
    
    StateA --> StateB: New service fails
    StateA --> StateA: All services OK
    
    StateB --> StateC: Button pressed
    StateB --> StateA: All services recover
    StateB --> StateB: New failure added
    
    StateC --> StateB: New service fails
    StateC --> StateA: All services recover
    StateC --> StateC: Same failures persist
    
    StateA: State A - All OK
    StateB: State B - Active Alert
    StateC: State C - Acknowledged
    
    note right of StateA
        Condition: failed_services empty
        Pattern: Green travelling wave
        Animation: breathing_animation_step
        - Rotating green wave
        - Breathing brightness
        - Phase offset per LED
        Button: ACK blink only
    end note
    
    note right of StateB
        Condition: failed_services not empty
        unsnoozed_failures not empty
        Pattern: Red bg + pulsing orange
        Animation: failure_animation_step
        - Red background (all LEDs)
        - Static purple/blue (snoozed)
        - Pulsing orange (unsnoozed)
        - Severity affects pulse speed/brightness
        Button: Snooze all -> State C
    end note
    
    note right of StateC
        Condition: failed_services not empty
        unsnoozed_failures empty
        Pattern: Red bg + static purple/blue
        Animation: failure_animation_step
        - Red background (all LEDs)
        - Static purple/blue only
        - No pulsing
        - Severity affects color gradient
        Button: ACK blink only
    end note
```

### State Transition Decision Tree

```mermaid
flowchart TD
    Start([After Service Check]) --> CalcCurrent[Calculate current_failed:<br/>All services where ok == False]
    
    CalcCurrent --> CheckEmpty{current_failed<br/>empty?}
    
    CheckEmpty -->|Yes| AllRecovered[All Services Recovered]
    AllRecovered --> ClearSets[Clear both sets:<br/>failed_services.clear<br/>snoozed_failed_services.clear]
    ClearSets --> SetInactive[Set alert_active = False<br/>alert_acknowledged = False]
    SetInactive --> TransitionA[Transition to State A]
    TransitionA --> End([End])
    
    CheckEmpty -->|No| CalcNew[Calculate new_failures:<br/>current_failed - failed_services]
    
    CalcNew --> CheckNew{new_failures<br/>not empty?}
    
    CheckNew -->|Yes| NewFailures[New Failures Detected]
    NewFailures --> SetActive[Set alert_active = True<br/>alert_acknowledged = False]
    SetActive --> UpdateFailed[Update failed_services = current_failed]
    UpdateFailed --> CheckUnsnoozed{unsnoozed_failures<br/>not empty?}
    
    CheckNew -->|No| UpdateFailed2[Update failed_services = current_failed]
    UpdateFailed2 --> CheckUnsnoozed
    
    CheckUnsnoozed -->|Yes| StateB[Remain/Enter State B<br/>Active Alert]
    CheckUnsnoozed -->|No| StateC[Remain/Enter State C<br/>Acknowledged]
    
    StateB --> End
    StateC --> End
    
    style AllRecovered fill:#90ee90
    style NewFailures fill:#ff6b6b
    style StateB fill:#ff6b6b
    style StateC fill:#9370db
    style TransitionA fill:#90ee90
```

### Button Press Handling Flow

```mermaid
flowchart TD
    Start([Button Press Detected]) --> PollButton[poll_button called]
    PollButton --> CheckPressed{Button<br/>pressed?}
    
    CheckPressed -->|No| End1([No Action])
    CheckPressed -->|Yes| CheckState{Current State?}
    
    CheckState -->|State A<br/>All OK| NoSnooze[No snooze action<br/>Optional ACK blink]
    NoSnooze --> End2([End])
    
    CheckState -->|State B<br/>Active Alert| ButtonCallback[button_callback invoked]
    CheckState -->|State C<br/>Acknowledged| NoSnooze2[No snooze action<br/>ACK blink only]
    NoSnooze2 --> End3([End])
    
    ButtonCallback --> SetVars[Set state variables:<br/>alert_acknowledged = True<br/>alert_active = False<br/>snoozed_failed_services =<br/>  set failed_services<br/>ack_flash_pending = True]
    
    SetVars --> NextFrame[Next Animation Frame]
    NextFrame --> ShowACK[ACK Flash Shown:<br/>All LEDs white 20,20,20<br/>50ms duration]
    
    ShowACK --> CalcUnsnoozed[Calculate unsnoozed_failures:<br/>failed_services - snoozed_failed_services]
    
    CalcUnsnoozed --> CheckEmpty{unsnoozed_failures<br/>empty?}
    
    CheckEmpty -->|Yes| TransitionBC["Transition B -> C<br/>All failures snoozed"]
    CheckEmpty -->|No| StayB[Remain in State B<br/>Some failures still unsnoozed]
    
    TransitionBC --> VisualChange["Visual Change:<br/>Pulsing orange -><br/>Static purple/blue"]
    StayB --> VisualChange2[Visual Change:<br/>Some pulsing orange remain<br/>Some static purple/blue]
    
    VisualChange --> End4([End])
    VisualChange2 --> End5([End])
    
    style ButtonCallback fill:#ffd700,stroke:#ff8c00,stroke-width:3px
    style SetVars fill:#ffd700
    style TransitionBC fill:#9370db
    style VisualChange fill:#9370db
    style ShowACK fill:#e1e5ff
```

### Transition Summary Table

| Transition | Trigger | State Changes | Visual Effect |
|------------|---------|---------------|---------------|
| **A → B** | New service fails | `failed_services` grows<br/>`unsnoozed_failures` grows<br/>`alert_active = True` | Green wave → Red bg + pulsing orange |
| **B → C** | Button pressed | `snoozed_failed_services = failed_services`<br/>`unsnoozed_failures = ∅`<br/>`ack_flash_pending = True` | Pulsing orange → Static purple/blue |
| **C → B** | New service fails (not snoozed) | `failed_services` grows<br/>`unsnoozed_failures` grows | Static purple/blue → Add pulsing orange |
| **B/C → A** | All services recover | `failed_services.clear()`<br/>`snoozed_failed_services.clear()`<br/>`alert_active = False` | Red bg → Green wave |

---

## 4. LED Mapping & Debugging

### LED Assignment Logic

```mermaid
flowchart TD
    Start([Service Failure Detected]) --> GetFailing[Get failing services list:<br/>name, severity pairs]
    
    GetFailing --> Separate[Separate into:<br/>unsnoozed list<br/>snoozed list]
    
    Separate --> SnoozedMap{For each<br/>snoozed service}
    SnoozedMap -->|idx, name, severity| CalcSnoozedLED[led_index = idx % LED_COUNT<br/>where idx is position in snoozed list]
    CalcSnoozedLED --> SetSnoozed[Set LED at led_index:<br/>Static purple/blue color]
    SetSnoozed --> SnoozedMap
    
    Separate --> UnsnoozedMap{For each<br/>unsnoozed service}
    UnsnoozedMap -->|idx, name, severity| CalcUnsnoozedLED[led_index = idx % LED_COUNT<br/>where idx is position in unsnoozed list]
    CalcUnsnoozedLED --> SetUnsnoozed[Set LED at led_index:<br/>Pulsing orange color<br/>Overwrites red background]
    SetUnsnoozed --> UnsnoozedMap
    
    SnoozedMap -->|All mapped| Render[Render all LEDs]
    UnsnoozedMap -->|All mapped| Render
    
    Render --> End([LED Ring Updated])
    
    style CalcSnoozedLED fill:#9370db
    style CalcUnsnoozedLED fill:#ffa500
    style SetSnoozed fill:#9370db
    style SetUnsnoozed fill:#ffa500
```

### Single Service Failure - Before & After Snooze

```mermaid
graph LR
    subgraph Before["Before Snooze (State B)"]
        B1[LED Ring] --> B2[All LEDs: Red background]
        B2 --> B3[LED 0: Pulsing Orange<br/>Service: myservice]
        B3 --> B4[LEDs 1-11: Red only]
    end
    
    subgraph After["After Snooze (State C)"]
        A1[LED Ring] --> A2[All LEDs: Red background]
        A2 --> A3[LED 0: Static Purple/Blue<br/>Service: myservice]
        A3 --> A4[LEDs 1-11: Red only]
    end
    
    Before -->|Button Press| After
    
    style B3 fill:#ffa500
    style A3 fill:#9370db
    style B2 fill:#ffcccc
    style A2 fill:#ffcccc
```

### Multiple Service Failures - LED Sharing

```mermaid
graph TD
    subgraph Scenario["Scenario: 3 Services Failing, 12 LEDs"]
        S1[Service A: unsnoozed] --> L1[LED 0: Pulsing Orange]
        S2[Service B: unsnoozed] --> L2[LED 1: Pulsing Orange]
        S3[Service C: snoozed] --> L3[LED 2: Static Purple/Blue]
    end
    
    subgraph Sharing["LED Sharing Logic"]
        SH1[LED index = service_idx % LED_COUNT]
        SH2[Multiple services can share same LED]
        SH3[Pulsing orange overwrites red background]
        SH4[Pulsing orange overwrites static purple/blue]
    end
    
    subgraph Example["Example: 15 Services, 12 LEDs"]
        E1["Service 0 -> LED 0"]
        E2["Service 1 -> LED 1"]
        E3["Service 11 -> LED 11"]
        E4["Service 12 -> LED 0<br/>Shares with Service 0"]
        E5["Service 13 -> LED 1<br/>Shares with Service 1"]
    end
    
    style L1 fill:#ffa500
    style L2 fill:#ffa500
    style L3 fill:#9370db
```

### Debugging: Why Two LEDs Appear

```mermaid
flowchart TD
    Observation[Observe: Two LEDs lit] --> CheckStatus[Check /status.json endpoint]
    
    CheckStatus --> CountFailed[Count failed_services in status]
    
    CountFailed --> OneFailed{One service<br/>in failed_services?}
    
    OneFailed -->|Yes| CheckSnooze{Service in<br/>snoozed_failed_services?}
    OneFailed -->|No| MultipleServices[Multiple services failing<br/>Each maps to different LED]
    
    CheckSnooze -->|No| StateB[State B: One pulsing orange LED<br/>Expected: 1 LED]
    CheckSnooze -->|Yes| StateC[State C: One static purple/blue LED<br/>Expected: 1 LED]
    
    MultipleServices --> DebugSteps[Debug Steps:<br/>1. Compare logs with /status.json<br/>2. Check service_statuses dict<br/>3. Verify LED mapping calculation<br/>4. Check for duplicate service names]
    
    StateB --> Unexpected[If 2 LEDs appear:<br/>Check for hidden services<br/>or mapping bug]
    StateC --> Unexpected
    
    Unexpected --> DebugSteps
    
    style MultipleServices fill:#ff6b6b
    style DebugSteps fill:#ffd700
```

---

This document reflects the current code paths in `pimonitor/monitor.py` after
removing `led_position` and moving to the wave + per‑service pulse model. It
should be updated whenever the state machine or colour semantics change.
