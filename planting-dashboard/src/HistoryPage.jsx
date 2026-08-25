import { useState, useEffect } from 'react';
import axios from 'axios';

// ---------------------------------------------------------------------------
// HistoryPage
// Lists past Random Forest + Weighted Bipartite Matching runs so an LGU
// planner can look back at previous planting blueprints and re-download them.
//
// BACKEND NOTE: This calls GET http://localhost:8000/api/history, which does
// not exist in main.py yet. If that call fails (404 / network error), the
// page falls back to sample rows so the screen is still demoable and your
// co-programmer can build the frontend without waiting on the backend.
//
// Once the FastAPI backend has a real history endpoint, remove the
// `catch` fallback block and let errors surface normally.
// ---------------------------------------------------------------------------

const SAMPLE_HISTORY = [
  {
    id: 'run-2026-08-20',
    date: '2026-08-20 09:14',
    totalAssignments: 42,
    engine: 'Bipartite Matching',
    status: 'Committed',
  },
  {
    id: 'run-2026-08-12',
    date: '2026-08-12 14:02',
    totalAssignments: 37,
    engine: 'Bipartite Matching',
    status: 'Committed',
  },
  {
    id: 'run-2026-08-05',
    date: '2026-08-05 10:47',
    totalAssignments: 30,
    engine: 'Bipartite Matching',
    status: 'Pending Review',
  },
];

function HistoryPage() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [usingSampleData, setUsingSampleData] = useState(false);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/history');
        setHistory(response.data.data);
      } catch (error) {
        console.warn('No /api/history endpoint yet — showing sample data.', error.message);
        setHistory(SAMPLE_HISTORY);
        setUsingSampleData(true);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, []);

  // Placeholder export: opens the browser's print dialog scoped to this run,
  // which can be saved as a PDF. Swap for a real backend PDF export
  // (e.g. GET /api/history/{id}/blueprint.pdf) when that endpoint exists.
  const handleDownloadBlueprint = (run) => {
    window.print();
  };

  return (
    <div style={{ minHeight: '100vh', width: '100%', backgroundColor: '#f4f6f8', fontFamily: 'sans-serif' }}>
      <div style={{ padding: '25px 40px', backgroundColor: '#1a365d', color: 'white' }}>
        <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 'bold' }}>
          Planting History &amp; Logs
        </h2>
        <p style={{ margin: '5px 0 0 0', fontSize: '0.9rem', color: '#a0aec0' }}>
          Past species-site suitability and matching runs
        </p>
      </div>

      <div style={{ padding: '30px 40px' }}>
        {usingSampleData && (
          <div
            style={{
              padding: '12px 16px',
              backgroundColor: '#fffaf0',
              border: '1px solid #feebc8',
              borderRadius: '6px',
              color: '#975a16',
              fontSize: '0.85rem',
              marginBottom: '20px',
            }}
          >
            Showing sample data — the backend does not have a <code>/api/history</code> endpoint yet.
          </div>
        )}

        {loading ? (
          <p style={{ color: '#4a5568' }}>Loading past runs…</p>
        ) : (
          <div
            style={{
              backgroundColor: 'white',
              borderRadius: '8px',
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
              overflow: 'hidden',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ backgroundColor: '#edf2f7' }}>
                  <th style={thStyle}>Run Date</th>
                  <th style={thStyle}>Total Assignments</th>
                  <th style={thStyle}>Engine</th>
                  <th style={thStyle}>Status</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {history.map((run) => (
                  <tr key={run.id} style={{ borderTop: '1px solid #edf2f7' }}>
                    <td style={tdStyle}>{run.date}</td>
                    <td style={tdStyle}>{run.totalAssignments}</td>
                    <td style={tdStyle}>{run.engine}</td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontWeight: 'bold',
                          color: run.status === 'Committed' ? '#38a169' : '#d69e2e',
                        }}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
                      <button
                        onClick={() => handleDownloadBlueprint(run)}
                        style={{
                          padding: '8px 14px',
                          backgroundColor: '#3182ce',
                          color: 'white',
                          border: 'none',
                          borderRadius: '6px',
                          fontSize: '0.85rem',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                        }}
                      >
                        Download Blueprint as PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {history.length === 0 && (
              <p style={{ padding: '20px', color: '#718096', textAlign: 'center' }}>
                No planting runs recorded yet.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const thStyle = {
  textAlign: 'left',
  padding: '14px 16px',
  fontSize: '0.8rem',
  color: '#4a5568',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
};

const tdStyle = {
  padding: '14px 16px',
  fontSize: '0.9rem',
  color: '#2d3748',
};

export default HistoryPage;
