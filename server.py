"""
Mem0 Dashboard 后端 API 服务 — 启动入口（向后兼容）

实际代码已拆分到 server/ 包中。
此文件仅作为 `python server.py` 的启动入口保留。
注意：`import server` 会导入 server/ 包，而非此文件。
"""

if __name__ == "__main__":
    from server.main import main
    main()
