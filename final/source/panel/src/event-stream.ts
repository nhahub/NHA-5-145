import {
  AGENT_EVENT_TYPES,
  parseAgentEvent,
  type AgentEvent,
} from "./panel.js";

interface EventStream {
  readonly readyState?: number;
  addEventListener(
    type: string,
    listener: (event: MessageEvent<string>) => void,
  ): void;
  close(): void;
}

/** Reconnect uses EventSource's Last-Event-ID; suppress duplicate delivery locally too. */
export function subscribeAgentStream(
  url: string,
  handler: (event: AgentEvent) => void,
  after = 0,
  onCursor?: (cursor: number) => void,
  createSource: (url: string) => EventStream = (url) =>
    new EventSource(url, { withCredentials: true }),
  onReset?: () => void,
): () => void {
  const source = createSource(url);
  let cursor = after;
  let closed = false;
  const close = () => {
    closed = true;
    source.close();
  };
  source.addEventListener("shopper_reset", () => {
    if (closed) return;
    close();
    onReset?.();
  });
  // EventSource reauthorizes reconnects at the server. Only terminal failures
  // reset the shopper; transient errors and application "error" events do not.
  source.addEventListener("error", () => {
    if (closed || source.readyState !== 2) return;
    close();
    onReset?.();
  });
  for (const type of AGENT_EVENT_TYPES)
    source.addEventListener(type, (message) => {
      if (closed) return;
      const next = Number(message.lastEventId);
      if (!Number.isSafeInteger(next) || next <= cursor) return;
      const event = parseAgentEvent(type, JSON.parse(message.data));
      handler(event);
      cursor = next;
      onCursor?.(cursor);
    });
  return close;
}
