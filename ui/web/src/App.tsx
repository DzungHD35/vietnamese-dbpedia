import { NavLink, Route, Routes } from "react-router-dom";
import { HealthBadge } from "./components/HealthBadge";
import { SearchBox } from "./components/SearchBox";
import { useInference } from "./context/InferenceContext";
import { AskPage } from "./pages/AskPage";
import { EntityPage } from "./pages/EntityPage";
import { MapPage } from "./pages/MapPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SparqlPage } from "./pages/SparqlPage";

const LINKS = [
  { to: "/", label: "Tổng quan", end: true },
  { to: "/ask", label: "Hỏi đáp", end: false },
  { to: "/sparql", label: "SPARQL", end: false },
  { to: "/map", label: "Bản đồ", end: false },
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
        <HealthBadge />
      </header>
      <main className="page">
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/entity/:id" element={<EntityPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/sparql" element={<SparqlPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="*" element={<OverviewPage />} />
        </Routes>
      </main>
    </>
  );
}
