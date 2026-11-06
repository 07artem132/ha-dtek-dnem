"""automations.yaml → automations.json (YAML-якорі розгортаються; deploy.ps1 шле JSON у HA REST)."""
import json, pathlib, yaml

here = pathlib.Path(__file__).parent
data = yaml.safe_load((here / "automations.yaml").read_text(encoding="utf-8"))
(here / "automations.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print("ok:", ", ".join(a["id"] for a in data))
