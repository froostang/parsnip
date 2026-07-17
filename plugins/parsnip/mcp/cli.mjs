import { readFile } from "node:fs/promises";
import { CapsuleStore } from "./capsule-store.mjs";

function usage() {
  return "Usage: cli.mjs create CAPSULE.json | navigate SESSION_ID ACTION";
}

async function main(argv) {
  const [command, first, second] = argv;
  const store = new CapsuleStore();
  let result;
  if (command === "create" && first && second === undefined) {
    result = await store.create(JSON.parse(await readFile(first, "utf8")));
  } else if (command === "navigate" && first && second) {
    result = await store.navigate(first, second);
  } else {
    throw new Error(usage());
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

main(process.argv.slice(2)).catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 2;
});
