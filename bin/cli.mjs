#!/usr/bin/env node
/**
 * Cross-platform npx launcher for Flash computer use MCP server.
 * Bootstraps an isolated Python virtual environment on first run (using `uv` or `python3 -m venv`)
 * and launches the stdio MCP server without polluting stdout.
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir, platform } from "node:os";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PACKAGE_ROOT = resolve(__dirname, "..");
const IS_WIN = platform() === "win32";

// Ensure common user binary locations are in PATH for GUI MCP clients (Cursor, Claude Desktop, etc.)
if (!IS_WIN) {
  const extraPaths = [
    join(homedir(), ".local", "bin"),
    join(homedir(), ".cargo", "bin"),
    "/opt/homebrew/bin",
    "/usr/local/bin",
  ];
  const currentPaths = new Set((process.env.PATH || "").split(delimiter));
  for (const p of extraPaths) {
    if (!currentPaths.has(p) && existsSync(p)) {
      process.env.PATH = `${p}${delimiter}${process.env.PATH || ""}`;
    }
  }
}

function venvPythonPath(venvDir) {
  return IS_WIN
    ? join(venvDir, "Scripts", "python.exe")
    : join(venvDir, "bin", "python");
}

function commandExists(cmd) {
  const res = spawnSync(cmd, ["--version"], { stdio: "ignore", shell: IS_WIN });
  return res.status === 0;
}

function findSystemPython() {
  for (const candidate of IS_WIN ? ["python", "py"] : ["python3", "python"]) {
    const args =
      candidate === "py"
        ? ["-3", "-c", "import sys; assert sys.version_info >= (3, 11)"]
        : ["-c", "import sys; assert sys.version_info >= (3, 11)"];
    const res = spawnSync(candidate, args, { stdio: "ignore", shell: IS_WIN });
    if (res.status === 0) {
      return candidate === "py" ? ["py", ["-3"]] : [candidate, []];
    }
  }
  return null;
}

function getCacheDir() {
  if (process.env.FLASH_COMPUTER_USE_CACHE_DIR) {
    return resolve(process.env.FLASH_COMPUTER_USE_CACHE_DIR);
  }
  if (IS_WIN) {
    const base = process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local");
    return join(base, "flash-computer-use");
  }
  const base = process.env.XDG_CACHE_HOME || join(homedir(), ".cache");
  return join(base, "flash-computer-use");
}

function runSetupStep(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, {
    stdio: ["ignore", process.stderr, process.stderr],
    shell: IS_WIN,
    ...opts,
  });
  if (res.status !== 0) {
    process.stderr.write(
      `[Flash computer use] Command failed: ${cmd} ${args.join(" ")}\n`
    );
    process.exit(res.status || 1);
  }
}

function ensureEnvironment() {
  // 1. Fast path: local pre-built .venv inside PACKAGE_ROOT
  const localVenvPython = venvPythonPath(join(PACKAGE_ROOT, ".venv"));
  if (existsSync(localVenvPython)) {
    const localPlaywright = join(PACKAGE_ROOT, ".runtime", "playwright");
    const extraEnv =
      existsSync(localPlaywright) && !process.env.PLAYWRIGHT_BROWSERS_PATH
        ? { PLAYWRIGHT_BROWSERS_PATH: localPlaywright }
        : {};
    return { python: localVenvPython, extraEnv };
  }

  // 2. Persistent user cache directory for npx runs
  const cacheDir = getCacheDir();
  const venvDir = join(cacheDir, "venv");
  const playwrightDir = join(cacheDir, "playwright");
  const stampFile = join(cacheDir, "installed-version.txt");
  const pkgVersion =
    JSON.parse(readFileSync(join(PACKAGE_ROOT, "package.json"), "utf8"))
      .version || "0.1.0";

  mkdirSync(cacheDir, { recursive: true });
  const pythonBin = venvPythonPath(venvDir);
  const currentStamp = existsSync(stampFile)
    ? readFileSync(stampFile, "utf8").trim()
    : "";

  if (!existsSync(pythonBin) || currentStamp !== pkgVersion) {
    process.stderr.write(
      `[Flash computer use] Initializing Python environment in ${venvDir}...\n`
    );
    if (commandExists("uv")) {
      if (!existsSync(pythonBin)) {
        runSetupStep("uv", ["venv", "--python", ">=3.11", venvDir]);
      }
      runSetupStep("uv", [
        "pip",
        "install",
        "--python",
        pythonBin,
        PACKAGE_ROOT,
      ]);
    } else {
      const sysPy = findSystemPython();
      if (!sysPy) {
        process.stderr.write(
          "[Flash computer use] Error: Python >= 3.11 or `uv` is required. Install uv (https://docs.astral.sh/uv/) or Python 3.11+.\n"
        );
        process.exit(1);
      }
      const [pyCmd, pyPrefixArgs] = sysPy;
      if (!existsSync(pythonBin)) {
        runSetupStep(pyCmd, [...pyPrefixArgs, "-m", "venv", venvDir]);
      }
      runSetupStep(pythonBin, ["-m", "pip", "install", "--upgrade", "pip"]);
      runSetupStep(pythonBin, ["-m", "pip", "install", PACKAGE_ROOT]);
    }

    // Ensure Playwright Chromium is installed
    const pwEnv = {
      ...process.env,
      PLAYWRIGHT_BROWSERS_PATH:
        process.env.PLAYWRIGHT_BROWSERS_PATH || playwrightDir,
    };
    process.stderr.write(
      "[Flash computer use] Ensuring Playwright Chromium browser is installed...\n"
    );
    runSetupStep(pythonBin, ["-m", "playwright", "install", "chromium"], {
      env: pwEnv,
    });
    writeFileSync(stampFile, pkgVersion, "utf8");
  }

  const extraEnv = !process.env.PLAYWRIGHT_BROWSERS_PATH
    ? { PLAYWRIGHT_BROWSERS_PATH: playwrightDir }
    : {};
  return { python: pythonBin, extraEnv };
}

const rawArgs = process.argv.slice(2);
const firstArg = rawArgs[0]?.replace(/^--/, "");

const { python, extraEnv } = ensureEnvironment();

let pyArgs;
if (firstArg === "doctor") {
  pyArgs = [
    "-c",
    "from d1_computer_use_mcp.portability import doctor; doctor()",
  ];
} else if (firstArg === "config") {
  pyArgs = [
    "-c",
    "import sys; from d1_computer_use_mcp.portability import configure; sys.argv = ['flash-config', *sys.argv[1:]]; configure()",
    ...rawArgs.slice(1),
  ];
} else if (firstArg === "check") {
  pyArgs = ["-m", "d1_computer_use_mcp.check", ...rawArgs.slice(1)];
} else {
  pyArgs = ["-m", "d1_computer_use_mcp.server", ...rawArgs];
}

const child = spawn(python, pyArgs, {
  stdio: "inherit",
  env: { ...process.env, ...extraEnv },
});

for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => {
    if (!child.killed) {
      child.kill(sig);
    }
  });
}

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 0);
  }
});
