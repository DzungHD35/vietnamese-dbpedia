import { useState, type ReactNode } from "react";

// bong bóng chữ đơn cách 11px ≈ 6,7px/ký tự, tối đa 60ch (CSS .iri-tip::after); dùng để đoán bề rộng trước khi hiện
const CHAR_PX = 6.7;
const PAD_PX = 20;
const MAX_CH = 60;

/**
 * Bọc một link: rê chuột hoặc focus thì hiện IRI đầy đủ ngay lập tức (bong bóng CSS `::after` từ `data-iri`,
 * không chờ 1 giây như `title`; `title` vẫn nên đặt trên link cho màn hình cảm ứng và trình đọc màn hình).
 * Gần mép phải màn hình thì canh phải để bong bóng không tràn ra ngoài.
 */
export function IriTip({ iri, children }: { iri: string; children: ReactNode }) {
  const [flip, setFlip] = useState(false);
  const place = (el: HTMLElement) => {
    const need = Math.min(iri.length, MAX_CH) * CHAR_PX + PAD_PX;
    setFlip(el.getBoundingClientRect().left + need > window.innerWidth - 12);
  };
  return (
    <span
      className={`iri-tip${flip ? " flip" : ""}`}
      data-iri={iri}
      onMouseEnter={(e) => place(e.currentTarget)}
      onFocus={(e) => place(e.currentTarget)}
    >
      {children}
    </span>
  );
}
