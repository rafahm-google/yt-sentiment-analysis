---
tokens:
  color:
    brand:
      primary: "#3498db" # Bright blue used for accents and highlights
      dark: "#2c3e50" # Slate blue used for primary headers
    background:
      light: "#f9f9f9" # Main background for the light report theme
      dark: "#08132a" # Deep navy background for the dark deck theme
      surface: "#ffffff" # White background for content containers
    text:
      primary: "#333333" # Main text color for readability on light surfaces
      light: "#d9e2ff" # Light text color for high contrast on dark surfaces
      muted: "#555555" # Secondary text color for blockquotes and metadata
    border:
      light: "#ecf0f1" # Subtle divider color for light themes
      dark: "#44474d" # Edge definition color for dark themes
  typography:
    fontFamily:
      sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
      mono: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace'
      accent: "'Inter', sans-serif"
    fontSize:
      h1: "2.5em"
      h2: "1.8em"
      h3: "1.4em"
      body: "1em"
      code: "0.9em"
  elevation:
    shadow:
      subtle: "0 2px 10px rgba(0,0,0,0.05)"
      strong: "0 4px 20px rgba(0,0,0,0.5)"
  radius:
    small: "4px"
    medium: "8px"
    large: "12px"
---

# Design System: YouTube Sentiment Analysis

## Look & Feel

The application's visual identity is split into two distinct modes, each serving a specific purpose and audience. This dual approach ensures that dense data is readable while executive summaries are engaging and cinematic.

### 1. The Strategic Report (Light Mode)
The report is designed for deep reading and data analysis. It uses a clean, editorial layout inspired by modern business whitepapers.
*   **Clarity First**: Large, dark slate headers break up the content, and bright blue accents guide the eye to key findings.
*   **Structure**: Generous padding and subtle box shadows create a layered effect, making the document feel organized and professional.
*   **Readability**: High contrast between the dark gray text and the pure white surface container reduces eye strain during analysis.

### 2. The Presentation Deck (Dark Mode)
The deck is designed for high-stakes executive presentations where impact and mood are critical. It adopts a cinematic, immersive dark theme.
*   **Visual Punch**: The deep navy background makes full-bleed AI-generated slides pop, creating a "theater" effect in the browser.
*   **Focus**: By removing all non-essential UI elements and using a thick border with heavy drop shadows, each slide feels like a physical card or screen.
*   **Modern Aesthetics**: The use of the `Inter` font ensures that the presentation feels state-of-the-art and avoids standard browser defaults.

## Design Intent

*   **Contrast as a Tool**: We use extreme dark and light themes to separate data analysis from executive storytelling.
*   **No Clutter**: Both outputs prioritize content over decoration. Borders are thin, shadows are soft, and spacing is generous.
*   **Premium Feel**: The choice of deep navy and bright blue highlights gives the application a high-tech, premium analytical feel, fitting for a tool powered by advanced AI.
