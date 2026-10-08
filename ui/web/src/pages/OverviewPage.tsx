import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Placeholder } from "../components/Placeholder";

export function OverviewPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const resource = params.get("resource");

  // /resource/X (Linked Data) chuyển trình duyệt về /?resource=X; ở đây đổi thành trang thực thể
  useEffect(() => {
    if (resource) navigate(`/entity/${encodeURIComponent(resource)}`, { replace: true });
  }, [resource, navigate]);

  return <Placeholder title="Tổng quan dataset" note="Sẽ làm ở phase P2." />;
}
