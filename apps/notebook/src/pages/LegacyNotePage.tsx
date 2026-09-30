// /notes/:ref — a note's address from before folders (its slug among the user's notes then): the
// server knows which note it was; this goes there.
import { useAtomSet } from "@effect-atom/atom-react";
import { Exit } from "effect";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { failure, legacyNote } from "@/features/notes";
import { PageMessage } from "@/shared/ui/PageMessage";

export function LegacyNotePage() {
  const { t } = useTranslation("pages", { keyPrefix: "note" });
  const { t: tLibrary } = useTranslation("library");
  const { ref = "" } = useParams();
  const navigate = useNavigate();
  const find = useAtomSet(legacyNote, { mode: "promiseExit" });
  const [problem, setProblem] = useState<"missing" | "unreachable" | null>(null);

  useEffect(() => {
    let alive = true;
    void find({ path: { ref } }).then((exit) => {
      if (!alive) return;
      if (Exit.isSuccess(exit)) navigate(`/n/${exit.value.id}`, { replace: true });
      else setProblem(failure(exit.cause)?._tag === "NotFound" ? "missing" : "unreachable");
    });
    return () => {
      alive = false;
    };
  }, [ref, find, navigate]);

  if (!problem) return null;
  return (
    <PageMessage title={problem === "missing" ? t("missing") : t("unreachable")}>
      <p>
        <Link to="/">{tLibrary("home")}</Link>
      </p>
    </PageMessage>
  );
}
