# Railroad Simulator Terminology Guide

This document defines the core terminology used in the railroad simulation project.

The goal is to maintain **clarity and consistency** across:
- domain model
- network topology
- movement logic
- future CTC / visualization layers

---

## 🔑 Core Principles

1. **Topology and operations are separate concepts**
2. **Names must reflect real railroad meaning where possible**
3. **Avoid overlapping terminology (especially "switch")**
4. **Objects should carry their own identity (name/display)**

---

## 🚂 Operational vs Physical Concepts

### Switching (Operations)
**Definition:**
Railcar handling operations such as:
- cutting
- coupling
- inserting
- pickup
- setout

**Code Location:**
- `switching_service.py`

**Important:**
"Switching" refers to **train operations**, NOT track hardware.

---

## 🧭 Topology Concepts

### TrackSegment
Represents a section of rail between two endpoints.

**Key Properties:**
- identity (id, name)
- endpoints
- length

**Important:**
A track does NOT assume:
- it is a stub
- it is a mainline
- it is a yard track

These are **roles**, not structural constraints.

---

### Junction
Represents a **generic topology connection** between track endpoints.

**Used For:**
- connecting tracks
- defining possible movement paths
- representing graph connectivity

**Important:**
A `Junction` is a **topology construct**, not necessarily a physical turnout.

---

## 🔀 Turnout (Physical Track Device)

### Definition
A **turnout** is a physical track structure that allows a train to move from one track to another.

This is the correct term for what railroaders often call a "switch".

---

### Current Implementation

#### TurnoutZone
Represents the physical and operational characteristics of a turnout:
- clearance zone
- turnout geometry (hand)
- routing state (normal/diverging)

---

#### TurnoutHand
Defines turnout geometry:
- LEFT
- RIGHT

---

#### TurnoutRouteKind
Defines active routing:
- NORMAL (straight route)
- DIVERGING (branch route)

---

#### TurnoutFoulingState
Represents whether a turnout is fouled by equipment:
- turnout_name
- is_fouled
- optional metadata (consist, equipment)

---

#### TurnoutEvaluator
Evaluates whether a consist footprint fouls a turnout.

Supports:
- single-track extents
- multi-track extents
- turnout zones spanning multiple tracks

---

## ⚠️ Terminology Clarification

### ❌ Avoid Using "Switch" in Code

"Switch" is ambiguous because it can refer to:
1. Physical turnout hardware
2. Switching operations (moving cars)

To avoid confusion:
- Use **"Turnout"** for track hardware
- Use **"Switching"** only for operations

---

### ❌ Do Not Use "Junction" as a Synonym for Turnout

- A **junction** is a topology concept
- A **turnout** is a physical device

They are related, but not interchangeable.

---

## 🧱 Future Trackwork (Planned)

The system may later support additional track devices:
- Wye
- Crossing (X)
- Slip switch
- Double-slip
- Crossover arrangements

These should be modeled as:
- specialized topology devices
- possibly extending or composing junction behavior

---

## 🧠 Mental Model

TrackSegment  ---->  Junction  ---->  TrackSegment
                      |
                      +--> Turnout behavior (routing, fouling)

- Tracks define space
- Junctions define connectivity
- Turnouts define **how movement is routed through that connectivity**

---

## 🏗️ Yard / Throat Design (Forward Looking)

A yard throat is composed of:
- one entry turnout
- one lead track (spine)
- a sequence of turnout connections (ladder)
- multiple branch tracks

Important:
- Branch tracks may be stub-ended OR continue to other topology
- No assumption of one-sided connectivity

---

## 🧾 Naming Guidelines (Future CTC Support)

All topology objects should expose:
- `id` (machine-stable)
- `name` (code reference)
- `display_name` (UI / CTC)

Example:

Turnout:
    id = "jt_01"
    name = "yard_entry"
    display_name = "SW-01"

Track:
    id = "trk_yard_01"
    name = "yard_1"
    display_name = "Yard 1"

---

## ✅ Summary

| Concept        | Meaning                          | Code Term        |
|----------------|----------------------------------|------------------|
| Car handling   | Operational switching            | Switching        |
| Track hardware | Physical route device            | Turnout          |
| Connectivity   | Graph connection                 | Junction         |
| Rail segment   | Physical track                   | TrackSegment     |

---

## 🚧 Guiding Rule

> Build topology using generic connections (junctions),  
> model routing using turnouts,  
> and keep operations separate (switching).
