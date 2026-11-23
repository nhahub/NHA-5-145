# CAP-06 provisioning signature verification

26 October 2026. Owner-approved local preparation for the
[offline provisioning design](../specs/2026-10-25-cap06-offline-provisioning-design.md).
This closes the retained Caddy publisher-signature and nftables RPM-signature
checks for the exact bytes below. It does not install them, approve the complete
host RPM transaction, authorize another AWS boot or qualify current security
status. No AWS/account, SSH, provider-key or ledger access was involved.

## Caddy 2.11.7

The [official Caddy verification contract](https://caddyserver.com/docs/signature-verification)
describes Fulcio certificates, detached signatures and Rekor transparency records.
The [v2.11.7 release](https://github.com/caddyserver/caddy/releases/tag/v2.11.7)
actually names the archive's certificate `caddy_2.11.7_linux_amd64.pem`; it is not
named `.tar.gz.pem`. The corresponding signature is
`caddy_2.11.7_linux_amd64.tar.gz.sig`. The checksum list has its own `.pem` and
`.sig` assets. All five small verification inputs were downloaded from that
official release and matched its API-reported lengths and SHA256 values.

Both certificates bind the exact expected identity and issuer:

```text
identity: https://github.com/caddyserver/caddy/.github/workflows/release.yml@refs/tags/v2.11.7
issuer:   https://token.actions.githubusercontent.com
source:   72dd0fb067f6d7826c7f79907670ba4a713bfe37
```

Two independent verification targets passed, each with process exit 0 and
`Verified OK` from Cosign, with SCT and transparency-log verification enabled:

| Target                            | SHA256                                                             | Retained Rekor integrated time |
| --------------------------------- | ------------------------------------------------------------------ | ------------------------------ |
| `caddy_2.11.7_linux_amd64.tar.gz` | `727b91701a392de6ebc5027509f548bf39979e5216340d0faed8fa5e69c84f8b` | `1791006686`                   |
| `caddy_2.11.7_checksums.txt`      | `5d27b76b95f496638d79208c55250317b8755fd9e90005f7466aa32956944a90` | `1791006744`                   |

The archive certificate's validity is 3 October 2026, 05:51:24–06:01:24 UTC;
the checksum certificate's validity is 05:52:24–06:02:24 UTC. These short-lived
certificates are validated at the signed log time, rather than requiring their
leaf validity to extend to installation day. The downloaded archive remains the
same retained 18,113,754 bytes; no new Caddy executable was run during verification.

### Verifier and offline material

Cosign was downloaded as a portable Linux executable from the
[official v3.1.4 release](https://github.com/sigstore/cosign/releases/tag/v3.1.4):
145,688,404 bytes, SHA256
`424e2c97d0b45fd7a6b608a87f090f35633f4c23ece5f092d48bba11aaf4bbfa`.
Its exact bytes were checked against the official HTTPS release API digest before
execution. **The verifier's own publisher signature was not independently
bootstrapped.** This official-HTTPS/checksum tool bootstrap is an explicit trust
boundary, not a claim that a checksum authenticates its publisher by itself.

The [versioned Cosign CLI contract](https://github.com/sigstore/cosign/blob/v3.1.4/doc/cosign_verify-blob.md)
accepts a protobuf bundle and explicit `--trusted-root`. The detached release
material and exact matching Rekor entry/proof were placed into v0.3 Sigstore
bundles. Preparation asserts that the entry's artifact hash, certificate and
signature exactly match the downloaded inputs. Cosign, rather than the preparation
script, then performs the actual artifact verification. No
`--insecure-ignore-tlog` or `--insecure-ignore-sct` was used.

The trusted root was collected from the
[official Sigstore TUF repository](https://tuf-repo-cdn.sigstore.dev/): root
versions 1 through 16, timestamp 818, snapshot 166 and targets 14. A local
cryptography cross-check verified every root update against both the preceding
and new root signature thresholds, then the timestamp/snapshot/targets role
thresholds, exact versions, current metadata expiry and trusted-root target
length/hash. TUF uses OLPC canonical JSON; ordinary JSON string escaping is not a
substitute for it when a key contains literal newlines.

The root-1 bootstrap SHA256 is
`cd7549b15e7b4e660a89c950bca1bce262a524a5cf909952b66951b5c8667bc6`.
It was obtained from the official HTTPS repository, not an independently supplied
out-of-band fingerprint. The resulting `trusted_root.json` is 6,787 bytes,
SHA256 `6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66`.
Metadata was checked for 26 October 2026; repeat freshness validation when preparing
a later install. Historical expired intermediate root versions are update-chain
inputs, not the final trusted metadata.

The two actual Cosign runs used the retained image
`public.ecr.aws/lambda/python@sha256:25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406`
with `--pull=never`, network none, read-only root, capabilities dropped,
no-new-privileges, UID/GID 10001, one CPU, 512-MiB memory/swap ceiling, 32 PIDs and
a private 128-MiB noexec tmpfs. All signature inputs were read-only. No owner home,
cloud credentials, browser state, project key material or Docker socket was
mounted. The explicit trust input avoids default online trust discovery; network
is also denied by the container boundary.

Exact archive-verification command inside that sandbox:

```sh
/signatures/cosign-linux-amd64 --timeout=30s verify-blob \
  --bundle=/signatures/caddy-archive.sigstore.json \
  --trusted-root=/signatures/trusted_root.json \
  --certificate-identity=https://github.com/caddyserver/caddy/.github/workflows/release.yml@refs/tags/v2.11.7 \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  /caddy/caddy_2.11.7_linux_amd64.tar.gz
```

Three additional no-network Cosign checks refused with exit 1: a one-byte-altered
checksum list, the exact valid blob with a wrong release identity, and the exact
valid blob with a wrong OIDC issuer. The errors identified signature, SAN identity
and issuer mismatches respectively. Receipts are `output/caddy-negative-results.json`
and the per-case invocation/stdout/stderr files.

For the checksum list, use its own `caddy-checksums.sigstore.json` bundle and
`/signatures/caddy_2.11.7_checksums.txt` blob. These are the exact versioned flags,
not the old documentation's experimental Cosign v1 command.

## Native nftables RPMs

All 14 retained RPMs in `.scratch/cap06-host-isolation/tools/inventory.json`
matched their expected lengths/SHA256 and passed verbose native RPM signature
verification against a newly initialized private RPM database. No system RPM
database was changed; no package installation or scriptlet execution occurred.
The two refusal checks also passed: a one-byte-modified RPM failed verification,
and the original RPM failed against an empty keyring with `NOKEY`.

The official Amazon key inside the pinned AL2023-based image has SHA256
`664b632018bd84f9b249be7bd26937c560edb2f2bfc0cbc01ec5a7b4e06aad56`
and full primary OpenPGP fingerprint:

```text
B21C 50FA 44A9 9720 EAA7 2F7F E951 904A D832 C631
```

The probe derives the full v4 fingerprint from the public-key packet and checks
the imported key rather than relying only on the short displayed `d832c631`
suffix. Native `rpm` version is 4.16.1.3. AWS identifies
`RPM-GPG-KEY-amazon-linux-2023` as the core package/repository key distributed in
`system-release`; see the
[official AL2023 key table](https://docs.aws.amazon.com/linux/al2023/ug/repo-metadata-signing.html#repo-metadata-signing-gpg-keys).
Trust here starts with the pinned official image's key bytes, not an arbitrary
newly imported public key. The real host key/provider inventory still must be
reconciled during its later authorized inspection.

The verified fixture covers nftables, libnftnl, libmnl, gmp, jansson, readline,
ncurses-libs, ncurses-base, iptables-libs, libnetfilter_conntrack, libnfnetlink,
libpcap, libibverbs and libnl3. The exact versions, requirements and scriptlet
text are retained in the receipt. The nftables seed remains
`nftables-1:1.0.4-3.amzn2023.0.3.x86_64`, SHA256
`f04fa5408e365de1a2ad1f1ed9b50f5c29d2287f1061e58af47ef3a1ece12ab1`.

Read-only scriptlet inspection confirms that first install invokes
`/usr/lib/systemd/systemd-update-helper install-system-units nftables.service`.
Keep the proposed persistent vendor-service mask before a later native install,
verify it remains inactive afterward, and do not load its vendor ruleset.

**These 14 verified fixture RPMs are not the host installation list.** The original
host's complete installed NEVRA/provider inventory remains unavailable. Resolve
the minimal additive transaction against that actual inventory and the fixed
repository; do not downgrade newer existing libraries to the historical fixture.
Any newly needed RPM must receive its own hash/signature/scriptlet checks.

## Evidence and remaining boundary

Ignored owner-held material is under
`.scratch/cap06-offline-provisioning/signatures/`: official release/API inputs,
Cosign acquisition receipt, detached checks, Rekor entries, TUF metadata/validation,
two prepared bundles and the exact verification script. The `output/` directory
contains per-run invocation, exit/stdout/stderr records and
`nft-rpm-signatures.json`. The latter receipt's SHA256 is
`bbec62e9c7ee10761f3daaa97266a3d8a17de0ee1a06032930f0aec86b4ab198`.
Raw acquisition/preparation records describe their earlier pre-execution state;
the later invocation/exit records establish what actually ran.

The package-signature gap for these retained inputs is closed. The host-specific
dependency closure, installation, timer repair, real-host boot, swap activation
and persistence, service isolation, capacity and production activation remain
unperformed. No inference or new AWS-credit use follows from signature checking.
