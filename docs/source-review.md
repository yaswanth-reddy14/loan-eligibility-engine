# Live source review register

Status on 19 October 2026: **no live source approved**. The independent engineering audit confirmed that the workflow gate and API both enforce this configuration. It did not establish new legal permission or successfully crawl a live lender. Notes below retain the implementation's existing research status, not fresh independent approval.

| Candidate official page | Existing review evidence | Current decision |
|---|---|---|
| https://www.icici.bank.in/personal-banking/loans/personal-loan/eligibility | Prior research browser reported an accessible eligibility page; robots and published automation restrictions were not verified. | Disabled. Accessibility alone does not establish permitted automated extraction. |
| https://www.hdfcbank.com/personal/borrow/popular-loans/personal-loan/eligibility-and-documentation | Prior page and robots fetch failed in the research browser. | Disabled. Failure does not justify guessed criteria or an alternate unofficial source. |
| https://www.axisbank.com/retail/loans/personal-loan/eligibility-documents | Prior robots lookup redirected to axis.bank.in and the fetch was unavailable; usage restrictions were not verified. | Disabled pending review of the current official site and terms. |

The executable configuration is `n8n/sources.json`, embedded in generated A JSON. Approval requires dated page/robots/terms evidence, allowed access and automation scope, explicit criterion text/source/time, and source-specific extraction tests. If terms remain unclear, keep the source disabled and seek permission or a permitted feed. Robots rules are guidance, not an independent legal permission grant.

Do not mark a product VERIFIED merely because a parser returns schema-valid JSON. The current live extractor always persists UNVERIFIED and incomplete eligibility, and production matching excludes it. Fixtures are separate, fictional, have embedded evidence and use example.org URLs. Optional LLM extraction is disabled.

After an actual source review, update this register and sources.json, run `scripts/generate_workflows.py`, validate/import the exports, and retain successful live A execution and crawl evidence. No future successful run should be backfilled into today's evidence.

## Re-review on 21 October 2026

No live source was enabled. ICICI robots could not be accessed through the research tool and the candidate general terms URL returned 404; HDFC robots returned 403; Axis robots redirected to axis.bank.in and could not be retrieved. Searches surfaced product-specific terms, which do not establish general automation permission for the eligibility pages. No explicitly permitted alternative providing the required product eligibility data was established in this review. These tool failures are observations, not proof that every ordinary browser request is blocked.

Remaining blockers are affirmative permission or a suitably licensed official feed, source-specific saved response fixtures/tests, verified rate/criterion provenance, and an actual allowed fetch-to-PostgreSQL execution. Accessibility alone does not clear these gates. Sources remain false in `n8n/sources.json`; offline fictional fixtures remain available.
