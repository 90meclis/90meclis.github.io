import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Skeleton } from "./components/ui";
import Home from "./pages/Home";

const MatchCenter = lazy(() => import("./pages/MatchCenter"));
const MatchDetail = lazy(() => import("./pages/MatchDetail"));
const PredictionBot = lazy(() => import("./pages/PredictionBot"));
const Archive = lazy(() => import("./pages/Archive"));
const Trust = lazy(() => import("./pages/Trust"));
const News = lazy(() => import("./pages/News"));
const Lab = lazy(() => import("./pages/Lab"));
const About = lazy(() => import("./pages/About"));
const Season = lazy(() => import("./pages/Season"));
const NotFound = lazy(() => import("./pages/NotFound"));

/** Eski adres: /tahmin-botu → /ortak (sorgu korunur). */
function OldBot() {
  const l = useLocation();
  return <Navigate to={`/ortak${l.search}`} replace />;
}

const base = import.meta.env.BASE_URL.replace(/\/$/, "");

export default function App() {
  return (
    <BrowserRouter basename={base}>
      <Suspense fallback={<Skeleton rows={5} />}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="mac-merkezi" element={<MatchCenter />} />
            <Route path="mac" element={<MatchDetail />} />
            <Route path="mac/:id" element={<MatchDetail />} />
            <Route path="ortak" element={<PredictionBot />} />
            <Route path="tahmin-botu" element={<OldBot />} />
            <Route path="tahmin-arsivi" element={<Archive />} />
            <Route path="guven-panosu" element={<Trust />} />
            <Route path="gundem-masasi" element={<News />} />
            <Route path="veri-laboratuvari" element={<Lab />} />
            <Route path="hakkinda" element={<About />} />
            <Route path="sezon-simulasyonu" element={<Season />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
