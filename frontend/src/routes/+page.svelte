<script lang="ts">
    import Terminal from '../lib/Terminal.svelte';
    import AIChat from '../lib/AIChat.svelte';

    let showAiChat = $state(false);
    let terminalSessionId = $state<string | null>(null);
    let terminalComponent: Terminal;

    function toggleAiChat() {
        showAiChat = !showAiChat;
    }

    function handleSessionChange(sessionId: string | null) {
        terminalSessionId = sessionId;
    }

    function handleExecuteCommand(command: string) {
        if (terminalComponent && terminalSessionId) {
            terminalComponent.sendCommand(command);
        }
    }
</script>

<style>
    :global(body) {
        margin: 0;
        padding: 0;
        height: 100vh;
        overflow: hidden;
    }
    
    .app-container {
        display: flex;
        height: 100vh;
        background: #1a1a1a;
    }
    
    .terminal-panel {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-width: 0; /* Allows flex item to shrink */
    }
    
    .ai-panel {
        width: 400px;
        background: #2a2a2a;
        border-left: 1px solid #3a3a3a;
        display: flex;
        flex-direction: column;
    }
    
    .toggle-button {
        position: fixed;
        top: 1rem;
        right: 1rem;
        background: #4a9eff;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 500;
        z-index: 1000;
    }
    
    .toggle-button:hover {
        background: #3a8eef;
    }
    
    @media (max-width: 768px) {
        .app-container {
            flex-direction: column;
        }
        
        .ai-panel {
            width: 100%;
            height: 300px;
        }
    }
</style>

<svelte:head>
    <title>Nexus SSH Terminal</title>
</svelte:head>

<div class="app-container">
    <div class="terminal-panel">
        <Terminal bind:this={terminalComponent} onSessionChange={handleSessionChange} />
    </div>

    {#if showAiChat}
        <div class="ai-panel">
            <AIChat
                terminalSessionId={terminalSessionId}
                onExecuteCommand={handleExecuteCommand}
            />
        </div>
    {/if}

    <button class="toggle-button" onclick={toggleAiChat}>
        {showAiChat ? 'Hide AI' : 'Show AI'}
    </button>
</div>