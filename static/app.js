class RemoteBrowserController {
    constructor() {
        this.ws = null;
        this.canvas = document.getElementById('browserCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.urlInput = document.getElementById('urlInput');
        
        this.isConnected = false;
        this.browserViewport = null;
        this.scale = 1;
        this.mousePosition = { x: 0, y: 0 };
        
        this.setupEventListeners();
        this.connect();
    }
    
    setupEventListeners() {
        // Navigation controls
        document.getElementById('navigateBtn').addEventListener('click', () => this.navigate());
        document.getElementById('backBtn').addEventListener('click', () => this.goBack());
        document.getElementById('forwardBtn').addEventListener('click', () => this.goForward());
        document.getElementById('refreshBtn').addEventListener('click', () => this.refresh());
        
        // URL input
        this.urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.navigate();
            }
        });
        
        // Canvas mouse events
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e));
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
        
        // Keyboard events
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
        document.addEventListener('keyup', (e) => this.handleKeyUp(e));
        
        // Prevent default browser behaviors
        document.addEventListener('keydown', (e) => {
            if (e.target === this.urlInput) return;
            e.preventDefault();
        });
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            this.isConnected = true;
            this.updateConnectionStatus('connected');
            this.loadingOverlay.classList.add('hidden');
            console.log('Connected to browser control server');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleServerMessage(message);
            } catch (error) {
                console.error('Error parsing server message:', error);
            }
        };
        
        this.ws.onclose = () => {
            this.isConnected = false;
            this.updateConnectionStatus('disconnected');
            this.loadingOverlay.classList.remove('hidden');
            console.log('Disconnected from server');
            
            // Attempt to reconnect after 3 seconds
            setTimeout(() => {
                if (!this.isConnected) {
                    this.connect();
                }
            }, 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('disconnected');
        };
    }
    
    handleServerMessage(message) {
        switch (message.type) {
            case 'screenshot':
                this.displayScreenshot(message.data);
                
                // Always update viewport and canvas size on first screenshot or when viewport changes
                const newViewport = message.viewport;
                const currentViewport = this.browserViewport;
                
                const viewportChanged = !currentViewport || 
                    (Array.isArray(newViewport) && Array.isArray(currentViewport) && 
                     (newViewport[0] !== currentViewport[0] || newViewport[1] !== currentViewport[1])) ||
                    (!Array.isArray(newViewport) && !Array.isArray(currentViewport) && 
                     (newViewport.width !== currentViewport.width || newViewport.height !== currentViewport.height));
                
                if (!currentViewport) {
                    console.log('Initial viewport set to', newViewport);
                    this.browserViewport = newViewport;
                    this.updateCanvasSize();
                } else if (viewportChanged) {
                    console.log('Viewport changed from', currentViewport, 'to', newViewport);
                    this.browserViewport = newViewport;
                    this.updateCanvasSize();
                } else {
                    console.log('Viewport unchanged, skipping updateCanvasSize');
                }
                break;
        }
    }
    
    displayScreenshot(screenshotData) {
        const img = new Image();
        img.onload = () => {
            console.log('Image loaded, canvas size:', this.canvas.width, 'x', this.canvas.height);
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            this.ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
            
            // Draw mouse cursor indicator
            this.drawMouseCursor();
        };
        img.onerror = (e) => {
            console.error('Image load error:', e);
        };
        img.src = `data:image/jpeg;base64,${screenshotData}`;
    }
    
    drawMouseCursor() {
        // Draw a small red circle at the actual mouse position on canvas
        const canvasX = this.mousePosition.canvasX;
        const canvasY = this.mousePosition.canvasY;
        
        this.ctx.save();
        this.ctx.beginPath();
        this.ctx.arc(canvasX, canvasY, 5, 0, 2 * Math.PI);
        this.ctx.fillStyle = 'red';
        this.ctx.fill();
        this.ctx.strokeStyle = 'white';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
        this.ctx.restore();
    }
    
    updateCanvasSize() {
        const container = this.canvas.parentElement;
        const maxWidth = container.clientWidth - 20;  // Reduced from 40 to 20
        const maxHeight = window.innerHeight * 0.9;    // Increased from 0.8 to 0.9
        
        // Handle both array [width, height] and object {width, height} formats
        const viewportWidth = Array.isArray(this.browserViewport) ? this.browserViewport[0] : this.browserViewport.width;
        const viewportHeight = Array.isArray(this.browserViewport) ? this.browserViewport[1] : this.browserViewport.height;
        
        const aspectRatio = viewportWidth / viewportHeight;
        
        // Calculate the maximum size that fits in the container while maintaining aspect ratio
        let canvasWidth = Math.min(viewportWidth, maxWidth);
        let canvasHeight = canvasWidth / aspectRatio;
        
        // If height is too big, scale down based on height
        if (canvasHeight > maxHeight) {
            canvasHeight = maxHeight;
            canvasWidth = canvasHeight * aspectRatio;
        }
        
        // Only resize if dimensions have actually changed
        if (Math.abs(this.canvas.width - canvasWidth) > 1 || Math.abs(this.canvas.height - canvasHeight) > 1) {
            console.log(`Canvas resize: ${this.canvas.width}x${this.canvas.height} -> ${canvasWidth}x${canvasHeight}`);
            this.canvas.width = canvasWidth;
            this.canvas.height = canvasHeight;
        }
        
        this.scale = canvasWidth / viewportWidth;
        console.log(`Scale: ${this.scale.toFixed(3)} (canvas: ${canvasWidth} / viewport: ${viewportWidth})`);
    }
    
    getCanvasCoordinates(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (event.clientX - rect.left) / this.scale;
        const y = (event.clientY - rect.top) / this.scale;
        return { x: Math.round(x), y: Math.round(y) };
    }
    
    handleMouseMove(event) {
        if (!this.isConnected) return;
        
        const coords = this.getCanvasCoordinates(event);
        // Store the raw canvas coordinates for drawing the red dot
        const rect = this.canvas.getBoundingClientRect();
        this.mousePosition = { 
            x: coords.x, 
            y: coords.y,
            canvasX: event.clientX - rect.left,
            canvasY: event.clientY - rect.top
        };
        this.sendMessage({
            type: 'mouse_move',
            x: coords.x,
            y: coords.y
        });
    }
    
    handleMouseDown(event) {
        if (!this.isConnected) return;
        
        const coords = this.getCanvasCoordinates(event);
        const button = event.button === 2 ? 'right' : 'left';
        
        this.sendMessage({
            type: 'mouse_down',
            x: coords.x,
            y: coords.y,
            button: button
        });
    }
    
    handleMouseUp(event) {
        if (!this.isConnected) return;
        
        const coords = this.getCanvasCoordinates(event);
        const button = event.button === 2 ? 'right' : 'left';
        
        this.sendMessage({
            type: 'mouse_up',
            x: coords.x,
            y: coords.y,
            button: button
        });
    }
    
    handleWheel(event) {
        if (!this.isConnected) return;
        
        event.preventDefault();
        
        this.sendMessage({
            type: 'mouse_wheel',
            deltaX: event.deltaX,
            deltaY: event.deltaY
        });
    }
    
    handleKeyDown(event) {
        if (!this.isConnected || event.target === this.urlInput) return;
        
        event.preventDefault();
        
        // Handle special keys
        const keyMap = {
            'Enter': 'Enter',
            'Escape': 'Escape',
            'Tab': 'Tab',
            'Backspace': 'Backspace',
            'Delete': 'Delete',
            'ArrowUp': 'ArrowUp',
            'ArrowDown': 'ArrowDown',
            'ArrowLeft': 'ArrowLeft',
            'ArrowRight': 'ArrowRight',
            'Home': 'Home',
            'End': 'End',
            'PageUp': 'PageUp',
            'PageDown': 'PageDown',
            'F1': 'F1', 'F2': 'F2', 'F3': 'F3', 'F4': 'F4',
            'F5': 'F5', 'F6': 'F6', 'F7': 'F7', 'F8': 'F8',
            'F9': 'F9', 'F10': 'F10', 'F11': 'F11', 'F12': 'F12'
        };
        
        const key = keyMap[event.key] || event.key;
        
        this.sendMessage({
            type: 'key_press',
            key: key
        });
    }
    
    handleKeyUp(event) {
        if (!this.isConnected || event.target === this.urlInput) return;
        // Key up events are handled by key down for simplicity
    }
    
    navigate() {
        if (!this.isConnected) return;
        
        const url = this.urlInput.value.trim();
        if (url) {
            this.sendMessage({
                type: 'navigate',
                url: url
            });
        }
    }
    
    goBack() {
        if (!this.isConnected) return;
        this.sendMessage({ type: 'go_back' });
    }
    
    goForward() {
        if (!this.isConnected) return;
        this.sendMessage({ type: 'go_forward' });
    }
    
    refresh() {
        if (!this.isConnected) return;
        this.sendMessage({ type: 'refresh' });
    }
    
    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }
    
    updateConnectionStatus(status) {
        this.connectionStatus.textContent = status === 'connected' ? 'Connected' : 
                                          status === 'connecting' ? 'Connecting...' : 'Disconnected';
        this.connectionStatus.className = `status-indicator ${status}`;
    }
}

// Initialize the controller when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new RemoteBrowserController();
});

// Handle window resize
window.addEventListener('resize', () => {
    if (window.controller) {
        window.controller.updateCanvasSize();
    }
});
