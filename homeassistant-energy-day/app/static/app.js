const state = {
  config: {
    solar_entities: [],
    grid_import_entity: "",
    grid_export_entity: "",
  },
  entities: [],
  selectedDay: new Date(),
  selectedMonth: new Date(),
};

const elements = {
  rangeLabel: document.querySelector("#range-label"),
  dayPicker: document.querySelector("#day-picker"),
  previousDay: document.querySelector("#previous-day"),
  nextDay: document.querySelector("#next-day"),
  today: document.querySelector("#today"),
  monthPicker: document.querySelector("#month-picker"),
  houseConsumption: document.querySelector("#house-consumption"),
  solarYield: document.querySelector("#solar-yield"),
  gridImport: document.querySelector("#grid-import"),
  gridExport: document.querySelector("#grid-export"),
  autarky: document.querySelector("#autarky"),
  selfConsumption: document.querySelector("#self-consumption"),
  calculationWindow: document.querySelector("#calculation-window"),
  dayBars: document.querySelector("#day-bars"),
  warnings: document.querySelector("#warnings"),
  solarSelect: document.querySelector("#solar-select"),
  gridImportSelect: document.querySelector("#grid-import-select"),
  gridExportSelect: document.querySelector("#grid-export-select"),
  solarList: document.querySelector("#solar-list"),
  addSolar: document.querySelector("#add-solar"),
  saveConfig: document.querySelector("#save-config"),
  saveStatus: document.querySelector("#save-status"),
  refreshEntities: document.querySelector("#refresh-entities"),
  monthChart: document.querySelector("#month-chart"),
  monthSummary: document.querySelector("#month-summary"),
  sourceTable: document.querySelector("#source-table"),
  solarItemTemplate: document.querySelector("#solar-item-template"),
};

function apiUrl(path) {
  return new URL(`api/${path}`, window.location.href);
}

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }
  return response.json();
}

function isoDate(date) {
  const copy = new Date(date);
  copy.setMinutes(copy.getMinutes() - copy.getTimezoneOffset());
  return copy.toISOString().slice(0, 10);
}

function isoMonth(date) {
  return isoDate(date).slice(0, 7);
}

function parseLocalDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatKwh(value) {
  return `${Number(value || 0).toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} kWh`;
}

function formatPercent(value) {
  return `${Number(value || 0).toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} %`;
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function entityLabel(entityId) {
  const entity = state.entities.find((item) => item.entity_id === entityId);
  return entity ? `${entity.name} (${entity.entity_id})` : entityId;
}

function setStatus(message) {
  elements.saveStatus.textContent = message;
}

function option(entity) {
  const item = document.createElement("option");
  item.value = entity.entity_id;
  item.textContent = `${entity.name} - ${entity.entity_id}`;
  return item;
}

function renderEntitySelects() {
  const selects = [elements.solarSelect, elements.gridImportSelect, elements.gridExportSelect];
  for (const select of selects) {
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Entity auswählen";
    select.append(empty);
    for (const entity of state.entities) {
      select.append(option(entity));
    }
  }

  elements.gridImportSelect.value = state.config.grid_import_entity;
  elements.gridExportSelect.value = state.config.grid_export_entity;
  renderSolarList();
}

function renderSolarList() {
  elements.solarList.replaceChildren();
  for (const entityId of state.config.solar_entities) {
    const item = elements.solarItemTemplate.content.firstElementChild.cloneNode(true);
    item.querySelector("span").textContent = entityLabel(entityId);
    item.querySelector("button").addEventListener("click", () => {
      state.config.solar_entities = state.config.solar_entities.filter((candidate) => candidate !== entityId);
      renderSolarList();
    });
    elements.solarList.append(item);
  }
}

function renderDayBars(day) {
  const values = [
    ["Solarertrag", day.solar_yield_kwh, "var(--yellow)"],
    ["Netzbezug", day.grid_import_kwh, "var(--blue)"],
    ["Netzeinspeisung", day.grid_export_kwh, "var(--coral)"],
    ["Eigenverbrauch", day.self_consumed_kwh, "var(--green)"],
  ];
  const max = Math.max(...values.map((item) => item[1]), 1);
  elements.dayBars.replaceChildren();

  for (const [label, value, color] of values) {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.style.setProperty("--accent", color);
    row.innerHTML = `
      <span>${label}</span>
      <div class="track"><div class="fill" style="--value: ${(value / max) * 100}%"></div></div>
      <strong>${formatKwh(value)}</strong>
    `;
    elements.dayBars.append(row);
  }
}

function renderWarnings(day) {
  if (!day.warnings?.length) {
    elements.warnings.hidden = true;
    elements.warnings.textContent = "";
    return;
  }
  elements.warnings.hidden = false;
  elements.warnings.replaceChildren();
  for (const warning of day.warnings) {
    const line = document.createElement("div");
    line.textContent = warning;
    elements.warnings.append(line);
  }
}

function sourceRows(day) {
  const solarRows = (day.sources?.solar || []).map((item) => ["Solar", item]);
  return [
    ...solarRows,
    ["Netzbezug", day.sources?.grid_import],
    ["Netzeinspeisung", day.sources?.grid_export],
  ].filter(([, item]) => item);
}

function renderSources(day) {
  elements.sourceTable.replaceChildren();
  for (const [type, source] of sourceRows(day)) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${type}</td>
      <td>${source.entity_id}</td>
      <td>${formatKwh(source.delta_kwh)}</td>
      <td>${source.sample_count}</td>
      <td>${source.reset_count}</td>
    `;
    elements.sourceTable.append(row);
  }
}

function renderDay(day) {
  elements.houseConsumption.textContent = formatKwh(day.house_consumption_kwh);
  elements.solarYield.textContent = formatKwh(day.solar_yield_kwh);
  elements.gridImport.textContent = formatKwh(day.grid_import_kwh);
  elements.gridExport.textContent = formatKwh(day.grid_export_kwh);
  elements.autarky.textContent = formatPercent(day.autarky_percent);
  elements.selfConsumption.textContent = formatPercent(day.self_consumption_percent);
  elements.rangeLabel.textContent = new Intl.DateTimeFormat("de-DE", { dateStyle: "full" }).format(parseLocalDate(day.date));
  elements.calculationWindow.textContent = `${formatDateTime(day.start)} bis ${formatDateTime(day.end)}`;
  renderDayBars(day);
  renderWarnings(day);
  renderSources(day);
}

function renderMonth(month) {
  const totals = month.totals;
  elements.monthSummary.textContent = `${formatKwh(totals.house_consumption_kwh)} Verbrauch, ${formatPercent(totals.autarky_percent)} Autarkie`;
  elements.monthChart.replaceChildren();
  const max = Math.max(
    ...month.days.map((day) => day.solar_yield_kwh + day.grid_import_kwh + day.grid_export_kwh),
    1,
  );

  for (const day of month.days) {
    const row = document.createElement("div");
    row.className = "month-day";
    const total = day.solar_yield_kwh + day.grid_import_kwh + day.grid_export_kwh;
    row.innerHTML = `
      <span>${new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit" }).format(parseLocalDate(day.date))}</span>
      <div class="month-stack" style="--solar: ${(day.solar_yield_kwh / max) * 100}%; --import: ${(day.grid_import_kwh / max) * 100}%; --export: ${(day.grid_export_kwh / max) * 100}%">
        <span title="Solar"></span>
        <span title="Netzbezug"></span>
        <span title="Netzeinspeisung"></span>
        <span></span>
      </div>
      <strong>${formatKwh(day.house_consumption_kwh)}</strong>
      <span>${formatPercent(day.autarky_percent)}</span>
    `;
    row.title = `Solar ${formatKwh(day.solar_yield_kwh)}, Bezug ${formatKwh(day.grid_import_kwh)}, Einspeisung ${formatKwh(day.grid_export_kwh)}, Summe ${formatKwh(total)}`;
    elements.monthChart.append(row);
  }
}

async function loadConfig() {
  state.config = await request("config");
  renderEntitySelects();
}

async function loadEntities() {
  state.entities = await request("entities");
  renderEntitySelects();
}

async function loadDay() {
  elements.dayPicker.value = isoDate(state.selectedDay);
  const day = await request(`day?date=${encodeURIComponent(elements.dayPicker.value)}`);
  renderDay(day);
}

async function loadMonth() {
  elements.monthPicker.value = isoMonth(state.selectedMonth);
  const month = await request(`month?month=${encodeURIComponent(elements.monthPicker.value)}`);
  renderMonth(month);
}

function shiftDay(amount) {
  const next = new Date(state.selectedDay);
  next.setDate(next.getDate() + amount);
  state.selectedDay = next;
  state.selectedMonth = next;
  loadDay();
  loadMonth();
}

elements.previousDay.addEventListener("click", () => shiftDay(-1));
elements.nextDay.addEventListener("click", () => shiftDay(1));
elements.today.addEventListener("click", () => {
  state.selectedDay = new Date();
  state.selectedMonth = new Date();
  loadDay();
  loadMonth();
});
elements.dayPicker.addEventListener("change", () => {
  state.selectedDay = parseLocalDate(elements.dayPicker.value);
  state.selectedMonth = state.selectedDay;
  loadDay();
});
elements.monthPicker.addEventListener("change", () => {
  const [year, month] = elements.monthPicker.value.split("-").map(Number);
  state.selectedMonth = new Date(year, month - 1, 1);
  loadMonth();
});
elements.addSolar.addEventListener("click", () => {
  const entityId = elements.solarSelect.value;
  if (!entityId || state.config.solar_entities.includes(entityId)) {
    return;
  }
  state.config.solar_entities.push(entityId);
  renderSolarList();
});
elements.gridImportSelect.addEventListener("change", () => {
  state.config.grid_import_entity = elements.gridImportSelect.value;
});
elements.gridExportSelect.addEventListener("change", () => {
  state.config.grid_export_entity = elements.gridExportSelect.value;
});
elements.refreshEntities.addEventListener("click", async () => {
  setStatus("Entities werden geladen ...");
  try {
    await loadEntities();
    setStatus("Entities aktualisiert.");
  } catch (error) {
    setStatus("Entities konnten nicht geladen werden.");
  }
});
elements.saveConfig.addEventListener("click", async () => {
  setStatus("Speichern ...");
  try {
    state.config = await request("config", {
      method: "PUT",
      body: JSON.stringify(state.config),
    });
    renderEntitySelects();
    await loadDay();
    await loadMonth();
    setStatus("Gespeichert.");
  } catch (error) {
    setStatus("Speichern fehlgeschlagen.");
  }
});

async function init() {
  elements.dayPicker.value = isoDate(state.selectedDay);
  elements.monthPicker.value = isoMonth(state.selectedMonth);
  try {
    await loadConfig();
    await loadEntities();
    await loadDay();
    await loadMonth();
  } catch (error) {
    setStatus("Home Assistant API nicht erreichbar.");
    console.error(error);
  }
}

init();
