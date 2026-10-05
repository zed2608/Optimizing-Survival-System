// Dataset version tag and hash (from GET /health), in the dark sidebar style.
export default function DatasetNote({ health }) {
  const d = health.status === 'ok' ? health.data : null
  return (
    <p className="nw-hint nw-dataset">
      {d ? (
        <>
          Dataset version <strong>{d.dataset_version ?? 'Data Unavailable'}</strong>
          <br />
          <span className="nw-mono" title="sha256 of the species dataset file">
            hash {d.dataset_file_hash ?? 'Data Unavailable'}
          </span>
          <br />
          Draft data: weights and soil map are provisional.
        </>
      ) : (
        'Dataset version unavailable (the planning service is not reachable).'
      )}
    </p>
  )
}
