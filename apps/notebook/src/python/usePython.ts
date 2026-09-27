// Whether Python (Pyodide, in a worker) is up: starting, ready, or failed.
import { useEffect, useState } from "react";
import { kernel } from "./kernel";

export type PythonStatus = { kind: "loading" | "ready" | "error"; text: string };

let known: PythonStatus = { kind: "loading", text: "Uruchamiam Pythona…" };
const ready = kernel.ready.then(
  () => (known = { kind: "ready", text: "Python gotowy" }),
  (error: Error) => (known = { kind: "error", text: `Python się nie uruchomił: ${error.message}` }),
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
