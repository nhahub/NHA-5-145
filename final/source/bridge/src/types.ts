export interface Viewport {
  w: number;
  h: number;
  scrollY: number;
}

export interface SnapshotElement {
  id: number;
  role: string;
  name: string;
  visible: boolean;
  href?: string;
  form_action?: string;
  mutation_state?: string;
  value?: string;
  options?: string[];
  checked?: boolean;
  group?: string;
  region?: string;
  disabled?: boolean;
  level?: number;
  sensitive?: true;
}

export interface Snapshot {
  v: 1;
  url: string;
  title: string;
  lang: string;
  viewport: Viewport;
  truncated: boolean;
  elements: SnapshotElement[];
}

export interface ActionBase {
  v: 1;
  task_id: string;
  action_id: string;
  sequence_number: number;
  narration: string;
}

export interface NavigateAction extends ActionBase {
  type: "navigate";
  url: string;
}

export interface ClickAction extends ActionBase {
  type: "click";
  id: number;
}

export interface GuardedClickAction extends ActionBase {
  type: "guarded_click";
  id: number;
  confirmation_id: string;
  mutation_kind: "clear_cart" | "submit_checkout";
  target_signature: string;
  state_signature: string;
  cart_revision: number;
  effect: string;
}

export interface TypeAction extends ActionBase {
  type: "type";
  id: number;
  text: string;
  submit: boolean;
}

export interface SelectAction extends ActionBase {
  type: "select";
  id: number;
  option: string;
}

export interface ScrollToAction extends ActionBase {
  type: "scroll_to";
  id: number;
}

export interface SpotlightAction extends ActionBase {
  type: "spotlight";
  id: number;
  message: string;
}

export interface AskShopperAction extends ActionBase {
  type: "ask_shopper";
  question: string;
  options: string[];
  kind?: "confirmation";
}

export interface DoneAction extends ActionBase {
  type: "done";
  summary: string;
}

export type Action =
  | NavigateAction
  | ClickAction
  | GuardedClickAction
  | TypeAction
  | SelectAction
  | ScrollToAction
  | SpotlightAction
  | AskShopperAction
  | DoneAction;

export interface ActionResult {
  v: 1;
  task_id: string;
  action_id: string;
  sequence_number: number;
  status: ActionResultStatus;
  snapshot: Snapshot;
}

const ACTION_RESULT_STATUSES = [
  "ok",
  "not_found",
  "blocked",
  "navigated",
  "timeout",
  "cancelled",
  "stale",
] as const;

const ACTION_BASE_KEYS = [
  "v",
  "type",
  "task_id",
  "action_id",
  "sequence_number",
  "narration",
] as const;

export type ActionResultStatus = (typeof ACTION_RESULT_STATUSES)[number];

function isActionResultStatus(value: string): value is ActionResultStatus {
  return (ACTION_RESULT_STATUSES as readonly string[]).includes(value);
}

type WireRecord = Record<string, unknown>;

function requireRecord(value: unknown, label: string): WireRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${label} must be an object`);
  }

  return value as WireRecord;
}

function requireString(record: WireRecord, key: string, label: string): string {
  const value = record[key];
  if (typeof value !== "string") {
    throw new TypeError(`${label}.${key} must be a string`);
  }
  return value;
}

function requireBoolean(
  record: WireRecord,
  key: string,
  label: string,
): boolean {
  const value = record[key];
  if (typeof value !== "boolean") {
    throw new TypeError(`${label}.${key} must be a boolean`);
  }
  return value;
}

function requireInteger(
  record: WireRecord,
  key: string,
  label: string,
): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    throw new TypeError(`${label}.${key} must be a safe integer`);
  }
  return value;
}

function requireOnlyKeys(
  record: WireRecord,
  allowed: readonly string[],
  label: string,
): void {
  const unknown = Object.keys(record).filter((key) => !allowed.includes(key));
  if (unknown.length > 0) {
    throw new TypeError(`${label} contains unknown field ${unknown[0]}`);
  }
}

function validateOptionalString(
  record: WireRecord,
  key: string,
  label: string,
): void {
  if (record[key] !== undefined && typeof record[key] !== "string") {
    throw new TypeError(`${label}.${key} must be a string when present`);
  }
}

function validateOptionalBoolean(
  record: WireRecord,
  key: string,
  label: string,
): void {
  if (record[key] !== undefined && typeof record[key] !== "boolean") {
    throw new TypeError(`${label}.${key} must be a boolean when present`);
  }
}

function validateSnapshotElement(value: unknown, index: number): void {
  const label = `Snapshot.elements[${index}]`;
  const element = requireRecord(value, label);
  requireOnlyKeys(
    element,
    [
      "id",
      "role",
      "name",
      "visible",
      "href",
      "form_action",
      "mutation_state",
      "value",
      "options",
      "checked",
      "group",
      "region",
      "disabled",
      "level",
      "sensitive",
    ],
    label,
  );
  requireInteger(element, "id", label);
  requireString(element, "role", label);
  requireString(element, "name", label);
  requireBoolean(element, "visible", label);

  for (const key of [
    "href",
    "form_action",
    "mutation_state",
    "value",
    "group",
    "region",
  ] as const) {
    validateOptionalString(element, key, label);
  }
  for (const key of ["checked", "disabled"] as const) {
    validateOptionalBoolean(element, key, label);
  }
  if (element.sensitive !== undefined && element.sensitive !== true) {
    throw new TypeError(`${label}.sensitive must be true when present`);
  }
  if (element.level !== undefined) {
    requireInteger(element, "level", label);
  }
  if (
    element.options !== undefined &&
    (!Array.isArray(element.options) ||
      !element.options.every((option) => typeof option === "string"))
  ) {
    throw new TypeError(
      `${label}.options must be an array of strings when present`,
    );
  }
  const sensitiveStateKeys = [
    "href",
    "form_action",
    "mutation_state",
    "value",
    "options",
    "checked",
    "group",
    "region",
    "disabled",
    "level",
  ];
  if (
    element.sensitive === true &&
    sensitiveStateKeys.some((key) => element[key] !== undefined)
  ) {
    throw new TypeError("Sensitive Fields may contain only minimal metadata");
  }
}

export function parseSnapshot(payload: unknown): Snapshot {
  const snapshot = requireRecord(payload, "Snapshot");
  requireOnlyKeys(
    snapshot,
    ["v", "url", "title", "lang", "viewport", "truncated", "elements"],
    "Snapshot",
  );
  if (snapshot.v !== 1) {
    throw new TypeError("Snapshot.v must be 1");
  }
  requireString(snapshot, "url", "Snapshot");
  requireString(snapshot, "title", "Snapshot");
  requireString(snapshot, "lang", "Snapshot");
  requireBoolean(snapshot, "truncated", "Snapshot");

  const viewport = requireRecord(snapshot.viewport, "Snapshot.viewport");
  requireOnlyKeys(viewport, ["w", "h", "scrollY"], "Snapshot.viewport");
  requireInteger(viewport, "w", "Snapshot.viewport");
  requireInteger(viewport, "h", "Snapshot.viewport");
  requireInteger(viewport, "scrollY", "Snapshot.viewport");

  if (!Array.isArray(snapshot.elements)) {
    throw new TypeError("Snapshot.elements must be an array");
  }
  snapshot.elements.forEach(validateSnapshotElement);

  return snapshot as unknown as Snapshot;
}

export function parseAction(payload: unknown): Action {
  const action = requireRecord(payload, "Action");
  if (action.v !== 1) {
    throw new TypeError("Action.v must be 1");
  }
  const type = requireString(action, "type", "Action");
  requireString(action, "task_id", "Action");
  requireString(action, "action_id", "Action");
  requireInteger(action, "sequence_number", "Action");
  requireString(action, "narration", "Action");

  switch (type) {
    case "navigate":
      requireOnlyKeys(action, [...ACTION_BASE_KEYS, "url"], "Action");
      requireString(action, "url", "Action");
      break;
    case "click":
    case "scroll_to":
      requireOnlyKeys(action, [...ACTION_BASE_KEYS, "id"], "Action");
      requireInteger(action, "id", "Action");
      break;
    case "guarded_click":
      requireOnlyKeys(
        action,
        [
          ...ACTION_BASE_KEYS,
          "id",
          "confirmation_id",
          "mutation_kind",
          "target_signature",
          "state_signature",
          "cart_revision",
          "effect",
        ],
        "Action",
      );
      requireInteger(action, "id", "Action");
      requireInteger(action, "cart_revision", "Action");
      for (const key of [
        "confirmation_id",
        "mutation_kind",
        "target_signature",
        "state_signature",
        "effect",
      ])
        requireString(action, key, "Action");
      if (
        !["clear_cart", "submit_checkout"].includes(
          action.mutation_kind as string,
        )
      )
        throw new TypeError("Action.mutation_kind is unsupported");
      if (!/^confirmation-[0-9a-f]{32}$/.test(action.confirmation_id as string))
        throw new TypeError("Action.confirmation_id is invalid");
      if (
        !(action.target_signature as string).trim() ||
        !(action.effect as string).trim()
      )
        throw new TypeError("Guarded Action needs a target and effect");
      if (
        (action.cart_revision as number) < 0 ||
        action.state_signature !== `cart:${action.cart_revision}`
      )
        throw new TypeError("Guarded Action has an invalid cart revision");
      break;
    case "type":
      requireOnlyKeys(
        action,
        [...ACTION_BASE_KEYS, "id", "text", "submit"],
        "Action",
      );
      requireInteger(action, "id", "Action");
      requireString(action, "text", "Action");
      requireBoolean(action, "submit", "Action");
      break;
    case "select":
      requireOnlyKeys(action, [...ACTION_BASE_KEYS, "id", "option"], "Action");
      requireInteger(action, "id", "Action");
      requireString(action, "option", "Action");
      break;
    case "spotlight":
      requireOnlyKeys(action, [...ACTION_BASE_KEYS, "id", "message"], "Action");
      requireInteger(action, "id", "Action");
      requireString(action, "message", "Action");
      break;
    case "ask_shopper":
      requireOnlyKeys(
        action,
        [...ACTION_BASE_KEYS, "question", "options", "kind"],
        "Action",
      );
      requireString(action, "question", "Action");
      if (
        !Array.isArray(action.options) ||
        !action.options.every((option) => typeof option === "string")
      ) {
        throw new TypeError("Action.options must be an array of strings");
      }
      if (action.kind !== undefined && action.kind !== "confirmation") {
        throw new TypeError("Action.kind is unsupported");
      }
      break;
    case "done":
      requireOnlyKeys(action, [...ACTION_BASE_KEYS, "summary"], "Action");
      requireString(action, "summary", "Action");
      break;
    default:
      throw new TypeError("Action.type is not supported by v1");
  }
  return action as unknown as Action;
}

export function parseActionResult(payload: unknown): ActionResult {
  const result = requireRecord(payload, "Action Result");
  requireOnlyKeys(
    result,
    ["v", "task_id", "action_id", "sequence_number", "status", "snapshot"],
    "Action Result",
  );
  if (result.v !== 1) {
    throw new TypeError("Action Result.v must be 1");
  }
  requireString(result, "task_id", "Action Result");
  requireString(result, "action_id", "Action Result");
  requireInteger(result, "sequence_number", "Action Result");
  const status = requireString(result, "status", "Action Result");
  if (!isActionResultStatus(status)) {
    throw new TypeError("Action Result.status is not supported by v1");
  }
  parseSnapshot(result.snapshot);
  return result as unknown as ActionResult;
}
