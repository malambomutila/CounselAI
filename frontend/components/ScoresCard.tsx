import type { ScoreRow } from "@/lib/api";

export function ScoresCard({ rows }: { rows: ScoreRow[] }) {
  return (
    <div className="scores-card">
      <h3>Argument Scores</h3>
      {rows.length === 0 ? (
        <p className="text-sm text-ink-subtle italic">
          Scores will appear after the Judge rules.
        </p>
      ) : (
        <table className="scores-table">
          <thead>
            <tr>
              <th>Criterion</th>
              <th>Plaintiff</th>
              <th>Defense</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r.criterion}</td>
                <td>{r.plaintiff}</td>
                <td>{r.defense}</td>
                <td className="text-ink-muted">{r.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
