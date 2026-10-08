import type { GraphElement, LayoutNode, TextPos } from "../../lib/mapTypes";
import type { LensLine as LensLineData, MarkerKind } from "../../lib/lens";
import { StateGlyph, WorkTypeGlyph } from "../common";
import { placed } from "./placement";


/** The one line under a node; what it says depends on the lens (PRD §5.5). */
export function LensLine({ line, pos }: { line: LensLineData; pos: TextPos }) {
  if (line.kind === "none") return null;
  return (
    <div className="map-lens" style={placed(pos)} data-lens={line.kind}>
      {line.kind === "text" && (
        <span className={line.danger ? "mono map-lens__danger" : line.muted ? "mono map-lens__muted" : "mono"}>
          {line.text}
        </span>
      )}
      {line.kind === "state" && <StateGlyph state={line.state} />}
      {line.kind === "work_type" && <WorkTypeGlyph type={line.type} proposed={line.proposed} />}
      {line.kind === "confidence" && (
        <>
          <span className="map-bar">
            <span
              className={line.low ? "map-bar__fill map-bar__fill--low" : "map-bar__fill"}
              style={{ width: line.bar }}
            />
          </span>
          <span className={line.low ? "mono map-lens__danger" : "mono"}>{line.text}</span>
        </>
      )}
      {line.kind === "time" && (
        <>
          <span className="map-bar__work" style={{ width: line.work }} />
          <span className="map-bar__wait" style={{ width: line.wait }} />
          <span className="mono">{line.text}</span>
        </>
      )}
    </div>
  );
}

export interface MapNodeProps {
  element: GraphElement;
  node: LayoutNode;
  name: string;
  markers: MarkerKind[];
  lens: LensLineData;
  selected: boolean;
  onSelect: (id: string) => void;
}

const HIT_PAD = 6;

/** One node: its shape (a button, named for screen readers), markers, label and lens line. */
export function MapNode({ element, node, name, markers, lens, selected, onSelect }: MapNodeProps) {
  const diamond = node.shape === "diamond";
  const circle = node.shape === "circle" || node.shape === "double_circle";
  const classes = [
    "map-node",
    `map-node--${node.shape}`,
    markers.includes("unreviewed") && "map-node--unreviewed",
    element.review_status === "rejected" && "map-node--rejected",
    node.ghost && "map-node--ghost",
    selected && "map-node--selected",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <>
      <button
        type="button"
        className={classes}
        style={
          circle // start and end are 16 px; the button around them keeps the 28 px hit target
            ? { left: node.x - HIT_PAD, top: node.y - HIT_PAD, width: node.w + 2 * HIT_PAD, height: node.h + 2 * HIT_PAD }
            : { left: node.x, top: node.y, width: node.w, height: node.h }
        }
        aria-label={name}
        aria-pressed={selected}
        title={element.label}
        data-node={element.id}
        onClick={() => onSelect(element.id)}
      >
        {diamond && <span className="map-node__diamond" aria-hidden="true" />}
        {circle && (
          <span
            className={`map-node__circle map-node__circle--${node.shape === "circle" ? "start" : "end"}`}
            style={{ width: node.w, height: node.h }}
            aria-hidden="true"
          />
        )}
        {!diamond && !circle && (
          <span className="map-node__label" aria-hidden="true">
            {node.label_lines.map((line, i) => (
              <span key={i}>{line}</span>
            ))}
          </span>
        )}
        {markers.includes("key_constraint") && (
          <span className="map-marker map-marker--constraint" aria-hidden="true" />
        )}
        {markers.includes("images") && <span className="map-marker map-marker--images" aria-hidden="true" />}
      </button>
      {diamond && (
        <div
          className={[
            "map-under",
            node.label_pos.align === "left" && "map-under--left",
            element.review_status === "rejected" && "map-under--rejected",
            node.ghost && "map-under--ghost",
          ]
            .filter(Boolean)
            .join(" ")}
          style={placed(node.label_pos)}
          aria-hidden="true"
        >
          {node.label_lines.map((line, i) => (
            <span key={i}>{line}</span>
          ))}
        </div>
      )}
      <div
        className={element.review_status === "rejected" ? "map-faded" : node.ghost ? "map-ghost-line" : undefined}
        aria-hidden="true"
      >
        <LensLine line={lens} pos={node.lens_pos} />
      </div>
    </>
  );
}
