import { useParams } from "react-router-dom";
import { Placeholder } from "../components/Placeholder";

export function EntityPage() {
  const { id } = useParams();
  return <Placeholder title={`Thực thể: ${id ?? ""}`} note="Sẽ làm ở phase P3." />;
}
