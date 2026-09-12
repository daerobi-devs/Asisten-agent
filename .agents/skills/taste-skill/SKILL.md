---
name: taste-skill
description: High-tier UI/UX Design System & Aesthetics Taste Skill (Linear/Vercel/Raycast/Apple level polish). Applies when designing Web UI, dashboards, CLI aesthetics, component hierarchies, dark mode palettes, typography, micro-interactions, and visual data representations.
---

# 🎨 Taste Skill — Premium UI/UX Design & Aesthetic Engineering

This skill defines the engineering and design rules for building world-class, premium, modern user interfaces with impeccable aesthetic taste.

---

## 1. Core Visual Principles

1. **Dark Mode First & Depth Layering**:
   - Never use pure `#000000` for background surfaces; use deep slate or zinc tones (e.g., `#090a0f`, `#0d1117`, `#12151c`).
   - Cards and elevated surfaces use subtle border contrast (`border border-white/5` to `border-white/10`) with slight background elevation (`bg-white/[0.02]` or `bg-slate-900/60` with `backdrop-blur-md`).
   - Inner glow / subtle top-highlight borders (`border-t-white/15`) to create depth.

2. **Typography & Hierarchy**:
   - Modern, high-legibility geometric sans fonts (Geist, Inter, Plus Jakarta Sans, SF Pro).
   - Monospace for hashes, metrics, tokens, ports, IP addresses, logs, and code (Geist Mono, JetBrains Mono, Fira Code).
   - Tight letter-spacing for headlines (`tracking-tight`), generous line-height for body copy.

3. **Color Accents & Semantic Signals**:
   - Primary Accent: Neon Violet / Indigo / Cyan (`#6366f1`, `#8b5cf6`, `#06b6d4`, `#3b82f6`).
   - Status indicators with glowing pulse effects:
     - Online / Active: `emerald-400` / `emerald-500` with subtle ping or pulse.
     - Warning / Syncing: `amber-400`.
     - Error / Disconnected: `rose-500`.
     - Idle / Muted: `slate-500`.

4. **Micro-Interactions & Polish**:
   - Smooth transitions on all interactive elements (`transition-all duration-200 ease-out`).
   - Hover states: subtle lift (`-translate-y-0.5`), surface brightening, or subtle accent border highlight.
   - Active state press feedback (`active:scale-[0.98]`).
   - Tooltips on every icon button and metric badge.
   - Skeletons / shimmer animations during data loading.

5. **Information Density & Layout**:
   - Dashboard layouts inspired by Linear, Raycast, and Vercel: dense, highly scannable, zero clutter.
   - Clean data tables with sortable headers, search filter bars, and status badges.
   - Real-time stream logs with autoscroll toggles and syntax highlighting.

---

## 2. CLI & Terminal Aesthetics (Rich / Textual)

- Use unified color themes (e.g., Tokyo Night / Catppuccin Mocha).
- Formatted tables with subtle borders (`box.ROUNDED`).
- Beautiful spinners, step indicators, and progress bars.
- Clear markdown rendering for agent reasoning and tool call cards.

---

## 3. UI Component Checklist

- [ ] Sticky, frosted-glass header with status indicators (9Router status, Tailscale status, active channel count).
- [ ] Sidebar navigation with collapsible groups and badge counts.
- [ ] Command Palette (`Ctrl+K` / `Cmd+K`) for fast action dispatching.
- [ ] Resizable panels for workspace file tree, editor, and chat.
- [ ] Real-time WebSocket connection state banner.