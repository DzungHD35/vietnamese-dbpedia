import { Suspense, lazy } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useHealth } from "./api/useHealth";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { GraphGate } from "./components/GraphGate";
import { Loading } from "./components/States";
import { HealthBadge } from "./components/HealthBadge";
import { SearchBox } from "./components/SearchBox";
import { useInference } from "./context/InferenceContext";
import { OverviewPage } from "./pages/OverviewPage";
import { SparqlPage } from "./pages/SparqlPage";

// các trang kéo theo Cytoscape / Leaflet tách thành chunk riêng để màn đầu tải nhanh
const AskPage = lazy(() => import("./pages/AskPage").then((m) => ({ default: m.AskPage })));
const EntityPage = lazy(() => import("./pages/EntityPage").then((m) => ({ default: m.EntityPage })));
const OntologyPage = lazy(() => import("./pages/OntologyPage").then((m) => ({ default: m.OntologyPage })));

const LINKS = [
  { to: "/", label: "Tổng quan", end: true },
  { to: "/ontology", label: "Ontology", end: false },
  { to: "/ask", label: "Hỏi đáp", end: false },
  { to: "/sparql", label: "SPARQL", end: false },
];

function InferenceToggle() {
  const { showInferred, setShowInferred } = useInference();
  return (
    <label className="toggle" title="Bật/tắt các triple do bộ suy luận OWL 2 RL thêm vào (nét đứt, màu tím)">
      <input type="checkbox" checked={showInferred} onChange={(e) => setShowInferred(e.target.checked)} />
      <span className="toggle-track" />
      Hiện suy luận
    </label>
  );
}

export function App() {
  const { health, offline } = useHealth();
  const { pathname } = useLocation();
  return (
    <>
      <header className="nav">
        <NavLink to="/" className="nav-logo">
          Vietnamese DBpedia
        </NavLink>
        <nav className="nav-links">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <span className="nav-spacer" />
        <SearchBox />
        <InferenceToggle />
        <HealthBadge health={health} offline={offline} />
      </header>
      <main className="page">
        <GraphGate health={health} offline={offline}>
          <Suspense fallback={<Loading />}>
            {/* key theo đường dẫn: lỗi ở một trang không khoá các trang khác */}
            <ErrorBoundary key={pathname}>
              <Routes>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/ontology" element={<OntologyPage />} />
                <Route path="/entity/:id" element={<EntityPage />} />
                <Route path="/ask" element={<AskPage />} />
                <Route path="/sparql" element={<SparqlPage />} />
                <Route path="*" element={<OverviewPage />} />
              </Routes>
            </ErrorBoundary>
          </Suspense>
        </GraphGate>
      </main>
    </>
  );
}
