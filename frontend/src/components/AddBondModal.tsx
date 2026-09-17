import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, apiErrorMessage } from '../lib/api';
import { useToast } from '../lib/toast';
import Modal from './Modal';

export default function AddBondModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post('/bonds', { code: code.trim() });
      toast(`Đã tạo trái phiếu ${data.code}`, 'ok');
      qc.invalidateQueries({ queryKey: ['bonds'] });
      onClose();
      navigate(`/bonds/${data.id}`);
    } catch (err) {
      setError(apiErrorMessage(err, 'Không tạo được trái phiếu.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Thêm trái phiếu" onCancel={onClose} onOk={submit} okText="Tạo" okDisabled={busy || !code.trim()}>
      <div className="field">
        <label>Mã trái phiếu</label>
        <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} autoFocus placeholder="VD: VHML12617" />
      </div>
      {error && <div className="field err">{error}</div>}
    </Modal>
  );
}
