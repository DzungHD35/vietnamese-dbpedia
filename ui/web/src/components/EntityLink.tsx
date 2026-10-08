import { Link } from "react-router-dom";
import type { Node } from "../api/types";
import { shortIri } from "../utils/format";
import { kindColorVar } from "../utils/kinds";

const VIO = "http://vi.dbpedia.org/ontology/";
const VIP = "http://vi.dbpedia.org/property/";

type LinkNode = Pick<Node, "id" | "iri" | "label" | "kind" | "external">;

/** Link tới trang thực thể (có chấm màu theo loại); thuật ngữ vio: mở định nghĩa, IRI ngoài mở tab mới. */
export function EntityLink({ node, text }: { node: LinkNode; text?: string }) {
  const dot = <i className="dot" style={{ background: kindColorVar(node.kind) }} />;
  const label = text ?? (node.label.startsWith("http") ? shortIri(node.label) : node.label);
  if (!node.external) {
    return (
      <Link className="entity-link" to={`/entity/${encodeURIComponent(node.id)}`} title={node.iri}>
        {dot}
        {label}
      </Link>
    );
  }
  if (node.iri.startsWith(VIP)) {
    // vip: là thuộc tính thô từ infobox, máy chủ chưa có trang riêng
    return (
      <span className="entity-link" title={node.iri}>
        {dot}
        {label}
      </span>
    );
  }
  const href = node.iri.startsWith(VIO) ? `/ontology/${node.iri.slice(VIO.length)}` : node.iri;
  return (
    <a className="entity-link" href={href} target="_blank" rel="noopener noreferrer" title={node.iri}>
      {dot}
      {label} ↗
    </a>
  );
}
