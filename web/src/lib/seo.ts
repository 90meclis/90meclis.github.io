import { useEffect } from "react";
import routes from "./routes.json";

export const SITE = "90 Meclis";
export const ROUTES: { path: string; title: string; description: string }[] = routes;

export function usePageMeta(title: string, description?: string) {
  useEffect(() => {
    document.title = title.startsWith(SITE) ? title : `${title} · ${SITE}`;
    if (description) document.querySelector('meta[name="description"]')?.setAttribute("content", description);
  }, [title, description]);
}
