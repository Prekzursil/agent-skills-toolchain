// mcpapply GUI -- hand-written, no framework, no CDN, no build step.
//
// XSS posture: this file assigns textContent ONLY. There is no innerHTML,
// outerHTML, insertAdjacentHTML, document.write or eval anywhere in it, and a test
// asserts that mechanically over this exact asset -- a server name is attacker-
// influenceable free text from a config file, so the DOM is built from nodes rather
// than from a string that could carry markup.
//
// Mutation posture: the apply button is disabled until a plan has been previewed,
// and pressing it opens a native confirm() before the request is sent. The request
// itself carries the literal {"confirm":"APPLY"} the server demands; a request
// without it is answered with the preview and an explicit refusal.
"use strict";

(function () {
  var token = document.getElementById("token").dataset.token;
  var out = document.getElementById("out");
  var planner = document.getElementById("planner");
  var applyButton = document.getElementById("apply");
  var current = null;

  function show(text) {
    out.textContent = text;
  }

  function post(path, body) {
    return fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-MCPApply-Token": token
      },
      body: JSON.stringify(body)
    }).then(function (response) {
      return response.json();
    });
  }

  function describe(payload) {
    var lines = [];
    var plan = payload.plan || {};
    (plan.changes || []).forEach(function (change) {
      lines.push(change.intent + " " + change.server + " (was: " + change.before + ")");
      (change.edits || []).forEach(function (edit) {
        lines.push("    " + edit.describe);
      });
      (change.warnings || []).forEach(function (warning) {
        lines.push("    ! " + warning);
      });
    });
    if (plan.empty) {
      lines.push("plan is EMPTY -- nothing would change");
    }
    var impact = payload.impact || {};
    lines.push("");
    // The basis rides WITH the number, always. A proxy figure spans 12.5x on this
    // box, so an unlabelled integer is indistinguishable from a measurement.
    lines.push(
      "tokens saved: " + fmt(impact.token_delta) + " [" + fmt(impact.token_basis) + "]"
    );
    lines.push("commit saved: " + fmt(impact.commit_delta));
    (impact.notes || []).forEach(function (note) {
      lines.push("note: " + note);
    });
    (plan.notes || []).forEach(function (note) {
      lines.push("note: " + note);
    });
    if (payload.error) {
      lines.push("");
      lines.push(payload.error);
    }
    if (payload.result) {
      lines.push("");
      lines.push(payload.result.dry_run ? "DRY RUN -- nothing written" : "APPLIED");
      (payload.result.written || []).forEach(function (path) {
        lines.push("wrote: " + path);
      });
      (payload.result.backups || []).forEach(function (record) {
        lines.push("backup: " + record.backup);
      });
      if (payload.result.blocked) {
        lines.push("BLOCKED: " + payload.result.blocked);
      }
      lines.push(payload.result.restore);
    }
    return lines.join("\n");
  }

  // An unmeasured value renders "-", never 0 -- "not measured" and "costs nothing"
  // are different facts and collapsing them makes the preview a lie.
  function fmt(value) {
    return value === null || value === undefined ? "-" : String(value);
  }

  planner.addEventListener("submit", function (event) {
    event.preventDefault();
    var data = new FormData(planner);
    current = {
      intent: String(data.get("intent")),
      server: String(data.get("server"))
    };
    applyButton.disabled = true;
    post("/api/plan", current).then(function (payload) {
      show(describe(payload));
      applyButton.disabled = Boolean(payload.plan && payload.plan.empty);
    });
  });

  applyButton.addEventListener("click", function () {
    if (!current) {
      return;
    }
    var ok = window.confirm(
      "Apply this plan to your live MCP configuration?\n\n" +
        current.intent +
        " " +
        current.server +
        "\n\nA timestamped backup is taken first and the restore command is printed."
    );
    if (!ok) {
      show("apply cancelled -- nothing was sent");
      return;
    }
    post("/api/apply", {
      intent: current.intent,
      server: current.server,
      confirm: "APPLY"
    }).then(function (payload) {
      show(describe(payload));
      applyButton.disabled = true;
    });
  });
})();
