// What is sent to the model besides text: pictures — a screenshot, a photo, a PDF's pages drawn
// here (pdf.js, loaded the first time a PDF comes) — each made smaller first (JPEG, at most 1600 px
// a side): screenshots are big, and the request has a size limit.
export const MAX_PICTURES = 12;
const SIDE = 1600;

/** A PDF page's own text (its text layer), by its picture: the words as written, for the reading to
 *  hold to (agent.ts). */
export const textOf = new Map<string, string>();

function toJpeg(source: CanvasImageSource, width: number, height: number): string {
  const scale = Math.min(1, SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const g = canvas.getContext("2d")!;
  g.fillStyle = "#fff"; // (a transparent PNG on white, as on paper)
  g.fillRect(0, 0, canvas.width, canvas.height);
  g.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.85);
}

async function picture(file: Blob): Promise<string> {
  const bitmap = await createImageBitmap(file);
  return toJpeg(bitmap, bitmap.width, bitmap.height);
}

/** A PDF's first pages, drawn. */
async function pages(file: Blob, max: number): Promise<string[]> {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).href;
  const pdf = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
  const out: string[] = [];
  for (let n = 1; n <= Math.min(pdf.numPages, max); n++) {
    const page = await pdf.getPage(n);
    const viewport = page.getViewport({ scale: 2 });
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvas, viewport }).promise;
    const url = toJpeg(canvas, canvas.width, canvas.height);
    const text = (await page.getTextContent()).items.map((i) => ("str" in i ? i.str : "")).join(" ");
    if (text.trim()) textOf.set(url, text.replace(/\s+/g, " ").trim());
    out.push(url);
  }
  return out;
}

/** Files (pictures, PDFs) as pictures for the model, at most ``room`` of them. */
export async function picturesOf(files: Iterable<File>, room: number): Promise<string[]> {
  const out: string[] = [];
  for (const file of files) {
    if (out.length >= room) break;
    if (file.type === "application/pdf") out.push(...(await pages(file, room - out.length)));
    else if (file.type.startsWith("image/")) out.push(await picture(file));
  }
  return out.slice(0, room);
}

export const accepts = (file: File) => file.type === "application/pdf" || file.type.startsWith("image/");
