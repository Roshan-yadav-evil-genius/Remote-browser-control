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

# Store last add_tab request time to prevent duplicates
last_add_tab_time = 0

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
                await handle_client_message(message, websocket)
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

async def handle_client_message(message: dict, websocket: WebSocket):
    """Handle incoming client messages."""
    try:
        message_type = message.get("type")
        
        if message_type == "mouse_move":
            x, y = message.get("x", 0), message.get("y", 0)
            logger.info(f"Mouse move: ({x}, {y}) on page {browser_manager._active_page_index}")
            await browser_manager.mouse_move(x, y)
        
        elif message_type == "mouse_click":
            x, y = message.get("x", 0), message.get("y", 0)
            button = message.get("button", "left")
            logger.info(f"Mouse click: ({x}, {y}) button={button} on page {browser_manager._active_page_index}")
            await browser_manager.mouse_click(x, y, button)
        
        elif message_type == "mouse_down":
            x, y = message.get("x", 0), message.get("y", 0)
            button = message.get("button", "left")
            logger.info(f"Mouse down: ({x}, {y}) button={button} on page {browser_manager._active_page_index}")
            await browser_manager.mouse_down(x, y, button)
        
        elif message_type == "mouse_up":
            x, y = message.get("x", 0), message.get("y", 0)
            button = message.get("button", "left")
            logger.info(f"Mouse up: ({x}, {y}) button={button} on page {browser_manager._active_page_index}")
            await browser_manager.mouse_up(x, y, button)
        
        elif message_type == "mouse_wheel":
            delta_x = message.get("deltaX", 0)
            delta_y = message.get("deltaY", 0)
            logger.info(f"Mouse wheel: deltaX={delta_x}, deltaY={delta_y} on page {browser_manager._active_page_index}")
            await browser_manager.mouse_wheel(delta_x, delta_y)
        
        elif message_type == "key_press":
            key = message.get("key")
            if key:
                logger.info(f"Key press: {key}")
                await browser_manager.keyboard_press(key)
        
        elif message_type == "key_type":
            text = message.get("text", "")
            logger.info(f"Key type: '{text}'")
            await browser_manager.keyboard_type(text)
        
        elif message_type == "navigate":
            url = message.get("url", "")
            logger.info(f"Navigate to: {url}")
            await browser_manager.navigate_to(url)
        
        elif message_type == "go_back":
            logger.info("Go back")
            await browser_manager.go_back()
        
        elif message_type == "go_forward":
            logger.info("Go forward")
            await browser_manager.go_forward()
        
        elif message_type == "refresh":
            logger.info("Refresh page")
            await browser_manager.refresh()
        
        elif message_type == "get_pages":
            logger.info("Get pages info")
            pages_info = browser_manager.get_pages_info()
            logger.info(f"Pages info: {pages_info}")
            await websocket.send_text(json.dumps({
                "type": "pages_info",
                "pages": pages_info
            }))
        
        elif message_type == "switch_page":
            page_index = message.get("page_index", 0)
            logger.info(f"Switch to page {page_index} - Current active page: {browser_manager._active_page_index}")
            success = await browser_manager.switch_to_page(page_index)
            logger.info(f"Page switch result: {'success' if success else 'failed'} for page {page_index}")
            await websocket.send_text(json.dumps({
                "type": "page_switched",
                "success": success,
                "page_index": page_index
            }))
        
        elif message_type == "close_page":
            page_index = message.get("page_index", 0)
            logger.info(f"Close page {page_index}")
            success = await browser_manager.close_page(page_index)
            await websocket.send_text(json.dumps({
                "type": "page_closed",
                "success": success,
                "page_index": page_index
            }))
        
        elif message_type == "add_tab":
            import time
            current_time = time.time()
            global last_add_tab_time
            
            # Prevent duplicate requests within 5 seconds
            if current_time - last_add_tab_time < 5.0:
                logger.info("Add tab request ignored (too soon after last request)")
                await websocket.send_text(json.dumps({
                    "type": "tab_added",
                    "success": False,
                    "reason": "duplicate_request"
                }))
                return
            
            last_add_tab_time = current_time
            logger.info("Add new tab")
            success = await browser_manager.add_new_tab()
            await websocket.send_text(json.dumps({
                "type": "tab_added",
                "success": success
            }))
        
        elif message_type == "refresh_pages":
            logger.info("Refresh pages list")
            browser_manager.cleanup_duplicate_pages()
            pages_info = browser_manager.get_pages_info()
            await websocket.send_text(json.dumps({
                "type": "pages_info",
                "pages": pages_info
            }))
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    except Exception as e:
        logger.error(f"Error handling client message: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)
