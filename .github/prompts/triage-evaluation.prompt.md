---
mode: agent
description: Read the latest agent evaluation, find every slip, and fix each one in code with a matching test and check.
---

Read `docs/agent-eval.md` (and `docs/agent-eval.json` for the numbers behind each answer and story).

1. List every failed check, then read every answer and story line by line for slips no check covers yet:
   wrong club, wrong number, wrong minute, a player not named, talk about notes or tools, taking a side,
   a stray English or European Portuguese word.
2. For each slip, decide whether it's real or the check's own mistake.
3. Fix real slips in code, not only in the agents' instructions: a guard in `services/api/lasso_api/main.py`
   (answers) or a backstop in `enrich` (stories), following the guards already there.
4. Add the slip as a case in `services/api/tests/test_guards.py` and, where it's measurable, a check in
   `services/api/tests/agent_eval.py`, so it can't come back unnoticed.
5. Run `python -m pytest -q tests/test_guards.py` from `services/api` and keep the house style in
   `.github/copilot-instructions.md`.
