// Applies the persisted theme before first paint to avoid a flash of the
// wrong color scheme. Lives as an external file (not inline in index.html)
// so the backend's Content-Security-Policy can stay `script-src 'self'`.
;(() => {
  try {
    const raw = localStorage.getItem('ui-store')
    if (!raw) return
    const data = JSON.parse(raw)
    const theme = data?.state?.theme
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
      document.documentElement.style.colorScheme = 'dark'
    } else if (theme === 'light') {
      document.documentElement.classList.remove('dark')
      document.documentElement.style.colorScheme = 'light'
    }
  } catch {}
})()
