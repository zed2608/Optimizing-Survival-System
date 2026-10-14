import qrcode from '../vendor/qrcode-generator-1.4.4/qrcode.esm.js'

// The QR code of the planter link, as plain SVG data (no innerHTML, no network, no CDN): the module matrix of the vendored qrcode-generator, drawn as ONE path.
// Error correction "M" (about 15% can be damaged); the quiet zone is 4 modules, as the QR standard asks. A link of this kind (about 60 characters) fits in version 4 or less.
export const QUIET = 4

export function qrMatrix(text) {
  const qr = qrcode(0, 'M') // 0 = the smallest version that fits
  qr.addData(String(text), 'Byte')
  qr.make()
  const n = qr.getModuleCount()
  const rows = []
  for (let r = 0; r < n; r += 1) {
    const row = []
    for (let c = 0; c < n; c += 1) row.push(qr.isDark(r, c))
    rows.push(row)
  }
  return rows
}

// { size, viewBox, d }: d is one path of 1 x 1 squares ("M x y h1 v1 h-1 z"), x and y already moved by the quiet zone.
export function qrSvg(text) {
  const rows = qrMatrix(text)
  const size = rows.length + 2 * QUIET
  const parts = []
  rows.forEach((row, r) => row.forEach((dark, c) => { if (dark) parts.push(`M${c + QUIET} ${r + QUIET}h1v1h-1z`) }))
  return { size, viewBox: `0 0 ${size} ${size}`, d: parts.join('') }
}
