"""The purchase workflow as a LangGraph graph, with the supervisor deciding the route.

    START -> plan --(ok)--> life_operations --\\
               |         -> consumer_buyer  ---> check_research --(ok)--> procurement --(ok)--> financial --(ok)--> verify -> END
               |                                      |                     |                    |
               +--(needs input / failed)--------------+---------------------+--(failed)-> recover <--(failed)
                                                                                         |
                                                     buyer_deep <--(deeper_search)-------+--(fit_remaining)--> procurement

Supervisor decisions (all deterministic, all recorded as agent runs):
- Skip the remaining agents when planning or research failed or needs the user.
- Recover from a cart that won't fit (deeper search) or a saved budget already partly used
  (rebuild for what's left). At most MAX_RECOVERIES attempts, never the same strategy twice.
- Retry an agent once if it crashed (not if it reported a failure: that's a real answer).
- Stop routing to agents once the time limit is used up, and cap total steps (recursion_limit).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session, sessionmaker

from app.agents import consumer_buyer, financial, life_operations, procurement, supervisor
from app.models import AgentRun, Objective, User, Workflow
from app.orchestration.state import PersonalIQState
from app.schemas.agents import AgentResult, AgentTask
from app.schemas.personal import UserContext
from app.services.personal_intelligence import build_user_context

AgentFn = Callable[[AgentTask, Session, UserContext], AgentResult]
MAX_ATTEMPTS = 2  # an agent that crashes gets one retry
TIME_LIMIT = timedelta(seconds=180)  # after this, no more agent steps: verify with what we have
STEP_LIMIT = 30  # LangGraph recursion_limit: a hard cap on node executions


@dataclass
class Deps:
    session_factory: sessionmaker
    workflow_id: uuid.UUID
    user_id: uuid.UUID


def _now() -> datetime:
    return datetime.now(timezone.utc)


def execute(deps: Deps, key: str, agent_name: str, fn: AgentFn, context: dict, constraints: dict, objective: str) -> dict:
    """Run one agent with its own session, recording start and finish as an AgentRun.
    A crash is retried once; a reported failure is a real result and isn't."""
    with deps.session_factory() as s:
        task = AgentTask(
            workflow_id=deps.workflow_id, user_id=deps.user_id, agent_name=agent_name,
            objective=objective, context=context, constraints=constraints,
        )
        run = AgentRun(workflow_id=deps.workflow_id, agent_name=key, status="running", input={"constraints": constraints})
        s.add(run)
        s.commit()
        crashes = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                ctx = build_user_context(s, s.get(User, deps.user_id))
                result = fn(task, s, ctx)
                break
            except Exception as e:  # an agent bug becomes a failed step, never a crashed workflow
                s.rollback()
                crashes.append(f"{type(e).__name__}: {e}")
                result = AgentResult(task_id=task.task_id, status="failed", explanation="This step failed unexpectedly.", errors=crashes[-1:])
        run = s.get(AgentRun, run.id)
        run.status = result.status
        run.output = {**result.model_dump(mode="json"), "attempts": attempt, "crashes": crashes}
        run.explanation = result.explanation + (f" (Succeeded on retry {attempt}.)" if crashes and result.status != "failed" else "")
        run.finished_at = _now()
        s.commit()
    return result.model_dump(mode="json")


def _deps(config) -> Deps:
    return config["configurable"]["deps"]


def _objective(state: PersonalIQState) -> str:
    return state["intent"]["objective"]


def _time_up(state: PersonalIQState) -> bool:
    started = state.get("started_at")
    return bool(started) and _now() - datetime.fromisoformat(started) > TIME_LIMIT


def _done(state: PersonalIQState, key: str) -> bool:
    return state.get("runs", {}).get(key, {}).get("status") == "completed"


# ---------- agent nodes ----------


def node_plan(state: PersonalIQState, config) -> dict:
    out = execute(_deps(config), "supervisor_plan", "supervisor", supervisor.plan, {"intent": state["intent"]}, {}, _objective(state))
    return {"runs": {"supervisor_plan": out}}


def node_life(state: PersonalIQState, config) -> dict:
    out = execute(_deps(config), "life_operations", "life_operations", life_operations.run, {"intent": state["intent"]}, {}, _objective(state))
    return {"runs": {"life_operations": out}}


def node_buyer(state: PersonalIQState, config) -> dict:
    out = execute(_deps(config), "consumer_buyer", "consumer_buyer", consumer_buyer.run, {"intent": state["intent"]}, {}, _objective(state))
    return {"runs": {"consumer_buyer": out}}


def node_buyer_deep(state: PersonalIQState, config) -> dict:
    depth = (state.get("recovery") or {}).get("depth")
    out = execute(_deps(config), "consumer_buyer", "consumer_buyer", consumer_buyer.run, {"intent": state["intent"]}, {"depth": depth}, _objective(state))
    return {"runs": {"consumer_buyer": out}}


def node_check_research(state: PersonalIQState, config) -> dict:
    return {}  # a join point; the supervisor's decision is in route_after_research


def _plan_constraints(state: PersonalIQState) -> dict:
    plan = state["runs"].get("supervisor_plan", {})
    if plan.get("status") != "completed":
        return {}
    budget = (state.get("recovery") or {}).get("budget") or plan["result"]["budget"]  # a recovery may tighten it
    return {"budget": budget, "budget_name": plan["result"]["budget_name"]}


def node_procurement(state: PersonalIQState, config) -> dict:
    runs = state["runs"]
    constraints = _plan_constraints(state)
    life = runs.get("life_operations", {})
    needs = life["result"].get("needs", []) if life.get("status") == "completed" and constraints else []
    context = {"needs": needs, "candidates": runs.get("consumer_buyer", {}).get("result", {}).get("candidates", {})}
    out = execute(_deps(config), "procurement", "procurement", procurement.run, context, constraints, _objective(state))
    return {"runs": {"procurement": out}}


def node_financial(state: PersonalIQState, config) -> dict:
    proc = state["runs"].get("procurement", {})
    context = {"cart": proc.get("result", {}).get("cart")} if proc.get("status") == "completed" else {}
    out = execute(_deps(config), "financial", "financial", financial.run, context, _plan_constraints(state), _objective(state))
    return {"runs": {"financial": out}}


def node_recover(state: PersonalIQState, config) -> dict:
    """The supervisor picks a recovery strategy from the failed results and records why."""
    deps = _deps(config)
    with deps.session_factory() as s:
        currency = s.get(User, deps.user_id).currency
        decision = supervisor.decide_recovery(state["runs"], state.get("recovery") or {}, currency)
        started = _now()
        s.add(AgentRun(
            workflow_id=deps.workflow_id, agent_name="supervisor_recover", status="completed", input={"tried": (state.get("recovery") or {}).get("tried", [])},
            output={"decision": decision}, explanation=decision["reason"], started_at=started, finished_at=_now(),
        ))
        s.commit()
    previous = state.get("recovery") or {}
    recovery = {**previous, "tried": [*previous.get("tried", []), decision["strategy"]], "last": decision["strategy"]}
    for k in ("budget", "depth"):
        if k in decision:
            recovery[k] = decision[k]
    # The failed results are about to be replaced; mark them so verify never reads a stale failure.
    stale = {"status": "superseded", "result": {}, "explanation": "Replaced after the supervisor's recovery."}
    return {"recovery": recovery, "runs": {"financial": stale, "procurement": stale}}


def node_verify(state: PersonalIQState, config) -> dict:
    deps = _deps(config)
    with deps.session_factory() as s:
        run = AgentRun(workflow_id=deps.workflow_id, agent_name="supervisor_verify", status="running", input={})
        s.add(run)
        s.commit()
        user = s.get(User, deps.user_id)
        wf = s.get(Workflow, deps.workflow_id)
        wf.state = {**wf.state, "runs": state["runs"], "recovery": state.get("recovery") or {}}  # the approval's risk check reads these
        s.flush()
        outcome = supervisor.verify(s, build_user_context(s, user), deps.workflow_id, wf.objective_id, state)

        run = s.get(AgentRun, run.id)
        run.status = "completed"
        run.explanation = outcome["message"]
        run.output = {"status": outcome["status"], "result": {k: v for k, v in outcome["result"].items() if k != "cart"}}
        run.finished_at = _now()

        wf.status = outcome["status"]
        wf.state = {**wf.state, "runs": state["runs"], "recovery": state.get("recovery") or {}, "outcome": outcome}
        if wf.objective_id:
            obj = s.get(Objective, wf.objective_id)
            obj.status = outcome["status"]
        s.commit()
    return {"outcome": outcome}


# ---------- supervisor routing ----------


def route_after_plan(state: PersonalIQState):
    if not _done(state, "supervisor_plan") or _time_up(state):
        return "verify"
    return ["life_operations", "consumer_buyer"]  # in parallel


def route_after_research(state: PersonalIQState) -> str:
    if _done(state, "life_operations") and _done(state, "consumer_buyer") and not _time_up(state):
        return "procurement"
    return "verify"  # needs input, failed, or out of time: nothing more to do


def _recover_or_verify(state: PersonalIQState) -> str:
    if _time_up(state):
        return "verify"
    decision = supervisor.decide_recovery(state["runs"], state.get("recovery") or {}, state["intent"].get("currency", ""))
    return "recover" if decision else "verify"


def route_after_cart(state: PersonalIQState) -> str:
    if _done(state, "procurement"):
        return "verify" if _time_up(state) else "financial"
    return _recover_or_verify(state)


def route_after_finance(state: PersonalIQState) -> str:
    return "verify" if _done(state, "financial") else _recover_or_verify(state)


def route_after_recover(state: PersonalIQState) -> str:
    return "buyer_deep" if (state.get("recovery") or {}).get("last") == "deeper_search" else "procurement"


def build_graph():
    g = StateGraph(PersonalIQState)
    for name, fn in [
        ("plan", node_plan), ("life_operations", node_life), ("consumer_buyer", node_buyer), ("check_research", node_check_research),
        ("procurement", node_procurement), ("financial", node_financial), ("recover", node_recover), ("buyer_deep", node_buyer_deep),
        ("verify", node_verify),
    ]:
        g.add_node(name, fn)

    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", route_after_plan, ["life_operations", "consumer_buyer", "verify"])
    g.add_edge(["life_operations", "consumer_buyer"], "check_research")  # join: waits for both
    g.add_conditional_edges("check_research", route_after_research, ["procurement", "verify"])
    g.add_conditional_edges("procurement", route_after_cart, ["financial", "recover", "verify"])
    g.add_conditional_edges("financial", route_after_finance, ["recover", "verify"])
    g.add_conditional_edges("recover", route_after_recover, ["buyer_deep", "procurement"])
    g.add_edge("buyer_deep", "procurement")
    g.add_edge("verify", END)
    return g.compile()


GRAPH = build_graph()
