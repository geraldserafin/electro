// Whether Python (Pyodide, in a worker) is up: starting, ready, or failed (and why: its own message).
import { useEffect, useState } from "react";
import { kernel } from "./kernel";

export type PythonStatus = { kind: "loading" | "ready" } | { kind: "error"; error: string };

let known: PythonStatus = { kind: "loading" };
const ready = kernel.ready.then(
  () => (known = { kind: "ready" }),
  (error: Error) => (known = { kind: "error", error: error.message }),
);

export function usePython(): PythonStatus {
  const [status, setStatus] = useState(known);
  useEffect(() => {
    let alive = true;
    void ready.then((s) => alive && setStatus(s));
    return () => {
      alive = false;
    };
  }, []);
  return status;
}
