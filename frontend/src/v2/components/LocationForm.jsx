import { useState } from 'react'
import { EXAMPLE_SPOT } from '../config.js'

// Type coordinates instead of clicking the map (works with the keyboard). It is re-created whenever the chosen spot changes,
// so the boxes always show the spot that is being ranked.
export default function LocationForm({ initial, onSubmit }) {
  const [lat, setLat] = useState(initial ? initial.lat.toFixed(5) : '')
  const [lon, setLon] = useState(initial ? initial.lon.toFixed(5) : '')
  const [problem, setProblem] = useState('')

  function submit(e) {
    e.preventDefault()
    const la = Number(lat)
    const lo = Number(lon)
    if (lat.trim() === '' || lon.trim() === '' || Number.isNaN(la) || Number.isNaN(lo) || la < -90 || la > 90 || lo < -180 || lo > 180) {
      setProblem('Please type the latitude (for example 14.69) and the longitude (for example 121.12) as numbers.')
      return
    }
    setProblem('')
    onSubmit(la, lo)
  }

  function useExample() {
    setLat(String(EXAMPLE_SPOT.lat))
    setLon(String(EXAMPLE_SPOT.lon))
    setProblem('')
    onSubmit(EXAMPLE_SPOT.lat, EXAMPLE_SPOT.lon)
  }

  return (
    <form className="locform" onSubmit={submit} noValidate>
      <div className="locform-fields">
        <label>
          Latitude
          <input type="text" inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="14.69" aria-describedby="loc-problem" />
        </label>
        <label>
          Longitude
          <input type="text" inputMode="decimal" value={lon} onChange={(e) => setLon(e.target.value)} placeholder="121.12" aria-describedby="loc-problem" />
        </label>
        <button type="submit" className="btn">
          Check this spot
        </button>
        <button type="button" className="btn btn-secondary" onClick={useExample}>
          Use an example spot
        </button>
      </div>
      <p id="loc-problem" className="form-problem" role="alert">
        {problem}
      </p>
    </form>
  )
}
