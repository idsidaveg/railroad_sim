# Railroad Simulation (railroad_sim)

A Python domain model for simulating railroad equipment and train consists.

This project focuses on modeling the **physical relationships between rolling stock**, including coupler connections, consist traversal, and safe manipulation of train equipment.

---

## Current Features

### Rolling Stock
Represents an individual piece of railroad equipment.

Each unit has:

- Immutable `asset_id`
- Railroad `reporting_mark`
- `road_number`
- Front and rear couplers

Example:
UP 1001

---

### Coupler System

Each piece of rolling stock owns two couplers:

FRONT
REAR


Couplers can connect to each other to form train consists.

---

### Consist

A **Consist** represents a chain of connected rolling stock.

Key design principle:

> The consist does **not store order**.  
> Order is derived by traversing coupler connections.

Capabilities include:

- Traversing equipment head → rear
- Detecting circular topologies
- Splitting consists
- Diagnostic visualization

Example diagram:
HEAD ->UP 1001 -- UP 1002 -- UP 1003 <-REAR


---

### Diagnostic Tools

Helpful debugging helpers:
consist_show()
consist_show_diagnostics()

Example output:
Consist Diagnostic
Anchor: UP 1002

[1] UP 1001
Front: None
Rear: UP 1002 FRONT

[2] UP 1002[ANCHOR]
Front: UP 1001 REAR
Rear: UP 1003 FRONT

[3] UP 1003
Front: UP 1002 REAR
Rear: None


---

## Testing

Testing is performed using **pytest**.

Current coverage:
-98%


Tests cover:

- rolling stock creation
- coupler connections
- consist traversal
- topology error detection
- consist splitting operations

---

## Project Structure
see project structure it will change, as it is still in development


---

## Future Development

Planned components:

- Train object
- Locomotive class
- Block/track system
- Dispatch / CTC control layer
- Simulation engine

---

## Development Environment

Python 3.12  
pytest  
VS Code