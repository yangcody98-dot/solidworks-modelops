# Design system: CAD Automation Delivery Workbench

## 1. Visual theme and atmosphere

The direction is a calm engineering control room: density 7/10, variation 4/10, and motion 2/10.

The interface should feel dependable, clear, and suitable for repeated use by mechanical engineers. Make project status, parameter completeness, P0 review, and delivery outputs easy to find. Use the restraint and order of a precision instrument panel.

## 2. Color palette and roles

- **Drafting Canvas** (#EDEEEA): main background, close to drafting paper without a yellow cast.
- **Instrument Surface** (#FAFAF7): forms, review areas, and main content panels.
- **Charcoal Console** (#141B1F): left navigation and bottom status area; avoid pure black.
- **Ink Primary** (#182024): headings, labels, and primary content.
- **Steel Text** (#56636B): supporting text, paths, and status descriptions.
- **Hairline Border** (#D8DDD7): 1px structural lines and input borders.
- **Copper Accent** (#B87333): the sole accent for primary buttons, selected states, and critical gates.

Do not use purple or blue neon, pure black, glowing shadows, or highly saturated gradients.

## 3. Typography

- **Display:** Microsoft YaHei UI Semibold, chosen for Chinese engineering-software text. Keep sizes restrained and use weight for hierarchy.
- **Body:** Microsoft YaHei UI, with comfortable line height and form text at least 13px.
- **Mono:** Cascadia Mono / Consolas for logs, file paths, and numeric lists.
- **Avoid:** serif fonts, extensive negative tracking, and oversized marketing headings.

## 4. Components

- **Buttons:** flat and clearly bounded; use Copper Accent for primary actions and darker copper when pressed. No outer glow.
- **Panels:** use only for actual functional areas. Keep radii below 10px and borders clear; avoid nested cards.
- **Inputs:** left-aligned labels, consistent field heights, and a focus state that changes only the border color.
- **Tables:** light-gray headers, clear numeric columns, and compact engineering density.
- **Status:** show P0/P1 results through text and color rather than decorative icons.
- **Empty states:** state the next action clearly, such as "Save parameters to generate the project directory."

## 5. Layout

- Place navigation and product identity on the left, working parameters in the center, and review and outputs on the right.
- Keep a top command bar with primary actions at the upper right.
- Show four core workflow facts in the summary strip: local execution, GB/T style, P0 gate, and mock status.
- Avoid three-column marketing cards and decorative visual noise.
- Show text in full; button widths must not truncate labels.

## 6. Motion and interaction

The current desktop prototype does not use complex animation. Feedback comes from hover, pressed, focus, and status-text changes. For future long-running CAD execution, use stage progress and streaming logs rather than a spinning indicator.

## 7. Anti-patterns

- Pure black.
- Purple or blue neon gradients.
- Decorative glow.
- Marketing copy.
- Emoji.
- Buttons that squeeze or truncate their text.
- Large blank areas that make forms look like empty demos.
- Review results hidden only in JSON; show key issues directly in the interface.
