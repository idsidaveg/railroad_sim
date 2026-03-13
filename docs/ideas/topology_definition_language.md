# Future Idea: Topology Definition Language

Goal:
Allow rail networks to be defined concisely in tests and simulation scenarios.

Example:

A --- B --- C
      |
      D

Possible syntax options:
- ASCII layout
- JSON/YAML topology
- Python DSL

Concerns:
- ambiguity of junction endpoints
- alignment defaults
- parser complexity

Conclusion:
Defer until dispatcher and routing logic stabilize.

Example of a Yard

Boise Yard
Main ----+---- Yard Lead
         |
         |
         +---- Track 1
         |
         +---- Track 2