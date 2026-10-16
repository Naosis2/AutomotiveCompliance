# Progress

- S1 skeleton, S2 polite fetcher (with redirect/IP checks), S4 discovery, S5 extraction
  (JSON-LD + generic text), S6 engine + 2 DRAFT rules, S7 Excel report, S3 scan workflow: built.
- Not done: S0 (repo + brief import), real platform fingerprints (need S4 fixtures),
  real rule set ON-01..08 (need docs/BRIEF.md and OMVIC guideline), S8 labelling script,
  S9 AI check, S10 stats sheet.
- rules/on.yaml v2: 10 rules from the OMVIC summary Taylor supplied (fees, levies, tied products,
  identity, as-is x2, limited supply, APR, term, lease km). Ids are descriptive; map to ON-xx
  and confirm section numbers against the real guideline. Low-confidence rules go to "To review".
- Not expressible as text patterns yet (need AI check): used-vs-new model year, prior use,
  photo/trim mismatch, sold-but-listed.
