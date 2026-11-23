// Opt-in local evaluation timings. No DOM, Action arguments, or field values are emitted.
export function recordEvaluationTiming(phase: string, started: number): void {
  if (
    typeof window === "undefined" ||
    !(window as Window & { __copilotEvaluation?: boolean }).__copilotEvaluation
  )
    return;
  window.parent.postMessage(
    {
      type: "evaluation_timing",
      phase,
      elapsed_ms: performance.now() - started,
    },
    "http://localhost:4100",
  );
}
