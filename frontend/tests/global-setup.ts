import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

export default function globalSetup() {
  const frontend = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
  const root = path.dirname(frontend);
  run("docker", ["compose", "-f", "deploy/local/compose.yaml", "up", "-d", "postgres"], root);
  run("uv", ["run", "alembic", "upgrade", "head"], root);
  run(
    "uv",
    ["run", "soc-ot", "fixtures", "import", "--case-id", "CASE-VR-001", "--replace-current"],
    root,
  );
  run("uv", ["run", "soc-ot", "fixtures", "import-hidden", "--case-id", "CASE-VR-001"], root, {
    ...process.env,
    SOC_OT_AUTHORING_MODE: "1",
  });
}

function run(command: string, args: string[], cwd: string, env = process.env) {
  execFileSync(command, args, { cwd, env, stdio: "inherit" });
}
