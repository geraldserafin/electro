// first: styles.css declares the order of the layers the slices' CSS goes into
import "./styles.css";
import "./i18n";
import "katex/dist/katex.min.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AuthGate } from "@/features/auth";
import { ExamplePage } from "@/pages/ExamplePage";
import { FolderPage } from "@/pages/FolderPage";
import { Home } from "@/pages/Home";
import { JoinPage } from "@/pages/JoinPage";
import { LegacyNotePage } from "@/pages/LegacyNotePage";
import { NotePage } from "@/pages/NotePage";

// /                    the user's library: their folders and notes, and what was shared with them
// /f/:id/:name         a folder (the name is only for reading: the id is what counts)
// /n/:id/:name         a note, read from the server and edited
// /notes/:ref          a note's address from before folders: goes to /n/:id
// /examples/:name      a new note from an example (then its address)
// /join/:token        a share's link: the item becomes the user's to open, and opens
// all behind signing in: without a session, the sign-in page (at the same address)
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthGate>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/f/:id/:name?" element={<FolderPage />} />
          <Route path="/n/:id/:name?" element={<NotePage />} />
          <Route path="/notes/:ref" element={<LegacyNotePage />} />
          <Route path="/examples/:name" element={<ExamplePage />} />
          <Route path="/join/:token" element={<JoinPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthGate>
    </BrowserRouter>
  </StrictMode>,
);
