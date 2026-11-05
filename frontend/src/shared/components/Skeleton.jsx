// Placeholder shown while its data loads. Shapes roughly match the real layout to avoid layout shift.
export default function Skeleton({ rows = 4, cards = 0 }) {
  return (
    <div className="skel" role="status" aria-label="Loading">
      <div className="skel-line w40" /><div className="skel-line w25" />
      {cards > 0 && <div className="skel-cards">{Array.from({ length: cards }, (_, i) => <div key={i} className="skel-card" />)}</div>}
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skel-row" />)}
    </div>
  );
}
