import os
import asyncio
import collections
import shutil
import psutil
from fastapi import FastAPI, WebSocket, Request, Response, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

mc_process = None
output_history = collections.deque(maxlen=300)
connected_clients = set()
BASE_DIR = os.path.abspath("/app")

# Global dict to store cached stats so the UI doesn't lag when polling
cached_stats = { "cpu": 0, "ram_used": 0, "ram_total": 16, "storage_used": 0, "storage_total": 50 }

# -----------------
# HTML FRONTEND (Ultimate SaaS Web3 Dashboard)
# -----------------
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Server Dashboard</title>
    
    <!-- Premium Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <!-- Phosphor Icons -->
    <script src="https://unpkg.com/@phosphor-icons/web"></script>
    <!-- Terminal -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm/css/xterm.css" />
    <script src="https://cdn.jsdelivr.net/npm/xterm/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit/lib/xterm-addon-fit.js"></script>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: { sans: ['Plus Jakarta Sans', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] },
                    colors: {
                        base: '#080B11',
                        surface: '#121620',
                        surfaceHover: '#1A1F2D',
                        border: '#22283A',
                        primary: '#6366F1',
                        secondary: '#A855F7',
                        accent: '#06B6D4'
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: theme('colors.base'); color: #F8FAFC; overflow: hidden; -webkit-font-smoothing: antialiased; }
        
        /* Dashboard Cards */
        .premium-card {
            background: theme('colors.surface');
            border: 1px solid theme('colors.border');
            border-radius: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            position: relative;
            overflow: hidden;
        }

        /* Gradients & Glows */
        .text-gradient { background: linear-gradient(135deg, theme('colors.primary'), theme('colors.secondary')); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .bg-gradient-btn { background: linear-gradient(135deg, theme('colors.primary'), theme('colors.secondary')); box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3); transition: all 0.2s ease; }
        .bg-gradient-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4); filter: brightness(1.1); }
        
        /* Terminal Fixing for Mobile Wrapping */
        .term-container { flex: 1; min-width: 0; min-height: 0; width: 100%; height: 100%; border-radius: 12px; overflow: hidden; position: relative; }
        .term-wrapper { padding: 12px; height: 100%; width: 100%; }
        .xterm .xterm-viewport { overflow-y: auto !important; width: 100% !important; background-color: transparent !important; }
        .xterm-screen { width: 100% !important; }
        
        /* Progress Bars */
        .progress-track { background: theme('colors.border'); border-radius: 999px; height: 6px; overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 999px; transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1); }

        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: theme('colors.border'); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #333C52; }

        /* Mobile Bottom Nav Glass */
        .mobile-nav-glass {
            background: rgba(18, 22, 32, 0.85);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-top: 1px solid theme('colors.border');
        }

        /* Nav active states */
        .nav-item { color: #64748B; transition: all 0.2s; }
        .nav-item:hover { color: #F8FAFC; background: theme('colors.surfaceHover'); }
        .nav-item.active { color: #F8FAFC; background: theme('colors.primary'); box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2); }
        
        /* Mobile Nav active states */
        .mob-nav-item { color: #64748B; }
        .mob-nav-item.active { color: theme('colors.primary'); }
        .mob-nav-indicator { display: none; height: 4px; width: 4px; border-radius: 50%; background: theme('colors.primary'); margin-top: 2px; }
        .mob-nav-item.active .mob-nav-indicator { display: block; }

        .fade-in { animation: fadeIn 0.3s ease-out forwards; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .hidden-tab { display: none !important; }
        
        /* SVG Background Wave */
        .bg-wave { position: absolute; bottom: 0; left: 0; right: 0; opacity: 0.1; transform: translateY(20%); pointer-events: none; }
    </style>
</head>
<body class="flex flex-col md:flex-row h-[100dvh] w-full text-sm">

    <!-- Desktop Sidebar -->
    <aside class="hidden md:flex flex-col w-[260px] premium-card m-4 mr-0 border-y-0 border-l-0 rounded-none rounded-l-2xl border-r border-border bg-surface shrink-0 z-20">
        <div class="p-6 pb-2">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-lg">
                    <i class="ph ph-cube text-xl text-white"></i>
                </div>
                <div>
                    <h1 class="font-bold text-lg text-white leading-tight">Server<span class="text-gradient">Space</span></h1>
                    <p class="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Engine v2.0</p>
                </div>
            </div>
        </div>

        <div class="px-6 py-4">
            <div class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Menu</div>
            <nav class="flex flex-col gap-2">
                <button onclick="switchTab('dashboard')" id="nav-dashboard" class="nav-item active flex items-center gap-3 px-4 py-3 rounded-xl font-medium">
                    <i class="ph ph-squares-four text-lg"></i> Dashboard
                </button>
                <button onclick="switchTab('files')" id="nav-files" class="nav-item flex items-center gap-3 px-4 py-3 rounded-xl font-medium">
                    <i class="ph ph-folder-open text-lg"></i> Files
                </button>
            </nav>
        </div>

        <div class="mt-auto p-6">
            <div class="bg-surfaceHover border border-border rounded-xl p-4 flex items-center gap-3">
                <div class="relative flex h-3 w-3">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                </div>
                <div>
                    <div class="text-xs font-bold text-white">Status Online</div>
                    <div class="text-[10px] text-slate-400">Container Active</div>
                </div>
            </div>
        </div>
    </aside>

    <!-- Mobile Header -->
    <header class="md:hidden flex justify-between items-center px-5 py-4 bg-surface border-b border-border shrink-0 z-20">
        <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <i class="ph ph-cube text-white"></i>
            </div>
            <h1 class="font-bold text-base text-white">Server<span class="text-gradient">Space</span></h1>
        </div>
        <div class="relative flex h-2 w-2">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
        </div>
    </header>

    <!-- Main Workspace -->
    <main class="flex-grow flex flex-col p-4 md:p-6 overflow-hidden min-w-0 bg-base relative z-10">
        
        <!-- DASHBOARD TAB -->
        <div id="tab-dashboard" class="h-full flex flex-col gap-4 md:gap-6 fade-in min-w-0">
            
            <!-- Metrics Row (Strictly 16GB / 2 Cores / 50GB) -->
            <div class="grid grid-cols-3 gap-3 md:gap-6 shrink-0">
                
                <!-- RAM Card -->
                <div class="premium-card p-4 flex flex-col justify-between h-[100px] md:h-[130px]">
                    <div class="flex justify-between items-start">
                        <div class="p-2 rounded-lg bg-primary/10 text-primary hidden md:block"><i class="ph-fill ph-memory text-xl"></i></div>
                        <i class="ph-fill ph-memory text-primary text-xl md:hidden"></i>
                        <span class="text-[10px] md:text-xs font-bold text-slate-400 uppercase tracking-wide">RAM Usage</span>
                    </div>
                    <div>
                        <div class="flex items-end gap-1 md:gap-2 mb-2">
                            <span class="text-lg md:text-3xl font-bold text-white font-mono leading-none" id="ram-val">0.0</span>
                            <span class="text-[10px] md:text-sm text-slate-500 font-mono mb-0.5">/ 16 GB</span>
                        </div>
                        <div class="progress-track"><div id="ram-bar" class="progress-fill bg-primary w-0"></div></div>
                    </div>
                </div>

                <!-- CPU Card -->
                <div class="premium-card p-4 flex flex-col justify-between h-[100px] md:h-[130px]">
                    <div class="flex justify-between items-start">
                        <div class="p-2 rounded-lg bg-secondary/10 text-secondary hidden md:block"><i class="ph-fill ph-cpu text-xl"></i></div>
                        <i class="ph-fill ph-cpu text-secondary text-xl md:hidden"></i>
                        <span class="text-[10px] md:text-xs font-bold text-slate-400 uppercase tracking-wide">vCores</span>
                    </div>
                    <div>
                        <div class="flex items-end gap-1 md:gap-2 mb-2">
                            <span class="text-lg md:text-3xl font-bold text-white font-mono leading-none" id="cpu-val">0</span>
                            <span class="text-[10px] md:text-sm text-slate-500 font-mono mb-0.5">% of 2</span>
                        </div>
                        <div class="progress-track"><div id="cpu-bar" class="progress-fill bg-secondary w-0"></div></div>
                    </div>
                </div>

                <!-- Storage Card -->
                <div class="premium-card p-4 flex flex-col justify-between h-[100px] md:h-[130px]">
                    <div class="flex justify-between items-start">
                        <div class="p-2 rounded-lg bg-accent/10 text-accent hidden md:block"><i class="ph-fill ph-hard-drives text-xl"></i></div>
                        <i class="ph-fill ph-hard-drives text-accent text-xl md:hidden"></i>
                        <span class="text-[10px] md:text-xs font-bold text-slate-400 uppercase tracking-wide">Disk Space</span>
                    </div>
                    <div>
                        <div class="flex items-end gap-1 md:gap-2 mb-2">
                            <span class="text-lg md:text-3xl font-bold text-white font-mono leading-none" id="disk-val">0.0</span>
                            <span class="text-[10px] md:text-sm text-slate-500 font-mono mb-0.5">/ 50 GB</span>
                        </div>
                        <div class="progress-track"><div id="disk-bar" class="progress-fill bg-accent w-0"></div></div>
                    </div>
                </div>
            </div>

            <!-- Terminal Area -->
            <div class="premium-card flex flex-col flex-grow min-h-0">
                <!-- Mac-style Terminal Header -->
                <div class="bg-surface border-b border-border px-4 py-3 flex items-center justify-between z-10 shrink-0">
                    <div class="flex gap-2">
                        <div class="w-3 h-3 rounded-full bg-[#EF4444]"></div>
                        <div class="w-3 h-3 rounded-full bg-[#F59E0B]"></div>
                        <div class="w-3 h-3 rounded-full bg-[#10B981]"></div>
                    </div>
                    <span class="text-xs font-mono text-slate-400">server_console ~ /app</span>
                    <div class="w-12"></div> <!-- Spacer for center alignment -->
                </div>
                
                <!-- Terminal Container -->
                <div class="term-container bg-[#080B11]">
                    <div id="terminal" class="term-wrapper"></div>
                </div>

                <!-- Input Field -->
                <div class="p-3 md:p-4 bg-surface/80 border-t border-border z-10 shrink-0">
                    <div class="relative flex items-center">
                        <i class="ph ph-terminal text-primary absolute left-4 text-lg"></i>
                        <input type="text" id="cmd-input" class="w-full bg-base border border-border focus:border-primary/50 text-white rounded-xl pl-12 pr-12 py-3 text-sm font-mono transition-all outline-none" placeholder="Enter command here...">
                        <button onclick="sendCommand()" class="absolute right-2 p-2 bg-gradient-btn rounded-lg text-white">
                            <i class="ph-bold ph-arrow-right"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- FILES TAB -->
        <div id="tab-files" class="hidden-tab h-full flex flex-col premium-card overflow-hidden min-w-0">
            <!-- Header -->
            <div class="bg-surface px-5 py-4 border-b border-border flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shrink-0">
                <div class="flex items-center gap-2 text-sm font-mono text-slate-300 overflow-x-auto whitespace-nowrap w-full sm:w-auto" id="breadcrumbs">
                    <!-- JS Breadcrumbs -->
                </div>
                <div class="flex gap-2 shrink-0">
                    <input type="file" id="file-upload" class="hidden" onchange="uploadFile(event)">
                    <button onclick="document.getElementById('file-upload').click()" class="bg-gradient-btn px-4 py-2 rounded-xl text-xs font-bold text-white flex items-center gap-2">
                        <i class="ph-bold ph-upload-simple"></i> Upload
                    </button>
                    <button onclick="loadFiles(currentPath)" class="bg-surfaceHover border border-border px-3 py-2 rounded-xl text-slate-300 hover:text-white transition-colors">
                        <i class="ph-bold ph-arrows-clockwise text-base"></i>
                    </button>
                </div>
            </div>
            
            <!-- File Headers (Desktop only) -->
            <div class="hidden sm:grid grid-cols-12 gap-4 px-6 py-3 bg-[#0D1017] border-b border-border text-[11px] font-bold text-slate-500 uppercase tracking-wider shrink-0">
                <div class="col-span-7">Name</div>
                <div class="col-span-3 text-right">Size</div>
                <div class="col-span-2 text-right">Actions</div>
            </div>

            <!-- File List -->
            <div class="flex-grow overflow-y-auto bg-base p-2 md:p-3" id="file-list">
                <!-- JS Files -->
            </div>
        </div>
    </main>

    <!-- Mobile Bottom Navigation -->
    <nav class="md:hidden mobile-nav-glass pb-safe pt-2 px-6 flex justify-around items-center shrink-0 z-50 rounded-t-2xl absolute bottom-0 w-full h-[70px]">
        <button onclick="switchTab('dashboard')" id="mob-dashboard" class="mob-nav-item active flex flex-col items-center gap-1 w-16">
            <i class="ph-fill ph-squares-four text-2xl"></i>
            <span class="text-[10px] font-semibold">Dash</span>
            <div class="mob-nav-indicator"></div>
        </button>
        <button onclick="switchTab('files')" id="mob-files" class="mob-nav-item flex flex-col items-center gap-1 w-16">
            <i class="ph-fill ph-folder text-2xl"></i>
            <span class="text-[10px] font-semibold">Files</span>
            <div class="mob-nav-indicator"></div>
        </button>
    </nav>

    <!-- File Editor Modal -->
    <div id="editor-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden items-center justify-center p-4 z-[100] opacity-0 transition-opacity duration-300">
        <div class="premium-card w-full max-w-4xl h-[85vh] flex flex-col transform scale-95 transition-transform duration-300" id="editor-card">
            <div class="bg-surface px-5 py-4 flex justify-between items-center border-b border-border shrink-0">
                <div class="flex items-center gap-3 text-sm font-mono text-white">
                    <i class="ph-fill ph-file-code text-primary text-xl"></i>
                    <span id="editor-title">file.txt</span>
                </div>
                <div class="flex gap-2">
                    <button onclick="closeEditor()" class="px-4 py-2 hover:bg-surfaceHover rounded-xl text-xs font-bold text-slate-400">Cancel</button>
                    <button onclick="saveFile()" class="bg-gradient-btn px-5 py-2 rounded-xl text-xs font-bold text-white shadow-lg flex items-center gap-2">
                        <i class="ph-bold ph-floppy-disk"></i> Save
                    </button>
                </div>
            </div>
            <textarea id="editor-content" class="flex-grow bg-[#080B11] text-slate-200 p-5 font-mono text-sm resize-none focus:outline-none w-full leading-loose" spellcheck="false"></textarea>
        </div>
    </div>

    <!-- Notification Toasts -->
    <div id="toast-container" class="fixed top-6 right-6 z-[200] flex flex-col gap-3 pointer-events-none"></div>

    <script>
        // --- Tab Navigation ---
        function switchTab(tab) {
            document.getElementById('tab-dashboard').classList.add('hidden-tab');
            document.getElementById('tab-files').classList.add('hidden-tab');
            
            // Reset Desktop
            document.getElementById('nav-dashboard').className = "nav-item flex items-center gap-3 px-4 py-3 rounded-xl font-medium";
            document.getElementById('nav-files').className = "nav-item flex items-center gap-3 px-4 py-3 rounded-xl font-medium";
            
            // Reset Mobile
            document.getElementById('mob-dashboard').classList.remove('active');
            document.getElementById('mob-files').classList.remove('active');
            
            // Activate
            document.getElementById('tab-' + tab).classList.remove('hidden-tab');
            document.getElementById('tab-' + tab).classList.add('fade-in');
            
            document.getElementById('nav-' + tab).className = "nav-item active flex items-center gap-3 px-4 py-3 rounded-xl font-medium";
            document.getElementById('mob-' + tab).classList.add('active');

            if(tab === 'dashboard' && fitAddon) setTimeout(() => fitAddon.fit(), 100);
            if(tab === 'files' && !window.filesLoaded) { loadFiles(''); window.filesLoaded = true; }
        }

        // --- Terminal Engine ---
        const term = new Terminal({ 
            theme: { background: 'transparent', foreground: '#E2E8F0', cursor: '#6366F1', selectionBackground: 'rgba(99, 102, 241, 0.3)' }, 
            fontFamily: "'JetBrains Mono', monospace", fontSize: 13, cursorBlink: true, convertEol: true 
        });
        const fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);
        term.open(document.getElementById('terminal'));
        
        // Exact fit tracking to fix wrapping
        const ro = new ResizeObserver(() => {
            if(!document.getElementById('tab-dashboard').classList.contains('hidden-tab')) {
                requestAnimationFrame(() => fitAddon.fit());
            }
        });
        ro.observe(document.querySelector('.term-container'));
        setTimeout(() => fitAddon.fit(), 200);

        const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
        ws.onopen = () => term.write('\\x1b[38;5;63m\\x1b[1m[Console]\\x1b[0m Engine connection established.\\r\\n');
        ws.onmessage = e => term.write(e.data + '\\n');
        
        const cmdInput = document.getElementById('cmd-input');
        cmdInput.addEventListener('keypress', e => { if (e.key === 'Enter') sendCommand(); });
        function sendCommand() {
            if(cmdInput.value.trim() && ws.readyState === WebSocket.OPEN) { 
                term.write(`\\x1b[90m> ${cmdInput.value}\\x1b[0m\\r\\n`);
                ws.send(cmdInput.value); cmdInput.value = ''; 
            }
        }

        // --- Container Metrics Engine ---
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                // RAM (Max 16GB)
                const ramVal = Math.min(data.ram_used, 16.0);
                document.getElementById('ram-val').innerText = ramVal.toFixed(1);
                document.getElementById('ram-bar').style.width = `${(ramVal / 16.0) * 100}%`;
                
                // CPU (Max 100% representing 2 cores)
                const cpuVal = Math.min(data.cpu, 100);
                document.getElementById('cpu-val').innerText = Math.round(cpuVal);
                document.getElementById('cpu-bar').style.width = `${cpuVal}%`;
                
                // Storage (Max 50GB)
                const diskVal = Math.min(data.storage_used, 50.0);
                document.getElementById('disk-val').innerText = diskVal.toFixed(1);
                document.getElementById('disk-bar').style.width = `${(diskVal / 50.0) * 100}%`;
                
            } catch (e) {}
        }
        setInterval(fetchStats, 2000);
        fetchStats();

        // --- File Manager ---
        let currentPath = '';
        let editPath = '';

        function showToast(msg, type='info') {
            const container = document.getElementById('toast-container');
            const el = document.createElement('div');
            let icon = '<i class="ph-fill ph-info text-blue-400 text-xl"></i>';
            if(type==='success') icon = '<i class="ph-fill ph-check-circle text-green-400 text-xl"></i>';
            if(type==='error') icon = '<i class="ph-fill ph-warning-circle text-red-400 text-xl"></i>';

            el.className = `flex items-center gap-3 bg-surface border border-border text-white px-5 py-4 rounded-xl shadow-2xl translate-x-10 opacity-0 transition-all duration-300`;
            el.innerHTML = `${icon} <span class="font-bold text-sm tracking-wide">${msg}</span>`;
            container.appendChild(el);
            
            requestAnimationFrame(() => el.classList.remove('translate-x-10', 'opacity-0'));
            setTimeout(() => { el.classList.add('translate-x-10', 'opacity-0'); setTimeout(() => el.remove(), 300); }, 3000);
        }

        async function loadFiles(path) {
            currentPath = path;
            const parts = path.split('/').filter(p => p);
            let bc = `<button onclick="loadFiles('')" class="hover:text-white transition"><i class="ph-fill ph-house text-lg"></i></button>`;
            let bp = '';
            parts.forEach((p, i) => {
                bp += (bp?'/':'') + p;
                bc += `<i class="ph-bold ph-caret-right text-xs mx-2 opacity-30"></i>`;
                if(i === parts.length-1) bc += `<span class="text-primary font-bold">${p}</span>`;
                else bc += `<button onclick="loadFiles('${bp}')" class="hover:text-white transition">${p}</button>`;
            });
            document.getElementById('breadcrumbs').innerHTML = bc;

            const list = document.getElementById('file-list');
            list.innerHTML = `<div class="flex justify-center py-12"><i class="ph-bold ph-spinner-gap animate-spin text-3xl text-primary"></i></div>`;

            try {
                const res = await fetch(`/api/fs/list?path=${encodeURIComponent(path)}`);
                const files = await res.json();
                list.innerHTML = '';
                
                if (path !== '') {
                    const parent = path.split('/').slice(0, -1).join('/');
                    list.innerHTML += `
                        <div class="flex items-center px-4 py-3 cursor-pointer hover:bg-surfaceHover rounded-xl transition mb-1 border border-transparent" onclick="loadFiles('${parent}')">
                            <i class="ph-bold ph-arrow-u-up-left text-slate-500 mr-3 text-lg"></i>
                            <span class="text-sm font-mono text-slate-400 font-semibold">.. back</span>
                        </div>`;
                }

                files.forEach(f => {
                    const icon = f.is_dir ? '<div class="p-2.5 bg-primary/10 rounded-lg text-primary"><i class="ph-fill ph-folder text-xl"></i></div>' : '<div class="p-2.5 bg-surface border border-border rounded-lg text-slate-400"><i class="ph-fill ph-file text-xl"></i></div>';
                    const sz = f.is_dir ? '--' : (f.size > 1048576 ? (f.size/1048576).toFixed(1) + ' MB' : (f.size/1024).toFixed(1) + ' KB');
                    const fp = path ? `${path}/${f.name}` : f.name;
                    
                    list.innerHTML += `
                        <div class="flex flex-col sm:grid sm:grid-cols-12 items-start sm:items-center px-3 py-2 gap-3 group hover:bg-surfaceHover rounded-xl transition mb-1 border border-transparent hover:border-border">
                            <div class="col-span-7 flex items-center gap-4 w-full ${f.is_dir?'cursor-pointer':''}" ${f.is_dir?`onclick="loadFiles('${fp}')"`:''}>
                                ${icon}
                                <span class="text-sm font-mono text-slate-200 truncate group-hover:text-primary transition font-medium">${f.name}</span>
                            </div>
                            <div class="col-span-3 text-right text-xs text-slate-500 font-mono hidden sm:block">${sz}</div>
                            <div class="col-span-2 flex justify-end gap-2 w-full sm:w-auto sm:opacity-0 group-hover:opacity-100 transition">
                                ${!f.is_dir ? `<button onclick="editFile('${fp}')" class="p-2 bg-surface border border-border hover:border-primary hover:text-primary rounded-lg transition"><i class="ph-bold ph-pencil-simple text-sm"></i></button>` : ''}
                                ${!f.is_dir ? `<a href="/api/fs/download?path=${encodeURIComponent(fp)}" class="p-2 bg-surface border border-border hover:border-green-400 hover:text-green-400 rounded-lg transition"><i class="ph-bold ph-download-simple text-sm"></i></a>` : ''}
                                <button onclick="deleteFile('${fp}')" class="p-2 bg-surface border border-border hover:border-red-400 hover:text-red-400 rounded-lg transition"><i class="ph-bold ph-trash text-sm"></i></button>
                            </div>
                        </div>`;
                });
            } catch (err) { list.innerHTML = `<div class="text-center py-8 text-red-400 text-sm">Failed to load files</div>`; }
        }

        async function editFile(path) {
            try {
                const res = await fetch(`/api/fs/read?path=${encodeURIComponent(path)}`);
                if(res.ok) {
                    editPath = path;
                    document.getElementById('editor-content').value = await res.text();
                    document.getElementById('editor-title').innerText = path.split('/').pop();
                    const m = document.getElementById('editor-modal'); const c = document.getElementById('editor-card');
                    m.classList.remove('hidden'); m.classList.add('flex');
                    requestAnimationFrame(() => { m.classList.remove('opacity-0'); c.classList.remove('scale-95'); });
                } else showToast('Binary file cannot be edited', 'error');
            } catch { showToast('Error opening file', 'error'); }
        }

        function closeEditor() {
            const m = document.getElementById('editor-modal'); const c = document.getElementById('editor-card');
            m.classList.add('opacity-0'); c.classList.add('scale-95');
            setTimeout(() => { m.classList.add('hidden'); m.classList.remove('flex'); }, 300);
        }

        async function saveFile() {
            const fd = new FormData(); fd.append('path', editPath); fd.append('content', document.getElementById('editor-content').value);
            try {
                const res = await fetch('/api/fs/write', { method: 'POST', body: fd });
                if(res.ok) { showToast('Saved securely', 'success'); closeEditor(); } else throw new Error();
            } catch { showToast('Save failed', 'error'); }
        }

        async function deleteFile(path) {
            if(confirm(`Erase ${path.split('/').pop()} permanentely?`)) {
                const fd = new FormData(); fd.append('path', path);
                try {
                    const res = await fetch('/api/fs/delete', { method: 'POST', body: fd });
                    if(res.ok) { showToast('Erased', 'success'); loadFiles(currentPath); } else throw new Error();
                } catch { showToast('Erase failed', 'error'); }
            }
        }

        async function uploadFile(e) {
            if(!e.target.files.length) return;
            showToast('Uploading data...', 'info');
            const fd = new FormData(); fd.append('path', currentPath); fd.append('file', e.target.files[0]);
            try {
                const res = await fetch('/api/fs/upload', { method: 'POST', body: fd });
                if(res.ok) { showToast('Upload complete', 'success'); loadFiles(currentPath); } else throw new Error();
            } catch { showToast('Upload failed', 'error'); }
            e.target.value = '';
        }
    </script>
</body>
</html>
"""

# -----------------
# STATS ENGINE BACKGROUND TASK (Container-Only Restrictions)
# -----------------
async def update_system_stats():
    """ Runs constantly in the background so the UI endpoint is instantly responsive. """
    while True:
        try:
            # 1. Gather Storage strictly for /app
            # Hugging Face usually provides around 50GB. We enforce this visual cap.
            total_st, used_st, free_st = shutil.disk_usage('/app')
            cached_stats["storage_used"] = used_st / (1024**3)
            cached_stats["storage_total"] = 50.0

            # 2. Gather RAM and CPU strictly for the python process + Java child (No Host Info)
            ram_used = 0
            cpu_percent_raw = 0.0
            
            try:
                main_proc = psutil.Process(os.getpid())
                ram_used += main_proc.memory_info().rss
                cpu_percent_raw += main_proc.cpu_percent()
                
                # Fetch Java child process metrics
                for child in main_proc.children(recursive=True):
                    try:
                        ram_used += child.memory_info().rss
                        cpu_percent_raw += child.cpu_percent()
                    except psutil.NoSuchProcess:
                        pass
            except Exception:
                pass

            # Convert RAM to GB
            cached_stats["ram_used"] = ram_used / (1024**3)
            cached_stats["ram_total"] = 16.0 # Strict Hugging Face Limit
            
            # Normalize CPU to 2 vCores (where 200% raw = 100% full capacity)
            normalized_cpu = cpu_percent_raw / 2.0
            cached_stats["cpu"] = min(100.0, normalized_cpu)

        except Exception as e:
            pass # Failsafe
            
        await asyncio.sleep(2) # Update every 2 seconds

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

async def read_stream(stream, prefix=""):
    while True:
        try:
            line = await stream.readline()
            if not line: break
            await broadcast(prefix + line.decode('utf-8', errors='replace').rstrip('\r\n'))
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
        *java_args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=BASE_DIR
    )
    asyncio.create_task(read_stream(mc_process.stdout))

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_minecraft())
    asyncio.create_task(update_system_stats()) # Start background polling loop

# -----------------
# API ROUTING
# -----------------
@app.get("/")
def get_panel(): return HTMLResponse(content=HTML_CONTENT)

@app.get("/api/stats")
def api_stats():
    # Returns the background-calculated stats instantly
    return JSONResponse(content=cached_stats)

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    for line in output_history: await websocket.send_text(line)
    try:
        while True:
            cmd = await websocket.receive_text()
            if mc_process and mc_process.stdin:
                mc_process.stdin.write((cmd + "\n").encode('utf-8'))
                await mc_process.stdin.drain()
    except:
        connected_clients.remove(websocket)

@app.get("/api/fs/list")
def fs_list(path: str = ""):
    target = get_safe_path(path)
    if not os.path.exists(target): return []
    items = []
    for f in os.listdir(target):
        fp = os.path.join(target, f)
        items.append({"name": f, "is_dir": os.path.isdir(fp), "size": os.path.getsize(fp) if not os.path.isdir(fp) else 0})
    return sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower()))

@app.get("/api/fs/read")
def fs_read(path: str):
    target = get_safe_path(path)
    if not os.path.isfile(target): raise HTTPException(400, "Not a file")
    try:
        with open(target, 'r', encoding='utf-8') as f: return Response(content=f.read(), media_type="text/plain")
    except: raise HTTPException(400, "File is binary")

@app.get("/api/fs/download")
def fs_download(path: str):
    target = get_safe_path(path)
    if not os.path.isfile(target): raise HTTPException(400, "Not a file")
    return FileResponse(target, filename=os.path.basename(target))

@app.post("/api/fs/write")
def fs_write(path: str = Form(...), content: str = Form(...)):
    with open(get_safe_path(path), 'w', encoding='utf-8') as f: f.write(content)
    return {"status": "ok"}

@app.post("/api/fs/upload")
async def fs_upload(path: str = Form(""), file: UploadFile = File(...)):
    with open(os.path.join(get_safe_path(path), file.filename), "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    return {"status": "ok"}

@app.post("/api/fs/delete")
def fs_delete(path: str = Form(...)):
    t = get_safe_path(path)
    if os.path.isdir(t): shutil.rmtree(t)
    else: os.remove(t)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")