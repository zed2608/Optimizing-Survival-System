import Icon from './Icon.jsx'

const GROUND_HINT = {
  ground_bare: 'Satellite land cover also looks bare here.',
  ground_built_up: 'Satellite land cover also looks built-up here.',
  ground_water: 'Satellite land cover also looks like water or wetland here.',
}

// "Why few or no species suit this square": the hard limits that rule species out (zone, elevation, slope, soil), in plain words with the numbers, from GET /rank limiting_factors.
// Shown when fewer than 3 species suit the square, and in the Full details view.
export default function WhyNone({ lf, ground }) {
  const few = lf.shown_because === 'fewer_than_3_species_suit'
  const hints = ground?.available ? ground.flags.map((f) => GROUND_HINT[f]).filter(Boolean) : []
  return (
    <section className="nw-pcard nw-whynone" aria-label="Why few or no species suit this square">
      <div className="nw-pcard-head">
        <h3>{few ? 'Why few or no species suit this square' : 'What limits the species here'}</h3>
      </div>
      <p className="nw-count-line">
        {lf.n_suitable} of {lf.n_species} species suit this square.
      </p>
      {lf.messages.length > 0 ? (
        <ul className="nw-warnlist">
          {lf.messages.map((m) => (
            <li key={m}>
              <Icon name="warn" size={14} /> {m}
            </li>
          ))}
        </ul>
      ) : (
        <p className="nw-plain">No hard limit rules species out here.</p>
      )}
      {hints.map((h) => (
        <p key={h} className="nw-plain nw-whynone-hint">
          <Icon name="mountain" size={14} /> {h}
        </p>
      ))}
    </section>
  )
}
