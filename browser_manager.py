import asyncio
import base64
from io import BytesIO
from typing import Optional, Tuple
from PIL import Image
import sys

# Try to import Playwright, fall back to Selenium if needed
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available, will use fallback method")

# Try to import Selenium as fallback
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium not available")


class BrowserManager:
    """Singleton class to manage browser instance with remote control capabilities."""
    
    _instance = None
    _browser = None
    _context = None
    _page = None
    _playwright = None
    _selenium_driver = None
    _viewport_size = (1920, 1080)
    _browser_type = None  # 'playwright', 'selenium', or 'mock'
    _pages = []  # List of all open pages
    _active_page_index = 0  # Index of currently active page
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance
    
    async def initialize(self, user_data_dir: str = "browser_data"):
        """Initialize the browser with persistent context."""
        if self._browser is None:
            try:
                print("Starting Playwright initialization...")
                
                # For Windows, try a completely different approach
                import sys
                import os
                import threading
                import time
                
                if sys.platform == "win32":
                    print("Windows detected - using alternative initialization method")
                    
                    # Try to use a different event loop policy
                    try:
                        # Create a new event loop in a separate thread
                        playwright_result = {"success": False, "playwright": None, "error": None}
                        
                        def start_playwright_in_thread():
                            try:
                                # Create a new event loop for this thread
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                
                                # Start playwright in this thread
                                playwright = loop.run_until_complete(async_playwright().start())
                                playwright_result["success"] = True
                                playwright_result["playwright"] = playwright
                                print("Playwright started in separate thread")
                            except Exception as e:
                                playwright_result["error"] = e
                                print(f"Thread-based Playwright failed: {e}")
                        
                        # Start the thread
                        thread = threading.Thread(target=start_playwright_in_thread)
                        thread.start()
                        thread.join(timeout=15)
                        
                        if playwright_result["success"]:
                            self._playwright = playwright_result["playwright"]
                            print("Playwright started successfully via thread")
                        else:
                            raise Exception(f"Thread-based initialization failed: {playwright_result.get('error', 'Unknown error')}")
                            
                    except Exception as e:
                        print(f"Thread-based approach failed: {e}")
                        # Fall back to direct approach
                        self._playwright = await async_playwright().start()
                        print("Playwright started via direct approach")
                else:
                    # Non-Windows systems
                    self._playwright = await async_playwright().start()
                    print("Playwright started successfully")
                
                print("Launching Chromium browser...")
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--window-size=1920,1080",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding"
                    ],
                    viewport={"width": self._viewport_size[0], "height": self._viewport_size[1]},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                )
                print("Chromium browser launched successfully")
                
                self._browser = self._context
                self._page = await self._context.new_page()
                self._pages = [self._page]  # Initialize pages list
                self._active_page_index = 0
                print("New page created")
                
                # Set up page event listeners
                self._context.on("page", self._on_new_page)
                
                print("Navigating to scrapingbee...")
                await self._page.goto("https://www.scrapingbee.com/blog/")
                print("Browser initialization completed successfully!")
                
            except Exception as e:
                print(f"Browser initialization error: {e}")
                import traceback
                traceback.print_exc()
                # Try alternative initialization
                await self._initialize_alternative()
    
    async def _initialize_alternative(self):
        """Alternative initialization method for Windows compatibility."""
        try:
            print("Trying alternative browser initialization...")
            
            # If playwright is None, try to initialize it again with different settings
            if self._playwright is None:
                print("Re-initializing Playwright...")
                self._playwright = await async_playwright().start()
                print("Playwright re-initialized")
            
            # Try with different browser args
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir="./POC/browser_data",
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1920,1080"
                ],
                viewport={"width": self._viewport_size[0], "height": self._viewport_size[1]}
            )
            print("Alternative browser context created")
            self._browser = self._context
            self._page = await self._context.new_page()
            print("Alternative page created")
            await self._page.goto("https://www.google.com")
            print("Alternative initialization successful!")
        except Exception as e:
            print(f"Alternative initialization also failed: {e}")
            import traceback
            traceback.print_exc()
            # Create a mock page for testing
            self._create_mock_browser()
    
    def _on_new_page(self, page):
        """Handle new page events (new tabs/windows)."""
        print(f"New page opened: {page.url}")
        self._pages.append(page)
        # Automatically switch to the new page for OAuth flows
        self._active_page_index = len(self._pages) - 1
        self._page = page
        print(f"Switched to new page. Total pages: {len(self._pages)}")
        print(f"Pages list: {[p.url if hasattr(p, 'url') else 'mock' for p in self._pages]}")
    
    def _create_mock_browser(self):
        """Create a mock browser for testing when real browser fails."""
        print("Creating mock browser for testing...")
        self._browser = "mock"
        self._context = "mock"
        self._page = "mock"
        self._browser_type = "mock"
        self._pages = ["mock"]
        self._active_page_index = 0
    
    async def get_screenshot(self) -> str:
        """Capture screenshot and return as base64 encoded string."""
        if not self._page:
            await self.initialize()
        
        # Handle mock browser case
        if self._page == "mock":
            return self._create_mock_screenshot()
        
        try:
            # Wait for page to be ready with more lenient timeout
            try:
                await self._page.wait_for_load_state("networkidle", timeout=2000)
            except Exception:
                # If networkidle times out, try domcontentloaded instead
                try:
                    await self._page.wait_for_load_state("domcontentloaded", timeout=1000)
                except Exception:
                    # If all else fails, just proceed with screenshot
                    pass
            
            # Take screenshot
            screenshot_bytes = await self._page.screenshot(
                type="jpeg", 
                quality=80,
                full_page=False
            )
            
            # Convert to base64
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            return screenshot_b64
        except Exception as e:
            print(f"Screenshot error: {e}")
            # Return a simple error image
            return self._create_error_screenshot()
    
    def _create_error_screenshot(self) -> str:
        """Create a simple error screenshot when browser fails."""
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Create a simple error image
        img = Image.new('RGB', (800, 600), color='lightgray')
        draw = ImageDraw.Draw(img)
        
        # Add error text
        try:
            draw.text((50, 50), "Browser Error - Check Console", fill='red')
            draw.text((50, 100), "Screenshot failed to capture", fill='black')
        except:
            pass
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def _create_mock_screenshot(self) -> str:
        """Create a mock screenshot for testing when browser is not available."""
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Create a mock browser screenshot
        img = Image.new('RGB', (1920, 1080), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add mock content
        try:
            draw.text((50, 50), "Mock Browser - Playwright Not Available", fill='blue')
            draw.text((50, 100), "This is a test screenshot", fill='black')
            draw.text((50, 150), "Browser functionality is limited in mock mode", fill='gray')
            draw.rectangle([50, 200, 500, 300], outline='black', width=2)
            draw.text((60, 220), "Mock Browser Window", fill='black')
        except:
            pass
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    async def mouse_move(self, x: int, y: int):
        """Move mouse to coordinates."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse moved to ({x}, {y})")
            return
        
        try:
            await self._page.mouse.move(x, y)
        except Exception as e:
            print(f"Error in mouse_move: {e}")
    
    async def mouse_click(self, x: int, y: int, button: str = "left"):
        """Click at coordinates."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse clicked at ({x}, {y}) with {button} button")
            return
        
        try:
            await self._page.mouse.click(x, y, button=button)
        except Exception as e:
            print(f"Error in mouse_click: {e}")
    
    async def mouse_down(self, x: int, y: int, button: str = "left"):
        """Mouse down at coordinates."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse down at ({x}, {y}) with {button} button")
            return
        
        try:
            await self._page.mouse.move(x, y)
            await self._page.mouse.down(button=button)
        except Exception as e:
            print(f"Error in mouse_down: {e}")
    
    async def mouse_up(self, x: int, y: int, button: str = "left"):
        """Mouse up at coordinates."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse up at ({x}, {y}) with {button} button")
            return
        
        try:
            await self._page.mouse.move(x, y)
            await self._page.mouse.up(button=button)
        except Exception as e:
            print(f"Error in mouse_up: {e}")
    
    async def mouse_wheel(self, delta_x: int, delta_y: int):
        """Scroll with mouse wheel."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse wheel delta_x={delta_x}, delta_y={delta_y}")
            return
        
        try:
            await self._page.mouse.wheel(delta_x, delta_y)
        except Exception as e:
            print(f"Error in mouse_wheel: {e}")
    
    async def keyboard_press(self, key: str):
        """Press a key."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Key pressed: {key}")
            return
        
        try:
            await self._page.keyboard.press(key)
        except Exception as e:
            print(f"Error in keyboard_press: {e}")
    
    async def keyboard_type(self, text: str):
        """Type text."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Typed text: {text}")
            return
        
        try:
            await self._page.keyboard.type(text)
        except Exception as e:
            print(f"Error in keyboard_type: {e}")
    
    async def navigate_to(self, url: str):
        """Navigate to URL."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Navigating to {url}")
            return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        await self._page.goto(url)
    
    async def go_back(self):
        """Go back in browser history."""
        if not self._page:
            await self.initialize()
        
        await self._page.go_back()
    
    async def go_forward(self):
        """Go forward in browser history."""
        if not self._page:
            await self.initialize()
        
        await self._page.go_forward()
    
    async def refresh(self):
        """Refresh the page."""
        if not self._page:
            await self.initialize()
        
        await self._page.reload()
    
    def get_viewport_size(self) -> list:
        """Get current viewport size."""
        return list(self._viewport_size)
    
    def get_pages_info(self) -> list:
        """Get information about all open pages."""
        print(f"get_pages_info called, tracking {len(self._pages)} pages")
        pages_info = []
        for i, page in enumerate(self._pages):
            if page == "mock":
                pages_info.append({
                    "index": i,
                    "url": "mock://page",
                    "title": "Mock Page",
                    "active": i == self._active_page_index
                })
            else:
                try:
                    # Get URL and title safely
                    url = getattr(page, 'url', 'unknown://page')
                    title = "Unknown Page"
                    try:
                        # Try to get title synchronously if possible
                        if hasattr(page, '_title'):
                            title = page._title
                        elif hasattr(page, 'url'):
                            # Extract title from URL or use a default
                            if 'google' in url.lower():
                                title = "Google"
                            elif 'scrapingbee' in url.lower():
                                title = "ScrapingBee"
                            else:
                                title = "Browser Tab"
                    except:
                        title = "Browser Tab"
                    
                    pages_info.append({
                        "index": i,
                        "url": url,
                        "title": title,
                        "active": i == self._active_page_index
                    })
                except Exception as e:
                    print(f"Error getting page info for page {i}: {e}")
                    pages_info.append({
                        "index": i,
                        "url": "unknown://page",
                        "title": "Unknown Page",
                        "active": i == self._active_page_index
                    })
        return pages_info
    
    async def switch_to_page(self, page_index: int) -> bool:
        """Switch to a specific page by index."""
        if 0 <= page_index < len(self._pages):
            self._active_page_index = page_index
            self._page = self._pages[page_index]
            print(f"Switched to page {page_index}: {self._page.url if hasattr(self._page, 'url') else 'mock'}")
            return True
        return False
    
    async def close_page(self, page_index: int) -> bool:
        """Close a specific page by index."""
        if 0 <= page_index < len(self._pages) and len(self._pages) > 1:
            page_to_close = self._pages[page_index]
            if page_to_close != "mock":
                await page_to_close.close()
            self._pages.pop(page_index)
            
            # Adjust active page index if needed
            if self._active_page_index >= len(self._pages):
                self._active_page_index = len(self._pages) - 1
                self._page = self._pages[self._active_page_index]
            
            print(f"Closed page {page_index}. Active page: {self._active_page_index}")
            return True
        return False
    
    async def add_new_tab(self) -> bool:
        """Add a new tab to the browser."""
        try:
            if self._context and self._context != "mock":
                new_page = await self._context.new_page()
                await new_page.goto("about:blank")
                self._pages.append(new_page)
                self._active_page_index = len(self._pages) - 1
                self._page = new_page
                print(f"Added new tab. Total pages: {len(self._pages)}")
                return True
            else:
                print("Cannot add new tab in mock mode")
                return False
        except Exception as e:
            print(f"Error adding new tab: {e}")
            return False
    
    async def close(self):
        """Close the browser."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None


# Global instance
browser_manager = BrowserManager()
