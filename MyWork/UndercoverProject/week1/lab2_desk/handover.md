# Claims Queue Handover

Decided under policy wording 2026.1 and claims manual 2026.2. All five open claims in `claims/` now have a decision file in `decisions/`. No payout exceeds the $1,000 approval limit, so **no sign-off is required on any of these claims**.

## Summary

| Claim | Customer | Plan | Type | Decision | Payout |
|---|---|---|---|---|---|
| CLM-1007 | Greg Kowalski | Economy | Baggage — accidental damage (phone in shower) | Approve | $50.00 |
| CLM-1015 | Kate Callister | First | Trip Interruption (left child at home) | Decline | $0.00 |
| CLM-1017 | Emily Nguyen | Economy | Baggage — theft (Naples backpack snatch) | Refer | $0.00 |
| CLM-1020 | Nadia Rahman | First | Baggage — wild animal (monkey took sunglasses) | Approve | $240.00 |
| CLM-1021 | Camille Fontaine | Premium + Electronics Plus | Baggage — theft (Buenos Aires snatch) | Approve | $825.00 |

## Notes on each decision

- **CLM-1007 (approve $50).** Accidental damage inside the covered trip, repair report and replacement receipt on file. Phone counts at the Economy per-item limit of $150, less the $100 deductible = $50. The high claimed amount ($1,099) is why the payout is small; the per-item limit does the work, not the amount claimed.
- **CLM-1015 (decline).** The only reason for the interruption is that an eight-year-old was left at home by mistake. That is not one of the listed reasons in wording section 2, which states "We do not pay for cancellation or interruption for any other reason." Filed in time and inside the trip; the reason alone defeats it. Letter names section 2 and quotes the sentence.
- **CLM-1017 (refer).** The Naples snatch is covered in principle (theft from the person is never "unattended"; filed within 90 days; inside the trip). But two required documents are missing: the police report (the customer says she made one and will send it when she finds it) and proof of value for the $130 sunglasses. Per manual section 5 this is a document referral, not a decline, because the step was taken. 30-day document request sent. Indicative payout if both documents arrive: **$420** (items capped at the $150 Economy per-item limit, less the $100 deductible). The file is open until the documents arrive.
- **CLM-1020 (approve $240).** The monkey is a wild animal, so per manual section 7 this is accidental loss, not theft — no police report needed, and the vermin/pets exclusion does not apply. The licensed guide's letter and the $240 replacement receipt are the required evidence. First plan, $0 deductible, under the $500 per-item limit.
- **CLM-1021 (approve $825).** Theft from the person, police report same day, proof of value on file for every item over $100. The judgment call: Electronics Plus lifts the per-item limit to $1,200 **only** for the items listed in wording section 8 (phones, tablets, laptops, cameras and lenses, e-readers, smartwatches). The e-reader qualifies ($180). The headphones and the handheld game console are **not** on that list, so each falls back to the Premium per-item limit of $300. Tote bag at $95 needs no receipt (items of $100 or less). $300 + $180 + $300 + $95 = $875, less the $50 deductible = **$825**.

## Things for the handler to know

- **No repeat-claim referrals.** None of these five customers has a prior claim, so the third-claim-in-12-months rule did not apply.
- **No fraud/SIU referrals.** No story-vs-documents conflicts met the manual section 8 threshold.
- **Only open item:** CLM-1017 is waiting on the customer. Chase it if the 30 days lapse; otherwise it is payable at ~$420.
- Customer letters are stored in each decision file under the `letter` field and follow manual section 12. No customer's data appears in another customer's letter or file.
