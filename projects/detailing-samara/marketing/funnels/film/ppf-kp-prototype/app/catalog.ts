export type PackageKey = "light" | "optimal" | "max";
export type FilmKey = "pro" | "rocket";

export type Vehicle = {
  id: string;
  brand: string;
  model: string;
  body: string;
  classId: string;
  active: boolean;
};

export type PriceClass = {
  id: string;
  name: string;
  description: string;
  prices: Record<FilmKey, Record<PackageKey, number>>;
  durations: Record<PackageKey, string>;
};

export type CaseItem = {
  id: string;
  title: string;
  brand: string;
  model: string;
  classId: string;
  packageKey: PackageKey;
  owner: string;
  story: string;
  result: string;
  price: number;
  active: boolean;
};

export type Catalog = {
  vehicles: Vehicle[];
  classes: PriceClass[];
  cases: CaseItem[];
  sourceLabel: string;
  updatedAt: string;
};

const classA: PriceClass = {
  id: "A",
  name: "Компакт",
  description: "Компактные седаны и хэтчбеки",
  prices: {
    pro: { light: 23_900, optimal: 64_900, max: 159_000 },
    rocket: { light: 20_900, optimal: 56_900, max: 139_000 },
  },
  durations: { light: "1 день", optimal: "2 дня", max: "3–4 дня" },
};

const classB: PriceClass = {
  id: "B",
  name: "Стандарт",
  description: "Средние седаны и компактные кроссоверы",
  prices: {
    pro: { light: 27_900, optimal: 79_900, max: 199_000 },
    rocket: { light: 24_900, optimal: 69_900, max: 175_000 },
  },
  durations: { light: "1 день", optimal: "2 дня", max: "4 дня" },
};

const classC: PriceClass = {
  id: "C",
  name: "Большой",
  description: "Бизнес-седаны и среднеразмерные SUV",
  prices: {
    pro: { light: 32_900, optimal: 94_900, max: 239_000 },
    rocket: { light: 28_900, optimal: 82_900, max: 209_000 },
  },
  durations: { light: "1 день", optimal: "2 дня", max: "4–5 дней" },
};

const classD: PriceClass = {
  id: "D",
  name: "XL",
  description: "Большие SUV, минивэны и длинные кузова",
  prices: {
    pro: { light: 38_900, optimal: 114_900, max: 289_000 },
    rocket: { light: 33_900, optimal: 99_900, max: 249_000 },
  },
  durations: { light: "1 день", optimal: "2–3 дня", max: "5 дней" },
};

const classE: PriceClass = {
  id: "E",
  name: "XXL / сложный кузов",
  description: "Полноразмерные и конструктивно сложные кузова",
  prices: {
    pro: { light: 44_900, optimal: 134_900, max: 349_000 },
    rocket: { light: 38_900, optimal: 117_900, max: 305_000 },
  },
  durations: { light: "1–2 дня", optimal: "3 дня", max: "5–6 дней" },
};

export const fallbackCatalog: Catalog = {
  sourceLabel: "локальная CSV-база",
  updatedAt: "21.07.2026",
  classes: [classA, classB, classC, classD, classE],
  vehicles: [
    { id: "geely-monjaro", brand: "Geely", model: "Monjaro", body: "Среднеразмерный кроссовер", classId: "C", active: true },
    { id: "haval-jolion", brand: "Haval", model: "Jolion", body: "Компактный кроссовер", classId: "B", active: true },
    { id: "toyota-camry", brand: "Toyota", model: "Camry", body: "Бизнес-седан", classId: "C", active: true },
    { id: "bmw-x5", brand: "BMW", model: "X5", body: "Большой кроссовер", classId: "D", active: true },
  ],
  cases: [
    {
      id: "case-monjaro-optimal",
      title: "Geely Monjaro: защита нового авто",
      brand: "Geely",
      model: "Monjaro",
      classId: "C",
      packageKey: "optimal",
      owner: "Михаил, 41 год",
      story: "Новый автомобиль, смешанный режим города и трассы, план владения — четыре года.",
      result: "Закрыли всю переднюю часть за 2 дня",
      price: 94_900,
      active: true,
    },
  ],
};

type Row = Record<string, string>;

function parseCsv(text: string): Row[] {
  const delimiter = text.split(/\r?\n/, 1)[0]?.includes(";") ? ";" : ",";
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === delimiter && !quoted) {
      row.push(cell.trim());
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell.trim());
      if (row.some(Boolean)) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  row.push(cell.trim());
  if (row.some(Boolean)) rows.push(row);

  const headers = (rows.shift() ?? []).map((header) => header.replace(/^\uFEFF/, ""));
  return rows.map((values) =>
    Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""])),
  );
}

const isActive = (value: string) => !["0", "false", "нет", "off"].includes(value.toLowerCase());
const toNumber = (value: string) => Number(value.replace(/[^0-9.-]/g, "")) || 0;

async function fetchText(url: string) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Не удалось загрузить ${url}`);
  return response.text();
}

export async function loadCatalog(): Promise<Catalog> {
  try {
    const configResponse = await fetch("/data/config.json", { cache: "no-store" });
    if (!configResponse.ok) throw new Error("Не удалось загрузить конфигурацию базы");
    const config = (await configResponse.json()) as {
      vehiclesUrl: string;
      classesUrl: string;
      casesUrl: string;
      sourceLabel?: string;
      updatedAt?: string;
    };
    const [vehicleText, classText, caseText] = await Promise.all([
      fetchText(config.vehiclesUrl),
      fetchText(config.classesUrl),
      fetchText(config.casesUrl),
    ]);

    const vehicles = parseCsv(vehicleText).map((row) => ({
      id: row.id,
      brand: row.brand,
      model: row.model,
      body: row.body,
      classId: row.class_id,
      active: isActive(row.active),
    }));

    const classes = parseCsv(classText).map((row) => ({
      id: row.id,
      name: row.name,
      description: row.description,
      prices: {
        pro: {
          light: toNumber(row.pro_light),
          optimal: toNumber(row.pro_optimal),
          max: toNumber(row.pro_max),
        },
        rocket: {
          light: toNumber(row.rocket_light),
          optimal: toNumber(row.rocket_optimal),
          max: toNumber(row.rocket_max),
        },
      },
      durations: {
        light: row.light_duration,
        optimal: row.optimal_duration,
        max: row.max_duration,
      },
    })) as PriceClass[];

    const cases = parseCsv(caseText).map((row) => ({
      id: row.id,
      title: row.title,
      brand: row.brand,
      model: row.model,
      classId: row.class_id,
      packageKey: row.package as PackageKey,
      owner: row.owner,
      story: row.story,
      result: row.result,
      price: toNumber(row.price),
      active: isActive(row.active),
    }));

    if (!vehicles.length || !classes.length || !cases.length) throw new Error("База данных пуста");
    return {
      vehicles,
      classes,
      cases,
      sourceLabel: config.sourceLabel ?? "внешняя таблица",
      updatedAt: config.updatedAt ?? "",
    };
  } catch (error) {
    console.warn("Используем резервный каталог", error);
    return fallbackCatalog;
  }
}
