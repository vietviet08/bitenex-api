# Financial Contract Phase 0

## Purpose

Define the production financial contract for Bitenex:
`Order Service -> Payment Service -> Ledger Service -> Payout Service -> PSP/Bank`.

This document is the Phase 0 source of truth for:

- accounting posting rules
- order/payment state contract
- cancel/refund matrix
- currency, decimal, rounding policy
- idempotency policy

## 1. Canonical Money Representation

Rules:

1. Persist all financial values as integer minor units (`amount_minor`) with explicit currency.
2. Currency must be ISO-4217 uppercase 3-letter code.
3. Ledger and payout persistence must not use float.

Example:

- Input: `123.45` USD
- Persisted: `amount_minor=12345`, `currency=USD`

Validation:

- Reject amounts with more decimal places than the currency exponent.

## 2. Currency and Decimal Policy

Rules:

1. A single order uses exactly one currency.
2. A single journal entry uses exactly one currency.
3. Cross-currency movement is represented by separate journal entries, never mixed lines.

## 3. Rounding Policy

Rules:

1. Use `ROUND_HALF_UP`.
2. Round each line subtotal to minor units before aggregation.
3. Enforce formula:
   `order_total = subtotal + delivery_fee + tax - discount`
4. Store only minor-unit integers at persistence boundaries.

## 4. Order and Payment State Contract

Order transitions:
`PENDING -> CONFIRMED -> PREPARING -> READY -> PICKING_UP -> DELIVERING -> DELIVERED`

Allowed exceptional transitions:

- `PENDING -> CANCELLED`
- `CONFIRMED -> CANCELLED`
- `PREPARING -> CANCELLED`
- `READY -> CANCELLED`
- `CANCELLED -> REFUNDED`

Forbidden cancellation transitions:

- `PICKING_UP -> CANCELLED`
- `DELIVERING -> CANCELLED`
- `DELIVERED -> CANCELLED`

Payment transitions:

- `PENDING -> PROCESSING -> COMPLETED`
- `PENDING -> PROCESSING -> FAILED`
- `COMPLETED -> REFUNDED`
- `PENDING|PROCESSING -> CANCELLED`

## 5. Cancellation and Refund Matrix

| Order status at cancel request | Cancel allowed | Refund behavior                                                         |
| ------------------------------ | -------------- | ----------------------------------------------------------------------- |
| PENDING                        | Yes            | If payment not completed: no refund posting. If completed: full refund. |
| CONFIRMED                      | Yes            | Full refund if payment completed.                                       |
| PREPARING                      | Yes            | Full refund if payment completed.                                       |
| READY                          | Yes            | Full refund if payment completed.                                       |
| PICKING_UP                     | No             | Cancel rejected. Refund only through dispute/admin flow.                |
| DELIVERING                     | No             | Cancel rejected. Refund only through dispute/admin flow.                |
| DELIVERED                      | No             | Cancel rejected. Refund only through dispute/admin flow.                |

## 6. Ledger Invariants (Double-Entry)

Rules:

1. Every journal entry has at least 2 lines.
2. `SUM(debit_minor) == SUM(credit_minor)` per journal entry.
3. Journal entries are immutable (no in-place update/delete).
4. Corrections use reversal entry plus replacement entry.
5. Every journal entry has unique traceable `source_event_id`.
6. Posting idempotency key is unique by `(source_event_id, posting_type)`.
7. Financial timestamps use UTC.

## 7. Chart of Accounts Baseline

| Code | Account                    | Type      | Scope                      |
| ---- | -------------------------- | --------- | -------------------------- |
| 1100 | PSP Clearing               | Asset     | Global per currency        |
| 2100 | Customer Prepay Holding    | Liability | Global per currency        |
| 2200 | Merchant Payable           | Liability | Per merchant, per currency |
| 2250 | Merchant Payout In Transit | Liability | Per merchant, per currency |
| 2300 | Driver Payable             | Liability | Per driver, per currency   |
| 2350 | Driver Payout In Transit   | Liability | Per driver, per currency   |
| 2400 | Refund Payable             | Liability | Global per currency        |
| 4100 | Platform Revenue           | Revenue   | Global per currency        |

## 8. Posting Rules for Main Events

Notation:

- `GROSS`: customer paid amount for the order.
- `MERCHANT_NET`: amount owed to merchant.
- `DRIVER_NET`: amount owed to driver.
- `PLATFORM_REV = GROSS - MERCHANT_NET - DRIVER_NET`.
- `REFUND_AMOUNT`: approved refund amount.
- `PAYOUT_AMOUNT`: payout amount for one beneficiary.

| Event                                                   | Preconditions                         | Debit                                             | Credit                                                                                                             |
| ------------------------------------------------------- | ------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `PaymentCompletedEvent`                                 | Payment confirmed by PSP webhook      | 1100 PSP Clearing = `GROSS`                       | 2100 Customer Prepay Holding = `GROSS`                                                                             |
| `OrderStatusChangedEvent(new=DELIVERED)`                | Order delivered and payment completed | 2100 Customer Prepay Holding = `GROSS`            | 2200 Merchant Payable = `MERCHANT_NET`; 2300 Driver Payable = `DRIVER_NET`; 4100 Platform Revenue = `PLATFORM_REV` |
| `OrderStatusChangedEvent(new=CANCELLED)` for paid order | Cancel accepted for paid order        | 2100 Customer Prepay Holding = `REFUND_AMOUNT`    | 2400 Refund Payable = `REFUND_AMOUNT`                                                                              |
| `RefundSucceededEvent`                                  | PSP confirms refund                   | 2400 Refund Payable = `REFUND_AMOUNT`             | 1100 PSP Clearing = `REFUND_AMOUNT`                                                                                |
| `MerchantPayoutInitiatedEvent`                          | Batch selects merchant payable item   | 2200 Merchant Payable = `PAYOUT_AMOUNT`           | 2250 Merchant Payout In Transit = `PAYOUT_AMOUNT`                                                                  |
| `MerchantPayoutSucceededEvent`                          | PSP/Bank confirms transfer            | 2250 Merchant Payout In Transit = `PAYOUT_AMOUNT` | 1100 PSP Clearing = `PAYOUT_AMOUNT`                                                                                |
| `MerchantPayoutFailedEvent`                             | PSP/Bank rejects transfer             | 2250 Merchant Payout In Transit = `PAYOUT_AMOUNT` | 2200 Merchant Payable = `PAYOUT_AMOUNT`                                                                            |
| `DriverPayoutInitiatedEvent`                            | Batch selects driver payable item     | 2300 Driver Payable = `PAYOUT_AMOUNT`             | 2350 Driver Payout In Transit = `PAYOUT_AMOUNT`                                                                    |
| `DriverPayoutSucceededEvent`                            | PSP/Bank confirms transfer            | 2350 Driver Payout In Transit = `PAYOUT_AMOUNT`   | 1100 PSP Clearing = `PAYOUT_AMOUNT`                                                                                |
| `DriverPayoutFailedEvent`                               | PSP/Bank rejects transfer             | 2350 Driver Payout In Transit = `PAYOUT_AMOUNT`   | 2300 Driver Payable = `PAYOUT_AMOUNT`                                                                              |

Rule:

- `PaymentFailedEvent` and unpaid cancellation create no ledger postings.

## 9. Idempotency Policy

Rules:

1. All client financial write endpoints require `Idempotency-Key`.
2. API idempotency scope: `actor_id + endpoint + request_fingerprint`.
3. Webhook dedup key: `gateway + gateway_event_id`.
4. Ledger dedup key: `(source_event_id, posting_type)`.
5. Payout dedup key: `(beneficiary_id, payout_cycle, currency)`.

Expected behavior:

- Duplicate webhook deliveries must produce exactly one payment transition and one posting.
- Retried payout calls must not create duplicate transfers.

## 10. Phase 0 Done Definition

Phase 0 is complete when:

1. This document is approved as the baseline financial contract.
2. Posting rules for all main events are explicitly documented.
3. Order/payment transitions and cancel/refund matrix are fixed.
4. Currency/decimal/rounding/idempotency policies are fixed.
