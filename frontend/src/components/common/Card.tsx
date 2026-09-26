import { useId, type ReactNode } from "react";
import "./common.css";

export interface CardProps {
  title?: string;
  description?: ReactNode;
  /** Controls shown on the right of the header. */
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}

/** A section card. With a title it is a labelled region for assistive technology. */
export function Card({ title, description, actions, className, children }: CardProps) {
  const titleId = useId();
  return (
    <section
      className={["card", className].filter(Boolean).join(" ")}
      aria-labelledby={title ? titleId : undefined}
    >
      {(title || actions) && (
        <div className="card__header">
          <div>
            {title && (
              <h2 id={titleId} className="card__title">
                {title}
              </h2>
            )}
            {description && <p className="card__description">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}
