// A small "Provisional" label for anything that comes from an interview or from a rule that the agriculturist has not confirmed yet.
export default function ProvisionalTag({ title = 'From an interview or a starting rule: to be confirmed' }) {
  return (
    <span className="nw-prov" title={title}>
      Provisional
    </span>
  )
}
