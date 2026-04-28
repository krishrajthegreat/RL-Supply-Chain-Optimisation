---
name: Cyber Logistics
colors:
  surface: '#0e141a'
  surface-dim: '#0e141a'
  surface-bright: '#343a41'
  surface-container-lowest: '#090f15'
  surface-container-low: '#171c23'
  surface-container: '#1b2027'
  surface-container-high: '#252a32'
  surface-container-highest: '#30353d'
  on-surface: '#dee3ec'
  on-surface-variant: '#baccb0'
  inverse-surface: '#dee3ec'
  inverse-on-surface: '#2c3138'
  outline: '#85967c'
  outline-variant: '#3c4b35'
  surface-tint: '#2ae500'
  primary: '#efffe3'
  on-primary: '#053900'
  primary-container: '#39ff14'
  on-primary-container: '#107100'
  inverse-primary: '#106e00'
  secondary: '#c4c6cf'
  on-secondary: '#2e3037'
  secondary-container: '#464950'
  on-secondary-container: '#b6b8c1'
  tertiary: '#fafafa'
  on-tertiary: '#303030'
  tertiary-container: '#dddddd'
  on-tertiary-container: '#616161'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#79ff5b'
  primary-fixed-dim: '#2ae500'
  on-primary-fixed: '#022100'
  on-primary-fixed-variant: '#095300'
  secondary-fixed: '#e1e2eb'
  secondary-fixed-dim: '#c4c6cf'
  on-secondary-fixed: '#191c22'
  on-secondary-fixed-variant: '#44474e'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c6'
  on-tertiary-fixed: '#1b1b1b'
  on-tertiary-fixed-variant: '#474747'
  background: '#0e141a'
  on-background: '#dee3ec'
  surface-variant: '#30353d'
typography:
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 40px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: '0'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: '0'
  label-caps:
    fontFamily: Space Grotesk
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.1em
  data-mono:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.4'
    letterSpacing: 0.02em
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  gutter: 16px
  margin: 32px
---

## Brand & Style
The design system is engineered for high-stakes environments where precision and speed are paramount. It evokes a "Mission Control" atmosphere, prioritizing data clarity and system status through a high-contrast, technical aesthetic. The brand personality is clinical, futuristic, and authoritative, designed to make users feel like they are piloting a sophisticated logistics engine.

The visual style blends **Minimalism** with **Glassmorphism** and **High-Contrast** elements. It utilizes a strict "Dark Mode" foundation to reduce eye strain during extended monitoring. Layouts are governed by a rigid grid system that suggests structural integrity, while thin borders and subtle neon glows provide a layer of tactical sophistication.

## Colors
The palette is rooted in a "True Black" (#000000) foundation to achieve infinite depth and maximum contrast. Deep Charcoal (#0B0E14) serves as the primary surface color, creating a subtle distinction between the background and interactive modules. 

The Primary Accent is a vibrant Neon Green (#39FF14), reserved exclusively for active states, critical data points, and primary actions. This color should be used sparingly but impactfully to guide the eye toward essential information. A secondary neutral grey is used for non-essential metadata and inactive iconography, ensuring that the interface remains uncluttered and functional.

## Typography
The typography strategy utilizes a dual-font approach to balance technical character with readability. **Space Grotesk** is used for headlines and navigational labels, providing a geometric, futuristic feel that aligns with the "Cyber" narrative. 

**Inter** is employed for body text and data visualizations to ensure maximum legibility and a neutral, professional tone. For data displays and logistics coordinates, uppercase labels with increased letter spacing are used to mimic industrial marking and instrumentation.

## Layout & Spacing
The design system follows a strict 4px baseline grid to ensure mathematical precision in all alignments. The layout philosophy is built on a **Fluid Grid** model, allowing dashboards to expand and contract across ultra-wide monitors while maintaining internal proportions.

Modules are separated by consistent 16px gutters. Heavy use of internal padding within containers (usually 24px) creates an "airtight" feel, preventing information density from becoming overwhelming. White space is treated as functional space—used to isolate critical data streams rather than just for aesthetic relief.

## Elevation & Depth
Depth is achieved through **Glassmorphism** and **Tonal Layering** rather than traditional shadows. 
- **Base Level:** True Black (#000000) represents the void.
- **Surface Level:** Deep Charcoal (#0B0E14) containers sit atop the base with 1px borders.
- **Overlay Level:** Modals and tooltips use a semi-transparent blur effect (backdrop-filter: blur(12px)) with a slightly lighter border to simulate glass.

Instead of shadows, a "Neon Glow" (box-shadow: 0 0 10px rgba(57, 255, 20, 0.3)) is applied to active elements and critical alerts to make them appear as if they are emitting light within the dark environment.

## Shapes
The shape language is defined by **Sharp (0px)** corners. This decision reinforces the technical, industrial nature of logistics and hardware interfaces. Every container, button, and input field features 90-degree angles to maintain a rigid, grid-locked appearance. 

Subtle 45-degree chamfers (clipped corners) may be used on specialized buttons or status tags to provide a "tactical" hardware feel without departing from the overall angular geometry.

## Components
- **Buttons:** Primary buttons are solid Neon Green with black text. Secondary buttons are ghost-style with a 1px Neon Green border and no fill. Both feature a subtle outer glow on hover.
- **Input Fields:** Styled with a 1px Charcoal border and a True Black background. On focus, the border turns Neon Green with a soft inner glow.
- **Status Chips:** Small, rectangular tags. Positive status uses a green outline; warning uses amber; critical uses red. All use monospace typography.
- **Data Cards:** Modules with thin 1px borders. Headers are separated by a horizontal rule. High-priority metrics are displayed in large, bold Space Grotesk.
- **Scrollbars:** Custom-styled to be ultra-thin (4px) in Neon Green, ensuring they act as visual indicators rather than bulky UI elements.
- **Logistics Indicators:** Specialized components such as "Route Progress Bars" use segmented blocks rather than a smooth fill to reflect the discrete nature of data segments.