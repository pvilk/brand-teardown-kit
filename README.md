# Brand Teardown kit for Claude Code

A Claude Code plugin that teaches your Claude the workflow behind the Drizzy report: how a young consumer brand is really performing, from public sources only. It adds a `/brand-teardown` command and two skills. Your Claude reads them; you don't have to.

## Install (about 5 minutes)

1. Unzip the folder somewhere permanent, e.g. `~/claude-kits/brand-teardown-kit`.
2. In Claude Code, run:
   ```
   /plugin marketplace add ~/claude-kits/brand-teardown-kit
   /plugin install brand-teardown@brand-teardown-kit
   ```
   Then restart Claude Code. From a terminal instead: `claude plugin marketplace add ~/claude-kits/brand-teardown-kit && claude plugin install brand-teardown@brand-teardown-kit`. 

   **From GitHub instead of the zip** (you need to be added to the private repo first): `/plugin marketplace add pvilk/brand-teardown-kit`, then the same install line. Pull updates later with `/plugin marketplace update brand-teardown-kit`.
3. Install the Python pieces the scripts use:
   ```
   pip install curl_cffi playwright && playwright install chromium
   ```

## Use it

- `/brand-teardown Drizzy getdrizzy.co`
- "How is Olipop's new brand performing? How many stores are they in?"
- "Re-run the Sprouts store check for Drizzy and compare it with last time."

**Give it the brand's website if the name is common or ambiguous.** Most bad first runs research the wrong company.

A full run launches six research agents in parallel and takes roughly 30 to 40 minutes. It is token-heavy (the Drizzy run used about 1.8M tokens across agents).

## Optional upgrades

- **Claude in Chrome extension:** lets one agent read LinkedIn, the TikTok video grid and Google Trends in your logged-in browser. Without it, the kit uses no-login routes and gets less.
- **A TikTok Shop analytics tool** (Euka's MCP, or Kalodata/FastMoss): daily TikTok Shop sales for any seller. Without it, the kit reads the public all-time "sold" count and you snapshot it over time.
- **Artifact publishing:** if your Claude Code can publish Artifacts, the report becomes a shareable link. Otherwise you get a local HTML file.

## What's inside

```
brand-teardown-kit/
  .claude-plugin/                 plugin + marketplace manifests
  commands/brand-teardown.md      the /brand-teardown command
  skills/brand-revenue-teardown/
    SKILL.md                      the workflow, step by step
    references/agent-prompts.md   the six research-agent prompts
    references/revenue-model.md   formulas, sourced Sprouts benchmarks, gross vs net
    references/scraping-recipes.md  endpoints and traps for every source
    references/report-example.html  the finished Drizzy report, used as the template
    scripts/                      store-locator puller, Sprouts store-by-store checker,
                                  run comparer, Meta / Google / TikTok ad checks
  skills/adlib-page-resolver/     finds a brand's real Meta Ad Library page
  requirements.txt
```

## Three rules that make or break the output

1. **Count stores, don't quote them.** Founder counts drift ("480+", "500+"), and store locators include warehouses. Verify store by store on the retailer's own site.
2. **Keep brand dollars and shelf dollars apart.** A $11.49 bottle on the shelf is $5.35 to the brand. Revenue estimates that look "too low" usually differ on this, or on gross vs net.
3. **A zero only counts with a control.** "No ads", "no Amazon listing" or "no Reddit mentions" means nothing until the same check finds a known positive.
