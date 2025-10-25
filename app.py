import asyncio
import json
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from browser_manager import browser_manager
import logging

# Set the event loop policy for Windows compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Initializing browser...")
    await browser_manager.initialize()
    logger.info("Browser initialized successfully")
    yield
    # Shutdown
    logger.info("Closing browser...")
    await browser_manager.close()
    logger.info("Browser closed")

app = FastAPI(title="Remote Browser Control", version="1.0.0", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_index():
    """Serve the main control interface."""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "browser": "connected"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for browser control."""
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"Client connected. Total connections: {len(active_connections)}")
    
    try:
        # Start screenshot streaming task
        screenshot_task = asyncio.create_task(stream_screenshots(websocket))
        
        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                await handle_client_message(message)
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        active_connections.discard(websocket)
        screenshot_task.cancel()
        logger.info(f"Client disconnected. Total connections: {len(active_connections)}")

async def stream_screenshots(websocket: WebSocket):
    """Stream screenshots to client at 10 FPS."""
    screenshot_count = 0
    while True:
        try:
            if websocket in active_connections:
                screenshot = await browser_manager.get_screenshot()
                screenshot_count += 1
                
                message = {
                    "type": "screenshot",
                    "data": screenshot,
                    "viewport": browser_manager.get_viewport_size()
                }
                await websocket.send_text(json.dumps(message))
                
                # Log every 10th screenshot to avoid spam
                if screenshot_count % 10 == 0:
                    logger.info(f"Sent {screenshot_count} screenshots")
            await asyncio.sleep(0.1)  # 10 FPS
        except WebSocketDisconnect:
            break
        except Exception as e:
            logger.error(f"Error streaming screenshot: {e}")
            break

async def handle_client_message(message: dict):
    """Handle incoming client messages."""
    try:
        message_type = message.get("type")
        
        if message_type == "mouse_move":
            x, y = message.get("x", 0), message.get("y", 0)
            await browser_manager.mouse_move(x, y)
        
        elif message_type == "mouse_click":
            x, y = message.get("x", 0), message.get("y", 0)
            button = message.get("button", "left")
            await browser_manager.mouse_click(x, y, button)
        
        elif message_type == "mouse_down":
            x, y = message.get("x", 0), message.get("y", 0)
            button = message.get("button", "left")
            await browser_manager.mouse_down(x, y, button)
        
        elif message_type == "mouse_up":
            x, y = message.get("x", 0), message.get("y", 0)
            button = message.get("button", "left")
            await browser_manager.mouse_up(x, y, button)
        
        elif message_type == "mouse_wheel":
            delta_x = message.get("deltaX", 0)
            delta_y = message.get("deltaY", 0)
            await browser_manager.mouse_wheel(delta_x, delta_y)
        
        elif message_type == "key_press":
            key = message.get("key")
            if key:
                await browser_manager.keyboard_press(key)
        
        elif message_type == "key_type":
            text = message.get("text", "")
            await browser_manager.keyboard_type(text)
        
        elif message_type == "navigate":
            url = message.get("url", "")
            await browser_manager.navigate_to(url)
        
        elif message_type == "go_back":
            await browser_manager.go_back()
        
        elif message_type == "go_forward":
            await browser_manager.go_forward()
        
        elif message_type == "refresh":
            await browser_manager.refresh()
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    except Exception as e:
        logger.error(f"Error handling client message: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)
