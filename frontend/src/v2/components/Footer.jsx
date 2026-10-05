// Footer: the dataset version tag and hash from GET /health.
export default function Footer({ health }) {
  const d = health.status === 'ok' ? health.data : null
  return (
    <footer className="v2-footer">
      {d ? (
        <>
          <span>
            Dataset version <strong>{d.dataset_version ?? 'Data Unavailable'}</strong>
          </span>
          <span className="mono" title="sha256 of the species dataset file">
            hash {d.dataset_file_hash ?? 'Data Unavailable'}
          </span>
          <span>
            {d.counts.species} species · {d.counts.legal_points} planting-zone grid points
          </span>
        </>
      ) : (
        <span>{health.status === 'loading' ? 'Loading dataset version…' : 'Dataset version unavailable (the planning service is not reachable).'}</span>
      )}
      <span>Draft data: weights and soil map are provisional.</span>
    </footer>
  )
}
