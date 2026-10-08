export function Loading({ text = "Đang tải…" }: { text?: string }) {
  return <div className="state state-loading">{text}</div>;
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state state-error" role="alert">
      <strong>Có lỗi:</strong> {message}
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return <div className="state state-empty">{text}</div>;
}
