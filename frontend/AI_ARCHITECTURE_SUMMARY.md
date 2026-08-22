# Miracle AI Frontend - Architecture & Context

> [!IMPORTANT]
> **For AI Assistants:** Read this document first to understand the application structure without having to reverse-engineer `index.html` and `app.js` from scratch.

## 1. Application Overview
Miracle AI is a single-page application (SPA) designed as an "Auto-Entry Platform" for accounting. It processes Sales Vouchers, Purchase Vouchers, Bank Statements, and Cash Entries. 

## 2. Core Technologies
- **HTML5**: Standard markup structure.
- **Tailwind CSS (via CDN)**: All styling is utility-first. Custom colors (brand, obsidian, emerald) are configured in a `<script>` tag at the top of `index.html`.
- **Vanilla JavaScript (`app.js`)**: Handles all DOM manipulation, API fetching, and dynamic HTML injection. No frameworks (React/Vue) are used.
- **FontAwesome**: Used for all iconography.

## 3. UI Layout (`index.html`)
The layout relies heavily on flexbox and CSS Grid.
- **Sidebar (`<aside>`)**: Contains the logo, active client/year selectors, main navigation links (Sales, Purchases, etc.), and action buttons (Auto-Learn, Settings).
- **Header (`<header>`)**: Contains the dynamic Module Title, Batch Date selectors, and utility buttons (like the Document Viewer toggle).
- **Main Workspace (`<main>`)**:
  - **Left Panel**: Contains the "Upload Dropzone" and the main Data Grid (`<table>`).
  - **Right Panel (Document Viewer)**: A resizable `<div id="docViewerPanel">` used to display the uploaded PDF/Image side-by-side with the data grid.
- **Modals**: There are multiple hidden modals (Settings, Mapping, Product Mapping, Audit Report) that are toggled via JavaScript classes (`.hidden`).

## 4. JavaScript Architecture (`app.js`)
`app.js` is structured around state management and event listeners.
- **State Variables**: Variables like `currentModule`, `clientLedgers`, `clientProducts`, and `currentExtractedData` hold the frontend state.
- **Dynamic Rendering**: Functions like `renderGrid(data)` manually construct HTML strings (using template literals `` ` ``) for table rows and use `innerHTML` or `appendChild()` to inject them into the DOM.
- **Event Listeners**: Attached to buttons and inputs for interactivity. *Note: Since rows are dynamically generated, event listeners for row inputs (like recalculating totals) are attached inside the `renderGrid` loop.*
- **Micro-interactions**: Handled via Tailwind utility classes (e.g., `hover:-translate-y-0.5`, `active:scale-95`, `focus:ring-2`) injected dynamically or hardcoded in HTML.

## 5. Styling Paradigm
- **Dark Premium Theme**: The app uses a deep dark theme (`bg-obsidian-950`).
- **Glassmorphism**: Elements like the sidebar use `backdrop-blur-md` and semi-transparent backgrounds (`bg-obsidian-900/40`).
- **Accessibility**: Inputs use focus rings (`focus:ring-2 focus:ring-brand-500`).
- **Feedback**: Animations like `animate-fade-in-up` (for row entry) and `error-shake` (for validation) are defined in `<style>` blocks in `index.html` and triggered via JS classes.

## 6. 🛡️ Mandatory Zero-Bug Pre/Post Verification Protocol
**CRITICAL INSTRUCTION FOR ALL AI ASSISTANTS:**
1. **Pre-Check**: Read `backend/verify_integrity.py` and `AI_ARCHITECTURE_SUMMARY.md` before making any code change.
2. **Implementation**: Enforce strict double-entry accounting rules (Bank Charges $\rightarrow$ Indirect Expenses `BP`, never Contra `BC`; Suspense Account $\rightarrow$ Retained for audit; POS $\rightarrow$ Local vs Interstate GST).
3. **Post-Check Verification**: Run `./venv/bin/python3 backend/verify_integrity.py` and `node --check frontend/app.js` after code changes.
4. **Self-Healing**: If any test fails, auto-heal the code and re-run verification until 100% clean before reporting completion.
