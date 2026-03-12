/**
 * AI Video Factory - Cloudflare Workers Cron Trigger
 *
 * Triggers the GitHub Actions workflow on schedule.
 * More reliable than GitHub's built-in cron (which can be delayed/skipped).
 *
 * Secrets needed:
 *   GITHUB_TOKEN - GitHub Personal Access Token with `repo` and `actions` scope
 *   CRON_SECRET  - Secret for manual trigger endpoint
 */

export default {
  // Cron trigger - fires on schedule defined in wrangler.toml
  async scheduled(event, env, ctx) {
    ctx.waitUntil(triggerPipeline(env, "cron"));
  },

  // HTTP trigger - for manual runs or health checks
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "video-factory-cron",
          timestamp: new Date().toISOString(),
        }),
        { headers: { "content-type": "application/json" } }
      );
    }

    if (url.pathname === "/trigger") {
      // Verify secret
      const auth = request.headers.get("Authorization");
      if (!auth || auth !== `Bearer ${env.CRON_SECRET}`) {
        return new Response("Unauthorized", { status: 401 });
      }

      // Parse optional params
      const niche = url.searchParams.get("niche") || "";
      const format = url.searchParams.get("format") || "";
      const dryRun = url.searchParams.get("dry-run") === "true";

      const result = await triggerPipeline(env, "manual", {
        niche,
        format,
        dry_run: dryRun,
      });
      return new Response(JSON.stringify(result), {
        headers: { "content-type": "application/json" },
      });
    }

    if (url.pathname === "/status") {
      const auth = request.headers.get("Authorization");
      if (!auth || auth !== `Bearer ${env.CRON_SECRET}`) {
        return new Response("Unauthorized", { status: 401 });
      }
      const result = await getWorkflowStatus(env);
      return new Response(JSON.stringify(result), {
        headers: { "content-type": "application/json" },
      });
    }

    return new Response("AI Video Factory Cron Worker\n\nEndpoints:\n  GET /health\n  POST /trigger (Bearer auth)\n  GET /status (Bearer auth)", {
      status: 200,
    });
  },
};

/**
 * Trigger the GitHub Actions workflow via the API.
 */
async function triggerPipeline(env, source = "cron", inputs = {}) {
  if (!env.GITHUB_TOKEN) {
    console.error("GITHUB_TOKEN not configured");
    return { status: "error", error: "GITHUB_TOKEN not configured" };
  }

  const repo = env.GITHUB_REPO || "PenuelM/ai-video-factory";
  const workflow = env.GITHUB_WORKFLOW || "daily-video.yml";

  try {
    const response = await fetch(
      `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "video-factory-cron",
        },
        body: JSON.stringify({
          ref: "main",
          inputs: {
            niche: inputs.niche || "",
            format: inputs.format || "",
            dry_run: String(inputs.dry_run || false),
            source: source,
          },
        }),
      }
    );

    if (response.status === 204) {
      console.log(
        `[video-cron] Triggered workflow (source: ${source}) at ${new Date().toISOString()}`
      );
      return {
        status: "triggered",
        source,
        timestamp: new Date().toISOString(),
        inputs,
      };
    }

    const errorText = await response.text();
    console.error(
      `[video-cron] GitHub API error: ${response.status} ${errorText}`
    );
    return {
      status: "error",
      code: response.status,
      error: errorText,
    };
  } catch (err) {
    console.error(`[video-cron] Failed to trigger: ${err.message}`);
    return { status: "error", error: err.message };
  }
}

/**
 * Get the status of the most recent workflow run.
 */
async function getWorkflowStatus(env) {
  const repo = env.GITHUB_REPO || "PenuelM/ai-video-factory";
  const workflow = env.GITHUB_WORKFLOW || "daily-video.yml";

  try {
    const response = await fetch(
      `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/runs?per_page=5`,
      {
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "video-factory-cron",
        },
      }
    );

    if (!response.ok) {
      return { status: "error", code: response.status };
    }

    const data = await response.json();
    const runs = (data.workflow_runs || []).map((run) => ({
      id: run.id,
      status: run.status,
      conclusion: run.conclusion,
      created_at: run.created_at,
      updated_at: run.updated_at,
      url: run.html_url,
    }));

    return { status: "ok", recent_runs: runs };
  } catch (err) {
    return { status: "error", error: err.message };
  }
}
