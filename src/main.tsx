import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { setLang, getLang } from "./i18n";

// ?lang=ar|en picks the language and direction, else the one last chosen with the header's language button.
let chosen: string | null = new URLSearchParams(location.search).get("lang");
if (!chosen) { try { chosen = localStorage.getItem("isit.lang"); } catch { /* storage blocked */ } }
setLang(chosen);
document.documentElement.lang = getLang();
document.documentElement.dir = getLang() === "ar" ? "rtl" : "ltr";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
