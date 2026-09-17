export default function PlaceholderPage({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="empty">
      <div style={{ fontWeight: 650, marginBottom: 6 }}>{title}</div>
      <div className="hint">Module này sẽ được triển khai ở {phase} theo kế hoạch phân giai đoạn trong prompt (mục 37).</div>
    </div>
  );
}
