# Handover: claims queue

All 5 claims in the queue have a decision file in `decisions/`.

| Claim | Decision | Payout | Notes |
|---|---|---|---|
| CLM-1007 | Approve | $50 | Phone damage. $1,099 capped at the $150 Economy per-item limit (no Electronics Plus), less the $100 deductible. |
| CLM-1015 | Decline | $0 | Trip interruption because the customer left a child at home. Not one of the five covered reasons in section 2. |
| CLM-1017 | Refer | $0 | Theft in Naples. Police report is missing. |
| CLM-1020 | Approve | $240 | Sunglasses taken by a macaque. Treated as accidental loss, so no police report was needed. First plan, $0 deductible. |
| CLM-1021 | Approve | $1,053 | Snatch theft. $1,103 of items less the $50 Premium deductible. |

## Needs your attention

- **CLM-1021: sign-off needed.** The payout is over $1,000, so payment waits for your approval (manual s3).
- **CLM-1017: waiting on the customer.** We need the Carabinieri report (the Italian original is fine) within 30 days. Check that it was made within 24 hours of the theft. If it was, the claim looks payable at about $720 ($820 of items, with the rain jacket capped at $150, less the $100 deductible). I have not confirmed that the document request has gone out to the customer, so please check.
- **CLM-1015: expect a complaint.** The decline follows the wording strictly, and the customer may dispute it.
