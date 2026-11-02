# Restaurant prototype specification

## Purpose
Provide local Spanish administrator workflows (user clarification; PDF OE4).

## Requirements
### Requirement: UI-1 Isolated modes
The system MUST offer explicit demo or own-restaurant mode, persist them separately, label demo assumptions, and never silently reset either dataset.

#### Scenario: Mode switch
- GIVEN a modified demo restaurant
- WHEN own-restaurant mode opens
- THEN it contains only its separately persisted data.

### Requirement: UI-2 Usable operations
The interface MUST expose catalog, purchases, sales, stock/waste, dashboard, forecasts and CSV exports using America/Lima business dates.

#### Scenario: Completed workflow
- GIVEN an own restaurant with recipes
- WHEN purchases and a sale are recorded
- THEN dashboard, history and exported stock reflect the committed operations.
