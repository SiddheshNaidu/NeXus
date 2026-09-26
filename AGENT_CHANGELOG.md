# NEXUS AGENT CHANGELOG

## [Phase 03] - Closeout
### Fixed
- Updated `layout.tsx` body class to use `bg-[#050505]` instead of `bg-zinc-950` to resolve hydration color-flashing and adhere strictly to the dark mode palette token.
- Implemented a mobile-only "Return to Answer" top navigation bar for `EvidenceViewer` (hidden above `lg` breakpoint) for responsive UX parity.
- Appended `aria-label="Upload document - click or drag and drop a file"` to the upload Dropzone button for screen reader accessibility compliance.
