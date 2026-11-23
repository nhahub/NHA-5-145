# Second frozen synthetic development pilot

Frozen 7 October 2026 before fitting: **308 source records, 263 eligible, 45 excluded; 210 training / 53 validation / zero unseen**. The 37 connected components stay whole. All data is exposed and synthetic, with draft labels rather than independent human gold.

- [Release](release.json): immutable examples, assignments, exclusions, allocation policy and source hashes.
- [Groups](groups.json): complete membership including excluded turns and context-linked cases.
- [Protocol](../../../../docs/cap03-expanded-pilot-protocol.md): pre-fit rules and explicit three-component mutation limitation.
- [Results and reproduction](../../../../docs/cap03-expanded-pilot-results.md): all trials and limitations.

Pilot 1 remains unchanged. This is a separate development exception; the final CAP-02 splits remain unfrozen and empty. Do not relabel or reallocate this version after seeing scores.
