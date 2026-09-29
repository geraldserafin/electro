// "Share", laid out as the PDF export is: on the left the item as it looks (a note's first page; a
// folder with a few of its notes in it), on the right who has it, as Notion lays it out — invite
// someone by email; the people who have it (the owner — the user, as only the owner opens it —
// and those it was shared with, whose access changes here, or goes); general access (only those
// invited, or anyone signed in with the link, and what the link lets them do); "Copy link" (the
// link, if there is one; else the item's own address, which works for those invited).
import { useAtomSet } from "@effect-atom/atom-react";
import type { ItemCard, ShareRole, Sharing } from "@electro/notes-api";
import { Exit, type Cause } from "effect";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { failure, folderUrl, LIBRARY, noteUrl, PagePreview } from "@/features/notes";
import { library } from "@/features/schematic";
import { Avatar } from "@/shared/ui/Avatar";
import { Check, Close, FolderIcon, GlobeIcon, LinkIcon, LockIcon, PageIcon } from "@/shared/ui/icons";
import { Picker, type PickerOption } from "@/shared/ui/Picker";
import { cn } from "@/shared/lib/cn";
import { addPerson, getSharing, joinUrl, newLink, setLink, setRole, unlink, unshare } from "./atoms";

/** What the dialog shows of the item: a card's worth. */
export type Shared = Pick<ItemCard, "id" | "name" | "kind" | "preview" | "previews" | "count">;

const heading = "mt-5 mb-1 text-[12px] font-semibold uppercase tracking-[0.05em] text-faint";
const person = "flex items-center gap-2.5 py-1.5";

export function ShareDialog({ item, onClose }: { item: Shared; onClose: () => void }) {
  const { t } = useTranslation("sharing");
  const { t: tLibrary } = useTranslation("library");
  const { id, kind } = item;
  const name = item.name || tLibrary("untitled");
  const calls = {
    get: useAtomSet(getSharing, { mode: "promiseExit" }),
    add: useAtomSet(addPerson, { mode: "promiseExit" }),
    setRole: useAtomSet(setRole, { mode: "promiseExit" }),
    unshare: useAtomSet(unshare, { mode: "promiseExit" }),
    link: useAtomSet(setLink, { mode: "promiseExit" }),
    newLink: useAtomSet(newLink, { mode: "promiseExit" }),
    unlink: useAtomSet(unlink, { mode: "promiseExit" }),
  };
  const [sharing, setSharing] = useState<Sharing | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [copied, setCopied] = useState(false);

  /** A call's answer: who has it now; or what went wrong. */
  const took = (exit: Exit.Exit<Sharing, unknown>) => {
    if (Exit.isSuccess(exit)) {
      setSharing(exit.value);
      setProblem(null);
      return true;
    }
    const error = failure(exit.cause as Cause.Cause<unknown>) as { _tag?: string; email?: string } | undefined;
    const tag = error?._tag;
    setProblem(tag === "NoSuchPerson" ? t("problem.NoSuchPerson", { email: error!.email })
      : tag === "RoleTooLow" || tag === "NotFound" ? t(`problem.${tag}`) : t("problem.failed"));
    return false;
  };

  useEffect(() => {
    void calls.get({ path: { id } }).then(took);
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  const invite = async () => {
    const address = email.trim();
    if (!address) return;
    if (took(await calls.add({ path: { id }, payload: { email: address, role: "editor" }, reactivityKeys: LIBRARY }))) setEmail("");
  };
  const copy = async () => {
    const own = kind === "folder" ? folderUrl(id, item.name) : noteUrl(id, item.name);
    await navigator.clipboard?.writeText(sharing?.link ? joinUrl(sharing.link.token) : location.origin + own).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const roles: PickerOption<ShareRole>[] = [
    { value: "editor", label: t("editor"), description: t("editorText") },
    { value: "viewer", label: t("viewer"), description: t("viewerText") },
  ];
  const general: PickerOption<"invited" | "link">[] = [
    { value: "invited", label: t("invited"), description: t("invitedText"), icon: <LockIcon /> },
    { value: "link", label: t("anyone"), description: t("anyoneText"), icon: <GlobeIcon /> },
  ];
  const link = sharing?.link ?? null;

  return createPortal(
    <div className="fixed inset-0 z-100 grid place-items-center bg-[rgb(0_0_0/0.45)] animate-fade-in" data-keep-focus
         onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal aria-label={t("title", { name })}
           className="appear relative grid grid-cols-[1fr_400px] max-[800px]:grid-cols-1
                      w-[min(1080px,94vw)] h-[min(760px,90vh)] rounded-[14px] overflow-hidden bg-surface border border-line">
        <button onClick={onClose} title={t("close")} aria-label={t("close")}
                className="absolute top-3 left-3 z-2 inline-flex size-9 items-center justify-center rounded-[10px] bg-surface shadow-island text-muted hover:text-fg">
          <Close />
        </button>

        {/* the item as it looks */}
        <div className="grid place-items-center min-h-0 overflow-hidden p-10 bg-hover max-[800px]:hidden">
          <figure className="grid justify-items-center gap-4 m-0">
            {kind === "note" ? <Page item={item} /> : <FolderPicture item={item} />}
            <figcaption className="grid justify-items-center">
              <span className="text-[16px] font-medium">{name}</span>
              <span className="text-[13px] text-muted">
                {kind === "folder" ? (item.count ? tLibrary("items", { count: item.count }) : tLibrary("empty")) : t("note")}
              </span>
            </figcaption>
          </figure>
        </div>

        {/* who has it */}
        <aside className="flex flex-col min-h-0 p-5 overflow-y-auto border-l border-line max-[800px]:border-l-0">
          <h2 className="m-0 mb-4 text-[18px] font-semibold">{t("share")}</h2>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void invite(); }}>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus
                   placeholder={t("emailPlaceholder")} aria-label={t("email")}
                   className="flex-1 min-w-0 h-9.5 px-3 rounded-[10px] border border-line bg-paper text-[14px] outline-none focus:border-accent" />
            <button disabled={!email.trim()}
                    className="h-9.5 px-3.5 rounded-[10px] border border-line text-[14px] font-medium hover:enabled:bg-hover disabled:opacity-45">
              {t("invite")}
            </button>
          </form>
          {problem && <p role="alert" className="m-0 mt-2 text-[13px] text-danger">{problem}</p>}

          {sharing === null ? <p className="mt-6 text-[14px] text-muted">{t("loading")}</p> : (
            <>
              <h3 className={heading}>{t("people")}</h3>
              <ul className="m-0 p-0 list-none" aria-label={t("people")}>
                <li className={person}>
                  <Avatar name={sharing.owner.name} url={sharing.owner.avatarUrl} />
                  <span className="flex-1 min-w-0 truncate text-[14px]">{sharing.owner.name} <span className="text-muted">({t("you")})</span></span>
                  <span className="px-2 text-[14px] text-muted">{t("owner")}</span>
                </li>
                {sharing.people.map((p) => (
                  <li key={p.id} className={person}>
                    <Avatar name={p.name} url={p.avatarUrl} />
                    <span className="grid flex-1 min-w-0 leading-tight">
                      <span className="truncate text-[14px]">{p.name}</span>
                      {p.email && <span className="truncate text-[12px] text-muted">{p.email}</span>}
                    </span>
                    <Picker label={t("roleOf", { name: p.name })} value={p.role} options={roles}
                            onChange={async (role) => took(await calls.setRole({ path: { id, user: p.id }, payload: { role } }))}
                            actions={[{
                              label: t("remove"), danger: true,
                              run: async () => took(await calls.unshare({ path: { id, user: p.id }, reactivityKeys: LIBRARY })),
                            }]} />
                  </li>
                ))}
              </ul>

              <h3 className={heading}>{t("general")}</h3>
              <div className="flex items-center gap-3 py-1.5">
                <span className={cn("grid place-items-center size-8 flex-none rounded-lg", link ? "bg-accent-soft text-accent" : "bg-selected text-muted")}>
                  {link ? <GlobeIcon /> : <LockIcon />}
                </span>
                <span className="grid flex-1 min-w-0 justify-items-start leading-tight">
                  <Picker label={t("general")} value={link ? "link" : "invited"} options={general} align="left" className="-ml-2 h-7 text-fg font-medium"
                          onChange={async (to) => took(to === "link"
                            ? await calls.link({ path: { id }, payload: { role: "viewer" }, reactivityKeys: LIBRARY })
                            : await calls.unlink({ path: { id }, reactivityKeys: LIBRARY }))}
                          actions={link ? [{ label: t("newLink"), description: t("newLinkTitle"), run: async () => took(await calls.newLink({ path: { id } })) }] : []} />
                  <span className="text-[12px] text-muted">{link ? t("anyoneText") : t("invitedText")}</span>
                </span>
                {link && (
                  <Picker label={t("linkRole")} value={link.role} options={roles}
                          onChange={async (role) => took(await calls.link({ path: { id }, payload: { role } }))} />
                )}
              </div>
              {kind === "folder" && <p className="m-0 mt-3 text-[12px] text-muted">{t("folderNote")}</p>}
            </>
          )}

          {/* the link: always in view at the bottom */}
          <div className="flex gap-2 mt-auto -mx-5 -mb-5 px-5 pt-3 pb-5 sticky -bottom-5 bg-surface border-t border-line">
            <button onClick={() => void copy()} disabled={sharing === null}
                    className="inline-flex flex-1 items-center justify-center gap-1.5 px-3 py-2.25 rounded-[10px] border border-primary bg-primary
                               text-[15px] font-medium text-on-primary hover:enabled:bg-primary-hover disabled:opacity-45">
              {copied ? <Check /> : <LinkIcon />}{copied ? t("copied") : t("copyLink")}
            </button>
          </div>
        </aside>
      </div>
    </div>,
    document.body,
  );
}

const PAGE = 380; // px: the note's first page, as big as it fits nicely

function Page({ item }: { item: Shared }) {
  return (
    <span className="grid overflow-hidden rounded-md bg-white shadow-lift" style={{ width: PAGE, aspectRatio: "794 / 1123" }}>
      {item.preview && <PagePreview preview={item.preview} library={library} width={PAGE} />}
    </span>
  );
}

const MINI = 160; // px: two across, in the folder's box

/** A folder: its box (as on the home screen, bigger), with up to four of its notes. */
function FolderPicture({ item }: { item: Shared }) {
  return (
    <span className="grid grid-cols-2 content-start gap-4 p-6 rounded-xl border-[1.5px] border-faint bg-paper"
          style={{ width: 2 * MINI + 16 + 48 + 3, aspectRatio: "794 / 1123" }}>
      {item.previews.slice(0, 4).map((preview, i) => (
        <span key={i} className="grid overflow-hidden rounded-[4px] bg-white shadow-island" style={{ width: MINI, aspectRatio: "794 / 1123" }}>
          <PagePreview preview={preview} library={library} width={MINI} />
        </span>
      ))}
    </span>
  );
}
