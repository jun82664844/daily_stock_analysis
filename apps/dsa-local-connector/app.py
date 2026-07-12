from __future__ import annotations

import threading
import tkinter as tk
import webbrowser

from runtime import ConnectorRuntime


class ConnectorWindow:
    STATES = {
        "disconnected": "未连接：请在网页获取配对码",
        "connecting": "正在连接 DSA",
        "connected": "已连接：发现 {count} 个 Ollama 模型",
        "ollama_unavailable": "Ollama 未启动或没有模型",
        "connection_failed": "连接失败，请确认配对码和本地服务",
    }

    def __init__(self) -> None:
        self.runtime = ConnectorRuntime()
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self.root = tk.Tk()
        self.root.title("DSA Local Connector")
        self.root.geometry("480x230")
        self.status = tk.StringVar(value=self.STATES["disconnected"])
        tk.Label(self.root, textvariable=self.status, padx=18, pady=18).pack()

        pairing_row = tk.Frame(self.root)
        pairing_row.pack(pady=4)
        tk.Label(pairing_row, text="配对码").pack(side="left", padx=4)
        self.pairing_code = tk.Entry(pairing_row, width=12)
        self.pairing_code.pack(side="left", padx=4)
        tk.Button(pairing_row, text="连接", command=self._pair).pack(side="left", padx=4)

        buttons = tk.Frame(self.root)
        buttons.pack(pady=12)
        tk.Button(
            buttons,
            text="打开 DSA 账户页",
            command=lambda: webbrowser.open(f"{self.runtime.base_url}/account"),
        ).pack(side="left", padx=4)
        tk.Button(buttons, text="重新连接", command=self._start_worker).pack(side="left", padx=4)
        tk.Button(buttons, text="退出", command=self._close).pack(side="left", padx=4)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        try:
            if self.runtime.restore():
                self._start_worker()
        except Exception:
            self.status.set(self.STATES["connection_failed"])

    def _pair(self) -> None:
        code = self.pairing_code.get().strip()
        if len(code) != 6 or not code.isdigit():
            self.status.set(self.STATES["connection_failed"])
            return
        self.status.set(self.STATES["connecting"])

        def pair_and_start() -> None:
            try:
                self.runtime.pair(code)
            except Exception:
                self.root.after(0, lambda: self.status.set(self.STATES["connection_failed"]))
                return
            self.root.after(0, self._start_worker)

        threading.Thread(target=pair_and_start, daemon=True).start()

    def _start_worker(self) -> None:
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return
        self.status.set(self.STATES["connecting"])

        def loop() -> None:
            attempt = 0
            while not self.stop_event.is_set():
                try:
                    state = self.runtime.process_once()
                    attempt = 0
                    if state["status"] == "connected":
                        text = self.STATES["connected"].format(count=state["model_count"])
                    else:
                        text = self.STATES[state["status"]]
                    self.root.after(0, lambda value=text: self.status.set(value))
                    if state["status"] == "ollama_unavailable":
                        self.stop_event.wait(2.0)
                except Exception:
                    self.root.after(0, lambda: self.status.set(self.STATES["connection_failed"]))
                    from client import ConnectorClient

                    ConnectorClient.sleep_for_attempt(attempt)
                    attempt += 1

        self.worker_thread = threading.Thread(target=loop, daemon=True)
        self.worker_thread.start()

    def _close(self) -> None:
        self.stop_event.set()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    ConnectorWindow().run()
