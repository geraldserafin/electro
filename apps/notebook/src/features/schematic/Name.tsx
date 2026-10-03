/** "U_R5" → U with a subscript R5 (as a book writes it). */
export function Name({ text }: { text: string }) {
  const [base, ...sub] = text.split("_");
  return (
    <>
      {base}
      {sub.length > 0 && <sub className="static align-sub text-[0.72em] leading-[inherit]">{sub.join("")}</sub>}
    </>
  );
}
