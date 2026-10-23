"use strict";

(() => {
  const style = getComputedStyle(document.body);
  const colour = name => style.getPropertyValue(name).trim();
  const palette = ["--accent", "--second", "--third"].map(colour);
  const number = value => typeof value === "number"
    ? value.toLocaleString("en-GB", { maximumFractionDigits: 3 })
    : String(value ?? "");
  const fail = error => {
    console.error("Report chart error:", error);
    const message = document.getElementById("report-error");
    message.hidden = false;
    message.textContent = "A chart could not be loaded. Reload the page or use the linked notebook and written findings.";
  };
  const states = new Map();
  const configuration = {
    responsive: true,
    displaylogo: false,
    scrollZoom: false,
    modeBarButtonsToRemove: ["select2d", "lasso2d"],
    toImageButtonOptions: { format: "png", scale: 2, filename: "report-chart" }
  };

  function makeTable(state, columns, rows) {
    state.columns = columns;
    state.rows = rows;
    if (!state.table.closest("details").open) {
      state.table.replaceChildren();
      return;
    }
    const table = document.createElement("table");
    const caption = document.createElement("caption");
    caption.textContent = state.spec.title;
    table.append(caption);
    const head = table.createTHead().insertRow();
    columns.forEach(column => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = column;
      head.append(th);
    });
    const body = table.createTBody();
    rows.slice(0, 500).forEach(row => {
      const tr = body.insertRow();
      row.forEach(value => { tr.insertCell().textContent = number(value); });
    });
    state.table.replaceChildren(table);
    if (rows.length > 500) {
      const note = document.createElement("p");
      note.textContent = `The first 500 of ${number(rows.length)} rows are shown. Download the CSV for all rows.`;
      state.table.prepend(note);
    }
  }

  function baseLayout(state, view) {
    const categories = view.traces.find(trace => Array.isArray(trace.y) && trace.y.every(value => typeof value === "string"))?.y;
    const ticks = categories ? {
      tickmode: "array", tickvals: categories,
      ticktext: categories.map(label => {
        const lines = [""];
        for (const word of label.split(" ")) {
          const last = lines.length - 1;
          if (lines[last] && lines[last].length + word.length > 22) lines.push(word);
          else lines[last] += (lines[last] ? " " : "") + word;
        }
        return lines.join("<br>");
      })
    } : {};
    return structuredClone({
      autosize: true,
      paper_bgcolor: colour("--white"),
      plot_bgcolor: colour("--white"),
      font: { family: "Segoe UI, Arial, sans-serif", size: 12, color: colour("--ink") },
      colorway: palette,
      margin: { l: 56, r: 18, t: 25, b: 58 },
      hovermode: view.hovermode || "closest",
      hoverlabel: { bgcolor: colour("--white"), font: { color: colour("--ink"), size: 13 }, namelength: -1 },
      xaxis: { title: { text: view.xTitle || "", standoff: 12 }, showgrid: false, zeroline: false, automargin: true, ...(view.xaxis || {}) },
      yaxis: { title: { text: view.yTitle || "", standoff: 12 }, gridcolor: colour("--rule"), zeroline: false, rangemode: "tozero", automargin: true, ...ticks, ...(view.yaxis || {}) },
      legend: { orientation: "h", x: 0, y: 1.14, font: { size: 12 } },
      barmode: "group",
      uirevision: `${state.id}-${state.key}`,
      ...(view.layout || {})
    });
  }

  function zoneView(state) {
    const spec = state.spec;
    const metric = state.key;
    const count = zone => metric === "night"
      ? zone.pickups.filter((_, i) => i >= 23 || i < 5).reduce((a, b) => a + b, 0)
      : zone[metric].reduce((a, b) => a + b, 0);
    const values = spec.zones.map(count);
    const maximum = Math.max(...values);
    const dark = palette[0].match(/\w\w/g).map(part => parseInt(part, 16));
    const traces = spec.zones.map((zone, i) => {
      const amount = Math.log1p(values[i]) / Math.log1p(maximum);
      const rgb = dark.map(v => Math.round(245 + (v - 245) * amount));
      return {
        type: "scatter", mode: "lines", x: zone.x, y: zone.y,
        fill: "toself", fillcolor: `rgb(${rgb.join(",")})`,
        line: { color: "#ffffff", width: 0.65 },
        hoveron: "fills", name: zone.name, text: `${zone.name}<br>${number(values[i])} sampled ${metric === "dropoffs" ? "dropoffs" : "pickups"}`,
        hoverinfo: "text", showlegend: false
      };
    });
    const columns = ["Zone", "Borough", "Sampled trips"];
    const rows = spec.zones.map((zone, i) => [zone.name, zone.borough, values[i]]).sort((a, b) => b[2] - a[2]);
    return {
      ...spec.views[metric], traces, columns, rows,
      layout: {
        margin: { l: 0, r: 0, t: 0, b: 0 }, dragmode: "pan",
        xaxis: { visible: false },
        yaxis: { visible: false, scaleanchor: "x", scaleratio: 1 }
      }
    };
  }

  async function render(state) {
    const view = state.spec.kind === "zones" ? zoneView(state) : state.spec.views[state.key];
    state.note.textContent = view.note;
    const traces = view.traces.map((trace, i) => {
      const result = { ...trace };
      if (trace.type === "heatmap") {
        result.colorscale = trace.colorscale || [[0, colour("--paper")], [0.5, colour("--second")], [1, colour("--accent")]];
      } else if (state.spec.kind !== "zones") {
        result.marker = { color: palette[i % palette.length], size: 6, ...trace.marker };
        result.line = { color: palette[i % palette.length], width: 2.5, ...trace.line };
      }
      return result;
    });
    makeTable(state, view.columns, view.rows);
    await Plotly.react(state.node, traces, baseLayout(state, view), configuration);
    state.node.dataset.ready = "true";
  }

  function download(state) {
    const escape = value => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [state.columns, ...state.rows].map(row => row.map(escape).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${state.id}-${state.key}.csv`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function describeZone(state, index) {
    const zone = state.spec.zones[index];
    if (!zone) return;
    const pickups = zone.pickups.reduce((a, b) => a + b, 0);
    const dropoffs = zone.dropoffs.reduce((a, b) => a + b, 0);
    const output = document.getElementById("zone-readout");
    const title = document.createElement("strong");
    title.textContent = `${zone.name}, ${zone.borough}`;
    output.replaceChildren(title, document.createTextNode(`${number(pickups)} sampled pickups and ${number(dropoffs)} sampled dropoffs across 2023. These are sample counts, not full-year estimates.`));
    document.getElementById("zone-choice").value = String(index);
  }

  function describeQuestion(index) {
    const item = window.REPORT.questions[index];
    const output = document.getElementById("question-readout");
    const title = document.createElement("strong");
    title.textContent = item.id;
    const evidence = item.scores[0] === 0
      ? "No retrieved chunk overlaps the reference span."
      : `The first overlapping chunk ranks ${Math.round(1 / item.scores[1])} of 5.`;
    output.replaceChildren(title, document.createTextNode(`${evidence} Answer relevancy: ${item.scores[3].toFixed(3)}. Faithfulness: ${item.scores[2].toFixed(3)}. A retrieval hit does not establish that the generated answer is correct.`));
    document.getElementById("question-choice").value = String(index);
  }

  async function start() {
    if (!window.Plotly || !window.REPORT) throw new Error("Local chart assets are missing.");
    for (const node of document.querySelectorAll("[data-chart]")) {
      const id = node.id;
      const spec = window.REPORT.charts[id];
      if (!spec) throw new Error(`Missing chart specification: ${id}`);
      const select = document.getElementById(`${id}-view`);
      const state = {
        id, spec, node, key: Object.keys(spec.views)[0],
        note: document.getElementById(`${id}-note`),
        table: document.getElementById(`${id}-table`)
      };
      states.set(id, state);
      state.table.closest("details").addEventListener("toggle", () => {
        if (state.rows) makeTable(state, state.columns, state.rows);
      });
      if (select) {
        Object.entries(spec.views).forEach(([key, view]) => select.add(new Option(view.label, key)));
        select.addEventListener("change", async () => {
          select.disabled = true;
          state.key = select.value;
          try { await render(state); } catch (error) { fail(error); }
          finally { select.disabled = false; }
        });
      }
      document.querySelector(`[data-download="${id}"]`).addEventListener("click", () => download(state));
      document.querySelector(`[data-reset="${id}"]`).addEventListener("click", () => {
        const view = spec.kind === "zones" ? zoneView(state) : spec.views[state.key];
        const layout = baseLayout(state, view);
        const axis = value => ({ ...value, autorange: value.range ? false : (value.autorange ?? true) });
        Plotly.relayout(node, { xaxis: axis(layout.xaxis), yaxis: axis(layout.yaxis) }).catch(fail);
      });
      await render(state);
      if (spec.kind === "zones") {
        const choice = document.getElementById("zone-choice");
        spec.zones.map((zone, index) => ({ zone, index })).sort((a, b) => a.zone.name.localeCompare(b.zone.name))
          .forEach(({ zone, index }) => choice.add(new Option(zone.name, String(index))));
        choice.addEventListener("change", () => describeZone(state, Number(choice.value)));
        node.on("plotly_click", event => describeZone(state, event.points[0].curveNumber));
        describeZone(state, spec.zones.findIndex(zone => zone.name === "JFK Airport"));
      }
      if (id === "question-scores") {
        const choice = document.getElementById("question-choice");
        window.REPORT.questions.forEach((question, index) => choice.add(new Option(question.id, String(index))));
        choice.addEventListener("change", () => describeQuestion(Number(choice.value)));
        node.on("plotly_click", event => {
          const index = window.REPORT.questions.findIndex(question => question.id === event.points[0].y);
          if (index >= 0) describeQuestion(index);
        });
        describeQuestion(0);
      }
    }
    document.documentElement.dataset.chartsReady = "true";
  }
  start().catch(fail);
})();
