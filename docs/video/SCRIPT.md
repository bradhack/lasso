# Lasso demo video: the script

About 100 seconds of narration (the recording runs a little longer while the live match plays). Generated from `docs/video/record_demo.py`, which records the video to match. With `--voice` it narrates these lines itself with an Azure AI Speech voice (Jane, excited, by default; `--sample-voices` says the opening and the VAR moment in about twenty voices so you can pick one, and `--style` and `--rate` change the delivery); without it, read them over the video, using `out/narration.md` for each scene's exact start time. The video must stay under two minutes.

| # | Scene | On screen | Say | At least |
|---|---|---|---|---|
| 1 | Lasso | Slide: the Lasso cover, while the showcase match restarts underneath. | This is Lasso. It's a team of AI agents that watches live football with you, explains every shift in momentum, answers your questions, and lets you predict what happens next. | 11s |
| 2 | The Gaffer's Gauge | The live match: Eastholme Rangers 1-1 Brackenford City in the second half, Eastholme down to ten. The score and the Gauge glow. | We're following our team, Eastholme Rangers. They're all square with Brackenford City, but their odds aren't great: they've been down to ten men since a red card in the fifth minute. | 11s |
| 3 | Why it moved | Why it moved glows: the agents' latest story, in plain words. | When the odds swing, Why it moved is the place to look. It explains each big shift in momentum and what caused it, in English, Spanish, Portuguese or French. Pick yours in your profile. | 13s |
| 4 | Ask the Gaffer | Typing "Can Eastholme still win this?" into Ask the Gaffer; the answer arrives with its AI agents chip. | Ask any question, at any time. One agent gathers the facts through the Model Context Protocol, and another writes your answer. | 8s |
| 5 | Call your shot | Call it: "Eastholme Rangers score before 89'?" Yes, then Lasso it. | Want to predict what happens next? If you're feeling brave, call your shot. Biscuit rewards follow the Gaffer's calculated odds, so long shots pay big. No money, just bragging rights. | 11s |
| 6 | VAR check | 82': Eastholme scores and VAR checks it: VAR CHECK over the Pitch, the VAR card shows the Gauge both ways, and Call it asks "Will the goal stand?" and the fan picks It stands. | Eastholme scores! But hold on, VAR is reviewing it. Watch it live, and take a guess: will the goal stand? We say yes. | 9s |
| 7 | It stands | The goal stands: the Gauge jumps, both calls pay out, and the agents' story replaces the instant one. | It stands. Eastholme's chances to win jump, and both our calls win biscuits! We correctly predicted Eastholme would score, and that the VAR review would stand. | 10s |
| 8 | Under the hood | Under the hood for the goal's story, enlarged: round one (Stats, Gaffer), round two (Narrator, Persona, Game Master), then Checked by code, each highlighted in turn. | Let's look at how those agents wrote that story. Two agents work out what changed, three more write it, and our code checks every fact. | 9s |
| 9 | Microsoft Fabric | Slide: the Lasso agents dashboard in Microsoft Fabric, panning down. | Everything streams into Microsoft Fabric, so we can track the agents' speed, cost and mistakes. | 6s |
| 10 | How it's built | Slide: how Lasso works, seven agents and one live pipeline. | Built on Microsoft Foundry and Agent Framework, over A2A and the Model Context Protocol, all running on Azure. | 7s |
| 11 | Close | Slide: the Lasso cover. | That's Lasso. Watch smarter, call it first, and believe your call. | 4s |

264 words in all.
