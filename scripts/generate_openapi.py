import ast
import json
import yaml
import sys
from pathlib import Path
from pydantic import BaseModel

# Add parent dir to path so we can import engram
sys.path.insert(0, str(Path(__file__).parent.parent))

from engram.protocol import (
    IngestSynapse, QuerySynapse, ChallengeSynapse, KeyShareSynapse, KeyShareRetrieve
)

def generate():
    miner_path = Path("neurons/miner.py")
    with open(miner_path, "r", encoding="utf-8") as f:
        miner_src = f.read()

    tree = ast.parse(miner_src)
    routes = []
    
    # Simple AST extraction of app.router.add_*
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Attribute):
                if getattr(node.func.value.value, "id", "") == "app" and node.func.value.attr == "router":
                    method = node.func.attr.replace("add_", "").lower()
                    if method in ("get", "post", "put", "delete", "patch"):
                        path = node.args[0].value
                        routes.append((method, path))

    openapi = {
        "openapi": "3.0.3",
        "info": {
            "title": "Engram Miner API",
            "version": "1.0.0",
            "description": "Auto-generated OpenAPI spec for Engram Miner."
        },
        "servers": [{"url": "http://localhost:8091", "description": "Local Miner Node"}],
        "paths": {},
        "components": {
            "schemas": {
                "IngestSynapse": IngestSynapse.model_json_schema(),
                "QuerySynapse": QuerySynapse.model_json_schema(),
                "ChallengeSynapse": ChallengeSynapse.model_json_schema(),
                "KeyShareSynapse": KeyShareSynapse.model_json_schema(),
                "KeyShareRetrieve": KeyShareRetrieve.model_json_schema(),
            }
        }
    }

    synapse_map = {
        "/IngestSynapse": "IngestSynapse",
        "/QuerySynapse": "QuerySynapse",
        "/ChallengeSynapse": "ChallengeSynapse",
        "/KeyShareSynapse": "KeyShareSynapse",
        "/KeyShareRetrieve": "KeyShareRetrieve",
    }

    for method, path in routes:
        if path not in openapi["paths"]:
            openapi["paths"][path] = {}
        
        op = {
            "summary": f"{method.upper()} {path}",
            "responses": {
                "200": {"description": "Success"}
            }
        }
        
        if path in synapse_map and method == "post":
            schema_name = synapse_map[path]
            op["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                    }
                }
            }
            
        openapi["paths"][path][method] = op

    docs_path = Path("docs/openapi.yaml")
    docs_path.parent.mkdir(exist_ok=True)
    with open(docs_path, "w", encoding="utf-8") as f:
        yaml.dump(openapi, f, sort_keys=False)

if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        with open("docs/openapi.yaml", "r") as f:
            old = f.read()
        generate()
        with open("docs/openapi.yaml", "r") as f:
            new = f.read()
        if old != new:
            print("ERROR: docs/openapi.yaml is out of sync. Please run python scripts/generate_openapi.py")
            sys.exit(1)
        else:
            print("docs/openapi.yaml is up to date.")
            sys.exit(0)
    else:
        generate()
        print("Generated docs/openapi.yaml successfully.")
