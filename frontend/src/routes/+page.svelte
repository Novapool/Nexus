<script>
    import Terminal from '../lib/Terminal.svelte';
    
    // Future: AI Chat component will go here
    let showAiChat = false;
    
    function toggleAiChat() {
        showAiChat = !showAiChat;
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
    
    .ai-panel-header {
        padding: 1rem;
        border-bottom: 1px solid #3a3a3a;
        color: #e0e0e0;
        font-weight: 600;
    }
    
    .ai-panel-content {
        flex: 1;
        padding: 1rem;
        color: #e0e0e0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-style: italic;
        opacity: 0.7;
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
        <Terminal />
    </div>
    
    {#if showAiChat}
        <div class="ai-panel">
            <div class="ai-panel-header">
                AI Assistant
                <button 
                    style="float: right; background: transparent; border: none; color: #e0e0e0; cursor: pointer;" 
                    on:click={toggleAiChat}
                >
                    ✕
                </button>
            </div>
            <div class="ai-panel-content">
                AI Chat coming in Phase 2.2...
            </div>
        </div>
    {/if}
    
    <button class="toggle-button" on:click={toggleAiChat}>
        {showAiChat ? 'Hide AI' : 'Show AI'}
    </button>
</div>