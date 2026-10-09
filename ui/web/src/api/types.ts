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
// mọi số liệu lấy bằng `.get()` từ stats.json nên có thể thiếu (null)
export interface Stats {
  total: number | null;
  asserted: number | null;
  inferred: number | null;
  ontology: number | null;
  entities: number | null;
  careerStations: number | null;
  sameAsDbpedia: number | null;
  sameAsWikidata: number | null;
  validationErrors: number | null;
  validationWarnings: number | null;
  built: string | null;
  reasoner: string | null;
  reasoningSeconds: number | null;
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

// ---- /api/entity/{id}/tree (cây quan hệ, giống mục "Cây quan hệ" ở tab Tài nguyên của Gradio) ----
export interface RelationGroup {
  prop: string; // qname, ví dụ "vio:careerStation"
  label: string;
  direction: "out" | "in";
  total: number;
  more: number; // số con bị cắt bớt (total - children.length)
  children: RelationNode[];
}

export interface RelationNode {
  node: Node;
  station: string | null; // id chặng thi đấu khi nút là đội của một chặng (vio:careerStation → vio:team)
  note: string | null; // "2015–2023, 103 trận, 36 bàn"
  groups: RelationGroup[]; // lồng tới maxDepth; chỉ triple khai báo
}

export interface RelationTree {
  root: Node;
  maxDepth: number;
  groups: RelationGroup[];
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

// ---- /api/ontology ----
export interface OntologyProperty {
  id: string;
  term: string;
  label: string;
  labelEn: string;
  kind: "object" | "datatype";
  range: string | null;
  domain: string | null;
  subPropertyOf: string[];
  functional: boolean;
  inverseOf: string | null;
  inferred: number;
}

export interface OntologyClass {
  id: string;
  term: string;
  label: string;
  labelEn: string;
  parent: string | null;
  dbo: string[];
  depth: number;
  asserted: number;
  total: number;
  properties: OntologyProperty[];
}

export interface OntologyAxioms {
  chains: { property: string; chain: string[]; inferred: number }[];
  inverses: { a: string; b: string; inferredA: number; inferredB: number }[];
  restrictions: { kind: string; onClass: string; property: string; filler: string; text: string; inferred: number }[];
  disjoint: string[][];
}

export interface Ontology {
  stats: {
    classes: number;
    objectProperties: number;
    datatypeProperties: number;
    triples: number;
    download: string;
    namespace: string;
  };
  classes: OntologyClass[]; // tiền thứ tự (cha trước con), thụt lề theo `depth`
  properties: OntologyProperty[];
  axioms: OntologyAxioms;
}

// ---- /api/tree (cây tài nguyên, giống tab "Cây tài nguyên" của Gradio) ----
export interface TreeItem {
  id: string;
  iri: string; // http://vi.dbpedia.org/resource/… (UI vẫn tự ghép nếu máy chủ cũ không trả)
  label: string;
  kind: Kind;
}

export interface TreeClass {
  id: string;
  term: string;
  label: string;
  parent: string | null;
  depth: number;
  dbo: string[];
  total: number; // thực thể của lớp và các lớp con, kể cả nhờ suy luận
  asserted: number;
  direct: TreeItem[]; // thực thể trực tiếp, đã sắp theo nhãn và cắt bớt
  directTotal: number; // số thực thể trực tiếp (sau lọc) chưa cắt
  directShown: number;
}

export interface TreeGroup {
  id: string;
  title: string;
  note: string;
  total: number; // chưa lọc
  matched: number; // sau lọc (= total khi không lọc)
  items: TreeItem[];
  shown: number;
}

export interface ResourceTree {
  query: string;
  summary: { classes: number; resources: number };
  classes: TreeClass[]; // tiền thứ tự (cha trước con); khi lọc chỉ gồm lớp có kết quả hoặc có lớp con có kết quả
  groups: TreeGroup[];
}
