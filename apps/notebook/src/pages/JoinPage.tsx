// /join/:token — a share's link: the item becomes the user's to open (a share with the link's
// role), and it opens. Signed out, the sign-in page comes first and brings them back here.
import { useAtomSet } from "@effect-atom/atom-react";
import { Exit } from "effect";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { failure, folderUrl, LIBRARY, noteUrl } from "@/features/notes";
import { join } from "@/features/sharing";
import { PageMessage } from "@/shared/ui/PageMessage";

export function JoinPage() {
  const { t } = useTranslation("sharing", { keyPrefix: "join" });
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const call = useAtomSet(join, { mode: "promiseExit" });
  const [state, setState] = useState<"joining" | "missing" | "unreachable">("joining");

  useEffect(() => {
    let alive = true;
    void call({ path: { token }, reactivityKeys: LIBRARY }).then((exit) => {
      if (!alive) return;
      if (Exit.isSuccess(exit)) {
        const { id, kind, name } = exit.value;
        navigate(kind === "folder" ? folderUrl(id, name) : noteUrl(id, name), { replace: true });
      } else setState(failure(exit.cause)?._tag === "NotFound" ? "missing" : "unreachable");
    });
    return () => { alive = false; };
  }, [token, call, navigate]);

  if (state === "joining") return <PageMessage title={t("joining")} />;
  return (
    <PageMessage title={state === "missing" ? t("missing") : t("unreachable")}>
      <p className="text-muted">{state === "missing" && t("missingText")} <Link to="/">{t("home")}</Link></p>
    </PageMessage>
  );
}
