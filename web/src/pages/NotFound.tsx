import { Link } from "react-router-dom";
import { usePageMeta } from "../lib/seo";
import { Empty } from "../components/ui";

export default function NotFound() {
  usePageMeta("Sayfa bulunamadı");
  return <Empty title="Aradığın sayfa masada yok" icon="?"><Link to="/" className="btn primary">Ana sayfaya dön</Link></Empty>;
}
