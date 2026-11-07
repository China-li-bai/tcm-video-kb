import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

export type FocusPreset = { label: string; focus: string };

type Props = {
  /** Plain Chinese page title, e.g. 方证关系图 */
  title: string;
  /** One-line role: 旁证，不是主场 */
  lead: string;
  focus: string;
  onFocus: (next: string) => void;
  presets: readonly FocusPreset[];
  /** Sibling tool link (graph ↔ paths) */
  sibling?: { to: string; label: string };
};

/**
 * Sparse C-end chrome for /graph and /paths inside ListenDeskShell.
 * No sidebar, no admin "焦点" topbar — presets first, raw id as fallback.
 */
export function ToolFocusBar({
  title,
  lead,
  focus,
  onFocus,
  presets,
  sibling,
}: Props) {
  const [draft, setDraft] = useState(focus);
  const activePreset = presets.find((p) => p.focus === focus);

  useEffect(() => {
    setDraft(focus);
  }, [focus]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    onFocus(draft);
  }

  return (
    <header className="tool-bar">
      <div className="tool-bar-top">
        <div className="tool-bar-titles">
          <h1 className="tool-title">{title}</h1>
          <p className="tool-lead">{lead}</p>
        </div>
        <p className="tool-bound">学习用 · 非诊疗</p>
      </div>

      <div className="tool-bar-row">
        <span className="tool-looking">
          正在看：<strong>{activePreset?.label ?? humanizeFocus(focus)}</strong>
        </span>
        <div className="tool-presets" role="group" aria-label="换一个看">
          {presets.map((p) => (
            <button
              key={p.focus}
              type="button"
              className={
                p.focus === focus ? "tool-preset is-on" : "tool-preset"
              }
              onClick={() => onFocus(p.focus)}
            >
              {p.label}
            </button>
          ))}
        </div>
        {sibling && (
          <Link className="tool-sibling" to={sibling.to}>
            {sibling.label}
          </Link>
        )}
      </div>

      <details className="tool-advanced">
        <summary>用编号打开</summary>
        <form className="tool-focus-form" onSubmit={onSubmit}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            aria-label="实体编号"
            placeholder="例如 formula.gui_zhi_tang"
          />
          <button type="submit" className="listen-btn listen-btn-ghost">
            打开
          </button>
        </form>
      </details>
    </header>
  );
}

function humanizeFocus(id: string): string {
  const tail = id.includes(".") ? id.slice(id.indexOf(".") + 1) : id;
  return tail.replace(/_/g, " ") || id;
}
