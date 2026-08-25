import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("renders the PPF proposal constructor", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Левша · Конструктор PPF-предложений/i);
  assert.match(html, /Соберите предложение, которое помогает выбрать/i);
  assert.match(html, /Geely/i);
  assert.match(html, /Ценовой класс/i);
  assert.match(html, /Кейсы в КП/i);
  assert.match(html, /Акционный блок/i);
  assert.match(html, /Ограниченное предложение · 7 дней/i);
  assert.match(html, /Забронировать осмотр и расчёт/i);
  assert.match(html, /value="10000"/i);
  assert.match(html, /Все цены и кейсы.+выдуманы/i);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
});

test("renders a client link with proposal content", async () => {
  const response = await render("/?view=client&client=Анна&car=bmw-x5&package=max&cases=case-bmw-x5-max");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /Персональный расчёт защиты/i);
  assert.match(html, /Light/i);
  assert.match(html, /Optimal/i);
  assert.match(html, /Max/i);
});

test("catalog tables have enough models and valid class references", async () => {
  const vehiclesText = await readFile(new URL("../public/data/vehicles.csv", import.meta.url), "utf8");
  const classesText = await readFile(new URL("../public/data/price-classes.csv", import.meta.url), "utf8");
  const casesText = await readFile(new URL("../public/data/cases.csv", import.meta.url), "utf8");
  const vehicleRows = vehiclesText.trim().split(/\r?\n/).slice(1);
  const classIds = new Set(classesText.trim().split(/\r?\n/).slice(1).map((row) => row.split(",")[0]));
  assert.ok(vehicleRows.length >= 180, `expected at least 180 vehicles, got ${vehicleRows.length}`);
  for (const row of vehicleRows) assert.ok(classIds.has(row.split(",")[4]), `unknown vehicle class in ${row}`);
  assert.ok(casesText.trim().split(/\r?\n/).slice(1).length >= 12);
});
