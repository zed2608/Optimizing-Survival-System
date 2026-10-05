// Dataset version tag and hash (from GET /health), in the dark sidebar style (inside the "More" menu).
export default function DatasetNote({ health }) {
  const d = health.status === 'ok' ? health.data : null
  return (
    <p className="nw-hint nw-dataset">
      {d ? (
        <>
          Version <strong>{d.dataset_version ?? 'Data Unavailable'}</strong>
          <br />
          <span className="nw-mono" title="sha256 of the species dataset file">
            hash {d.dataset_file_hash ?? 'Data Unavailable'}
          </span>
          <br />
          Draft data: weights are provisional.
        </>
      ) : (
        'Version unavailable (the service is not reachable).'
      )}
    </p>
  )
}
