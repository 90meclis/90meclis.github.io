import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "@fontsource/barlow-condensed/600.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource/barlow-condensed/800.css";
import "./styles/app.css";
import App from "./App";
import { leagueNames } from "./lib/data";
import { registerLeagues } from "./lib/labels";

const render = () => createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
// Lig adları (leagues tablosu) en çok 1,5 sn beklenir; gelmezse kodlar sabit listeyle gösterilir.
Promise.race([leagueNames().then(registerLeagues).catch(() => undefined), new Promise((r) => setTimeout(r, 1500))]).finally(render);
