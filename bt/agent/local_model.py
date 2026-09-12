"""Run the agent's model locally (e.g. on a free Kaggle GPU) instead of through a hosted API.

Responses come back in the same shape as the OpenAI-compatible router, so the
agent loop, the tools and the guardrails are exactly the same code. Greedy
decoding: the same prompt gives the same memo.
"""
from __future__ import annotations

import json
import re

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
THINK = re.compile(r"<think>.*?</think>", re.S)
SPECIAL = re.compile(r"<\|[^|<>]+\|>")


class LocalChat:
    def __init__(self, name: str, max_new_tokens: int = 900):
        self.name = name
        self.tok = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float16, device_map="auto")
        self.max_new = max_new_tokens
        self.n = 0

    @staticmethod
    def _prep(messages: list[dict]) -> list[dict]:
        """Chat templates want tool-call arguments as objects, not JSON strings."""
        out = []
        for m in messages:
            m = dict(m)
            if m.get("tool_calls"):
                m["tool_calls"] = [{"type": "function", "function": {
                    "name": c["function"]["name"],
                    "arguments": json.loads(c["function"]["arguments"] or "{}")
                    if isinstance(c["function"]["arguments"], str) else c["function"]["arguments"]}}
                    for c in m["tool_calls"]]
            out.append(m)
        return out

    def __call__(self, model: str, messages: list[dict], tools: list[dict] | None) -> dict:
        extra = {"enable_thinking": False} if "qwen3" in self.name.lower() else {}
        prompt = self.tok.apply_chat_template(self._prep(messages), tools=tools, add_generation_prompt=True,
                                              tokenize=False, **extra)
        ids = self.tok(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            gen = self.model.generate(**ids, max_new_tokens=self.max_new, do_sample=False, temperature=None,
                                      top_p=None, top_k=None, pad_token_id=self.tok.eos_token_id)
        new = gen[0][ids["input_ids"].shape[1]:]
        text = SPECIAL.sub("", THINK.sub("", self.tok.decode(new, skip_special_tokens=False))).strip()
        calls = []
        for raw in TOOL_CALL.findall(text):
            try:
                c = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self.n += 1
            calls.append({"id": f"call_{self.n}", "type": "function",
                          "function": {"name": c.get("name"), "arguments": json.dumps(c.get("arguments") or {})}})
        return {"choices": [{"message": {"role": "assistant", "content": TOOL_CALL.sub("", text).strip(),
                                         "tool_calls": calls or None}}],
                "usage": {"total_tokens": int(ids["input_ids"].shape[1] + len(new))}}
