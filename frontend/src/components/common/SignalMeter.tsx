import type { SignalStrength } from "../../lib/reviewTypes";

export interface SignalMeterProps {
  signal: SignalStrength;
  /** Just the meter and the label (banners); otherwise the explanation follows. */
  compact?: boolean;
}

/**
 * Signal strength (P12): three bars, filled for the score and hollow for the rest, with the level
 * in words, so it never depends on colour (constraint 17).
 */
export function SignalMeter({ signal, compact = false }: SignalMeterProps) {
  return (
    <span className={`signal signal--${signal.level}`}>
      <span className="signal__meter" aria-hidden="true">
        {[1, 2, 3].map((n) => (
          <span key={n} className={`signal__bar${n <= signal.score ? " signal__bar--on" : ""}`} />
        ))}
      </span>
      <span className="signal__label">
        Signal strength: <strong>{signal.label}</strong>
        <span className="visually-hidden"> ({signal.score} of 3)</span>
      </span>
      {!compact && <span className="signal__detail">{signal.detail}</span>}
    </span>
  );
}
