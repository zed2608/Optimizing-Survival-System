import { useId } from 'react'
import Icon from './Icon.jsx'
import { dayAdvice, dayCondition, hourInPhilippines, rainBarPct, timeOfDay } from './weatherView.js'
import { tr, useLang } from './i18n.js'

// The animated weather art of the Weather view, drawn in SVG and CSS (no image, no library). Only what the forecast carries is drawn: clear sky, cloud, rain, heavy rain. Wind, thunder and humidity are
// not in the forecast, so they are never drawn. Motion is decorative and is switched off by prefers-reduced-motion (canopy.css).
export function WxIcon({ kind, size = 40 }) {
  return (
    <svg className={`wx-icon wx-icon-${kind}`} viewBox="0 0 48 48" width={size} height={size} aria-hidden="true">
      {kind === 'clear' && (
        <g className="wx-sun">
          <circle cx="24" cy="24" r="8" className="wx-sun-core" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <line key={a} x1="24" y1="8" x2="24" y2="12" transform={`rotate(${a} 24 24)`} className="wx-ray" />
          ))}
        </g>
      )}
      {kind !== 'clear' && kind !== 'none' && (
        <>
          <g className="wx-cloud-drift">
            <path d="M14 32h20a7 7 0 0 0 1-13.9A9 9 0 0 0 17.5 17 7.5 7.5 0 0 0 14 32z" className="wx-cloud" />
          </g>
          {[16, 24, 32].map((x, i) => (kind === 'light' || kind === 'rainy' || kind === 'heavy') && <line key={x} x1={x} y1="36" x2={x - 2} y2="43" className="wx-drop" style={{ animationDelay: `${i * 0.25}s` }} />)}
        </>
      )}
      {kind === 'none' && <path d="M24 14v12M24 32v.01" className="wx-unknown" />}
    </svg>
  )
}

// The hero of the week: the sky of the first day, drawn for the real time of day in San Mateo, with rain falling when the forecast says rain.
export default function WeatherHero({ day, heavy, dateLabel, habagat }) {
  const lang = useLang()
  const t = (k, p) => tr(k, p, lang)
  const id = useId()
  const cond = dayCondition(day.rain_mm, heavy)
  const phase = timeOfDay(hourInPhilippines())
  const drops = cond === 'heavy' ? 34 : cond === 'rainy' ? 22 : cond === 'light' ? 10 : 0
  const stars = phase === 'night' && cond === 'clear'
  return (
    <section className={`wx-hero wx-sky-${phase} wx-cond-${cond}`} aria-label={t('wx.heroLabel')} data-role="wx-hero" data-tour="w-hero" data-cond={cond} data-phase={phase}>
      <svg className="wx-scene" viewBox="0 0 600 200" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
        {stars && [40, 120, 210, 300, 380, 470, 540].map((x, i) => <circle key={x} cx={x} cy={20 + ((i * 37) % 70)} r="1.6" className="wx-star" style={{ animationDelay: `${i * 0.4}s` }} />)}
        {cond === 'clear' && (phase === 'day' || phase === 'dawn' || phase === 'dusk') && (
          <g className="wx-big-sun" transform={`translate(${phase === 'day' ? 470 : 520} ${phase === 'day' ? 62 : 120})`}>
            <circle r="26" className="wx-sun-core" />
            {Array.from({ length: 12 }, (_, i) => <line key={i} x1="0" y1="-34" x2="0" y2="-44" transform={`rotate(${i * 30})`} className="wx-ray" />)}
          </g>
        )}
        {cond === 'clear' && phase === 'night' && <path d="M470 40a24 24 0 1 0 22 34 20 20 0 0 1-22-34z" className="wx-moon" />}
        {cond !== 'clear' && cond !== 'none' && (
          <>
            <g className="wx-cloud-drift wx-c1"><path d="M60 110h150a34 34 0 0 0 6-67 44 44 0 0 0-84-8 36 36 0 0 0-72 75z" className="wx-cloud" transform="translate(330 14) scale(0.55)" /></g>
            <g className="wx-cloud-drift wx-c2"><path d="M60 110h150a34 34 0 0 0 6-67 44 44 0 0 0-84-8 36 36 0 0 0-72 75z" className="wx-cloud" transform="translate(450 64) scale(0.42)" /></g>
          </>
        )}
        {Array.from({ length: drops }, (_, i) => {
          const x = 24 + ((i * 577) % 560)
          return <line key={i} x1={x} y1="90" x2={x - 8} y2="116" className="wx-rain" style={{ animationDelay: `${(i % 9) * 0.12}s`, animationDuration: `${0.7 + (i % 4) * 0.12}s` }} />
        })}
        <path d="M0 200V150L60 120 120 146 190 108 260 142 330 112 410 148 480 124 560 150 600 136V200z" className="wx-hill-back" />
        <path d="M0 200V170L80 150 170 172 260 152 360 174 460 156 540 172 600 160V200z" className="wx-hill-front" />
      </svg>
      <div className="wx-hero-body">
        <div className="wx-hero-where">{dateLabel}</div>
        <div className="wx-hero-main">
          <WxIcon kind={cond} size={56} />
          <div>
            <div className="wx-hero-word" data-role="wx-word">{t(`wx.cond.${cond}`)}</div>
            <div className="wx-hero-sub">
              {day.tmin_c === null || day.tmax_c === null ? t('wx.noTemp') : `${Math.round(day.tmin_c)}–${Math.round(day.tmax_c)} °C`} ·{' '}
              {day.rain_mm === null || day.rain_mm === undefined ? t('wx.noRain') : t('wx.rainMm', { mm: day.rain_mm })}
            </div>
          </div>
        </div>
        <div className="wx-hero-advice" id={id} data-role="wx-hero-advice">
          <Icon name={dayAdvice(day.rain_mm, heavy) === 'postpone' ? 'warn' : 'check'} size={16} /> {t(`wx.adv.${dayAdvice(day.rain_mm, heavy)}`)}
        </div>
        {habagat?.active && (
          <div className="wx-habagat" role="note" data-role="habagat">
            <Icon name="rain" size={16} />{' '}
            <span>
              {t('wx.habagat', { months: habagat.month_names.join('–'), places: habagat.barangays.join(', ') })} <span className="wx-prov">{t('wx.provisional')}</span>
            </span>
          </div>
        )}
      </div>
    </section>
  )
}

// The seven days as a strip: animated icon, rain amount as a bar (an amount in mm, NOT a chance of rain: the forecast has no chance), temperatures and one advice line per day.
export function WeekStrip({ days, heavy, weekday, dayLabel }) {
  const lang = useLang()
  const t = (k, p) => tr(k, p, lang)
  const weekMax = Math.max(0, ...days.map((d) => d.rain_mm ?? 0))
  return (
    <ol className="wx-strip" aria-label={t('wx.stripLabel')} data-role="wx-strip" data-tour="w-strip">
      {days.map((x) => {
        const c = dayCondition(x.rain_mm, heavy)
        const adv = dayAdvice(x.rain_mm, heavy)
        return (
          <li key={x.date} className={`wx-day wx-adv-${adv}`} data-cond={c}>
            <div className="wx-day-date">
              <strong>{weekday(x.date)}</strong> {dayLabel(x.date)}
            </div>
            <WxIcon kind={c} size={40} />
            <div className="wx-day-word">{t(`wx.cond.${c}`)}</div>
            <div className="wx-bar" role="img" aria-label={x.rain_mm === null || x.rain_mm === undefined ? t('wx.noRain') : t('wx.rainMm', { mm: x.rain_mm })}>
              <span style={{ width: `${rainBarPct(x.rain_mm, weekMax)}%` }} />
            </div>
            <div className="wx-day-nums">
              {x.rain_mm === null || x.rain_mm === undefined ? t('wx.noRain') : t('wx.rainMm', { mm: x.rain_mm })}
              <br />
              {x.tmin_c === null || x.tmax_c === null ? t('wx.noTemp') : `${Math.round(x.tmin_c)}–${Math.round(x.tmax_c)} °C`}
            </div>
            <div className="wx-day-advice">{t(`wx.adv.${adv}`)}</div>
          </li>
        )
      })}
    </ol>
  )
}

// The rules behind the day words and the advice, always visible, so that nobody has to guess where a line comes from.
export function WeatherRules({ heavy }) {
  const lang = useLang()
  return (
    <p className="muted wx-rules" data-role="wx-rules" data-tour="w-rules">
      {tr('wx.rules', { heavy }, lang)}
    </p>
  )
}
