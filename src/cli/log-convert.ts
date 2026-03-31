#!/usr/bin/env bun

import { existsSync } from "fs";
import { resolve } from "path";

function main(): never {
  const scriptPath = resolve(
    import.meta.dir,
    "../../ai-log-converter/ai-log-converter.py",
  );
  if (!existsSync(scriptPath)) {
    console.error(`未找到 ai-log-converter 执行脚本: ${scriptPath}`);
    process.exit(1);
  }

  const pythonBin = process.env["PYTHON_BIN"] || "python3";
  const args = process.argv.slice(2);
  const proc = Bun.spawnSync({
    cmd: [pythonBin, scriptPath, ...args],
    stdio: ["inherit", "inherit", "inherit"],
  });

  if (proc.exitCode == null) {
    console.error("ai-log-converter 执行失败: 未获取退出码");
    process.exit(1);
  }

  process.exit(proc.exitCode);
}

main();
