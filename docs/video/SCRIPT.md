# Lasso demo video: the script

About 100 seconds of narration (the recording runs a little longer while the live match plays). Generated from `docs/video/record_demo.py`, which records the video to match. With `--voice` it narrates these lines itself with an Azure AI Speech voice (Jane, excited, by default; `--sample-voices` says the opening and the VAR moment in about twenty voices so you can pick one, and `--style` and `--rate` change the delivery); without it, read them over the video, using `out/narration.md` for each scene's exact start time. The video must stay under two minutes.

| # | Scene | On screen | Say | At least |
|---|---|---|---|---|
| 1 | Lasso | Slide: the Lasso cover, while the showcase match restarts underneath. | This is Lasso. A team of AI agents watches live football with you, explains every shift in momentum, answers your questions, and lets you call what happens next. | 10s |
| 2 | The Gaffer's Gauge | The live match: Eastholme Rangers 1-1 Brackenford City in the second half, Eastholme down to ten. The score and the Gauge glow. | We're following Eastholme Rangers: 1-1 late in the second half, down to ten men since an early red card, and our win probability model, the Gaffer, doesn't fancy their chances. | 11s |
| 3 | Why it moved | Why it moved glows: the agents' latest story, in plain words. | Next, Why it moved. It explains what caused the win probability to change, in English, Spanish, Portuguese or French. | 7s |
| 4 | Ask the Gaffer | Typing "Can Eastholme still win this?" into Ask the Gaffer; the answer arrives with its AI agents chip. | Ask any question, at any time. One agent gathers the facts through the Model Context Protocol, and another writes your answer. | 8s |
| 5 | Call your shot | Call it: "Eastholme Rangers score before 89'?" Yes, then Lasso it. | Feeling brave? Call your shot. Biscuit rewards are set by the Gaffer's calculated odds, so long shots pay big. | 7s |
| 6 | VAR check | 82': Eastholme scores and VAR checks it. The VAR card shows the Gauge both ways; Call it asks "Will the goal stand?" and the fan picks It stands. | Eastholme scores! But VAR is checking it. The Gauge shows both outcomes, and a new call appears: will the goal stand? We say yes. | 9s |
| 7 | It stands | The goal stands: the Gauge jumps, both calls pay out, and the agents' story replaces the instant one. | It stands! The Gauge jumps, and both our calls win biscuits: Eastholme to score, and the goal to stand. | 7s |
| 8 | Under the hood | Under the hood for the goal's story, enlarged: round one (Stats, Gaffer), round two (Narrator, Persona, Game Master), then Checked by code, each highlighted in turn. | How did the agents write that story? Tap AI agents to look under the hood: two agents work out what changed, three more write the story, and our code checks every fact before you see it. | 13s |
| 9 | Microsoft Fabric | Slide: the Lasso agents dashboard in Microsoft Fabric, panning down. | Everything streams into Microsoft Fabric, so we can track the agents' speed, cost and mistakes. | 6s |
| 10 | A team of agents or one | Slide: the Press Room team against one agent alone, on the same 27 questions. | Is a team of AI agents better than one? On the same 27 questions, the team passed them all, and a single agent missed two. | 9s |
| 11 | How it's built | Slide: how Lasso works, seven agents and one live pipeline. | Built on Microsoft Foundry and Agent Framework, over A2A and the Model Context Protocol, all running on Azure. | 7s |
| 12 | Close | Slide: the Lasso cover. | That's Lasso. Watch smarter, call it first, and believe your call. | 4s |

265 words in all.
