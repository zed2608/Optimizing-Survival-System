import test from 'node:test'
import assert from 'node:assert/strict'
import { toCsv } from './csv.js'

test('toCsv quotes commas, quotes and line breaks, and defuses spreadsheet formulas', () => {
  const rows = [{ a: 'Maly', n: 3 }, { a: 'Santa Ana, Rizal', n: 4 }, { a: 'say "hi"', n: 5 }, { a: '=SUM(A1)', n: -2 }, { a: null, n: 0 }]
  const out = toCsv(rows, [{ key: 'a', label: 'Barangay' }, { key: 'n', label: 'Squares' }, { label: 'Double', get: (r) => r.n * 2 }])
  assert.equal(out.split('\r\n')[0], 'Barangay,Squares,Double')
  assert.ok(out.includes('"Santa Ana, Rizal",4,8'))
  assert.ok(out.includes('"say ""hi""",5,10'))
  assert.ok(out.includes("'=SUM(A1),-2,-4"))
  assert.ok(out.includes(',0,0'))
  assert.ok(out.endsWith('\r\n'))
})
