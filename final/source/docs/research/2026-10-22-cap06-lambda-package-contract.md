# CAP-06 Lambda Python package contract

Checked 22 October 2026 against AWS, PyPA and exact-version publisher metadata
on PyPI. Used agent-reach's Jina web route and the web reader for primary sources.
This research performed no AWS API/model calls, credential access, package
installation/download, resource writes or runtime activation. Reading PyPI JSON
metadata does not establish that wheel contents have been verified.

## Runtime and archive requirements

AWS currently lists `python3.12` on Amazon Linux 2023 as supported, with planned
deprecation 31 October 2028, blocked creation 30 November 2028 and blocked updates
10 January 2029. Recheck this mutable schedule before deployment.
[AWS Python runtime table](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html).

The archive must expose the handler module and dependency import roots directly
at its root, without an enclosing build directory. `/var/task` takes precedence
over the managed SDK and layers. Include Boto3 and its complete dependency set:
AWS warns that bundling an SDK dependency while relying on runtime Boto3 can
produce incompatible versions. Exclude build-machine bytecode and `__pycache__`.
AWS permits pure Python dependencies to be packaged on any local build machine;
native extensions instead need Linux/architecture-compatible wheels or a matching
Amazon Linux build.
[AWS Python ZIP packaging](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html).

The configured handler is `module.function`; AWS passes event and context to the
function. For example, `lambda_function.py` at archive root with
`def lambda_handler(event, context)` uses `lambda_function.lambda_handler`.
[AWS handler naming and signature](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html).

Lambda requires `0644` for non-executable files and `0755` for directories and
executables. Encode those POSIX archive attributes explicitly when packaging on
Windows, rather than inferring Linux access from Windows ACLs.
[AWS package permissions](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-update).

The documented limits are 50 MB compressed for direct API/SDK or console upload,
and 250 MB uncompressed including layers/custom runtimes; larger ZIP uploads use
S3. AWS uses MB to mean 1024 KB here. A local builder can enforce a stricter
50 _ 1024 _ 1024 compressed ceiling and 250 _ 1024 _ 1024 extracted ceiling without
requiring an upload or creating a bucket.
[AWS deployment size quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html).

## Narrow dependency closure

Recommendation: retain the repository's existing versions for the control-plane
imports, with no optional extras, and create a separate complete Lambda lock.
Do not copy the development environment or its Moto/cryptography/ML dependencies.
The exact-version publisher metadata below lists universal wheels and Python
requirements compatible with 3.12. This is metadata evidence, pending wheel-byte
verification by the package builder.

| Distribution      | Existing pin | Published wheel tag | Exact publisher metadata                                       |
| ----------------- | ------------ | ------------------- | -------------------------------------------------------------- |
| boto3             | 1.43.115     | py3-none-any        | [PyPI](https://pypi.org/pypi/boto3/1.43.115/json)              |
| botocore          | 1.43.115     | py3-none-any        | [PyPI](https://pypi.org/pypi/botocore/1.43.115/json)           |
| s3transfer        | 0.19.3       | py3-none-any        | [PyPI](https://pypi.org/pypi/s3transfer/0.19.3/json)           |
| jmespath          | 1.1.0        | py3-none-any        | [PyPI](https://pypi.org/pypi/jmespath/1.1.0/json)              |
| python-dateutil   | 2.9.0.post0  | py2.py3-none-any    | [PyPI](https://pypi.org/pypi/python-dateutil/2.9.0.post0/json) |
| six               | 1.17.0       | py2.py3-none-any    | [PyPI](https://pypi.org/pypi/six/1.17.0/json)                  |
| urllib3           | 2.8.0        | py3-none-any        | [PyPI](https://pypi.org/pypi/urllib3/2.8.0/json)               |
| httpx             | 0.28.1       | py3-none-any        | [PyPI](https://pypi.org/pypi/httpx/0.28.1/json)                |
| anyio             | 4.15.1       | py3-none-any        | [PyPI](https://pypi.org/pypi/anyio/4.15.1/json)                |
| certifi           | 2026.7.22    | py3-none-any        | [PyPI](https://pypi.org/pypi/certifi/2026.7.22/json)           |
| httpcore          | 1.0.9        | py3-none-any        | [PyPI](https://pypi.org/pypi/httpcore/1.0.9/json)              |
| h11               | 0.16.0       | py3-none-any        | [PyPI](https://pypi.org/pypi/h11/0.16.0/json)                  |
| idna              | 3.19         | py3-none-any        | [PyPI](https://pypi.org/pypi/idna/3.19/json)                   |
| typing_extensions | 4.16.0       | py3-none-any        | [PyPI](https://pypi.org/pypi/typing_extensions/4.16.0/json)    |

For this no-extra closure on Python 3.12, AnyIO requires `typing_extensions`,
while `exceptiongroup` is conditioned on Python below 3.11. The selected HTTPX
does not declare `sniffio`; infer dependencies from exact metadata, rather than
from an older documentation overview. Boto3's `crt` extra adds native `awscrt`
through Botocore. Keep it and optional HTTPX compression/proxy/CLI extras absent.
[AnyIO metadata](https://pypi.org/pypi/anyio/4.15.1/json),
[HTTPX metadata](https://pypi.org/pypi/httpx/0.28.1/json),
[Botocore metadata](https://pypi.org/pypi/botocore/1.43.115/json).

PyPA tags describe Python implementation/version, ABI and platform compatibility.
`py3-none-any` has no native ABI or platform requirement; `py2.py3` includes the
Python 3 tag. A universal archive can serve either Lambda architecture, but the
deployment must still choose its architecture explicitly and qualify execution.
This conclusion assumes the wheel payload matches its metadata.
[PyPA compatibility tags](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/).

## Recommended local preparation

These are proposed future packaging steps, not commands executed by this research.

1. Review a complete lock of all 14 exact pins and approved wheel SHA-256 hashes.
   Hash checking requires every transitive dependency to be pinned and hashed;
   `--only-binary=:all:` refuses source distributions. Lock review establishes
   which bytes are accepted; hashes alone do not establish publisher trust or
   prove absence of vulnerabilities.
   [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/).
2. Prepare a caller-selected wheel directory separately from offline assembly.
   The following PowerShell-compatible single-line example constrains all four
   target dimensions, avoiding Windows/native wheel selection:

   ```text
   python -m pip download --only-binary=:all: --platform any --implementation py --python-version 3.12 --abi none --require-hashes -r <complete-lambda-lock> --dest <wheel-directory>
   ```

   pip documents generic wheels still matching constrained downloads, and supports
   using the resulting directory with `--find-links` for offline installation.
   Do not claim these target flags alone validate arbitrary environment markers;
   evaluate the selected closure for Linux CPython 3.12 with no extras.
   [pip cross-target download](https://pip.pypa.io/en/stable/cli/pip_download/),
   [PyPA dependency marker specification](https://packaging.python.org/en/latest/specifications/dependency-specifiers/).

3. Build without network from that exact wheel inventory and an explicit source
   allowlist. With a full installer, use `--no-index --find-links`, hashes,
   `--only-binary=:all:`, a fresh `--target` and `--no-compile`. Avoid installing
   the complete repository or development extras. A retained wheelhouse plus lock
   separates artifact availability from index availability.
   [pip install options](https://pip.pypa.io/en/stable/cli/pip_install/),
   [pip repeatable wheelhouse installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/).
4. A custom restricted wheel assembler must verify compatible tags,
   `Root-Is-Purelib`, `METADATA`, `RECORD`, outer lock hashes and dependency closure.
   The wheel standard includes `.data` relocation and script rewriting, so merely
   unzipping an arbitrary wheel is insufficient. Refuse unsupported layout or
   metadata instead of silently losing required files; preserve package data,
   certificates, SDK service models, distribution metadata and licences.
   [PyPA wheel installation and RECORD contract](https://packaging.python.org/en/latest/specifications/binary-distribution-format/).
5. Project hardening choice: reject traversal, absolute/backslash paths, links,
   duplicate/colliding names, native payloads, malformed metadata and inventory
   drift before writing. These restrictions narrow the accepted wheel format;
   they are not additional requirements imposed by Lambda.
6. Project reproducibility choice: emit sorted member paths with fixed timestamps,
   explicit POSIX modes and no host-specific metadata. `ZIP_STORED` avoids zlib
   version differences at the cost of size; otherwise pin the compression toolchain
   as well. Python exposes member timestamp, creator and external attributes
   through `ZipInfo`; use a timestamp within ZIP's supported range.
   [Python 3.12 zipfile](https://docs.python.org/3.12/library/zipfile.html#zipinfo-objects).

## Evidence boundary

A Windows build can verify archive contents, import closure in an isolated local
Python process, reproducibility, hash/mode/size invariants and injected handler
behaviour. Keep imports and these tests free of live credential/provider discovery
or SDK requests. They cannot prove AL2023 execution, effective Lambda permissions,
OAC/event delivery, account eligibility, model qualification or deployed safety.

Before a Linux-runtime claim, run the exact emitted artifact in Python 3.12 on
the intended Linux/architecture runtime and record that evidence independently.
An approved Lambda runtime container can provide local runtime evidence if
available; it still does not establish deployed acceptance. No Linux-runtime
execution was performed by this research. Existing resource/cost/rollback,
observation delivery and Bedrock qualification gates remain open.
