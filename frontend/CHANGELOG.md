# UI/UX & Frontend Changelog

This document tracks the recent major UI/UX overhauls applied to the Miracle AI frontend.

## Latest Updates (Current Session)

### 0. Blank Discount Ledger & Payloaded Auto-Backup Path
- **Blank Discount Ledger**: Changed the discount ledger code from dynamic `DISCOUNT A/C` to `""` (empty string) in both the header charges and item details database tables, matching native Miracle behavior and keeping the ledger box completely blank. This fixes the incorrect bill totals (e.g. 4,125 instead of 4,860) by preventing Miracle from posting the discount to a separate ledger.
- **Payloaded Auto-Backup Path**: Added the `backup_path` field to the frontend payloads (`pushPayload` and opening balance payload) and backend HTTP models (`PushPayload` and `OpeningBalancePushPayload`). This allows the push action to dynamically read the current state of the inline `Auto-Backup Path` box in the UI, correctly disabling backups when the box is empty and running them only when configured.

### 1. Visual Polish & Color Bug Fixes
- **Opaque Modal Backgrounds**: Defined `.bg-darkcard` style explicitly to use a premium, solid `#0d1321` color with `#1b2536` borders. This prevents background page elements (such as document viewer bouncing icons) from bleeding through transparent settings and audit modals.
- **Active Navigation Highlights**: Fixed a bug where switching sidebar modules broke link highlighting due to undefined `bg-primary/10` and `text-primary` classes. Replaced with proper brand color classes (`bg-brand-600/10`, `text-brand-500`, `border-brand-500/30`, `border-l-4`, `border-l-brand-500`) to ensure tactile visual feedback.
- **Tailwind Color Palette Extension**: Configured custom `slate` palette extension inside `tailwind.config` to define `slate-850` (#151e2e) and `slate-950` (#090d16). This fixes all missing border borders across grids, panels, and input elements.
- **Color Accent Fixes**: Replaced undefined `text-accent` classes in `app.js` and `index.html` with valid `text-brand-500` or `text-emerald-500` classes to restore rich color indicators for Mapped statuses and Grand Totals.
- **Vertical Directory Paths Layout**: Redesigned the three directory path input blocks inside the Configure Settings modal to lay out vertically with (1, 2, 3) numbering. This makes each path input field occupy the full width of the container, preventing truncation of long paths (like `/Users/...`) and making them completely readable.
- **Restored Opening Balance & Batch Date Visibility**: Fixed a bug where the "Opening Bal:" and "Set Date" boxes would only appear *after* a document was processed, preventing users from setting them beforehand. Linked their visibility directly to the sidebar module selection so they show up immediately on clicking "Bank Statements" or "Cash Entries".
- **Interactive Column Header Sorting**: Added ascending/descending column header sorting (`Date`, `Bill No`, `Party Name`, `Qty`, `Taxable`, `GST`, `Total`, `Reference No`, `Withdrawal`, `Deposit`, `Balance`, `Ledger Name`) with interactive sort direction arrows (`fa-sort`, `fa-sort-up`, `fa-sort-down`). Manual input edits are automatically saved before sorting so user changes are preserved.
- **Editable Quantity (Qty) Column**: Added an editable "Qty" column right after Party Name in Sales and Purchases grids. Quantities are populated automatically from AI extractions (or default to 1) and feed directly into Miracle DBF file generation.

### 1. Typography & Readability Standardization
- **Problem**: Original font sizes were too small (`text-[9px]`, `text-[10px]`, `text-xs`), making the dashboard hard to read.
- **Solution**: Systematically replaced micro-text with `text-sm` (14px) and `text-base` (16px) across `index.html` and `app.js`. Scaled up header titles to `text-lg` to establish a clearer typographic hierarchy.

### 2. Spacing & Fitts's Law Implementations
- **Header Padding**: Increased main header height from `h-16` to `h-20` for a more spacious, less cluttered feel.
- **Modal Breathing Room**: Expanded inner padding of all modals from `p-6` to `p-8`.
- **Button Sizing**: Ensured all primary touch targets (buttons/inputs) have sufficient padding (minimum 44px equivalent height).

### 3. Tactile Micro-Interactions (Hover & Active States)
- **Buttons**: Injected `transform transition-all duration-200 hover:-translate-y-0.5 active:scale-95 shadow-md` into all buttons. This creates a tactile, responsive feel when hovering and clicking.
- **Inputs**: Upgraded focus states across all inputs and selects to use a glowing ring (`focus:ring-2 focus:ring-brand-500/50 focus:ring-offset-2 focus:ring-offset-obsidian-950`) instead of a basic border change, drastically improving keyboard navigation accessibility.

### 4. Dynamic Animations & Visual Cues
- **Table Row Entry**: Added an `@keyframes fadeInUp` animation to `index.html`. In `app.js`, dynamically generated `<tr>` elements now receive the `animate-fade-in-up` class so new data slides smoothly into view.
- **Validation Errors**: Created an `@keyframes errorShake` animation. When mapping validation fails, the input border turns red and literally shakes (`error-shake` class), drawing the user's eye immediately.
- **Empty States**: Redesigned the "Document Viewer" empty state from a static icon to a glowing, hovering drop-zone with a bouncing upload icon.

### 5. Layout Controls (Document Viewer Resizer & Toggle)
- **Toggle Button**: Added a header button (`#toggleDocViewerBtn`) to completely hide/show the right-side document viewer panel.
- **Draggable Resizer**: Implemented a vertical drag handle (`#panelResizer`) between the data grid and the document viewer. Added mouse event listeners (`mousedown`, `mousemove`, `mouseup`) in `app.js` to allow fluid, real-time resizing of the document panel between 250px and 800px.
