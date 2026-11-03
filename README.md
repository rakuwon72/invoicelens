# InvoiceLens

An offline, AI-assisted research prototype for duplicate-invoice review in US accounts payable. **Synthetic data only. Not a payment approval system.**

Public repository: [rakuwon72/invoicelens](https://github.com/rakuwon72/invoicelens).

## Open the demonstration

Unzip the project and open `index.html` in a modern browser. No server, installation, API key, or internet connection is needed. Choose a case, compare both records, inspect feature contributions, reveal the expected synthetic outcome, and record a reasoned reviewer decision. Export review history as JSON. Decisions persist in browser local storage when available; this is not authenticated or tamper-proof storage.

## Reproduce the experiment

Python 3.10 or later; standard library only:

```sh
python invoicelens.py
python -m unittest -v
```

The first command trains the model from `data/train.json`, scores the fixed evaluation cases, and rebuilds `model.json`, `results.json`, `results.csv`, and `index.html`. The second runs 10 software checks. The reference run used CPython 3.14 on Windows. Browser checks passed in Microsoft Edge at desktop and mobile viewport sizes, including reason validation, decision persistence, export, error filtering, and no JavaScript errors.

## What is implemented

- Pair scoring over structured, synthetic invoice records, with exact Decimal comparisons for amounts and explicit currency/date checks.
- A real logistic-regression classifier trained locally; seven transparent features and no pretrained or hosted LLM at runtime.
- Three deterministic baselines; fixed evaluation data; per-case expected labels and rationales.
- Evidence hashes, model hash, policy version, signed feature contributions and an offline reviewer with decision export.

No PDF extraction, OCR, semantic embeddings, supplier-master reconciliation, invoice-history ingestion, production candidate retrieval, payment integration, access control or immutable audit ledger is implemented. OCR-like errors are manually simulated in structured fields. These boundaries matter: the demo evaluates supplied pairs, not discovery across a ledger.

## Data and model

All business names, amounts, invoice records, scenarios and labels are invented. Public audit materials informed the problem, not training labels. `data/train.json` contains 240 generated pairs (120 positive and 120 negative), using a fixed generator seed of 20261103. `generate_data.py` reproduces these files from the project folder. `data/test.json` contains 26 manually authored scenario pairs: 12 duplicate obligations, 10 distinct obligations and 4 unclassified routing cases. No training base-record hash occurs as a test base-record hash. Test cases share two base invoice families, so they are not independent samples. Training and test cases also share scenario motifs. Neither separation establishes real-world generalization.

Model: logistic regression, full-batch gradient descent, 1,500 steps, learning rate 0.25, L2 coefficient 0.01, zero initialization. Features: vendor/name similarity, invoice-number similarity, description similarity, exact amount equality, date proximity, same service period and different service period. Text similarity is character sequence similarity, **not semantic understanding**. Missing periods encode both period indicators as zero. The score is sigmoid(bias + sum(weight * feature)). Feature weights and training-data hash are in `model.json`.

The threshold of 0.60 was specified before the first evaluation and was not tuned on test results. The score is uncalibrated. All thresholds and feature choices are illustrative; no validation set or production calibration was used. Existing ERP controls must remain in place: this prototype is not a replacement and does not implement an ERP-control union.

## Decision order

1. Missing/invalid required values: DATA REVIEW.
2. Credit notes, non-invoice types or non-positive amounts: SPECIALIST REVIEW.
3. Either currency outside USD: OUT OF SCOPE.
4. Unequal face amounts: NO FLAG under the narrow equal-amount policy.
5. Otherwise, score >= 0.60: REVIEW; below threshold: NO FLAG.

Partial duplicates are deliberately included as a stress case: the equal-amount gate misses them. NO FLAG does not certify uniqueness or authorize payment. Scores displayed on routed cases are informational only and do not override routing.

## Actual results

Classification denominator: 22 labeled pairs. Precision = true positives / flags. Recall = true positives / 12 known duplicates. The 4 routing cases are excluded from classification metrics.

| Method | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Exact vendor ID + raw invoice number + amount | 3 | 1 | 9 | 9 | 75.0% | 25.0% |
| Vendor ID + normalized invoice number + amount | 4 | 1 | 8 | 9 | 80.0% | 33.3% |
| Fuzzy vendor >= 0.55 + same amount + date within 45 days | 8 | 6 | 4 | 4 | 57.1% | 66.7% |
| Learned score + deterministic gates | 7 | 3 | 5 | 7 | 70.0% | 58.3% |

All baselines are restricted to positive USD invoices with equal face amounts. Normalization lowercases and removes non-alphanumeric characters. All 4 routing checks passed. Software tests passing does not mean the model correctly classified every example.

### Where it fails

- Misses: E03 (supplier alias), E07 (alias plus changed number), E08 (abbreviation), E09 (paraphrased description), E10 (partial duplicate).
- False flags: E14 (missing recurring period), E15 (two legitimate deliveries on one day), E21 (legitimate later reorder).
- The learned date-proximity coefficient is -0.405, the opposite of a useful general expectation here. Invoice similarity also has a small negative coefficient. Correlated, simplistic synthetic training templates create misleading relationships. E21 illustrates the danger; this model should not be deployed.
- Duplicate labels rely on fictional underlying histories described in the rationales. Some pairs cannot be resolved from displayed fields alone. That is an information limitation, not something a higher score can fix.

The experiment demonstrates an auditable review workflow and a measurable precision/recall trade-off; it does not prove AI is necessary or profitable. The broad fuzzy baseline has better recall. Before any real pilot, obtain authorized, de-identified historical cases and practitioner labels, split by supplier/time, reserve a validation set, inspect leakage, calibrate the threshold against a review budget, and compare every approach on the same independently labeled test set. Track candidate-retrieval recall separately.

## Architecture and boundaries

Implemented: structured pairs -> validation/Decimal gates -> learned ranker -> evidence packet -> local human review -> JSON export. Source records and feature definitions are inspectable; hashes identify record content but do not prove source authenticity.

Proposed production additions: retain original invoice files and page/field provenance; verify extracted fields; retrieve candidates from the ledger and supplier master; keep existing exact-match controls; write decisions to an authenticated append-only store; reconcile refunds, cancellations and settlement before reporting savings. A controller owns policy/threshold changes and approves releases; a separate payment approver remains responsible for execution. No online learning from unverified reviewer clicks.

## Sources (accessed 3 November 2026)

1. [North Carolina Central University, Accounts Payable Internal Audit, AUD24001, 30 May 2024](https://www.nccu.edu/sites/default/files/2024-06/Interna-Audit-Report-Accounts-Payable.pdf), Finding 7, printed page 17. The report describes $140,307.55 across 70 duplicate-payment invoices and invoice-number modification issues. Historical case, not an estimate of general prevalence or current conditions.
2. [New York State Comptroller, Unique Invoice Number Requirements](https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii5b-unique-invoice-number-requirements). Discusses unique invoice references and controls for multiple vouchers/partial deliveries. Used as a design counterexample, not a rule applicable to every US organization.
3. [Washington State Auditor, Paying vendors twice is a problem, 2022](https://sao.wa.gov/the-audit-connection-blog/2022/paying-vendors-twice-problem-sao-offers-tips-prevent-duplicate-payments). Describes weaknesses around duplicate supplier records and inconsistent invoice entry. Web access to sources 2 and 3 was limited to search-index text; full-page fetches were blocked. No legal-compliance conclusion is drawn.

## Files

- `invoicelens.py`: training, scoring, exact gates, evaluation and static report generation.
- `generate_data.py`: reproducible synthetic training/evaluation fixtures.
- `data/*.json`: supplied training and evaluation records.
- `model.json`: learned coefficients and provenance.
- `results.json` / `results.csv`: complete measured results.
- `reviewer.template.html` / `index.html`: reviewer source / self-contained generated demo.
- `test_invoicelens.py`: financial-input, abstention, provenance and reproducibility checks.

## AI use and hosting

Codex, based on GPT-6, assisted with research, problem selection, design, coding, synthetic fixtures, testing, analysis and writing. No practitioner interviews or independent candidate-originated technical insights are claimed. No paid model or API is required. The accompanying brief has the AI-use appendix; the separate logs archive contains the visible conversation.

Use the public repository URL above for a prototype/repository submission link. Download the repository ZIP and open `index.html` for the offline demo, or clone it and run the commands above. GitHub Actions regenerates the experiment and runs the checks on Python 3.10 and 3.14. The written brief and private chat logs are separate submission artifacts and are not included in this public repository.
