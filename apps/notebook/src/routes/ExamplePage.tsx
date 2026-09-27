// /examples/:name — a new note from that example, then its address (the example stays as it is).
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { fromExample } from "../examples";
import { useCreateNote } from "../notes/create";

export function ExamplePage() {
  const { name = "" } = useParams();
  const create = useCreateNote();
  const [problem, setProblem] = useState<string | null>(null);
  const started = useRef(false); // once, even when React mounts twice (StrictMode)

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const notebook = fromExample(name);
    if (!notebook) {
      setProblem(`Nie ma przykładu „${name}”.`);
      return;
    }
    void create(notebook, { replace: true }).then((ok) => ok || setProblem("Serwer notatek nie odpowiada."));
  }, [name, create]);

  return (
    <div className="page-message">
      {problem ? <><h1>{problem}</h1><p><Link to="/">Wszystkie notatki</Link></p></> : <p className="muted">Tworzę notatkę z przykładu…</p>}
    </div>
  );
}
