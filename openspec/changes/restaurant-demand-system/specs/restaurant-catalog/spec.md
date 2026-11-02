# Restaurant catalog specification

## Purpose
Maintain the inputs required for recipe-based operations (user clarification; PDF OE4).

## Requirements
### Requirement: CAT-1 Editable catalog
The system MUST maintain ingredients with unit, cost, shelf life, pack size and safety stock; dishes with price; and positive ingredient quantities per dish recipe. Nonfinite values and invalid quantities MUST be rejected.

#### Scenario: Valid recipe
- GIVEN active ingredients
- WHEN an administrator saves a dish and its recipe
- THEN the recipe is available for sales and demand conversion.

#### Scenario: Invalid amount
- GIVEN an existing catalog
- WHEN a negative or nonfinite amount is submitted
- THEN no catalog change occurs and an actionable error appears.

### Requirement: CAT-2 Historical safety
The system MUST support disabling catalog items without deleting historical transactions or changing recorded consumption.

#### Scenario: Disabled dish
- GIVEN a previously sold dish
- WHEN it is disabled
- THEN new sales reject it and previous sales remain readable.
