# Shopping Copilot — final submission (23 November 2026)

DEPI graduation project · AWS ML Engineering · NHA-5-145

An Arabic-first shopping assistant that turns everyday requests (Egyptian Arabic, English, Franco-Arabic or mixed) into visible, checked actions on a real storefront.

## Contents

| Item | File |
| --- | --- |
| Presentation (PowerPoint, 19 slides with demo clips and Morph transitions) | [presentation/Shopping-Copilot-Graduation-Defense-2026-11-24.pptx](presentation/Shopping-Copilot-Graduation-Defense-2026-11-24.pptx) |
| Presentation (PDF copy) | [presentation/Shopping-Copilot-Graduation-Defense-2026-11-24.pdf](presentation/Shopping-Copilot-Graduation-Defense-2026-11-24.pdf) |
| Demo video (4:22, 1080p) | [video/shopping-copilot-demo-2026-11-23.mp4](video/shopping-copilot-demo-2026-11-23.mp4) |
| Infographic | [infographic/shopping-copilot-infographic.png](infographic/shopping-copilot-infographic.png) · [PDF](infographic/shopping-copilot-infographic.pdf) |
| Source code | [source/](source/) — start with [source/README.md](source/README.md) |

## Demo video

Recorded on 23 November 2026 on the deployed site (`app.scpilot.tech`, AWS Stockholm) with the real language model and the fictional store. Nine scenes: advice, a checked add («تقصد خطوة سريعة؟»), a colour change done as add-then-remove, opening a product by name, a page refresh that keeps the page and the conversation, adding from the open page, a negated removal, a guarded "empty the cart" with Confirmation, and a three-step request. Waiting time is shown in real time; captions quote each Arabic request with an English gloss.

## What changed since the defense

- Shopper state (cart and Copilot conversation) is saved on the host disk for seven days and survives restarts.
- A page refresh keeps the current store page and the conversation.
- A colour change is two normal cart changes (add the new variant, remove the old one), each with Undo.
- Misreads seen live were fixed in code: the product the shopper names wins, an unnamed product is confirmed first, and filter values the store does not know are refused.

## Known limits

- Placing an order is left to the shopper: the Copilot never fills card fields, so it stops before submitting checkout.
- A conditional step ("only if under EGP 1,000") can be answered as advice instead of being skipped.
- All evidence comes from one controlled storefront with fictional products and payments.

## Live demo

The invitation-only demo starts from <https://djlnacpannb9q.cloudfront.net/> (access code supplied privately). The host wakes on demand and stops after 60 idle minutes; the demo window closes 4 December 2026, 23:59 Cairo.
