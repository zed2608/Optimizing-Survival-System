/*
 * Adapted from the SpotlightCard idea of React Bits (David Haz, https://github.com/DavidHDev/react-bits, MIT with Commons Clause). Rewritten for this project (plain CSS variables, no dependency);
 * the licence header is kept as the author asks. The glow follows the pointer and is only decoration.
 */
export default function SpotlightCard({ children, className = '', ...rest }) {
  const move = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
    e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
  }
  return (
    <div className={`cy-spot ${className}`} onMouseMove={move} {...rest}>
      {children}
    </div>
  )
}
