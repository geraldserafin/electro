// A grid of folders and notes — the home screen's, or a folder's: folders first (a picture of a
// few of their notes, like an iPhone's), then notes. "New" comes first (a note or a folder); a card's
// "⋯" renames, moves ("Move to…"), shares or deletes it; a card dragged onto a folder goes into it.
import { useAtomSet } from "@effect-atom/atom-react";
import type { ItemCard, Role } from "@electro/notes-api";
import { type Cause, Exit } from "effect";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Card,
  createFolder,
  failure,
  folderUrl,
  LIBRARY,
  NewCard,
  noteUrl,
  patchItem,
  removeItem,
  useCreateNote,
  useWhen,
} from "@/features/notes";
import { library } from "@/features/schematic";
import { leave, ShareDialog, enabled as sharingOn } from "@/features/sharing";
import { blank } from "@/shared/model/format";
import { FolderIcon, PageIcon } from "@/shared/ui/icons";
import { dragging } from "./drag";
import { FolderThumb } from "./FolderThumb";
import { MoveDialog } from "./MoveDialog";
import { canEdit, canTakeOut } from "./rules";

const grid =
  "grid w-full grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-x-6 gap-y-7 max-sm:grid-cols-2 max-sm:gap-x-4 max-sm:gap-y-5";

export function LibraryGrid({
  items,
  parentId,
  container,
  label,
  onProblem,
}: {
  items: readonly ItemCard[];
  parentId: string | null; // where new things go (null: the top of the user's own)
  container: Role | null; // the user's role in that folder (null: the home screen)
  label: string;
  onProblem: (problem: string | null) => void;
}) {
  const { t } = useTranslation("library");
  const { t: tSharing } = useTranslation("sharing");
  const when = useWhen();
  const createNote = useCreateNote();
  const folder = useAtomSet(createFolder, { mode: "promiseExit" });
  const patch = useAtomSet(patchItem, { mode: "promiseExit" });
  const remove = useAtomSet(removeItem, { mode: "promiseExit" });
  const { said, moveTo: move } = useLibraryCalls(onProblem);
  const [moving, setMoving] = useState<ItemCard | null>(null);
  const [sharing, setSharing] = useState<ItemCard | null>(null);
  const quit = useAtomSet(leave, { mode: "promiseExit" });
  const [over, setOver] = useState<string | null>(null);
  const writable = container === null || container === "owner" || container === "editor";
  const moveTo = (card: ItemCard, into: string | null) => {
    setMoving(null);
    return move(card, into);
  };

  const actions = (card: ItemCard) => {
    const name = card.name || t("untitled");
    return [
      ...(sharingOn && card.role === "owner" ? [{ label: `${tSharing("share")}…`, run: () => setSharing(card) }] : []),
      ...(canEdit(card)
        ? [
            {
              label: t("rename"),
              run: async () => {
                const next = prompt(t("renamePrompt"), card.name)?.trim();
                if (next && next !== card.name)
                  said(await patch({ path: { id: card.id }, payload: { name: next }, reactivityKeys: LIBRARY }));
              },
            },
          ]
        : []),
      ...(canTakeOut(card, container)
        ? [
            { label: t("move"), run: () => setMoving(card) },
            {
              label: t("delete"),
              danger: true,
              run: async () => {
                if (
                  !confirm(
                    card.kind === "folder" ? t("confirmDeleteFolder", { name }) : t("confirmDeleteNote", { name }),
                  )
                )
                  return;
                said(await remove({ path: { id: card.id }, reactivityKeys: LIBRARY }));
              },
            },
          ]
        : []),
      // shared with the user on its own (at the top of their home screen): off it
      ...(card.owner !== null && container === null
        ? [
            {
              label: tSharing("leave"),
              danger: true,
              run: async () => {
                if (confirm(tSharing("confirmLeave", { name })))
                  said(await quit({ path: { id: card.id }, reactivityKeys: LIBRARY }));
              },
            },
          ]
        : []),
    ];
  };

  /** Picked up (what may be taken out), dropped onto (a folder the user may put things into). */
  const drag = (card: ItemCard) => ({
    draggable: canTakeOut(card, container),
    onDragStart: () => dragging.start(card),
    onDragEnd: () => {
      dragging.end();
      setOver(null);
    },
    ...(card.kind === "folder" && canEdit(card)
      ? {
          onDragOver: (e: React.DragEvent) => {
            const moved = dragging.get();
            if (!moved || moved.id === card.id) return;
            e.preventDefault();
            setOver(card.id);
          },
          onDragLeave: (e: React.DragEvent) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(null);
          },
          onDrop: (e: React.DragEvent) => {
            e.preventDefault();
            setOver(null);
            const moved = dragging.get();
            if (moved) void moveTo(moved, card.id);
          },
        }
      : {}),
  });

  const meta = (card: ItemCard) =>
    [
      card.owner ? t("sharedBy", { name: card.owner.name }) : null,
      card.shared ? t("shared") : null,
      card.role === "viewer" ? t("readOnly") : null,
      card.kind === "folder"
        ? card.count
          ? t("items", { count: card.count })
          : t("empty")
        : card.modified
          ? when(card.modified)
          : null,
    ]
      .filter(Boolean)
      .join(" · ");

  return (
    <>
      <ul className={grid} aria-label={label}>
        {writable && (
          <NewCard
            label={t("new")}
            choices={[
              {
                label: t("newNote"),
                icon: <PageIcon />,
                run: async () => {
                  onProblem(null);
                  if (!(await createNote(blank(), { parentId }))) onProblem(t("problem.failed"));
                },
              },
              {
                label: t("newFolder"),
                icon: <FolderIcon />,
                run: async () => {
                  const name = prompt(t("folderName"))?.trim();
                  if (name) said(await folder({ payload: { name, parentId }, reactivityKeys: LIBRARY }));
                },
              },
            ]}
          />
        )}
        {items.map((card, i) => (
          <Card
            key={card.id}
            index={i}
            id={card.id}
            title={card.name || t("untitled")}
            meta={meta(card)}
            library={library}
            to={card.kind === "folder" ? folderUrl(card.id, card.name) : noteUrl(card.id, card.name)}
            preview={card.preview ?? undefined}
            thumb={card.kind === "folder" ? <FolderThumb previews={card.previews} library={library} /> : undefined}
            actions={actions(card)}
            drag={drag(card)}
            target={over === card.id}
          />
        ))}
      </ul>
      {moving && (
        <MoveDialog card={moving} onChoose={(into) => void moveTo(moving, into)} onClose={() => setMoving(null)} />
      )}
      {sharing && <ShareDialog item={sharing} onClose={() => setSharing(null)} />}
    </>
  );
}

/** A call's outcome said (the server's reason, if it gave one), and moving a card into a folder
 *  (null: the top) — for the grid, and for the breadcrumbs a card may be dropped onto. */
export function useLibraryCalls(onProblem: (problem: string | null) => void) {
  const { t } = useTranslation("library");
  const patch = useAtomSet(patchItem, { mode: "promiseExit" });
  const said = (exit: Exit.Exit<unknown, unknown>) => {
    if (Exit.isSuccess(exit)) return onProblem(null);
    const tag = failure(exit.cause as Cause.Cause<unknown>)?._tag;
    const known = ["MoveIntoItself", "OtherOwner", "RoleTooLow", "NotFound", "NotAFolder"] as const;
    onProblem(t(`problem.${known.find((k) => k === tag) ?? "failed"}`));
  };
  const moveTo = async (card: ItemCard, into: string | null) => {
    if (into === card.parentId || into === card.id) return;
    said(await patch({ path: { id: card.id }, payload: { parentId: into }, reactivityKeys: LIBRARY }));
  };
  return { said, moveTo };
}
