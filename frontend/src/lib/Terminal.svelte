<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    
    // State variables with proper types
    let terminal: any = null;
    let fitAddon: any = null;
    let ws: WebSocket | null = null;
    let sessionId: string | null = null;
    let isConnected: boolean = false;
    let isConnecting: boolean = false;
    
    // Form values with proper types
    let host: string = '';
    let port: number = 22;
    let username: string = '';
    let password: string = '';
    
    // Status with proper types
    let statusIndicator: string = 'disconnected';
    let statusText: string = 'Disconnected';
    
    // DOM element reference with proper type
    let terminalElement: HTMLDivElement;
    
    onMount(() => {
        // Wait for xterm.js to load from CDN
        const checkXtermLoaded = () => {
            const win = window as any;
            if (win.Terminal && win.FitAddon && win.WebLinksAddon) {
                initTerminal();
            } else {
                setTimeout(checkXtermLoaded, 100);
            }
        };
        checkXtermLoaded();
        
        // Handle window resize
        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
        };
    });
    
    onDestroy(() => {
        disconnect();
    });
    
    function initTerminal(): void {
        const win = window as any;
        const Terminal = win.Terminal;
        const FitAddon = win.FitAddon?.FitAddon || win.FitAddon;
        const WebLinksAddon = win.WebLinksAddon?.WebLinksAddon || win.WebLinksAddon;
        
        terminal = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: '"Cascadia Code", "Fira Code", "Consolas", "Monaco", monospace',
            theme: {
                background: '#0c0c0c',
                foreground: '#e0e0e0',
                cursor: '#4a9eff',
                selection: 'rgba(74, 158, 255, 0.3)',
                black: '#000000',
                red: '#ff5555',
                green: '#50fa7b',
                yellow: '#f1fa8c',
                blue: '#4a9eff',
                magenta: '#ff79c6',
                cyan: '#8be9fd',
                white: '#bfbfbf',
                brightBlack: '#4d4d4d',
                brightRed: '#ff6e67',
                brightGreen: '#5af78e',
                brightYellow: '#f4f99d',
                brightBlue: '#6ab7ff',
                brightMagenta: '#ff92d0',
                brightCyan: '#9aedfe',
                brightWhite: '#e6e6e6'
            }
        });
        
        // Add fit addon
        fitAddon = new FitAddon();
        terminal.loadAddon(fitAddon);
        
        // Add web links addon
        const webLinksAddon = new WebLinksAddon();
        terminal.loadAddon(webLinksAddon);
        
        // Open terminal in DOM
        if (terminalElement) {
            terminal.open(terminalElement);
            fitAddon.fit();
        }
        
        // Handle terminal input
        terminal.onData((data: string) => {
            if (ws && ws.readyState === WebSocket.OPEN && isConnected) {
                ws.send(JSON.stringify({
                    type: 'input',
                    data: data
                }));
            }
        });
        
        // Handle resize
        terminal.onResize(({ cols, rows }: { cols: number; rows: number }) => {
            if (ws && ws.readyState === WebSocket.OPEN && isConnected) {
                ws.send(JSON.stringify({
                    type: 'resize',
                    cols: cols,
                    rows: rows
                }));
            }
        });
        
        // Display welcome message
        terminal.writeln('\r\n\x1b[1;34m═══════════════════════════════════════\x1b[0m');
        terminal.writeln('\r\n  \x1b[1;36mNexus SSH Terminal\x1b[0m');
        terminal.writeln('\r\n  Enter connection details above to start');
        terminal.writeln('\r\n\x1b[1;34m═══════════════════════════════════════\x1b[0m\r\n');
    }
    
    async function connect(): Promise<void> {
        if (!host.trim() || !username.trim()) {
            showError('Please enter host and username');
            return;
        }
        
        if (isConnecting) return;
        
        isConnecting = true;
        updateStatus('connecting', 'Connecting...');
        
        try {
            // Create WebSocket connection
            const wsUrl = `ws://${window.location.host}/ws/terminal`;
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                if (terminal) {
                    terminal.clear();
                    terminal.writeln('\r\n\x1b[33mConnecting to ' + host + '...\x1b[0m\r\n');
                }
                
                // Send connection request
                if (ws) {
                    ws.send(JSON.stringify({
                        type: 'connect',
                        host: host.trim(),
                        port: port,
                        username: username.trim(),
                        password: password
                    }));
                }
            };
            
            ws.onmessage = (event: MessageEvent) => {
                const message = JSON.parse(event.data);
                
                switch (message.type) {
                    case 'connected':
                        sessionId = message.session_id;
                        isConnected = true;
                        isConnecting = false;
                        updateStatus('connected', `Connected to ${host}`);
                        if (terminal) {
                            terminal.writeln('\r\n\x1b[32mConnected successfully!\x1b[0m\r\n');
                            terminal.focus();
                        }
                        break;
                        
                    case 'output':
                        if (terminal) {
                            terminal.write(message.data);
                        }
                        break;
                        
                    case 'error':
                        showError(message.message);
                        updateStatus('error', 'Connection failed');
                        isConnecting = false;
                        if (terminal) {
                            terminal.writeln('\r\n\x1b[31mError: ' + message.message + '\x1b[0m\r\n');
                        }
                        break;
                        
                    case 'reconnected':
                        sessionId = message.session_id;
                        isConnected = true;
                        updateStatus('connected', 'Reconnected');
                        if (terminal) {
                            terminal.writeln('\r\n\x1b[32mReconnected to session\x1b[0m\r\n');
                        }
                        break;
                        
                    case 'keepalive':
                        // Server sent keepalive, respond with pong
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            ws.send(JSON.stringify({ type: 'pong' }));
                        }
                        break;
                        
                    case 'pong':
                        // Server responded to our ping
                        console.debug('Received pong from server');
                        break;
                }
            };
            
            ws.onerror = (error: Event) => {
                console.error('WebSocket error:', error);
                showError('WebSocket connection failed');
                updateStatus('error', 'Connection error');
                isConnecting = false;
            };
            
            ws.onclose = () => {
                if (isConnected) {
                    updateStatus('disconnected', 'Disconnected');
                    if (terminal) {
                        terminal.writeln('\r\n\x1b[33mConnection closed\x1b[0m\r\n');
                    }
                }
                isConnected = false;
                isConnecting = false;
                ws = null;
            };
            
        } catch (error) {
            console.error('Connection error:', error);
            showError('Failed to establish connection');
            updateStatus('error', 'Connection failed');
            isConnecting = false;
        }
    }
    
    function disconnect(): void {
        if (ws) {
            ws.close();
            ws = null;
        }
        isConnected = false;
        sessionId = null;
        updateStatus('disconnected', 'Disconnected');
    }
    
    function clearTerminal(): void {
        if (terminal) {
            terminal.clear();
        }
    }
    
    function copySelection(): void {
        if (terminal && terminal.hasSelection()) {
            const selection = terminal.getSelection();
            navigator.clipboard.writeText(selection).then(() => {
                terminal.clearSelection();
                showMessage('Copied to clipboard');
            }).catch(() => {
                // Fallback for older browsers
                showMessage('Copy selection failed');
            });
        }
    }
    
    function updateStatus(status: string, text: string): void {
        statusIndicator = status;
        statusText = text;
    }
    
    function showError(message: string): void {
        console.error('Terminal Error:', message);
        // You can implement a toast notification here
    }
    
    function showMessage(message: string): void {
        console.info('Terminal Info:', message);
        // You can implement a toast notification here
    }
    
    function handleKeyPress(event: KeyboardEvent): void {
        if (event.key === 'Enter' && !isConnecting) {
            connect();
        }
    }
    
    // Handle window resize
    function handleResize(): void {
        if (fitAddon) {
            fitAddon.fit();
        }
    }
</script>

<style>
    .terminal-container {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: #1a1a1a;
        color: #e0e0e0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    }
    
    .header {
        background: #2a2a2a;
        padding: 1rem;
        border-bottom: 1px solid #3a3a3a;
        display: flex;
        align-items: center;
        gap: 1rem;
        flex-shrink: 0;
    }
    
    .connection-form {
        display: flex;
        gap: 0.5rem;
        flex: 1;
        align-items: center;
    }
    
    .connection-form input {
        background: #1a1a1a;
        border: 1px solid #3a3a3a;
        color: #e0e0e0;
        padding: 0.5rem;
        border-radius: 4px;
        font-size: 14px;
    }
    
    .connection-form input:focus {
        outline: none;
        border-color: #4a9eff;
    }
    
    .connection-form input[type="number"] {
        width: 80px;
    }
    
    .connection-form button {
        background: #4a9eff;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 500;
        font-size: 14px;
    }
    
    .connection-form button:hover:not(:disabled) {
        background: #3a8eef;
    }
    
    .connection-form button:disabled {
        background: #666;
        cursor: not-allowed;
    }
    
    .status {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        background: #1a1a1a;
        border-radius: 4px;
        font-size: 14px;
    }
    
    .status-indicator {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #666;
    }
    
    .status-indicator.connected {
        background: #4ade80;
        animation: pulse 2s infinite;
    }
    
    .status-indicator.connecting {
        background: #fbbf24;
        animation: pulse 1s infinite;
    }
    
    .status-indicator.error {
        background: #ef4444;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    
    .terminal-wrapper {
        flex: 1;
        padding: 1rem;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
    
    .terminal-element {
        flex: 1;
        background: #0c0c0c;
        border-radius: 4px;
        padding: 0.5rem;
    }
    
    .controls {
        background: #2a2a2a;
        padding: 0.5rem 1rem;
        border-top: 1px solid #3a3a3a;
        display: flex;
        gap: 1rem;
        align-items: center;
        font-size: 0.9rem;
        flex-shrink: 0;
    }
    
    .controls button {
        background: #3a3a3a;
        color: #e0e0e0;
        border: none;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.85rem;
    }
    
    .controls button:hover {
        background: #4a4a4a;
    }
    
    .session-info {
        margin-left: auto;
        opacity: 0.7;
        font-size: 0.8rem;
    }
</style>

<div class="terminal-container">
    <div class="header">
        <div class="connection-form">
            <input 
                type="text" 
                bind:value={host}
                placeholder="Host (e.g., 192.168.1.100)" 
                on:keypress={handleKeyPress}
                disabled={isConnecting}
            />
            <input 
                type="number" 
                bind:value={port}
                placeholder="Port" 
                on:keypress={handleKeyPress}
                disabled={isConnecting}
            />
            <input 
                type="text" 
                bind:value={username}
                placeholder="Username" 
                on:keypress={handleKeyPress}
                disabled={isConnecting}
            />
            <input 
                type="password" 
                bind:value={password}
                placeholder="Password" 
                on:keypress={handleKeyPress}
                disabled={isConnecting}
            />
            
            {#if !isConnected}
                <button 
                    on:click={connect}
                    disabled={isConnecting}
                >
                    {isConnecting ? 'Connecting...' : 'Connect'}
                </button>
            {:else}
                <button on:click={disconnect}>
                    Disconnect
                </button>
            {/if}
        </div>
        
        <div class="status">
            <span class="status-indicator {statusIndicator}"></span>
            <span>{statusText}</span>
        </div>
    </div>
    
    <div class="terminal-wrapper">
        <div class="terminal-element" bind:this={terminalElement}></div>
    </div>
    
    <div class="controls">
        <button on:click={clearTerminal}>Clear</button>
        <button on:click={copySelection}>Copy</button>
        
        <div class="session-info">
            {#if sessionId}
                Session: {sessionId.substring(0, 8)}...
            {/if}
        </div>
    </div>
</div>
