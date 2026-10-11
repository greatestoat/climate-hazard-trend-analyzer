import { useCallback, useRef, useState } from "react";
import { ApiError, createAnalysis } from "../services/api";
import type { Analysis, AnalysisRequest } from "../types/api";

export type AnalysisState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: Analysis }
  | { status: "error"; error: ApiError };

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({ status: "idle" });
  const last = useRef<AnalysisRequest | null>(null);
  const seq = useRef(0);

  const run = useCallback(async (req: AnalysisRequest) => {
    last.current = req;
    const id = ++seq.current;
    setState({ status: "loading" });
    try {
      const data = await createAnalysis(req);
      if (id === seq.current) setState({ status: "success", data });
    } catch (e) {
      const error = e instanceof ApiError ? e : new ApiError("Unexpected error.", 0, "unknown");
      if (id === seq.current) setState({ status: "error", error });
    }
  }, []);

  const retry = useCallback(() => {
    if (last.current) void run(last.current);
  }, [run]);

  return { state, run, retry };
}
