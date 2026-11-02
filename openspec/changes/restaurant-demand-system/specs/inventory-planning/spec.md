# Inventory planning specification

## Purpose
Translate demand history into useful ingredient purchasing guidance (PDF OE4).

## Requirements
### Requirement: PLAN-1 Honest forecasts
The system MUST forecast ingredient demand using only observations before the forecast origin, identify the method and history limits, and provide an explicit fallback when history is insufficient.

#### Scenario: Empty history
- GIVEN no recorded demand
- WHEN forecasts are requested
- THEN no learned accuracy claim is shown and insufficient history is explained.

#### Scenario: Future observation changed
- GIVEN a forecast origin and historical observations
- WHEN observations at or after that origin change
- THEN the origin's forecast remains unchanged.

### Requirement: PLAN-2 Purchase suggestions
Suggestions MUST account for demand, safety stock, stock surviving each target date, and pack rounding. Suggestions MUST NOT execute purchases.

#### Scenario: Stock allocated once
- GIVEN stock sufficient for only the first forecast day
- WHEN a multi-day purchase plan is computed
- THEN later dates use carried remaining stock and planned receipts without reusing consumed stock.

#### Scenario: Expiring stock
- GIVEN stock expiring before a target date
- WHEN its purchase suggestion is computed
- THEN that stock does not reduce the target requirement.
