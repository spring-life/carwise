const state = { vehicles: [], selected: new Set(), view: "directory", modelFilter: "" };
const $ = (id) => document.getElementById(id);

function money(value) {
  return value == null ? "暂无可靠数据" : `¥${new Intl.NumberFormat("zh-CN").format(value)}`;
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function setStatus(id, text, error = false) {
  const target = $(id);
  target.textContent = text;
  target.classList.toggle("is-error", error);
}

function groupedVehicles() {
  const groups = new Map();
  const filter = state.modelFilter.trim().toLowerCase();
  for (const vehicle of state.vehicles) {
    if (filter && !`${vehicle.make} ${vehicle.model}`.toLowerCase().includes(filter)) continue;
    const key = `${vehicle.make} ${vehicle.model}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(vehicle);
  }
  return groups;
}

function allGroups() {
  const groups = new Map();
  for (const vehicle of state.vehicles) {
    const key = `${vehicle.make} ${vehicle.model}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(vehicle);
  }
  return groups;
}

function priceRange(vehicles) {
  const prices = vehicles.map(vehicle => vehicle.msrp).filter(value => value != null);
  if (!prices.length) return "暂无指导价";
  return `${money(Math.min(...prices))} - ${money(Math.max(...prices))}`;
}

function renderDirectory() {
  const target = $("model-grid");
  target.replaceChildren();
  const groups = [...groupedVehicles().entries()];
  $("directory-count").textContent = `${groups.length} 款车型 · ${groups.reduce((sum, [, items]) => sum + items.length, 0)} 个版本`;
  if (!groups.length) {
    target.append(node("div", "directory-empty", "没有找到匹配车型"));
    return;
  }
  for (const [model, vehicles] of groups) {
    const card = node("article", "model-card");
    const image = node("img", "model-image");
    image.src = vehicles.find(vehicle => vehicle.image_url)?.image_url || "";
    image.alt = `${model} 官方车型图片`;
    image.loading = "lazy";
    image.addEventListener("error", () => { image.style.display = "none"; });
    const body = node("div", "model-card-body");
    body.append(node("h3", "", model));
    body.append(node("div", "model-meta", `2026 款 · ${vehicles.length} 个配置版本`));
    body.append(node("div", "model-price", priceRange(vehicles)));
    const action = node("button", "card-action", "查看配置 →");
    action.type = "button";
    action.addEventListener("click", () => openModel(model));
    body.append(action);
    card.append(image, body);
    target.append(card);
  }
}

function openModel(model) {
  state.modelFilter = model;
  renderSelector();
  setView("compare");
  $("vehicle-sidebar").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderSelector() {
  const target = $("vehicle-list");
  target.replaceChildren();
  $("selection-count").textContent = `${state.selected.size} / 3`;
  for (const [model, vehicles] of groupedVehicles()) {
    const group = node("section", "vehicle-group");
    group.append(node("h3", "", model));
    for (const vehicle of vehicles.sort((a, b) => a.msrp - b.msrp)) {
      const label = node("label", "vehicle-option");
      const checkbox = node("input");
      checkbox.type = "checkbox";
      checkbox.checked = state.selected.has(vehicle.id);
      checkbox.disabled = !checkbox.checked && state.selected.size >= 3;
      checkbox.setAttribute("aria-label", vehicle.trim);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.selected.add(vehicle.id);
        else state.selected.delete(vehicle.id);
        renderSelector();
        renderCompare();
      });
      label.append(checkbox, node("span", "option-title", vehicle.trim), node("span", "option-price", money(vehicle.msrp)));
      group.append(label);
    }
    target.append(group);
  }
}

function renderDocumentVehicleOptions() {
  const target = $("document-vehicle-options");
  if (!target) return;
  target.replaceChildren();
  for (const [model, vehicles] of allGroups()) {
    const label = node("label", "document-vehicle-option");
    const checkbox = node("input");
    checkbox.type = "checkbox";
    checkbox.name = "vehicle_id";
    checkbox.value = vehicles[0].id;
    checkbox.checked = state.selected.has(vehicles[0].id);
    label.append(checkbox, node("span", "", model));
    target.append(label);
  }
}

function renderDocuments(items) {
  const target = $("document-list");
  target.replaceChildren();
  $("document-count").textContent = `${items.length} 份资料`;
  const types = { official: "官方资料", recall: "召回公告", review: "第三方评测", owner_report: "用户个案" };
  for (const item of items) {
    const row = node("article", "document-row");
    row.append(node("h3", "", item.title));
    const linked = (item.linked_vehicle_ids || []).map(id => state.vehicles.find(vehicle => vehicle.id === id)?.model).filter(Boolean);
    row.append(node("p", "", `${types[item.source_type] || item.source_type} · ${item.indexed_chunks} 个片段${linked.length ? ` · ${[...new Set(linked)].join("、")}` : ""}`));
    const link = node("a", "", "打开来源");
    link.href = item.source_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    row.append(node("p", "", ""), link);
    target.append(row);
  }
}

async function loadDocuments() {
  try {
    const response = await fetch("/api/documents");
    if (!response.ok) throw new Error("资料列表载入失败");
    renderDocuments(await response.json());
  } catch (error) {
    setStatus("document-status", error.message, true);
  }
}

async function submitDocument(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const selected = [...form.querySelectorAll('input[name="vehicle_id"]:checked')].map(input => input.value);
  if (!selected.length) {
    setStatus("document-status", "至少关联一款车型。", true);
    return;
  }
  const formData = new FormData(form);
  formData.delete("vehicle_id");
  formData.append("vehicle_ids", JSON.stringify(selected));
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  setStatus("document-status", "正在解析并建立索引…");
  try {
    const response = await fetch("/api/documents", { method: "POST", body: formData });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "资料添加失败");
    setStatus("document-status", `已添加资料，建立 ${result.indexed_chunks} 个检索片段。`);
    form.reset();
    await loadDocuments();
    const health = await fetch("/api/health").then(response => response.json());
    $("index-state").textContent = `车型 ${health.vehicles} · 资料片段 ${health.indexed_chunks}`;
  } catch (error) {
    setStatus("document-status", error.message, true);
  } finally {
    button.disabled = false;
  }
}

function cell(value, className = "") {
  return node("td", className, value == null || value === "" ? "暂无可靠数据" : String(value));
}

function renderCompare() {
  const target = $("compare-content");
  target.replaceChildren();
  const vehicles = [...state.selected].map(id => state.vehicles.find(v => v.id === id)).filter(Boolean);
  if (vehicles.length < 2) {
    setStatus("compare-status", "请选择至少 2 个具体配置版本。", false);
    target.append(node("div", "empty-state", "选择车辆后，这里会显示价格、配置与来源。"));
    return;
  }
  setStatus("compare-status", `正在比较 ${vehicles.length} 个配置版本 · 官方指导价`, false);
  const prices = vehicles.map(v => v.msrp).filter(v => v != null);
  if (prices.length === vehicles.length) {
    const summary = node("div", "comparison-summary");
    const spread = Math.max(...prices) - Math.min(...prices);
    summary.append(node("span", "", "所选版本指导价相差"), node("strong", "", money(spread)));
    target.append(summary);
  }

  const scroll = node("div", "table-scroll");
  const table = node("table", "comparison-table");
  const thead = node("thead");
  const header = node("tr");
  header.append(node("th", "", "比较项目"));
  for (const vehicle of vehicles) {
    const th = node("th");
    th.append(node("div", "table-model", `${vehicle.make} ${vehicle.model} · ${vehicle.year}款`));
    th.append(node("div", "table-trim", vehicle.trim));
    header.append(th);
  }
  thead.append(header);
  table.append(thead);

  const rows = [
    ["官方指导价", v => money(v.msrp), "price-cell"],
    ["动力类型", v => v.powertrain],
    ["能耗", v => v.fuel_consumption == null ? null : `${v.fuel_consumption} ${v.fuel_unit} · ${v.fuel_standard}`],
  ];
  const featureNames = new Set(vehicles.flatMap(v => Object.keys(v.features || {})));
  for (const name of featureNames) rows.push([name, v => v.features?.[name]]);
  const tbody = node("tbody");
  for (const [name, getValue, className] of rows) {
    const row = node("tr");
    row.append(node("th", "", name));
    for (const vehicle of vehicles) row.append(cell(getValue(vehicle), className || ""));
    tbody.append(row);
  }
  table.append(tbody);
  scroll.append(table);
  target.append(scroll);

  const sources = node("section", "source-list");
  sources.append(node("h2", "", "数据来源"));
  for (const vehicle of vehicles) {
    const source = vehicle.sources.price || vehicle.sources.specs;
    const line = node("div", "source-line");
    line.append(node("span", "", `${vehicle.model} ${vehicle.trim}`));
    const link = node("a", "", source.title);
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    line.append(link, node("span", "", `记录于 ${source.observed_on}`));
    sources.append(line);
  }
  target.append(sources);
}

function renderAnswer(result) {
  const target = $("answer-content");
  target.replaceChildren();
  const panel = node("section", "answer-panel");
  panel.append(node("h2", "", "回答"), node("p", "answer-text", result.answer));
  if (result.mode === "evidence_selected") panel.append(node("p", "answer-mode", "模型选择的原文已逐字校验；请以来源文件为准。"));
  if (result.mode === "retrieval_only") panel.append(node("p", "answer-mode", "当前仅展示检索结果，尚未生成回答。"));
  target.append(panel);
  if (!result.citations.length) return;
  const evidence = node("section", "evidence-list");
  evidence.append(node("h2", "", "引用资料"));
  const types = { official: "官方资料", recall: "召回公告", review: "第三方评测", owner_report: "用户个案" };
  for (const citation of result.citations) {
    const item = node("article", "evidence-item");
    const head = node("div", "evidence-head");
    head.append(node("span", "evidence-id", citation.id));
    const link = node("a", "", citation.title);
    link.href = citation.url.endsWith(".pdf") && citation.location?.match(/第 (\d+) 页/)
      ? `${citation.url}#page=${citation.location.match(/第 (\d+) 页/)[1]}` : citation.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    head.append(link);
    item.append(head);
    item.append(node("div", "evidence-meta", [types[citation.source_type] || citation.source_type, citation.published_on, citation.location].filter(Boolean).join(" · ")));
    item.append(node("blockquote", "", citation.excerpt));
    const pageMatch = citation.location?.match(/第 (\d+) 页/);
    if (pageMatch) {
      const button = node("button", "extract-button", "抽取本页要点");
      const factList = node("div", "fact-list");
      button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "提取中…";
        factList.replaceChildren();
        try {
          const response = await fetch("/api/extract", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ document_id: citation.document_id, page_number: Number(pageMatch[1]) }),
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || "抽取失败");
          if (!data.facts.length) factList.append(node("p", "muted", "本页暂无可确认的要点。"));
          for (const fact of data.facts) {
            const line = node("p", "fact-item");
            line.append(node("strong", "", fact.fact_type), node("span", "", fact.quote));
            factList.append(line);
          }
        } catch (error) {
          factList.append(node("p", "error-text", error.message));
        } finally {
          button.disabled = false;
          button.textContent = "重新抽取";
        }
      });
      item.append(button, factList);
    }
    evidence.append(item);
  }
  target.append(evidence);
}

async function ask(question) {
  const button = $("ask-button");
  button.disabled = true;
  setStatus("answer-status", "正在查找资料…");
  $("answer-content").replaceChildren();
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, vehicle_ids: [...state.selected] }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "查询失败");
    setStatus("answer-status", result.citations.length ? `找到 ${result.citations.length} 条引用资料` : "没有可引用的资料");
    renderAnswer(result);
  } catch (error) {
    setStatus("answer-status", error.message, true);
  } finally {
    button.disabled = false;
  }
}

function setView(view) {
  state.view = view;
  $("directory-view").hidden = view !== "directory";
  $("compare-view").hidden = view !== "compare";
  $("research-view").hidden = view !== "research";
  $("documents-view").hidden = view !== "documents";
  $("vehicle-sidebar").hidden = view === "directory" || view === "documents";
  document.querySelector(".workspace").classList.toggle("directory-mode", view === "directory");
  document.querySelector(".workspace").classList.toggle("documents-mode", view === "documents");
  for (const tab of document.querySelectorAll(".nav-tab")) tab.classList.toggle("is-active", tab.dataset.view === view);
  if (view === "documents") {
    renderDocumentVehicleOptions();
    loadDocuments();
  }
}

async function init() {
  document.querySelectorAll(".nav-tab").forEach(tab => tab.addEventListener("click", () => {
    if (tab.dataset.view === "compare") state.modelFilter = "";
    setView(tab.dataset.view);
    if (tab.dataset.view === "compare") renderSelector();
  }));
  $("vehicle-search").addEventListener("input", event => {
    state.modelFilter = event.target.value;
    renderDirectory();
  });
  $("vehicle-search").addEventListener("keydown", event => {
    if (event.key === "Enter") {
      const first = [...groupedVehicles().keys()][0];
      if (first) openModel(first);
    }
  });
  document.addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      setView("directory");
      $("vehicle-search").focus();
    }
  });
  $("question-form").addEventListener("submit", event => {
    event.preventDefault();
    const question = $("question-input").value.trim();
    if (question) ask(question);
  });
  $("document-form").addEventListener("submit", submitDocument);
  try {
    const [vehiclesResponse, healthResponse] = await Promise.all([fetch("/api/vehicles"), fetch("/api/health")]);
    if (!vehiclesResponse.ok || !healthResponse.ok) throw new Error("数据载入失败");
    state.vehicles = await vehiclesResponse.json();
    const health = await healthResponse.json();
    $("index-state").textContent = `车型 ${health.vehicles} · 资料片段 ${health.indexed_chunks}`;
    renderDirectory();
    renderSelector();
    renderCompare();
    setView("directory");
  } catch (error) {
    setStatus("compare-status", error.message, true);
    $("index-state").textContent = "载入失败";
  }
}

init();

