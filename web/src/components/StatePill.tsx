import type { LifecycleState } from "../lib/types";

export function StatePill({ state }: { state: LifecycleState }) {
  return (
    <span className={`pill st-${state}`}>
      <span className="dot" />
      {state}
    </span>
  );
}
