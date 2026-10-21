// Client-side CSV of one chart's rows (nothing is sent anywhere). Values are quoted when they hold a comma, a quote or a line break; a value that starts with = + - @ is prefixed with an apostrophe so that a
// spreadsheet does not read it as a formula.
const cell = (v) => {
  let t = v === null || v === undefined ? '' : String(v)
  if (/^[=+\-@]/.test(t) && Number.isNaN(Number(t))) t = `'${t}`
  return /[",\n\r]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t
}

export function toCsv(rows, columns) {
  const head = columns.map((c) => cell(c.label)).join(',')
  const body = rows.map((r) => columns.map((c) => cell(typeof c.get === 'function' ? c.get(r) : r[c.key])).join(','))
  return [head, ...body].join('\r\n') + '\r\n'
}

export function downloadCsv(name, text) {
  try {
    const url = URL.createObjectURL(new Blob(['﻿', text], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = name.endsWith('.csv') ? name : `${name}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    return true
  } catch {
    return false
  }
}
