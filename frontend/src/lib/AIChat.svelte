<script lang="ts">
    import { onMount, onDestroy } from 'svelte';

    // Props
    type Props = {
        terminalSessionId?: string | null;
        onExecuteCommand?: (command: string) => void;
    };

    let { terminalSessionId = null, onExecuteCommand }: Props = $props();

    // WebSocket message types
    type WSMessage =
        | { type: 'connected'; ai_session_id: string }
        | { type: 'message_chunk'; content: string; done: boolean }
        | { type: 'message_complete'; full_message: string }
        | { type: 'command_detected'; command: string; safety_level: string }
        | { type: 'error'; message: string }
        | { type: 'keepalive' }
        | { type: 'pong' };

    type Message = {
        id: string;
        role: 'user' | 'assistant';
        content: string;
        timestamp: Date;
    };

    type DetectedCommand = {
        command: string;
        safety_level: string;
    };

    // State
    let ws = $state<WebSocket | null>(null);
    let aiSessionId = $state<string | null>(null);
    let isConnected = $state(false);
    let messages = $state<Message[]>([]);
    let inputMessage = $state('');
    let isProcessing = $state(false);
    let currentAssistantMessage = $state('');
    let detectedCommands = $state<DetectedCommand[]>([]);
    let errorMessage = $state<string | null>(null);

    // DOM references
    let messagesContainer: HTMLDivElement;
    let inputField: HTMLTextAreaElement;

    onMount(() => {
        connectToAI();
        return () => {
            disconnect();
        };
    });

    onDestroy(() => {
        disconnect();
    });

    function connectToAI(): void {
        try {
            const wsUrl = `ws://${window.location.host}/ws/ai`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log('AI WebSocket connected');

                // Send connect message
                if (ws) {
                    ws.send(JSON.stringify({
                        type: 'connect',
                        terminal_session_id: terminalSessionId
                    }));
                }
            };

            ws.onmessage = (event: MessageEvent) => {
                const message = JSON.parse(event.data) as WSMessage;
                handleWSMessage(message);
            };

            ws.onerror = (error: Event) => {
                console.error('AI WebSocket error:', error);
                errorMessage = 'Connection error. Please check if Ollama is running.';
            };

            ws.onclose = (event: CloseEvent) => {
                isConnected = false;
                ws = null;
                console.log('AI WebSocket closed:', event.code);
            };

        } catch (error) {
            console.error('Failed to connect to AI:', error);
            errorMessage = 'Failed to connect to AI service';
        }
    }

    function handleWSMessage(message: WSMessage): void {
        switch (message.type) {
            case 'connected':
                aiSessionId = message.ai_session_id;
                isConnected = true;
                errorMessage = null;
                console.log('AI session connected:', aiSessionId);
                break;

            case 'message_chunk':
                // Accumulate chunks for streaming response
                currentAssistantMessage += message.content;
                scrollToBottom();
                break;

            case 'message_complete':
                // Finalize assistant message
                if (currentAssistantMessage || message.full_message) {
                    const content = message.full_message || currentAssistantMessage;
                    messages.push({
                        id: generateId(),
                        role: 'assistant',
                        content: content,
                        timestamp: new Date()
                    });
                    currentAssistantMessage = '';
                    isProcessing = false;
                    scrollToBottom();
                }
                break;

            case 'command_detected':
                detectedCommands.push({
                    command: message.command,
                    safety_level: message.safety_level
                });
                break;

            case 'error':
                errorMessage = message.message;
                isProcessing = false;
                currentAssistantMessage = '';
                break;

            case 'keepalive':
                // Respond with pong
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'pong' }));
                }
                break;

            case 'pong':
                // Server acknowledged our ping
                console.debug('Received pong from AI server');
                break;
        }
    }

    function sendMessage(): void {
        if (!inputMessage.trim() || !isConnected || isProcessing) {
            return;
        }

        // Add user message to display
        messages.push({
            id: generateId(),
            role: 'user',
            content: inputMessage,
            timestamp: new Date()
        });

        // Send to AI
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'message',
                content: inputMessage,
                include_context: true
            }));

            isProcessing = true;
            currentAssistantMessage = '';
            detectedCommands = [];
            errorMessage = null;
        }

        // Clear input
        inputMessage = '';
        scrollToBottom();
    }

    function handleKeyDown(event: KeyboardEvent): void {
        // Send on Enter (without Shift)
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }

    function disconnect(): void {
        if (ws) {
            ws.close();
            ws = null;
        }
        isConnected = false;
        aiSessionId = null;
    }

    function scrollToBottom(): void {
        if (messagesContainer) {
            setTimeout(() => {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }, 0);
        }
    }

    function generateId(): string {
        return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }

    function formatTime(date: Date): string {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function getSafetyColor(level: string): string {
        switch (level) {
            case 'safe': return '#4ade80';
            case 'caution': return '#fbbf24';
            case 'dangerous': return '#ef4444';
            default: return '#666';
        }
    }

    function clearChat(): void {
        messages = [];
        detectedCommands = [];
        errorMessage = null;
    }

    function executeCommand(command: string, safetyLevel: string): void {
        // Show confirmation for dangerous commands
        if (safetyLevel === 'dangerous') {
            const confirmed = confirm(
                `⚠️ DANGEROUS COMMAND ⚠️\n\nThis command could harm your system:\n\n${command}\n\nAre you absolutely sure you want to execute it?`
            );
            if (!confirmed) {
                return;
            }
        } else if (safetyLevel === 'caution') {
            const confirmed = confirm(
                `⚠️ CAUTION\n\nThis command requires elevated privileges or modifies system state:\n\n${command}\n\nDo you want to execute it?`
            );
            if (!confirmed) {
                return;
            }
        }

        // Call the parent's execute command handler
        if (onExecuteCommand) {
            onExecuteCommand(command);
        } else {
            errorMessage = 'Terminal not connected. Cannot execute command.';
        }
    }

    function copyMessage(content: string): void {
        navigator.clipboard.writeText(content).then(() => {
            // Could add a toast notification here
            console.log('Message copied to clipboard');
        }).catch((err) => {
            console.error('Failed to copy:', err);
        });
    }

    function renderMessage(content: string): string {
        // Simple code block highlighting
        return content.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) => {
            return `<pre class="code-block"><code>${escapeHtml(code.trim())}</code></pre>`;
        }).replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    }

    function escapeHtml(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
</script>

<style>
    .ai-chat-container {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: #2a2a2a;
    }

    .chat-header {
        padding: 1rem;
        border-bottom: 1px solid #3a3a3a;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .header-title {
        color: #e0e0e0;
        font-weight: 600;
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #666;
    }

    .status-dot.connected {
        background: #4ade80;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    .header-actions {
        display: flex;
        gap: 0.5rem;
    }

    .header-button {
        background: #3a3a3a;
        border: none;
        color: #e0e0e0;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.85rem;
    }

    .header-button:hover {
        background: #4a4a4a;
    }

    .messages-container {
        flex: 1;
        overflow-y: auto;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .message {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        animation: fadeIn 0.2s ease-in;
        position: relative;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .message.user {
        align-items: flex-end;
    }

    .message.assistant {
        align-items: flex-start;
    }

    .message-content {
        max-width: 85%;
        padding: 0.75rem 1rem;
        border-radius: 12px;
        word-wrap: break-word;
        white-space: pre-wrap;
        line-height: 1.5;
    }

    .message.user .message-content {
        background: #4a9eff;
        color: white;
        border-bottom-right-radius: 4px;
    }

    .message.assistant .message-content {
        background: #3a3a3a;
        color: #e0e0e0;
        border-bottom-left-radius: 4px;
    }

    .message-time {
        font-size: 0.75rem;
        color: #888;
        padding: 0 0.5rem;
    }

    .processing-indicator {
        padding: 0.75rem 1rem;
        background: #3a3a3a;
        color: #e0e0e0;
        border-radius: 12px;
        border-bottom-left-radius: 4px;
        max-width: 85%;
        animation: fadeIn 0.2s ease-in;
    }

    .typing-dots {
        display: flex;
        gap: 0.25rem;
    }

    .typing-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #888;
        animation: typing 1.4s infinite;
    }

    .typing-dot:nth-child(2) {
        animation-delay: 0.2s;
    }

    .typing-dot:nth-child(3) {
        animation-delay: 0.4s;
    }

    @keyframes typing {
        0%, 60%, 100% { opacity: 0.3; }
        30% { opacity: 1; }
    }

    .commands-section {
        padding: 0.5rem 1rem;
        background: #1a1a1a;
        border-top: 1px solid #3a3a3a;
    }

    .commands-title {
        color: #e0e0e0;
        font-size: 0.85rem;
        margin-bottom: 0.5rem;
        font-weight: 500;
    }

    .command-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem;
        background: #2a2a2a;
        border-radius: 4px;
        margin-bottom: 0.5rem;
        border-left: 3px solid;
    }

    .command-code {
        flex: 1;
        font-family: 'Cascadia Code', 'Fira Code', monospace;
        color: #50fa7b;
        font-size: 0.85rem;
    }

    .command-execute {
        background: #4a9eff;
        border: none;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.8rem;
    }

    .command-execute:hover {
        background: #3a8eef;
    }

    .error-banner {
        background: #ef4444;
        color: white;
        padding: 0.75rem 1rem;
        font-size: 0.9rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .error-close {
        background: none;
        border: none;
        color: white;
        cursor: pointer;
        font-size: 1.2rem;
        padding: 0;
        width: 24px;
        height: 24px;
    }

    .input-container {
        padding: 1rem;
        border-top: 1px solid #3a3a3a;
        display: flex;
        gap: 0.5rem;
        background: #2a2a2a;
    }

    .input-field {
        flex: 1;
        background: #1a1a1a;
        border: 1px solid #3a3a3a;
        color: #e0e0e0;
        padding: 0.75rem;
        border-radius: 8px;
        font-size: 0.95rem;
        font-family: inherit;
        resize: none;
        max-height: 120px;
        min-height: 44px;
    }

    .input-field:focus {
        outline: none;
        border-color: #4a9eff;
    }

    .input-field:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .send-button {
        background: #4a9eff;
        border: none;
        color: white;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        cursor: pointer;
        font-weight: 500;
        font-size: 0.95rem;
        transition: background 0.2s;
    }

    .send-button:hover:not(:disabled) {
        background: #3a8eef;
    }

    .send-button:disabled {
        background: #666;
        cursor: not-allowed;
    }

    .empty-state {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: #888;
        text-align: center;
        padding: 2rem;
    }

    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }

    .empty-state-title {
        font-size: 1.1rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
        color: #aaa;
    }

    .empty-state-text {
        font-size: 0.9rem;
        line-height: 1.6;
    }

    /* Scrollbar styling */
    .messages-container::-webkit-scrollbar {
        width: 8px;
    }

    .messages-container::-webkit-scrollbar-track {
        background: #1a1a1a;
    }

    .messages-container::-webkit-scrollbar-thumb {
        background: #4a4a4a;
        border-radius: 4px;
    }

    .messages-container::-webkit-scrollbar-thumb:hover {
        background: #5a5a5a;
    }

    .copy-button {
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        background: #4a4a4a;
        border: none;
        color: #e0e0e0;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.75rem;
        opacity: 0;
        transition: opacity 0.2s;
    }

    .message:hover .copy-button {
        opacity: 1;
    }

    .copy-button:hover {
        background: #5a5a5a;
    }

    :global(.code-block) {
        background: #1a1a1a;
        padding: 1rem;
        border-radius: 4px;
        overflow-x: auto;
        margin: 0.5rem 0;
        border-left: 3px solid #4a9eff;
    }

    :global(.code-block code) {
        font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
        font-size: 0.9rem;
        color: #50fa7b;
    }

    :global(.inline-code) {
        background: #1a1a1a;
        padding: 0.2rem 0.4rem;
        border-radius: 3px;
        font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
        font-size: 0.9em;
        color: #50fa7b;
    }
</style>

<div class="ai-chat-container">
    <div class="chat-header">
        <div class="header-title">
            <span class="status-dot" class:connected={isConnected}></span>
            AI Assistant
        </div>
        <div class="header-actions">
            <button class="header-button" onclick={clearChat}>Clear</button>
        </div>
    </div>

    {#if errorMessage}
        <div class="error-banner">
            <span>{errorMessage}</span>
            <button class="error-close" onclick={() => errorMessage = null}>×</button>
        </div>
    {/if}

    <div class="messages-container" bind:this={messagesContainer}>
        {#if messages.length === 0 && !isProcessing}
            <div class="empty-state">
                <div class="empty-state-icon">🤖</div>
                <div class="empty-state-title">Nexus AI Assistant</div>
                <div class="empty-state-text">
                    Ask me anything about your server, Linux commands, or system administration.
                    <br />I can generate and explain commands based on your terminal session.
                </div>
            </div>
        {:else}
            {#each messages as message (message.id)}
                <div class="message {message.role}">
                    <div class="message-content">{@html renderMessage(message.content)}</div>
                    <button
                        class="copy-button"
                        onclick={() => copyMessage(message.content)}
                        title="Copy message"
                    >
                        Copy
                    </button>
                    <div class="message-time">{formatTime(message.timestamp)}</div>
                </div>
            {/each}

            {#if isProcessing && currentAssistantMessage}
                <div class="message assistant">
                    <div class="message-content">{@html renderMessage(currentAssistantMessage)}</div>
                </div>
            {:else if isProcessing}
                <div class="processing-indicator">
                    <div class="typing-dots">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            {/if}
        {/if}
    </div>

    {#if detectedCommands.length > 0}
        <div class="commands-section">
            <div class="commands-title">Detected Commands</div>
            {#each detectedCommands as cmd}
                <div class="command-item" style="border-left-color: {getSafetyColor(cmd.safety_level)}">
                    <div class="command-code">{cmd.command}</div>
                    <button
                        class="command-execute"
                        title="Execute in terminal"
                        onclick={() => executeCommand(cmd.command, cmd.safety_level)}
                    >
                        Execute
                    </button>
                </div>
            {/each}
        </div>
    {/if}

    <div class="input-container">
        <textarea
            bind:this={inputField}
            bind:value={inputMessage}
            onkeydown={handleKeyDown}
            class="input-field"
            placeholder={isConnected ? "Ask me anything..." : "Connecting to AI..."}
            disabled={!isConnected || isProcessing}
            rows="1"
        ></textarea>
        <button
            class="send-button"
            onclick={sendMessage}
            disabled={!isConnected || isProcessing || !inputMessage.trim()}
        >
            Send
        </button>
    </div>
</div>
