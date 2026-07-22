import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

export default function globalSetup() {
  const frontend = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
  const root = path.dirname(frontend);
  run("docker", ["compose", "-f", "deploy/local/compose.yaml", "up", "-d", "postgres"], root);
  run("uv", ["run", "alembic", "upgrade", "head"], root);
}

export function resetReplayCase(root: string, caseId: string) {
  resetCaseExecutionState(root, caseId);
  run(
    "uv",
    ["run", "soc-ot", "fixtures", "import", "--case-id", caseId, "--replace-current"],
    root,
  );
  run("uv", ["run", "soc-ot", "fixtures", "import-hidden", "--case-id", caseId], root, {
    ...process.env,
    SOC_OT_AUTHORING_MODE: "1",
  });
}

export function resetProjectFixtures(root: string) {
  const projectIds = ["PROJECT-U", "PROJECT-V", "PROJECT-W"];
  const quotedIds = projectIds.map((projectId) => `'${projectId}'`).join(", ");
  run(
    "docker",
    [
      "compose", "-f", "deploy/local/compose.yaml", "exec", "-T", "postgres",
      "psql", "-v", "ON_ERROR_STOP=1", "-U", "soc_ot_admin", "-d", "soc_ot", "-c",
      `DELETE FROM observable.development_projects WHERE project_id IN (${quotedIds})`,
    ],
    root,
  );
  for (const projectId of projectIds) {
    run(
      "uv",
      [
        "run", "soc-ot", "fixtures", "import-project",
        "--project-id", projectId, "--replace-current",
      ],
      root,
    );
  }
}

function resetCaseExecutionState(root: string, caseId: string) {
  const quotedCaseId = `'${caseId.replaceAll("'", "''")}'`;
  const sql = [
    `DELETE FROM audit.agent_run_events WHERE run_id IN (SELECT run_id FROM observable.agent_runs WHERE case_id = ${quotedCaseId})`,
    `DELETE FROM audit.agent_attempts WHERE case_id = ${quotedCaseId}`,
    `DELETE FROM observable.agent_run_steps WHERE run_id IN (SELECT run_id FROM observable.agent_runs WHERE case_id = ${quotedCaseId})`,
    `DELETE FROM hidden.outcome_evaluations WHERE case_id = ${quotedCaseId}`,
    `DELETE FROM hidden.outcome_advances WHERE case_id = ${quotedCaseId}`,
    `DELETE FROM observable.simulated_decisions WHERE case_id = ${quotedCaseId}`,
    `DELETE FROM observable.simulation_states WHERE case_id = ${quotedCaseId}`,
    `DELETE FROM observable.agent_runs WHERE case_id = ${quotedCaseId}`,
  ].join("; ");
  run(
    "docker",
    [
      "compose", "-f", "deploy/local/compose.yaml", "exec", "-T", "postgres",
      "psql", "-v", "ON_ERROR_STOP=1", "-U", "soc_ot_admin", "-d", "soc_ot", "-c", sql,
    ],
    root,
  );
}

function run(command: string, args: string[], cwd: string, env = process.env) {
  execFileSync(command, args, { cwd, env, stdio: "inherit" });
}
