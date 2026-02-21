import os
import asyncio
import collections
import shutil
from fastapi import FastAPI, WebSocket, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

mc_process = None
output_history = collections.deque(maxlen=300)
connected_clients = set()
BASE_DIR = os.path.abspath("/app")

# -----------------
# HTML FRONTEND (Ultra-Modern Black & Green UI)
# -----------------
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Server Engine</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root { 
            --bg: #000000; --panel: #0a0a0a; --panel-hover: #111111; 
            --border: #1a1a1a; --text: #a1a1aa; --text-light: #e4e4e7;
            --accent: #22c55e; --accent-hover: #16a34a; --accent-glow: rgba(34, 197, 94, 0.15);
        }
        body { background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; overflow: hidden; -webkit-font-smoothing: antialiased; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        
        /* Custom Scrollbars */
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent); }

        /* Sidebar & Layout */
        .sidebar { width: 45px; transition: all 0.3s ease; }
        .nav-btn { color: #52525b; transition: all 0.2s; position: relative; }
        .nav-btn:hover, .nav-btn.active { color: var(--accent); }
        .nav-btn.active::before { content: ''; position: absolute; left: -12px; top: 10%; height: 80%; width: 2px; background: var(--accent); border-radius: 4px; box-shadow: 0 0 8px var(--accent); }

        /* Terminal Mask & Animations */
        .term-mask { mask-image: linear-gradient(to bottom, transparent 0%, black 8%, black 100%); -webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 8%, black 100%); }
        @keyframes fadeUpLine { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .log-line { animation: fadeUpLine 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards; word-break: break-all; padding: 1px 0; }
        
        /* File Row */
        .file-row { border-bottom: 1px solid var(--border); transition: background 0.15s; }
        .file-row:hover { background: var(--panel-hover); }
        .file-row:last-child { border-bottom: none; }

        /* Modals & Inputs */
        input:focus, textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-glow); }
        .modal-enter { animation: modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        @keyframes modalIn { from { opacity: 0; transform: scale(0.95) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }
        
        /* Loader */
        .loader { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .hidden-tab { display: none !important; }
    </style>
</head>
<body class="flex h-screen w-full select-none">

    <!-- Super Slim Sidebar (45px) -->
    <aside class="sidebar bg-[#050505] border-r border-[#1a1a1a] flex flex-col items-center py-6 gap-8 z-40 shrink-0">
        <div class="text-green-500 shadow-[0_0_15px_rgba(34,197,94,0.3)] rounded-full"><i data-lucide="server" class="w-5 h-5"></i></div>
        <nav class="flex flex-col gap-6 w-full items-center mt-4">
            <button onclick="switchTab('console')" id="nav-console" class="nav-btn active" title="Console"><i data-lucide="terminal-square" class="w-5 h-5"></i></button>
            <button onclick="switchTab('files')" id="nav-files" class="nav-btn" title="File Manager"><i data-lucide="folder-tree" class="w-5 h-5"></i></button>
            <button onclick="switchTab('config')" id="nav-config" class="nav-btn" title="Server Config"><i data-lucide="settings-2" class="w-5 h-5"></i></button>
            <button onclick="switchTab('plugins')" id="nav-plugins" class="nav-btn" title="Plugins"><i data-lucide="puzzle" class="w-5 h-5"></i></button>
        </nav>
    </aside>

    <!-- Main Workspace -->
    <main class="flex-1 relative bg-black flex flex-col overflow-hidden">
        
        <!-- ================= CONSOLE TAB ================= -->
        <div id="tab-console" class="absolute inset-0 flex flex-col p-3 sm:p-5">
            <div class="flex-1 bg-panel border border-[#1a1a1a] rounded-xl flex flex-col overflow-hidden relative shadow-2xl">
                <!-- Top Status Bar -->
                <div class="h-10 border-b border-[#1a1a1a] bg-[#050505] flex items-center px-4 justify-between">
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]"></div>
                        <span class="text-xs font-mono text-zinc-400">engine-live-stream</span>
                    </div>
                </div>
                
                <!-- Terminal Output -->
                <div id="terminal-output" class="flex-1 p-4 overflow-y-auto font-mono text-[13px] text-zinc-300 term-mask select-text">
                    <!-- Logs injected here -->
                </div>

                <!-- Terminal Input -->
                <div class="h-14 border-t border-[#1a1a1a] bg-[#050505] flex items-center px-4 gap-3">
                    <i data-lucide="chevron-right" class="w-4 h-4 text-green-500"></i>
                    <input type="text" id="cmd-input" class="flex-1 bg-transparent border-none text-green-400 font-mono text-sm placeholder-zinc-700" placeholder="Execute command...">
                </div>
            </div>
        </div>

        <!-- ================= FILES TAB ================= -->
        <div id="tab-files" class="hidden-tab absolute inset-0 flex flex-col p-3 sm:p-5">
            <div class="flex-1 bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl flex flex-col overflow-hidden shadow-2xl">
                <!-- File Header -->
                <div class="bg-[#050505] border-b border-[#1a1a1a] px-4 py-3 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                    <div class="flex items-center gap-2 text-sm font-mono text-zinc-400 w-full sm:w-auto overflow-x-auto hide-scrollbar" id="breadcrumbs"></div>
                    
                    <div class="flex items-center gap-2 shrink-0">
                        <input type="file" id="file-upload" class="hidden" onchange="uploadFile(event)">
                        <button onclick="showCreateModal('file')" class="p-1.5 hover:bg-[#1a1a1a] hover:text-green-400 rounded transition-colors text-zinc-400" title="New File"><i data-lucide="file-plus" class="w-4 h-4"></i></button>
                        <button onclick="showCreateModal('folder')" class="p-1.5 hover:bg-[#1a1a1a] hover:text-green-400 rounded transition-colors text-zinc-400" title="New Folder"><i data-lucide="folder-plus" class="w-4 h-4"></i></button>
                        <button onclick="document.getElementById('file-upload').click()" class="p-1.5 hover:bg-[#1a1a1a] hover:text-green-400 rounded transition-colors text-zinc-400" title="Upload"><i data-lucide="upload" class="w-4 h-4"></i></button>
                        <div class="w-px h-4 bg-[#222] mx-1"></div>
                        <button onclick="loadFiles(currentPath)" class="p-1.5 hover:bg-[#1a1a1a] text-zinc-400 rounded transition-colors"><i data-lucide="rotate-cw" class="w-4 h-4"></i></button>
                    </div>
                </div>

                <!-- File List Header -->
                <div class="hidden sm:grid grid-cols-12 gap-4 px-4 py-2 border-b border-[#1a1a1a] bg-[#080808] text-[11px] font-semibold text-zinc-600 uppercase tracking-widest">
                    <div class="col-span-8">Filename</div>
                    <div class="col-span-3 text-right">Size</div>
                    <div class="col-span-1 text-right"></div>
                </div>

                <!-- File List -->
                <div class="flex-1 overflow-y-auto pb-10" id="file-list"></div>
            </div>
        </div>

        <!-- ================= CONFIG TAB ================= -->
        <div id="tab-config" class="hidden-tab absolute inset-0 flex flex-col p-3 sm:p-5">
            <div class="flex-1 bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl flex flex-col overflow-hidden shadow-2xl relative">
                <div class="h-12 border-b border-[#1a1a1a] bg-[#050505] flex items-center px-4 justify-between">
                    <div class="flex items-center gap-2 text-sm font-mono text-zinc-300">
                        <i data-lucide="sliders" class="w-4 h-4 text-green-500"></i> server.properties
                    </div>
                    <button onclick="saveConfig()" class="bg-green-600 hover:bg-green-500 text-black px-4 py-1.5 rounded text-xs font-bold transition-colors flex items-center gap-2">
                        <i data-lucide="save" class="w-3.5 h-3.5"></i> Apply Details
                    </button>
                </div>
                <textarea id="config-editor" class="flex-1 bg-transparent p-4 text-zinc-300 font-mono text-[13px] resize-none focus:outline-none leading-relaxed select-text w-full h-full" spellcheck="false"></textarea>
            </div>
        </div>

        <!-- ================= PLUGINS TAB ================= -->
        <div id="tab-plugins" class="hidden-tab absolute inset-0 flex items-center justify-center">
            <div class="text-center flex flex-col items-center gap-4 opacity-50">
                <div class="w-16 h-16 rounded-2xl border border-green-500/30 flex items-center justify-center bg-green-500/5 shadow-[0_0_30px_rgba(34,197,94,0.1)]">
                    <i data-lucide="blocks" class="w-8 h-8 text-green-500"></i>
                </div>
                <div>
                    <h2 class="text-xl font-bold text-white tracking-tight">Plugin Manager</h2>
                    <p class="text-sm text-zinc-500 mt-1 font-mono">system.status = "COMING_SOON"</p>
                </div>
            </div>
        </div>

    </main>

    <!-- ================= CONTEXT MENU (•••) ================= -->
    <div id="context-menu" class="hidden absolute z-50 bg-[#0a0a0a] border border-[#222] rounded-md shadow-2xl py-1 w-36 overflow-hidden">
        <!-- Injected via JS -->
    </div>

    <!-- ================= CUSTOM MODALS OVERLAY ================= -->
    <div id="modal-overlay" class="hidden fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 opacity-0 transition-opacity duration-200">
        
        <!-- Input Modal (Create/Rename/Move) -->
        <div id="input-modal" class="hidden bg-[#0a0a0a] border border-[#222] rounded-xl w-full max-w-sm shadow-2xl flex-col overflow-hidden modal-enter">
            <div class="p-5 border-b border-[#1a1a1a]">
                <h3 id="input-modal-title" class="text-white font-medium text-sm">Action</h3>
                <p id="input-modal-desc" class="text-xs text-zinc-500 mt-1"></p>
            </div>
            <div class="p-5">
                <input type="text" id="input-modal-field" class="w-full bg-[#050505] border border-[#222] text-white text-sm rounded-lg px-3 py-2.5 focus:border-green-500 transition-colors font-mono" autocomplete="off">
            </div>
            <div class="px-5 py-3 bg-[#050505] border-t border-[#1a1a1a] flex justify-end gap-2">
                <button onclick="closeModal()" class="px-4 py-1.5 text-xs text-zinc-400 hover:text-white transition-colors">Cancel</button>
                <button id="input-modal-submit" class="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-black text-xs font-bold rounded transition-colors">Confirm</button>
            </div>
        </div>

        <!-- Confirm Modal (Delete) -->
        <div id="confirm-modal" class="hidden bg-[#0a0a0a] border border-[#222] rounded-xl w-full max-w-sm shadow-2xl flex-col overflow-hidden modal-enter">
            <div class="p-5 border-b border-[#1a1a1a] flex gap-3">
                <i data-lucide="alert-triangle" class="w-5 h-5 text-red-500 shrink-0 mt-0.5"></i>
                <div>
                    <h3 id="confirm-modal-title" class="text-white font-medium text-sm">Delete File</h3>
                    <p id="confirm-modal-msg" class="text-xs text-zinc-400 mt-1 leading-relaxed"></p>
                </div>
            </div>
            <div class="px-5 py-3 bg-[#050505] flex justify-end gap-2">
                <button onclick="closeModal()" class="px-4 py-1.5 text-xs text-zinc-400 hover:text-white transition-colors">Cancel</button>
                <button id="confirm-modal-submit" class="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs font-bold rounded transition-colors">Delete Permanently</button>
            </div>
        </div>

        <!-- Editor Modal -->
        <div id="editor-modal" class="hidden bg-[#0a0a0a] border border-[#222] rounded-xl w-full max-w-4xl h-[85vh] shadow-2xl flex-col overflow-hidden modal-enter">
            <div class="px-4 py-3 border-b border-[#1a1a1a] bg-[#050505] flex justify-between items-center">
                <span id="editor-modal-title" class="text-sm font-mono text-green-400">editing...</span>
                <div class="flex gap-2">
                    <button onclick="closeModal()" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white transition-colors">Discard</button>
                    <button id="editor-modal-submit" class="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-black text-xs font-bold rounded transition-colors flex items-center gap-1.5">
                        <i data-lucide="save" class="w-3.5 h-3.5"></i> Save File
                    </button>
                </div>
            </div>
            <textarea id="editor-modal-content" class="flex-1 bg-transparent p-4 text-zinc-300 font-mono text-[13px] resize-none focus:outline-none w-full leading-relaxed select-text" spellcheck="false"></textarea>
        </div>
    </div>

    <!-- Toast Notifications -->
    <div id="toast-container" class="fixed bottom-5 right-5 z-[200] flex flex-col gap-3 pointer-events-none"></div>

    <script>
        lucide.createIcons();

        // ----------------- TOAST SYSTEM -----------------
        function showToast(msg, type = 'info') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            let color = type === 'error' ? 'text-red-500 border-red-500/20' : (type === 'success' ? 'text-green-500 border-green-500/20' : 'text-blue-400 border-blue-400/20');
            toast.className = `flex items-center gap-3 bg-[#0a0a0a] border ${color} px-4 py-3 rounded-lg shadow-2xl translate-y-4 opacity-0 transition-all duration-300 pointer-events-auto`;
            toast.innerHTML = `<span class="text-xs font-mono text-white">${msg}</span>`;
            container.appendChild(toast);
            requestAnimationFrame(() => toast.classList.remove('translate-y-4', 'opacity-0'));
            setTimeout(() => {
                toast.classList.add('translate-y-4', 'opacity-0');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        // ----------------- NAVIGATION -----------------
        function switchTab(tab) {
            document.querySelectorAll('.tab-content, [id^="tab-"]').forEach(el => el.classList.add('hidden-tab'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            
            document.getElementById('tab-' + tab).classList.remove('hidden-tab');
            document.getElementById('nav-' + tab).classList.add('active');

            if (tab === 'files' && !currentPathLoaded) { loadFiles(''); currentPathLoaded = true; }
            if (tab === 'config') { loadConfig(); }
            if (tab === 'console') { scrollToBottom(); }
        }

        // ----------------- MODAL SYSTEM -----------------
        const overlay = document.getElementById('modal-overlay');
        let currentModalAction = null;

        function openModalElement(id) {
            document.getElementById('input-modal').classList.add('hidden');
            document.getElementById('confirm-modal').classList.add('hidden');
            document.getElementById('editor-modal').classList.add('hidden');
            
            overlay.classList.remove('hidden');
            document.getElementById(id).classList.remove('hidden');
            requestAnimationFrame(() => overlay.classList.remove('opacity-0'));
        }

        function closeModal() {
            overlay.classList.add('opacity-0');
            setTimeout(() => overlay.classList.add('hidden'), 200);
            currentModalAction = null;
        }

        function showPrompt(title, desc, defaultVal, onConfirm) {
            document.getElementById('input-modal-title').innerText = title;
            document.getElementById('input-modal-desc').innerText = desc;
            const input = document.getElementById('input-modal-field');
            input.value = defaultVal;
            openModalElement('input-modal');
            input.focus();
            
            const submitBtn = document.getElementById('input-modal-submit');
            submitBtn.onclick = () => { onConfirm(input.value); closeModal(); };
            input.onkeydown = (e) => { if(e.key === 'Enter') submitBtn.click(); };
        }

        function showConfirm(title, msg, onConfirm) {
            document.getElementById('confirm-modal-title').innerText = title;
            document.getElementById('confirm-modal-msg').innerText = msg;
            openModalElement('confirm-modal');
            document.getElementById('confirm-modal-submit').onclick = () => { onConfirm(); closeModal(); };
        }

        // ----------------- CUSTOM TERMINAL LOGIC -----------------
        const termOut = document.getElementById('terminal-output');
        const cmdInput = document.getElementById('cmd-input');
        
        function parseANSI(str) {
            str = str.replace(/</g, '&lt;').replace(/>/g, '&gt;');
            let res = '', styles = [];
            const chunks = str.split(/\\x1b\\[/);
            res += chunks[0];
            
            for (let i = 1; i < chunks.length; i++) {
                const match = chunks[i].match(/^([0-9;]*)m(.*)/s);
                if (match) {
                    const codes = match[1].split(';');
                    for(let code of codes) {
                        if(code === '' || code === '0') styles = [];
                        else if(code === '1') styles.push('font-weight:bold');
                        else if(code === '31' || code === '91') styles.push('color:#ef4444');
                        else if(code === '32' || code === '92') styles.push('color:#22c55e');
                        else if(code === '33' || code === '93') styles.push('color:#eab308');
                        else if(code === '34' || code === '94') styles.push('color:#3b82f6');
                        else if(code === '35' || code === '95') styles.push('color:#d946ef');
                        else if(code === '36' || code === '96') styles.push('color:#06b6d4');
                        else if(code === '37' || code === '97') styles.push('color:#fafafa');
                        else if(code === '90') styles.push('color:#71717a');
                    }
                    const styleStr = styles.length ? `style="${styles.join(';')}"` : '';
                    res += styles.length ? `<span ${styleStr}>${match[2]}</span>` : match[2];
                } else {
                    res += '\\x1b[' + chunks[i]; // Unhandled escape
                }
            }
            return res || '&nbsp;';
        }

        function scrollToBottom() {
            termOut.scrollTop = termOut.scrollHeight;
        }

        function appendLog(text) {
            const isAtBottom = termOut.scrollHeight - termOut.clientHeight <= termOut.scrollTop + 10;
            const div = document.createElement('div');
            div.className = 'log-line';
            div.innerHTML = parseANSI(text);
            termOut.appendChild(div);
            
            // Keep memory bound
            if(termOut.childElementCount > 400) termOut.removeChild(termOut.firstChild);
            if(isAtBottom) scrollToBottom();
        }

        const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
        let ws;
        function connectWS() {
            ws = new WebSocket(wsUrl);
            ws.onopen = () => appendLog('\\x1b[32m\\x1b[1m[Panel]\\x1b[0m Stream connected.');
            ws.onmessage = e => appendLog(e.data);
            ws.onclose = () => { appendLog('\\x1b[31m\\x1b[1m[Panel]\\x1b[0m Connection lost. Reconnecting...'); setTimeout(connectWS, 3000); };
        }
        connectWS();

        cmdInput.addEventListener('keypress', e => {
            if (e.key === 'Enter') {
                const val = cmdInput.value.trim();
                if(val && ws && ws.readyState === WebSocket.OPEN) {
                    appendLog(`\\x1b[90m> ${val}\\x1b[0m`);
                    ws.send(val);
                    cmdInput.value = '';
                }
            }
        });

        // ----------------- FILE MANAGER LOGIC -----------------
        let currentPath = '';
        let currentPathLoaded = false;
        let menuTarget = null;

        document.addEventListener('click', () => {
            document.getElementById('context-menu').classList.add('hidden');
        });

        function openMenu(e, name, isDir) {
            e.stopPropagation();
            menuTarget = { name, isDir, path: (currentPath ? currentPath + '/' + name : name) };
            const menu = document.getElementById('context-menu');
            
            let html = '';
            if(!isDir) html += `<button onclick="editFile('${menuTarget.path}')" class="w-full text-left px-4 py-2 hover:bg-[#1a1a1a] hover:text-green-400 text-xs text-zinc-300 transition-colors flex gap-2 items-center"><i data-lucide="edit-3" class="w-3.5 h-3.5"></i> Edit</button>`;
            
            html += `<button onclick="initRename()" class="w-full text-left px-4 py-2 hover:bg-[#1a1a1a] hover:text-green-400 text-xs text-zinc-300 transition-colors flex gap-2 items-center"><i data-lucide="type" class="w-3.5 h-3.5"></i> Rename</button>
                     <button onclick="initMove()" class="w-full text-left px-4 py-2 hover:bg-[#1a1a1a] hover:text-green-400 text-xs text-zinc-300 transition-colors flex gap-2 items-center"><i data-lucide="move" class="w-3.5 h-3.5"></i> Move</button>`;
            
            if(!isDir) html += `<button onclick="window.open('/api/fs/download?path=' + encodeURIComponent('${menuTarget.path}'))" class="w-full text-left px-4 py-2 hover:bg-[#1a1a1a] hover:text-green-400 text-xs text-zinc-300 transition-colors flex gap-2 items-center"><i data-lucide="download" class="w-3.5 h-3.5"></i> Download</button>`;
            
            html += `<div class="h-px w-full bg-[#1a1a1a] my-1"></div>
                     <button onclick="initDelete()" class="w-full text-left px-4 py-2 hover:bg-red-500/10 hover:text-red-400 text-xs text-red-500 transition-colors flex gap-2 items-center"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Delete</button>`;
            
            menu.innerHTML = html;
            lucide.createIcons();
            
            menu.style.left = Math.min(e.pageX, window.innerWidth - 150) + 'px';
            menu.style.top = Math.min(e.pageY, window.innerHeight - 200) + 'px';
            menu.classList.remove('hidden');
        }

        async function loadFiles(path) {
            currentPath = path;
            renderBreadcrumbs(path);
            const list = document.getElementById('file-list');
            list.innerHTML = `<div class="flex justify-center py-10"><i data-lucide="loader-2" class="w-6 h-6 text-green-500 loader"></i></div>`;
            lucide.createIcons();

            try {
                const res = await fetch(`/api/fs/list?path=${encodeURIComponent(path)}`);
                const files = await res.json();
                list.innerHTML = '';
                
                if (path !== '') {
                    const parent = path.split('/').slice(0, -1).join('/');
                    list.innerHTML += `
                        <div class="file-row flex items-center px-4 py-3 cursor-pointer group" onclick="loadFiles('${parent}')">
                            <i data-lucide="corner-left-up" class="w-4 h-4 text-zinc-600 group-hover:text-green-400 mr-3 transition-colors"></i>
                            <span class="text-xs font-mono text-zinc-500 group-hover:text-green-400 transition-colors">..</span>
                        </div>`;
                }

                if(files.length === 0 && path === '') list.innerHTML += `<div class="text-center py-10 text-zinc-600 text-xs font-mono">Directory empty</div>`;

                files.forEach(f => {
                    const icon = f.is_dir ? '<i data-lucide="folder" class="w-4 h-4 text-green-500"></i>' : '<i data-lucide="file" class="w-4 h-4 text-zinc-500"></i>';
                    const sizeStr = f.is_dir ? '--' : (f.size > 1024*1024 ? (f.size/(1024*1024)).toFixed(1) + ' MB' : (f.size / 1024).toFixed(1) + ' KB');
                    const clickAct = f.is_dir ? `onclick="loadFiles('${currentPath ? currentPath + '/' + f.name : f.name}')"` : '';
                    
                    list.innerHTML += `
                        <div class="file-row flex flex-col sm:grid sm:grid-cols-12 items-start sm:items-center px-4 py-2.5 gap-2 group cursor-pointer" ${clickAct}>
                            <div class="col-span-8 flex items-center gap-3 w-full truncate">
                                ${icon}
                                <span class="text-[13px] font-mono text-zinc-300 group-hover:text-white transition-colors truncate">${f.name}</span>
                            </div>
                            <div class="col-span-3 text-right text-[11px] text-zinc-600 font-mono hidden sm:block">${sizeStr}</div>
                            <div class="col-span-1 flex justify-end w-full sm:w-auto mt-1 sm:mt-0">
                                <button onclick="openMenu(event, '${f.name}', ${f.is_dir})" class="p-1 hover:bg-[#222] rounded text-zinc-500 hover:text-white transition-colors">
                                    <i data-lucide="more-horizontal" class="w-4 h-4"></i>
                                </button>
                            </div>
                        </div>`;
                });
                lucide.createIcons();
            } catch { showToast("Error loading files", "error"); }
        }

        function renderBreadcrumbs(path) {
            const parts = path.split('/').filter(p => p);
            let html = `<button onclick="loadFiles('')" class="hover:text-green-400 transition-colors"><i data-lucide="home" class="w-4 h-4"></i></button>`;
            let build = '';
            parts.forEach((p, i) => {
                build += (build ? '/' : '') + p;
                html += `<span class="opacity-30 mx-1">/</span>`;
                if(i === parts.length - 1) html += `<span class="text-green-500">${p}</span>`;
                else html += `<button onclick="loadFiles('${build}')" class="hover:text-green-400 transition-colors">${p}</button>`;
            });
            document.getElementById('breadcrumbs').innerHTML = html;
            lucide.createIcons();
        }

        // --- CRUD ACTIONS ---
        function showCreateModal(type) {
            showPrompt(`New ${type === 'folder' ? 'Folder' : 'File'}`, 'Enter name:', '', async (val) => {
                if(!val) return;
                const path = currentPath ? `${currentPath}/${val}` : val;
                const endpoint = type === 'folder' ? '/api/fs/create_dir' : '/api/fs/create_file';
                const fd = new FormData(); fd.append('path', path);
                try {
                    const r = await fetch(endpoint, { method: 'POST', body: fd });
                    if(r.ok) { showToast('Created successfully', 'success'); loadFiles(currentPath); }
                    else showToast('Failed to create', 'error');
                } catch { showToast('Network error', 'error'); }
            });
        }

        function initRename() {
            const t = menuTarget;
            showPrompt('Rename', `Enter new name for ${t.name}:`, t.name, async (val) => {
                if(!val || val === t.name) return;
                const fd = new FormData(); fd.append('old_path', t.path); fd.append('new_name', val);
                try {
                    const r = await fetch('/api/fs/rename', { method: 'POST', body: fd });
                    if(r.ok) { showToast('Renamed', 'success'); loadFiles(currentPath); }
                    else showToast('Rename failed', 'error');
                } catch { showToast('Network error', 'error'); }
            });
        }

        function initMove() {
            const t = menuTarget;
            showPrompt('Move', `Enter destination folder path for ${t.name} (relative to root, leave blank for root):`, '', async (val) => {
                const destFolder = val.trim();
                const destPath = destFolder ? `${destFolder}/${t.name}` : t.name;
                if(destPath === t.path) return;
                const fd = new FormData(); fd.append('source', t.path); fd.append('dest', destPath);
                try {
                    const r = await fetch('/api/fs/move', { method: 'POST', body: fd });
                    if(r.ok) { showToast('Moved', 'success'); loadFiles(currentPath); }
                    else showToast('Move failed', 'error');
                } catch { showToast('Network error', 'error'); }
            });
        }

        function initDelete() {
            const t = menuTarget;
            showConfirm('Delete Permanently', `Are you sure you want to delete ${t.name}? This action cannot be undone.`, async () => {
                const fd = new FormData(); fd.append('path', t.path);
                try {
                    const r = await fetch('/api/fs/delete', { method: 'POST', body: fd });
                    if(r.ok) { showToast('Deleted', 'success'); loadFiles(currentPath); }
                    else showToast('Delete failed', 'error');
                } catch { showToast('Network error', 'error'); }
            });
        }

        async function uploadFile(e) {
            const file = e.target.files[0];
            if(!file) return;
            showToast(`Uploading ${file.name}...`);
            const fd = new FormData(); fd.append('path', currentPath); fd.append('file', file);
            try {
                const r = await fetch('/api/fs/upload', { method: 'POST', body: fd });
                if(r.ok) { showToast('Upload complete', 'success'); loadFiles(currentPath); }
                else showToast('Upload failed', 'error');
            } catch { showToast('Network error', 'error'); }
            e.target.value = '';
        }

        // --- EDITOR LOGIC ---
        let currentEditPath = '';
        async function editFile(path) {
            try {
                const r = await fetch(`/api/fs/read?path=${encodeURIComponent(path)}`);
                if(!r.ok) throw new Error();
                const text = await r.text();
                currentEditPath = path;
                document.getElementById('editor-modal-title').innerText = path;
                document.getElementById('editor-modal-content').value = text;
                openModalElement('editor-modal');
                
                document.getElementById('editor-modal-submit').onclick = async () => {
                    const fd = new FormData(); fd.append('path', currentEditPath);
                    fd.append('content', document.getElementById('editor-modal-content').value);
                    const res = await fetch('/api/fs/write', { method: 'POST', body: fd });
                    if(res.ok) { showToast('File saved', 'success'); closeModal(); }
                    else showToast('Save failed', 'error');
                };
            } catch { showToast('Cannot open file (might be binary)', 'error'); }
        }

        // --- CONFIG TAB LOGIC ---
        async function loadConfig() {
            try {
                const r = await fetch(`/api/fs/read?path=server.properties`);
                if(r.ok) {
                    document.getElementById('config-editor').value = await r.text();
                } else {
                    document.getElementById('config-editor').value = "# server.properties not found yet.";
                }
            } catch { showToast('Failed to load config', 'error'); }
        }

        async function saveConfig() {
            const fd = new FormData();
            fd.append('path', 'server.properties');
            fd.append('content', document.getElementById('config-editor').value);
            try {
                const r = await fetch('/api/fs/write', { method: 'POST', body: fd });
                if(r.ok) showToast('Config applied successfully', 'success');
                else showToast('Failed to save', 'error');
            } catch { showToast('Network error', 'error'); }
        }

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
            if not line: break
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
    os.makedirs(BASE_DIR, exist_ok=True)
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
        with open(target, 'r', encoding='utf-8') as f:
            return Response(content=f.read(), media_type="text/plain")
    except UnicodeDecodeError:
        raise HTTPException(400, "File is binary or unsupported encoding")

@app.get("/api/fs/download")
def fs_download(path: str):
    target = get_safe_path(path)
    if not os.path.isfile(target): raise HTTPException(400, "Not a file")
    return FileResponse(target, filename=os.path.basename(target))

@app.post("/api/fs/write")
def fs_write(path: str = Form(...), content: str = Form(...)):
    target = get_safe_path(path)
    with open(target, 'w', encoding='utf-8') as f:
        f.write(content)
    return {"status": "ok"}

@app.post("/api/fs/upload")
async def fs_upload(path: str = Form(""), file: UploadFile = File(...)):
    target_dir = get_safe_path(path)
    os.makedirs(target_dir, exist_ok=True)
    target_file = os.path.join(target_dir, file.filename)
    with open(target_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "ok"}

@app.post("/api/fs/delete")
def fs_delete(path: str = Form(...)):
    target = get_safe_path(path)
    if os.path.isdir(target): shutil.rmtree(target)
    else: os.remove(target)
    return {"status": "ok"}

@app.post("/api/fs/create_dir")
def fs_create_dir(path: str = Form(...)):
    target = get_safe_path(path)
    try:
        os.makedirs(target, exist_ok=True)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/fs/create_file")
def fs_create_file(path: str = Form(...)):
    target = get_safe_path(path)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, 'a').close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/fs/rename")
def fs_rename(old_path: str = Form(...), new_name: str = Form(...)):
    src = get_safe_path(old_path)
    base_dir = os.path.dirname(src)
    dst = os.path.join(base_dir, new_name)
    try:
        os.rename(src, dst)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/fs/move")
def fs_move(source: str = Form(...), dest: str = Form(...)):
    src = get_safe_path(source)
    dst = get_safe_path(dest)
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(400, str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")