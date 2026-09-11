## 2026-09-11 - React 4Hz Re-render Optimization
**Learning:** Found that a 4Hz SSE stream in `App.tsx` was causing heavy sub-components (`NotesVaultPanel`, `BriefingModal`, `ActiveTimersBar`, `StatusBar`) to re-render constantly, consuming unnecessary CPU.
**Action:** Used `React.memo()` and `useCallback()` to decouple these heavy subviews from the high-frequency parent state changes.
