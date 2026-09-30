// /s#… — a note shared by link (features/sharing/link.ts): the note is in the address, to read, run
// and copy into one's own notes. /embed#… the same without the app around it, for an <iframe>.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router";
import { Notebook } from "@/features/notebook";
import { decodeNote } from "@/features/sharing";
import type { Notebook as NotebookData } from "@/shared/model/types";
import { PageMessage } from "@/shared/ui/PageMessage";

export function SharedPage({ embed = false }: { embed?: boolean }) {
  const { t } = useTranslation("sharing");
  const { t: tNote } = useTranslation("notebook");
  const { hash } = useLocation();
  const [notebook, setNotebook] = useState<NotebookData | "broken" | null>(null);

  useEffect(() => {
    let alive = true;
    decodeNote(hash).then(
      (nb) => alive && setNotebook(nb),
      () => alive && setNotebook("broken"),
    );
    return () => {
      alive = false;
    };
  }, [hash]);

  if (notebook === "broken")
    return (
      <PageMessage title={t("broken")}>
        <p>
          <Link to="/">{tNote("allNotes")}</Link>
        </p>
      </PageMessage>
    );
  if (!notebook) return null;
  return (
    <Notebook
      key={hash}
      initial={notebook}
      revision={null}
      reload={() => {}}
      readOnly
      embed={embed ? `${import.meta.env.BASE_URL}s${hash}` : undefined}
      back={{ to: "/", label: tNote("allNotes") }}
    />
  );
}
