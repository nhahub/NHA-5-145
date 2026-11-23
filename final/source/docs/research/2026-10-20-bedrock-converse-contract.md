# Bedrock Converse contract for the offline adapter slice

Checked 2026-10-20 against current primary AWS, PyPI, and Python documentation. This is API research, not evidence of AWS access, model qualification, deployed resources, latency, or spend.

## Slice decision

The first adapter slice uses nonstreaming `bedrock-runtime.converse`, text messages, the full inline response JSON Schema as a system format instruction, and the existing authoritative response validator. A format instruction does not enforce schema compliance remotely. Fail validation locally; do not repair, replay, execute tools, or bypass the Intent Boundary. Native structured output and forced-tool output remain future model-qualification options. This is the implementing agent's bounded choice for the authorized offline slice, not an owner-selected decoding method or an AWS capability claim.

The candidate model ID is `openai.gpt-oss-20b-1:0`. Its current card lists Converse on `bedrock-runtime`, text input/output, reasoning enabled by default, and structured output support. The candidate region is `eu-north-1`; selecting it in offline configuration is not evidence that the account can invoke the model there. [AWS GPT-OSS 20B model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-20b.html).

## Dependency pin

PyPI metadata returned `boto3==1.43.115` and `botocore==1.43.115`. Both require Python `>=3.10`, covering Python 3.12. Boto3 declares `botocore>=1.43.115,<1.44.0`, so these exact pins are compatible. No package was installed for this research. [Boto3 release metadata](https://pypi.org/pypi/boto3/1.43.115/json), [Botocore release metadata](https://pypi.org/pypi/botocore/1.43.115/json).

## Request and response

Minimal request mapping:

```python
client.converse(
    modelId=configured_model_id,
    system=[{"text": system_instruction}],
    messages=[{"role": "user", "content": [{"text": prompt}]}],
    inferenceConfig={"maxTokens": output_limit, "temperature": temperature},
)
```

System instructions are separate `system` content blocks. Conversation message roles are `user` or `assistant`, with content blocks such as `{"text": "..."}`. Converse uses `bedrock:InvokeModel` permission; it is not the Responses API. [AWS Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html), [AWS Message type](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Message.html).

Base inference keys are `maxTokens`, `temperature`, `topP`, and `stopSequences`. `maxTokens` is an integer >=1; temperature/topP are in [0,1]. Defaults and model-specific support differ. Additional provider parameters belong in `additionalModelRequestFields`; the first slice need not expose this escape hatch. [AWS InferenceConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InferenceConfiguration.html).

Read final text from `response["output"]["message"]["content"]` text blocks. Do not concatenate `reasoningContent` into answer text. Reasoning is a separate union containing `reasoningText` or `redactedContent`; it is not a universal reasoning-token counter. [AWS Converse output example](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html), [AWS ReasoningContentBlock](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ReasoningContentBlock.html).

The documented `stopReason` values are `end_turn`, `tool_use`, `max_tokens`, `stop_sequence`, `guardrail_intervened`, `content_filtered`, `malformed_model_output`, `malformed_tool_use`, and `model_context_window_exceeded`. Recommendation: accept only the explicitly supported final-answer reasons and valid nonempty text; treat truncation/filtering/malformed/tool responses as failures before domain execution. [AWS Converse response contract](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html).

Usage contains required `inputTokens`, `outputTokens`, and `totalTokens`, plus optional `cacheReadInputTokens`, `cacheWriteInputTokens`, and `cacheDetails`. There is no generic `reasoningTokens` member in this contract. Preserve unknown/absent metrics as unknown, rather than inventing zero reasoning usage. [AWS TokenUsage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html).

With prompt caching enabled, AWS specifically says `inputTokens` counts uncached input and total input is `inputTokens + cacheReadInputTokens + cacheWriteInputTokens`. Preserve separate counters rather than assuming OpenAI-compatible accounting. The first slice does not enable cache checkpoints. Token counters alone do not establish billable price or actual cost; keep cost unknown and retain the reservation under the existing project policy. [AWS prompt caching accounting](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html).

## Timeouts, retry bounds, errors, and correlation

Use explicit `botocore.config.Config(connect_timeout=..., read_timeout=..., retries={"mode": "standard", "total_max_attempts": 1})`. `total_max_attempts=1` includes the initial request and disables SDK retry attempts; `max_attempts=0` is the alternate Config spelling. Both timeouts default to 60 seconds without explicit configuration. A socket read timeout is not proof of provider cancellation or a complete wall-clock deadline. [Botocore Config reference](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html).

Converse documents `AccessDeniedException` (403), `ValidationException` (400), `ResourceNotFoundException` (404), `ModelTimeoutException` (408), `ModelErrorException` (424, with `originalStatusCode` and `resourceName`), `ModelNotReadyException` and `ThrottlingException` (429), `InternalServerException` (500), and `ServiceUnavailableException` (503). The default SDK can retry model-not-ready responses, reinforcing the need for explicit retry configuration. [AWS Converse errors](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html).

`ClientError.response` exposes `Error.Code` and `ResponseMetadata.RequestId`, `HTTPStatusCode`, `HTTPHeaders`, and `RetryAttempts`. Botocore transport/configuration exceptions, including connect/read timeout and missing credentials, are separate client-side exceptions and may have no AWS request ID. Recommendation: preserve safe code/status/request ID fields, never raw provider messages or request payloads in shopper-facing errors or telemetry. [Boto3 error handling](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html).

## Cancellation and streaming boundary

Running synchronous Boto3 in `asyncio.to_thread` or an executor lets the event loop continue; cancelling the await does not stop an already-running worker callable. Python futures cannot cancel work already executing. The worker can finish after the Shopping Task has been cancelled, and a request already sent can still incur cost. Recommendation: reject late results, keep admission/cost accounting attached until real worker completion, and never describe cancellation as remotely aborting inference. An executor context manager waits for running work on exit, which can accidentally delay cancellation propagation. [Python 3.12 Future.cancel and executor shutdown](https://docs.python.org/3.12/library/concurrent.futures.html).

`ConverseStream` is a separate streaming operation using `bedrock:InvokeModelWithResponseStream`, with message/content delta events and final metadata. Supporting ordinary Converse does not imply the same model supports tool use while streaming. The first slice should not manufacture streaming chunks or advertise provider cancellation from its nonstreaming operation. [AWS ConverseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html), [AWS client-side tool streaming limitations](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html).

## Future structured-output options and limits

Native schema output is now documented using `outputConfig.textFormat.type="json_schema"` and `outputConfig.textFormat.structure.jsonSchema.schema=json.dumps(schema)`. The schema value is a JSON **string**, with optional `name`/`description`. This avoids a synthetic tool call when a qualified model supports it. It is not required by the first slice. [AWS structured-output request examples](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html), [AWS JsonSchemaDefinition](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_JsonSchemaDefinition.html).

The native grammar accepts only a subset of JSON Schema 2020-12. Unsupported examples include numerical bounds, string length bounds, recursive/external references, and `additionalProperties` values other than false. Unsupported schemas return HTTP 400; first compilation can take minutes, with compiled grammars cached for 24 hours. Therefore do not silently transform the authoritative project schema and claim equivalent remote enforcement. [AWS structured-output limitations](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html).

Alternative tool shape is `toolConfig={"tools":[{"toolSpec":{"name":"emit_response","inputSchema":{"json":schema}}}],"toolChoice":{"tool":{"name":"emit_response"}}}`. Forced tool selection and strict schema enforcement are different features: strict enforcement adds `toolSpec.strict=True` where supported. Tool output appears as `toolUse` with `name`, `toolUseId`, and JSON `input`; it is not ordinary text. [AWS ToolSpecification](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolSpecification.html), [AWS ToolUseBlock](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolUseBlock.html).

Do not assume GPT-OSS supports forced named tools. The generic ToolChoice reference restricts named `tool` to Claude 3 and Nova, while the current client-side guide warns that `any` and `tool` support varies by individual model and unsupported settings fail with `ValidationException`. Nova explicitly documents all three choices (`auto`, `any`, `tool`), with limited top-level schema support. No live model call was made to resolve GPT-OSS forced-tool behavior. [AWS ToolChoice](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ToolChoice.html), [AWS client-side tool choice](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html), [Nova tool definition](https://docs.aws.amazon.com/nova/latest/userguide/tool-use-definition.html).
