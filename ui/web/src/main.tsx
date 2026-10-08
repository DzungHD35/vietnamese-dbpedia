import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { InferenceProvider } from "./context/InferenceContext";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/components.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <InferenceProvider>
        <App />
      </InferenceProvider>
    </BrowserRouter>
  </StrictMode>,
);
