import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
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
const NotFound = lazy(() => import("./pages/NotFound"));

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
            <Route path="tahmin-botu" element={<PredictionBot />} />
            <Route path="tahmin-arsivi" element={<Archive />} />
            <Route path="guven-panosu" element={<Trust />} />
            <Route path="gundem-masasi" element={<News />} />
            <Route path="veri-laboratuvari" element={<Lab />} />
            <Route path="hakkinda" element={<About />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
