"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  fallbackCatalog,
  loadCatalog,
  type CaseItem,
  type FilmKey,
  type PackageKey,
} from "./catalog";

type RouteKey = "city" | "mixed" | "highway";
type OwnershipKey = "1-2" | "3-4" | "5+";
type PriorityKey = "budget" | "balance" | "protection";
type BookingType = "inspection" | "installation";

const packages: Record<PackageKey, { name: string; eyebrow: string; coverage: number; zones: string[]; fit: string }> = {
  light: {
    name: "Light",
    eyebrow: "Точечная защита",
    coverage: 18,
    zones: ["Фары", "Полоса капота", "Зоны под ручками"],
    fit: "Для города и аккуратного бюджета",
  },
  optimal: {
    name: "Optimal",
    eyebrow: "Вся передняя часть",
    coverage: 46,
    zones: ["Бампер и капот", "Передние крылья", "Фары и зеркала"],
    fit: "Для города + трассы без переплаты",
  },
  max: {
    name: "Max",
    eyebrow: "Весь кузов",
    coverage: 100,
    zones: ["Все наружные ЛКП-зоны", "Фары и стойки", "Погрузочная зона"],
    fit: "Для новой машины и владения 5+ лет",
  },
};

const routeLabels: Record<RouteKey, string> = {
  city: "Город",
  mixed: "Город + трасса",
  highway: "В основном трасса",
};

const priorityLabels: Record<PriorityKey, string> = {
  budget: "Минимальный бюджет",
  balance: "Баланс цены и защиты",
  protection: "Максимум защиты",
};

const filmData: Record<FilmKey, { name: string; warranty: string }> = {
  pro: { name: "Quantum Pro", warranty: "7 лет" },
  rocket: { name: "Quantum Rocket", warranty: "5 лет" },
};

const defaultBookingDiscounts: Record<PackageKey, number> = {
  light: 5_000,
  optimal: 10_000,
  max: 15_000,
};

const formatPrice = (value: number) =>
  new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(value);

function getAutoRecommendation(route: RouteKey, ownership: OwnershipKey, priority: PriorityKey): PackageKey {
  if (priority === "protection" || ownership === "5+") return "max";
  if (priority === "budget" && route === "city" && ownership === "1-2") return "light";
  return "optimal";
}

function caseScore(item: CaseItem, brand: string, model: string, classId: string) {
  if (item.brand === brand && item.model === model) return 0;
  if (item.brand === brand) return 1;
  if (item.classId === classId) return 2;
  return 3;
}

export default function Home() {
  const [catalog, setCatalog] = useState(fallbackCatalog);
  const [clientName, setClientName] = useState("Михаил");
  const [managerName, setManagerName] = useState("Анастасия");
  const [vehicleId, setVehicleId] = useState("geely-monjaro");
  const [year, setYear] = useState("2025");
  const [route, setRoute] = useState<RouteKey>("mixed");
  const [ownership, setOwnership] = useState<OwnershipKey>("3-4");
  const [priority, setPriority] = useState<PriorityKey>("balance");
  const [film, setFilm] = useState<FilmKey>("pro");
  const [manualPackage, setManualPackage] = useState<PackageKey | null>(null);
  const [offerEnabled, setOfferEnabled] = useState(true);
  const [offerDiscounts, setOfferDiscounts] = useState(defaultBookingDiscounts);
  const [bookingType, setBookingType] = useState<BookingType>("inspection");
  const [bookingDate, setBookingDate] = useState("");
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [clientMode, setClientMode] = useState(false);
  const [toast, setToast] = useState("");
  const initialCasesHandled = useRef(false);

  useEffect(() => {
    loadCatalog().then(setCatalog);
    const params = new URLSearchParams(window.location.search);
    const paramRoute = params.get("route") as RouteKey | null;
    const paramOwnership = params.get("ownership") as OwnershipKey | null;
    const paramPriority = params.get("priority") as PriorityKey | null;
    const paramFilm = params.get("film") as FilmKey | null;
    const paramPackage = params.get("package") as PackageKey | null;
    const discountParam = (name: string, fallback: number) => {
      const value = params.get(name);
      return value === null ? fallback : Math.max(0, Number(value) || 0);
    };
    if (params.get("cases")) initialCasesHandled.current = true;
    window.queueMicrotask(() => {
      if (params.get("car")) setVehicleId(params.get("car") ?? "geely-monjaro");
      if (paramRoute && paramRoute in routeLabels) setRoute(paramRoute);
      if (paramOwnership && ["1-2", "3-4", "5+"].includes(paramOwnership)) setOwnership(paramOwnership);
      if (paramPriority && paramPriority in priorityLabels) setPriority(paramPriority);
      if (paramFilm && paramFilm in filmData) setFilm(paramFilm);
      if (paramPackage && paramPackage in packages) setManualPackage(paramPackage);
      if (params.get("offer") === "0") setOfferEnabled(false);
      setOfferDiscounts({
        light: discountParam("discountLight", defaultBookingDiscounts.light),
        optimal: discountParam("discountOptimal", defaultBookingDiscounts.optimal),
        max: discountParam("discountMax", defaultBookingDiscounts.max),
      });
      if (params.get("client")) setClientName(params.get("client") ?? "Клиент");
      if (params.get("year")) setYear(params.get("year") ?? "2025");
      if (params.get("cases")) setSelectedCaseIds((params.get("cases") ?? "").split(",").filter(Boolean).slice(0, 3));
      if (params.get("view") === "client") setClientMode(true);
    });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const activeVehicles = useMemo(
    () => catalog.vehicles.filter((item) => item.active).sort((a, b) =>
      `${a.brand} ${a.model}`.localeCompare(`${b.brand} ${b.model}`, "ru")),
    [catalog.vehicles],
  );
  const car = activeVehicles.find((item) => item.id === vehicleId) ?? activeVehicles[0] ?? fallbackCatalog.vehicles[0];
  const brands = useMemo(() => [...new Set(activeVehicles.map((item) => item.brand))].sort((a, b) => a.localeCompare(b, "ru")), [activeVehicles]);
  const brandVehicles = activeVehicles.filter((item) => item.brand === car.brand);
  const priceClass = catalog.classes.find((item) => item.id === car.classId) ?? fallbackCatalog.classes[2];
  const activeCases = useMemo(() => catalog.cases.filter((item) => item.active), [catalog.cases]);
  const sortedCases = useMemo(
    () => [...activeCases].sort((a, b) => caseScore(a, car.brand, car.model, car.classId) - caseScore(b, car.brand, car.model, car.classId)),
    [activeCases, car.brand, car.classId, car.model],
  );

  useEffect(() => {
    if (initialCasesHandled.current || !sortedCases.length) return;
    setSelectedCaseIds([sortedCases[0].id]);
    initialCasesHandled.current = true;
  }, [sortedCases]);

  const selectedCases = selectedCaseIds
    .map((id) => activeCases.find((item) => item.id === id))
    .filter((item): item is CaseItem => Boolean(item));
  const autoRecommendation = getAutoRecommendation(route, ownership, priority);
  const recommendation = manualPackage ?? autoRecommendation;
  const filmInfo = filmData[film];
  const prices = priceClass.prices[film];
  const bookingDiscount = offerDiscounts[recommendation];
  const bookingPrice = Math.max(0, prices[recommendation] - bookingDiscount);

  const recommendationReason = useMemo(() => {
    if (recommendation === "max") {
      return `Вы планируете владеть автомобилем ${ownership === "5+" ? "пять лет или дольше" : "достаточно долго"}, поэтому полная оклейка лучше всего сохраняет заводское ЛКП и внешний вид.`;
    }
    if (recommendation === "light") {
      return "Для преимущественно городской езды достаточно закрыть самые уязвимые и заметные зоны — без стоимости полной передней части.";
    }
    return `${route === "highway" ? "На трассе" : "В смешанном режиме"} основной удар принимают капот, бампер, крылья и зеркала. Optimal закрывает их без стоимости полной оклейки.`;
  }, [ownership, recommendation, route]);

  const casesText = selectedCases.length
    ? `\n\nПохожие работы:\n${selectedCases.map((item) => `• ${item.title} — ${item.result}`).join("\n")}`
    : "";
  const bookingText = offerEnabled && bookingDate
    ? `\n\nВыбрана дата: ${bookingDate} · ${bookingType === "inspection" ? "осмотр и расчёт" : "оклейка"}.`
    : "";
  const offerText = offerEnabled
    ? `\n\nПри бронировании даты в течение 7 дней скидка на ${packages[recommendation].name} — ${formatPrice(bookingDiscount)} ₽. Цена с учётом скидки — ${formatPrice(bookingPrice)} ₽.`
    : "";
  const proposalText = `${clientName || "Добрый день"}, подготовили три варианта защиты для ${car.brand} ${car.model} ${year}:\n\nLight — ${formatPrice(prices.light)} ₽\nOptimal — ${formatPrice(prices.optimal)} ₽\nMax — ${formatPrice(prices.max)} ₽\n\nРекомендуем ${packages[recommendation].name}: ${recommendationReason}${offerText}\n\nМатериал: ${filmInfo.name}, гарантия ${filmInfo.warranty}.${casesText}${bookingText}\n\nЦены предварительные — точная смета после бесплатного осмотра.`;

  async function copyText(text: string, success: string) {
    try {
      await navigator.clipboard.writeText(text);
      setToast(success);
    } catch {
      setToast("Не удалось скопировать — попробуйте ещё раз");
    }
  }

  async function copyShareLink() {
    const url = new URL(window.location.href);
    url.search = new URLSearchParams({
      view: "client",
      client: clientName,
      car: car.id,
      year,
      route,
      ownership,
      priority,
      film,
      package: recommendation,
      offer: offerEnabled ? "1" : "0",
      discountLight: String(offerDiscounts.light),
      discountOptimal: String(offerDiscounts.optimal),
      discountMax: String(offerDiscounts.max),
      cases: selectedCaseIds.join(","),
    }).toString();
    await copyText(url.toString(), "Ссылка на клиентскую версию скопирована");
  }

  function selectVehicle(id: string) {
    const nextCar = activeVehicles.find((item) => item.id === id);
    setVehicleId(id);
    setManualPackage(null);
    if (!nextCar) return;
    const bestCase = activeCases
      .slice()
      .sort((a, b) => caseScore(a, nextCar.brand, nextCar.model, nextCar.classId) - caseScore(b, nextCar.brand, nextCar.model, nextCar.classId))[0];
    setSelectedCaseIds(bestCase ? [bestCase.id] : []);
  }

  function toggleCase(id: string) {
    setSelectedCaseIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= 3) {
        setToast("В одно КП можно добавить не больше 3 кейсов");
        return current;
      }
      return [...current, id];
    });
  }

  function reserveDate() {
    if (!bookingDate) {
      setToast("Сначала выберите дату осмотра или оклейки");
      return;
    }
    const formattedDate = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" })
      .format(new Date(`${bookingDate}T12:00:00`));
    setToast(`${bookingType === "inspection" ? "Осмотр и расчёт" : "Оклейка"} на ${formattedDate} забронированы · скидка ${formatPrice(bookingDiscount)} ₽ закреплена`);
  }

  return (
    <main className={clientMode ? "page client-mode" : "page"}>
      <header className="site-header no-print">
        <a className="brand" href="#top" aria-label="Левша — в начало">
          <span className="brand-mark">Л</span>
          <span><strong>ЛЕВША</strong><small>PPF proposal lab</small></span>
        </a>
        <div className="header-actions">
          <span className="demo-chip"><i /> Демонстрационный прототип</span>
          {clientMode ? (
            <button className="ghost-button" onClick={() => setClientMode(false)}>← Вернуться в конструктор</button>
          ) : (
            <button className="ghost-button" onClick={() => setClientMode(true)}>Предпросмотр клиента</button>
          )}
        </div>
      </header>

      {!clientMode && (
        <section className="hero no-print" id="top">
          <div className="hero-copy">
            <div className="section-label">КП за 3 минуты</div>
            <h1>Соберите предложение, которое помогает выбрать</h1>
            <p>Выберите авто, условия эксплуатации и 1–3 похожих кейса — цены и клиентская версия соберутся автоматически.</p>
            <button className="primary-cta" onClick={() => document.getElementById("builder")?.scrollIntoView({ behavior: "smooth" })}>
              Собрать тестовое КП <span>↓</span>
            </button>
          </div>
          <div className="hero-outcome" aria-label="Результат работы конструктора">
            <div className="outcome-orbit orbit-one" /><div className="outcome-orbit orbit-two" />
            <div className="outcome-card">
              <span className="outcome-kicker">Готовое предложение</span>
              <strong>3 пакета</strong><em>до 3 похожих кейсов</em>
              <div className="outcome-line"><span /><span /><span /></div>
              <small>Можно отправить ссылкой или PDF</small>
            </div>
          </div>
          <div className="hero-stats">
            <div><strong>{activeVehicles.length}</strong><span>моделей авто</span></div>
            <div><strong>{activeCases.length}</strong><span>кейсов в базе</span></div>
            <div><strong>{catalog.classes.length}</strong><span>ценовых классов</span></div>
          </div>
        </section>
      )}

      <section className="builder-section" id="builder">
        {!clientMode && (
          <aside className="control-panel no-print">
            <div className="panel-heading">
              <span>01</span><div><h2>Вводные клиента</h2><p>КП обновляется автоматически</p></div>
            </div>
            <div className="form-stack">
              <label className="field">
                <span>Имя клиента</span>
                <input value={clientName} onChange={(event) => setClientName(event.target.value)} placeholder="Например, Михаил" />
              </label>

              <fieldset className="field">
                <legend>Автомобиль</legend>
                <div className="vehicle-select-grid">
                  <label><span>Марка</span><select value={car.brand} onChange={(event) => {
                    const first = activeVehicles.find((item) => item.brand === event.target.value);
                    if (first) selectVehicle(first.id);
                  }}>{brands.map((brand) => <option key={brand}>{brand}</option>)}</select></label>
                  <label><span>Модель</span><select value={car.id} onChange={(event) => selectVehicle(event.target.value)}>
                    {brandVehicles.map((item) => <option key={item.id} value={item.id}>{item.model}</option>)}
                  </select></label>
                </div>
                <div className="class-card">
                  <span>Ценовой класс {priceClass.id}</span>
                  <strong>{priceClass.name}</strong>
                  <small>{priceClass.description}</small>
                </div>
              </fieldset>

              <label className="field"><span>Год выпуска</span><select value={year} onChange={(event) => setYear(event.target.value)}>
                {Array.from({ length: 12 }, (_, index) => String(2026 - index)).map((item) => <option key={item}>{item}</option>)}
              </select></label>

              <SegmentedField<RouteKey> label="Где ездит" value={route} options={routeLabels} onChange={(value) => { setRoute(value); setManualPackage(null); }} />
              <SegmentedField<OwnershipKey> label="Сколько планирует владеть" value={ownership} options={{ "1-2": "1–2 года", "3-4": "3–4 года", "5+": "5+ лет" }} onChange={(value) => { setOwnership(value); setManualPackage(null); }} />

              <label className="field"><span>Главный приоритет</span><select value={priority} onChange={(event) => { setPriority(event.target.value as PriorityKey); setManualPackage(null); }}>
                {(Object.keys(priorityLabels) as PriorityKey[]).map((key) => <option key={key} value={key}>{priorityLabels[key]}</option>)}
              </select></label>

              <fieldset className="field"><legend>Материал</legend><div className="film-picker">
                {(Object.keys(filmData) as FilmKey[]).map((key) => <button key={key} className={film === key ? "film-option active" : "film-option"} onClick={() => setFilm(key)} type="button">
                  <span>{filmData[key].name}</span><small>Гарантия {filmData[key].warranty}</small>
                </button>)}
              </div></fieldset>

              <fieldset className="field offer-settings">
                <legend>Акционный блок</legend>
                <label className="offer-switch">
                  <input type="checkbox" checked={offerEnabled} onChange={(event) => setOfferEnabled(event.target.checked)} />
                  <span><strong>{offerEnabled ? "Акция включена" : "Акция выключена"}</strong><small>Показывать клиенту предложение на 7 дней</small></span>
                  <i aria-hidden="true" />
                </label>
                {offerEnabled && <div className="discount-settings">
                  {(Object.keys(packages) as PackageKey[]).map((key) => <label key={key}>
                    <span>{packages[key].name}</span>
                    <div><input type="number" min="0" step="1000" value={offerDiscounts[key]} onChange={(event) => setOfferDiscounts((current) => ({ ...current, [key]: Math.max(0, Number(event.target.value) || 0) }))} /><b>₽</b></div>
                  </label>)}
                </div>}
              </fieldset>

              <fieldset className="field case-selector"><legend>Кейсы в КП <b>{selectedCaseIds.length}/3</b></legend>
                <p>Сначала — кейсы той же модели, марки и класса.</p>
                <div className="case-selector-list">
                  {sortedCases.map((item) => {
                    const checked = selectedCaseIds.includes(item.id);
                    return <label className={checked ? "case-selector-card active" : "case-selector-card"} key={item.id}>
                      <input type="checkbox" checked={checked} disabled={!checked && selectedCaseIds.length >= 3} onChange={() => toggleCase(item.id)} />
                      <span><strong>{item.brand} {item.model}</strong><small>{packages[item.packageKey].name} · {item.result}</small></span>
                    </label>;
                  })}
                </div>
              </fieldset>

              <label className="field"><span>Менеджер</span><input value={managerName} onChange={(event) => setManagerName(event.target.value)} /></label>
            </div>
            <button className="generate-button" onClick={() => { document.getElementById("proposal")?.scrollIntoView({ behavior: "smooth" }); setToast("КП обновлено — можно отправлять клиенту"); }}>
              Обновить предложение <span>↗</span>
            </button>
            <p className="data-note">Источник: {catalog.sourceLabel}{catalog.updatedAt ? ` · ${catalog.updatedAt}` : ""}. Все данные прототипа выдуманы.</p>
          </aside>
        )}

        <article className="proposal" id="proposal">
          <div className="proposal-toolbar no-print"><div><i /> <span>{clientMode ? "Клиентская версия" : "Живой предпросмотр КП"}</span></div><span>Расчёт по классу {priceClass.id}</span></div>
          <section className="proposal-cover">
            <div className="cover-copy">
              <span className="proposal-label">Персональный расчёт защиты</span>
              <h2>{clientName || "Клиент"}, три варианта для {car.brand} {car.model}</h2>
              <p>Подобрали варианты под ваш режим езды, срок владения и бюджет.</p>
              <div className="context-chips"><span>{year} год</span><span>{routeLabels[route]}</span><span>{ownership} владения</span><span>Класс {priceClass.id}</span></div>
            </div>
            <div className={`car-stage class-${priceClass.id.toLowerCase()}`} aria-label={`${car.brand} ${car.model}`}>
              <div className="stage-glow" /><div className="car-meta"><span>{car.brand}</span><strong>{car.model}</strong><small>{car.body}</small></div>
              <div className="car-shape" aria-hidden="true"><div className="car-roof" /><div className="car-body" /><div className="wheel wheel-left" /><div className="wheel wheel-right" /><div className="film-sheen" /></div>
              <div className="protection-badge"><span>{priceClass.id}</span> класс<br />кузова</div>
            </div>
          </section>

          <section className="proposal-body">
            <div className="section-intro"><div><span className="step-number">01</span><h3>Выберите объём защиты</h3></div><p>Цена берётся из матрицы класса {priceClass.id}; вручную считать площадь автомобиля не нужно.</p></div>
            <div className="package-grid">
              {(Object.keys(packages) as PackageKey[]).map((key) => {
                const item = packages[key];
                const isRecommended = recommendation === key;
                return <div className={isRecommended ? "package-card recommended" : "package-card"} key={key}>
                  {isRecommended && <div className="recommendation-ribbon">Рекомендуем</div>}
                  <div className="package-top"><span>{item.eyebrow}</span><strong>{item.name}</strong></div>
                  <div className="coverage-meter" aria-label={`Покрытие кузова ${item.coverage}%`}><span style={{ width: `${item.coverage}%` }} /></div>
                  <div className="package-price"><strong>{formatPrice(prices[key])} ₽</strong><small>демо-цена · класс {priceClass.id}</small></div>
                  <ul>{item.zones.map((zone) => <li key={zone}><i>✓</i>{zone}</li>)}</ul>
                  <div className="package-meta"><span>{priceClass.durations[key]}</span><span>{filmInfo.warranty} гарантии</span></div>
                  <p>{item.fit}</p>
                  <button type="button" onClick={() => setManualPackage(key)} className={isRecommended ? "package-button active" : "package-button"}>{isRecommended ? "Выбрано менеджером" : "Рекомендовать этот"}</button>
                </div>;
              })}
            </div>

            {offerEnabled && <section className="limited-offer">
              <div className="limited-offer-copy">
                <span className="limited-badge"><i /> Ограниченное предложение · 7 дней</span>
                <div className="limited-offer-heading">
                  <div>
                    <h3>Закрепите скидку за выбранным тарифом</h3>
                    <p>Выберите дату в течение 7 дней. Сам осмотр или оклейка могут пройти позже.</p>
                  </div>
                  <div className="discount-burst">
                    <small>Скидка на {packages[recommendation].name}</small>
                    <strong>−{formatPrice(bookingDiscount)} ₽</strong>
                  </div>
                </div>
              </div>

              <div className="booking-panel">
                <div className="booking-kind" aria-label="Что забронировать">
                  <button type="button" className={bookingType === "inspection" ? "active" : ""} onClick={() => setBookingType("inspection")}>Осмотр и расчёт</button>
                  <button type="button" className={bookingType === "installation" ? "active" : ""} onClick={() => setBookingType("installation")}>Дату оклейки</button>
                </div>
                <label className="booking-date">
                  <span>Выберите дату</span>
                  <input type="date" value={bookingDate} onChange={(event) => setBookingDate(event.target.value)} />
                </label>
                <div className="booking-price">
                  <span>Цена после брони</span>
                  <div><s>{formatPrice(prices[recommendation])} ₽</s><strong>{formatPrice(bookingPrice)} ₽</strong></div>
                </div>
                <button type="button" className="booking-cta" onClick={reserveDate}>
                  <span>{bookingType === "inspection" ? "Забронировать осмотр и расчёт" : "Забронировать дату оклейки"}</span>
                  <b>−{formatPrice(bookingDiscount)} ₽</b>
                </button>
                <small className="booking-note">Скидка закрепляется за автомобилем и выбранным тарифом.</small>
              </div>
            </section>}

            <section className="expert-choice">
              <div className="expert-avatar">{(managerName || "Л").charAt(0).toUpperCase()}</div>
              <div className="expert-copy"><span>Рекомендация {managerName || "специалиста Левши"}</span><h3>Я бы начал с {packages[recommendation].name}</h3><p>{recommendationReason}</p>
                {manualPackage && manualPackage !== autoRecommendation && <button className="reset-choice no-print" onClick={() => setManualPackage(null)}>Вернуть автоматическую рекомендацию</button>}
              </div>
              <div className="expert-price"><small>Итого</small><strong>{formatPrice(prices[recommendation])} ₽</strong><span>{priceClass.durations[recommendation]}</span></div>
            </section>

            <section className="included-section">
              <div className="section-intro compact"><div><span className="step-number">02</span><h3>В каждом варианте</h3></div></div>
              <div className="included-grid">
                <div><span>01</span><strong>Осмотр ЛКП</strong><p>Фиксируем состояние до начала работ</p></div><div><span>02</span><strong>Подвороты краёв</strong><p>Плёнка незаметна на кузове</p></div><div><span>03</span><strong>Паспорт защиты</strong><p>Материал, зоны и гарантия в одном документе</p></div><div><span>04</span><strong>Мойка + чекап</strong><p>Через 30 дней после оклейки</p></div>
              </div>
            </section>

            {selectedCases.length > 0 && <section className="selected-cases-section">
              <div className="section-intro compact"><div><span className="step-number">03</span><h3>Похожие задачи</h3></div><p>Менеджер выбрал эти кейсы специально для вашего КП.</p></div>
              <div className="selected-cases-grid">
                {selectedCases.map((item) => <article className="case-highlight" key={item.id}>
                  <div className="case-visual"><span className="fiction-label">Выдуманный кейс</span><div className="case-car-name"><small>{item.brand}</small><strong>{item.model}</strong></div><div className="case-film-line" /></div>
                  <div className="case-copy"><span>{item.title}</span><h3>{item.owner} · пакет {packages[item.packageKey].name}</h3><p>{item.story}</p><div className="case-result"><i>✓</i>{item.result}</div></div>
                </article>)}
              </div>
            </section>}

            <section className="next-step"><div><span className="step-number">{selectedCases.length ? "04" : "03"}</span><h3>Точная смета — после бесплатного осмотра</h3><p>40 минут в студии: посмотрим ЛКП, покажем материал и зафиксируем цену.</p></div><div className="slot-picker"><button type="button" onClick={() => setToast("Слот завтра в 11:00 выбран")}>Завтра · 11:00</button><button type="button" onClick={() => setToast("Слот в четверг в 18:30 выбран")}>Четверг · 18:30</button></div></section>
            <div className="legal-note">* Все цены и кейсы на этой странице выдуманы для демонстрации прототипа. Это не публичная оферта.</div>
          </section>

          <div className="proposal-actions no-print"><button className="action-primary" onClick={() => copyText(proposalText, "Сообщение для клиента скопировано")}>Скопировать сообщение</button><button onClick={copyShareLink}>Скопировать ссылку</button><button onClick={() => window.print()}>Сохранить в PDF</button></div>
        </article>
      </section>

      {!clientMode && <section className="cases-gallery no-print">
        <div className="gallery-heading"><span className="section-label">Отдельная база доказательств</span><h2>Кейсы можно переиспользовать в любом КП</h2><p>Добавили работу в таблицу один раз — менеджеры выбирают её галочкой для подходящего клиента.</p></div>
        <div className="gallery-grid">{activeCases.slice(0, 4).map((item, index) => <article className={`gallery-card gallery-${index + 1}`} key={item.id}><span>ВЫДУМАННЫЙ КЕЙС</span><div className="gallery-model"><small>{item.brand}</small><strong>{item.model}</strong></div><div className="gallery-footer"><div><small>Пакет</small><strong>{packages[item.packageKey].name}</strong></div><div><small>Стоимость</small><strong>{formatPrice(item.price)} ₽</strong></div></div></article>)}</div>
      </section>}

      <footer className="site-footer no-print"><div className="brand footer-brand"><span className="brand-mark">Л</span><span><strong>ЛЕВША</strong><small>PPF proposal lab</small></span></div><p>Интерактивный прототип конструктора КП · Самара · 2026</p></footer>
      {toast && <div className="toast" role="status">✓ {toast}</div>}
    </main>
  );
}

function SegmentedField<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: Record<T, string>; onChange: (value: T) => void }) {
  return <fieldset className="field"><legend>{label}</legend><div className="segmented-control">{(Object.keys(options) as T[]).map((key) => <button key={key} className={value === key ? "active" : ""} onClick={() => onChange(key)} type="button">{options[key]}</button>)}</div></fieldset>;
}
