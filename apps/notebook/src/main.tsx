import "katex/dist/katex.min.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { ExamplePage } from "./routes/ExamplePage";
import { Home } from "./routes/Home";
import { NotePage } from "./routes/NotePage";
import "./styles.css";

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
