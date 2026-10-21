// Words for "there is no weather now" (C3). Pure function, tested in weatherText.test.mjs.
// When the forecast cannot be had (our service is not reachable, or it answered 5xx because Open-Meteo could not be reached and there is no saved copy) the person reads ONE plain Filipino sentence,
// and the technical reason stays under it, so nothing is hidden. Other errors (for example 422: the place is outside San Mateo) keep the service's own message: they are not "unreachable".
import { getLang, tr } from './i18n.js'

export function weatherError(error, lang = getLang()) {
  const WEATHER_UNREACHABLE = tr('wx.unreachable', {}, lang)
  const network = !!(error && error.network)
  const status = error && typeof error.status === 'number' ? error.status : null
  const message = error && error.message ? String(error.message) : ''
  if (network) return { unreachable: true, main: WEATHER_UNREACHABLE, detail: 'The planning service could not be reached, so there is no forecast now.' }
  if (status !== null && status >= 500) return { unreachable: true, main: WEATHER_UNREACHABLE, detail: message }
  return { unreachable: false, main: message || WEATHER_UNREACHABLE, detail: '' }
}
