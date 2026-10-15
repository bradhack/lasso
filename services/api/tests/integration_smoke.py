"""End-to-end smoke test against a running API (python integration_smoke.py [base_url])."""

import asyncio
import json
import sys

import httpx
import websockets
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
MATCH = "S5-MD07-03"


async def main(seconds: float = 40) -> None:
    async with httpx.AsyncClient(base_url=B, timeout=10) as c:
        u = (await c.post("/api/users", json={"name": "Brad", "club_id": "C09"})).json()
        uid = u["id"]
        print("user", uid, u["biscuits"], "level", u["level"])
        neg = (await c.get("/api/negotiate", params={"user_id": uid})).json()
        got: dict[str, int] = {}
        placed = set()
        async with websockets.connect(neg["url"], subprotocols=["json.webpubsub.azure.v1"]) as ws:
            await ws.send(json.dumps({"type": "joinGroup", "group": f"match:{MATCH}", "ackId": 1}))
            loop = asyncio.get_event_loop()
            t0 = loop.time()
            while loop.time() - t0 < seconds:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                except asyncio.TimeoutError:
                    continue
                if msg.get("type") != "message":
                    continue
                d = msg["data"]
                got[d["type"]] = got.get(d["type"], 0) + 1
                if d["type"] in ("moment", "moment_update") and got[d["type"]] <= 5:
                    m = d["moment"]
                    print(d["type"].upper(), m["trigger"], m["minute"], m["headline"]["en"], "|", m["story"]["en"],
                          "|", m.get("source"))
                if d["type"] == "market_open":
                    m = d["market"]
                    print("MARKET", m["question"], [(o["label"], o["p"], o["multiplier"]) for o in m["options"]])
                    if m["market_id"] not in placed:
                        r = await c.post("/api/calls", json={"user_id": uid, "market_id": m["market_id"],
                                                             "option_id": m["options"][0]["id"], "stake": 100,
                                                             "confidence": 0.7})
                        body = r.json()
                        print("  call", r.status_code, body.get("user", {}).get("biscuits"), body.get("detail"))
                        placed.add(m["market_id"])
                if d["type"] == "call_settled":
                    print("SETTLED", d["call"]["status"], d["call"]["payout"], d["user"]["biscuits"],
                          "streak", d["user"]["streak"])
                if d["type"] in ("sticker", "goldfish", "mission_complete"):
                    print(d)
        print(got)
        lb = (await c.get("/api/leaderboard", params={"code": "DIAMOND"})).json()
        print("leaderboard", [(r["name"], r["biscuits"]) for r in lb["rows"]])
        snap = (await c.get(f"/api/matches/{MATCH}")).json()
        print("snapshot", list(snap), "history", len(snap["history"]))
        story = (await c.get(f"/api/matches/{MATCH}/story")).json()
        print("story", len(story), [(m["minute"], m["trigger"], m.get("source")) for m in story])
        r = await c.post(f"/api/matches/{MATCH}/ask", json={"user_id": uid, "question": "Can we still win this?",
                                                            "lang": "en"}, timeout=60)
        a = r.json()
        print("ASK", r.status_code, a.get("source"), a.get("latency_ms"), "ms |", a.get("answer"), "|",
              a.get("followups"), [(t["agent"], t["ms"], t["ok"]) for t in a.get("trace", [])])
    async with streamablehttp_client(B + "/mcp/") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("MCP tools", [t.name for t in tools.tools])
            res = await s.call_tool("why_it_moved", {"match_id": MATCH})
            print("why_it_moved", res.content[0].text[:300])
            res = await s.call_tool("chances_at", {"match_id": MATCH, "minute": 45})
            print("chances_at 45", res.content[0].text[:200])


if __name__ == "__main__":
    asyncio.run(main())
