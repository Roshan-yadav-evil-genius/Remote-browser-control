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
    _creating_tab = False  # Flag to prevent duplicate tab creation
    
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
        
        # Check if this page already exists (same URL)
        existing_page = None
        for i, existing in enumerate(self._pages):
            if existing != "mock" and hasattr(existing, 'url') and existing.url == page.url:
                existing_page = i
                break
        
        if existing_page is not None:
            print(f"Page with URL {page.url} already exists, switching to it instead of creating duplicate")
            self._active_page_index = existing_page
            self._page = self._pages[existing_page]
        else:
            self._pages.append(page)
            # Automatically switch to the new page for OAuth flows
            self._active_page_index = len(self._pages) - 1
            self._page = page
            
            # Auto-focus popup windows immediately when they appear
            if page != "mock":
                try:
                    # Use asyncio.create_task to avoid blocking the event handler
                    import asyncio
                    asyncio.create_task(self._ensure_page_focused(page))
                    print(f"Auto-focusing new popup page: {page.url}")
                except Exception as e:
                    print(f"Warning: Could not auto-focus popup: {e}")
            
            print(f"Added new page. Total pages: {len(self._pages)}")
        
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
            
            # Update viewport size with actual page dimensions
            actual_dimensions = await self.get_actual_page_dimensions()
            if actual_dimensions != self._viewport_size:
                print(f"Page dimensions changed from {self._viewport_size} to {actual_dimensions}")
                self._viewport_size = actual_dimensions
            
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
        """Move mouse to coordinates with focus verification."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse moved to ({x}, {y})")
            return
        
        try:
            # Ensure page is focused before mouse movement
            await self._ensure_page_focused(self._page)
            await self._page.mouse.move(x, y)
        except Exception as e:
            print(f"Error in mouse_move: {e}")
    
    async def mouse_click(self, x: int, y: int, button: str = "left"):
        """Click at coordinates with focus verification and retry logic."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse clicked at ({x}, {y}) with {button} button")
            return
        
        try:
            # First attempt - try to click directly
            await self._page.mouse.click(x, y, button=button)
            print(f"Successfully clicked at ({x}, {y}) with {button} button")
        except Exception as e:
            print(f"First click attempt failed: {e}, retrying with focus...")
            try:
                # Retry with focus verification
                await self._ensure_page_focused(self._page)
                await self._page.mouse.click(x, y, button=button)
                print(f"Retry successful: clicked at ({x}, {y}) with {button} button")
            except Exception as retry_e:
                print(f"Retry also failed: {retry_e}")
    
    async def mouse_down(self, x: int, y: int, button: str = "left"):
        """Mouse down at coordinates with focus verification."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse down at ({x}, {y}) with {button} button")
            return
        
        try:
            # Ensure page is focused before mouse interaction
            await self._ensure_page_focused(self._page)
            await self._page.mouse.move(x, y)
            await self._page.mouse.down(button=button)
        except Exception as e:
            print(f"Error in mouse_down: {e}")
    
    async def mouse_up(self, x: int, y: int, button: str = "left"):
        """Mouse up at coordinates with focus verification."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse up at ({x}, {y}) with {button} button")
            return
        
        try:
            # Ensure page is focused before mouse interaction
            await self._ensure_page_focused(self._page)
            await self._page.mouse.move(x, y)
            await self._page.mouse.up(button=button)
        except Exception as e:
            print(f"Error in mouse_up: {e}")
    
    async def mouse_wheel(self, delta_x: int, delta_y: int):
        """Scroll with mouse wheel with focus verification."""
        if not self._page:
            await self.initialize()
        
        if self._page == "mock":
            print(f"Mock: Mouse wheel delta_x={delta_x}, delta_y={delta_y}")
            return
        
        try:
            # Ensure page is focused before scrolling
            await self._ensure_page_focused(self._page)
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
    
    async def get_actual_page_dimensions(self) -> tuple:
        """Get the actual dimensions of the current page."""
        if not self._page or self._page == "mock":
            return self._viewport_size
        
        try:
            # Get the actual viewport size of the current page
            # viewport_size is a property, not a method
            viewport_size = self._page.viewport_size
            if viewport_size:
                return (viewport_size['width'], viewport_size['height'])
            else:
                return self._viewport_size
        except Exception as e:
            print(f"Error getting page dimensions: {e}")
            return self._viewport_size
    
    def get_viewport_size(self) -> list:
        """Get current viewport size - returns actual page dimensions if available."""
        # For synchronous access, return the stored viewport size
        # The actual dimensions will be updated in get_screenshot()
        return list(self._viewport_size)
    
    def get_pages_info(self) -> list:
        """Get information about all open pages."""
        print(f"get_pages_info called, tracking {len(self._pages)} pages")
        
        # Clean up duplicate pages first
        self.cleanup_duplicate_pages()
        
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
                            if 'google.com' in url.lower():
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
        
        print(f"Returning {len(pages_info)} unique pages")
        return pages_info
    
    async def _ensure_page_focused(self, page, timeout: int = 5000) -> bool:
        """Ensure a page is focused and ready for interaction."""
        if page == "mock":
            return True
        
        try:
            # Bring page to front to ensure it has focus
            await page.bring_to_front()
            print(f"Brought page to front: {page.url if hasattr(page, 'url') else 'unknown'}")
            
            # Wait for page to be in an interactive state
            await page.wait_for_load_state('domcontentloaded', timeout=timeout)
            print(f"Page is ready for interaction: {page.url if hasattr(page, 'url') else 'unknown'}")
            return True
        except Exception as e:
            print(f"Warning: Could not focus page: {e}")
            return False
    
    async def switch_to_page(self, page_index: int) -> bool:
        """Switch to a specific page by index."""
        if 0 <= page_index < len(self._pages):
            self._active_page_index = page_index
            self._page = self._pages[page_index]
            
            # Ensure the page is properly focused, especially for popup windows
            focus_success = await self._ensure_page_focused(self._page)
            
            print(f"Switched to page {page_index}: {self._page.url if hasattr(self._page, 'url') else 'mock'} (focus: {'success' if focus_success else 'failed'})")
            return focus_success
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
    
    def cleanup_duplicate_pages(self):
        """Remove duplicate pages based on URL."""
        if not self._pages:
            return
        
        seen_urls = set()
        unique_pages = []
        
        for page in self._pages:
            if page == "mock":
                unique_pages.append(page)
            else:
                try:
                    url = getattr(page, 'url', 'unknown://page')
                    if url not in seen_urls:
                        seen_urls.add(url)
                        unique_pages.append(page)
                    else:
                        print(f"Removing duplicate page with URL: {url}")
                except:
                    unique_pages.append(page)
        
        if len(unique_pages) != len(self._pages):
            print(f"Cleaned up {len(self._pages) - len(unique_pages)} duplicate pages")
            self._pages = unique_pages
            # Adjust active page index if needed
            if self._active_page_index >= len(self._pages):
                self._active_page_index = max(0, len(self._pages) - 1)
                if self._pages:
                    self._page = self._pages[self._active_page_index]
    
    async def add_new_tab(self) -> bool:
        """Add a new tab to the browser."""
        try:
            if self._context and self._context != "mock":
                # Prevent multiple simultaneous tab creation
                if self._creating_tab:
                    print("Tab creation already in progress, ignoring duplicate request")
                    return False
                
                self._creating_tab = True
                
                # Check if we already have a Google tab to avoid duplicates
                google_tabs = [page for page in self._pages if hasattr(page, 'url') and 'google.com' in page.url]
                if google_tabs:
                    print(f"Google tab already exists, switching to it. Total pages: {len(self._pages)}")
                    self._active_page_index = self._pages.index(google_tabs[0])
                    self._page = google_tabs[0]
                    self._creating_tab = False
                    return True
                
                print(f"Creating new Google tab. Current pages: {len(self._pages)}")
                new_page = await self._context.new_page()
                await new_page.goto("https://www.google.com")
                self._pages.append(new_page)
                self._active_page_index = len(self._pages) - 1
                self._page = new_page
                print(f"Added new tab with Google.com. Total pages: {len(self._pages)}")
                self._creating_tab = False
                return True
            else:
                print("Cannot add new tab in mock mode")
                return False
        except Exception as e:
            print(f"Error adding new tab: {e}")
            self._creating_tab = False
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
