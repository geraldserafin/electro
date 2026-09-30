// Sharing a note by link: the note is in the link (link.ts), to read, and the same to embed.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Notebook } from "@/shared/model/types";
import { Dialog } from "@/shared/ui/Dialog";
import { linksTo } from "./link";

const field = "w-full min-w-0 h-9 px-2.5 rounded-lg border border-line bg-board font-mono text-[12px] text-muted";
const primary = "h-9 px-4 rounded-lg bg-primary text-on-primary text-[14px] font-medium hover:bg-primary-hover";

function Copyable({ label, text }: { label: string; text: string }) {
  const { t } = useTranslation("sharing");
  const [copied, setCopied] = useState(false);
  return (
    <label className="grid gap-1 text-[13px]">
      {label}
      <span className="flex gap-2">
        <input className={field} readOnly value={text} onFocus={(e) => e.target.select()} />
        <button
          type="button"
          className={primary}
          onClick={() => void navigator.clipboard.writeText(text).then(() => setCopied(true))}
        >
          {copied ? t("copied") : t("copy")}
        </button>
      </span>
    </label>
  );
}

export function LinkDialog({ notebook, onClose }: { notebook: Notebook; onClose: () => void }) {
  const { t } = useTranslation("sharing");
  const [links, setLinks] = useState<{ read: string; embed: string } | null>(null);
  useEffect(() => void linksTo(notebook).then(setLinks), [notebook]);
  const iframe = links && `<iframe src="${links.embed}" width="100%" height="600" style="border:0"></iframe>`;
  return (
    <Dialog label={t("linkTitle", { name: notebook.title })} onClose={onClose} className="max-w-140 gap-3">
      <h2 className="m-0 text-[17px] font-medium">{t("linkTitle", { name: notebook.title })}</h2>
      <p className="m-0 text-[13px] text-muted leading-relaxed">{t("linkIntro")}</p>
      {!links ? (
        <p className="m-0 text-[13px] text-muted">{t("loading")}</p>
      ) : (
        <>
          <Copyable label={t("readLink")} text={links.read} />
          <Copyable label={t("embed")} text={iframe ?? ""} />
          {links.read.length > 8000 && (
            <p className="m-0 text-[12px] text-warn">{t("longLink", { kb: Math.round(links.read.length / 1024) })}</p>
          )}
        </>
      )}
    </Dialog>
  );
}
