#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { execSync, spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, "..");
const TRANSLATION_SOURCE = path.join(PROJECT_ROOT, "translations", "codex-0.120.0.json");
const SUPPORTED_VERSION = "0.120.0";
const BACKUP_FILE = `codex.original.${SUPPORTED_VERSION}.cn-backup.js`;
const TRANSLATION_FILE = "codex-cn.translations.json";
const WRAPPER_MARKER = "Codex-CLI-CN wrapper for @openai/codex 0.120.0";

main();

function main() {
  const { command, target, force, help, json } = parseArgs(process.argv.slice(2));

  if (help || !command) {
    printUsage();
    process.exit(command ? 0 : 1);
  }

  try {
    switch (command) {
      case "locate":
        emitResult(locateInstall({ target }), json);
        break;
      case "inject":
        emitResult(injectPatch({ target, force }), json);
        break;
      case "restore":
        emitResult(restorePatch({ target }), json);
        break;
      case "status":
        emitResult(getStatus({ target }), json);
        break;
      default:
        console.error(`❌ 不支持的命令：${command}`);
        printUsage();
        process.exit(1);
    }
  } catch (error) {
    console.error(`❌ ${error.message}`);
    process.exit(1);
  }
}

function parseArgs(argv) {
  const result = {
    command: null,
    target: null,
    force: false,
    help: false,
    json: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!result.command && !token.startsWith("-")) {
      result.command = token;
      continue;
    }

    if (token === "--target") {
      result.target = argv[index + 1] ?? null;
      index += 1;
      continue;
    }

    if (token === "--force") {
      result.force = true;
      continue;
    }

    if (token === "-h" || token === "--help") {
      result.help = true;
      continue;
    }

    if (token === "--json") {
      result.json = true;
      continue;
    }

    throw new Error(`无法识别的参数：${token}`);
  }

  return result;
}

function printUsage() {
  console.log(
    [
      "Codex-CLI-CN",
      "",
      "用法：",
      "  node scripts/codex-cn.mjs <locate|inject|restore|status> [--target <codex目录>] [--force]",
      "",
      "说明：",
      "  locate   自动搜索当前机器上的 Codex 安装目录",
      "  inject   为 @openai/codex 0.120.0 注入中文补丁并自动备份原始启动器",
      "  restore  恢复原始启动器并移除补丁文件",
      "  status   查看当前目标目录的补丁状态",
      "",
      "可选参数：",
      "  --target <path>  指定要补丁的 Codex 安装目录；默认自动解析全局 npm 安装目录",
      "  --force          允许对非 0.120.0 版本进行试注入（不推荐）",
      "  --json           以 JSON 形式输出状态结果（适合 GUI / 自动化调用）"
    ].join("\n"),
  );
}

function injectPatch({ target, force }) {
  const installation = resolveCodexInstallation(target);
  const targetRoot = installation.root;
  const meta = readTargetMeta(targetRoot);
  ensureSupportedVersion(meta.version, force);

  const backupPath = path.join(meta.binDir, BACKUP_FILE);
  const translationPath = path.join(meta.binDir, TRANSLATION_FILE);

  if (!fs.existsSync(backupPath)) {
    fs.copyFileSync(meta.codexJsPath, backupPath);
  }

  fs.copyFileSync(TRANSLATION_SOURCE, translationPath);
  fs.writeFileSync(
    meta.codexJsPath,
    createWrapper({
      backupFile: BACKUP_FILE,
      marker: WRAPPER_MARKER,
      supportedVersion: SUPPORTED_VERSION,
      translationFile: TRANSLATION_FILE,
    }),
    "utf8",
  );

  return {
    ok: true,
    action: "inject",
    message: "中文补丁注入完成",
    targetRoot,
    source: installation.source,
    version: meta.version,
    injected: true,
    backupPath,
    translationPath,
  };
}

function restorePatch({ target }) {
  const installation = resolveCodexInstallation(target);
  const targetRoot = installation.root;
  const meta = readTargetMeta(targetRoot);
  const backupPath = path.join(meta.binDir, BACKUP_FILE);
  const translationPath = path.join(meta.binDir, TRANSLATION_FILE);

  if (!fs.existsSync(backupPath)) {
    throw new Error("没有找到可恢复的备份文件，已取消恢复");
  }

  fs.copyFileSync(backupPath, meta.codexJsPath);
  if (fs.existsSync(translationPath)) {
    fs.rmSync(translationPath, { force: true });
  }

  return {
    ok: true,
    action: "restore",
    message: "已恢复原始启动器",
    targetRoot,
    source: installation.source,
    version: meta.version,
    injected: false,
    backupPath,
    translationPath: fs.existsSync(translationPath) ? translationPath : null,
  };
}

function getStatus({ target }) {
  const installation = resolveCodexInstallation(target);
  const targetRoot = installation.root;
  const meta = readTargetMeta(targetRoot);
  const codexJs = fs.readFileSync(meta.codexJsPath, "utf8");
  const backupPath = path.join(meta.binDir, BACKUP_FILE);
  const translationPath = path.join(meta.binDir, TRANSLATION_FILE);
  return {
    ok: true,
    action: "status",
    message: "状态检查完成",
    targetRoot,
    source: installation.source,
    version: meta.version,
    injected: codexJs.includes(WRAPPER_MARKER),
    backupPath: fs.existsSync(backupPath) ? backupPath : null,
    translationPath: fs.existsSync(translationPath) ? translationPath : null,
    coverage: "帮助页、登录提示、常用状态输出与共享说明文本",
  };
}

function locateInstall({ target }) {
  const report = findCodexInstallations(target ? path.resolve(target) : null);
  const selected = target
    ? report.candidates.find((candidate) => candidate.source === "命令行 --target" && candidate.valid) ?? null
    : report.selected;

  if (target && !selected) {
    throw new Error(`指定目录不是有效的 Codex 安装目录：${path.resolve(target)}`);
  }

  return {
    ok: true,
    action: "locate",
    message: selected ? "已定位到 Codex 安装目录" : "未找到有效的 Codex 安装目录",
    targetRoot: selected?.root ?? null,
    source: selected?.source ?? null,
    version: selected?.version ?? null,
    candidates: report.candidates,
  };
}

function emitResult(result, asJson) {
  if (asJson) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  switch (result.action) {
    case "locate":
      if (result.targetRoot) {
        console.log("🔍 已定位到 Codex 安装目录");
        console.log(`📁 目标目录：${result.targetRoot}`);
        console.log(`📌 来源：${result.source}`);
        console.log(`🧩 Codex 版本：${result.version ?? "未知"}`);
      } else {
        console.log("⚠️ 未找到有效的 Codex 安装目录");
      }
      if (Array.isArray(result.candidates) && result.candidates.length > 0) {
        console.log("候选路径：");
        for (const candidate of result.candidates) {
          const suffix = candidate.valid
            ? `有效，版本 ${candidate.version ?? "未知"}`
            : `无效，原因：${candidate.issue ?? "未知"}`;
          console.log(`- ${candidate.source}: ${candidate.root} (${suffix})`);
        }
      }
      break;
    case "inject":
      console.log("✅ 中文补丁注入完成");
      console.log(`📁 目标目录：${result.targetRoot}`);
      console.log(`📌 来源：${result.source}`);
      console.log(`🧩 Codex 版本：${result.version}`);
      console.log(`💾 启动器备份：${result.backupPath}`);
      console.log(`🗂️ 翻译文件：${result.translationPath}`);
      console.log("💡 建议运行：codex --help");
      break;
    case "restore":
      console.log("✅ 已恢复原始启动器");
      console.log(`📁 目标目录：${result.targetRoot}`);
      console.log(`📌 来源：${result.source}`);
      console.log(`💾 使用备份：${result.backupPath}`);
      break;
    case "status":
      console.log("Codex-CLI-CN 状态");
      console.log(`- 目标目录：${result.targetRoot}`);
      console.log(`- 路径来源：${result.source}`);
      console.log(`- Codex 版本：${result.version}`);
      console.log(`- 已注入：${result.injected ? "是" : "否"}`);
      console.log(`- 备份文件：${result.backupPath ?? "未找到"}`);
      console.log(`- 翻译文件：${result.translationPath ?? "未找到"}`);
      console.log(`- 覆盖范围：${result.coverage}`);
      break;
    default:
      console.log(result.message);
      break;
  }
}

function resolveCodexInstallation(target) {
  const report = findCodexInstallations(target ? path.resolve(target) : null);

  if (target) {
    const explicit = report.candidates.find((candidate) => candidate.source === "命令行 --target");
    if (!explicit?.valid) {
      throw new Error(`指定目录不是有效的 Codex 安装目录：${path.resolve(target)}`);
    }
    return explicit;
  }

  const selected = report.selected;
  if (!selected) {
    const checked = report.candidates.map((candidate) => `${candidate.source}: ${candidate.root}`).join("；");
    throw new Error(`未找到有效的 Codex 安装目录。${checked ? `已检查：${checked}` : ""}`);
  }

  return selected;
}

function findCodexInstallations(preferredTarget) {
  const candidates = [];
  const seen = new Set();

  const addCandidate = (rawPath, source) => {
    if (!rawPath) {
      return;
    }

    const normalized = path.resolve(rawPath.trim());
    const key = process.platform === "win32" ? normalized.toLowerCase() : normalized;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    candidates.push(inspectCandidate(normalized, source));
  };

  if (preferredTarget) {
    addCandidate(preferredTarget, "命令行 --target");
  } else if (process.env.CODEX_CN_TARGET) {
    addCandidate(process.env.CODEX_CN_TARGET, "环境变量 CODEX_CN_TARGET");
  }

  if (process.platform === "win32") {
    for (const commandName of ["codex.cmd", "codex"]) {
      const output = safeExec(`where.exe ${commandName}`);
      if (!output) {
        continue;
      }
      for (const line of output.split(/\r?\n/)) {
        addCandidate(inferRootFromLauncher(line), `where ${commandName}`);
      }
    }
  }

  const npmGlobalRoot = safeExec("npm root -g");
  if (npmGlobalRoot) {
    addCandidate(path.join(npmGlobalRoot, "@openai", "codex"), "npm root -g");
  }

  const npmPrefix = safeExec("npm prefix -g");
  if (npmPrefix) {
    addCandidate(path.join(npmPrefix, "node_modules", "@openai", "codex"), "npm prefix -g");
  }

  if (process.env.APPDATA) {
    addCandidate(
      path.join(process.env.APPDATA, "npm", "node_modules", "@openai", "codex"),
      "%APPDATA%",
    );
  }

  if (process.env.USERPROFILE) {
    addCandidate(
      path.join(process.env.USERPROFILE, "AppData", "Roaming", "npm", "node_modules", "@openai", "codex"),
      "%USERPROFILE%\\AppData\\Roaming",
    );
  }

  if (process.env.ProgramFiles) {
    addCandidate(
      path.join(process.env.ProgramFiles, "nodejs", "node_modules", "@openai", "codex"),
      "%ProgramFiles%\\nodejs",
    );
  }

  if (process.env.LOCALAPPDATA) {
    addCandidate(
      path.join(process.env.LOCALAPPDATA, "Programs", "nodejs", "node_modules", "@openai", "codex"),
      "%LOCALAPPDATA%\\Programs\\nodejs",
    );
  }

  return {
    selected: candidates.find((candidate) => candidate.valid) ?? null,
    candidates,
  };
}

function inferRootFromLauncher(launcherPath) {
  const resolved = path.resolve(launcherPath.trim());
  const baseName = path.basename(resolved).toLowerCase();
  if (!baseName.startsWith("codex")) {
    return null;
  }

  const parentDir = path.basename(path.dirname(resolved)).toLowerCase();
  const grandParentDir = path.basename(path.dirname(path.dirname(resolved))).toLowerCase();
  if (parentDir === "bin" && grandParentDir === "codex") {
    return path.dirname(path.dirname(resolved));
  }

  return path.join(path.dirname(resolved), "node_modules", "@openai", "codex");
}

function inspectCandidate(root, source) {
  const packageJsonPath = path.join(root, "package.json");
  const codexJsPath = path.join(root, "bin", "codex.js");

  if (!fs.existsSync(root)) {
    return { root, source, valid: false, version: null, issue: "目录不存在" };
  }

  if (!fs.existsSync(packageJsonPath)) {
    return { root, source, valid: false, version: null, issue: "缺少 package.json" };
  }

  if (!fs.existsSync(codexJsPath)) {
    return { root, source, valid: false, version: null, issue: "缺少 bin/codex.js" };
  }

  try {
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
    return {
      root,
      source,
      valid: true,
      version: packageJson.version ?? null,
      issue: null,
    };
  } catch (error) {
    return {
      root,
      source,
      valid: false,
      version: null,
      issue: `package.json 读取失败：${error.message}`,
    };
  }
}

function safeExec(command) {
  try {
    return execSync(command, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

function readTargetMeta(targetRoot) {
  const packageJsonPath = path.join(targetRoot, "package.json");
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
  return {
    version: packageJson.version,
    binDir: path.join(targetRoot, "bin"),
    codexJsPath: path.join(targetRoot, "bin", "codex.js"),
  };
}

function ensureSupportedVersion(version, force) {
  if (version === SUPPORTED_VERSION || version.startsWith(`${SUPPORTED_VERSION}-`)) {
    return;
  }

  if (force) {
    console.warn(
      `⚠️ 当前版本为 ${version}，不是官方验证过的 ${SUPPORTED_VERSION}；已按 --force 继续。`,
    );
    return;
  }

  throw new Error(
    `当前检测到的 Codex 版本为 ${version}。本补丁默认只支持 ${SUPPORTED_VERSION}，如需继续请追加 --force。`,
  );
}

function createWrapper({ backupFile, marker, supportedVersion, translationFile }) {
  return `#!/usr/bin/env node
// ${marker}

import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const require = createRequire(import.meta.url);

const TRANSLATIONS = Object.entries(
  JSON.parse(readFileSync(path.join(__dirname, "${translationFile}"), "utf8")),
).sort((left, right) => right[0].length - left[0].length);

const PLATFORM_PACKAGE_BY_TARGET = {
  "x86_64-unknown-linux-musl": "@openai/codex-linux-x64",
  "aarch64-unknown-linux-musl": "@openai/codex-linux-arm64",
  "x86_64-apple-darwin": "@openai/codex-darwin-x64",
  "aarch64-apple-darwin": "@openai/codex-darwin-arm64",
  "x86_64-pc-windows-msvc": "@openai/codex-win32-x64",
  "aarch64-pc-windows-msvc": "@openai/codex-win32-arm64"
};

const { platform, arch } = process;

let targetTriple = null;
switch (platform) {
  case "linux":
  case "android":
    switch (arch) {
      case "x64":
        targetTriple = "x86_64-unknown-linux-musl";
        break;
      case "arm64":
        targetTriple = "aarch64-unknown-linux-musl";
        break;
      default:
        break;
    }
    break;
  case "darwin":
    switch (arch) {
      case "x64":
        targetTriple = "x86_64-apple-darwin";
        break;
      case "arm64":
        targetTriple = "aarch64-apple-darwin";
        break;
      default:
        break;
    }
    break;
  case "win32":
    switch (arch) {
      case "x64":
        targetTriple = "x86_64-pc-windows-msvc";
        break;
      case "arm64":
        targetTriple = "aarch64-pc-windows-msvc";
        break;
      default:
        break;
    }
    break;
  default:
    break;
}

if (!targetTriple) {
  throw new Error(\`Unsupported platform: \${platform} (\${arch})\`);
}

const platformPackage = PLATFORM_PACKAGE_BY_TARGET[targetTriple];
if (!platformPackage) {
  throw new Error(\`Unsupported target triple: \${targetTriple}\`);
}

const codexBinaryName = process.platform === "win32" ? "codex.exe" : "codex";
const localVendorRoot = path.join(__dirname, "..", "vendor");
const localBinaryPath = path.join(localVendorRoot, targetTriple, "codex", codexBinaryName);

let vendorRoot;
try {
  const packageJsonPath = require.resolve(\`\${platformPackage}/package.json\`);
  vendorRoot = path.join(path.dirname(packageJsonPath), "vendor");
} catch {
  if (existsSync(localBinaryPath)) {
    vendorRoot = localVendorRoot;
  } else {
    const packageManager = detectPackageManager();
    const updateCommand =
      packageManager === "bun"
        ? "bun install -g @openai/codex@latest"
        : "npm install -g @openai/codex@latest";
    throw new Error(
      \`Missing optional dependency \${platformPackage}. Reinstall Codex: \${updateCommand}\`,
    );
  }
}

if (!vendorRoot) {
  const packageManager = detectPackageManager();
  const updateCommand =
    packageManager === "bun"
      ? "bun install -g @openai/codex@latest"
      : "npm install -g @openai/codex@latest";
  throw new Error(
    \`Missing optional dependency \${platformPackage}. Reinstall Codex: \${updateCommand}\`,
  );
}

const archRoot = path.join(vendorRoot, targetTriple);
const binaryPath = path.join(archRoot, "codex", codexBinaryName);

function getUpdatedPath(newDirs) {
  const pathSep = process.platform === "win32" ? ";" : ":";
  const existingPath = process.env.PATH || "";
  return [...newDirs, ...existingPath.split(pathSep).filter(Boolean)].join(pathSep);
}

function detectPackageManager() {
  const userAgent = process.env.npm_config_user_agent || "";
  if (/\\\\bbun\\//.test(userAgent)) {
    return "bun";
  }

  const execPath = process.env.npm_execpath || "";
  if (execPath.includes("bun")) {
    return "bun";
  }

  if (
    __dirname.includes(".bun/install/global") ||
    __dirname.includes(".bun\\\\install\\\\global")
  ) {
    return "bun";
  }

  return userAgent ? "npm" : null;
}

function translateText(text) {
  let result = text;
  for (const [english, chinese] of TRANSLATIONS) {
    result = result.split(english).join(chinese);
  }
  return result;
}

function shouldTranslate(args) {
  return args.includes("--help") || args.includes("-h") || args[0] === "help";
}

function shouldCaptureTranslatedOutput(args) {
  if (shouldTranslate(args)) {
    return true;
  }

  if (args.length === 0) {
    return false;
  }

  return ["login", "logout", "features", "completion"].includes(args[0]);
}

function runTranslatedCommand(args, env) {
  const result = spawnSync(binaryPath, args, {
    env,
    encoding: "utf8"
  });

  if (result.error) {
    console.error(result.error);
    process.exit(1);
  }

  if (result.stdout) {
    process.stdout.write(translateText(result.stdout));
  }

  if (result.stderr) {
    process.stderr.write(translateText(result.stderr));
  }

  if (result.signal) {
    process.kill(process.pid, result.signal);
    return;
  }

  process.exit(result.status ?? 1);
}

function maybePrintLaunchBanner(args) {
  if (
    args.length !== 0 ||
    process.env.CODEX_CN_LAUNCH_BANNER === "0" ||
    !process.stdout.isTTY ||
    !process.stdin.isTTY
  ) {
    return;
  }

  console.log("🀄 Codex-CLI-CN 已启用，正在启动交互界面...");
  console.log("已扩大覆盖帮助页、登录提示、常用状态输出与共享说明文本。");
}

const additionalDirs = [];
const pathDir = path.join(archRoot, "path");
if (existsSync(pathDir)) {
  additionalDirs.push(pathDir);
}

const env = { ...process.env, PATH: getUpdatedPath(additionalDirs) };
const packageManagerEnvVar =
  detectPackageManager() === "bun"
    ? "CODEX_MANAGED_BY_BUN"
    : "CODEX_MANAGED_BY_NPM";
env[packageManagerEnvVar] = "1";
env.CODEX_CN_PATCH = "${supportedVersion}";
env.CODEX_CN_BACKUP_FILE = "${backupFile}";

const args = process.argv.slice(2);
if (shouldCaptureTranslatedOutput(args)) {
  runTranslatedCommand(args, env);
}

maybePrintLaunchBanner(args);

const child = spawn(binaryPath, args, {
  stdio: "inherit",
  env
});

child.on("error", (err) => {
  console.error(err);
  process.exit(1);
});

const forwardSignal = (signal) => {
  if (child.killed) {
    return;
  }
  try {
    child.kill(signal);
  } catch {
    // ignore
  }
};

["SIGINT", "SIGTERM", "SIGHUP"].forEach((signal) => {
  process.on(signal, () => forwardSignal(signal));
});

const childResult = await new Promise((resolve) => {
  child.on("exit", (code, signal) => {
    if (signal) {
      resolve({ type: "signal", signal });
    } else {
      resolve({ type: "code", exitCode: code ?? 1 });
    }
  });
});

if (childResult.type === "signal") {
  process.kill(process.pid, childResult.signal);
} else {
  process.exit(childResult.exitCode);
}
`;
}
