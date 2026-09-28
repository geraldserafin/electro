// first: styles.css declares the order of the layers the slices' CSS goes into
import "./styles.css";
import "./i18n";
import "katex/dist/katex.min.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { ExamplePage } from "@/pages/ExamplePage";
import { Home } from "@/pages/Home";
import { NotePage } from "@/pages/NotePage";

// /                 all notes
// /notes/:ref       a note (by its slug — from the title — or id), read from the server and edited
// /examples/:name   a new note from an example (then its address)
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/notes/:ref" element={<NotePage />} />
        <Route path="/examples/:name" element={<ExamplePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
