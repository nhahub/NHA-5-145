# CAP-03 frozen synthetic holdout evidence

See [closeout and methodology](../../../docs/cap02-cap03-closeout.md) and the
[executed notebook](../../../notebooks/cap03-synthetic-holdout.ipynb).

- `report.json`: eight contenders, all metrics, confusion matrices, language slices,
  fixed source bindings, full paid ledger and measured cost.
- `offline.json`: aggregate final offline evidence, including explicit recovery provenance.
- `initial-offline.json`: original results including two encoder startup failures.
- `recovery.json`: first predictions for the two embedding models after cache repair.
- `recovery-source.py.txt`: exact source executed for that recovery.
- `llm.json`: 120 single attempts; no repairs, unknown costs or failures.
- `run.json` / `initial-run.json`: invocations and environment/source bindings.
- `figures/`: comparison and raw/normalized confusion matrices, including failure column.

Synthetic and generated with a language model; no independent human labels.
Balanced and often explicitly disambiguated prompts are not real traffic. Equal
raw-message inputs do not imply equal prior training. No whole-agent safety,
constraint extraction or browser-completion conclusion follows from these scores.
