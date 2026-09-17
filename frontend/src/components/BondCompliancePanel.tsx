import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, apiErrorMessage } from '../lib/api';
import { curMonthKey } from '../lib/timeline';
import { useToast } from '../lib/toast';

interface Entry {
  id: string;
  month_key: string;
  text: string;
  done: boolean;
  note: string | null;
  deadline: string | null;
  version: number;
}
interface ItemGroup {
  item_id: string;
  group_key: string;
  item_key: string;
  name: string;
  entries: Entry[];
  done_count: number;
  total_count: number;
}

const GROUP_LABEL: Record<string, string> = { cbtt: 'CBTT định kỳ', ktdk: 'Kiểm tra định kỳ' };

export default function BondCompliancePanel({ bondId, canEdit }: { bondId: string; canEdit: boolean }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [month, setMonth] = useState(curMonthKey());

  const { data: groups, isLoading } = useQuery<ItemGroup[]>({
    queryKey: ['compliance', bondId, month],
    queryFn: async () => (await api.get(`/bonds/${bondId}/compliance`, { params: { month } })).data,
  });

  const refetch = () => qc.invalidateQueries({ queryKey: ['compliance', bondId, month] });

  async function addEntry(itemKey: string) {
    try {
      await api.post(`/bonds/${bondId}/compliance/${itemKey}/entries`, { month_key: month, text: '' });
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function toggleDone(entry: Entry) {
    try {
      await api.patch(`/bonds/${bondId}/compliance/entries/${entry.id}`, {
        text: entry.text, done: !entry.done, note: entry.note, deadline: entry.deadline, version: entry.version,
      });
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function saveText(entry: Entry, text: string) {
    if (text === entry.text) return;
    try {
      await api.patch(`/bonds/${bondId}/compliance/entries/${entry.id}`, {
        text, done: entry.done, note: entry.note, deadline: entry.deadline, version: entry.version,
      });
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function removeEntry(entry: Entry) {
    try {
      await api.delete(`/bonds/${bondId}/compliance/entries/${entry.id}`);
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  const doneTotal = groups?.reduce((s, g) => s + g.done_count, 0) ?? 0;
  const total = groups?.reduce((s, g) => s + g.total_count, 0) ?? 0;

  const byGroup = (groups ?? []).reduce<Record<string, ItemGroup[]>>((acc, g) => {
    (acc[g.group_key] ??= []).push(g);
    return acc;
  }, {});

  return (
    <div className="panel">
      <header>
        <h2>Sau đầu tư / Compliance</h2>
        <span className="hint spacer" style={{ textAlign: 'right' }}>
          {doneTotal}/{total} hoàn thành tháng {month}
        </span>
      </header>
      <div className="body">
        <div className="field" style={{ maxWidth: 220, marginBottom: 12 }}>
          <label>Tháng</label>
          <input placeholder="YYYY-MM" value={month} onChange={(e) => setMonth(e.target.value)} />
        </div>
        {isLoading ? (
          <div className="empty">Đang tải…</div>
        ) : (
          Object.entries(byGroup).map(([groupKey, items]) => (
            <div key={groupKey} style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 650, fontSize: 12, marginBottom: 6 }}>{GROUP_LABEL[groupKey] ?? groupKey}</div>
              {items.map((item) => (
                <div key={item.item_id} style={{ marginBottom: 8, paddingLeft: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <strong style={{ fontSize: 12 }}>{item.name}</strong>
                    <span className="hint">
                      ({item.done_count}/{item.total_count})
                    </span>
                    {canEdit && (
                      <button className="btn sm" onClick={() => addEntry(item.item_key)}>
                        + Add item
                      </button>
                    )}
                  </div>
                  <div className="cklist" style={{ marginTop: 4 }}>
                    {item.entries.map((e) => (
                      <div key={e.id} className={`ckrow${e.done ? ' done' : ''}`}>
                        <input type="checkbox" className="chk" checked={e.done} disabled={!canEdit} onChange={() => toggleDone(e)} />
                        <input
                          type="text"
                          defaultValue={e.text}
                          disabled={!canEdit}
                          placeholder="Nội dung công việc…"
                          onBlur={(ev) => saveText(e, ev.target.value)}
                        />
                        {canEdit && (
                          <button className="btn sm" onClick={() => removeEntry(e)}>
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
