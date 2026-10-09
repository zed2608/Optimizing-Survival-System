// The search of the Help page: every word typed must appear in the question, the answer, the topic or the hidden search words of an answer.
export function matchFaq(faq, query) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return true
  const hay = `${faq.q} ${faq.a} ${faq.words ?? ''} ${faq.topic}`.toLowerCase()
  return words.every((w) => hay.includes(w))
}
