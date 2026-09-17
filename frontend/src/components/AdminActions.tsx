import { useRef, useState } from 'react';
import Modal from '../components/Modal';
import { api, apiErrorMessage } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useToast } from '../lib/toast';

export default function AdminActions() {
  const toast = useToast();
  const { hasRole } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showReset, setShowReset] = useState(false);
  const [showImportReport, setShowImportReport] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function exportJson() {
    try {
      const res = await api.get('/admin/export/json', { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'tps_ib_export.json';
      a.click();
      URL.revokeObjectURL(url);
      toast('Đã xuất JSON', 'ok');
    } catch (err) {
      toast(apiErrorMessage(err, 'Không xuất được dữ liệu.'), 'err');
    }
  }

  async function importJson(file: File) {
    const form = new FormData();
    form.append('file', file);
    setBusy(true);
    try {
      const { data } = await api.post('/admin/import/json', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      const createdSummary = Object.entries(data.created as Record<string, number>)
        .filter(([, n]) => n > 0)
        .map(([k, n]) => `${k}: +${n}`)
        .join(', ');
      const skippedSummary = Object.entries(data.skipped as Record<string, number>)
        .filter(([, n]) => n > 0)
        .map(([k, n]) => `${k}: bỏ qua ${n} (đã tồn tại)`)
        .join(', ');
      setShowImportReport(
        `Đã tạo mới: ${createdSummary || 'không có'}.\nBỏ qua (đã tồn tại): ${skippedSummary || 'không có'}.` +
          (data.errors.length ? `\nLỗi: ${data.errors.join('; ')}` : ''),
      );
      toast('Đã nhập JSON', 'ok');
    } catch (err) {
      toast(apiErrorMessage(err, 'Không nhập được dữ liệu.'), 'err');
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function triggerBackup() {
    setBusy(true);
    try {
      const { data } = await api.post('/admin/backup');
      toast(`Đã sao lưu: ${data.filename}`, 'ok');
    } catch (err) {
      toast(apiErrorMessage(err, 'Sao lưu thất bại.'), 'err');
    } finally {
      setBusy(false);
    }
  }

  if (!hasRole('Admin')) return null;

  return (
    <>
      <button className="btn" disabled={busy} onClick={exportJson}>
        Xuất JSON
      </button>
      <button className="btn" disabled={busy} onClick={() => fileInputRef.current?.click()}>
        Nhập JSON
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept="application/json"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) importJson(f);
        }}
      />
      <button className="btn" disabled={busy} onClick={triggerBackup}>
        Sao lưu
      </button>
      <button className="btn danger" disabled={busy} onClick={() => setShowReset(true)}>
        Xóa dữ liệu
      </button>

      {showReset && <ResetDataModal onClose={() => setShowReset(false)} />}

      {showImportReport && (
        <Modal title="Kết quả nhập JSON" onCancel={() => setShowImportReport(null)} cancelText="Đóng">
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{showImportReport}</pre>
        </Modal>
      )}
    </>
  );
}

function ResetDataModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [password, setPassword] = useState('');
  const [confirmWord, setConfirmWord] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.post('/admin/reset', { password, confirm_word: confirmWord });
      toast('Đã xóa toàn bộ dữ liệu nghiệp vụ.', 'ok');
      onClose();
      window.location.reload();
    } catch (err) {
      setError(apiErrorMessage(err, 'Không thực hiện được reset.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Xóa toàn bộ dữ liệu"
      onCancel={onClose}
      onOk={submit}
      okText="Xóa toàn bộ dữ liệu"
      danger
      okDisabled={busy || confirmWord !== 'RESET' || !password}
    >
      <p style={{ marginTop: 0, color: 'var(--neg)', fontWeight: 600 }}>
        Cảnh báo: thao tác này xóa toàn bộ dữ liệu nghiệp vụ (trái phiếu, benchmark, hợp đồng, IR, tuần, compliance) và ảnh
        hưởng tới TẤT CẢ người dùng đang sử dụng hệ thống. Không thể hoàn tác trừ khi khôi phục từ bản sao lưu.
      </p>
      <div className="field">
        <label>Mật khẩu của bạn</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      </div>
      <div className="field">
        <label>Gõ "RESET" để xác nhận</label>
        <input value={confirmWord} onChange={(e) => setConfirmWord(e.target.value)} />
      </div>
      {error && <div className="field err">{error}</div>}
    </Modal>
  );
}
