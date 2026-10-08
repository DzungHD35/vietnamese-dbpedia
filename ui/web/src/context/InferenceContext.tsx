import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

const STORAGE_KEY = "vdb.showInferred";

interface InferenceValue {
  showInferred: boolean;
  setShowInferred: (v: boolean) => void;
}

const InferenceContext = createContext<InferenceValue>({ showInferred: true, setShowInferred: () => {} });

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== "0";
  } catch {
    return true; // localStorage có thể bị chặn (cửa sổ ẩn danh, v.v.)
  }
}

/** Công tắc toàn cục "Hiện suy luận": mọi màn đọc cùng một giá trị. */
export function InferenceProvider({ children }: { children: ReactNode }) {
  const [showInferred, setState] = useState(readStored);
  const setShowInferred = useCallback((v: boolean) => {
    setState(v);
    try {
      localStorage.setItem(STORAGE_KEY, v ? "1" : "0");
    } catch {
      /* bỏ qua: vẫn hoạt động trong phiên hiện tại */
    }
  }, []);
  return <InferenceContext.Provider value={{ showInferred, setShowInferred }}>{children}</InferenceContext.Provider>;
}

export function useInference() {
  return useContext(InferenceContext);
}
