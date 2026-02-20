import os
import asyncio
import collections
import shutil
from fastapi import FastAPI, WebSocket, Request, Response, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Global State
mc_process = None
output_history = collections.deque(maxlen=300)
connected_clients = set()

# Configuration
# Change this to "." if running locally on Windows/Linux outside of Docker
BASE_DIR = os.path.abspath(".") 
SERVER_JAR = "purpur.jar" # Change this to your jar name

# -----------------
# HTML FRONTEND (Your Design + Wired Logic)
# -----------------
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>OrbitMC — Server Panel</title>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{
--bg:#0a0a0f;
--surface:#12121a;
--surface2:#1a1a26;
--surface3:#222233;
--border:#2a2a3a;
--border2:#333346;
--text:#e8e8f0;
--text2:#9999b0;
--text3:#666680;
--accent:#6c5ce7;
--accent2:#7c6ef7;
--accent-glow:rgba(108,92,231,.15);
--green:#00d67e;
--red:#ff4757;
--orange:#ffa502;
--yellow:#ffc312;
--radius:12px;
--radius-sm:8px;
--radius-xs:6px;
--transition:all .2s cubic-bezier(.4,0,.2,1);
--shadow:0 4px 24px rgba(0,0,0,.4);
--shadow-lg:0 8px 40px rgba(0,0,0,.6);
}

html{font-size:14px;-webkit-tap-highlight-color:transparent}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);overflow:hidden;height:100dvh;width:100vw;display:flex;flex-direction:column}

/* Scrollbar */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--border2)}

/* Animations */
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeInScale{from{opacity:0;transform:scale(.95) translateY(8px)}to{opacity:1;transform:scale(1) translateY(0)}}
@keyframes slideUp{from{opacity:0;transform:translateY(100%)}to{opacity:1;transform:translateY(0)}}
@keyframes slideRight{from{opacity:0;transform:translateX(-20px)}to{opacity:1;transform:translateX(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes ripple{to{transform:scale(4);opacity:0}}
@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
@keyframes blink{0%,50%{opacity:1}51%,100%{opacity:0}}
@keyframes toast-in{from{opacity:0;transform:translateX(100%)}to{opacity:1;transform:translateX(0)}}
@keyframes toast-out{from{opacity:1;transform:translateX(0)}to{opacity:0;transform:translateX(100%)}}

/* Header */
.header{
display:flex;align-items:center;justify-content:space-between;
padding:12px 20px;
background:var(--surface);
border-bottom:1px solid var(--border);
flex-shrink:0;
z-index:100;
backdrop-filter:blur(20px);
-webkit-backdrop-filter:blur(20px);
}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1.2rem;letter-spacing:-.02em}
.logo-icon{
width:32px;height:32px;
background:linear-gradient(135deg,var(--accent),#a855f7);
border-radius:8px;
display:flex;align-items:center;justify-content:center;
font-size:14px;font-weight:800;color:#fff;
box-shadow:0 2px 12px rgba(108,92,231,.4);
position:relative;
overflow:hidden;
}
.logo-icon::after{
content:'';position:absolute;inset:0;
background:linear-gradient(135deg,transparent 40%,rgba(255,255,255,.15) 50%,transparent 60%);
animation:shimmer 3s infinite;
background-size:200% 100%;
}
.server-status{display:flex;align-items:center;gap:8px;font-size:.8rem;color:var(--text2)}
.status-dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 2s infinite}
.status-dot.offline{background:var(--red);box-shadow:0 0 8px var(--red)}

/* Nav */
.nav{
display:flex;
gap:2px;
padding:8px 12px;
background:var(--surface);
border-bottom:1px solid var(--border);
flex-shrink:0;
overflow-x:auto;
-webkit-overflow-scrolling:touch;
scrollbar-width:none;
}
.nav::-webkit-scrollbar{display:none}
.nav-item{
position:relative;
display:flex;align-items:center;gap:8px;
padding:10px 16px;
border-radius:var(--radius-sm);
font-size:.82rem;font-weight:500;
color:var(--text2);
cursor:pointer;
transition:var(--transition);
white-space:nowrap;
user-select:none;
-webkit-user-select:none;
border:none;background:none;
flex-shrink:0;
}
.nav-item:hover{color:var(--text);background:var(--surface2)}
.nav-item.active{color:var(--text);background:var(--accent-glow)}
.nav-item.active::after{
content:'';position:absolute;bottom:0;left:50%;transform:translateX(-50%);
width:20px;height:2px;background:var(--accent);border-radius:1px;
}
.nav-item svg{width:16px;height:16px;flex-shrink:0}
.nav-badge{
font-size:.6rem;padding:2px 6px;
background:var(--surface3);color:var(--text3);
border-radius:4px;font-weight:600;text-transform:uppercase;
letter-spacing:.05em;
}
.nav-item.disabled{opacity:.4;pointer-events:none}

/* Content */
.content{flex:1;overflow:hidden;position:relative}
.panel{display:none;height:100%;flex-direction:column;animation:fadeIn .3s ease}
.panel.active{display:flex}

/* Console */
.console-wrap{flex:1;display:flex;flex-direction:column;position:relative;overflow:hidden}
.console-terminal{
flex:1;
overflow-y:auto;
padding:16px;
font-family:'JetBrains Mono','Fira Code','Cascadia Code',monospace;
font-size:.78rem;
line-height:1.7;
position:relative;
scroll-behavior:smooth;
overscroll-behavior:contain;
}
.console-terminal::before{
content:'';position:sticky;top:0;left:0;right:0;
display:block;height:40px;margin-bottom:-40px;
background:linear-gradient(var(--bg),transparent);
pointer-events:none;z-index:2;
}
.console-line{
word-wrap:break-word;
overflow-wrap:break-word;
white-space:pre-wrap;
padding:1px 0;
animation:slideRight .15s ease;
}
.console-line .time{color:var(--text3);margin-right:8px;font-size:.72rem}
.console-line .info{color:#5b9bd5}
.console-line .warn{color:var(--orange)}
.console-line .error{color:var(--red)}
.console-line .server{color:var(--green)}
.console-line .player{color:var(--yellow)}
.console-line .cmd{color:var(--accent2)}

.console-input-wrap{
display:flex;gap:8px;
padding:12px 16px;
background:var(--surface);
border-top:1px solid var(--border);
flex-shrink:0;
}
.console-input-prefix{
color:var(--accent);font-family:'JetBrains Mono',monospace;
font-size:.82rem;display:flex;align-items:center;
user-select:none;font-weight:600;flex-shrink:0;
}
.console-input{
flex:1;background:none;border:none;outline:none;
color:var(--text);font-family:'JetBrains Mono',monospace;
font-size:.82rem;caret-color:var(--accent);
}
.console-input::placeholder{color:var(--text3)}
.console-send-btn{
background:var(--accent);color:#fff;border:none;
padding:8px 16px;border-radius:var(--radius-xs);
cursor:pointer;font-size:.78rem;font-weight:600;
transition:var(--transition);display:flex;align-items:center;gap:6px;
flex-shrink:0;
}
.console-send-btn:hover{background:var(--accent2);transform:translateY(-1px)}
.console-send-btn:active{transform:translateY(0)}
.console-send-btn svg{width:14px;height:14px}

/* File Manager */
.fm{display:flex;flex-direction:column;height:100%}
.fm-toolbar{
display:flex;align-items:center;gap:8px;
padding:10px 16px;
background:var(--surface);
border-bottom:1px solid var(--border);
flex-shrink:0;
flex-wrap:wrap;
}
.fm-breadcrumb{
display:flex;align-items:center;gap:2px;
flex:1;min-width:0;
overflow-x:auto;
scrollbar-width:none;
-webkit-overflow-scrolling:touch;
padding:4px 0;
}
.fm-breadcrumb::-webkit-scrollbar{display:none}
.fm-crumb{
padding:4px 8px;border-radius:var(--radius-xs);
font-size:.78rem;color:var(--text2);
cursor:pointer;transition:var(--transition);
white-space:nowrap;flex-shrink:0;
background:none;border:none;
}
.fm-crumb:hover{color:var(--text);background:var(--surface2)}
.fm-crumb.active{color:var(--text);font-weight:600}
.fm-crumb-sep{color:var(--text3);font-size:.7rem;flex-shrink:0}
.fm-actions{display:flex;gap:4px;flex-shrink:0}
.fm-btn{
display:flex;align-items:center;justify-content:center;gap:6px;
padding:8px 12px;border-radius:var(--radius-xs);
font-size:.75rem;font-weight:500;
color:var(--text2);background:var(--surface2);
border:1px solid var(--border);cursor:pointer;
transition:var(--transition);white-space:nowrap;
position:relative;overflow:hidden;
}
.fm-btn:hover{color:var(--text);background:var(--surface3);border-color:var(--border2)}
.fm-btn:active{transform:scale(.97)}
.fm-btn svg{width:14px;height:14px;flex-shrink:0}
.fm-btn.accent{background:var(--accent);color:#fff;border-color:var(--accent)}
.fm-btn.accent:hover{background:var(--accent2)}
.fm-btn .btn-label{display:inline}

.fm-list{flex:1;overflow-y:auto;padding:8px;overscroll-behavior:contain}
.fm-item{
display:flex;align-items:center;gap:12px;
padding:10px 14px;border-radius:var(--radius-sm);
cursor:pointer;transition:var(--transition);
position:relative;
animation:fadeIn .2s ease;
user-select:none;
-webkit-user-select:none;
border:1px solid transparent;
}
.fm-item:hover{background:var(--surface2);border-color:var(--border)}
.fm-item:active{background:var(--surface3)}
.fm-item.selected{background:var(--accent-glow);border-color:rgba(108,92,231,.3)}
.fm-item-icon{
width:36px;height:36px;border-radius:var(--radius-xs);
display:flex;align-items:center;justify-content:center;
flex-shrink:0;font-size:.75rem;
}
.fm-item-icon.folder{background:rgba(255,165,2,.1);color:var(--orange)}
.fm-item-icon.file{background:rgba(108,92,231,.1);color:var(--accent)}
.fm-item-icon.jar{background:rgba(0,214,126,.1);color:var(--green)}
.fm-item-icon.yml{background:rgba(91,155,213,.1);color:#5b9bd5}
.fm-item-icon.log{background:rgba(255,71,87,.1);color:var(--red)}
.fm-item-icon.json{background:rgba(255,195,18,.1);color:var(--yellow)}
.fm-item-icon.properties{background:rgba(168,85,247,.1);color:#a855f7}
.fm-item-info{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.fm-item-name{font-size:.82rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fm-item-meta{font-size:.7rem;color:var(--text3);display:flex;gap:12px}
.fm-item-actions{
display:flex;gap:2px;
opacity:0;transition:var(--transition);flex-shrink:0;
}
.fm-item:hover .fm-item-actions{opacity:1}
.fm-action-btn{
width:30px;height:30px;border-radius:var(--radius-xs);
display:flex;align-items:center;justify-content:center;
background:none;border:none;color:var(--text3);
cursor:pointer;transition:var(--transition);
}
.fm-action-btn:hover{color:var(--text);background:var(--surface3)}
.fm-action-btn.danger:hover{color:var(--red);background:rgba(255,71,87,.1)}
.fm-action-btn svg{width:14px;height:14px}

.fm-empty{
display:flex;flex-direction:column;align-items:center;justify-content:center;
height:100%;color:var(--text3);gap:12px;
}
.fm-empty svg{width:48px;height:48px;opacity:.3}
.fm-empty-text{font-size:.85rem}

/* Mobile file actions */
.fm-mobile-actions{display:none}

/* Config Panel */
.config-wrap{display:flex;flex-direction:column;height:100%;overflow:hidden}
.config-header{
display:flex;align-items:center;justify-content:space-between;
padding:16px 20px;
background:var(--surface);
border-bottom:1px solid var(--border);
flex-shrink:0;
}
.config-title{font-size:.9rem;font-weight:600;display:flex;align-items:center;gap:8px}
.config-title svg{width:18px;height:18px;color:var(--accent)}
.config-body{flex:1;overflow-y:auto;padding:16px 20px;overscroll-behavior:contain}
.config-section{margin-bottom:24px;animation:fadeIn .3s ease}
.config-section-title{
font-size:.72rem;font-weight:600;text-transform:uppercase;
letter-spacing:.08em;color:var(--text3);margin-bottom:12px;
padding-bottom:8px;border-bottom:1px solid var(--border);
}
.config-field{
display:flex;flex-direction:column;gap:6px;
padding:12px 0;
border-bottom:1px solid rgba(42,42,58,.5);
}
.config-field:last-child{border-bottom:none}
.config-label{
display:flex;align-items:center;justify-content:space-between;
}
.config-label-text{font-size:.82rem;font-weight:500}
.config-label-key{font-size:.68rem;color:var(--text3);font-family:monospace}
.config-input{
width:100%;padding:10px 12px;
background:var(--surface2);border:1px solid var(--border);
border-radius:var(--radius-xs);color:var(--text);
font-size:.82rem;outline:none;transition:var(--transition);
font-family:inherit;
}
.config-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.config-input::placeholder{color:var(--text3)}
select.config-input{cursor:pointer;appearance:none;
background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239999b0' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
background-repeat:no-repeat;background-position:right 12px center;
padding-right:32px;
}
.config-toggle{
position:relative;width:44px;height:24px;flex-shrink:0;
}
.config-toggle input{opacity:0;width:0;height:0;position:absolute}
.config-toggle-track{
position:absolute;inset:0;
background:var(--surface3);border-radius:12px;
cursor:pointer;transition:var(--transition);
border:1px solid var(--border);
}
.config-toggle-track::after{
content:'';position:absolute;top:3px;left:3px;
width:16px;height:16px;border-radius:50%;
background:#fff;transition:var(--transition);
box-shadow:0 1px 3px rgba(0,0,0,.3);
}
.config-toggle input:checked+.config-toggle-track{background:var(--accent);border-color:var(--accent)}
.config-toggle input:checked+.config-toggle-track::after{transform:translateX(20px)}

/* Modal / Overlay */
.modal-overlay{
position:fixed;inset:0;
background:rgba(0,0,0,.7);
backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
z-index:1000;
display:none;align-items:center;justify-content:center;
padding:20px;
opacity:0;transition:opacity .2s ease;
}
.modal-overlay.show{display:flex;opacity:1}
.modal{
background:var(--surface);
border:1px solid var(--border);
border-radius:var(--radius);
width:100%;max-width:420px;
box-shadow:var(--shadow-lg);
animation:fadeInScale .25s ease;
overflow:hidden;
}
.modal-head{
display:flex;align-items:center;justify-content:space-between;
padding:16px 20px;
border-bottom:1px solid var(--border);
}
.modal-title{font-size:.9rem;font-weight:600;display:flex;align-items:center;gap:8px}
.modal-close{
width:28px;height:28px;border-radius:var(--radius-xs);
display:flex;align-items:center;justify-content:center;
background:none;border:none;color:var(--text3);cursor:pointer;
transition:var(--transition);
}
.modal-close:hover{color:var(--text);background:var(--surface2)}
.modal-close svg{width:16px;height:16px}
.modal-body{padding:20px}
.modal-body p{font-size:.82rem;color:var(--text2);line-height:1.6;margin-bottom:16px}
.modal-input{
width:100%;padding:10px 12px;
background:var(--surface2);border:1px solid var(--border);
border-radius:var(--radius-xs);color:var(--text);
font-size:.82rem;outline:none;transition:var(--transition);
font-family:inherit;
}
.modal-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.modal-input::placeholder{color:var(--text3)}
.modal-foot{
display:flex;gap:8px;justify-content:flex-end;
padding:14px 20px;
border-top:1px solid var(--border);
background:rgba(0,0,0,.1);
}
.modal-btn{
padding:8px 20px;border-radius:var(--radius-xs);
font-size:.8rem;font-weight:500;cursor:pointer;
transition:var(--transition);border:1px solid var(--border);
background:var(--surface2);color:var(--text);
}
.modal-btn:hover{background:var(--surface3)}
.modal-btn:active{transform:scale(.97)}
.modal-btn.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.modal-btn.primary:hover{background:var(--accent2)}
.modal-btn.danger{background:var(--red);color:#fff;border-color:var(--red)}
.modal-btn.danger:hover{background:#ff6b7a}

/* Context Menu */
.context-menu{
position:fixed;
background:var(--surface);
border:1px solid var(--border);
border-radius:var(--radius-sm);
box-shadow:var(--shadow-lg);
z-index:900;
min-width:180px;
padding:4px;
animation:fadeInScale .15s ease;
display:none;
}
.context-menu.show{display:block}
.ctx-item{
display:flex;align-items:center;gap:10px;
padding:8px 12px;border-radius:var(--radius-xs);
font-size:.78rem;color:var(--text2);
cursor:pointer;transition:var(--transition);
border:none;background:none;width:100%;text-align:left;
}
.ctx-item:hover{color:var(--text);background:var(--surface2)}
.ctx-item.danger{color:var(--red)}
.ctx-item.danger:hover{background:rgba(255,71,87,.1)}
.ctx-item svg{width:14px;height:14px;flex-shrink:0}
.ctx-sep{height:1px;background:var(--border);margin:4px 8px}

/* Toast */
.toast-container{
position:fixed;top:70px;right:16px;
z-index:2000;display:flex;flex-direction:column;gap:8px;
pointer-events:none;
}
.toast{
display:flex;align-items:center;gap:10px;
padding:12px 16px;border-radius:var(--radius-sm);
background:var(--surface);border:1px solid var(--border);
box-shadow:var(--shadow);
font-size:.78rem;color:var(--text);
animation:toast-in .3s ease;
pointer-events:auto;
max-width:320px;
}
.toast.removing{animation:toast-out .3s ease forwards}
.toast-icon{width:18px;height:18px;flex-shrink:0}
.toast.success .toast-icon{color:var(--green)}
.toast.error .toast-icon{color:var(--red)}
.toast.warning .toast-icon{color:var(--orange)}
.toast.info .toast-icon{color:var(--accent)}

/* Upload area */
.upload-area{
border:2px dashed var(--border);
border-radius:var(--radius);
padding:32px;
display:flex;flex-direction:column;align-items:center;justify-content:center;
gap:12px;
cursor:pointer;transition:var(--transition);
min-height:120px;
}
.upload-area:hover,.upload-area.dragover{border-color:var(--accent);background:var(--accent-glow)}
.upload-area svg{width:32px;height:32px;color:var(--text3)}
.upload-area p{font-size:.8rem;color:var(--text2);text-align:center}
.upload-area .small{font-size:.7rem;color:var(--text3)}

/* Editor modal */
.editor-overlay{
position:fixed;inset:0;
background:rgba(0,0,0,.85);
backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
z-index:1000;
display:none;flex-direction:column;
opacity:0;transition:opacity .2s ease;
}
.editor-overlay.show{display:flex;opacity:1}
.editor-bar{
display:flex;align-items:center;justify-content:space-between;
padding:12px 20px;
background:var(--surface);
border-bottom:1px solid var(--border);
flex-shrink:0;
}
.editor-filename{font-size:.82rem;font-weight:500;display:flex;align-items:center;gap:8px}
.editor-filename svg{width:16px;height:16px;color:var(--accent)}
.editor-actions{display:flex;gap:8px}
.editor-textarea{
flex:1;width:100%;
background:var(--bg);
border:none;outline:none;
color:var(--text);
font-family:'JetBrains Mono','Fira Code',monospace;
font-size:.8rem;line-height:1.7;
padding:20px;
resize:none;
tab-size:4;
}

/* Loading */
.loading-bar{
position:fixed;top:0;left:0;
height:2px;background:linear-gradient(90deg,var(--accent),#a855f7);
z-index:9999;
transition:width .3s ease;
box-shadow:0 0 10px var(--accent);
}

/* Mobile responsive */
@media(max-width:768px){
.header{padding:10px 14px}
.logo{font-size:1rem}
.logo-icon{width:28px;height:28px;font-size:12px}
.server-status span{display:none}
.nav{padding:6px 8px;gap:1px}
.nav-item{padding:8px 12px;font-size:.78rem}
.nav-item .nav-text{display:none}
.nav-item svg{width:18px;height:18px}

.console-terminal{padding:12px;font-size:.72rem}
.console-input-wrap{padding:10px 12px}
.console-send-btn span{display:none}
.console-send-btn{padding:8px 12px}

.fm-toolbar{padding:8px 10px;gap:4px}
.fm-btn .btn-label{display:none}
.fm-btn{padding:8px 10px}
.fm-list{padding:4px}
.fm-item{padding:10px 10px;gap:10px}
.fm-item-icon{width:32px;height:32px}
.fm-item-actions{opacity:1}
.fm-action-btn{width:34px;height:34px}

.config-body{padding:12px 14px}

.modal{margin:12px;max-width:none}
.toast-container{right:8px;left:8px}
.toast{max-width:none}
}

@media(max-width:380px){
.nav-badge{display:none}
.fm-btn{padding:6px 8px}
.fm-action-btn{width:28px;height:28px}
}

/* Coming soon overlay for panel */
.coming-soon{
flex:1;display:flex;flex-direction:column;
align-items:center;justify-content:center;
gap:16px;color:var(--text3);
}
.coming-soon svg{width:64px;height:64px;opacity:.2}
.coming-soon h3{font-size:1.1rem;font-weight:600;color:var(--text2)}
.coming-soon p{font-size:.82rem;max-width:300px;text-align:center;line-height:1.6}

/* Ripple effect */
.ripple{
position:absolute;border-radius:50%;
background:rgba(255,255,255,.12);
transform:scale(0);animation:ripple .6s linear;
pointer-events:none;
}

/* Drag ghost */
.fm-item.dragging{opacity:.4}

/* Selection highlight */
::selection{background:rgba(108,92,231,.3)}
</style>
</head>
<body>

<!-- Loading bar -->
<div class="loading-bar" id="loadingBar" style="width:0"></div>

<!-- Header -->
<header class="header">
<div class="logo">
<div class="logo-icon">O</div>
<span>OrbitMC</span>
</div>
<div class="server-status">
<div class="status-dot" id="statusDot"></div>
<span>Online</span>
</div>
</header>

<!-- Navigation -->
<nav class="nav" id="nav">
<button class="nav-item active" data-panel="console" onclick="switchPanel('console')">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
<span class="nav-text">Console</span>
</button>
<button class="nav-item" data-panel="files" onclick="switchPanel('files')">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
<span class="nav-text">Files</span>
</button>
<button class="nav-item disabled" data-panel="plugins">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M12 8v8m-4-4h8"/></svg>
<span class="nav-text">Plugins</span>
<span class="nav-badge">Soon</span>
</button>
<button class="nav-item" data-panel="config" onclick="switchPanel('config')">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
<span class="nav-text">Config</span>
</button>
</nav>

<!-- Content -->
<main class="content">

<!-- Console Panel -->
<div class="panel active" id="panel-console">
<div class="console-wrap">
<div class="console-terminal" id="terminal"></div>
<div class="console-input-wrap">
<span class="console-input-prefix">›</span>
<input class="console-input" id="cmdInput" type="text" placeholder="Enter command..." autocomplete="off" spellcheck="false">
<button class="console-send-btn" onclick="sendCommand()">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
<span>Send</span>
</button>
</div>
</div>
</div>

<!-- Files Panel -->
<div class="panel" id="panel-files">
<div class="fm">
<div class="fm-toolbar">
<div class="fm-breadcrumb" id="breadcrumb"></div>
<div class="fm-actions">
<button class="fm-btn" onclick="showModal('newFile')" title="New File">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
<span class="btn-label">New File</span>
</button>
<button class="fm-btn" onclick="showModal('newFolder')" title="New Folder">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
<span class="btn-label">New Folder</span>
</button>
<button class="fm-btn accent" onclick="showModal('upload')" title="Upload">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3"/></svg>
<span class="btn-label">Upload</span>
</button>
</div>
</div>
<div class="fm-list" id="fileList"></div>
</div>
</div>

<!-- Plugins Panel (Coming Soon) -->
<div class="panel" id="panel-plugins">
<div class="coming-soon">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M12 8v8m-4-4h8"/></svg>
<h3>Plugins Manager</h3>
<p>We're building something amazing. Plugin management is coming in the next update.</p>
</div>
</div>

<!-- Config Panel -->
<div class="panel" id="panel-config">
<div class="config-wrap">
<div class="config-header">
<div class="config-title">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
server.properties
</div>
<button class="fm-btn accent" onclick="saveConfig()">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
<span class="btn-label">Save</span>
</button>
</div>
<div class="config-body" id="configBody"></div>
</div>
</div>

</main>

<!-- Modal Overlay -->
<div class="modal-overlay" id="modalOverlay" onclick="closeModalOutside(event)">
<div class="modal" id="modalContent"></div>
</div>

<!-- Editor Overlay -->
<div class="editor-overlay" id="editorOverlay">
<div class="editor-bar">
<div class="editor-filename" id="editorFilename">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
<span id="editorName"></span>
</div>
<div class="editor-actions">
<button class="fm-btn accent" onclick="saveFile()">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
<span class="btn-label">Save</span>
</button>
<button class="fm-btn" onclick="closeEditor()">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
</button>
</div>
</div>
<textarea class="editor-textarea" id="editorTextarea" spellcheck="false"></textarea>
</div>

<!-- Context Menu -->
<div class="context-menu" id="contextMenu"></div>

<!-- Toast Container -->
<div class="toast-container" id="toastContainer"></div>

<script>
// ===== State =====
let currentPath = '';
let commandHistory = [];
let historyIndex = -1;
let currentEditFile = null;
let ws = null;
let serverProps = {};

// ===== Console =====
function initConsole() {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${window.location.host}/ws`);
    
    ws.onopen = () => {
        addConsoleLine({time: getTime(), type: 'server', text: 'Connected to panel.'});
        document.getElementById('statusDot').classList.remove('offline');
    };
    
    ws.onclose = () => {
        addConsoleLine({time: getTime(), type: 'error', text: 'Disconnected from panel.'});
        document.getElementById('statusDot').classList.add('offline');
        setTimeout(initConsole, 3000);
    };

    ws.onmessage = (event) => {
        // Simple log parsing attempt
        const raw = event.data;
        let type = 'info';
        if (raw.toLowerCase().includes('error') || raw.toLowerCase().includes('exception')) type = 'error';
        else if (raw.toLowerCase().includes('warn')) type = 'warn';
        else if (raw.includes('<')) type = 'player';
        
        addConsoleLine({time: getTime(), type: type, text: raw});
    };
}

function getTime() {
    const now = new Date();
    return `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

function addConsoleLine(log) {
    const terminal = document.getElementById('terminal');
    const line = document.createElement('div');
    line.className = 'console-line';
    line.innerHTML = `<span class="time">${log.time}</span><span class="${log.type}">${escapeHtml(log.text)}</span>`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function sendCommand() {
    const input = document.getElementById('cmdInput');
    const cmd = input.value.trim();
    if (!cmd) return;

    commandHistory.unshift(cmd);
    historyIndex = -1;
    input.value = '';

    if(ws && ws.readyState === WebSocket.OPEN) {
        ws.send(cmd);
        addConsoleLine({ time: getTime(), type: 'cmd', text: `> ${cmd}` });
    } else {
        toast('Not connected to server', 'error');
    }
}

document.getElementById('cmdInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        sendCommand();
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (historyIndex < commandHistory.length - 1) {
            historyIndex++;
            this.value = commandHistory[historyIndex];
        }
    } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (historyIndex > 0) {
            historyIndex--;
            this.value = commandHistory[historyIndex];
        } else {
            historyIndex = -1;
            this.value = '';
        }
    }
});

// ===== Panel Switching =====
function switchPanel(name) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById(`panel-${name}`).classList.add('active');
    document.querySelector(`[data-panel="${name}"]`).classList.add('active');

    if (name === 'files') renderFiles();
    if (name === 'config') renderConfig();

    showLoading();
}

// ===== Loading Bar =====
function showLoading() {
    const bar = document.getElementById('loadingBar');
    bar.style.width = '0';
    bar.style.opacity = '1';
    requestAnimationFrame(() => {
        bar.style.width = '70%';
        setTimeout(() => {
            bar.style.width = '100%';
            setTimeout(() => {
                bar.style.opacity = '0';
                setTimeout(() => { bar.style.width = '0'; }, 300);
            }, 200);
        }, 300);
    });
}

// ===== File Manager =====
async function renderFiles() {
    renderBreadcrumb();
    const list = document.getElementById('fileList');
    list.innerHTML = '';
    
    try {
        const res = await fetch(`/api/fs/list?path=${encodeURIComponent(currentPath)}`);
        const files = await res.json();

        if (files.length === 0) {
            list.innerHTML = `
            <div class="fm-empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
            <div class="fm-empty-text">This folder is empty</div>
            </div>`;
            return;
        }

        list.innerHTML = files.map((f, i) => {
            const type = f.is_dir ? 'folder' : 'file';
            const iconClass = getFileIconClass(f.name, type);
            const iconSvg = f.is_dir ? folderSvg : fileSvg;
            const sizeStr = f.is_dir ? '' : formatSize(f.size);
            
            return `
            <div class="fm-item" data-name="${f.name}" data-type="${type}"
            onclick="handleFileClick(event, '${f.name}', '${type}')"
            oncontextmenu="showContextMenu(event, '${f.name}', '${type}')"
            style="animation-delay:${i * 20}ms">
            <div class="fm-item-icon ${iconClass}">${iconSvg}</div>
            <div class="fm-item-info">
            <div class="fm-item-name">${f.name}</div>
            <div class="fm-item-meta">
            ${sizeStr ? `<span>${sizeStr}</span>` : ''}
            </div>
            </div>
            <div class="fm-item-actions">
            ${!f.is_dir ? `
            <button class="fm-action-btn" onclick="event.stopPropagation();editFile('${f.name}')" title="Edit">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>` : ''}
            <button class="fm-action-btn" onclick="event.stopPropagation();showModal('rename','${f.name}')" title="Rename">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
            ${!f.is_dir ? `
            <button class="fm-action-btn" onclick="event.stopPropagation();downloadFile('${f.name}')" title="Download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </button>` : ''}
            <button class="fm-action-btn danger" onclick="event.stopPropagation();showModal('delete','${f.name}','${type}')" title="Delete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
            </button>
            </div>
            </div>`;
        }).join('');

    } catch (e) {
        toast('Failed to load files', 'error');
    }
}

const folderSvg = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>';
const fileSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';

function getFileIconClass(name, type) {
    if (type === 'folder') return 'folder';
    const ext = name.split('.').pop().toLowerCase();
    const map = { jar: 'jar', yml: 'yml', yaml: 'yml', log: 'log', gz: 'log', json: 'json', properties: 'properties' };
    return map[ext] || 'file';
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function handleFileClick(e, name, type) {
    if (e.target.closest('.fm-item-actions')) return;
    if (type === 'folder') {
        currentPath = currentPath ? `${currentPath}/${name}` : name;
        showLoading();
        renderFiles();
    } else {
        editFile(name);
    }
}

function renderBreadcrumb() {
    const bc = document.getElementById('breadcrumb');
    const parts = currentPath.split('/').filter(Boolean);
    let html = `<button class="fm-crumb ${parts.length === 0 ? 'active' : ''}" onclick="navigateTo('')">
    <svg style="width:14px;height:14px;vertical-align:middle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
    </button>`;
    let path = '';
    parts.forEach((p, i) => {
        path += (path ? '/' : '') + p;
        const isLast = i === parts.length - 1;
        html += `<span class="fm-crumb-sep">›</span>
        <button class="fm-crumb ${isLast ? 'active' : ''}" onclick="navigateTo('${path}')">${p}</button>`;
    });
    bc.innerHTML = html;
}

function navigateTo(path) {
    currentPath = path;
    showLoading();
    renderFiles();
}

// ===== Context Menu =====
function showContextMenu(e, name, type) {
    e.preventDefault();
    e.stopPropagation();
    const menu = document.getElementById('contextMenu');

    let items = '';
    if (type === 'folder') {
        items = `
        <button class="ctx-item" onclick="handleFileClick(event,'${name}','folder');hideContextMenu()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
        Open
        </button>
        <button class="ctx-item" onclick="showModal('rename','${name}');hideContextMenu()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
        Rename
        </button>
        <div class="ctx-sep"></div>
        <button class="ctx-item danger" onclick="showModal('delete','${name}','${type}');hideContextMenu()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
        Delete
        </button>`;
    } else {
        items = `
        <button class="ctx-item" onclick="editFile('${name}');hideContextMenu()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        Edit
        </button>
        <button class="ctx-item" onclick="showModal('rename','${name}');hideContextMenu()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
        Rename
        </button>
        <button class="ctx-item" onclick="downloadFile('${name}');hideContextMenu()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Download
        </button>
        <div class="ctx-sep"></div>
        <button class="ctx-item danger" onclick="showModal('delete','${name}','${type}');hideContextMenu()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
        Delete
        </button>`;
    }

    menu.innerHTML = items;
    menu.classList.add('show');

    // Position
    const x = e.clientX || e.touches?.[0]?.clientX || 100;
    const y = e.clientY || e.touches?.[0]?.clientY || 100;
    menu.style.left = Math.min(x, window.innerWidth - 200) + 'px';
    menu.style.top = Math.min(y, window.innerHeight - 200) + 'px';

    setTimeout(() => document.addEventListener('click', hideContextMenu, { once: true }), 10);
}

function hideContextMenu() {
    document.getElementById('contextMenu').classList.remove('show');
}

// ===== Modals =====
function showModal(type, arg1, arg2) {
    const overlay = document.getElementById('modalOverlay');
    const content = document.getElementById('modalContent');

    let html = '';
    switch (type) {
    case 'newFile':
    html = `
    <div class="modal-head">
    <div class="modal-title">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
    Create New File
    </div>
    <button class="modal-close" onclick="closeModal()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="modal-body">
    <input class="modal-input" id="modalInput" type="text" placeholder="filename.txt" autofocus>
    </div>
    <div class="modal-foot">
    <button class="modal-btn" onclick="closeModal()">Cancel</button>
    <button class="modal-btn primary" onclick="createNewFile()">Create</button>
    </div>`;
    break;

    case 'newFolder':
    html = `
    <div class="modal-head">
    <div class="modal-title">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--orange)"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
    Create New Folder
    </div>
    <button class="modal-close" onclick="closeModal()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="modal-body">
    <input class="modal-input" id="modalInput" type="text" placeholder="folder-name" autofocus>
    </div>
    <div class="modal-foot">
    <button class="modal-btn" onclick="closeModal()">Cancel</button>
    <button class="modal-btn primary" onclick="createNewFolder()">Create</button>
    </div>`;
    break;

    case 'rename':
    html = `
    <div class="modal-head">
    <div class="modal-title">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
    Rename
    </div>
    <button class="modal-close" onclick="closeModal()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="modal-body">
    <input class="modal-input" id="modalInput" type="text" value="${arg1}" autofocus>
    </div>
    <div class="modal-foot">
    <button class="modal-btn" onclick="closeModal()">Cancel</button>
    <button class="modal-btn primary" onclick="renameItem('${arg1}')">Rename</button>
    </div>`;
    break;

    case 'delete':
    html = `
    <div class="modal-head">
    <div class="modal-title">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--red)"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
    Delete ${arg2 === 'folder' ? 'Folder' : 'File'}
    </div>
    <button class="modal-close" onclick="closeModal()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="modal-body">
    <p>Are you sure you want to delete <strong style="color:var(--text)">${arg1}</strong>? This action cannot be undone.</p>
    </div>
    <div class="modal-foot">
    <button class="modal-btn" onclick="closeModal()">Cancel</button>
    <button class="modal-btn danger" onclick="deleteItem('${arg1}')">Delete</button>
    </div>`;
    break;

    case 'upload':
    html = `
    <div class="modal-head">
    <div class="modal-title">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3"/></svg>
    Upload Files
    </div>
    <button class="modal-close" onclick="closeModal()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="modal-body">
    <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileUpload').click()" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)" ondrop="handleDrop(event)">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3"/></svg>
    <p>Drop files here or click to browse</p>
    <p class="small">Max file size: 100MB</p>
    </div>
    <input type="file" id="fileUpload" multiple style="display:none" onchange="handleUpload(this.files)">
    </div>
    <div class="modal-foot">
    <button class="modal-btn" onclick="closeModal()">Close</button>
    </div>`;
    break;
    }

    content.innerHTML = html;
    overlay.classList.add('show');

    // Focus input after animation
    setTimeout(() => {
        const inp = document.getElementById('modalInput');
        if (inp) { inp.focus(); inp.select(); }
    }, 100);

    // Enter key
    setTimeout(() => {
        const inp = document.getElementById('modalInput');
        if (inp) {
            inp.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const btns = content.querySelectorAll('.modal-btn.primary, .modal-btn.danger');
                    if (btns.length) btns[btns.length - 1].click();
                }
            });
        }
    }, 50);
}

function closeModal() {
    document.getElementById('modalOverlay').classList.remove('show');
}

function closeModalOutside(e) {
    if (e.target === document.getElementById('modalOverlay')) closeModal();
}

// ===== Actions via API =====
async function createNewFile() {
    const name = document.getElementById('modalInput').value.trim();
    if (!name) return toast('Please enter a file name', 'warning');
    
    const formData = new FormData();
    const p = currentPath ? `${currentPath}/${name}` : name;
    formData.append('path', p);
    formData.append('content', '');

    try {
        await fetch('/api/fs/write', { method: 'POST', body: formData });
        closeModal();
        renderFiles();
        toast(`Created ${name}`, 'success');
    } catch(e) { toast('Error creating file', 'error'); }
}

async function createNewFolder() {
    const name = document.getElementById('modalInput').value.trim();
    if (!name) return toast('Please enter a folder name', 'warning');

    const formData = new FormData();
    const p = currentPath ? `${currentPath}/${name}` : name;
    formData.append('path', p);

    try {
        await fetch('/api/fs/mkdir', { method: 'POST', body: formData });
        closeModal();
        renderFiles();
        toast(`Created folder ${name}`, 'success');
    } catch(e) { toast('Error creating folder', 'error'); }
}

async function renameItem(oldName) {
    const newName = document.getElementById('modalInput').value.trim();
    if (!newName) return toast('Please enter a name', 'warning');
    if (newName === oldName) { closeModal(); return; }

    const oldPath = currentPath ? `${currentPath}/${oldName}` : oldName;
    const newPath = currentPath ? `${currentPath}/${newName}` : newName;
    
    const formData = new FormData();
    formData.append('old_path', oldPath);
    formData.append('new_path', newPath);

    try {
        await fetch('/api/fs/move', { method: 'POST', body: formData });
        closeModal();
        renderFiles();
        toast(`Renamed to ${newName}`, 'success');
    } catch(e) { toast('Error renaming item', 'error'); }
}

async function deleteItem(name) {
    const p = currentPath ? `${currentPath}/${name}` : name;
    const formData = new FormData();
    formData.append('path', p);

    try {
        await fetch('/api/fs/delete', { method: 'POST', body: formData });
        closeModal();
        renderFiles();
        toast(`Deleted ${name}`, 'success');
    } catch(e) { toast('Error deleting item', 'error'); }
}

function downloadFile(name) {
    const p = currentPath ? `${currentPath}/${name}` : name;
    window.location.href = `/api/fs/download?path=${encodeURIComponent(p)}`;
    toast(`Downloading ${name}...`, 'info');
}

function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
}
function handleDragLeave(e) {
    e.currentTarget.classList.remove('dragover');
}
function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    handleUpload(e.dataTransfer.files);
}
async function handleUpload(files) {
    if (!files.length) return;
    
    for (let i = 0; i < files.length; i++) {
        const formData = new FormData();
        formData.append('path', currentPath);
        formData.append('file', files[i]);
        await fetch('/api/fs/upload', { method: 'POST', body: formData });
    }

    closeModal();
    renderFiles();
    toast(`Uploaded ${files.length} file${files.length > 1 ? 's' : ''}`, 'success');
}

// ===== File Editor =====
async function editFile(name) {
    currentEditFile = name;
    document.getElementById('editorName').textContent = name;
    
    const p = currentPath ? `${currentPath}/${name}` : name;
    try {
        const res = await fetch(`/api/fs/read?path=${encodeURIComponent(p)}`);
        if(!res.ok) throw new Error('Cannot read file');
        const text = await res.text();
        document.getElementById('editorTextarea').value = text;
        document.getElementById('editorOverlay').classList.add('show');
        setTimeout(() => document.getElementById('editorTextarea').focus(), 100);
    } catch(e) {
        toast('Error reading file (maybe binary?)', 'error');
    }
}

async function saveFile() {
    const content = document.getElementById('editorTextarea').value;
    const p = currentPath ? `${currentPath}/${currentEditFile}` : currentEditFile;
    const formData = new FormData();
    formData.append('path', p);
    formData.append('content', content);

    try {
        await fetch('/api/fs/write', { method: 'POST', body: formData });
        toast(`Saved ${currentEditFile}`, 'success');
    } catch(e) {
        toast('Error saving file', 'error');
    }
}

function closeEditor() {
    document.getElementById('editorOverlay').classList.remove('show');
    currentEditFile = null;
}

// ===== Config Panel =====
// We parse server.properties for this UI
async function renderConfig() {
    const body = document.getElementById('configBody');
    body.innerHTML = '<div class="fm-empty-text">Loading configuration...</div>';
    
    try {
        const res = await fetch('/api/fs/read?path=server.properties');
        if(!res.ok) {
            body.innerHTML = '<div class="fm-empty-text">server.properties not found</div>';
            return;
        }
        const text = await res.text();
        
        // Parse properties
        serverProps = {};
        text.split('\n').forEach(line => {
            if(!line.startsWith('#') && line.includes('=')) {
                const [k, v] = line.split('=');
                if(k) serverProps[k.trim()] = v ? v.trim() : '';
            }
        });

        // Define UI Structure mapping to keys
        const configStruct = {
            'General': [
                { key: 'motd', label: 'Server MOTD', type: 'text' },
                { key: 'max-players', label: 'Max Players', type: 'text' },
                { key: 'server-port', label: 'Server Port', type: 'text' },
                { key: 'level-name', label: 'World Name', type: 'text' },
                { key: 'level-seed', label: 'World Seed', type: 'text', placeholder: 'Leave blank for random' },
                { key: 'gamemode', label: 'Default Gamemode', type: 'select', options: ['survival', 'creative', 'adventure', 'spectator'] },
                { key: 'difficulty', label: 'Difficulty', type: 'select', options: ['peaceful', 'easy', 'normal', 'hard'] },
            ],
            'Gameplay': [
                { key: 'pvp', label: 'PvP', type: 'toggle' },
                { key: 'allow-flight', label: 'Allow Flight', type: 'toggle' },
                { key: 'allow-nether', label: 'Allow Nether', type: 'toggle' },
                { key: 'generate-structures', label: 'Generate Structures', type: 'toggle' },
                { key: 'enable-command-block', label: 'Command Blocks', type: 'toggle' },
                { key: 'spawn-protection', label: 'Spawn Protection Radius', type: 'text' },
                { key: 'view-distance', label: 'View Distance', type: 'text' },
            ],
            'Security': [
                { key: 'online-mode', label: 'Online Mode', type: 'toggle' },
                { key: 'white-list', label: 'Whitelist', type: 'toggle' },
                { key: 'enforce-secure-profile', label: 'Enforce Secure Profile', type: 'toggle' },
                { key: 'enable-rcon', label: 'Enable RCON', type: 'toggle' },
            ],
        };

        let html = '';
        for (const [section, fields] of Object.entries(configStruct)) {
            html += `<div class="config-section">
            <div class="config-section-title">${section}</div>`;
            fields.forEach(f => {
                const val = serverProps[f.key] || '';
                html += `<div class="config-field">
                <div class="config-label">
                <span class="config-label-text">${f.label}</span>
                <span class="config-label-key">${f.key}</span>
                </div>`;

                if (f.type === 'toggle') {
                    const checked = val === 'true';
                    html += `<label class="config-toggle">
                    <input type="checkbox" ${checked ? 'checked' : ''} data-key="${f.key}">
                    <span class="config-toggle-track"></span>
                    </label>`;
                } else if (f.type === 'select') {
                    html += `<select class="config-input" data-key="${f.key}">
                    ${f.options.map(o => `<option value="${o}" ${o === val ? 'selected' : ''}>${o}</option>`).join('')}
                    </select>`;
                } else {
                    html += `<input class="config-input" type="text" value="${escapeHtml(val)}" placeholder="${f.placeholder || ''}" data-key="${f.key}">`;
                }
                html += '</div>';
            });
            html += '</div>';
        }
        body.innerHTML = html;

    } catch (e) {
        body.innerHTML = '<div class="fm-empty-text">Error loading config</div>';
    }
}

async function saveConfig() {
    showLoading();
    
    // Gather inputs
    document.querySelectorAll('[data-key]').forEach(el => {
        const key = el.getAttribute('data-key');
        let val;
        if(el.type === 'checkbox') val = el.checked ? 'true' : 'false';
        else val = el.value;
        serverProps[key] = val;
    });

    // Reconstruct file content
    let fileContent = '#Minecraft server properties\n#Generated by OrbitMC Panel\n';
    for(const [k,v] of Object.entries(serverProps)) {
        fileContent += `${k}=${v}\n`;
    }

    const formData = new FormData();
    formData.append('path', 'server.properties');
    formData.append('content', fileContent);

    try {
        await fetch('/api/fs/write', { method: 'POST', body: formData });
        toast('Configuration saved successfully', 'success');
    } catch(e) {
        toast('Error saving configuration', 'error');
    }
}

// ===== Toast =====
function toast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast ${type}`;

    const icons = {
        success: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        warning: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    };

    t.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
    container.appendChild(t);

    setTimeout(() => {
        t.classList.add('removing');
        setTimeout(() => t.remove(), 300);
    }, 3000);
}

// ===== Utilities =====
function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function pad(n) { return n.toString().padStart(2, '0'); }

// ===== Keyboard Shortcuts =====
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeEditor();
        hideContextMenu();
    }
});

// Close context menu on scroll
document.addEventListener('scroll', hideContextMenu, true);

// ===== Init =====
window.addEventListener('DOMContentLoaded', () => {
    showLoading();
    initConsole();
    renderFiles();
});
</script>
</body>
</html>
"""

# -----------------
# UTILITIES & SERVER
# -----------------
def get_safe_path(subpath: str):
    subpath = (subpath or "").strip("/")
    target = os.path.abspath(os.path.join(BASE_DIR, subpath))
    if not target.startswith(BASE_DIR):
        raise HTTPException(status_code=403, detail="Access denied")
    return target

async def broadcast(message: str):
    output_history.append(message)
    dead = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except:
            dead.add(client)
    connected_clients.difference_update(dead)

async def read_stream(stream):
    while True:
        try:
            line = await stream.readline()
            if not line: break
            await broadcast(line.decode('utf-8', errors='replace').rstrip('\r\n'))
        except Exception:
            break

async def start_minecraft():
    global mc_process
    jar_path = os.path.join(BASE_DIR, SERVER_JAR)
    
    if not os.path.exists(jar_path):
        await broadcast(f"Error: {SERVER_JAR} not found in {BASE_DIR}")
        return

    java_args = [
        "java", "-server", "-Xmx4G", "-Xms1G", 
        "-jar", SERVER_JAR, "--nogui"
    ]
    
    try:
        mc_process = await asyncio.create_subprocess_exec(
            *java_args, 
            stdin=asyncio.subprocess.PIPE, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.STDOUT, 
            cwd=BASE_DIR
        )
        await broadcast(f"Server started ({SERVER_JAR})")
        asyncio.create_task(read_stream(mc_process.stdout))
    except Exception as e:
        await broadcast(f"Failed to start server: {e}")

@app.on_event("startup")
async def startup_event():
    # Only start if the jar exists, otherwise we wait for upload
    asyncio.create_task(start_minecraft())

# -----------------
# API ROUTING
# -----------------
@app.get("/")
def get_panel(): return HTMLResponse(content=HTML_CONTENT)

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    # Send history on connect
    for line in output_history: await websocket.send_text(line)
    try:
        while True:
            cmd = await websocket.receive_text()
            if mc_process and mc_process.stdin:
                try:
                    mc_process.stdin.write((cmd + "\n").encode('utf-8'))
                    await mc_process.stdin.drain()
                except Exception as e:
                    await websocket.send_text(f"Error sending command: {e}")
            else:
                await websocket.send_text("Server is not running.")
    except:
        connected_clients.remove(websocket)

@app.get("/api/fs/list")
def fs_list(path: str = ""):
    target = get_safe_path(path)
    if not os.path.exists(target): return []
    items = []
    try:
        for f in os.listdir(target):
            fp = os.path.join(target, f)
            items.append({
                "name": f, 
                "is_dir": os.path.isdir(fp), 
                "size": os.path.getsize(fp) if not os.path.isdir(fp) else 0
            })
    except Exception:
        pass
    return sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower()))

@app.get("/api/fs/read")
def fs_read(path: str):
    target = get_safe_path(path)
    if not os.path.isfile(target): raise HTTPException(400, "Not a file")
    try:
        # Try reading as text
        with open(target, 'r', encoding='utf-8') as f: 
            return Response(content=f.read(), media_type="text/plain")
    except UnicodeDecodeError:
        raise HTTPException(400, "File is binary")
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/fs/download")
def fs_download(path: str):
    target = get_safe_path(path)
    if not os.path.isfile(target): raise HTTPException(400, "Not a file")
    return FileResponse(target, filename=os.path.basename(target))

@app.post("/api/fs/write")
def fs_write(path: str = Form(...), content: str = Form(...)):
    target = get_safe_path(path)
    try:
        with open(target, 'w', encoding='utf-8') as f: 
            f.write(content)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/fs/mkdir")
def fs_mkdir(path: str = Form(...)):
    target = get_safe_path(path)
    try:
        os.makedirs(target, exist_ok=True)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/fs/move")
def fs_move(old_path: str = Form(...), new_path: str = Form(...)):
    src = get_safe_path(old_path)
    dst = get_safe_path(new_path)
    try:
        shutil.move(src, dst)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/fs/upload")
async def fs_upload(path: str = Form(""), file: UploadFile = File(...)):
    target_dir = get_safe_path(path)
    file_path = os.path.join(target_dir, file.filename)
    try:
        with open(file_path, "wb") as buffer: 
            shutil.copyfileobj(file.file, buffer)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/fs/delete")
def fs_delete(path: str = Form(...)):
    t = get_safe_path(path)
    try:
        if os.path.isdir(t): shutil.rmtree(t)
        else: os.remove(t)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    print(f"Starting panel on http://localhost:7860")
    print(f"Serving files from: {BASE_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="error")