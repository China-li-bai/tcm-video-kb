import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { DEFAULT_FOCUS } from "../types";

/** URL ?focus=… with a safe default — graph/paths share this, no AppShell. */
export function useToolFocus(fallback: string = DEFAULT_FOCUS): {
  focus: string;
  setFocus: (next: string) => void;
} {
  const [params, setParams] = useSearchParams();
  const focus = (params.get("focus") || fallback).trim() || fallback;

  const setFocus = useCallback(
    (next: string) => {
      const value = next.trim();
      if (!value) return;
      const query = new URLSearchParams(params);
      query.set("focus", value);
      setParams(query, { replace: true });
    },
    [params, setParams],
  );

  return { focus, setFocus };
}
