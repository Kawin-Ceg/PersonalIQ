from decimal import Decimal

from app.services.intent import understand


def test_clear_request_starts_a_workflow(client):
    res = client.post("/api/v1/chat", json={"message": "Set up my new apartment with the essentials"}).json()
    assert res["status"] == "started" and res["workflow_id"]
    wf = client.get(f"/api/v1/workflows/{res['workflow_id']}").json()
    assert wf["status"] == "awaiting_approval"


def test_unclear_request_gets_a_question_then_uses_the_answer(client):
    first = client.post("/api/v1/chat", json={"message": "stuff for my place"}).json()
    assert first["status"] == "clarifying" and first["workflow_id"] is None
    assert first["reply"].endswith("?") and first["suggestions"]

    second = client.post("/api/v1/chat", json={"conversation_id": first["conversation_id"], "message": "an office chair"}).json()
    assert second["status"] == "started"
    assert [n["need"] for n in second["understood"]["needs"]] == ["office_chair"]

    history = client.get(f"/api/v1/chat/{first['conversation_id']}/messages").json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]


class FakeLLM:
    """Returns deliberately bad suggestions: code must keep only what is valid."""

    available = True

    def extract_json(self, instruction, text):
        return {
            "objective": "Kettle",
            "template": "spaceship",
            "needs": [{"need": "hoverboard"}, {"need": "kettle", "required": False}],
            "deadline_days": 9999,
            "budget": 1,  # the LLM must never set the budget
        }


def test_llm_suggestions_are_validated_and_money_comes_from_rules():
    intent = understand("a kettle under ₹3000", "INR", FakeLLM(), known_needs={"kettle", "mattress"})
    assert intent.understood_by == "nemotron"
    assert intent.template is None  # "spaceship" isn't a template
    assert [n.need for n in intent.needs] == ["kettle"]  # "hoverboard" isn't in the catalog
    assert intent.budget == Decimal("3000.00")  # from the text, not the LLM's 1
    assert intent.deadline is None  # 9999 days is out of range
