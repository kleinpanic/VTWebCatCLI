#!/usr/bin/env node
const { spawnSync } = require("node:child_process");

function usage() {
  console.log(`usage: node scripts/ci_monitor.cjs <command> [args]

commands:
  runs [--branch NAME] [--limit N]
  watch RUN_ID
  log-failed RUN_ID
  check-actions [workflow.yml]
`);
}

function run(cmd, args, options = {}) {
  const result = spawnSync(cmd, args, { stdio: "inherit", encoding: "utf8", ...options });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  process.exitCode = result.status ?? 1;
  return result;
}

function output(cmd, args) {
  const result = spawnSync(cmd, args, { encoding: "utf8" });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) {
    process.stderr.write(result.stderr);
    process.exit(result.status ?? 1);
  }
  return result.stdout;
}

const args = process.argv.slice(2);
const command = args.shift();

if (!command || command === "-h" || command === "--help") {
  usage();
  process.exit(command ? 0 : 2);
}

if (command === "runs") {
  const ghArgs = ["run", "list", "--repo", "kleinpanic/VTWebCatCLI"];
  let limit = "10";
  while (args.length) {
    const arg = args.shift();
    if (arg === "--branch") {
      ghArgs.push("--branch", args.shift());
    } else if (arg === "--limit") {
      limit = args.shift();
    } else {
      console.error(`unknown runs option: ${arg}`);
      process.exit(2);
    }
  }
  ghArgs.push("--limit", limit);
  run("gh", ghArgs);
} else if (command === "watch") {
  const runId = args.shift();
  if (!runId) {
    console.error("watch requires RUN_ID");
    process.exit(2);
  }
  run("gh", ["run", "watch", runId, "--repo", "kleinpanic/VTWebCatCLI", "--exit-status"]);
} else if (command === "log-failed") {
  const runId = args.shift();
  if (!runId) {
    console.error("log-failed requires RUN_ID");
    process.exit(2);
  }
  run("gh", ["run", "view", runId, "--repo", "kleinpanic/VTWebCatCLI", "--log-failed"]);
} else if (command === "check-actions") {
  const file = args.shift() || ".github/workflows/ci.yml";
  const text = output("sed", ["-n", "1,240p", file]);
  const uses = [...text.matchAll(/uses:\s*([^\s#]+)/g)].map((match) => match[1]);
  const unpinned = uses.filter((value) => !/@v\d+/.test(value) && !/@[a-f0-9]{40}$/i.test(value));
  if (unpinned.length) {
    console.error(`Unpinned or unusual actions in ${file}:`);
    for (const value of unpinned) {
      console.error(`  ${value}`);
    }
    process.exit(1);
  }
  console.log(`PASS action references in ${file}`);
} else {
  console.error(`unknown command: ${command}`);
  usage();
  process.exit(2);
}
