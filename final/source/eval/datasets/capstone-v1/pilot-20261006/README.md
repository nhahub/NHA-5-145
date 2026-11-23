# Frozen synthetic development pilot

Owner-approved 6 October 2026. This separate release permits an exploratory CAP-03 experiment while CAP-02 final release and unseen evaluation remain open.

`release.json` contains 82 training, 21 validation and 37 excluded records derived from the 140 synthetic source messages; there are zero unseen examples. Eligible text and labels, reviewed connected groups, exclusions and input hashes are frozen before training. Both original annotation files retain their draft/exposed metadata; this exception does not promote them to independently reviewed gold.

See [protocol](../../../../docs/cap03-pilot-protocol.md), [annotation review](../../../../docs/cap02-annotation-review.md) and [results](../../../../docs/cap03-pilot-results.md). The final `../splits.json` placeholder remains unfrozen and unassigned. Do not overwrite this pilot after reviewing scores; use a new version for subsequent data or protocol changes.
