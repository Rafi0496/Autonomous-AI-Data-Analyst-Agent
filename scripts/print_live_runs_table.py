import glob
import json

runs = []
for p in sorted(glob.glob('data/eval/runs/run_[BC]_*.json')):
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
        runs.append((p, d))

print("| Run File | System | Type | Seed | Provider / Model | Rounds | Tools Called Count | Tools Called | Tokens Consumed | Latency (s) |")
print("|---|---|---|---|---|---|---|---|---|---|")
for path, r in runs:
    ds = r.get('dataset', '')
    sys_id = r.get('system', '')
    is_null = "Null" if r.get('is_null') else "Planted"
    seed = r.get('seed', '')
    model = f"{r.get('provider')}:{r.get('model')}"
    rounds = r.get('rounds') if r.get('rounds') is not None else 1
    tools_list = r.get('tools_called', [])
    tools_count = len(tools_list)
    tools_str = ", ".join(tools_list) if tools_list else "None"
    tokens = r.get('tokens_consumed', 0)
    tokens_str = f"{tokens:,}" if isinstance(tokens, int) else str(tokens)
    lat = r.get('wall_time_seconds', r.get('latency_seconds', 0.0))
    print(f"| `{path}` | System {sys_id} | {is_null} | {seed} | {model} | {rounds} | {tools_count} | `{tools_str}` | {tokens_str} | {lat:.2f}s |")
