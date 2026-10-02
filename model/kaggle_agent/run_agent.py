"""Batch job: the investigator agent on an open model, on a free Kaggle GPU.

RUNS ON KAGGLE. Same agent loop, read-only tools and memo guardrails as
bt.agent.investigate; the only difference is that the model (Qwen3-8B,
Apache-2.0, open weights) runs on this GPU instead of behind a hosted API.

Inputs, found by walking /kaggle/input (private dataset borrower-truth-agent-input):
- code/bt/...            the agent package (agent, tools, GLEIF adapter)
- demo/*.parquet         the synthetic demo book the tools read
- demo/run/cases.json    the rules' verdicts (the agent cannot change them)
Output: /kaggle/working/agent/<borrower>.json + index.json
"""
import glob
import os
import subprocess
import sys
import zipfile

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "duckdb", "rapidfuzz"], check=True)

import torch  # noqa: E402

print("GPUs:", [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])


def find(pattern):
    hits = glob.glob(f"/kaggle/input/**/{pattern}", recursive=True) or glob.glob(f"/kaggle/working/input/**/{pattern}", recursive=True)
    return hits[0] if hits else None


if not find("run/cases.json"):  # dataset folders uploaded as zips: unpack them
    for z in glob.glob("/kaggle/input/**/*.zip", recursive=True):
        zipfile.ZipFile(z).extractall(os.path.join("/kaggle/working/input", os.path.basename(z)[:-4]))

cases = find("run/cases.json")
book = os.path.dirname(os.path.dirname(cases))
code_root = os.path.dirname(os.path.dirname(os.path.dirname(find("bt/agent/investigate.py"))))
print("book:", book, "| code:", code_root)
sys.path.insert(0, code_root)
os.environ["BT_CACHE_DIR"] = "/kaggle/working/gleif_cache"
# Kaggle is not a bank, and this book is synthetic: the model weights download from Hugging Face, and GLEIF answers live
os.environ["BT_OFFLINE"] = "0"

from bt.agent.investigate import main  # noqa: E402

main(["--data", book, "--out", "/kaggle/working/agent", "--backend", "local", "--local-model", "Qwen/Qwen3-8B",
      "--top-review", "8"])
