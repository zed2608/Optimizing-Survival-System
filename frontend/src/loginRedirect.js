// With the shared access code on (OS_ACCESS_CODE), the service answers 401 with the header X-Login-Required when the login cookie is missing or has expired.
// One wrapper around fetch sends the person back to the login page, so no single call has to handle it. Without the access code nothing ever sends that header.
const original = window.fetch.bind(window)
window.fetch = async (...args) => {
  const res = await original(...args)
  if (res.status === 401 && res.headers.get('X-Login-Required')) window.location.assign('/login')
  return res
}
