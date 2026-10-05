import { useState } from 'react'
import './v2.css'
import Footer from './components/Footer.jsx'
import LimitsBox from './components/LimitsBox.jsx'
import LocationForm from './components/LocationForm.jsx'
import MapView from './components/MapView.jsx'
import MunicipalTab from './components/MunicipalTab.jsx'
import RankingPanel from './components/RankingPanel.jsx'
import Tabs from './components/Tabs.jsx'
import { ErrorBox } from './components/Status.jsx'
import { RANK_LIMIT } from './config.js'
import { PURPOSES } from './labels.js'
import { useApi } from './useApi.js'

const TABS = [
  { id: 'spot', label: 'Rank species at a spot' },
  { id: 'municipal', label: 'Whole municipality' },
]

// The new dashboard (open it with #/v2 at the end of the address). Part A: ranking and explanations.
export default function App2() {
  const [purpose, setPurpose] = useState('urban')
  const [tab, setTab] = useState('spot')
  const [spot, setSpot] = useState(null) // { lat, lon } chosen by a click, the form, or "go to this spot"
  const [viableFor, setViableFor] = useState(null) // the spot + purpose for which the nearest suitable spot was asked
  const [flyTarget, setFlyTarget] = useState(null)
  const [limitsOpen, setLimitsOpen] = useState(false)

  const health = useApi('/health')
  const spotQuery = spot ? `purpose=${purpose}&lat=${spot.lat.toFixed(6)}&lon=${spot.lon.toFixed(6)}` : null
  const rank = useApi(spotQuery ? `/rank?${spotQuery}&limit=${RANK_LIMIT}` : null)
  const viable = useApi(spotQuery && viableFor === spotQuery ? `/nearest-viable?${spotQuery}` : null)

  const pick = (lat, lon) => {
    setSpot({ lat, lon })
    setTab('spot')
  }
  const goTo = (lat, lon) => {
    setSpot({ lat, lon })
    setFlyTarget({ lat, lon })
  }
  const grid = rank.status === 'ok' ? rank.data.point : null
  const suggested = viable.status === 'ok' && !viable.data.already_viable ? viable.data.point : null
  const purposeInfo = PURPOSES.find((p) => p.value === purpose)

  return (
    <div className="v2">
      <a className="skip-link" href="#v2-main">
        Skip to the main content
      </a>
      <header className="v2-header">
        <div className="v2-title-row">
          <h1>Which trees where? San Mateo planting guide</h1>
          <div className="v2-header-actions">
            <button type="button" className="btn btn-secondary" aria-expanded={limitsOpen} aria-controls="limits-panel" onClick={() => setLimitsOpen((o) => !o)}>
              {limitsOpen ? 'Hide known limits' : 'Known limits'}
            </button>
            <a className="btn btn-secondary" href="#/">
              Earlier dashboard
            </a>
          </div>
        </div>
        <fieldset className="purpose">
          <legend>What is the planting for?</legend>
          {PURPOSES.map((p) => (
            <label key={p.value} className={`purpose-option ${purpose === p.value ? 'is-selected' : ''}`}>
              <input type="radio" name="purpose" value={p.value} checked={purpose === p.value} onChange={() => setPurpose(p.value)} />
              <span>
                <strong>{p.label}</strong>
              </span>
            </label>
          ))}
          <p className="muted purpose-help">{purposeInfo.help}</p>
        </fieldset>
        <Tabs tabs={TABS} value={tab} onChange={setTab} label="Choose a view" />
      </header>
      <LimitsBox health={health} open={limitsOpen} />
      {health.status === 'error' && health.error.network && (
        <div className="v2-banner">
          <ErrorBox error={health.error} onRetry={health.retry} />
        </div>
      )}

      <main id="v2-main" className="v2-main">
        <section id="tabpanel-spot" role="tabpanel" aria-labelledby="tab-spot" className={`spot-view ${tab === 'spot' ? '' : 'is-hidden'}`}>
          <div className="map-col">
            <MapView spot={spot} grid={grid} viable={suggested} onPick={pick} visible={tab === 'spot'} flyTarget={flyTarget} />
          </div>
          <aside className="side-col" aria-label="Ranking of species for the chosen spot">
            <LocationForm key={spot ? `${spot.lat}|${spot.lon}` : 'none'} initial={spot} onSubmit={goTo} />
            <div aria-live="polite">
              <RankingPanel
                key={`${purpose}|${spot ? `${spot.lat}|${spot.lon}` : 'none'}`}
                rank={rank}
                purpose={purpose}
                viable={viable}
                onFindViable={() => setViableFor(spotQuery)}
                onGo={goTo}
              />
            </div>
          </aside>
        </section>
        <section id="tabpanel-municipal" role="tabpanel" aria-labelledby="tab-municipal" className={`municipal-view ${tab === 'municipal' ? '' : 'is-hidden'}`}>
          {tab === 'municipal' && <MunicipalTab purpose={purpose} />}
        </section>
      </main>
      <Footer health={health} />
    </div>
  )
}
