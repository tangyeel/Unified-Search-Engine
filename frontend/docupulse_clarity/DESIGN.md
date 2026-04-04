# Design System Specification

## 1. Overview & Creative North Star: "The Digital Curator"

This design system is built upon the North Star of **"The Digital Curator."** In a world of cluttered data and chaotic file structures, this system acts as a serene, hyper-intelligent gallery for information. We move away from the "utility-first" look of traditional search engines toward a high-end, editorial experience.

### The Editorial Shift
To achieve a premium feel, we reject the rigid, boxy constraints of standard SaaS platforms. Instead, we utilize:
*   **Intentional Asymmetry:** Off-setting search results or metadata panels to create a rhythmic, non-linear reading path.
*   **Atmospheric Depth:** Using the "Cloud White" palette not as a flat background, but as a series of layered, translucent vellum sheets.
*   **Micro-Moments of Vibrancy:** Reserving the "Electric Blue" (Primary) for high-intent actions, ensuring it acts as a beacon within the expansive whitespace.

---

## 2. Color & Surface Architecture

The palette is rooted in a "Cloud-to-Electric" spectrum. We prioritize tonal shifts over structural lines.

### The "No-Line" Rule
**Explicit Instruction:** Do not use 1px solid borders to section off content. Traditional borders create visual noise that traps the eye. Instead:
*   **Background Shifts:** Distinguish the sidebar from the main feed by transitioning from `surface` (#f7f9fb) to `surface-container-low` (#f2f4f6).
*   **Tonal Definition:** Define search bars and cards through subtle elevation or slight color darkening rather than an outline.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of premium paper and glass.
*   **Base Layer:** `surface` (#f7f9fb) — The infinite canvas.
*   **Structural Sections:** `surface-container` (#eceef0) — For persistent navigation or sidebars.
*   **Interactive Cards:** `surface-container-lowest` (#ffffff) — Used for document result cards to make them "pop" against the off-white background.

### The "Glass & Gradient" Rule
To inject "soul" into the tech-forward aesthetic:
*   **Glassmorphism:** Floating modals and sticky headers must use `surface-container-lowest` at 80% opacity with a `24px` backdrop-blur. 
*   **Signature Gradients:** Primary CTAs should utilize a subtle linear gradient: `primary` (#0050cb) to `primary-container` (#0066ff) at a 135° angle.

---

## 3. Typography: The Intellectual Voice

We use a dual-font strategy to balance technical precision with editorial authority.

*   **The Authority (Manrope):** Used for `Display` and `Headline` scales. Its geometric but warm construction provides a "tech-forward" yet humanistic feel.
*   **The Engine (Inter):** Used for `Title`, `Body`, and `Label` scales. Inter provides maximum legibility for dense document metadata and file paths.

### Typography Scale Highlights
*   **Display-LG (Manrope, 3.5rem):** Reserved for empty states or hero search moments. Low letter-spacing (-0.02em).
*   **Headline-SM (Manrope, 1.5rem):** For document titles in preview modes.
*   **Label-MD (Inter, 0.75rem):** For file tags and "Last Modified" metadata. Always set in `secondary` (#505f76) to maintain hierarchy.

---

## 4. Elevation & Depth: Tonal Layering

We avoid "floating shadows" that feel disconnected. Depth must feel like ambient light hitting a physical surface.

*   **The Layering Principle:** To lift a document card, place a `surface-container-lowest` (#ffffff) card on a `surface-container-low` (#f2f4f6) background. The delta in lightness provides a soft, natural lift.
*   **Ambient Shadows:** For high-importance floating elements (e.g., a File Upload modal), use a multi-layered shadow:
    *   `offset: 0px 12px | blur: 32px | color: rgba(25, 28, 30, 0.06)`
*   **The "Ghost Border" Fallback:** If a container requires definition against a white background, use the `outline-variant` (#c2c6d8) at **15% opacity**. Never use a 100% opaque border.

---

## 5. Components & UI Elements

### Roundedness Scale
All primary containers (Cards, Inputs, Modals) must use the **XL (1.5rem / 24px)** or **LG (1rem / 16px)** radius to reinforce the "Soft Minimalism" aesthetic.

### Key Components
*   **Search Input:** Use `surface-container-lowest` with a "Ghost Border." On focus, transition the border to a 1px `primary` glow with a soft `primary-fixed` ambient shadow.
*   **Document Cards:** Absolute prohibition of divider lines. Separate the document title, snippet, and metadata using the **Spacing Scale (16px/24px)**. Use high-quality, custom-rendered icons for DOCX, PDF, and PPTX that utilize the system's `Electric Blue` for accents.
*   **Action Chips:** Filter chips for "Date" or "File Type" should use `surface-container-high` (#e6e8ea) with no border. On selection, they morph into `primary` with `on-primary` (white) text.
*   **Buttons:**
    *   *Primary:* Gradient-filled (Electric Blue), 16px corners, subtle lift on hover.
    *   *Secondary:* `surface-container-highest` background with `primary` text. No border.
*   **File Type Iconography:** Icons are not mere illustrations; they are functional signals. Use a 2pt stroke weight for icons to match the "Soft Slate" typography weight.

---

## 6. Do’s and Don’ts

### Do
*   **DO** use whitespace as a functional tool. If a layout feels cramped, increase the padding to the next tier in the scale rather than adding a line.
*   **DO** use "Electric Blue" sparingly. It is a precision tool for directing the user's eye to the "Search" or "Download" buttons.
*   **DO** ensure all glassmorphic elements have sufficient backdrop blur (min 20px) to maintain text readability over varying background content.

### Don’t
*   **DON'T** use pure black (#000000) for text. Always use `on-surface` (#191c1e) for primary text to maintain the soft, high-end visual tone.
*   **DON'T** use standard 1px gray dividers. If you must separate content, use a 4px height `surface-container-low` bar or simply more whitespace.
*   **DON'T** use sharp corners. Every element, from checkboxes to large hero sections, must adhere to the 16px (LG) or 24px (XL) rounding.