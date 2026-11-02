# Restaurant operations specification

## Purpose
Persist trustworthy daily restaurant operations (user clarification).

## Requirements
### Requirement: OPS-1 Receipts and waste
The system MUST receive positive purchases as dated lots and record deliberate or expiration waste with quantities, costs and reasons. Expired lots MUST be unavailable for sales.

#### Scenario: Purchase receipt
- GIVEN a valid ingredient
- WHEN a purchase is received
- THEN stock and receipt history persist after reopening.

#### Scenario: Expiration
- GIVEN an expired lot
- WHEN stock is inspected or consumed
- THEN it cannot satisfy demand and expiration waste is auditable.

### Requirement: OPS-2 Atomic sales
The system MUST consume recipe quantities from eligible lots FIFO, atomically across all sale lines, preserving prices and consumption history.

#### Scenario: FIFO sale
- GIVEN two valid lots received on different dates
- WHEN a recipe-based sale consumes more than the older lot contains
- THEN the older lot is exhausted before the newer lot and the sale survives reopening.

#### Scenario: Insufficient ingredient
- GIVEN a sale requiring multiple ingredients
- WHEN any ingredient lacks eligible stock
- THEN neither sale nor stock changes are committed.

### Requirement: OPS-3 Idempotent writes
The system MUST prevent retrying one request from executing its purchase, sale or waste twice.

#### Scenario: Retry
- GIVEN a completed request
- WHEN its identical request key is retried
- THEN the original result returns without another stock movement.

#### Scenario: Conflicting retry
- GIVEN a completed request key
- WHEN a different payload reuses that key
- THEN the request is rejected without changing stock or history.
