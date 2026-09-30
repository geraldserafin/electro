// /examples/:name — a new note from that example, then its address (the example stays as it is).
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { fromExample } from "@/features/examples";
import { useCreateNote } from "@/features/notes";
import { PageMessage } from "@/shared/ui/PageMessage";

export function ExamplePage() {
  const { t } = useTranslation("pages", { keyPrefix: "example" });
  const { t: tNote } = useTranslation("notebook");
  const { name = "" } = useParams();
  const create = useCreateNote();
  const [problem, setProblem] = useState<string | null>(null);
  const started = useRef(false); // once, even when React mounts twice (StrictMode)

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const notebook = fromExample(name);
    if (!notebook) {
      setProblem(t("missing", { name }));
      return;
    }
    void create(notebook, { replace: true }).then((ok) => ok || setProblem(t("unreachable")));
  }, [name, create, t]);

  return problem ? (
    <PageMessage title={problem}>
      <p>
        <Link to="/">{tNote("allNotes")}</Link>
      </p>
    </PageMessage>
  ) : (
    <PageMessage>
      <p className="text-muted">{t("creating")}</p>
    </PageMessage>
  );
}
