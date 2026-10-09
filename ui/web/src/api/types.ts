// Kiểu dữ liệu JSON của ui/api (xem .agents/PLAN.md §2). Cập nhật khi thêm endpoint.

export type Kind = "player" | "club" | "stadium" | "uni" | "prov" | "station" | "other" | "lod";

export interface Health {
  ready: boolean;
  asserted_ready: boolean;
  llm: boolean;
  message: string;
  error: string | null;
}

export interface Node {
  id: string;
  iri: string;
  label: string;
  cls: string;
  kind: Kind;
  external?: boolean;
}

export interface SearchHit {
  id: string;
  label: string;
  cls: string;
  kind: Kind;
}

export type Value =
  | { type: "literal"; value: string; lang?: string; datatype?: string; inferred: boolean }
  | { type: "iri"; node: Node; inferred: boolean };

export interface Edge {
  source: string;
  target: string;
  prop: string;
  propLabel: string;
  inferred: boolean;
}

export interface GraphData {
  nodes: Node[];
  edges: Edge[];
}

export interface Neighbors extends GraphData {
  center: Node;
  hidden: number;
}

// ---- /api/overview ----
export interface Stats {
  total: number;
  asserted: number;
  inferred: number;
  ontology: number;
  entities: number;
  careerStations: number;
  sameAsDbpedia: number;
  sameAsWikidata: number;
  validationErrors: number;
  validationWarnings: number;
  built: string;
  reasoner: string;
  reasoningSeconds: number;
}

export interface ClassRow {
  id: string;
  label: string;
  parent: string | null;
  dbo: string[];
  total: number;
  asserted: number;
  direct: number;
}

export interface InferredProp {
  prop: string;
  label: string;
  count: number;
}

export interface Overview {
  stats: Stats;
  byClass: ClassRow[];
  inferredByPredicate: InferredProp[];
  featured: Node[];
  questions: string[];
}

// ---- /api/entity/{id} ----
export interface EntityClass {
  id: string;
  label: string;
  inferred: boolean;
  parent: string | null;
  also: string[];
}

export interface Lod {
  wikipedia: string | null;
  dbpedia: string[];
  wikidata: string[];
  derivedFrom: string | null;
  lat: number | null;
  lon: number | null;
  linkedData: string;
}

export type StationKind = "youth" | "club" | "national";

export interface CareerStation {
  station: string;
  kind: StationKind;
  team: Node | null;
  start: number | null;
  end: number | null;
  apps: number | null;
  goals: number | null;
  onLoan: boolean;
}

export interface Fact {
  prop: string;
  label: string;
  ns: "vio" | "dbo" | "other" | "vip";
  values: Value[];
  more: number;
}

export interface IncomingGroup {
  prop: string;
  label: string;
  count: number;
  items: (Node & { inferred: boolean })[];
}

export interface Entity {
  node: Node;
  abstract: string | null;
  thumbnail: string | null;
  altLabels: string[];
  classes: EntityClass[];
  lod: Lod;
  career: CareerStation[];
  facts: Fact[];
  incoming: IncomingGroup[];
  counts: { asserted: number; inferred: number };
}

// ---- /api/ask ----
export interface AssertedInfo {
  rows: number | null;
  status: "ok" | "loading" | "error";
  error?: string;
}

export type Cells = Record<string, string>;

export interface AskResult {
  question: string;
  source: "cache" | "llm";
  sparql: string;
  attempts: number;
  error: string | null;
  columns: string[];
  rows: Cells[];
  rowsTotal: number;
  links: Record<string, Node>;
  evidence: Node[];
  asserted: AssertedInfo;
}

export interface AnswerResult {
  answer: string | null;
  reasoning: string;
  source: "cache" | "llm" | "none";
  note?: string;
}

// ---- /api/sparql ----
export interface SparqlResult {
  type: "SELECT" | "ASK" | "CONSTRUCT" | "DESCRIBE" | null;
  columns: string[];
  rows: Cells[];
  links: Record<string, Node>;
  total: number;
  ms: number;
  error: string | null;
}

export interface SparqlExample {
  name: string;
  query: string;
}

// ---- /api/map ----
export interface MapPoint {
  node: Node;
  lat: number;
  lon: number;
  former: boolean;
}

export interface Succession {
  from: string;
  to: string;
  year: number | null;
  inferred: boolean;
}

export interface MapData {
  points: MapPoint[];
  successions: Succession[];
  successionsTotal: number;
}
