from __future__ import annotations

import logging
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    PROJECT_ROOT = BASE_DIR
else:
    BASE_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = BASE_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LOG_FILE = BASE_DIR / "astock_workbench.log"

logger = logging.getLogger("AStockWorkbench")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

shutdown_event = threading.Event()
server = None


def find_free_port(start: int = 8770, attempts: int = 80) -> int:
    for port in range(start, start + attempts):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            sock.close()
    raise RuntimeError("无法找到可用端口")


def start_server(port: int) -> None:
    global server
    try:
        import uvicorn
        from market_app.server import app

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_config=None,
            access_log=False,
            workers=1,
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception:
        logger.exception("本地服务异常")
        shutdown_event.set()


def wait_until_ready(port: int, timeout: int = 25) -> bool:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if shutdown_event.is_set():
            return False
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except (OSError, URLError):
            pass
        time.sleep(0.25)
    return False


def open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        logger.exception("系统浏览器打开失败: %s", url)


def main() -> int:
    logger.info("=" * 64)
    logger.info("A股趋势工作台启动")
    logger.info("程序目录: %s", BASE_DIR)

    thread = None
    try:
        port = find_free_port()
        url = f"http://127.0.0.1:{port}"
        logger.info("本地服务端口: %s", port)

        thread = threading.Thread(target=start_server, args=(port,), daemon=True, name="uvicorn")
        thread.start()
        if not wait_until_ready(port):
            logger.error("服务启动超时")
            return 1

        logger.info("服务就绪: %s", url)
        try:
            import webview

            window = webview.create_window(
                title="A股趋势工作台",
                url=url,
                width=1480,
                height=940,
                min_size=(1120, 720),
                resizable=True,
                confirm_close=False,
            )

            def on_closed() -> None:
                shutdown_event.set()
                if server is not None:
                    server.should_exit = True

            window.events.closed += on_closed
            webview.start(debug=False, http_server=False)
        except ImportError:
            logger.warning("未安装 pywebview，改用系统浏览器")
            open_browser(url)
            while thread.is_alive() and not shutdown_event.is_set():
                time.sleep(0.5)
        except Exception:
            logger.exception("桌面窗口异常，改用系统浏览器")
            open_browser(url)
            while thread.is_alive() and not shutdown_event.is_set():
                time.sleep(0.5)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        logger.error("启动失败:\n%s", traceback.format_exc())
        return 1
    finally:
        shutdown_event.set()
        if server is not None:
            server.should_exit = True
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        logger.info("A股趋势工作台已退出")


if __name__ == "__main__":
    raise SystemExit(main())
