# Remote Browser Control System

A FastAPI-based web application that allows clients to control a headless Playwright browser through a VNC-style web interface with real-time mouse and keyboard control.

## Features

- **Real-time Browser Control**: Control a headless Playwright browser through a web interface
- **VNC-style Interface**: Mouse and keyboard control with live screenshot streaming
- **Persistent Browser State**: Uses existing browser data directory for session persistence
- **Modern Web Interface**: Responsive design with real-time status indicators
- **WebSocket Communication**: Low-latency bidirectional communication
- **Cross-platform**: Works on Windows, macOS, and Linux

## Requirements

- Python 3.8+
- Playwright browser binaries
- Modern web browser for the control interface

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright browsers:**
   ```bash
   playwright install chromium
   ```

3. **Start the application:**
   ```bash
   python app.py
   ```

4. **Open your web browser and navigate to:**
   ```
   http://localhost:8001
   ```

## Usage

### Web Interface Controls

- **Mouse Control**: Click and drag on the browser viewport to interact
- **Keyboard Input**: Click on input fields and type normally
- **Scrolling**: Use mouse wheel to scroll pages
- **Navigation**: Use the URL bar and navigation buttons
- **Right-click**: Right-click for context menus

### Keyboard Shortcuts

- **Enter**: Submit forms or activate buttons
- **Tab**: Navigate between form elements
- **Arrow Keys**: Navigate within pages
- **F5**: Refresh page
- **Ctrl+A**: Select all
- **Ctrl+C**: Copy
- **Ctrl+V**: Paste

## Architecture

### Components

- **`app.py`**: FastAPI application with WebSocket endpoints
- **`browser_manager.py`**: Singleton class managing Playwright browser instance
- **`static/index.html`**: Web interface HTML
- **`static/styles.css`**: Modern responsive styling
- **`static/app.js`**: Client-side JavaScript for browser control

### Communication Flow

1. Client connects via WebSocket to `/ws` endpoint
2. Server streams screenshots at 10 FPS to client
3. Client sends mouse/keyboard events to server
4. Server translates events to Playwright commands
5. Browser executes commands and updates viewport

### Browser Configuration

The browser runs with the following settings:
- **Headless mode**: Browser runs without visible window
- **Viewport**: 1920x1080 resolution
- **User agent**: Chrome 140.0.0.0
- **Anti-detection**: Disabled automation indicators

## API Endpoints

### REST Endpoints

- `GET /` - Main control interface
- `GET /health` - Health check
- `GET /static/*` - Static files

### WebSocket Endpoints

- `WS /ws` - Browser control communication

### WebSocket Message Types

**Client to Server:**
```json
{
  "type": "mouse_move",
  "x": 100,
  "y": 200
}
```

```json
{
  "type": "mouse_click",
  "x": 100,
  "y": 200,
  "button": "left"
}
```

```json
{
  "type": "key_press",
  "key": "Enter"
}
```

```json
{
  "type": "navigate",
  "url": "https://example.com"
}
```

**Server to Client:**
```json
{
  "type": "screenshot",
  "data": "base64_encoded_image",
  "viewport": [1920, 1080]
}
```

## Development

### Project Structure
```
remotebrowser/
├── app.py                    # FastAPI application
├── browser_manager.py        # Browser control logic
├── requirements.txt          # Dependencies
├── static/
│   ├── index.html           # Web interface
│   ├── styles.css           # Styling
│   └── app.js               # Client JavaScript
├── POC/                     # Existing browser data
└── README.md                # This file
```

### Running in Development

```bash
# Activate conda environment
conda activate TheOneEyePoc

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run the application
python app.py

# Or with uvicorn directly
uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

### Customization

- **Screenshot Quality**: Modify `quality=80` in `browser_manager.py`
- **Streaming FPS**: Change `await asyncio.sleep(0.1)` in `app.py`
- **Viewport Size**: Update `_viewport_size` in `browser_manager.py`
- **Browser Args**: Modify browser launch arguments in `browser_manager.py`

## Troubleshooting

### Common Issues

1. **Browser won't start**: Ensure Playwright is installed with `playwright install chromium`
2. **WebSocket connection fails**: Check firewall settings and port availability
3. **Screenshots not updating**: Verify browser is running and responsive
4. **Mouse/keyboard not working**: Check browser focus and event handling
5. **Canvas not displaying screenshots**: Check browser console for JavaScript errors
6. **WSL/Linux issues**: Ensure conda environment is activated before running

### Logs

The application logs important events:
- Browser initialization
- WebSocket connections
- Client message handling
- Error conditions

Check console output for debugging information.

## Security Considerations

- **Local Access Only**: By default, the server binds to `127.0.0.1:8001`
- **No Authentication**: The interface has no built-in authentication
- **Browser Security**: Uses persistent context with existing browser data
- **Network Security**: Consider using HTTPS in production

## License

This project is for educational and development purposes.
