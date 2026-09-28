// Placeholders in the shape of what is coming, shimmering while it loads.
import type { CSSProperties } from "react";

export const Bone = ({ w, h = 14, style }: { w: string | number; h?: number; style?: CSSProperties }) => (
  <span className="skeleton" style={{ width: w, height: h, ...style }} />
);
