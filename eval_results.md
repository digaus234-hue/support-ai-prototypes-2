# Eval Results — model: `claude-sonnet-5`

Generated: 2026-09-04T22:42:58.549275+00:00

## Retrieval accuracy (deterministic, no API calls)

**70.0%** (7/10)

| ID | Expected KB | Matched KB | Correct |
|----|--------------|-------------|---------|
| A01 | KB01 | KB01 | ✅ |
| A02 | KB05 | KB05 | ✅ |
| A03 | KB03 | KB03 | ✅ |
| A04 | KB04 | KB04 | ✅ |
| A05 | KB06 | KB06 | ✅ |
| A06 | KB07 | KB07 | ✅ |
| A07 | KB08 | KB08 | ✅ |
| A08 | KB02 | KB05 | ❌ |
| A09 | (none) | KB01 | ❌ |
| A10 | (none) | KB07 | ❌ |

## Generation eval (schema validity + flagging behavior)

**Schema-valid responses: 100.0%**

| ID | Input (truncated) | Variants Returned | Flag for Review | Confidence | Latency (ms) |
|----|---------------------|----------------------|--------------------|--------------|---------------|
| A01 | I was charged twice this month for my subscription, please refund the ... | 3 | False | high | 4534.1 |
| A02 | How do I switch from monthly to annual billing? | 3 | False | high | 4420.3 |
| A03 | I never got my password reset email, I've tried twice. | 3 | False | medium | 4689.3 |
| A04 | My consultant showed up late, was dismissive, and gave advice that con... | 3 | True | medium | 6156.7 |
| A05 | My card keeps getting declined when my subscription tries to renew, ev... | 3 | False | high | 6641.5 |
| A06 | The app crashes every time I try to upload a photo on my iPhone, start... | 3 | False | high | 5392.8 |
| A07 | There's a booking on my account I never made, and my payment method wa... | 3 | True | high | 5842.2 |
| A08 | I want a refund but it's been 2 months since I subscribed — is that ev... | 3 | True | low | 4680.6 |
| A09 | just wanted to say thanks, the new dashboard is way easier to use now! | 3 | False | high | 4056.3 |
| A10 | asdf my thing is broken please help fix idk what happened | 3 | True | low | 5943.5 |