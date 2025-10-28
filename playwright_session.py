import threading
import time
from playwright.sync_api import sync_playwright

class PlaywrightSessionManager:
    _playwright = None
    _browser = None
    _context = None
    _page = None
    _last_used = time.time()
    _monitor_thread = None
    _inactivity_limit = 900  # seconds (15 minutes)

    @classmethod
    def start(cls):
        if cls._playwright is None:
            print("🟢 Starting new Playwright session...")
            cls._playwright = sync_playwright().start()
            cls._browser = cls._playwright.firefox.launch(headless=True)
            cls._context = cls._browser.new_context()
            cls._context.set_default_timeout(15000)

            # To block resources in a selective way to make execution "a little bit" lightweight (and try to not break Cloudflare)
            cls._context.route("**/*", lambda route, request: cls._handle_route(route, request))

            cls._page = cls._context.new_page()
            cls._start_monitor()
        else:
            print("🔄 Reusing Playwright existing session.")
        cls._last_used = time.time()
        return cls._page

    @classmethod
    def _handle_route(cls, route, request):
        url = request.url
        tipo = request.resource_type
        if tipo in ["image", "stylesheet", "font"] or "google-analytics" in url or "doubleclick" in url:
            route.abort()
        else:
            route.continue_()

    @classmethod
    def get_page(cls, new=False):
        if not cls.is_active():
            cls.start()
        cls._last_used = time.time()
        if new:
            print("🆕 Creating new page in current context.")
            return cls._context.new_page()
        else:
            print("🔄 Reusing main page.")
            return cls._page

    @classmethod
    def _start_monitor(cls):
        if cls._monitor_thread is None:
            def monitor():
                while True:
                    time.sleep(60)
                    if cls._playwright and time.time() - cls._last_used > cls._inactivity_limit:
                        print("⏳ Inactivity detected. Closing Playwright existing session...")
                        cls.close()
                        break
            cls._monitor_thread = threading.Thread(target=monitor, daemon=True)
            cls._monitor_thread.start()

    @classmethod
    def is_active(cls):
        # return cls._playwright is not None
        return cls._playwright is not None and cls._browser is not None and cls._context is not None

    @classmethod
    def close(cls):
        try:
            if cls._context:
                cls._context.close()
        except Exception as e:
            print("⚠️ Error while closing context")
        try:
            if cls._browser:
                cls._browser.close()
        except Exception as e:
            print("⚠️ Error while closing browser")
        try:
            if cls._playwright:
                cls._playwright.stop()
        except Exception as e:
            print("⚠️ Error while closing Playwright")

        cls._playwright = cls._browser = cls._context = cls._page = None
        cls._monitor_thread = None
        print("🔴 Playwright session closed.")