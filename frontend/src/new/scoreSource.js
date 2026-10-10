// The service fell back from the Random Forest scores to the expert rules: the saved scores have no complete s_prob (GET /health: s_source "rules", s_source_requested "rf").
export function isFallback(health) {
  return !!health && health.s_source === 'rules' && health.s_source_requested === 'rf'
}
