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


LOG_FILE = BASE_DIR / "aihedgefundos.log"

logger = logging.getLogger("AIHedgeFundOS")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.FileHandler(
        LOG_FILE,
        mode="a",
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)


shutdown_event = threading.Event()
server = None


def find_free_port(start: int = 8765, attempts: int = 100) -> int:
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


def start_server(port: int):
    global server

    try:
        import uvicorn
        from desktop.app import app

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
        logger.exception("Uvicorn 服务线程异常")
        shutdown_event.set()


def wait_until_ready(port: int, timeout: int = 20) -> bool:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if shutdown_event.is_set():
            return False

        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    logger.info("服务健康检查通过: %s", url)
                    return True

        except (OSError, URLError):
            pass

        time.sleep(0.25)

    logger.error("服务启动超时，等待时间: %s 秒", timeout)
    return False


def stop_server():
    shutdown_event.set()

    if server is not None:
        server.should_exit = True
        logger.info("已发送 Uvicorn 优雅退出信号")


def open_browser_fallback(url: str):
    try:
        logger.info("尝试使用系统浏览器打开: %s", url)
        opened = webbrowser.open(url)

        if opened:
            logger.info("系统浏览器已请求打开")
        else:
            logger.warning(
                "系统浏览器未确认打开，请手动访问: %s",
                url,
            )

    except Exception:
        logger.exception("系统浏览器打开失败: %s", url)


def main() -> int:
    logger.info("=" * 60)
    logger.info("AI Hedge Fund OS V3.10 启动")
    logger.info("程序目录: %s", BASE_DIR)
    logger.info("项目目录: %s", PROJECT_ROOT)

    thread = None

    try:
        port = find_free_port(8765)
        url = f"http://127.0.0.1:{port}"

        logger.info("选择本地服务端口: %s", port)

        thread = threading.Thread(
            target=start_server,
            args=(port,),
            name="uvicorn-server",
            daemon=True,
        )
        thread.start()

        if not wait_until_ready(port, timeout=20):
            logger.error("AI Hedge Fund OS 服务启动失败")
            stop_server()
            thread.join(timeout=5)
            return 1

        logger.info("AI Hedge Fund OS 服务启动成功: %s", url)

        try:
            import webview

            logger.info("pywebview 导入成功，准备创建桌面窗口")

            window = webview.create_window(
                title="AI Hedge Fund OS V3.10",
                url=url,
                width=1100,
                height=780,
                min_size=(850, 600),
                resizable=True,
            )

            def on_closed():
                logger.info("桌面窗口关闭")
                stop_server()

            window.events.closed += on_closed

            try:
                webview.start(
                    debug=False,
                    http_server=False,
                )
            except Exception:
                logger.exception("pywebview 窗口运行异常")
                open_browser_fallback(url)

                while thread.is_alive() and not shutdown_event.is_set():
                    time.sleep(0.5)

        except ImportError:
            logger.exception("pywebview 不可用")
            open_browser_fallback(url)

            while thread.is_alive() and not shutdown_event.is_set():
                time.sleep(0.5)

        except Exception:
            logger.exception("pywebview 启动异常")
            open_browser_fallback(url)

            while thread.is_alive() and not shutdown_event.is_set():
                time.sleep(0.5)

        return 0

    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
        return 0

    except Exception:
        logger.error(
            "桌面客户端启动发生致命异常:\n%s",
            traceback.format_exc(),
        )
        return 1

    finally:
        stop_server()

        if thread is not None and thread.is_alive():
            thread.join(timeout=5)

        logger.info("AI Hedge Fund OS V3.10 已退出")


if __name__ == "__main__":
    raise SystemExit(main())