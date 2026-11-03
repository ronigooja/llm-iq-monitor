import pytest

from llm_iq_monitor.judge import judge_reply


@pytest.mark.asyncio
async def test_judge_brief_guidance_differs_for_marketing_and_nonmarketing():
    prompts = []

    class Gateway:
        async def chat(self, model, messages, **kwargs):
            prompts.append(messages[0]["content"])
            return type("Result", (), {"reply": '{"fit": 4, "fluency": 4, "persuasion": 4}', "error": None,
                                        "in_tok": 1, "out_tok": 1, "latency_s": 0.1})()

    gateway = Gateway()
    await judge_reply(gateway, "judge", "low", {"task": "social post", "marketing": True, "product": "x", "audience": "y", "tone": "z"}, "reply", "en", max_tokens=10, timeout=1)
    await judge_reply(gateway, "judge", "low", {"task": "notice", "marketing": False, "subject": "x", "audience": "y", "tone": "z"}, "reply", "en", max_tokens=10, timeout=1)
    assert "This is marketing copy" in prompts[0]
    assert "This is not marketing" in prompts[1]
    assert prompts[0] != prompts[1]
