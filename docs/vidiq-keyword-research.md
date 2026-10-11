# vidIQ Keyword Research — Clip Factory Workflow

## Live integration status

The GitHub Actions workflow now includes a live research step using vidIQ's official remote MCP server at `https://mcp.vidiq.com/mcp`. It runs after the per-clip queue is generated and before the output artifact is uploaded.

**One-time setup required:** GitHub Actions cannot reuse the vidIQ authorization that is connected to ChatGPT. Create a vidIQ MCP API key and store it as a GitHub Actions repository secret named `VIDIQ_MCP_API_KEY`. Never commit the key into this repository or put it in a workflow file.

1. Sign in to vidIQ at https://app.vidiq.com/.
2. Open **Account Settings → MCP** and create an API key.
3. In the GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**.
4. Name the secret exactly `VIDIQ_MCP_API_KEY`, paste the key as its value, and save.
5. Run the **Clip Factory - AI Best Moments** workflow again. The live keyword research step will call vidIQ for each generated clip and update the JSON/CSV queue before the artifact upload.

If the secret is missing, the workflow intentionally skips live calls and leaves the queue marked for research. If a call fails, the affected clip remains **Needs vidIQ review** and no fake metrics are written. The API key is passed as a runtime environment variable and is never included in artifacts or printed in logs.

The live step uses one keyword-research call per clip (normally 5 vidIQ credits per call). It searches the primary seed, reads the returned keyword metrics and related suggestions, and records the selected opportunity for human review. Because vidIQ scores and monthly search volume are estimates, verify that the selected phrase accurately matches the actual clip before publishing.

## Goal

For every clip produced by Burnt-Out-Productions Clip Factory, research the topic in vidIQ before finalizing its title, description, and tags. Prioritize relevant search demand with comparatively low competition; never choose a keyword solely because its volume is high.

## Per-clip workflow

1. Analyze the full source video and the selected clip. Extract the main subject, specific moment, names/entities, niche, and likely viewer intent.
2. Draft natural search phrases that accurately describe the clip. Include specific long-tail phrases, not just broad terms.
3. Research the primary phrase in vidIQ through the official MCP integration. Record the returned search-volume estimate, competition, overall score, related phrases, and date checked when available.
4. Select the strongest relevant phrase using this order:
   - The phrase accurately matches the actual clip.
   - Prefer higher search demand paired with lower competition.
   - Prefer specific long-tail phrases when broad phrases are too competitive.
   - Reject misleading, unrelated, or sensational keywords even if their metrics look strong.
5. Build metadata:
   - **Primary keyword:** best-supported target phrase.
   - **Title:** clear and compelling, naturally includes the primary phrase where it reads well.
   - **Description:** one or two accurate sentences with the primary phrase and closely related terms.
   - **Tags:** a concise set of highly relevant variants, entities, niche terms, and long-tail phrases. Avoid keyword stuffing and unrelated trending tags.
   - **Hashtags:** only a few relevant hashtags when appropriate for the platform; do not treat hashtags and YouTube tags as interchangeable.
6. Save the chosen phrase, alternatives, vidIQ metrics, date checked, proposed title, description, tags, and research status in the clip's metadata/review record.
7. Present the metadata for human review before publishing. If vidIQ cannot be accessed or its metrics cannot be verified, mark research as **Needs vidIQ review** and provide suggested tags clearly labeled as unverified; never invent volume or competition numbers.

## Automation and integration constraints

- Use the official vidIQ MCP endpoint and API-key authentication; do not scrape the vidIQ website or store credentials in source code.
- Keep video selection, editing, rights checks, and publication workflow separate from keyword research. Keyword research must not bypass the existing rights-aware, review-first publishing process.
- The research step does not publish videos or automatically change YouTube metadata.
- Keep this workflow usable from the iPhone-first dashboard. Review the generated `vidiq-research-queue.json` and `vidiq-research-queue.csv` files in the GitHub Actions artifact.
- Research status values include **Needs vidIQ review** and **Ready for human review**. The latter still requires a human to confirm relevance and approve final metadata.

## Useful links

- vidIQ MCP setup: https://support.vidiq.com/en/articles/15082430-vidiq-mcp
- vidIQ keyword research guide: https://support.vidiq.com/en/articles/9421214-keywords-research
- vidIQ account: https://app.vidiq.com/
