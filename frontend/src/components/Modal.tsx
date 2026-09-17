import type { ReactNode } from 'react';

export default function Modal({
  title,
  wide,
  onCancel,
  onOk,
  okText = 'Xác nhận',
  cancelText = 'Hủy',
  okDisabled,
  danger,
  children,
}: {
  title: string;
  wide?: boolean;
  onCancel: () => void;
  onOk?: () => void;
  okText?: string;
  cancelText?: string;
  okDisabled?: boolean;
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="mask" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className={`modal${wide ? ' wide' : ''}`} role="dialog" aria-modal="true">
        <header>{title}</header>
        <div className="mbody">{children}</div>
        <footer>
          <button className="btn" onClick={onCancel}>
            {cancelText}
          </button>
          {onOk && (
            <button className={`btn ${danger ? 'danger' : 'primary'}`} onClick={onOk} disabled={okDisabled}>
              {okText}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
