import type { CSSProperties } from "react";
import type { TextPos } from "../../lib/mapTypes";

/** CSS for a text the layout placed: `x` is its left edge, centre or right edge per `align`. */
export function placed(pos: TextPos): CSSProperties {
  const shift = { left: "0", center: "-50%", right: "-100%" }[pos.align];
  return { left: pos.x, top: pos.y, transform: `translateX(${shift})`, textAlign: pos.align };
}

/** Edge labels are placed by their centre line (the layout's `y`), not their top. */
export function placedChip(pos: TextPos): CSSProperties {
  const style = placed(pos);
  return { ...style, transform: `${String(style.transform)} translateY(-50%)` };
}
