// Dataset release tag and hash (from GET /health), in the dark sidebar style (inside the "More" menu).
// hash = the combined 12-character hash of the two raw files; the title holds both full sha256 values.
export default function DatasetNote({ health }) {
  const d = health.status === 'ok' ? health.data : null
  return (
    <p className="nw-hint nw-dataset">
      {d ? (
        <>
          Version <strong>{d.dataset_version ?? 'Data Unavailable'}</strong>
          <br />
          <span className="nw-mono" title={`species file sha256 ${d.dataset_species_file_sha256 ?? d.dataset_file_hash ?? 'Data Unavailable'} · sources file sha256 ${d.dataset_sources_file_sha256 ?? 'Data Unavailable'}`}>
            hash {d.dataset_hash ?? d.dataset_file_hash ?? 'Data Unavailable'}
          </span>
          <br />
          {String(d.dataset_note ?? '').startsWith('frozen') ? 'Frozen for review' : 'Draft data'}; weights and soil are provisional.
        </>
      ) : (
        'Version unavailable (the service is not reachable).'
      )}
    </p>
  )
}
