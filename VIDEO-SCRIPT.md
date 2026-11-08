# AgentGuard Drawerrr video script

Target 2 minutes 15 seconds. Record the public site at 1080p with the browser
signed out. Keep the demo’s guided simulation text visible or add a **Guided
simulation** caption. The evidence page already shows **Recorded verification ·
November 6, 2026**.
The walkthrough needs no live dashboard, account details, or credentials.

| Time | On screen | Say |
| --- | --- | --- |
| 0:00–0:18 | Start on the [homepage](https://agentguard-eight.vercel.app). Show the AgentGuard title and refund example. | “An AI support agent can ask for a refund in one tool call. What stops it from spending more than the business authorized? I’m Haisam Arshad. I built AgentGuard to enforce that decision before the refund can take effect.” |
| 0:18–0:38 | Open the [demo](https://agentguard-eight.vercel.app/demo). Select **Human review**, then **Show simulated decision**. Hold on the amount and zero receipts. | “This is the public simulation. The Finance Agent has permission to request a refund. This one is seven hundred and fifty-five dollars, so it waits for an independent reviewer. At this point, the ledger has zero receipts.” |
| 0:38–1:03 | Click **Simulate human approval**, **Simulate execution**, and **Try replaying the approval**. Pause on the final receipt count. | “The operator reviews the stored amount and destination. In the real dashboard, approval requires a recent passkey or MFA. After approval, the original agent can execute the stored request once. If it retries the execution, AgentGuard rejects the replay. The ledger still has one receipt.” |
| 1:03–1:22 | Select **Split the budget**, then **Show simulated decision**. Show the remaining budget and pending result. | “A smaller refund can still require review. Here, three hundred dollars has already been used, so only two hundred remains. The next two-hundred-and-fifty-dollar request waits for a human. Splitting the total across requests doesn’t reset the shared budget.” |
| 1:22–1:49 | Open the [evidence page](https://agentguard-eight.vercel.app/evidence). Hold on the live approval and then the local comparison. | “The November sixth hosted test used a real human passkey approval. It recorded one simulated seven-hundred-and-fifty-five-dollar receipt and rejected replay. Separately, the reproducible local evaluation matched the expected ledger effects in all ten cases. The scope-and-threshold baseline matched three, and the unguarded baseline matched one.” |
| 1:49–2:12 | End on the evidence links or show the [MCP README](README.md) with the evaluator commands. Add the demo and repository links to the closing frame. | “AgentGuard is a sandbox for financial actions. No money moves. The same boundary is visible at each step: permissions let the agent request an action, the policy can hold it, and a human can authorize the exact transaction. You can try the walkthrough without an account and reproduce the ledger checks from the repository.” |

Before recording, open the home, demo, and evidence tabs in order. Confirm the
comparison and hosted proof are visible at the recording width. Record one
clean take, then check the replay state, narration, captions, and link frame.
The November 6 report is the source for the live claims. The comparison uses
fixed scenarios and illustrative baselines. Keep those captions distinct.
