import type { ComponentPropsWithoutRef } from "react";

export type DeskStageVariant = "narrow" | "default" | "watch" | "tool";
type DeskStageProps = ComponentPropsWithoutRef<"div"> & { variant?: DeskStageVariant };

/** One learner stage: widths belong to the variant, never to a desktop override. */
export function DeskStage({ variant = "default", className = "", ...props }: DeskStageProps) {
  return <div {...props} data-desk-stage={variant}
    className={`listen-stage listen-stage-${variant}${className ? ` ${className}` : ""}`} />;
}
