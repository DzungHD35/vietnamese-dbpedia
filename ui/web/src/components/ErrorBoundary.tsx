import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  error: Error | null;
}

/** Chặn lỗi render của một trang để cả ứng dụng không trắng màn; đặt `key` theo đường dẫn để đổi trang là thử lại. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Lỗi khi hiển thị trang:", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="state state-error boundary" role="alert">
        <strong>Có lỗi khi hiển thị trang này.</strong>
        <pre className="boundary-msg">{error.message}</pre>
        <div className="boundary-actions">
          <button type="button" className="btn" onClick={() => window.location.reload()}>
            Tải lại
          </button>
          <a className="btn" href="/">
            Về Tổng quan
          </a>
        </div>
      </div>
    );
  }
}
