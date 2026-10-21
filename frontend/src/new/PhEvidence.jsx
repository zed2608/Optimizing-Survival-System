import { useId, useState } from 'react'
import SourceLink from '../v2/components/SourceLink.jsx'
import { COMPARE_TEXT, PH_TEXT, compareMeasured, parsePhInput, phRowFromRef } from './phEvidence.js'

const firstUrl = (s) => (typeof s === 'string' ? (s.match(/https?:\/\/[^\s,]+/) ?? [null])[0] : null)

function Two({ t }) {
  return (
    <>
      {t.en}
      <span className="nw-fil">{t.fil}</span>
    </>
  )
}

// "Sukat sa lugar": the pH the researcher measured on the spot against the evidence range. Client side only: nothing is saved, nothing is sent.
export function PhMeasureTool({ reference }) {
  const id = useId()
  const [text, setText] = useState('')
  const typed = text.trim() !== ''
  const value = parsePhInput(text)
  const code = value === null ? null : compareMeasured(value, reference)
  return (
    <div className="nw-ph-tool" data-role="ph-tool">
      <label htmlFor={id}>
        <strong>
          <Two t={PH_TEXT.toolTitle} />
        </strong>
      </label>
      <div className="nw-ph-tool-row">
        <input
          id={id}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-label={PH_TEXT.toolLabel.fil}
          placeholder="6.5"
          aria-describedby={`${id}-note`}
        />
        <button type="button" className="btn btn-small" onClick={() => setText('')} disabled={!typed}>
          {PH_TEXT.toolReset.fil}
        </button>
      </div>
      <div className="muted" id={`${id}-note`}>
        <Two t={PH_TEXT.toolNote} />
      </div>
      {typed && value === null && (
        <div className="nw-ph-tool-bad" role="alert">
          <Two t={PH_TEXT.toolBad} />
        </div>
      )}
      {code && (
        <div className={`nw-climate-verdict is-ph-${code}`} data-role="ph-tool-result" data-result={code} role="status">
          <Two t={COMPARE_TEXT[code]} />
        </div>
      )}
    </div>
  )
}

// The "Soil pH" row of the Species card, from the evidence file (ph_reference). With a range: tolerated / best / listed, the kind of range, the real source link with its rank badge,
// and the tag "from a source, not yet signed by the agriculturist". Without one: "No confirmed pH range", the instruction, and NO link and NO rank.
export default function PhEvidence({ reference }) {
  const row = phRowFromRef(reference)
  return (
    <div className="nw-fact" data-row="ph-evidence">
      <dt>
        <Two t={{ en: 'Soil pH', fil: 'pH ng lupa' }} />
      </dt>
      <dd>
        {row.none ? (
          <>
            <span className="unavailable" data-role="ph-none">
              <Two t={row.text} />
            </span>
            <div className="muted" data-role="ph-none-help">
              <Two t={row.help} />
            </div>
          </>
        ) : (
          <>
            {row.summary && (
              <p className="nw-plain" data-role="ph-summary">
                <Two t={row.summary} />
              </p>
            )}
            {row.other && (
              <p className="muted" data-role="ph-other">
                <Two t={row.other.text} />
              </p>
            )}
            <ul className="plain-list nw-ph-lines" hidden={!!row.summary}>
              {row.lines.map((l) => (
                <li key={l.key} data-ph-line={l.key}>
                  <strong>
                    {l.label.en}: {l.range}
                  </strong>
                  <span className="nw-fil">
                    {l.label.fil}: {l.range}
                  </span>
                </li>
              ))}
            </ul>
            {row.kind && (
              <div className="muted" data-role="ph-kind">
                <Two t={row.kind} />
              </div>
            )}
            {row.group && (
              <div className="muted" data-role="ph-group">
                <Two t={PH_TEXT.group} />
              </div>
            )}
            <span className="nw-draft" data-role="ph-tag">
              <Two t={row.tag} />
            </span>
            {row.conflict && (
              <div className="nw-ph-conflict" data-role="ph-conflict" role="note">
                <Two t={PH_TEXT.conflict} />
              </div>
            )}
            <div className="nw-fact-src" data-role="ph-source">
              {row.dataset ? firstUrl(row.source.url) && <a href={firstUrl(row.source.url)} target="_blank" rel="noopener noreferrer">{row.source.name ?? firstUrl(row.source.url)}</a> : <SourceLink source={{ url: row.source.url, rank: row.source.rank }} />}
            </div>
          </>
        )}
        <PhMeasureTool reference={reference} />
      </dd>
    </div>
  )
}
