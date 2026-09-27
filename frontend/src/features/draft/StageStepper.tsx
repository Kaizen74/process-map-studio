import { useEffect, useState } from "react";
import type { JobStage } from "../../api/types";
import { STAGE_LOOK, elapsedLabel, stageElapsedMs, type StageLook } from "../../lib/draft";

function StageShape({ look }: { look: StageLook }) {
  const tone = `tone-${look.tone}`;
  return (
    <svg className="stage__shape" width="14" height="14" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
      {look.shape === "filled-circle" && <circle cx="6" cy="6" r="4.5" className={tone} />}
      {look.shape === "half-circle" && (
        <>
          <circle cx="6" cy="6" r="4.5" className={`${tone} no-fill`} />
          <path d="M6 1.5 A4.5 4.5 0 0 1 6 10.5 Z" className={tone} />
        </>
      )}
      {look.shape === "dashed-ring" && <circle cx="6" cy="6" r="4.5" className={`${tone} no-fill`} strokeDasharray="2 1.6" />}
      {look.shape === "ring-cross" && (
        <>
          <circle cx="6" cy="6" r="4.5" className={`${tone} no-fill`} strokeWidth="1.5" />
          <path d="M3.8 3.8 L8.2 8.2 M8.2 3.8 L3.8 8.2" className={tone} strokeWidth="1.5" />
        </>
      )}
      {look.shape === "dash" && <path d="M2 6 H10" className={`${tone} no-fill`} strokeWidth="2" />}
      {look.shape === "outlined-square" && <rect x="1.75" y="1.75" width="8.5" height="8.5" className={`${tone} no-fill`} />}
    </svg>
  );
}

/** The vertical stage stepper (PRD §5.4 Draft): each stage with its status and elapsed time. */
export function StageStepper({ stages }: { stages: readonly JobStage[] }) {
  const running = stages.some((s) => s.status === "running");
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  return (
    <ol className="stages" aria-label="Drafting stages">
      {stages.map((stage) => {
        const look = STAGE_LOOK[stage.status];
        const elapsed = stageElapsedMs(stage, now);
        return (
          <li key={stage.id} className={`stage stage--${stage.status}`}>
            <StageShape look={look} />
            <span className="stage__name">{stage.name}</span>
            <span className="stage__status">
              {look.label}
              {elapsed !== null && <span className="stage__time mono"> · {elapsedLabel(elapsed)}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
