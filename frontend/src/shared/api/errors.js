/** Turns an RTK Query error into { formError, fieldErrors } from DRF's response shape. */
export function parseApiError(error) {
  if (!error) return { formError: null, fieldErrors: {} }

  if (error.status === 'FETCH_ERROR') {
    return { formError: 'Cannot reach the API. Is the Django server running?', fieldErrors: {} }
  }

  const data = error.data
  if (typeof data === 'string') return { formError: data, fieldErrors: {} }
  if (!data || typeof data !== 'object') {
    return { formError: 'Something went wrong. Please try again.', fieldErrors: {} }
  }

  const fieldErrors = {}
  let formError = null
  for (const [key, value] of Object.entries(data)) {
    const message = Array.isArray(value) ? value.join(' ') : String(value)
    if (key === 'detail' || key === 'non_field_errors') formError = message
    else fieldErrors[key] = message
  }
  if (!formError && Object.keys(fieldErrors).length === 0) {
    formError = 'Something went wrong. Please try again.'
  }
  return { formError, fieldErrors }
}
