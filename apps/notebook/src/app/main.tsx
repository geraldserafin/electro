// first: styles.css declares the order of the layers the slices' CSS goes into
import "./styles.css";
import "./i18n";
import "katex/dist/katex.min.css";
import { StrictMode, useLayoutEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigationType } from "react-router";
import { Downloads } from "@/features/downloads";
import { finishConnecting, startSaving } from "@/features/vault";
import { CoursePage } from "@/pages/CoursePage";
import { ExamplePage } from "@/pages/ExamplePage";
import { FolderPage } from "@/pages/FolderPage";
import { Home } from "@/pages/Home";
import { NotePage } from "@/pages/NotePage";

// /                    the user's library: their folders and notes
// /f/:id/:name         a folder (the name is only for reading: the id is what counts)
// /n/:id/:name         a note, edited
// /examples/:course    a course: its lessons (features/examples)
// /examples/:course/:lesson  a lesson: to read, change and run, saved only when added to the notes
// /auth/callback       back from GitHub's consent screen: connected, then where it started
// The notes are in this browser (features/vault); no one signs in. Opening the app saves the session
// from before (with GitHub: what is new there brought in). All under the address the app is served
// at (BASE_URL: on GitHub Pages, the repository's name).
void finishConnecting().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <ScrollOnNavigate />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/f/:id/:name?" element={<FolderPage />} />
          <Route path="/n/:id/:name?" element={<NotePage />} />
          <Route path="/examples/:course" element={<CoursePage />} />
          <Route path="/examples/:course/:name" element={<ExamplePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Downloads />
      </BrowserRouter>
    </StrictMode>,
  );
  startSaving(); // (after the first render: the lists hear what it brings from GitHub)
  dismissBoot();
});

/** A page gone to (a link, not back or forward, nor the address following a note's title) starts at its
 *  top: the window would keep where the page before was scrolled. Back, the browser brings it back. */
function ScrollOnNavigate() {
  const { pathname } = useLocation();
  const how = useNavigationType();
  useLayoutEffect(() => {
    if (how === "PUSH") window.scrollTo(0, 0);
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps -- (how: as it was when it moved)
  return null;
}

/** The loader over the page (index.html): once its bolt has filled up at least once, faded away. */
function dismissBoot() {
  const boot = document.getElementById("boot");
  if (!boot) return;
  const FILLED = 150 + 1000; // ms from the page's start: its delay, then 70 % of the 1.4 s fill
  window.setTimeout(
    () => {
      boot.classList.add("done");
      window.setTimeout(() => boot.remove(), 400);
    },
    Math.max(0, FILLED - performance.now()),
  );
}
