# Lasso demo video: the script

About 98 seconds of narration (the recording runs a little longer while the live match plays). Generated from `docs/video/record_demo.py`, which records the video to match. With `--voice` it narrates these lines itself with an Azure AI Speech voice (a natural US voice by default; `--sample-voices` says the opening and the VAR moment in ten voices so you can pick one, and `--style` and `--rate` change the delivery); without it, read them over the video, using `out/narration.md` for each scene's exact start time. The video must stay under two minutes.

| # | Scene | On screen | Say | At least |
|---|---|---|---|---|
| 1 | Lasso | Slide: the Lasso cover, while the showcase match restarts underneath. | This is Lasso. A team of AI agents watches live football with you, explains every swing, answers your questions, and lets you call what happens next. | 10s |
| 2 | The Gaffer's Gauge | The live match: Eastholme Rangers 1-1 Brackenford City in the second half, Eastholme down to ten. The score and the Gauge glow. | We're backing Eastholme Rangers: 1-1 late in the second half, down to ten since an early red card, and the Gaffer, our win probability model, doesn't fancy their chances. | 11s |
| 3 | Why it moved | Why it moved glows: the agents' latest story, in plain words. | Why it moved explains what changed the win probability, in English, Spanish, Portuguese or French. | 6s |
| 4 | Ask the Gaffer | Typing "Can Eastholme still win this?" into Ask the Gaffer; the answer arrives with its AI agents chip. | Ask anything, at any point in the match. One agent digs up the facts through the Model Context Protocol, and another writes your answer. | 9s |
| 5 | Call your shot | Call it: "Eastholme Rangers score before 89'?" Yes, then Lasso it. | Feeling brave? Call your shot. Biscuit rewards are set by the Gaffer's calculated odds, so long shots pay big. No money, just bragging rights. | 9s |
| 6 | VAR check | 82': Eastholme score and VAR checks it. The VAR card shows the Gauge both ways; Call it asks "Will the goal stand?" and the fan picks It stands. | Eastholme score! But VAR is checking it. The Gauge shows the win probability both ways, and a quick call opens: will it stand? | 9s |
| 7 | It stands | The goal stands: the Gauge jumps, both calls pay out, and the agents' story replaces the instant one. | It stands! The Gauge jumps, both calls pay off, and the agents tell the story. | 6s |
| 8 | Under the hood | Under the hood for the goal's story, enlarged: round one (Stats, Gaffer), round two (Narrator, Persona, Game Master), then Checked by code, each highlighted in turn. | Tap AI agents to see how. Two agents pull the stats and work out what changed, three more write the story, and our code checks every fact before you see it. | 11s |
| 9 | Microsoft Fabric | Slide: the Lasso agents dashboard in Microsoft Fabric, panning down. | Everything streams into Microsoft Fabric: how fast the agents are, what they cost, and what they get wrong. | 7s |
| 10 | A team of agents or one | Slide: the Press Room team against one agent alone, on the same 27 questions. | Is a team of AI agents better than one? On the same 27 questions, the team passed all 27, and a single agent missed two. | 9s |
| 11 | How it's built | Slide: how Lasso works, seven agents and one live pipeline. | Built on Microsoft Foundry and Agent Framework, over A2A and the Model Context Protocol, all on Azure. | 7s |
| 12 | Close | Slide: the Lasso cover. | That's Lasso. Watch smarter, call it first, and believe your call. | 4s |

258 words in all.
