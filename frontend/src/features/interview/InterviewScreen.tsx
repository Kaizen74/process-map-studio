import { useParams } from "react-router";
import { ErrorState, Skeleton } from "../../components/common";
import { TemplateCard } from "../../components/interview";
import { useEngagement } from "../../hooks/useEngagements";
import { useTemplatePlans } from "../../hooks/useTemplates";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { QUESTION_ID_TIP } from "../../lib/templates";
import { EngagementProblem } from "../engagement/EngagementProblem";
import "./interview.css";

/**
 * Interview (PRD v1.10 §5.4): the Templates tab, always available. Tailored guides and the
 * coverage report join this screen when they are built (phase P4c).
 */
export function InterviewScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const plans = useTemplatePlans();

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  return (
    <main className="screen" aria-labelledby="interview-title">
      <div>
        <h1 id="interview-title">Interview</h1>
        <p className="screen__intro">
          Standard interview templates give every interviewer the same questions, question IDs and minute plan. Download one,
          fill in the header, and use it during the interview; then upload the transcript on Sources.
        </p>
      </div>
      <section className="interview-templates" aria-labelledby="templates-title">
        <h2 id="templates-title" className="interview-templates__title">
          Templates
        </h2>
        <p className="interview-tip">{QUESTION_ID_TIP}</p>
        {plans.isPending && (
          <div className="interview-templates__grid" aria-busy="true">
            <Skeleton height="260px" />
            <Skeleton height="260px" />
            <Skeleton height="260px" />
          </div>
        )}
        {plans.isError && (
          <ErrorState
            title="The interview templates couldn't be loaded"
            message={messageOf(plans.error)}
            details={copyDetailsOf(plans.error)}
            onRetry={() => void plans.refetch()}
          />
        )}
        {plans.data && (
          <div className="interview-templates__grid">
            {plans.data.map((template) => (
              <TemplateCard key={template.type} template={template} />
            ))}
          </div>
        )}
        <p className="interview-note">
          Tailored interview guides and the coverage report are not available yet; the standard templates work for every
          interview in the meantime.
        </p>
      </section>
    </main>
  );
}
