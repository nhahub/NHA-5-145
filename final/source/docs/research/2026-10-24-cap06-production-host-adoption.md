# CAP-06 production host adoption: source review

24 October 2026. Public primary-source research and local evidence inspection only.
This note creates no resource, installs no package, changes no runtime pin and
makes no account/provider request. Actual account observations belong to the
coordinator's separately retained receipts. Controlled Storefront, Stockholm,
Free-plan and USD0cash constraints remain binding.

**Finding:** The prepared native proof establishes application compatibility with
its recorded tools. Production adoption still needs an exact EC2 image/package
record. In particular, Node24.13.0 predates current security fixes, and the Lambda
image's Python3.12.15 is not evidence that the EC2 RPM interpreter has that version.

## Image identity and repository version

AWS documents the public parameter
`/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64` and requires
checking the Amazon owner alias. Its default kernel changed to6.18 on17August2026;
older running instances retain their booted kernel. The parameter is a moving
selection, not an immutable approved image. Freeze the resolved image ID and
describe its Amazon ownership, available state, architecture, name/build date,
root-device mapping and relevant deprecation/Allowed-AMIs information in the
actual account before proposing creation. The coordinator reported parameter
version196 resolving to `ami-0111419d42d14a400`; this research did not independently
query it. [AWS AL2023 EC2 guide](https://docs.aws.amazon.com/linux/al2023/ug/ec2.html),
[DescribeImages](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-images.html).

AL2023 AMIs use versioned package repositories. Record the exact repository release
and package NEVRAs rather than allowing an unreviewed `latest` update at first
production boot. AWS recommends applying available release updates; selecting
individual security fixes is the exception. Use the selected release's update and
support metadata to decide what is adopted, then test that same selection.
[Package/OS updates](https://docs.aws.amazon.com/linux/al2023/ug/managing-repos-os-updates.html),
[deterministic updates](https://docs.aws.amazon.com/linux/al2023/ug/deterministic-upgrades-usage.html).

## Python adoption and offline application environment

AL2023 supplies namespaced Python3.12 packages alongside its system Python3.9.
Keep `/usr/bin/python3` unchanged; use the versioned interpreter for the application.
AWS's Python packages have their own upstream-aligned support periods. Python3.12
is in upstream security support, scheduled through October2028. Check the exact
RPM's `dnf supportinfo` and applicable Amazon Linux advisories rather than inferring
patch status from the major/minor version alone.
[Python in AL2023](https://docs.aws.amazon.com/linux/al2023/ug/python.html),
[package support](https://docs.aws.amazon.com/linux/al2023/release-notes/support-information.html),
[Python version lifecycle](https://devguide.python.org/versions/).

The retained official repository metadata for2023.12.20260914 contains
`python3.12` and `python3.12-libs` through3.12.14-2.amzn2023.0.1 and no3.12.15 entry.
This is a **historical repository observation**, not the selected October AMI's
installed package version. Its retained primary.xml.gz SHA256 is
`bca2711e5684cf73a38f962d50f108d4a8288cc1c89c75b512f45ccb32ecf040`; provenance is in
the prior Git acquisition receipt. The current EC2 candidate therefore still needs
an exact package record and native interpreter observation.
[Historical public repository metadata](https://cdn.amazonlinux.com/al2023/core/guids/6ac5adb46dce32d21e7bd0c7e97948be299a34e9e2f7a2cb3ca6ae047b0f869e/x86_64/repodata/primary.xml.gz).

The selected image's **2023.12.20261021 repository** was subsequently resolved
through its official x86_64 and SRPMS mirror lists. Published compressed and
uncompressed SHA256/lengths match both primary indexes and the x86_64 updateinfo
index. The highest matching repository candidates are still
`python3.12-0:3.12.14-2.amzn2023.0.1.x86_64` and
`python3.12-libs-0:3.12.14-2.amzn2023.0.1.x86_64`. These are repository records,
not installed AMI observations or approved interpreter bytes.
[Fixed-release mirror](https://cdn.amazonlinux.com/al2023/core/mirrors/2023.12.20261021/x86_64/mirror.list),
[primary index](https://cdn.amazonlinux.com/al2023/core/guids/2f9b939514669e37a7d960f1674eb90574bd9a9378a35bd965ebf50114e9be96/x86_64/repodata/primary.xml.gz),
[source primary index](https://cdn.amazonlinux.com/al2023/core/guids/2f9b939514669e37a7d960f1674eb90574bd9a9378a35bd965ebf50114e9be96/SRPMS/repodata/primary.xml.gz).

| Candidate                                                                                                                                                                          | Published RPM SHA256                                               |      Bytes |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ---------: |
| [python3.12](https://cdn.amazonlinux.com/al2023/blobstore/b0110c2dd0a9e7335826a8fbbf9222dbc0df2f9d10dd38189382645065175889/python3.12-3.12.14-2.amzn2023.0.1.x86_64.rpm)           | `b0110c2dd0a9e7335826a8fbbf9222dbc0df2f9d10dd38189382645065175889` |     27,565 |
| [python3.12-libs](https://cdn.amazonlinux.com/al2023/blobstore/2f411ef99fe7380111a3d689855db0f13fd08a87e65458e606f3b8e08c23d2ca/python3.12-libs-3.12.14-2.amzn2023.0.1.x86_64.rpm) | `2f411ef99fe7380111a3d689855db0f13fd08a87e65458e606f3b8e08c23d2ca` |  9,674,254 |
| [shared source RPM](https://cdn.amazonlinux.com/al2023/blobstore/51d13377596cfe2de2f62f9e786fb0b2a75883698c499b6acfea38554cf15063/python3.12-3.12.14-2.amzn2023.0.1.src.rpm)       | `51d13377596cfe2de2f62f9e786fb0b2a75883698c499b6acfea38554cf15063` | 20,884,093 |

At metadata-resolution time no RPM was downloaded or signature-verified. The ignored receipt at
`.scratch/cap06-production-host/python-repository/python-candidates.json` records
the exact URLs/checksums/bounds, pip/pip-wheel23.2.1-4.amzn2023.0.12 candidates and
26 relevant repository advisories. ALAS2124 names the selected Python3.12 RPM;
ALAS3173 names the pip update. Repository fix metadata does not establish absence
of other vulnerabilities: the vendor's CVE-2026-12345 page still lists Python3.12
as pending a fix for a local temporary-directory cleanup race. Applicability and
current remediation therefore remain part of interpreter security adoption,
without asserting that this application is exploitable.
[ALAS2124](https://alas.aws.amazon.com/AL2023/ALAS2023-2026-2124.html),
[ALAS3173](https://alas.aws.amazon.com/AL2023/ALAS2023-2026-3173.html),
[vendor pending-fix record](https://explore.alas.aws.amazon.com/CVE-2026-12345.html).

Subsequent authorized candidate acquisition downloaded the four Python/pip RPMs
and15 fixed-release shared-library RPMs, checked their published hashes/lengths,
and verified all19 supplier signatures against the pinned image's Amazon key
(`d832c631`) in a temporary private RPM database. This is extraction only: no
package installation, downloaded-binary execution, global environment change or
actual host acceptance occurred. The final private-prefix archive is
`.scratch/cap06-production-host/python-3.12.14/output/python-3.12.14-complete2-prefix.tar`,
SHA256 `e0531746fc5e1ff28d941af91b4d30ea93fd5b2d3c10c94ec8318d8f8d0e5ce8`,
81,438,720bytes. Its corresponding `python-rpm-complete2-extraction.json` binds
every selected file, package signature and21 separately exported regular SONAME
files under `output/native-libs-complete2/`. Only the pinned image's glibc loader,
libc and libm remain external; actual symbol compatibility still needs execution.

The extractor preserves safe internal relative symlinks and materializes CPIO
hardlink members as regular files. It explicitly maps libgcc's two `/lib64` payload
paths into the private `usr/lib64` layout, with provenance. It omits non-`usr`
OpenSSL configuration paths and two dangling vendor build-ID debug links, rather
than allowing runtime links to escape the prefix. Original and failed intermediate
archives/receipts are retained separately. No glibc/loader replacement or provider
activation is implied.

The coordinator subsequently executed the complete prefix in the bounded,
network-none AL2023 container. The native smoke observed Python3.12.14,
`cpython-312-x86_64-linux-gnu`, OpenSSL3.5.8 and all14 checked native standard-library
modules from the private prefix, with no Lambda/site-package fallback. Vendor
pip23.2.1 also starts from that prefix. The retained receipt is
`.scratch/cap06-production-host/python-3.12.14/smoke-complete/output/vendor-python.json`.
This resolves the candidate's isolated symbol/import question. The subsequent
[alignment proof](../cap06-vendor-runtime-alignment.md) also passes a clean
application build and repeated startup under those same bytes. No EC2 package
installation or production-security adoption follows from it.

Local code inspection found `TemporaryDirectory` in the release builder and
installer (`deploy/artifact.py`), not in project Agent request handlers. Both
staging trees use the caller's output parent. **Relevance inference:** the vendor
race therefore warrants review of staging ownership, other same-UID processes and
whether an attacker can mutate a cleanup tree; version text alone cannot establish
safety. The private local proof does not replace actual host privilege/filesystem
evidence or resolve the vendor's pending-fix status.

AWS describes Lambda Python images as bundles containing a language runtime and
Lambda runtime-interface tooling. Their successful local execution does not adopt
that bundle as the native EC2 interpreter. A project-consistent candidate is the
reviewed AL2023 Python3.12 RPM plus an isolated environment at the existing unit's
`/opt/shopping-copilot/python` path. Build that environment from the adopted host
interpreter; do not copy a pre-existing venv or `/var/lang` directory from the
Lambda image. [Lambda Python image contents](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html),
[Python venv behavior and portability](https://docs.python.org/3.12/library/venv.html).

Install only the separately locked28wheel application closure, using the verified
wheelhouse with no index, required hashes, binary-only artifacts and no dependency
resolution. Hash checking needs every requirement/dependency pinned and hashed.
The project already verifies the complete closure before its no-deps installation.
A host patch differing from the recorded3.12.15 marker requires an explicit target
reconciliation and repeated native imports/startup; do not relabel the old proof or
set production_interpreter_approved merely because the ABI remains cp312.
[pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/).

## Native Node and Caddy

The current official Node24 LTS release is24.22.1, published21October2026 as a
security release. The advisory includes HIGH-severity fixes affecting24.x,
including DNS/TLS validation and Brotli decoding. The older tested24.13.0 binary
therefore remains historical functional evidence; it should not receive a current
production security-adoption claim. Review24.22.1 as a replacement candidate,
verify the official signed checksums/archive/binary, and repeat the affected native
Storefront, persistence, private API and Agent integration checks. No pin or binary
was changed by this note.
[Node24.22.1 release](https://nodejs.org/en/blog/release/v24.22.1/),
[21October security advisory](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases),
[official downloads and signed-checksum verification](https://nodejs.org/en/download).

Caddy's official2.11.7 release fixes HTTP/2 proxy crashes and interrupted streams
introduced in2.11.6, relevant to the Copilot's streaming traffic. Caddy documents
release-asset signature verification in addition to hashes, and recommends a
system service for production. Retain the reviewed static binary and project-owned
units/ACME state; do not install a distribution package that silently starts a
second default service. Version/adaptation success still does not prove live TLS,
streaming, systemd permissions or reboot behavior.
[Caddy2.11.7](https://github.com/caddyserver/caddy/releases/tag/v2.11.7),
[asset signatures](https://caddyserver.com/docs/signature-verification),
[installation/service behavior](https://caddyserver.com/docs/install).

## Account-plan evidence and remaining decision

The actual CLI read operation is `freetier get-account-plan-state`. Its response
includes plan type (FREE/PAID), status, remaining credits and expiration. AWS lists
Free Tier's global endpoint in us-east-1; reading it does not create a Virginia
resource. Restricted project permissions can still deny that read. Preserve the
denial or obtain current console evidence rather than upgrading the account or
inventing a balance. General Free-plan documentation permits a proof of concept
until credit exhaustion or the six-month deadline; it is not evidence of this
account's current eligibility, service quotas or the proposed workload's costs.
[CLI operation](https://docs.aws.amazon.com/cli/latest/reference/freetier/get-account-plan-state.html),
[API response](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_freetier_GetAccountPlanState.html),
[global endpoint](https://docs.aws.amazon.com/general/latest/gr/billing.html),
[Free-plan FAQ](https://aws.amazon.com/free/free-tier-faqs/).

Before actual creation, the concrete proposal still needs the resolved Amazon
AMI/repository/RPM/security records; selected Node/Caddy binary provenance; actual
subnet/route/IGW and quota eligibility; current plan/credit/expiry evidence; exact
resource, workload-cost and rollback bindings. After approved provisioning, verify
the actual interpreter/native dependencies, service users/systemd/PID1/reboot,
metadata/capability/log boundaries, protected model-key/remaining-credit custody,
qualified readiness and measured capacity. The current synthetic-authority proof
closes none of those external acceptance claims.
