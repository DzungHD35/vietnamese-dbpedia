import type { MouseEvent } from "react";

// Mũi tên mở/thu dùng chung cho các cây (Cây tài nguyên ở trang Ontology, Cây quan hệ ở trang Thực thể); CSS: .ct-chev

export function Chevron({ open, onToggle, small = false }: { open: boolean; onToggle: () => void; small?: boolean }) {
  return (
    <button
      type="button"
      className={`ct-chev${small ? " ct-chev-sm" : ""}${open ? " open" : ""}`}
      aria-expanded={open}
      aria-label={open ? "Thu" : "Mở"}
      title={open ? "Thu" : "Mở"}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
    >
      ▸
    </button>
  );
}

/** Chỗ trống cùng bề rộng mũi tên để nhãn của nút lá thẳng hàng với nút khác. */
export function LeafMark({ small = false }: { small?: boolean }) {
  return (
    <span className={`ct-chev ct-leaf${small ? " ct-chev-sm" : ""}`} aria-hidden="true">
      ▸
    </span>
  );
}

/** Bấm vào dòng (trừ link / nút bên trong) thì mở/thu nút đó. */
export function rowToggle(onToggle: () => void) {
  return (e: MouseEvent<HTMLElement>) => {
    if ((e.target as HTMLElement).closest("a, button")) return;
    onToggle();
  };
}
