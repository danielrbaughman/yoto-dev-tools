"""Small system adapters: wall clock and browser."""

import time
import webbrowser


class SystemClock:
    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class WebBrowserOpener:
    def open(self, url: str) -> bool:
        try:
            return webbrowser.open(url)
        except webbrowser.Error:
            return False
