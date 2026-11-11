import type { ReactNode, Ref } from "react";
import { DeskStage } from "./DeskStage";

type WatchFrameProps = {
  fixed: ReactNode;
  tabs: ReactNode;
  children: ReactNode;
  scriptScrollRef?: Ref<HTMLDivElement>;
  overlays?: ReactNode;
};

/** Always stacked. The shell supplies viewport height; only script-scroll can scroll.
 * Keep the ref on that exact node: selection/return-to-sentence observers rely on it.
 */
export function WatchFrame({ fixed, tabs, children, scriptScrollRef, overlays }: WatchFrameProps) {
  return (
    <DeskStage variant="watch" data-watch-frame="stacked">
      <div className="watch-fixed">{fixed}</div>
      <section className="script-section" aria-label="文稿与章节">
        <div className="script-tabs">{tabs}</div>
        <div className="script-scroll" ref={scriptScrollRef}>{children}</div>
      </section>
      {overlays}
    </DeskStage>
  );
}
