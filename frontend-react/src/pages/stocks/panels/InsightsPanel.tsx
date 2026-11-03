import { InsightItem } from '../../../api';

export default function InsightsPanel({ items = [] }: { items?: InsightItem[] }) {
  if (!items.length) {
    return (
      <div className="insights-strip" role="note">
        Insights will appear here when suggestions are available.
      </div>
    );
  }

  return (
    <section className="panel">
      <h2>Insights</h2>
      <p className="panel-subtitle">Decision suggestions for this stock.</p>
      <div className="insights-list">
        {items.map((item) => (
          <article key={item.id} className="insight-card">
            <small>{item.kind}</small>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
            {item.citations?.length ? (
              <ul>
                {item.citations.map((citation) => (
                  <li key={citation}>{citation}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
