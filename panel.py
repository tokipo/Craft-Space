import os
import asyncio
import collections
import shutil
import psutil
import time
from fastapi import FastAPI, WebSocket, Request, Response, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

mc_process = None
output_history = collections.deque(maxlen=500)
connected_clients = set()
BASE_DIR = os.path.abspath("/app")
CONTAINER_CPU_CORES = 2
CONTAINER_RAM_MB = 16384
CONTAINER_STORAGE_GB = 50

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scale=no">
<title>MC Server Panel</title>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{
--bg-primary:#0a0a0f;--bg-secondary:#12121a;--bg-tertiary:#1a1a2e;--bg-card:#16162a;
--bg-hover:#1e1e3a;--bg-active:#252545;--border-primary:#2a2a4a;--border-glow:#7c3aed40;
--text-primary:#f0f0ff;--text-secondary:#a0a0c0;--text-muted:#606080;
--accent:#7c3aed;--accent-hover:#9333ea;--accent-glow:#7c3aed30;
--success:#10b981;--warning:#f59e0b;--danger:#ef4444;--info:#3b82f6;
--radius:12px;--radius-sm:8px;--radius-lg:16px;
--shadow:0 4px 24px rgba(0,0,0,0.4);--shadow-glow:0 0 30px var(--accent-glow);
--transition:all 0.2s cubic-bezier(0.4,0,0.2,1);
--font:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif;
--font-mono:'SF Mono','Cascadia Code','Fira Code',Consolas,monospace;
}
html{font-family:var(--font);background:var(--bg-primary);color:var(--text-primary);
-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;overflow:hidden;height:100%}
body{height:100%;overflow:hidden}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border-primary);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--accent)}

.app{display:flex;flex-direction:column;height:100vh;overflow:hidden}

/* Top Bar */
.topbar{display:flex;align-items:center;justify-content:space-between;padding:0 16px;
height:52px;min-height:52px;background:var(--bg-secondary);
border-bottom:1px solid var(--border-primary);z-index:100;gap:12px;
backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
.topbar-brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:15px;white-space:nowrap}
.topbar-brand svg{color:var(--accent)}
.topbar-status{display:flex;align-items:center;gap:6px;padding:4px 12px;
border-radius:20px;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase}
.status-online{background:#10b98118;color:#10b981;border:1px solid #10b98130}
.status-offline{background:#ef444418;color:#ef4444;border:1px solid #ef444430}
.topbar-stats{display:flex;align-items:center;gap:4px}
.stat-chip{display:flex;align-items:center;gap:6px;padding:5px 10px;
background:var(--bg-tertiary);border:1px solid var(--border-primary);
border-radius:var(--radius-sm);font-size:11px;font-weight:500;white-space:nowrap}
.stat-chip .stat-val{font-weight:700;color:var(--text-primary);font-variant-numeric:tabular-nums}
.stat-chip .stat-lbl{color:var(--text-muted);font-size:10px}
.stat-bar-wrap{width:40px;height:4px;background:var(--bg-primary);border-radius:2px;overflow:hidden}
.stat-bar-fill{height:100%;border-radius:2px;transition:width 0.6s ease}
.hamburger{display:none;background:none;border:none;color:var(--text-primary);cursor:pointer;padding:4px}

/* Navigation Tabs */
.nav-tabs{display:flex;align-items:center;gap:2px;padding:0 16px;
height:42px;min-height:42px;background:var(--bg-secondary);
border-bottom:1px solid var(--border-primary);overflow-x:auto}
.nav-tab{display:flex;align-items:center;gap:6px;padding:8px 14px;
font-size:12px;font-weight:500;color:var(--text-secondary);
border-radius:var(--radius-sm) var(--radius-sm) 0 0;cursor:pointer;
transition:var(--transition);white-space:nowrap;border:none;background:none;
border-bottom:2px solid transparent;position:relative}
.nav-tab:hover{color:var(--text-primary);background:var(--bg-hover)}
.nav-tab.active{color:var(--accent);background:var(--bg-tertiary);border-bottom-color:var(--accent)}
.nav-tab svg{width:14px;height:14px;flex-shrink:0}

/* Main Content */
.main-content{flex:1;overflow:hidden;position:relative}
.panel{display:none;height:100%;flex-direction:column;overflow:hidden}
.panel.active{display:flex}

/* Console */
.console-wrap{flex:1;display:flex;flex-direction:column;overflow:hidden}
.console-output{flex:1;overflow-y:auto;padding:12px 16px;font-family:var(--font-mono);
font-size:12.5px;line-height:1.7;background:var(--bg-primary);scroll-behavior:smooth;
-webkit-overflow-scrolling:touch}
.console-line{padding:1px 0;word-break:break-all;animation:fadeIn 0.15s ease}
.console-line:hover{background:var(--bg-hover);border-radius:2px}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.console-line .timestamp{color:var(--text-muted);margin-right:8px;font-size:11px;user-select:none}
.log-info{color:#60a5fa}.log-warn{color:#fbbf24}.log-error{color:#f87171}
.log-server{color:#a78bfa}.log-chat{color:#34d399}.log-default{color:var(--text-secondary)}
.console-input-wrap{display:flex;gap:8px;padding:10px 16px;background:var(--bg-secondary);
border-top:1px solid var(--border-primary);align-items:center}
.console-prefix{color:var(--accent);font-family:var(--font-mono);font-size:13px;
font-weight:700;user-select:none;flex-shrink:0}
.console-input{flex:1;background:var(--bg-tertiary);border:1px solid var(--border-primary);
color:var(--text-primary);font-family:var(--font-mono);font-size:12.5px;padding:8px 12px;
border-radius:var(--radius-sm);outline:none;transition:var(--transition)}
.console-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.console-input::placeholder{color:var(--text-muted)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:7px 14px;
font-size:12px;font-weight:600;border:1px solid var(--border-primary);border-radius:var(--radius-sm);
cursor:pointer;transition:var(--transition);background:var(--bg-tertiary);color:var(--text-primary);
white-space:nowrap;font-family:var(--font)}
.btn:hover{background:var(--bg-hover);border-color:var(--accent)}
.btn:active{transform:scale(0.97)}
.btn-accent{background:var(--accent);border-color:var(--accent);color:#fff}
.btn-accent:hover{background:var(--accent-hover);border-color:var(--accent-hover)}
.btn-danger{background:var(--danger);border-color:var(--danger);color:#fff}
.btn-danger:hover{background:#dc2626;border-color:#dc2626}
.btn-sm{padding:5px 10px;font-size:11px}
.btn-icon{padding:6px;width:32px;height:32px}
.btn svg{width:14px;height:14px;flex-shrink:0}
.console-toolbar{display:flex;align-items:center;gap:6px;padding:6px 16px;
background:var(--bg-secondary);border-bottom:1px solid var(--border-primary);
overflow-x:auto;flex-wrap:nowrap}
.console-toolbar .btn{flex-shrink:0}
.quick-cmds{display:flex;gap:4px;flex-wrap:nowrap;overflow-x:auto;flex:1}
.quick-cmds .btn{font-size:10px;padding:4px 8px;background:var(--bg-card);color:var(--text-secondary)}
.quick-cmds .btn:hover{color:var(--text-primary);background:var(--accent);border-color:var(--accent)}

/* File Manager */
.fm-container{display:flex;flex-direction:column;height:100%;overflow:hidden}
.fm-toolbar{display:flex;align-items:center;gap:8px;padding:10px 16px;
background:var(--bg-secondary);border-bottom:1px solid var(--border-primary);flex-wrap:wrap}
.fm-path{display:flex;align-items:center;gap:2px;flex:1;min-width:200px;overflow-x:auto;flex-wrap:nowrap}
.fm-crumb{padding:4px 8px;font-size:11px;color:var(--text-secondary);cursor:pointer;
border-radius:var(--radius-sm);transition:var(--transition);white-space:nowrap;
background:none;border:none;font-family:var(--font)}
.fm-crumb:hover{background:var(--bg-hover);color:var(--text-primary)}
.fm-crumb.active{color:var(--accent);font-weight:600}
.fm-crumb-sep{color:var(--text-muted);font-size:10px;user-select:none}
.fm-body{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch}
.fm-list{width:100%}
.fm-item{display:flex;align-items:center;gap:10px;padding:9px 16px;cursor:pointer;
transition:var(--transition);border-bottom:1px solid var(--border-primary)}
.fm-item:hover{background:var(--bg-hover)}
.fm-item.selected{background:var(--accent-glow);border-left:3px solid var(--accent)}
.fm-icon{width:18px;height:18px;flex-shrink:0;display:flex;align-items:center;justify-content:center}
.fm-icon.folder{color:#fbbf24}.fm-icon.file{color:var(--text-muted)}
.fm-icon.jar{color:#ef4444}.fm-icon.yml{color:#10b981}.fm-icon.json{color:#f59e0b}
.fm-icon.properties{color:#3b82f6}.fm-icon.log{color:#8b5cf6}.fm-icon.img{color:#ec4899}
.fm-name{flex:1;font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fm-size{font-size:11px;color:var(--text-muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.fm-actions{display:flex;gap:2px;opacity:0;transition:var(--transition)}
.fm-item:hover .fm-actions{opacity:1}
.fm-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;
padding:60px 20px;color:var(--text-muted);gap:12px}
.fm-empty svg{width:48px;height:48px;opacity:0.3}

/* Editor */
.editor-container{display:flex;flex-direction:column;height:100%;overflow:hidden}
.editor-header{display:flex;align-items:center;gap:10px;padding:10px 16px;
background:var(--bg-secondary);border-bottom:1px solid var(--border-primary)}
.editor-filename{font-size:13px;font-weight:600;color:var(--accent);flex:1;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.editor-textarea{flex:1;width:100%;resize:none;background:var(--bg-primary);
color:var(--text-primary);font-family:var(--font-mono);font-size:12.5px;
line-height:1.6;padding:16px;border:none;outline:none;tab-size:4;
-webkit-overflow-scrolling:touch}
.editor-textarea::placeholder{color:var(--text-muted)}

/* Dashboard Cards */
.dashboard{padding:16px;overflow-y:auto;-webkit-overflow-scrolling:touch;height:100%}
.dash-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.dash-card{background:var(--bg-card);border:1px solid var(--border-primary);
border-radius:var(--radius);padding:20px;transition:var(--transition)}
.dash-card:hover{border-color:var(--accent);box-shadow:var(--shadow-glow)}
.dash-card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.dash-card-title{font-size:13px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px}
.dash-card-icon{width:36px;height:36px;border-radius:var(--radius-sm);display:flex;
align-items:center;justify-content:center}
.dash-card-icon.cpu{background:#7c3aed20;color:#7c3aed}
.dash-card-icon.ram{background:#3b82f620;color:#3b82f6}
.dash-card-icon.disk{background:#10b98120;color:#10b981}
.dash-card-icon.status{background:#f59e0b20;color:#f59e0b}
.dash-metric{font-size:32px;font-weight:800;line-height:1;margin-bottom:4px;
font-variant-numeric:tabular-nums;letter-spacing:-1px}
.dash-metric-sub{font-size:12px;color:var(--text-muted)}
.dash-progress{width:100%;height:6px;background:var(--bg-primary);border-radius:3px;
margin-top:12px;overflow:hidden}
.dash-progress-fill{height:100%;border-radius:3px;transition:width 0.8s cubic-bezier(0.4,0,0.2,1)}
.color-green{color:var(--success)}.color-yellow{color:var(--warning)}
.color-red{color:var(--danger)}.color-blue{color:var(--info)}.color-purple{color:var(--accent)}
.fill-green{background:var(--success)}.fill-yellow{background:var(--warning)}
.fill-red{background:var(--danger)}.fill-blue{background:var(--info)}.fill-purple{background:var(--accent)}

/* Upload Overlay */
.upload-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);
backdrop-filter:blur(8px);z-index:200;align-items:center;justify-content:center}
.upload-overlay.active{display:flex}
.upload-modal{background:var(--bg-card);border:1px solid var(--border-primary);
border-radius:var(--radius-lg);padding:32px;width:min(440px,90vw);text-align:center}
.upload-zone{border:2px dashed var(--border-primary);border-radius:var(--radius);
padding:40px 20px;margin:20px 0;transition:var(--transition);cursor:pointer}
.upload-zone:hover,.upload-zone.dragover{border-color:var(--accent);background:var(--accent-glow)}
.upload-zone svg{width:40px;height:40px;color:var(--text-muted);margin-bottom:12px}
.upload-zone p{font-size:13px;color:var(--text-secondary)}

/* Toast Notifications */
.toast-container{position:fixed;bottom:20px;right:20px;z-index:300;display:flex;flex-direction:column;gap:8px}
.toast{padding:12px 16px;border-radius:var(--radius-sm);font-size:12px;font-weight:500;
animation:toastIn 0.3s ease,toastOut 0.3s ease 2.7s forwards;display:flex;align-items:center;gap:8px;
box-shadow:var(--shadow);max-width:min(360px,calc(100vw - 40px))}
.toast-success{background:#065f46;border:1px solid #10b98150;color:#d1fae5}
.toast-error{background:#7f1d1d;border:1px solid #ef444450;color:#fee2e2}
.toast-info{background:#1e3a5f;border:1px solid #3b82f650;color:#dbeafe}
@keyframes toastIn{from{opacity:0;transform:translateX(40px)}to{opacity:1;transform:translateX(0)}}
@keyframes toastOut{from{opacity:1}to{opacity:0;transform:translateY(10px)}}

/* Context Menu */
.ctx-menu{position:fixed;background:var(--bg-card);border:1px solid var(--border-primary);
border-radius:var(--radius-sm);padding:4px;z-index:250;min-width:160px;
box-shadow:var(--shadow);display:none}
.ctx-menu.active{display:block}
.ctx-item{display:flex;align-items:center;gap:8px;padding:7px 12px;font-size:12px;
color:var(--text-secondary);cursor:pointer;border-radius:4px;transition:var(--transition);
border:none;background:none;width:100%;text-align:left;font-family:var(--font)}
.ctx-item:hover{background:var(--bg-hover);color:var(--text-primary)}
.ctx-item.danger{color:var(--danger)}
.ctx-item.danger:hover{background:#ef444420}
.ctx-item svg{width:14px;height:14px;flex-shrink:0}
.ctx-sep{height:1px;background:var(--border-primary);margin:4px 0}

/* Connection indicator */
.conn-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.conn-dot.connected{background:var(--success);box-shadow:0 0 6px var(--success)}
.conn-dot.disconnected{background:var(--danger);box-shadow:0 0 6px var(--danger)}

/* Responsive */
@media(max-width:768px){
  .topbar{padding:0 10px;height:48px;min-height:48px}
  .topbar-stats{display:none}
  .topbar-brand span{display:none}
  .hamburger{display:flex}
  .nav-tabs{height:38px;min-height:38px;padding:0 8px;gap:0}
  .nav-tab{padding:6px 10px;font-size:11px}
  .nav-tab span{display:none}
  .console-output{padding:8px;font-size:11px;line-height:1.5}
  .console-input-wrap{padding:8px 10px}
  .console-toolbar{padding:4px 8px}
  .fm-toolbar{padding:8px 10px}
  .fm-item{padding:8px 10px}
  .fm-actions{opacity:1}
  .dashboard{padding:10px}
  .dash-grid{grid-template-columns:1fr}
  .dash-metric{font-size:26px}
  .stat-chip{padding:3px 6px;font-size:10px}
  .mobile-stats{display:flex !important}
}
@media(max-width:480px){
  .nav-tabs{overflow-x:auto}
  .console-toolbar{flex-wrap:nowrap;overflow-x:auto}
  .quick-cmds .btn{padding:3px 6px;font-size:9px}
}
.mobile-stats{display:none;gap:4px;padding:6px 10px;background:var(--bg-secondary);
border-bottom:1px solid var(--border-primary);overflow-x:auto}

/* Loading skeleton */
.skeleton{background:linear-gradient(90deg,var(--bg-tertiary) 25%,var(--bg-hover) 50%,var(--bg-tertiary) 75%);
background-size:200% 100%;animation:shimmer 1.5s infinite;border-radius:4px}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* Smooth transitions for panels */
.panel{animation:panelIn 0.2s ease}
@keyframes panelIn{from{opacity:0}to{opacity:1}}

.search-input{background:var(--bg-tertiary);border:1px solid var(--border-primary);
color:var(--text-primary);font-size:12px;padding:5px 10px;border-radius:var(--radius-sm);
outline:none;transition:var(--transition);width:140px;font-family:var(--font)}
.search-input:focus{border-color:var(--accent);width:200px}
@media(max-width:768px){.search-input{width:100px}.search-input:focus{width:140px}}
</style>
</head>
<body>
<div class="app">
  <!-- Top Bar -->
  <div class="topbar">
    <div style="display:flex;align-items:center;gap:10px">
      <button class="hamburger" onclick="toggleMobileStats()">
        <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h14M3 10h14M3 14h14"/></svg>
      </button>
      <div class="topbar-brand">
        <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="18" rx="3"/><path d="M8 12h8M12 8v8"/></svg>
        <span>MC Panel</span>
      </div>
      <div class="topbar-status" id="serverStatus">
        <div class="conn-dot disconnected" id="connDot"></div>
        <span id="statusText">CONNECTING</span>
      </div>
    </div>
    <div class="topbar-stats" id="topbarStats">
      <div class="stat-chip" title="CPU Usage (2 vCPU)">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="1" width="10" height="10" rx="2"/><path d="M4 4h4M4 6h4M4 8h2"/></svg>
        <div><div class="stat-val" id="cpuTopVal">0%</div><div class="stat-lbl">CPU</div></div>
        <div class="stat-bar-wrap"><div class="stat-bar-fill fill-purple" id="cpuTopBar" style="width:0%"></div></div>
      </div>
      <div class="stat-chip" title="RAM Usage (16 GB)">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="1" width="8" height="10" rx="1"/><path d="M4 11v1M8 11v1M1 4h10"/></svg>
        <div><div class="stat-val" id="ramTopVal">0 MB</div><div class="stat-lbl">RAM</div></div>
        <div class="stat-bar-wrap"><div class="stat-bar-fill fill-blue" id="ramTopBar" style="width:0%"></div></div>
      </div>
      <div class="stat-chip" title="Storage">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="6" cy="4" rx="5" ry="2"/><path d="M1 4v4c0 1.1 2.2 2 5 2s5-.9 5-2V4"/></svg>
        <div><div class="stat-val" id="diskTopVal">-- GB</div><div class="stat-lbl">DISK</div></div>
        <div class="stat-bar-wrap"><div class="stat-bar-fill fill-green" id="diskTopBar" style="width:0%"></div></div>
      </div>
    </div>
  </div>
  
  <!-- Mobile Stats (hidden by default) -->
  <div class="mobile-stats" id="mobileStats">
    <div class="stat-chip"><span class="stat-val" id="cpuMobVal">0%</span><span class="stat-lbl">CPU</span></div>
    <div class="stat-chip"><span class="stat-val" id="ramMobVal">0 MB</span><span class="stat-lbl">RAM</span></div>
    <div class="stat-chip"><span class="stat-val" id="diskMobVal">--</span><span class="stat-lbl">DISK</span></div>
  </div>

  <!-- Navigation Tabs -->
  <div class="nav-tabs">
    <button class="nav-tab active" data-tab="dashboard" onclick="switchTab('dashboard')">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
      <span>Dashboard</span>
    </button>
    <button class="nav-tab" data-tab="console" onclick="switchTab('console')">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
      <span>Console</span>
    </button>
    <button class="nav-tab" data-tab="files" onclick="switchTab('files')">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
      <span>Files</span>
    </button>
    <button class="nav-tab" data-tab="editor" onclick="switchTab('editor')" id="editorTab" style="display:none">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
      <span>Editor</span>
    </button>
  </div>

  <!-- Main Content Area -->
  <div class="main-content">

    <!-- Dashboard Panel -->
    <div class="panel active" id="panel-dashboard">
      <div class="dashboard">
        <div class="dash-grid">
          <div class="dash-card">
            <div class="dash-card-header">
              <div class="dash-card-title">CPU Usage</div>
              <div class="dash-card-icon cpu">
                <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="16" height="16" rx="3"/><path d="M6 6h8M6 10h8M6 14h4"/></svg>
              </div>
            </div>
            <div class="dash-metric color-purple" id="cpuDashVal">0%</div>
            <div class="dash-metric-sub">of 2 vCPU Cores</div>
            <div class="dash-progress"><div class="dash-progress-fill fill-purple" id="cpuDashBar" style="width:0%"></div></div>
          </div>
          <div class="dash-card">
            <div class="dash-card-header">
              <div class="dash-card-title">Memory</div>
              <div class="dash-card-icon ram">
                <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="1" width="14" height="16" rx="2"/><path d="M6 17v2M14 17v2M10 17v2M1 6h18"/></svg>
              </div>
            </div>
            <div class="dash-metric color-blue" id="ramDashVal">0 MB</div>
            <div class="dash-metric-sub" id="ramDashSub">of 16,384 MB</div>
            <div class="dash-progress"><div class="dash-progress-fill fill-blue" id="ramDashBar" style="width:0%"></div></div>
          </div>
          <div class="dash-card">
            <div class="dash-card-header">
              <div class="dash-card-title">Storage</div>
              <div class="dash-card-icon disk">
                <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="10" cy="6" rx="8" ry="3"/><path d="M2 6v5c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M2 11v5c0 1.7 3.6 3 8 3s8-1.3 8-3v-5"/></svg>
              </div>
            </div>
            <div class="dash-metric color-green" id="diskDashVal">-- GB</div>
            <div class="dash-metric-sub" id="diskDashSub">loading...</div>
            <div class="dash-progress"><div class="dash-progress-fill fill-green" id="diskDashBar" style="width:0%"></div></div>
          </div>
          <div class="dash-card">
            <div class="dash-card-header">
              <div class="dash-card-title">Server Status</div>
              <div class="dash-card-icon status">
                <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="10" cy="10" r="8"/><polyline points="10 5 10 10 13 12"/></svg>
              </div>
            </div>
            <div class="dash-metric" id="uptimeVal" style="font-size:24px;color:var(--text-primary)">--</div>
            <div class="dash-metric-sub" id="uptimeSub">Container uptime</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Console Panel -->
    <div class="panel" id="panel-console">
      <div class="console-wrap">
        <div class="console-toolbar">
          <button class="btn btn-sm" onclick="sendCmd('list')" title="List Players">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 10a3 3 0 100-6 3 3 0 000 6zM1 12a6 6 0 0112 0"/></svg>
            Players
          </button>
          <div class="quick-cmds">
            <button class="btn" onclick="sendCmd('tps')">TPS</button>
            <button class="btn" onclick="sendCmd('gc')">GC</button>
            <button class="btn" onclick="sendCmd('mem')">Mem</button>
            <button class="btn" onclick="sendCmd('version')">Ver</button>
            <button class="btn" onclick="sendCmd('plugins')">Plugins</button>
            <button class="btn" onclick="sendCmd('whitelist list')">WL</button>
            <button class="btn" onclick="sendCmd('save-all')">Save</button>
          </div>
          <button class="btn btn-sm btn-danger" onclick="if(confirm('Stop the server?'))sendCmd('stop')" title="Stop Server">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="1" width="10" height="10" rx="1"/></svg>
            Stop
          </button>
          <button class="btn btn-sm btn-icon" onclick="clearConsole()" title="Clear Console">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 1l10 10M11 1L1 11"/></svg>
          </button>
          <button class="btn btn-sm btn-icon" onclick="scrollToBottom()" title="Scroll to Bottom">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 1v10M2 7l4 4 4-4"/></svg>
          </button>
        </div>
        <div class="console-output" id="consoleOutput"></div>
        <div class="console-input-wrap">
          <span class="console-prefix">$</span>
          <input class="console-input" id="consoleInput" type="text" placeholder="Type a command..." autocomplete="off" spellcheck="false">
          <button class="btn btn-accent" onclick="sendCurrentCmd()">
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 1l11 6-11 6V1z"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Files Panel -->
    <div class="panel" id="panel-files">
      <div class="fm-container">
        <div class="fm-toolbar">
          <div class="fm-path" id="fmBreadcrumb"></div>
          <input class="search-input" type="text" placeholder="Filter..." id="fmSearch" oninput="filterFiles()">
          <button class="btn btn-sm" onclick="refreshFiles()" title="Refresh">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 1v4h4M11 11v-4h-4"/><path d="M10.4 5A5 5 0 003 3.5L1 5M1.6 7a5 5 0 007.4 1.5L11 7"/></svg>
          </button>
          <button class="btn btn-sm" onclick="showUploadModal()" title="Upload File">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 10V2M2 6l4-4 4 4"/><path d="M1 10v1a1 1 0 001 1h8a1 1 0 001-1v-1"/></svg>
            Upload
          </button>
          <button class="btn btn-sm" onclick="createNewFile()" title="New File">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 1v10M1 6h10"/></svg>
            New
          </button>
        </div>
        <div class="fm-body" id="fmBody">
          <div class="fm-empty"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg><span>Loading files...</span></div>
        </div>
      </div>
    </div>

    <!-- Editor Panel -->
    <div class="panel" id="panel-editor">
      <div class="editor-container">
        <div class="editor-header">
          <button class="btn btn-sm" onclick="closeEditor()">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 1L1 6l9 5"/></svg>
            Back
          </button>
          <div class="editor-filename" id="editorFilename">No file open</div>
          <button class="btn btn-sm btn-accent" onclick="saveFile()" id="editorSaveBtn">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 1h8l2 2v8a1 1 0 01-1 1H2a1 1 0 01-1-1V2a1 1 0 011-1z"/><path d="M4 1v3h4V1M3 7h6v4H3z"/></svg>
            Save
          </button>
          <button class="btn btn-sm" onclick="downloadCurrentFile()">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 1v8M2 6l4 4 4-4"/><path d="M1 10v1a1 1 0 001 1h8a1 1 0 001-1v-1"/></svg>
          </button>
        </div>
        <textarea class="editor-textarea" id="editorContent" placeholder="File contents will appear here..." spellcheck="false"></textarea>
      </div>
    </div>
  </div>
</div>

<!-- Upload Modal -->
<div class="upload-overlay" id="uploadOverlay" onclick="if(event.target===this)hideUploadModal()">
  <div class="upload-modal">
    <h3 style="font-size:16px;font-weight:700;margin-bottom:4px">Upload File</h3>
    <p style="font-size:12px;color:var(--text-muted)" id="uploadPathDisplay">to /</p>
    <div class="upload-zone" id="uploadZone" onclick="document.getElementById('uploadFileInput').click()">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path d="M12 16V4M8 8l4-4 4 4"/><path d="M20 16v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2"/></svg>
      <p>Click or drag files here</p>
      <p style="font-size:11px;color:var(--text-muted);margin-top:4px" id="uploadFileName">No file selected</p>
    </div>
    <input type="file" id="uploadFileInput" style="display:none" onchange="handleFileSelect(this)">
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button class="btn" onclick="hideUploadModal()">Cancel</button>
      <button class="btn btn-accent" onclick="doUpload()" id="uploadBtn">Upload</button>
    </div>
  </div>
</div>

<!-- Context Menu -->
<div class="ctx-menu" id="ctxMenu">
  <button class="ctx-item" onclick="ctxAction('open')"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>Open</button>
  <button class="ctx-item" onclick="ctxAction('edit')"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>Edit</button>
  <button class="ctx-item" onclick="ctxAction('download')"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 16V4M8 12l4 4 4-4"/><path d="M20 16v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2"/></svg>Download</button>
  <button class="ctx-item" onclick="ctxAction('rename')"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M17 3a2.83 2.83 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>Rename</button>
  <div class="ctx-sep"></div>
  <button class="ctx-item danger" onclick="ctxAction('delete')"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>Delete</button>
</div>

<!-- Toast Container -->
<div class="toast-container" id="toastContainer"></div>

<script>
// ========== STATE ==========
let ws=null, wsConnected=false, currentPath='', editingFile='', cmdHistory=[], cmdHistoryIdx=-1;
let ctxTarget=null, allFileItems=[], autoScroll=true, startTime=Date.now();
const consoleEl=document.getElementById('consoleOutput');
const consoleInput=document.getElementById('consoleInput');

// ========== TABS ==========
function switchTab(tab){
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  document.getElementById('panel-'+tab).classList.add('active');
  if(tab==='files')loadFiles(currentPath);
  if(tab==='console')requestAnimationFrame(()=>scrollToBottom());
}

// ========== WEBSOCKET ==========
function connectWS(){
  const proto=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(proto+'//'+location.host+'/ws');
  ws.onopen=()=>{wsConnected=true;updateStatus(true);toast('Connected to server','success')};
  ws.onclose=()=>{wsConnected=false;updateStatus(false);setTimeout(connectWS,2000)};
  ws.onerror=()=>{wsConnected=false;updateStatus(false)};
  ws.onmessage=e=>{appendConsole(e.data)};
}
function updateStatus(online){
  const dot=document.getElementById('connDot');
  const txt=document.getElementById('statusText');
  const wrap=document.getElementById('serverStatus');
  dot.className='conn-dot '+(online?'connected':'disconnected');
  txt.textContent=online?'ONLINE':'OFFLINE';
  wrap.className='topbar-status '+(online?'status-online':'status-offline');
}

// ========== CONSOLE ==========
function classifyLine(text){
  const t=text.toLowerCase();
  if(t.includes('error')||t.includes('exception')||t.includes('severe')||t.includes('fatal'))return 'log-error';
  if(t.includes('warn'))return 'log-warn';
  if(t.includes('info'))return 'log-info';
  if(t.includes('server')||t.includes('starting')||t.includes('done'))return 'log-server';
  if(t.includes('<')||t.includes('joined')||t.includes('left'))return 'log-chat';
  return 'log-default';
}
function appendConsole(text){
  const div=document.createElement('div');
  div.className='console-line '+classifyLine(text);
  const now=new Date();
  const ts=String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0')+':'+String(now.getSeconds()).padStart(2,'0');
  div.innerHTML='<span class="timestamp">'+ts+'</span>'+escapeHtml(text);
  consoleEl.appendChild(div);
  // Keep max 500 lines in DOM
  while(consoleEl.children.length>500)consoleEl.removeChild(consoleEl.firstChild);
  if(autoScroll)scrollToBottom();
}
function scrollToBottom(){consoleEl.scrollTop=consoleEl.scrollHeight}
function clearConsole(){consoleEl.innerHTML='';toast('Console cleared','info')}
function escapeHtml(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}

consoleEl.addEventListener('scroll',()=>{
  const atBottom=consoleEl.scrollHeight-consoleEl.scrollTop-consoleEl.clientHeight<50;
  autoScroll=atBottom;
});

function sendCmd(cmd){
  if(ws&&ws.readyState===1){ws.send(cmd);appendConsole('> '+cmd)}
  else toast('Not connected','error');
}
function sendCurrentCmd(){
  const v=consoleInput.value.trim();
  if(!v)return;
  cmdHistory.unshift(v);if(cmdHistory.length>50)cmdHistory.pop();cmdHistoryIdx=-1;
  sendCmd(v);consoleInput.value='';
}
consoleInput.addEventListener('keydown',e=>{
  if(e.key==='Enter'){e.preventDefault();sendCurrentCmd()}
  if(e.key==='ArrowUp'){e.preventDefault();if(cmdHistoryIdx<cmdHistory.length-1){cmdHistoryIdx++;consoleInput.value=cmdHistory[cmdHistoryIdx]}}
  if(e.key==='ArrowDown'){e.preventDefault();if(cmdHistoryIdx>0){cmdHistoryIdx--;consoleInput.value=cmdHistory[cmdHistoryIdx]}else{cmdHistoryIdx=-1;consoleInput.value=''}}
  if(e.key==='Tab'){e.preventDefault();/* Could add tab completion */}
});

// ========== STATS ==========
function getColorForPercent(p){return p>=90?'red':p>=70?'yellow':'green'}
async function fetchStats(){
  try{
    const r=await fetch('/api/stats');const d=await r.json();
    const cpuP=Math.min(100,d.cpu_percent||0).toFixed(1);
    const ramMB=(d.ram_used_mb||0).toFixed(0);
    const ramP=((d.ram_used_mb||0)/16384*100).toFixed(1);
    const diskUsedGB=(d.disk_used_gb||0).toFixed(1);
    const diskTotalGB=(d.disk_total_gb||0).toFixed(1);
    const diskP=diskTotalGB>0?((d.disk_used_gb/d.disk_total_gb)*100).toFixed(1):'0';
    const cpuCol=getColorForPercent(cpuP);
    const ramCol=getColorForPercent(ramP);
    const diskCol=getColorForPercent(diskP);
    
    // Topbar
    document.getElementById('cpuTopVal').textContent=cpuP+'%';
    document.getElementById('cpuTopBar').style.width=cpuP+'%';
    document.getElementById('cpuTopBar').className='stat-bar-fill fill-'+cpuCol;
    document.getElementById('ramTopVal').textContent=ramMB+' MB';
    document.getElementById('ramTopBar').style.width=ramP+'%';
    document.getElementById('ramTopBar').className='stat-bar-fill fill-'+ramCol;
    document.getElementById('diskTopVal').textContent=diskUsedGB+' GB';
    document.getElementById('diskTopBar').style.width=diskP+'%';
    document.getElementById('diskTopBar').className='stat-bar-fill fill-'+diskCol;

    // Mobile
    document.getElementById('cpuMobVal').textContent=cpuP+'%';
    document.getElementById('ramMobVal').textContent=ramMB+' MB';
    document.getElementById('diskMobVal').textContent=diskUsedGB+'G';

    // Dashboard
    document.getElementById('cpuDashVal').textContent=cpuP+'%';
    document.getElementById('cpuDashBar').style.width=cpuP+'%';
    document.getElementById('cpuDashBar').className='dash-progress-fill fill-'+cpuCol;
    document.getElementById('cpuDashVal').className='dash-metric color-'+cpuCol;

    document.getElementById('ramDashVal').textContent=ramMB+' MB';
    document.getElementById('ramDashSub').textContent=ramP+'% of 16,384 MB';
    document.getElementById('ramDashBar').style.width=ramP+'%';
    document.getElementById('ramDashBar').className='dash-progress-fill fill-'+ramCol;
    document.getElementById('ramDashVal').className='dash-metric color-'+ramCol;

    document.getElementById('diskDashVal').textContent=diskUsedGB+' GB';
    document.getElementById('diskDashSub').textContent=diskP+'% of '+diskTotalGB+' GB';
    document.getElementById('diskDashBar').style.width=diskP+'%';
    document.getElementById('diskDashBar').className='dash-progress-fill fill-'+diskCol;
    document.getElementById('diskDashVal').className='dash-metric color-'+diskCol;

    // Uptime
    const upSec=Math.floor((Date.now()-startTime)/1000);
    const h=Math.floor(upSec/3600),m=Math.floor((upSec%3600)/60),s=upSec%60;
    document.getElementById('uptimeVal').textContent=
      (h>0?h+'h ':'')+(m>0?m+'m ':'')+s+'s';
    document.getElementById('uptimeSub').textContent='Session uptime';
  }catch(e){}
}
setInterval(fetchStats,2000);
fetchStats();

// ========== FILE MANAGER ==========
function formatSize(b){
  if(b===0)return'--';
  if(b<1024)return b+' B';
  if(b<1048576)return(b/1024).toFixed(1)+' KB';
  if(b<1073741824)return(b/1048576).toFixed(1)+' MB';
  return(b/1073741824).toFixed(2)+' GB';
}
function getFileIcon(name,isDir){
  if(isDir)return{cls:'folder',svg:'<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>'};
  const ext=name.split('.').pop().toLowerCase();
  const map={jar:{cls:'jar',i:'☕'},yml:{cls:'yml',i:'⚙'},yaml:{cls:'yml',i:'⚙'},
    json:{cls:'json',i:'{}'},properties:{cls:'properties',i:'🔧'},log:{cls:'log',i:'📜'},
    txt:{cls:'file',i:'📄'},png:{cls:'img',i:'🖼'},jpg:{cls:'img',i:'🖼'},gif:{cls:'img',i:'🖼'},
    toml:{cls:'yml',i:'⚙'},conf:{cls:'properties',i:'🔧'},cfg:{cls:'properties',i:'🔧'},
    sk:{cls:'yml',i:'📜'},sh:{cls:'log',i:'⚡'},bat:{cls:'log',i:'⚡'}};
  const m=map[ext]||{cls:'file',i:'📄'};
  return{cls:m.cls,text:m.i};
}

async function loadFiles(path){
  currentPath=path||'';
  buildBreadcrumb();
  const body=document.getElementById('fmBody');
  body.innerHTML='<div style="padding:20px;text-align:center;color:var(--text-muted)"><div class="skeleton" style="height:20px;width:60%;margin:8px auto"></div><div class="skeleton" style="height:20px;width:80%;margin:8px auto"></div><div class="skeleton" style="height:20px;width:50%;margin:8px auto"></div></div>';
  try{
    const r=await fetch('/api/fs/list?path='+encodeURIComponent(currentPath));
    allFileItems=await r.json();
    renderFiles(allFileItems);
  }catch(e){body.innerHTML='<div class="fm-empty"><span>Failed to load</span></div>'}
}

function renderFiles(items){
  const body=document.getElementById('fmBody');
  const search=document.getElementById('fmSearch').value.toLowerCase();
  let filtered=items;
  if(search)filtered=items.filter(i=>i.name.toLowerCase().includes(search));
  
  if(!filtered.length&&!currentPath){body.innerHTML='<div class="fm-empty"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg><span>Directory is empty</span></div>';return}
  
  let html='';
  // Parent directory
  if(currentPath){
    html+='<div class="fm-item" ondblclick="goUp()" onclick="goUp()"><div class="fm-icon folder"><svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg></div><div class="fm-name" style="color:var(--text-muted)">..</div><div class="fm-size"></div></div>';
  }
  filtered.forEach((item,idx)=>{
    const icon=getFileIcon(item.name,item.is_dir);
    const iconHtml=icon.svg
      ?'<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'+icon.svg+'</svg>'
      :'<span style="font-size:16px">'+icon.text+'</span>';
    html+=`<div class="fm-item" data-name="${escapeHtml(item.name)}" data-dir="${item.is_dir}" data-idx="${idx}"
      ondblclick="fmDblClick('${escapeHtml(item.name)}',${item.is_dir})"
      oncontextmenu="fmCtx(event,'${escapeHtml(item.name)}',${item.is_dir})">
      <div class="fm-icon ${icon.cls}">${iconHtml}</div>
      <div class="fm-name">${escapeHtml(item.name)}</div>
      <div class="fm-size">${item.is_dir?'':formatSize(item.size)}</div>
      <div class="fm-actions">
        ${!item.is_dir?`<button class="btn btn-sm btn-icon" onclick="event.stopPropagation();editFile('${escapeHtml(item.name)}')" title="Edit"><svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M8.5 1.5a1.4 1.4 0 012 2L4 10l-2.5.5.5-2.5L8.5 1.5z"/></svg></button>`:''}
        ${!item.is_dir?`<button class="btn btn-sm btn-icon" onclick="event.stopPropagation();downloadFile('${escapeHtml(item.name)}')" title="Download"><svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 1v8M3 6l3 3 3-3"/><path d="M1 9v2h10V9"/></svg></button>`:''}
        <button class="btn btn-sm btn-icon" onclick="event.stopPropagation();deleteItem('${escapeHtml(item.name)}')" title="Delete" style="color:var(--danger)"><svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 3h10M3.5 3V2a1 1 0 011-1h3a1 1 0 011 1v1M9 3v7a1 1 0 01-1 1H4a1 1 0 01-1-1V3"/></svg></button>
      </div>
    </div>`;
  });
  body.innerHTML='<div class="fm-list">'+html+'</div>';
}

function filterFiles(){renderFiles(allFileItems)}
function buildBreadcrumb(){
  const el=document.getElementById('fmBreadcrumb');
  const parts=currentPath?currentPath.split('/').filter(Boolean):[];
  let html='<button class="fm-crumb '+(parts.length===0?'active':'')+'" onclick="loadFiles(\\'\\')">root</button>';
  let acc='';
  parts.forEach((p,i)=>{
    acc+=(acc?'/':'')+p;
    const a=acc;
    html+='<span class="fm-crumb-sep">/</span>';
    html+='<button class="fm-crumb '+(i===parts.length-1?'active':'')+'" onclick="loadFiles(\''+a+'\')">'+escapeHtml(p)+'</button>';
  });
  el.innerHTML=html;
}
function goUp(){
  const parts=currentPath.split('/').filter(Boolean);
  parts.pop();
  loadFiles(parts.join('/'));
}
function fmDblClick(name,isDir){
  if(isDir)loadFiles((currentPath?currentPath+'/':'')+name);
  else editFile(name);
}

async function editFile(name){
  const fpath=(currentPath?currentPath+'/':'')+name;
  try{
    const r=await fetch('/api/fs/read?path='+encodeURIComponent(fpath));
    if(!r.ok){toast('Cannot open: '+await r.text(),'error');return}
    const text=await r.text();
    editingFile=fpath;
    document.getElementById('editorFilename').textContent=fpath;
    document.getElementById('editorContent').value=text;
    document.getElementById('editorTab').style.display='';
    switchTab('editor');
    toast('Opened '+name,'info');
  }catch(e){toast('Failed to open file','error')}
}
async function saveFile(){
  if(!editingFile)return;
  try{
    const fd=new FormData();
    fd.append('path',editingFile);
    fd.append('content',document.getElementById('editorContent').value);
    const r=await fetch('/api/fs/write',{method:'POST',body:fd});
    if(r.ok)toast('Saved '+editingFile,'success');
    else toast('Save failed','error');
  }catch(e){toast('Save error','error')}
}
function closeEditor(){
  switchTab('files');
  document.getElementById('editorTab').style.display='none';
}
function downloadFile(name){
  const fpath=(currentPath?currentPath+'/':'')+name;
  window.open('/api/fs/download?path='+encodeURIComponent(fpath),'_blank');
}
function downloadCurrentFile(){
  if(editingFile)window.open('/api/fs/download?path='+encodeURIComponent(editingFile),'_blank');
}
async function deleteItem(name){
  if(!confirm('Delete "'+name+'"?'))return;
  const fpath=(currentPath?currentPath+'/':'')+name;
  try{
    const fd=new FormData();fd.append('path',fpath);
    await fetch('/api/fs/delete',{method:'POST',body:fd});
    toast('Deleted '+name,'success');
    loadFiles(currentPath);
  }catch(e){toast('Delete failed','error')}
}
async function createNewFile(){
  const name=prompt('Enter filename (or foldername/):');
  if(!name)return;
  const fpath=(currentPath?currentPath+'/':'')+name;
  if(name.endsWith('/')){
    // Create directory by writing a temp file and deleting it — or we can use the write endpoint
    toast('Creating directories not supported yet','info');
    return;
  }
  try{
    const fd=new FormData();fd.append('path',fpath);fd.append('content','');
    await fetch('/api/fs/write',{method:'POST',body:fd});
    toast('Created '+name,'success');
    loadFiles(currentPath);
  }catch(e){toast('Failed','error')}
}

// Upload
function showUploadModal(){
  document.getElementById('uploadOverlay').classList.add('active');
  document.getElementById('uploadPathDisplay').textContent='to /'+(currentPath||'');
  document.getElementById('uploadFileName').textContent='No file selected';
  document.getElementById('uploadFileInput').value='';
}
function hideUploadModal(){document.getElementById('uploadOverlay').classList.remove('active')}
function handleFileSelect(inp){
  if(inp.files.length)document.getElementById('uploadFileName').textContent=inp.files[0].name;
}
async function doUpload(){
  const inp=document.getElementById('uploadFileInput');
  if(!inp.files.length){toast('Select a file first','error');return}
  const fd=new FormData();fd.append('path',currentPath);fd.append('file',inp.files[0]);
  document.getElementById('uploadBtn').textContent='Uploading...';
  try{
    await fetch('/api/fs/upload',{method:'POST',body:fd});
    toast('Uploaded '+inp.files[0].name,'success');
    hideUploadModal();
    loadFiles(currentPath);
  }catch(e){toast('Upload failed','error')}
  document.getElementById('uploadBtn').textContent='Upload';
}
// Drag & drop
const uploadZone=document.getElementById('uploadZone');
uploadZone.addEventListener('dragover',e=>{e.preventDefault();uploadZone.classList.add('dragover')});
uploadZone.addEventListener('dragleave',()=>uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop',e=>{
  e.preventDefault();uploadZone.classList.remove('dragover');
  if(e.dataTransfer.files.length){
    document.getElementById('uploadFileInput').files=e.dataTransfer.files;
    document.getElementById('uploadFileName').textContent=e.dataTransfer.files[0].name;
  }
});

// Context Menu
function fmCtx(e,name,isDir){
  e.preventDefault();e.stopPropagation();
  ctxTarget={name,isDir};
  const menu=document.getElementById('ctxMenu');
  menu.classList.add('active');
  // Position
  const x=Math.min(e.clientX,window.innerWidth-170);
  const y=Math.min(e.clientY,window.innerHeight-200);
  menu.style.left=x+'px';menu.style.top=y+'px';
}
document.addEventListener('click',()=>document.getElementById('ctxMenu').classList.remove('active'));
function ctxAction(action){
  if(!ctxTarget)return;
  const{name,isDir}=ctxTarget;
  document.getElementById('ctxMenu').classList.remove('active');
  switch(action){
    case'open':fmDblClick(name,isDir);break;
    case'edit':if(!isDir)editFile(name);break;
    case'download':if(!isDir)downloadFile(name);break;
    case'rename':
      const nn=prompt('Rename to:',name);
      if(nn&&nn!==name)toast('Rename not implemented yet','info');
      break;
    case'delete':deleteItem(name);break;
  }
}

// ========== TOAST ==========
function toast(msg,type='info'){
  const c=document.getElementById('toastContainer');
  const t=document.createElement('div');
  t.className='toast toast-'+type;
  const icons={success:'✓',error:'✕',info:'ℹ'};
  t.innerHTML='<span>'+(icons[type]||'ℹ')+'</span><span>'+escapeHtml(msg)+'</span>';
  c.appendChild(t);
  setTimeout(()=>t.remove(),3000);
}

// ========== MOBILE ==========
function toggleMobileStats(){
  const el=document.getElementById('mobileStats');
  el.style.display=el.style.display==='flex'?'none':'flex';
}

// ========== KEYBOARD SHORTCUTS ==========
document.addEventListener('keydown',e=>{
  if(e.ctrlKey&&e.key==='s'){e.preventDefault();if(editingFile)saveFile()}
  if(e.ctrlKey&&e.key==='`'){e.preventDefault();switchTab('console');consoleInput.focus()}
});

// ========== INIT ==========
connectWS();
loadFiles('');
</script>
</body>
</html>
"""

# -----------------
# UTILITIES
# -----------------
def get_safe_path(subpath: str):
    subpath = (subpath or "").strip("/")
    target = os.path.abspath(os.path.join(BASE_DIR, subpath))
    if not target.startswith(BASE_DIR):
        raise HTTPException(status_code=403, detail="Access denied outside /app")
    return target

async def broadcast(message: str):
    output_history.append(message)
    dead_clients = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except:
            dead_clients.add(client)
    connected_clients.difference_update(dead_clients)

# -----------------
# SERVER PROCESSES
# -----------------
async def read_stream(stream, prefix=""):
    while True:
        try:
            line = await stream.readline()
            if not line:
                break
            line_str = line.decode('utf-8', errors='replace').rstrip('\r\n')
            await broadcast(prefix + line_str)
        except Exception:
            break

async def start_minecraft():
    global mc_process
    java_args = [
        "java", "-server", "-Xmx8G", "-Xms8G", "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled",
        "-XX:ParallelGCThreads=2", "-XX:ConcGCThreads=1", "-XX:MaxGCPauseMillis=50",
        "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
        "-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=50", "-XX:G1HeapRegionSize=16M",
        "-XX:G1ReservePercent=15", "-XX:G1HeapWastePercent=5", "-XX:G1MixedGCCountTarget=3",
        "-XX:InitiatingHeapOccupancyPercent=10", "-XX:G1MixedGCLiveThresholdPercent=90",
        "-XX:G1RSetUpdatingPauseTimePercent=5", "-XX:SurvivorRatio=32", "-XX:+PerfDisableSharedMem",
        "-XX:MaxTenuringThreshold=1", "-XX:G1SATBBufferEnqueueingThresholdPercent=30",
        "-XX:G1ConcMarkStepDurationMillis=5", "-XX:G1ConcRSHotCardLimit=16",
        "-XX:+UseStringDeduplication", "-Dfile.encoding=UTF-8", "-Dspring.output.ansi.enabled=ALWAYS",
        "-jar", "purpur.jar", "--nogui"
    ]
    mc_process = await asyncio.create_subprocess_exec(
        *java_args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=BASE_DIR
    )
    asyncio.create_task(read_stream(mc_process.stdout))

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_minecraft())

# -----------------
# API ROUTING
# -----------------
@app.get("/")
def get_panel():
    return HTMLResponse(content=HTML_CONTENT)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    for line in output_history:
        await websocket.send_text(line)
    try:
        while True:
            cmd = await websocket.receive_text()
            if mc_process and mc_process.stdin:
                mc_process.stdin.write((cmd + "\n").encode('utf-8'))
                await mc_process.stdin.drain()
    except:
        connected_clients.discard(websocket)

@app.get("/api/stats")
def get_stats():
    try:
        current_process = psutil.Process(os.getpid())
        mem_usage = current_process.memory_info().rss
        cpu_percent = current_process.cpu_percent(interval=0)

        for child in current_process.children(recursive=True):
            try:
                mem_usage += child.memory_info().rss
                cpu_percent += child.cpu_percent(interval=0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Normalize CPU to 0-100% for 2 cores
        normalized_cpu = min(100.0, cpu_percent / CONTAINER_CPU_CORES)

        # Disk usage for the container's BASE_DIR
        try:
            disk = shutil.disk_usage(BASE_DIR)
            disk_used_gb = disk.used / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)
        except Exception:
            disk_used_gb = 0
            disk_total_gb = CONTAINER_STORAGE_GB

        return {
            "ram_used_mb": round(mem_usage / (1024 * 1024), 1),
            "ram_total_mb": CONTAINER_RAM_MB,
            "cpu_percent": round(normalized_cpu, 1),
            "cpu_cores": CONTAINER_CPU_CORES,
            "disk_used_gb": round(disk_used_gb, 2),
            "disk_total_gb": round(disk_total_gb, 2),
        }
    except Exception:
        return {
            "ram_used_mb": 0, "ram_total_mb": CONTAINER_RAM_MB,
            "cpu_percent": 0, "cpu_cores": CONTAINER_CPU_CORES,
            "disk_used_gb": 0, "disk_total_gb": CONTAINER_STORAGE_GB,
        }

@app.get("/api/fs/list")
def fs_list(path: str = ""):
    target = get_safe_path(path)
    if not os.path.exists(target):
        return []
    items = []
    try:
        for f in os.listdir(target):
            fp = os.path.join(target, f)
            try:
                is_dir = os.path.isdir(fp)
                size = 0 if is_dir else os.path.getsize(fp)
                items.append({"name": f, "is_dir": is_dir, "size": size})
            except OSError:
                pass
    except PermissionError:
        pass
    return sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower()))

@app.get("/api/fs/read")
def fs_read(path: str):
    target = get_safe_path(path)
    if not os.path.isfile(target):
        raise HTTPException(400, "Not a file")
    try:
        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(5 * 1024 * 1024)  # Max 5MB read
        return Response(content=content, media_type="text/plain")
    except Exception as e:
        raise HTTPException(400, f"Cannot read: {str(e)}")

@app.get("/api/fs/download")
def fs_download(path: str):
    target = get_safe_path(path)
    if not os.path.isfile(target):
        raise HTTPException(400, "Not a file")
    return FileResponse(target, filename=os.path.basename(target))

@app.post("/api/fs/write")
def fs_write(path: str = Form(...), content: str = Form(...)):
    target = get_safe_path(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w', encoding='utf-8') as f:
        f.write(content)
    return {"status": "ok"}

@app.post("/api/fs/upload")
async def fs_upload(path: str = Form(""), file: UploadFile = File(...)):
    target_dir = get_safe_path(path)
    os.makedirs(target_dir, exist_ok=True)
    target_file = os.path.join(target_dir, file.filename)
    if not os.path.abspath(target_file).startswith(BASE_DIR):
        raise HTTPException(403, "Access denied")
    with open(target_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "ok"}

@app.post("/api/fs/delete")
def fs_delete(path: str = Form(...)):
    target = get_safe_path(path)
    if not os.path.exists(target):
        raise HTTPException(404, "Not found")
    if os.path.isdir(target):
        shutil.rmtree(target)
    else:
        os.remove(target)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")