import { Card } from "../common";
import { FORMATS, templateUrl, type TemplateSummary } from "../../lib/templates";
import "./interview.css";

/** Download Word · Download Markdown for one template (plain links: the server names the file). */
export function TemplateDownloads({ template }: { template: TemplateSummary }) {
  return (
    <span className="template-downloads">
      {FORMATS.map(({ format, label }) => (
        <a key={format} className="btn btn--secondary" href={templateUrl(template.type, format)} download>
          Download {label}{" "}
          <span className="visually-hidden">{template.title} interview template</span>
        </a>
      ))}
    </span>
  );
}

/** One standard template (Interview screen, PRD §5.4): purpose, who it is for, minute plan, downloads. */
export function TemplateCard({ template }: { template: TemplateSummary }) {
  return (
    <Card
      title={`${template.title} (${template.minutes} min)`}
      description={template.purpose}
      className="template-card"
    >
      <p className="template-card__who">For: {template.who}</p>
      <table className="template-plan">
        <caption className="visually-hidden">Minute plan of the {template.title} template</caption>
        <thead className="visually-hidden">
          <tr>
            <th scope="col">Part</th>
            <th scope="col">Minutes</th>
          </tr>
        </thead>
        <tbody>
          {template.plan.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td className="template-plan__minutes mono">{row.minutes}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Total</th>
            <td className="template-plan__minutes mono">{template.minutes}</td>
          </tr>
        </tfoot>
      </table>
      <p className="template-card__meta">
        {template.question_count} question IDs · question bank v{template.bank_version}
      </p>
      <TemplateDownloads template={template} />
    </Card>
  );
}

/** The three templates in one compact list (home screen card, PRD §5.4). */
export function TemplateList({ templates }: { templates: readonly TemplateSummary[] }) {
  return (
    <ul className="template-list" aria-label="Interview templates">
      {templates.map((template) => (
        <li key={template.type} className="template-list__item">
          <span>
            <strong className="template-list__title">
              {template.title} <span className="mono">({template.minutes} min)</span>
            </strong>
            <span className="template-list__who">{template.who}</span>
          </span>
          <TemplateDownloads template={template} />
        </li>
      ))}
    </ul>
  );
}
