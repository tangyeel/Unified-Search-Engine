import { useState, useEffect, useRef, useMemo } from "react";

const API_BASE = import.meta.env?.VITE_API_BASE || "http://127.0.0.1:8000";

async function safeFetchJson(url, options) {
  const res = await fetch(url, options);
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const message = data?.detail || data?.message || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

const colors = {
  primary: "#ff4fa3",
  primaryContainer: "#ff78bf",
  surface: "#ececef",
  surfaceContainerLowest: "#ffffff",
  surfaceContainerLow: "#f5f5f7",
  surfaceContainer: "#efeff2",
  surfaceContainerHigh: "#e3e5ec",
  surfaceContainerHighest: "#d9dce5",
  onSurface: "#191c1e",
  secondary: "#4e5f79",
  onSecondary: "#ffffff",
  primaryFixed: "#ffd9ea",
  outlineVariant: "#cfd3df",
  outline: "#757b8e",
};

const style = `
  @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body, #root { width: 100%; min-height: 100%; }
  body { cursor: auto; background: #e8e8e8; }

  .tp-vanta-bg {
    position: fixed;
    inset: 0;
    z-index: 1;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.4s ease;
  }
  .tp-vanta-bg.active { opacity: 1; }

  .tp-dot-grid {
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 2;
    pointer-events: none;
  }

  .tp-root {
    font-family: 'Inter', sans-serif;
    background: transparent;
    color: ${colors.onSurface};
    min-height: 100vh;
    display: flex;
    overflow: hidden;
    position: relative;
    z-index: 12;
  }

  .tp-sidebar {
    width: 240px;
    min-height: 100vh;
    background: white;
    border-radius: 0 24px 24px 0;
    padding: 20px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    position: fixed;
    left: -232px;
    top: 0;
    z-index: 100;
    box-shadow: 4px 0 24px rgba(255,79,163,0.08);
    transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
    flex-shrink: 0;
  }

  .tp-sidebar:hover {
    left: 0;
    box-shadow: 12px 0 40px rgba(255,79,163,0.15);
  }

  .tp-sidebar-trigger {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: 12px;
    z-index: 90;
  }

  .tp-logo-area {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 8px 20px;
    margin-bottom: 8px;
  }

  .tp-logo-icon {
    width: 38px;
    height: 38px;
    border-radius: 12px;
    background: linear-gradient(135deg, ${colors.primary}, ${colors.primaryContainer});
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(255,79,163,0.32);
  }

  .tp-logo-text h1 {
    font-family: 'Manrope', sans-serif;
    font-size: 17px;
    font-weight: 800;
    color: ${colors.primary};
    line-height: 1;
  }

  .tp-logo-text p {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: ${colors.secondary};
    margin-top: 3px;
  }

  .tp-nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 14px;
    font-size: 13.5px;
    font-weight: 500;
    color: ${colors.secondary};
    cursor: pointer;
    transition: all 0.22s cubic-bezier(0.34,1.56,0.64,1);
    border: none;
    background: transparent;
    width: 100%;
    text-align: left;
    position: relative;
    overflow: hidden;
  }

  .tp-nav-item:hover {
    background: ${colors.surfaceContainerLow};
    color: ${colors.onSurface};
    transform: translateX(2px);
  }

  .tp-nav-item.active {
    background: ${colors.surfaceContainerLowest};
    color: ${colors.primary};
    font-weight: 700;
    box-shadow: 0 2px 12px rgba(255,79,163,0.16);
  }

  .tp-nav-item .mso {
    font-size: 20px;
    transition: transform 0.22s;
  }
  .tp-nav-item:hover .mso { transform: scale(1.15); }

  .tp-nav-footer {
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid ${colors.surfaceContainerHigh};
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .tp-upload-btn {
    margin: 8px 4px 12px;
    padding: 11px 16px;
    background: linear-gradient(135deg, ${colors.primary}, ${colors.primaryContainer});
    color: white;
    border: none;
    border-radius: 14px;
    font-family: 'Manrope', sans-serif;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    justify-content: center;
    transition: all 0.22s cubic-bezier(0.34,1.56,0.64,1);
    box-shadow: 0 4px 14px rgba(255,79,163,0.24);
  }
  .tp-upload-btn:hover {
    transform: translateY(-1px) scale(1.02);
    box-shadow: 0 6px 20px rgba(255,79,163,0.34);
  }

  .tp-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
    min-width: 0;
    margin-left: 0;
    transition: margin-left 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  }

  .tp-topbar {
    position: sticky;
    top: 0;
    z-index: 40;
    background: rgba(248,248,252,0.8);
    backdrop-filter: blur(24px);
    border-bottom: 1px solid rgba(255,79,163,0.2);
    padding: 12px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }

  .tp-search-wrap {
    position: relative;
    flex: 1;
    max-width: 440px;
  }

  .tp-search-wrap .mso {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: ${colors.outline};
    font-size: 18px;
    pointer-events: none;
  }

  .tp-search-input {
    width: 100%;
    background: ${colors.surfaceContainerLow};
    border: none;
    border-radius: 14px;
    padding: 9px 16px 9px 40px;
    font-size: 13.5px;
    color: ${colors.onSurface};
    outline: none;
    transition: all 0.2s;
    font-family: 'Inter', sans-serif;
  }
  .tp-search-input:focus {
    background: white;
    box-shadow: 0 0 0 2px rgba(255,79,163,0.22);
  }

  .tp-topbar-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .tp-icon-btn {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    border: none;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    color: ${colors.secondary};
    cursor: pointer;
    transition: all 0.18s;
    font-size: 20px;
  }
  .tp-icon-btn:hover { background: ${colors.surfaceContainerLow}; color: ${colors.primary}; }

  .tp-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, ${colors.primary}, ${colors.primaryContainer});
    color: white;
    font-weight: 700;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(255,79,163,0.22);
  }

  .tp-page {
    padding: 28px;
    flex: 1;
    overflow-y: auto;
    animation: fadeSlideIn 0.38s cubic-bezier(0.22,1,0.36,1);
  }

  @keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes pulse-ring {
    0% { box-shadow: 0 0 0 0 rgba(255,79,163,0.3); }
    70% { box-shadow: 0 0 0 12px rgba(255,79,163,0); }
    100% { box-shadow: 0 0 0 0 rgba(255,79,163,0); }
  }

  @keyframes accentFloat {
    0%,100% { transform: translateY(0px); }
    50% { transform: translateY(-4px); }
  }

  @keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }

  @keyframes floatCard {
    0%,100% { transform: translateY(0px) rotate(var(--r,0deg)); }
    50% { transform: translateY(-8px) rotate(var(--r,0deg)); }
  }

  @keyframes loadingBar {
    0% { transform: translateX(-100%); width: 25%; }
    50% { transform: translateX(150%); width: 55%; }
    100% { transform: translateX(400%); width: 25%; }
  }

  @keyframes orbitSpin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  @keyframes counterUp {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .card {
    background: white;
    border-radius: 20px;
    padding: 22px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.03);
    transition: all 0.28s cubic-bezier(0.34,1.56,0.64,1);
    border: 1px solid rgba(194,198,216,0.08);
  }
  .card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 24px rgba(255,79,163,0.12), 0 1px 4px rgba(0,0,0,0.04);
  }

  .mso {
    font-family: 'Material Symbols Outlined';
    font-weight: normal;
    font-style: normal;
    font-size: 22px;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    vertical-align: middle;
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  }

  .mso.filled {
    font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 12px;
    border-radius: 99px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: all 0.2s cubic-bezier(0.34,1.56,0.64,1);
  }

  .chip-default {
    background: ${colors.surfaceContainerHigh};
    color: ${colors.secondary};
  }
  .chip-default:hover { background: ${colors.surfaceContainerHighest}; transform: scale(1.04); }

  .chip-active {
    background: ${colors.primary};
    color: white;
    box-shadow: 0 3px 10px rgba(255,79,163,0.3);
  }

  .btn-primary {
    background: linear-gradient(135deg, ${colors.primary}, ${colors.primaryContainer});
    color: white;
    border: none;
    border-radius: 13px;
    padding: 10px 20px;
    font-size: 13.5px;
    font-weight: 700;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    transition: all 0.22s cubic-bezier(0.34,1.56,0.64,1);
    font-family: 'Manrope', sans-serif;
    box-shadow: 0 3px 12px rgba(255,79,163,0.25);
  }
  .btn-primary:hover {
    transform: translateY(-1px) scale(1.02);
    box-shadow: 0 6px 20px rgba(255,79,163,0.35);
  }

  .btn-secondary {
    background: ${colors.surfaceContainerHighest};
    color: ${colors.primary};
    border: none;
    border-radius: 13px;
    padding: 10px 20px;
    font-size: 13.5px;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    transition: all 0.2s;
    font-family: 'Manrope', sans-serif;
  }
  .btn-secondary:hover { background: ${colors.surfaceContainerHigh}; transform: translateY(-1px); }

  .h-headline { font-family: 'Manrope', sans-serif; }
  .text-primary-color { color: ${colors.primary}; }
  .text-secondary-color { color: ${colors.secondary}; }

  .stagger-1 { animation-delay: 0.05s; animation-fill-mode: both; }
  .stagger-2 { animation-delay: 0.10s; animation-fill-mode: both; }
  .stagger-3 { animation-delay: 0.15s; animation-fill-mode: both; }
  .stagger-4 { animation-delay: 0.20s; animation-fill-mode: both; }
  .stagger-5 { animation-delay: 0.25s; animation-fill-mode: both; }
  .stagger-6 { animation-delay: 0.30s; animation-fill-mode: both; }

  .animate-slide-up { animation: slideUp 0.45s cubic-bezier(0.22,1,0.36,1); }

  .glow-orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(80px);
    pointer-events: none;
    z-index: 0;
  }

  .loading-progress {
    width: 100%;
    height: 3px;
    background: ${colors.surfaceContainerHigh};
    border-radius: 99px;
    overflow: hidden;
    position: relative;
  }
  .loading-progress-bar {
    position: absolute;
    top: 0; left: 0; height: 100%;
    background: linear-gradient(90deg, ${colors.primary}, ${colors.primaryContainer});
    border-radius: 99px;
    animation: loadingBar 2.2s ease-in-out infinite;
  }

  .result-card {
    background: white;
    border-radius: 20px;
    padding: 20px 22px;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.28s cubic-bezier(0.22,1,0.36,1);
    animation: slideUp 0.4s cubic-bezier(0.22,1,0.36,1) both;
  }
  .result-card:hover {
    border-color: rgba(255,79,163,0.2);
    box-shadow: 0 4px 24px rgba(255,79,163,0.12);
    transform: translateY(-2px);
  }

  .file-icon-wrap {
    width: 48px; height: 48px;
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    transition: transform 0.22s cubic-bezier(0.34,1.56,0.64,1);
  }
  .result-card:hover .file-icon-wrap { transform: scale(1.1) rotate(-3deg); }

  .mindmap-canvas {
    position: relative;
    flex: 1;
    background: radial-gradient(#e2e8f0 1px, transparent 1px);
    background-size: 28px 28px;
    overflow: hidden;
  }

  .map-node-center {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    z-index: 20;
  }

  .map-node {
    position: absolute;
    transform: translate(-50%, -50%);
    cursor: pointer;
    z-index: 10;
  }

  .node-circle {
    width: 78px; height: 78px;
    border-radius: 50%;
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(20px);
    border: 1.5px solid rgba(255,79,163,0.2);
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    color: ${colors.primary};
    box-shadow: 0 4px 20px rgba(255,79,163,0.14);
    transition: all 0.28s cubic-bezier(0.34,1.56,0.64,1);
    text-align: center;
    padding: 8px;
  }
  .node-circle:hover {
    transform: scale(1.15);
    box-shadow: 0 8px 32px rgba(255,79,163,0.24);
    background: white;
  }

  .sub-node {
    display: flex; align-items: center; gap: 6px;
    background: white;
    padding: 6px 12px;
    border-radius: 99px;
    font-size: 11px; font-weight: 600;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    border: 1px solid rgba(194,198,216,0.2);
    position: absolute;
    white-space: nowrap;
    cursor: pointer;
    transition: all 0.22s cubic-bezier(0.34,1.56,0.64,1);
  }
  .sub-node:hover { transform: scale(1.06); box-shadow: 0 4px 16px rgba(255,79,163,0.12); }

  .dashboard-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 18px;
  }

  .stat-badge {
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 11px;
    font-weight: 700;
    background: ${colors.primaryFixed};
    color: ${colors.primary};
  }

  .activity-line {
    position: absolute;
    left: 15px; top: 4px; bottom: 0;
    width: 1.5px;
    background: ${colors.surfaceContainerHigh};
  }

  .activity-item {
    position: relative;
    padding-left: 42px;
    padding-bottom: 24px;
    animation: slideUp 0.4s cubic-bezier(0.22,1,0.36,1) both;
  }

  .activity-dot {
    position: absolute;
    left: 0; top: 2px;
    width: 30px; height: 30px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px;
    ring: 4px;
  }

  .preview-panel {
    display: flex;
    flex: 1;
    gap: 18px;
    overflow: hidden;
  }

  .pdf-viewer {
    flex: 3;
    background: white;
    border-radius: 20px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    position: relative;
  }

  .meta-panel {
    width: 270px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
    overflow-y: auto;
  }

  .version-item {
    position: relative;
    padding-left: 20px;
    padding-bottom: 18px;
    border-left: 2px solid ${colors.surfaceContainerHigh};
  }
  .version-item.active { border-left-color: ${colors.primary}; }
  .version-dot {
    position: absolute;
    left: -5px; top: 3px;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: ${colors.surfaceContainerHighest};
  }
  .version-item.active .version-dot { background: ${colors.primary}; }

  .home-hero {
    position: relative;
    text-align: center;
    padding: 48px 20px 32px;
    overflow: visible;
  }

  .home-hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255,79,163,0.08);
    border: 1px solid rgba(255,79,163,0.15);
    border-radius: 99px;
    padding: 4px 14px 4px 8px;
    font-size: 11.5px;
    font-weight: 700;
    color: ${colors.primary};
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 20px;
    animation: slideUp 0.4s cubic-bezier(0.22,1,0.36,1) both;
  }

  .home-hero-title {
    background: linear-gradient(120deg, #2a2b31 5%, ${colors.primary} 66%, ${colors.primaryContainer} 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    animation: slideUp 0.45s cubic-bezier(0.22,1,0.36,1) both, accentFloat 4s ease-in-out infinite;
  }

  .search-hero-wrap {
    position: relative;
    max-width: 600px;
    margin: 0 auto;
    z-index: 10;
    animation: slideUp 0.45s cubic-bezier(0.22,1,0.36,1) 0.15s both;
  }

  .search-hero-box {
    background: rgba(255,255,255,0.9);
    backdrop-filter: blur(28px);
    border-radius: 18px;
    padding: 8px 8px 8px 18px;
    display: flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 4px 24px rgba(255,79,163,0.12), 0 1px 4px rgba(0,0,0,0.04);
    border: 1px solid rgba(255,79,163,0.1);
    transition: box-shadow 0.2s, border-color 0.2s;
  }

  .search-hero-box:focus-within {
    box-shadow: 0 8px 32px rgba(255,79,163,0.2), 0 1px 4px rgba(0,0,0,0.04);
    border-color: rgba(255,79,163,0.25);
  }

  .home-search-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font-size: 15px;
    color: ${colors.onSurface};
    font-family: 'Inter', sans-serif;
    padding: 6px 0;
  }

  .home-search-input::placeholder {
    color: ${colors.outline};
  }

  .search-hint-pills {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 16px;
    flex-wrap: wrap;
    animation: slideUp 0.45s cubic-bezier(0.22,1,0.36,1) 0.25s both;
  }

  .search-hint-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255,255,255,0.7);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(194,198,216,0.2);
    border-radius: 99px;
    padding: 5px 13px 5px 9px;
    font-size: 12px;
    font-weight: 500;
    color: ${colors.secondary};
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.34,1.56,0.64,1);
    white-space: nowrap;
  }
  .search-hint-pill:hover {
    background: white;
    color: ${colors.primary};
    border-color: rgba(255,79,163,0.2);
    transform: translateY(-1px);
    box-shadow: 0 3px 12px rgba(255,79,163,0.1);
  }

  .dropdown-result {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 14px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .dropdown-result:hover { background: ${colors.surfaceContainerLow}; }

  .bento-card {
    background: rgba(255,255,255,0.6);
    backdrop-filter: blur(12px);
    border-radius: 18px;
    padding: 22px;
    border: 1px solid rgba(194,198,216,0.12);
    transition: all 0.28s cubic-bezier(0.34,1.56,0.64,1);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .bento-card:hover {
    background: white;
    border-color: rgba(255,79,163,0.18);
    box-shadow: 0 6px 24px rgba(255,79,163,0.12);
    transform: translateY(-2px);
  }

  .recent-file-chip {
    display: flex; align-items: center; gap: 8px;
    background: rgba(255,255,255,0.9);
    padding: 8px 14px;
    border-radius: 12px;
    font-size: 12px; font-weight: 500;
    cursor: pointer;
    border: 1px solid rgba(194,198,216,0.15);
    transition: all 0.22s cubic-bezier(0.34,1.56,0.64,1);
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  }
  .recent-file-chip:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(255,79,163,0.16); }

  .collection-tile {
    background: ${colors.surfaceContainerLow};
    border-radius: 16px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.28s cubic-bezier(0.34,1.56,0.64,1);
  }
  .collection-tile:hover {
    background: ${colors.surfaceContainerHighest};
    transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.06);
  }
  .collection-tile .mso { font-size: 28px; margin-bottom: 10px; display: block; transition: transform 0.22s cubic-bezier(0.34,1.56,0.64,1); }
  .collection-tile:hover .mso { transform: scale(1.2) rotate(-5deg); }

  .auth-container {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 20px;
    position: relative;
    z-index: 20;
  }

  .auth-card {
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(32px);
    border-radius: 28px;
    padding: 40px;
    width: 100%;
    max-width: 420px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.6);
    animation: slideUp 0.6s cubic-bezier(0.22, 1, 0.36, 1);
  }

  .auth-input-group {
    margin-bottom: 20px;
  }

  .auth-label {
    display: block;
    font-size: 13px;
    font-weight: 700;
    color: ${colors.secondary};
    margin-bottom: 8px;
    margin-left: 4px;
  }

  .auth-input {
    width: 100%;
    background: white;
    border: 1px solid ${colors.surfaceContainerHigh};
    border-radius: 14px;
    padding: 12px 16px;
    font-size: 14px;
    font-family: 'Inter', sans-serif;
    color: ${colors.onSurface};
    outline: none;
    transition: all 0.2s;
  }

  .auth-input:focus {
    border-color: ${colors.primary};
    box-shadow: 0 0 0 4px rgba(255, 79, 163, 0.1);
  }

  .auth-footer {
    margin-top: 24px;
    text-align: center;
    font-size: 13.5px;
    color: ${colors.secondary};
  }

  .auth-link {
    color: ${colors.primary};
    font-weight: 700;
    cursor: pointer;
    text-decoration: none;
    margin-left: 4px;
  }
`;

const navItems = [
  { id: "home", label: "Home", icon: "home" },
  { id: "search", label: "Search", icon: "search" },
  { id: "collections", label: "Collections", icon: "folder_special" },
  { id: "experts", label: "Experts", icon: "psychology" },
  { id: "mindmap", label: "Mind Map", icon: "hub" },
  { id: "dashboard", label: "Dashboard", icon: "dashboard" },
];

function loadExternalScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      if (existing.dataset.loaded === "true") {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error(`Failed to load: ${src}`)), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.addEventListener("load", () => {
      script.dataset.loaded = "true";
      resolve();
    });
    script.addEventListener("error", () => reject(new Error(`Failed to load: ${src}`)));
    document.head.appendChild(script);
  });
}

function VantaGlobeBackground({ enabled }) {
  const elRef = useRef(null);
  const vantaRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const destroyVanta = () => {
      if (vantaRef.current) {
        vantaRef.current.destroy();
        vantaRef.current = null;
      }
    };

    if (!enabled) {
      destroyVanta();
      return undefined;
    }

    const initVanta = async () => {
      try {
        await loadExternalScript("https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js");
        await loadExternalScript("https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.globe.min.js");
        if (cancelled || !elRef.current || !window.VANTA || !window.THREE) return;
        destroyVanta();
        vantaRef.current = window.VANTA.GLOBE({
          el: elRef.current,
          mouseControls: true,
          touchControls: true,
          gyroControls: false,
          minHeight: 200.0,
          minWidth: 200.0,
          scale: 1.0,
          scaleMobile: 1.0,
          color: 0xff4fa3,
          color2: 0xff8bc9,
          backgroundColor: 0xe8e8e8,
          size: 1.1,
        });
      } catch (error) {
        console.warn("Vanta initialization failed.", error);
      }
    };

    initVanta();
    return () => {
      cancelled = true;
      destroyVanta();
    };
  }, [enabled]);

  return <div ref={elRef} className={`tp-vanta-bg${enabled ? " active" : ""}`} aria-hidden />;
}

function InteractiveDotGrid() {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: -10_000, y: -10_000 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const ctx = canvas.getContext("2d");
    let rafId = null;

    const state = {
      width: 0,
      height: 0,
      dpr: Math.max(1, Math.min(2, window.devicePixelRatio || 1)),
      spacing: 28,
      radius: 2.2,
      falloff: 170,
    };

    const resize = () => {
      state.width = window.innerWidth;
      state.height = window.innerHeight;
      state.dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      canvas.width = Math.floor(state.width * state.dpr);
      canvas.height = Math.floor(state.height * state.dpr);
      canvas.style.width = `${state.width}px`;
      canvas.style.height = `${state.height}px`;
      ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    };

    const handleMove = event => {
      mouseRef.current = { x: event.clientX, y: event.clientY };
    };

    const handleLeave = () => {
      mouseRef.current = { x: -10_000, y: -10_000 };
    };

    const draw = () => {
      ctx.clearRect(0, 0, state.width, state.height);

      for (let y = 0; y <= state.height + state.spacing; y += state.spacing) {
        for (let x = 0; x <= state.width + state.spacing; x += state.spacing) {
          const dx = x - mouseRef.current.x;
          const dy = y - mouseRef.current.y;
          const distance = Math.hypot(dx, dy);
          const glow = Math.max(0, 1 - distance / state.falloff);

          const baseRadius = 1.4;
          ctx.beginPath();
          ctx.fillStyle = "rgba(0,0,0,0.12)";
          ctx.arc(x, y, baseRadius, 0, Math.PI * 2);
          ctx.fill();

          if (glow > 0) {
            const intensity = glow * glow;
            const accentRadius = baseRadius + 1.1 + intensity * state.radius;

            ctx.beginPath();
            ctx.fillStyle = `rgba(255,79,163,${0.2 + intensity * 0.75})`;
            ctx.shadowColor = `rgba(255,79,163,${0.25 + intensity * 0.7})`;
            ctx.shadowBlur = 10 + intensity * 24;
            ctx.arc(x, y, accentRadius, 0, Math.PI * 2);
            ctx.fill();

            ctx.beginPath();
            ctx.fillStyle = `rgba(255,156,208,${0.12 + intensity * 0.38})`;
            ctx.shadowColor = "transparent";
            ctx.arc(x, y, accentRadius + 1.8, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }

      ctx.shadowColor = "transparent";
      ctx.shadowBlur = 0;
      rafId = window.requestAnimationFrame(draw);
    };

    resize();
    draw();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseleave", handleLeave);

    return () => {
      if (rafId) window.cancelAnimationFrame(rafId);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseleave", handleLeave);
    };
  }, []);

  return <canvas ref={canvasRef} className="tp-dot-grid" aria-hidden />;
}

// ===================== LOADING SCREEN =====================
function LoadingScreen({ onDone }) {
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState(0);
  const steps = ["Indexing your workspace...", "Mapping knowledge graph...", "Curating results...", "Almost there..."];

  useEffect(() => {
    const t = setInterval(() => {
      setProgress(p => {
        const next = p + Math.random() * 14 + 4;
        if (next >= 100) { clearInterval(t); setTimeout(onDone, 500); return 100; }
        return next;
      });
    }, 250);
    const s = setInterval(() => setStep(x => Math.min(x + 1, steps.length - 1)), 900);
    return () => { clearInterval(t); clearInterval(s); };
  }, []);

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: colors.surface,
      display: "flex", alignItems: "center", justifyContent: "center",
      flexDirection: "column",
      animation: progress >= 100 ? "fadeOut 0.5s ease forwards" : undefined,
    }}>
      <style>{`@keyframes fadeOut { to { opacity: 0; pointer-events: none; } }`}</style>

      {/* Atmospheric orbs */}
      <div className="glow-orb" style={{ width: 600, height: 600, background: "rgba(255,79,163,0.06)", top: "-15%", right: "-10%" }} />
      <div className="glow-orb" style={{ width: 400, height: 400, background: "rgba(80,95,118,0.05)", bottom: "-10%", left: "5%" }} />

      {/* Orbital rings */}
      <div style={{ position: "relative", width: 220, height: 220, marginBottom: 48 }}>
        <div style={{
          position: "absolute", inset: 0, borderRadius: "50%",
          border: "1.5px dashed rgba(255,79,163,0.15)",
          animation: "orbitSpin 18s linear infinite"
        }}>
          <div style={{
            position: "absolute", top: -5, left: "50%", marginLeft: -5,
            width: 10, height: 10, borderRadius: "50%",
            background: colors.primary, boxShadow: "0 0 0 3px rgba(255,79,163,0.2)"
          }} />
        </div>
        <div style={{
          position: "absolute", inset: 28, borderRadius: "50%",
          border: "1.5px dashed rgba(255,79,163,0.2)",
          animation: "orbitSpin 10s linear infinite reverse"
        }}>
          <div style={{
            position: "absolute", bottom: -5, left: "50%", marginLeft: -5,
            width: 8, height: 8, borderRadius: "50%",
            background: colors.primaryContainer, boxShadow: "0 0 0 3px rgba(255,120,191,0.2)"
          }} />
        </div>

        {/* Center logo */}
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{
            width: 100, height: 100, borderRadius: "50%",
            background: "linear-gradient(135deg, " + colors.primary + ", " + colors.primaryContainer + ")",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 8px 32px rgba(255,79,163,0.35)",
            animation: "pulse-ring 2.5s ease infinite",
          }}>
            <span className="mso filled" style={{ color: "white", fontSize: 38 }}>auto_awesome</span>
          </div>
        </div>
      </div>

      <h2 className="h-headline" style={{ fontSize: 28, fontWeight: 800, color: colors.onSurface, marginBottom: 8 }}>
        Curating your <span style={{ color: colors.primary, fontStyle: "italic" }}>library</span>
      </h2>
      <p style={{ fontSize: 13, color: colors.secondary, marginBottom: 32, height: 18, transition: "all 0.3s" }}>
        {steps[step]}
      </p>

      <div style={{ width: 260, marginBottom: 14 }}>
        <div className="loading-progress" style={{ height: 4 }}>
          <div style={{
            position: "absolute", top: 0, left: 0, height: "100%",
            width: progress + "%",
            background: "linear-gradient(90deg, " + colors.primary + ", " + colors.primaryContainer + ")",
            borderRadius: 99,
            transition: "width 0.3s ease",
          }} />
        </div>
      </div>

      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        background: "rgba(255,255,255,0.7)", backdropFilter: "blur(16px)",
        borderRadius: 99, padding: "7px 16px",
        border: "1px solid rgba(255,79,163,0.1)",
      }}>
        <div style={{
          width: 7, height: 7, borderRadius: "50%",
          background: colors.primary,
          animation: "pulse-ring 1.5s ease infinite",
        }} />
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: colors.secondary }}>
          Deep Indexing Active
        </span>
      </div>

      {/* Floating doc traces */}
      <div style={{ position: "fixed", bottom: 48, right: 48, opacity: 0.35 }}>
        {[{ r: "8deg", tx: 16, icon: "description", bg: "#eff3ff" }, { r: "-5deg", tx: -24, icon: "picture_as_pdf", bg: "#fff1f0" }].map((d, i) => (
          <div key={i} style={{
            background: "white", borderRadius: 14, padding: 14, marginBottom: 10,
            transform: `rotate(${d.r}) translateX(${d.tx}px)`,
            animation: `floatCard ${3 + i * 0.5}s ease-in-out infinite`,
            "--r": d.r,
            boxShadow: "0 3px 12px rgba(0,0,0,0.08)",
          }}>
            <span className="mso filled" style={{ color: colors.primary, display: "block", marginBottom: 6 }}>{d.icon}</span>
            <div style={{ height: 6, width: 56, background: colors.surfaceContainerHigh, borderRadius: 99 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ===================== SIDEBAR =====================
function Sidebar({ page, setPage, onLogout, role }) {
  return (
    <aside className="tp-sidebar">
      <div className="tp-logo-area">
        <div className="tp-logo-icon">
          <span className="mso filled" style={{ fontSize: 20 }}>auto_awesome</span>
        </div>
        <div className="tp-logo-text">
          <h1>TracePath</h1>
          <p>{role === "admin" ? "Admin Console" : "Premium Curator"}</p>
        </div>
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1 }}>
        {navItems.map((item, i) => (
          <button
            key={item.id}
            className={"tp-nav-item" + (page === item.id ? " active" : "")}
            style={{ animationDelay: i * 0.04 + "s", animationFillMode: "both" }}
            onClick={() => setPage(item.id)}
          >
            <span className={"mso" + (page === item.id ? " filled" : "")}>{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="tp-nav-footer">
        {role === "admin" && (
          <button className="tp-upload-btn">
            <span className="mso" style={{ fontSize: 18 }}>admin_panel_settings</span>
            Admin Tools
          </button>
        )}
        <button className="tp-upload-btn">
          <span className="mso" style={{ fontSize: 18 }}>cloud_upload</span>
          Upload File
        </button>
        <button className="tp-nav-item" onClick={onLogout}>
          <span className="mso">logout</span>Logout
        </button>
      </div>
    </aside>
  );
}

// ===================== TOPBAR =====================
function Topbar({ page, query, setQuery, setPage, user }) {
  const [driveStatus, setDriveStatus] = useState({ loading: true, ok: false });

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await safeFetchJson(`${API_BASE}/search/gdrive/tokens/status`);
        if (!mounted) return;
        const healthy = Array.isArray(data) ? data.some((t) => t.healthy && !t.expired) : false;
        setDriveStatus({ loading: false, ok: healthy });
      } catch {
        if (!mounted) return;
        try {
          await safeFetchJson(`${API_BASE}/search/gdrive?q=&kind=files&limit=1`);
          if (!mounted) return;
          setDriveStatus({ loading: false, ok: true });
        } catch {
          if (!mounted) return;
          setDriveStatus({ loading: false, ok: false });
        }
      }
    })();
    return () => { mounted = false; };
  }, []);

  return (
    <div className="tp-topbar">
      <div className="tp-search-wrap">
        <span className="mso">search</span>
        <input
          className="tp-search-input"
          placeholder="Search your intelligent library..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && query.trim()) {
              setPage("search");
            }
          }}
        />
      </div>
      <div className="tp-topbar-actions">
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          borderRadius: 999,
          background: "rgba(255,255,255,0.6)",
          fontSize: 10,
          color: colors.secondary,
          border: `1px solid ${colors.surfaceContainerHigh}`,
          marginRight: 12,
        }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: driveStatus.loading ? "#f59e0b" : driveStatus.ok ? "#22c55e" : "#ef4444",
              display: "inline-block",
            }}
          />
          Drive
        </div>
        <div style={{ marginRight: 12, textAlign: 'right' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: colors.onSurface }}>{user?.name}</div>
          <div style={{ fontSize: 10, fontWeight: 700, color: colors.primary, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{user?.role}</div>
        </div>
        <button className="tp-icon-btn"><span className="mso">notifications</span></button>
        <button className="tp-icon-btn"><span className="mso">settings</span></button>
        <div className="tp-avatar">{user?.name?.split(' ').map(n => n[0]).join('')}</div>
      </div>
    </div>
  );
}

// ===================== HOME PAGE =====================
function HomePage({ setPage, query, setQuery }) {
  const [showDrop, setShowDrop] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);

  const recentFiles = [
    { icon: "draft",   color: "#f97316", label: "Brand_Guidelines_v2" },
    { icon: "article", color: colors.primary, label: "Contract_Signed" },
    { icon: "movie",   color: "#a855f7", label: "Promo_Assets" },
    { icon: "folder",  color: "#10b981", label: "Archive_2023" },
  ];

  const quickSearches = [
    { icon: "code",         label: "clawtech" },
    { icon: "description",  label: "README.md" },
    { icon: "history",      label: "Recent commits" },
    { icon: "bug_report",   label: "Open issues" },
  ];

  const stats = [
    { icon: "folder_open",  label: "Repos Indexed",    value: "12",   color: "#4f46e5", bg: "#eef2ff" },
    { icon: "insert_drive_file", label: "Files Found", value: "847",  color: "#059669", bg: "#ecfdf5" },
    { icon: "merge_type",   label: "Connections",       value: "2.3k", color: colors.primary, bg: "#fff0f7" },
    { icon: "bolt",         label: "Last Sync",         value: "Now",  color: "#d97706", bg: "#fffbeb" },
  ];

  const handleSearchEnter = () => {
    if (query.trim()) {
      setShowDrop(false);
      setPage("search");
    }
  };

  return (
    <div className="tp-page" style={{ position: "relative", maxWidth: 900, margin: "0 auto" }}>

      {/* Ambient orb */}
      <div className="glow-orb" style={{ width: 560, height: 560, background: "rgba(255,79,163,0.04)", top: "-10%", right: "-8%", zIndex: 0 }} />
      <div className="glow-orb" style={{ width: 320, height: 320, background: "rgba(79,70,229,0.04)", bottom: "10%", left: "-5%", zIndex: 0 }} />

      {/* ── Hero ── */}
      <div className="home-hero">

        {/* Eyebrow badge */}
        <div className="home-hero-eyebrow">
          <span className="mso filled" style={{ fontSize: 14 }}>auto_awesome</span>
          Intelligent Knowledge Curator
        </div>

        {/* Title */}
        <h1
          className="h-headline home-hero-title"
          style={{ fontSize: 54, fontWeight: 800, letterSpacing: "-0.025em", marginBottom: 10, position: "relative", zIndex: 1 }}
        >
          TracePath
        </h1>

        {/* Subtitle */}
        <p style={{
          fontSize: 15, color: colors.secondary, maxWidth: 420,
          margin: "0 auto 28px", lineHeight: 1.65,
          position: "relative", zIndex: 1,
          animation: "slideUp 0.45s cubic-bezier(0.22,1,0.36,1) 0.1s both",
        }}>
          Search your GitHub repos, files & knowledge graph — all in one place.
        </p>

        {/* Search bar */}
        <div className="search-hero-wrap">
          <div className="search-hero-box">
            <span className="mso" style={{ color: inputFocused ? colors.primary : colors.outline, flexShrink: 0, transition: "color 0.2s", fontSize: 20 }}>search</span>
            <input
              className="home-search-input"
              placeholder="Search repos, files, commits…"
              value={query}
              onChange={e => { setQuery(e.target.value); setShowDrop(e.target.value.length > 0); }}
              onFocus={() => { setInputFocused(true); if (query.trim()) setShowDrop(true); }}
              onBlur={() => { setInputFocused(false); setTimeout(() => setShowDrop(false), 150); }}
              onKeyDown={e => { if (e.key === "Enter") handleSearchEnter(); if (e.key === "Escape") setShowDrop(false); }}
            />
            {query && (
              <button
                onClick={() => { setQuery(""); setShowDrop(false); }}
                style={{ background: "none", border: "none", cursor: "pointer", color: colors.outline, padding: "0 4px", display: "flex", alignItems: "center" }}
              >
                <span className="mso" style={{ fontSize: 18 }}>close</span>
              </button>
            )}
            <button
              className="btn-primary"
              style={{ flexShrink: 0, borderRadius: 12, padding: "9px 18px", fontSize: 13 }}
              onClick={handleSearchEnter}
            >
              <span className="mso filled" style={{ fontSize: 16 }}>bolt</span>
              Search
            </button>
          </div>

          {/* Dropdown — only when user has typed */}
          {showDrop && query.trim() && (
            <div style={{
              position: "absolute", top: "calc(100% + 8px)", left: 0, right: 0,
              background: "rgba(255,255,255,0.97)", backdropFilter: "blur(24px)",
              borderRadius: 16, boxShadow: "0 12px 40px rgba(0,0,0,0.08), 0 2px 8px rgba(255,79,163,0.08)",
              border: "1px solid rgba(194,198,216,0.2)", overflow: "hidden",
              animation: "slideUp 0.22s cubic-bezier(0.22,1,0.36,1)",
              zIndex: 50,
            }}>
              <div style={{ padding: "8px 8px 4px" }}>
                <div style={{ padding: "6px 12px 8px", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: colors.outline }}>
                  Suggested
                </div>
                {[
                  { icon: "code",         bg: "#eef2ff", color: "#4f46e5", name: `Search "${query}" in repos`,      path: "GitHub Repositories" },
                  { icon: "insert_drive_file", bg: "#ecfdf5", color: "#059669", name: `Find files matching "${query}"`, path: "File Metadata" },
                  { icon: "hub",          bg: "#fff0f7", color: colors.primary, name: `Explore "${query}" in graph`,  path: "Knowledge Graph" },
                ].map((item, i) => (
                  <div key={i} className="dropdown-result" onMouseDown={() => { setShowDrop(false); setPage("search"); }}>
                    <div style={{ width: 36, height: 36, borderRadius: 10, background: item.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <span className="mso" style={{ color: item.color, fontSize: 18 }}>{item.icon}</span>
                    </div>
                    <div style={{ flex: 1, textAlign: "left" }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: colors.onSurface }}>{item.name}</div>
                      <div style={{ fontSize: 10.5, color: colors.secondary, textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600, marginTop: 1 }}>{item.path}</div>
                    </div>
                    <span className="mso" style={{ color: colors.outline, fontSize: 16 }}>north_east</span>
                  </div>
                ))}
              </div>
              <div style={{ background: colors.surfaceContainerLow, padding: "8px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 11, color: colors.secondary }}>
                  Press <kbd style={{ background: "white", padding: "1px 6px", borderRadius: 4, border: "1px solid " + colors.outlineVariant, fontSize: 10, fontFamily: "monospace" }}>Enter</kbd> to search
                </span>
                <button style={{ fontSize: 11, color: colors.primary, fontWeight: 700, border: "none", background: "none", cursor: "pointer" }} onMouseDown={() => setPage("search")}>
                  View all results →
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Quick-search hint pills */}
        <div className="search-hint-pills">
          <span style={{ fontSize: 11.5, color: colors.outline, fontWeight: 500 }}>Try:</span>
          {quickSearches.map((qs, i) => (
            <button
              key={i}
              className="search-hint-pill"
              onClick={() => { setQuery(qs.label); setPage("search"); }}
            >
              <span className="mso" style={{ fontSize: 14, color: colors.primary }}>{qs.icon}</span>
              {qs.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Stats row ── */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12,
        marginBottom: 20,
        animation: "slideUp 0.45s cubic-bezier(0.22,1,0.36,1) 0.2s both",
        position: "relative", zIndex: 1,
      }}>
        {stats.map((s, i) => (
          <div key={i} style={{
            background: "rgba(255,255,255,0.65)",
            backdropFilter: "blur(12px)",
            borderRadius: 16,
            padding: "16px 18px",
            border: "1px solid rgba(194,198,216,0.12)",
            display: "flex", alignItems: "center", gap: 12,
            transition: "all 0.22s cubic-bezier(0.34,1.56,0.64,1)",
          }}>
            <div style={{ width: 40, height: 40, borderRadius: 12, background: s.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <span className="mso filled" style={{ color: s.color, fontSize: 20 }}>{s.icon}</span>
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, fontFamily: "'Manrope', sans-serif", color: colors.onSurface, lineHeight: 1.1 }}>{s.value}</div>
              <div style={{ fontSize: 11, color: colors.secondary, fontWeight: 500, marginTop: 2 }}>{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Bento grid ── */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: 14,
        position: "relative", zIndex: 1,
        animation: "slideUp 0.45s cubic-bezier(0.22,1,0.36,1) 0.3s both",
      }}>

        {/* Upload card */}
        <div className="bento-card" onClick={() => setPage("dashboard")}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ width: 46, height: 46, borderRadius: 14, background: "rgba(255,79,163,0.08)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span className="mso filled" style={{ color: colors.primary, fontSize: 22 }}>cloud_upload</span>
            </div>
            <span className="mso" style={{ color: "rgba(255,79,163,0.25)", fontSize: 18 }}>arrow_outward</span>
          </div>
          <div>
            <div className="h-headline" style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>Upload File</div>
            <p style={{ fontSize: 12.5, color: colors.secondary, lineHeight: 1.5 }}>Drag & drop or browse to add documents to your library.</p>
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
            {["PDF", "DOCX", "XLSX"].map(t => (
              <span key={t} style={{ fontSize: 10.5, fontWeight: 700, padding: "3px 9px", borderRadius: 99, background: "rgba(255,79,163,0.07)", color: colors.primary }}>{t}</span>
            ))}
          </div>
        </div>

        {/* Recent files card */}
        <div className="bento-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="h-headline" style={{ fontSize: 15, fontWeight: 700, display: "flex", alignItems: "center", gap: 7 }}>
              <span className="mso filled" style={{ color: colors.primary, fontSize: 18 }}>history</span>
              Recent Files
            </div>
            <button style={{ fontSize: 12, fontWeight: 700, color: colors.primary, border: "none", background: "none", cursor: "pointer", opacity: 0.8 }}>See all</button>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {recentFiles.map((f, i) => (
              <div key={i} className="recent-file-chip">
                <span className="mso" style={{ color: f.color, fontSize: 16 }}>{f.icon}</span>
                <span style={{ fontSize: 12 }}>{f.label}</span>
              </div>
            ))}
          </div>
          <div style={{ borderTop: "1px solid " + colors.surfaceContainerHigh, paddingTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: colors.secondary }}>4 items · Updated just now</span>
            <button
              style={{ fontSize: 12, fontWeight: 600, color: colors.primary, border: "none", background: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
              onClick={() => setPage("search")}
            >
              <span className="mso" style={{ fontSize: 16 }}>search</span> Search all
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


// ===================== SEARCH PAGE =====================
function SearchPage({ setPage, query, githubOwner, githubRepo }) {
  const [activeType, setActiveType] = useState("All");
  const [results, setResults] = useState([]);
  const [count, setCount] = useState(0);
  const [status, setStatus] = useState({ loading: false, error: null, sourceErrors: [] });

  const types = ["All", "DOCX", "Excel", "PDF", "PPTX"];

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setCount(0);
      setStatus({ loading: false, error: null, sourceErrors: [] });
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        setStatus({ loading: true, error: null, sourceErrors: [] });
        const scopeRepo = githubOwner && githubRepo ? `&github_repo=${encodeURIComponent(`${githubOwner}/${githubRepo}`)}` : "";
        const scopeOwner = githubOwner ? `&github_owner=${encodeURIComponent(githubOwner)}` : "";
        const data = await safeFetchJson(
          `${API_BASE}/search/unified?q=${encodeURIComponent(query)}&per_source=8${scopeRepo}${scopeOwner}`,
          { signal: controller.signal }
        );
        setResults(Array.isArray(data?.results) ? data.results : []);
        setCount(typeof data?.count === "number" ? data.count : (data?.results?.length || 0));
        setStatus({
          loading: false,
          error: data?.errors?.length ? "Some sources could not be reached." : null,
          sourceErrors: Array.isArray(data?.errors) ? data.errors : [],
        });
      } catch (err) {
        if (err?.name !== "AbortError") {
          setStatus({ loading: false, error: err?.message || "Backend unavailable.", sourceErrors: [] });
        }
      }
    }, 320);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const getExtension = (title = "") => {
    const parts = title.split(".");
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : "";
  };

  const isTypeMatch = (title) => {
    if (activeType === "All") return true;
    const ext = getExtension(title);
    if (activeType === "DOCX") return ["doc", "docx"].includes(ext);
    if (activeType === "Excel") return ["xls", "xlsx", "csv"].includes(ext);
    if (activeType === "PDF") return ["pdf"].includes(ext);
    if (activeType === "PPTX") return ["ppt", "pptx"].includes(ext);
    return true;
  };

  const filteredResults = results.filter((r) => isTypeMatch(r?.title || ""));
  const displayCount = activeType === "All" ? count : filteredResults.length;

  const sourceStyles = {
    github: { icon: "code", bg: "#eef2ff", color: "#4f46e5" },
    slack: { icon: "forum", bg: "#fff7ed", color: "#f97316" },
    gdrive: { icon: "cloud", bg: "#ecfdf3", color: "#16a34a" },
    default: { icon: "description", bg: "#f4f4f5", color: colors.primary },
  };

  return (
    <div className="tp-page">
      <div style={{ display: "flex", gap: 28 }}>
        {/* Filters */}
        <div style={{ width: 210, flexShrink: 0 }}>
          <div className="animate-slide-up stagger-1" style={{ marginBottom: 28 }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: colors.secondary, marginBottom: 12 }}>File Types</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {types.map(t => (
                <button key={t} className={"chip " + (activeType === t ? "chip-active" : "chip-default")} onClick={() => setActiveType(t)}>
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="animate-slide-up stagger-2" style={{ marginBottom: 28 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: colors.secondary }}>Last Modified</div>
              <span style={{ fontSize: 10, fontWeight: 700, color: colors.primary, background: colors.primaryFixed, padding: "2px 8px", borderRadius: 99 }}>90 Days</span>
            </div>
            <div style={{ padding: "0 4px" }}>
              <div style={{ height: 5, background: colors.surfaceContainerHighest, borderRadius: 99, position: "relative" }}>
                <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: "67%", background: colors.primary, borderRadius: 99 }} />
                <div style={{ position: "absolute", left: "67%", top: "50%", transform: "translate(-50%, -50%)", width: 14, height: 14, background: "white", border: "2px solid " + colors.primary, borderRadius: "50%", boxShadow: "0 2px 6px rgba(255,79,163,0.25)" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 10, color: colors.secondary, fontWeight: 500 }}>
                <span>Anytime</span><span>Today</span>
              </div>
            </div>
          </div>

          <div className="animate-slide-up stagger-3" style={{ borderTop: "1px solid " + colors.surfaceContainerHigh, paddingTop: 22 }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: colors.secondary, marginBottom: 12 }}>Sources</div>
            {["GitHub", "Slack", "Google Drive"].map(a => (
              <label key={a} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, cursor: "pointer" }}>
                <div style={{ width: 16, height: 16, border: "1.5px solid " + colors.outline, borderRadius: 5, flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: colors.secondary }}>{a}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Results */}
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 22, animation: "slideUp 0.4s cubic-bezier(0.22,1,0.36,1) both" }}>
            <div>
              <h2 className="h-headline" style={{ fontSize: 22, fontWeight: 800 }}>
                {query.trim() ? `${displayCount} Results for "${query}"` : "Enter a search query"}
              </h2>
              <p style={{ fontSize: 13, color: colors.secondary, marginTop: 3 }}>
                {status.loading ? "Searching across connected sources..." : "Discovering intellectual assets across your workspace."}
              </p>
              {githubOwner && githubRepo ? (
                <p style={{ fontSize: 11, color: colors.secondary, marginTop: 6 }}>
                  GitHub scope: {githubOwner}/{githubRepo}
                </p>
              ) : githubOwner ? (
                <p style={{ fontSize: 11, color: colors.secondary, marginTop: 6 }}>
                  GitHub scope: {githubOwner}/*
                </p>
              ) : null}
              {status.error && (
                <p style={{ fontSize: 11, color: "#dc2626", marginTop: 6 }}>{status.error}</p>
              )}
              {status.sourceErrors?.length ? (
                <p style={{ fontSize: 11, color: colors.secondary, marginTop: 4 }}>
                  {status.sourceErrors.map(e => `${e.source}: ${e.error}`).join(" | ")}
                </p>
              ) : null}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: colors.secondary }}>
              Sort by: <button style={{ color: colors.onSurface, border: "none", background: "none", cursor: "pointer", fontWeight: 700, display: "flex", alignItems: "center", gap: 2, fontSize: 12 }}>Relevance <span className="mso" style={{ fontSize: 16 }}>expand_more</span></button>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {status.loading && (
              <div className="result-card" style={{ padding: 24, textAlign: "center" }}>
                <div style={{ fontSize: 13, color: colors.secondary }}>Searching the connected graph...</div>
              </div>
            )}

            {!status.loading && filteredResults.length === 0 && query.trim() && (
              <div className="result-card" style={{ padding: 24, textAlign: "center" }}>
                <div style={{ fontSize: 13, color: colors.secondary }}>No matches found. Try a broader keyword.</div>
              </div>
            )}

            {!query.trim() && (
              <div className="result-card" style={{ padding: 24, textAlign: "center" }}>
                <div style={{ fontSize: 13, color: colors.secondary }}>Type in the search bar to begin.</div>
              </div>
            )}

            {filteredResults.map((r, i) => {
              const stylePack = sourceStyles[r.source] || sourceStyles.default;
              return (
                <div
                  key={`${r.source}-${r.title}-${i}`}
                  className="result-card"
                  style={{ animationDelay: i * 0.08 + "s" }}
                >
                  <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
                    <div className="file-icon-wrap" style={{ background: stylePack.bg }}>
                      <span className="mso filled" style={{ color: stylePack.color, fontSize: 24 }}>{stylePack.icon}</span>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <h3 className="h-headline" style={{ fontSize: 14, fontWeight: 700, color: colors.onSurface, flex: 1, marginRight: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {r.title || "Untitled result"}
                        </h3>
                        {r.url ? (
                          <a
                            href={r.url}
                            target="_blank"
                            rel="noreferrer"
                            style={{ background: "none", border: "none", cursor: "pointer", color: colors.secondary, flexShrink: 0, textDecoration: "none" }}
                          >
                            <span className="mso">open_in_new</span>
                          </a>
                        ) : (
                          <button style={{ background: "none", border: "none", cursor: "pointer", color: colors.secondary, flexShrink: 0 }}>
                            <span className="mso">more_vert</span>
                          </button>
                        )}
                      </div>
                      <p style={{ fontSize: 12.5, color: colors.secondary, marginTop: 6, lineHeight: 1.6, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                        {r.snippet || "No snippet available for this match."}
                      </p>
                      <div style={{ display: "flex", gap: 18, marginTop: 12, flexWrap: "wrap" }}>
                        {[["hub", (r.source || "source").toUpperCase()], ["sell", r.kind || "item"], ["link", r.meta?.repo || r.meta?.mime || r.meta?.team || "Metadata"]].map(([ic, val]) => (
                          <div key={ic} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                            <span className="mso" style={{ fontSize: 14, color: colors.outline }}>{ic}</span>
                            <span style={{ fontSize: 11.5, color: colors.secondary, fontWeight: 500 }}>{val}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ display: "flex", justifyContent: "center", padding: "32px 0", animation: "slideUp 0.4s cubic-bezier(0.22,1,0.36,1) 0.3s both" }}>
            <button className="btn-secondary" style={{ borderRadius: 16, padding: "12px 24px" }}>
              Load more discoveries
              <span className="mso" style={{ fontSize: 18 }}>arrow_downward</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ===================== MINDMAP PAGE =====================
function MindMapPage({ owner, repo, setOwner, setRepo }) {
  const [repos, setRepos] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [childNodes, setChildNodes] = useState([]);
  const [status, setStatus] = useState({ loading: true, error: null, childLoading: false });

  // Fetch repo list on mount
  useEffect(() => {
    (async () => {
      try {
        const scope = owner ? `?user=${encodeURIComponent(owner)}` : "";
        const data = await safeFetchJson(`${API_BASE}/github/repos/list${scope}`);
        setRepos(Array.isArray(data?.repos) ? data.repos : []);
        setStatus({ loading: false, error: data?.error || null, childLoading: false });
      } catch (e) {
        setStatus({ loading: false, error: e.message, childLoading: false });
      }
    })();
  }, [owner]);

  // Fetch tree when a repo is selected
  const expandRepo = async (repo) => {
    if (selectedRepo?.full_name === repo.full_name) {
      setSelectedRepo(null);
      setChildNodes([]);
      setRepo("");
      return;
    }
    setSelectedRepo(repo);
    setRepo(repo.name || "");
    setChildNodes([]);
    setStatus(s => ({ ...s, childLoading: true }));
    try {
      const data = await safeFetchJson(
        `${API_BASE}/github/repos/tree?full_name=${encodeURIComponent(repo.full_name)}`
      );
      setChildNodes(Array.isArray(data?.nodes) ? data.nodes : []);
    } catch (e) {
      // silently fail, just show empty children
    }
    setStatus(s => ({ ...s, childLoading: false }));
  };

  // ── Layout math ──────────────────────────────────────────────────────────
  const LANG_COLORS = {
    JavaScript: "#f7df1e", TypeScript: "#3178c6", Python: "#3572A5",
    Java: "#b07219", "C++": "#f34b7d", C: "#555", Go: "#00ADD8",
    Rust: "#dea584", HTML: "#e34c26", CSS: "#563d7c", default: colors.primary,
  };

  const visibleRepos = repos;
  const repoAngle = (i) => (-Math.PI / 2) + (Math.PI * 2 * i) / visibleRepos.length;

  // Repo ring: cx/cy as % of 800x600 canvas
  const W = 800, H = 600, cx = W / 2, cy = H / 2;
  const repoCount = Math.max(visibleRepos.length, 1);
  const R_REPO = Math.min(260, 140 + repoCount * 3);
  const repoPos = (i) => ({
    x: cx + R_REPO * Math.cos(repoAngle(i)),
    y: cy + R_REPO * Math.sin(repoAngle(i)),
  });

  // Child ring around selected repo node
  const selectedIdx = selectedRepo ? visibleRepos.findIndex(r => r.full_name === selectedRepo.full_name) : -1;
  const selPos = selectedIdx >= 0 ? repoPos(selectedIdx) : null;
  const R_CHILD = 90;
  const visibleChildren = childNodes.slice(0, 12);
  const childPos = (i) => ({
    x: selPos.x + R_CHILD * Math.cos(-Math.PI / 2 + (Math.PI * 2 * i) / visibleChildren.length),
    y: selPos.y + R_CHILD * Math.sin(-Math.PI / 2 + (Math.PI * 2 * i) / visibleChildren.length),
  });

  const langColor = (lang) => LANG_COLORS[lang] || LANG_COLORS.default;

  return (
    <div className="tp-page" style={{ padding: 0, display: "flex", flexDirection: "column", height: "calc(100vh - 62px)", overflow: "hidden", position: "relative" }}>

      {/* Top info bar */}
      <div style={{
        position: "absolute", top: 16, left: 16, right: 16, zIndex: 20,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "rgba(255,255,255,0.9)", backdropFilter: "blur(18px)",
        borderRadius: 18, padding: "12px 20px",
        boxShadow: "0 4px 24px rgba(255,79,163,0.1)",
        border: "1px solid rgba(255,79,163,0.1)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="mso filled" style={{ color: colors.primary, fontSize: 22 }}>account_tree</span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 800, color: colors.onSurface }}>Repository Mind Map</div>
            <div style={{ fontSize: 11, color: colors.secondary }}>
              {status.loading ? "Loading repos…" : `${repos.length} repos · click to expand files`}
            </div>
          </div>
        </div>
        {selectedRepo && (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: colors.primary }}>{selectedRepo.name}</div>
            {status.childLoading && (
              <span style={{ fontSize: 11, color: colors.secondary }}>Loading tree…</span>
            )}
            <button
              onClick={() => { setSelectedRepo(null); setChildNodes([]); }}
              style={{ background: colors.surfaceContainerLow, border: "none", borderRadius: 99, padding: "4px 12px", fontSize: 11, fontWeight: 700, cursor: "pointer", color: colors.secondary }}
            >
              ✕ Close
            </button>
          </div>
        )}
        {!selectedRepo && !status.loading && (
          <div style={{ fontSize: 11, color: colors.secondary, background: colors.surfaceContainerLow, padding: "6px 14px", borderRadius: 99 }}>
            <span className="mso" style={{ fontSize: 14, verticalAlign: "middle", marginRight: 4 }}>touch_app</span>
            Click a repo to explore
          </div>
        )}
      </div>

      {/* SVG canvas */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
      >
        {/* Edges: center → repo */}
        {visibleRepos.map((r, i) => {
          const pos = repoPos(i);
          const isSelected = selectedRepo?.full_name === r.full_name;
          return (
            <line key={r.id}
              x1={cx} y1={cy} x2={pos.x} y2={pos.y}
              stroke={isSelected ? colors.primary : colors.outlineVariant}
              strokeWidth={isSelected ? 2 : 1}
              strokeDasharray={isSelected ? "none" : "5,4"}
              opacity={isSelected ? 0.8 : 0.4}
            />
          );
        })}

        {/* Edges: selected repo → children */}
        {selPos && visibleChildren.map((c, i) => {
          const cp = childPos(i);
          return (
            <line key={c.path}
              x1={selPos.x} y1={selPos.y} x2={cp.x} y2={cp.y}
              stroke={c.type === "dir" ? "#6366f1" : "#16a34a"}
              strokeWidth={1}
              strokeDasharray="4,3"
              opacity={0.6}
            />
          );
        })}
      </svg>

      {/* Center node */}
      <div style={{
        position: "absolute",
        left: `${cx / W * 100}%`, top: `${cy / H * 100}%`,
        transform: "translate(-50%, -50%)",
        zIndex: 10,
      }}>
        <div
          onClick={() => { setSelectedRepo(null); setChildNodes([]); }}
          style={{
            width: 90, height: 90, borderRadius: "50%",
            background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryContainer})`,
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            color: "white", cursor: "pointer",
            boxShadow: "0 8px 32px rgba(255,79,163,0.4), 0 0 0 8px rgba(255,79,163,0.1)",
            transition: "transform 0.2s",
          }}
        >
          <span className="mso filled" style={{ color: "white", fontSize: 28 }}>workspaces</span>
          <span style={{ fontSize: 9, fontWeight: 700, marginTop: 2 }}>My Repos</span>
        </div>
      </div>

      {/* Repo nodes */}
      {visibleRepos.map((r, i) => {
        const pos = repoPos(i);
        const isSelected = selectedRepo?.full_name === r.full_name;
        const lc = langColor(r.language);
        const baseSize = repoCount > 28 ? 44 : repoCount > 18 ? 52 : 60;
        const nodeSize = isSelected ? baseSize + 12 : baseSize;
        return (
          <div key={r.id} style={{
            position: "absolute",
            left: `${pos.x / W * 100}%`, top: `${pos.y / H * 100}%`,
            transform: "translate(-50%, -50%)",
            zIndex: 10,
          }}>
            <div
              onClick={() => expandRepo(r)}
              title={r.description || r.name}
              style={{
                width: nodeSize,
                height: nodeSize,
                borderRadius: "50%",
                background: isSelected ? `linear-gradient(135deg, ${lc}22, ${lc}44)` : "rgba(255,255,255,0.9)",
                border: `2px solid ${isSelected ? lc : "rgba(194,198,216,0.3)"}`,
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                cursor: "pointer",
                boxShadow: isSelected
                  ? `0 6px 24px ${lc}44, 0 0 0 4px ${lc}22`
                  : "0 3px 12px rgba(0,0,0,0.08)",
                transition: "all 0.25s cubic-bezier(0.34,1.56,0.64,1)",
                backdropFilter: "blur(12px)",
              }}
            >
              <span className="mso filled" style={{ color: lc, fontSize: repoCount > 28 ? 16 : 20, lineHeight: 1 }}>code</span>
              <span style={{
                fontSize: repoCount > 28 ? 7 : 8, fontWeight: 700, textAlign: "center", maxWidth: 56,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                color: colors.onSurface, marginTop: 2,
                padding: "0 4px",
              }}>{r.name}</span>
              {r.language && (
                <span style={{ fontSize: repoCount > 28 ? 6 : 7, color: lc, fontWeight: 700, marginTop: 1 }}>{r.language}</span>
              )}
            </div>
          </div>
        );
      })}

      {/* Child nodes (file tree) */}
      {selPos && visibleChildren.map((c, i) => {
        const cp = childPos(i);
        const isDir = c.type === "dir";
        return (
          <div key={c.path} style={{
            position: "absolute",
            left: `${cp.x / W * 100}%`, top: `${cp.y / H * 100}%`,
            transform: "translate(-50%, -50%)",
            zIndex: 11,
          }}>
            <a
              href={`${selectedRepo.html_url}/${isDir ? "tree" : "blob"}/${selectedRepo.default_branch}/${c.path}`}
              target="_blank" rel="noreferrer"
              title={c.path}
              style={{ textDecoration: "none" }}
            >
              <div style={{
                width: 48, height: 48, borderRadius: "50%",
                background: isDir ? "#eef2ff" : "#ecfdf5",
                border: `1.5px solid ${isDir ? "#a5b4fc" : "#6ee7b7"}`,
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                cursor: "pointer",
                boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                transition: "all 0.2s cubic-bezier(0.34,1.56,0.64,1)",
              }}>
                <span className="mso filled" style={{ fontSize: 16, color: isDir ? "#6366f1" : "#16a34a" }}>
                  {isDir ? "folder" : "description"}
                </span>
                <span style={{
                  fontSize: 7, fontWeight: 700, color: isDir ? "#4f46e5" : "#15803d",
                  maxWidth: 42, textAlign: "center",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  padding: "0 2px",
                }}>{c.path}</span>
              </div>
            </a>
          </div>
        );
      })}

      {/* Legend */}
      <div style={{
        position: "absolute", bottom: 20, right: 20, zIndex: 20,
        background: "rgba(255,255,255,0.9)", backdropFilter: "blur(16px)",
        borderRadius: 14, padding: "12px 16px",
        boxShadow: "0 4px 20px rgba(0,0,0,0.07)",
        border: "1px solid rgba(194,198,216,0.15)",
        fontSize: 11, color: colors.secondary,
        display: "flex", flexDirection: "column", gap: 6,
      }}>
        <div style={{ fontWeight: 700, color: colors.onSurface, marginBottom: 2 }}>Legend</div>
        {[
          { color: colors.primary, label: "Workspace center" },
          { color: "#aaa", label: "Repository" },
          { color: "#6366f1", label: "Folder" },
          { color: "#16a34a", label: "File" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: color, flexShrink: 0 }} />
            {label}
          </div>
        ))}
      </div>

      {/* Loading overlay */}
      {status.loading && (
        <div style={{
          position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(255,255,255,0.7)", backdropFilter: "blur(8px)", zIndex: 50,
        }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ width: 48, height: 48, borderRadius: "50%", border: `3px solid ${colors.primary}`, borderTopColor: "transparent", animation: "orbitSpin 0.8s linear infinite", margin: "0 auto 12px" }} />
            <div style={{ fontSize: 13, color: colors.secondary }}>Loading your repositories…</div>
          </div>
        </div>
      )}
    </div>
  );
}

// ===================== DASHBOARD PAGE =====================
function DashboardPage({ githubOwner }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const scope = githubOwner ? `?user=${encodeURIComponent(githubOwner)}` : "";
        const d = await safeFetchJson(`${API_BASE}/github/dashboard${scope}`);
        if (d?.error) setError(d.error);
        else setData(d);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [githubOwner]);

  const LANG_COLORS = {
    JavaScript: "#f7df1e", TypeScript: "#3178c6", Python: "#3572A5",
    Java: "#b07219", Go: "#00ADD8", Rust: "#dea584",
    HTML: "#e34c26", CSS: "#563d7c", "C++": "#f34b7d",
  };

  const relativeTime = (dateStr) => {
    if (!dateStr) return "";
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  if (loading) return (
    <div className="tp-page" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 400 }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ width: 48, height: 48, borderRadius: "50%", border: `3px solid ${colors.primary}`, borderTopColor: "transparent", animation: "orbitSpin 0.8s linear infinite", margin: "0 auto 12px" }} />
        <div style={{ fontSize: 13, color: colors.secondary }}>Loading GitHub dashboard…</div>
      </div>
    </div>
  );

  if (error) return (
    <div className="tp-page">
      <div className="card" style={{ textAlign: "center", padding: 32 }}>
        <span className="mso" style={{ fontSize: 32, color: "#dc2626", marginBottom: 12, display: "block" }}>error</span>
        <div style={{ fontWeight: 700, marginBottom: 6 }}>GitHub connection failed</div>
        <div style={{ fontSize: 12, color: colors.secondary }}>{error}</div>
        <div style={{ fontSize: 11, color: colors.secondary, marginTop: 8 }}>Make sure GITHUB_TOKEN is set in your .env file.</div>
      </div>
    </div>
  );

  const user = data?.user || {};
  const stats = data?.stats || {};
  const langs = data?.languages || [];
  const repos = data?.repos || [];
  const commits = data?.recent_commits || [];

  const statCards = [
    { icon: "code", label: "Total Repos",   value: stats.total_repos || 0,        color: "#4f46e5", bg: "#eef2ff" },
    { icon: "star", label: "Total Stars",   value: stats.total_stars || 0,        color: "#d97706", bg: "#fffbeb" },
    { icon: "fork_right", label: "Total Forks", value: stats.total_forks || 0,   color: "#059669", bg: "#ecfdf5" },
    { icon: "lock", label: "Private Repos", value: stats.private_repos || 0,      color: colors.primary, bg: "#fff0f7" },
  ];

  return (
    <div className="tp-page">

      {/* ── Hero: User profile ── */}
      <div className="card animate-slide-up stagger-1" style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 20, padding: "20px 24px" }}>
        {user.avatar_url && (
          <img src={user.avatar_url} alt={user.login}
            style={{ width: 64, height: 64, borderRadius: "50%", flexShrink: 0, border: `2px solid ${colors.primary}22` }} />
        )}
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
            <h1 className="h-headline" style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>
              {user.name || user.login}
            </h1>
            <span style={{ fontSize: 13, color: colors.secondary }}>@{user.login}</span>
          </div>
          {user.bio && <p style={{ fontSize: 13, color: colors.secondary, marginTop: 4, lineHeight: 1.5 }}>{user.bio}</p>}
          <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap" }}>
            {[
              ["people", `${user.followers} followers`],
              ["person_add", `${user.following} following`],
              ["folder_open", `${user.public_repos} public repos`],
            ].map(([icon, label]) => (
              <span key={label} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: colors.secondary }}>
                <span className="mso" style={{ fontSize: 15, color: colors.outline }}>{icon}</span>{label}
              </span>
            ))}
          </div>
        </div>
        <a href={user.html_url} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
          <button className="btn-secondary" style={{ fontSize: 12 }}>
            <span className="mso" style={{ fontSize: 16 }}>open_in_new</span>GitHub Profile
          </button>
        </a>
      </div>

      {/* ── Stats row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 20 }}>
        {statCards.map((s, i) => (
          <div key={i} className="card animate-slide-up" style={{ animationDelay: i * 0.07 + "s", padding: "16px 18px", display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 42, height: 42, borderRadius: 13, background: s.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <span className="mso filled" style={{ color: s.color, fontSize: 20 }}>{s.icon}</span>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1 }}>{s.value}</div>
              <div style={{ fontSize: 11, color: colors.secondary, fontWeight: 500, marginTop: 2 }}>{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16, marginBottom: 20 }}>

        {/* ── Recent repos ── */}
        <div className="card animate-slide-up stagger-2" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "16px 20px 12px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${colors.surfaceContainerHigh}` }}>
            <span className="h-headline" style={{ fontWeight: 700, fontSize: 15, display: "flex", alignItems: "center", gap: 7 }}>
              <span className="mso filled" style={{ color: colors.primary, fontSize: 18 }}>source</span>
              Repositories
            </span>
            <a href={`https://github.com/${user.login}?tab=repositories`} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
              <button style={{ fontSize: 11, color: colors.primary, fontWeight: 700, border: "none", background: "none", cursor: "pointer" }}>
                View all →
              </button>
            </a>
          </div>
          <div style={{ maxHeight: 340, overflowY: "auto" }}>
            {repos.slice(0, 8).map((r, i) => (
              <a key={i} href={r.html_url} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
                <div style={{
                  display: "flex", alignItems: "center", padding: "12px 20px", gap: 12,
                  borderBottom: i < 7 ? `1px solid ${colors.surfaceContainerHigh}` : "none",
                  transition: "background 0.15s",
                  cursor: "pointer",
                }}
                  onMouseEnter={e => e.currentTarget.style.background = colors.surfaceContainerLow}
                  onMouseLeave={e => e.currentTarget.style.background = ""}
                >
                  <div style={{ width: 34, height: 34, borderRadius: 10, background: r.private ? "#fff0f7" : "#eef2ff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <span className="mso filled" style={{ fontSize: 17, color: r.private ? colors.primary : "#4f46e5" }}>
                      {r.private ? "lock" : "code"}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: colors.onSurface, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.name}
                    </div>
                    <div style={{ fontSize: 11, color: colors.secondary, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.description || "No description"}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 10, flexShrink: 0, alignItems: "center" }}>
                    {r.language && (
                      <span style={{ fontSize: 10, fontWeight: 700, color: LANG_COLORS[r.language] || colors.secondary }}>
                        {r.language}
                      </span>
                    )}
                    {r.stars > 0 && (
                      <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 11, color: colors.secondary }}>
                        <span className="mso" style={{ fontSize: 13 }}>star</span>{r.stars}
                      </span>
                    )}
                    <span style={{ fontSize: 10, color: colors.outline }}>{relativeTime(r.updated_at)}</span>
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>

        {/* ── Language breakdown ── */}
        <div className="card animate-slide-up stagger-3" style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16, display: "flex", alignItems: "center", gap: 7 }}>
            <span className="mso filled" style={{ color: colors.primary, fontSize: 18 }}>bar_chart</span>
            Top Languages
          </div>
          {langs.length === 0 && <div style={{ fontSize: 12, color: colors.secondary }}>No language data available.</div>}
          {langs.map(({ name, count }, i) => {
            const maxCount = langs[0]?.count || 1;
            return (
              <div key={name} style={{ marginBottom: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 5 }}>
                  <span style={{ fontWeight: 700, color: colors.onSurface, display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ width: 10, height: 10, borderRadius: "50%", background: LANG_COLORS[name] || colors.outline, display: "inline-block" }} />
                    {name}
                  </span>
                  <span style={{ color: colors.secondary, fontWeight: 500 }}>{count} repo{count > 1 ? "s" : ""}</span>
                </div>
                <div style={{ height: 6, background: colors.surfaceContainerLow, borderRadius: 99, overflow: "hidden" }}>
                  <div style={{
                    height: "100%",
                    width: `${(count / maxCount) * 100}%`,
                    background: LANG_COLORS[name] || colors.primary,
                    borderRadius: 99,
                    transition: "width 0.6s cubic-bezier(0.22,1,0.36,1)",
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Recent commits ── */}
      <div className="card animate-slide-up stagger-4" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px 12px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${colors.surfaceContainerHigh}` }}>
          <span className="h-headline" style={{ fontWeight: 700, fontSize: 15, display: "flex", alignItems: "center", gap: 7 }}>
            <span className="mso filled" style={{ color: colors.primary, fontSize: 18 }}>commit</span>
            Recent Commits
          </span>
          <span style={{ fontSize: 11, color: colors.secondary }}>Across your top 5 repos</span>
        </div>
        {commits.length === 0 && (
          <div style={{ padding: "20px", fontSize: 12, color: colors.secondary, textAlign: "center" }}>No commit data available.</div>
        )}
        <div>
          {commits.slice(0, 10).map((c, i) => (
            <a key={i} href={c.url} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
              <div style={{
                display: "flex", alignItems: "center", padding: "12px 20px", gap: 12,
                borderBottom: i < 9 ? `1px solid ${colors.surfaceContainerHigh}` : "none",
                transition: "background 0.15s", cursor: "pointer",
              }}
                onMouseEnter={e => e.currentTarget.style.background = colors.surfaceContainerLow}
                onMouseLeave={e => e.currentTarget.style.background = ""}
              >
                <code style={{ fontSize: 10, background: colors.surfaceContainerLow, color: colors.primary, padding: "2px 7px", borderRadius: 5, flexShrink: 0, fontFamily: "monospace", fontWeight: 700 }}>
                  {c.sha}
                </code>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: colors.onSurface, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.message}
                  </div>
                  <div style={{ fontSize: 10.5, color: colors.secondary, marginTop: 2 }}>
                    <span style={{ fontWeight: 600, color: "#4f46e5" }}>{c.repo.split("/")[1]}</span>
                    {" · "}{c.author}
                  </div>
                </div>
                <span style={{ fontSize: 10, color: colors.outline, flexShrink: 0 }}>{relativeTime(c.date)}</span>
              </div>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}

// ===================== COLLECTIONS PAGE =====================
function CollectionsPage() {
  const [folders, setFolders] = useState([]);
  const [status, setStatus] = useState({ loading: true, error: null });

  useEffect(() => {
    (async () => {
      try {
        const data = await safeFetchJson(`${API_BASE}/search/gdrive?q=&kind=folders&limit=30`);
        setFolders(Array.isArray(data?.items) ? data.items : []);
        setStatus({ loading: false, error: null });
      } catch (e) {
        setStatus({ loading: false, error: e.message });
      }
    })();
  }, []);

  const relativeTime = (dateStr) => {
    if (!dateStr) return "";
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <div className="tp-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, animation: "slideUp 0.4s cubic-bezier(0.22,1,0.36,1) both" }}>
        <div>
          <h1 className="h-headline" style={{ fontSize: 24, fontWeight: 800 }}>My Collections</h1>
          <p style={{ fontSize: 13, color: colors.secondary, marginTop: 4 }}>Organize and access your document vaults</p>
        </div>
        <button className="btn-primary">
          <span className="mso">add</span>New Collection
        </button>
      </div>
      {status.loading && (
        <div className="card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: 13, color: colors.secondary }}>Loading collections from Google Drive…</div>
        </div>
      )}
      {status.error && (
        <div className="card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: 13, color: "#dc2626" }}>{status.error}</div>
          <div style={{ fontSize: 11, color: colors.secondary, marginTop: 6 }}>
            Make sure `GDRIVE_TOKEN` is set in `backend/.env`.
          </div>
        </div>
      )}
      {!status.loading && folders.length === 0 && (
        <div className="card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: 13, color: colors.secondary }}>No Drive folders found.</div>
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        {folders.map((f, i) => {
          return (
            <a
              key={f.id || f.name || i}
              href={f.web_view_link || "#"}
              target="_blank"
              rel="noreferrer"
              style={{ textDecoration: "none" }}
            >
              <div className="card" style={{ cursor: "pointer", animationDelay: i * 0.06 + "s", animation: "slideUp 0.4s cubic-bezier(0.22,1,0.36,1) both", padding: "24px" }}>
                <div style={{ width: 52, height: 52, borderRadius: 16, background: "#eef2ff", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16, transition: "transform 0.22s cubic-bezier(0.34,1.56,0.64,1)" }}>
                  <span className="mso filled" style={{ color: colors.primary, fontSize: 28 }}>folder</span>
                </div>
                <div className="h-headline" style={{ fontSize: 15, fontWeight: 700, marginBottom: 4, color: colors.onSurface }}>{f.name || "Untitled folder"}</div>
                <div style={{ fontSize: 12, color: colors.secondary, marginBottom: 6 }}>{(f.owners || []).join(", ") || "Drive"}</div>
                <div style={{ display: "flex", gap: 12, fontSize: 11, color: colors.secondary }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span className="mso" style={{ fontSize: 13 }}>schedule</span>{relativeTime(f.modified_time)}
                  </span>
                  {f.permissions_summary && <span>{f.permissions_summary}</span>}
                </div>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}

// ===================== EXPERTS PAGE =====================
function ExpertsPage() {
  const [task, setTask] = useState("");
  const [data, setData] = useState(null);
  const [status, setStatus] = useState({ loading: false, error: null });
  const [lastQuery, setLastQuery] = useState("");

  const runSearch = async () => {
    if (!task.trim()) return;
    try {
      setStatus({ loading: true, error: null });
      setData(null);
      setLastQuery(task.trim());
      const d = await safeFetchJson(`${API_BASE}/expert/drive?q=${encodeURIComponent(task)}&limit=40`);
      setData(d);
      setStatus({ loading: false, error: null });
    } catch (e) {
      setStatus({ loading: false, error: e.message });
    }
  };

  return (
    <div className="tp-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 className="h-headline" style={{ fontSize: 24, fontWeight: 800 }}>Experts</h1>
          <p style={{ fontSize: 13, color: colors.secondary, marginTop: 4 }}>
            Rank experts by Google Drive metadata only (no file content).
          </p>
        </div>
      </div>

      <div className="card" style={{ padding: 20, marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span className="mso" style={{ color: colors.secondary }}>psychology</span>
          <input
            value={task}
            onChange={(e) => setTask(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
            placeholder="Describe a task (e.g. onboarding, finance reports, security audit)"
            style={{
              flex: 1,
              border: "1px solid " + colors.surfaceContainerHigh,
              borderRadius: 12,
              padding: "10px 12px",
              fontSize: 13,
              fontFamily: "Inter, sans-serif",
              outline: "none",
            }}
          />
          <button className="btn-primary" onClick={runSearch}>
            <span className="mso">search</span>Find Experts
          </button>
        </div>
      </div>

      {status.loading && (
        <div className="card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: 13, color: colors.secondary }}>Analyzing Drive metadata…</div>
        </div>
      )}
      {status.error && (
        <div className="card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: 13, color: "#dc2626" }}>{status.error}</div>
          <div style={{ fontSize: 11, color: colors.secondary, marginTop: 6 }}>
            Ensure `GDRIVE_TOKEN` is set in `backend/.env`.
          </div>
        </div>
      )}

      {lastQuery && !status.loading && !data?.experts?.length && !status.error && (
        <div className="card" style={{ padding: 24, textAlign: "center" }}>
          <div style={{ fontSize: 13, color: colors.secondary }}>No experts found for “{lastQuery}”.</div>
        </div>
      )}

      {data?.experts?.length ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
          {data.experts.map((ex, i) => (
            <div key={ex.name || i} className="card" style={{ padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: colors.onSurface }}>{ex.name}</div>
                  <div style={{ fontSize: 12, color: colors.secondary }}>
                    {ex.count} relevant files
                  </div>
                </div>
                <span style={{ fontSize: 11, color: colors.secondary }}>
                  Last modified: {ex.last_modified || "n/a"}
                </span>
              </div>
              <div style={{ marginTop: 12 }}>
                {(ex.files || []).map((f, idx) => (
                  <div key={idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: idx < ex.files.length - 1 ? "1px solid " + colors.surfaceContainerHigh : "none" }}>
                    <a href={f.url || "#"} target="_blank" rel="noreferrer" style={{ textDecoration: "none", color: colors.onSurface, fontSize: 12 }}>
                      {f.name}
                    </a>
                    <span style={{ fontSize: 10, color: colors.secondary }}>{f.mime || ""}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ===================== AUTH PAGES =====================
const USERS_DB = [
  { email: "admin@tracepath.ai", password: "password", role: "admin", name: "Arthur Admin" },
  { email: "user@tracepath.ai", password: "password", role: "user", name: "Arthur User" }
];

function LoginPage({ onLogin, onSwitch }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    const user = USERS_DB.find(u => u.email === email && u.password === password);
    if (user) {
      onLogin(user);
    } else {
      setError("Invalid credentials. Try admin@tracepath.ai / password");
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="tp-logo-area" style={{ justifyContent: 'center', marginBottom: 32 }}>
          <div className="tp-logo-icon"><span className="mso filled">auto_awesome</span></div>
          <div className="tp-logo-text"><h1>TracePath</h1><p>Premium Curator</p></div>
        </div>
        <h2 className="h-headline" style={{ fontSize: 22, fontWeight: 800, marginBottom: 8, textAlign: 'center' }}>Welcome Back</h2>
        <p style={{ color: colors.secondary, fontSize: 14, textAlign: 'center', marginBottom: 32 }}>Enter your credentials to access your library</p>
        
        <form onSubmit={handleSubmit}>
          <div className="auth-input-group">
            <label className="auth-label">Email Address</label>
            <input className="auth-input" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@company.com" required />
          </div>
          <div className="auth-input-group">
            <label className="auth-label">Password</label>
            <input className="auth-input" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />
          </div>
          {error && <p style={{ color: colors.primary, fontSize: 12, marginBottom: 16, textAlign: 'center', fontWeight: 600 }}>{error}</p>}
          <button className="btn-primary" style={{ width: '100%', padding: '14px', borderRadius: '16px', fontSize: 15 }}>Sign In</button>
        </form>
        
        <div className="auth-footer">
          Don't have an account? <span className="auth-link" onClick={onSwitch}>Create one</span>
        </div>
      </div>
    </div>
  );
}

function SignupPage({ onSignup, onSwitch }) {
  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="tp-logo-area" style={{ justifyContent: 'center', marginBottom: 32 }}>
          <div className="tp-logo-icon"><span className="mso filled">auto_awesome</span></div>
          <div className="tp-logo-text"><h1>TracePath</h1><p>Premium Curator</p></div>
        </div>
        <h2 className="h-headline" style={{ fontSize: 22, fontWeight: 800, marginBottom: 8, textAlign: 'center' }}>Get Started</h2>
        <p style={{ color: colors.secondary, fontSize: 14, textAlign: 'center', marginBottom: 32 }}>Join the future of intelligent document curation</p>
        
        <form onSubmit={e => e.preventDefault()}>
          <div className="auth-input-group">
            <label className="auth-label">Full Name</label>
            <input className="auth-input" type="text" placeholder="Arthur Dent" required />
          </div>
          <div className="auth-input-group">
            <label className="auth-label">Email Address</label>
            <input className="auth-input" type="email" placeholder="name@company.com" required />
          </div>
          <div className="auth-input-group">
            <label className="auth-label">Password</label>
            <input className="auth-input" type="password" placeholder="Create a strong password" required />
          </div>
          <button className="btn-primary" style={{ width: '100%', padding: '14px', borderRadius: '16px', fontSize: 15 }} onClick={() => onSignup({ name: "New User", role: "user" })}>Create Account</button>
        </form>
        
        <div className="auth-footer">
          Already have an account? <span className="auth-link" onClick={onSwitch}>Sign in</span>
        </div>
      </div>
    </div>
  );
}

// ===================== MAIN APP =====================
export default function App() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("login"); // "login" or "signup"
  const [page, setPage] = useState("home");
  const [query, setQuery] = useState("");
  const [githubOwner, setGithubOwner] = useState("tangyeel");
  const [githubRepo, setGithubRepo] = useState("");

  const handleLogout = () => {
    setUser(null);
    setPage("home");
  };

  const pageComponents = {
    home: <HomePage setPage={setPage} query={query} setQuery={setQuery} />,
    search: (
      <SearchPage
        setPage={setPage}
        query={query}
        githubOwner={githubOwner}
        githubRepo={githubRepo}
      />
    ),
    collections: <CollectionsPage />,
    experts: <ExpertsPage />,
    mindmap: (
      <MindMapPage
        owner={githubOwner}
        repo={githubRepo}
        setOwner={setGithubOwner}
        setRepo={setGithubRepo}
      />
    ),
    dashboard: <DashboardPage githubOwner={githubOwner} />,
  };

  return (
    <>
      <style>{style}</style>
      {loading && <LoadingScreen onDone={() => setLoading(false)} />}
      {!loading && (
        <>
          <VantaGlobeBackground enabled={page === "home" || !user} />
          <InteractiveDotGrid />
          {!user ? (
            authMode === "login" ? 
              <LoginPage onLogin={setUser} onSwitch={() => setAuthMode("signup")} /> : 
              <SignupPage onSignup={setUser} onSwitch={() => setAuthMode("login")} />
          ) : (
            <div className="tp-root">
              <div className="tp-sidebar-trigger" />
              <Sidebar page={page} setPage={setPage} onLogout={handleLogout} role={user.role} />
              <div className="tp-main">
                <Topbar page={page} query={query} setQuery={setQuery} setPage={setPage} user={user} />
                <div key={page} style={{ flex: 1, overflow: "hidden" }}>
                  {pageComponents[page]}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
