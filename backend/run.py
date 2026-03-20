import os
import sys
import uvicorn


def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from backend.app import load_config
    config = load_config()

    port = int(config.get("service_port", 5000))
    host = config.get("host", "0.0.0.0")

    uvicorn.run("backend.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
