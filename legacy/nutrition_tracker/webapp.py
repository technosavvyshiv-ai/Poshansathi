#!/usr/bin/env python3
"""Poshansathi web interface.

A small browser UI built only on the Python standard library
(``http.server`` + ``sqlite3``), so it runs anywhere with no ``pip install``.

Run with::

    python webapp.py            # then open http://localhost:8000
    python webapp.py --port 9000
"""

from __future__ import annotations

import argparse
import html
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from poshansathi import database, reports, tracker
from poshansathi.nutrition import ACTIVITY_FACTORS, GOAL_ADJUSTMENT, profile_summary
from poshansathi.suggestions import build_report

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  background: #f4f7f2; color: #22301f; line-height: 1.5;
}
header {
  background: linear-gradient(135deg, #2e7d32, #66bb6a);
  color: #fff; padding: 18px 24px; box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
header h1 { margin: 0; font-size: 22px; }
header .sub { opacity: .85; font-size: 13px; }
nav { margin-top: 10px; }
nav a {
  color: #fff; text-decoration: none; margin-right: 16px; font-size: 14px;
  padding: 4px 0; border-bottom: 2px solid transparent;
}
nav a:hover { border-color: #fff; }
main { max-width: 960px; margin: 24px auto; padding: 0 16px; }
.card {
  background: #fff; border-radius: 12px; padding: 18px 20px; margin-bottom: 18px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.card h2 { margin: 0 0 12px; font-size: 17px; color: #2e7d32; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.stat { background: #f1f8e9; border-radius: 10px; padding: 12px 14px; }
.stat .value { font-size: 24px; font-weight: 700; color: #2e7d32; }
.stat .label { font-size: 12px; text-transform: uppercase; letter-spacing: .5px; color: #607d5a; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #e6ece4; }
th { color: #607d5a; font-size: 12px; text-transform: uppercase; }
.bar { background: #e6ece4; border-radius: 20px; height: 12px; overflow: hidden; }
.bar > span { display: block; height: 100%; background: #66bb6a; }
.bar.over > span { background: #ef5350; }
.bar.warn > span { background: #ffa726; }
form.inline { display: flex; flex-wrap: wrap; gap: 10px; align-items: end; }
label { font-size: 12px; color: #607d5a; display: block; }
select, input {
  padding: 8px 10px; border: 1px solid #cfd8cb; border-radius: 8px;
  font-size: 14px; background: #fff; width: 100%;
}
button {
  background: #2e7d32; color: #fff; border: 0; border-radius: 8px;
  padding: 9px 16px; font-size: 14px; cursor: pointer;
}
button:hover { background: #256428; }
button.ghost { background: #e8f5e9; color: #2e7d32; }
.pill { display: inline-block; padding: 2px 10px; border-radius: 20px;
  font-size: 12px; background: #e8f5e9; color: #2e7d32; }
.pill.low { background: #ffebee; color: #c62828; }
.hint { font-size: 13px; color: #607d5a; }
a.plain { color: #2e7d32; }
.empty { color: #90a4ae; font-style: italic; }
"""


def esc(value) -> str:
    return html.escape(str(value))


def page(title: str, body: str, user_id: int | None = None,
         users: list | None = None) -> str:
    """Wrap ``body`` in the shared layout with navigation."""
    uid = f"?user={user_id}" if user_id else ""
    user_options = ""
    if users:
        options = "".join(
            f'<option value="{u.id}"{" selected" if u.id == user_id else ""}>'
            f'{esc(u.name)}</option>'
            for u in users
        )
        user_options = (
            '<form method="get" style="display:inline-block;margin-left:16px">'
            f'<select name="user" onchange="this.form.submit()">{options}</select>'
            "</form>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} - Poshansathi</title>
<style>{CSS}</style></head>
<body>
<header>
  <h1>🍛 Poshansathi</h1>
  <div class="sub">Your nutrition companion</div>
  <nav>
    <a href="/{uid}">Dashboard</a>
    <a href="/profile{uid}">Profile</a>
    <a href="/foods{uid}">Foods</a>
    <a href="/week{uid}">Weekly</a>
    <a href="/profile?new=1">New profile</a>
  </nav>
  {user_options}
</header>
<main>{body}</main>
</body></html>"""


def progress(percent: float, status: str = "") -> str:
    width = max(0.0, min(100.0, percent))
    cls = "bar"
    if status == "over":
        cls += " over"
    elif 0 < width < 60:
        cls += " warn"
    return f'<div class="{cls}"><span style="width:{width:.0f}%"></span></div>'


# --------------------------------------------------------------------------
# Page renderers
# --------------------------------------------------------------------------
def render_dashboard(conn, user, day: str) -> str:
    entries = tracker.get_entries(conn, user.id, day)
    totals = tracker.daily_totals(conn, user.id, day)
    report = build_report(conn, user, totals)
    cal = report["calories"]
    profile = report["profile"]

    stats = f"""
    <div class="grid">
      <div class="stat"><div class="value">{cal['consumed']:.0f}</div>
        <div class="label">kcal eaten</div></div>
      <div class="stat"><div class="value">{cal['target']:.0f}</div>
        <div class="label">daily target</div></div>
      <div class="stat"><div class="value">{cal['remaining']:.0f}</div>
        <div class="label">remaining</div></div>
      <div class="stat"><div class="value">{profile['bmi']}</div>
        <div class="label">BMI ({esc(profile['bmi_category'])})</div></div>
    </div>"""

    macro_rows = ""
    for macro, info in report["macros"].items():
        macro_rows += (
            f"<tr><td>{esc(macro.title())}</td>"
            f"<td>{info['value']:.0f} / {info['target']:.0f} g</td>"
            f"<td style='width:180px'>{progress(info['percent'])}</td>"
            f"<td>{info['percent']:.0f}%</td></tr>"
        )

    gap_rows = ""
    for gap in report["gaps"]:
        pill = 'low' if gap["critical"] else ''
        recs = report["recommendations"].get(gap["nutrient"], [])
        names = ", ".join(esc(r["food"].name) for r in recs)
        gap_rows += (
            f"<tr><td>{esc(gap['nutrient'])}</td>"
            f"<td>{gap['value']} / {gap['target']}</td>"
            f"<td><span class='pill {pill}'>{gap['percent']:.0f}%</span></td>"
            f"<td class='hint'>{names or '-'}</td></tr>"
        )
    gaps_html = (f"<table><tr><th>Nutrient</th><th>Have / Need</th>"
                 f"<th>%</th><th>Add</th></tr>{gap_rows}</table>"
                 if gap_rows else "<p class='hint'>All tracked nutrients met 🎉</p>")

    entry_rows = "".join(
        f"<tr><td>{esc(e['meal_type'])}</td><td>{esc(e['food_name'])}</td>"
        f"<td>{e['quantity']:g}</td><td>{e['total_calories']:.0f}</td>"
        f"<td><form method='post' action='/delete' style='margin:0'>"
        f"<input type='hidden' name='user' value='{user.id}'>"
        f"<input type='hidden' name='entry' value='{e['id']}'>"
        f"<input type='hidden' name='date' value='{esc(day)}'>"
        f"<button class='ghost' type='submit'>×</button></form></td></tr>"
        for e in entries
    )
    entries_html = (f"<table><tr><th>Meal</th><th>Food</th><th>Qty</th>"
                    f"<th>kcal</th><th></th></tr>{entry_rows}</table>"
                    if entry_rows else "<p class='empty'>Nothing logged yet.</p>")

    foods = tracker.list_foods(conn)
    food_options = "".join(
        f'<option value="{f.id}">{esc(f.name)} ({f.calories:.0f} kcal)</option>'
        for f in foods
    )
    meal_options = "".join(
        f'<option value="{m}">{m.title()}</option>' for m in tracker.MEAL_TYPES
    )

    body = f"""
    <div class="card">
      <h2>Today &middot; {esc(day)}</h2>
      {stats}
      <p class="hint" style="margin-top:12px">{esc(cal['message'])}</p>
    </div>

    <div class="card">
      <h2>Log a meal</h2>
      <form class="inline" method="post" action="/log">
        <input type="hidden" name="user" value="{user.id}">
        <div style="flex:1;min-width:150px"><label>Date</label>
          <input type="date" name="date" value="{esc(day)}"></div>
        <div style="flex:1;min-width:120px"><label>Meal</label>
          <select name="meal">{meal_options}</select></div>
        <div style="flex:2;min-width:180px"><label>Food</label>
          <select name="food">{food_options}</select></div>
        <div style="width:100px"><label>Servings</label>
          <input type="number" name="quantity" value="1" step="0.5" min="0.25"></div>
        <button type="submit">Add</button>
      </form>
    </div>

    <div class="card">
      <h2>Meals logged</h2>
      {entries_html}
    </div>

    <div class="card">
      <h2>Macros vs target</h2>
      <table><tr><th>Macro</th><th>Amount</th><th></th><th>%</th></tr>
      {macro_rows}</table>
    </div>

    <div class="card">
      <h2>Nutrient gaps &amp; suggestions</h2>
      {gaps_html}
      <p class="hint" style="margin-top:12px">Tip: {esc(report['tip'])}</p>
    </div>
    """
    return page("Dashboard", body, user.id, tracker.list_users(conn))


def render_profile(conn, user=None, show_new: bool = False) -> str:
    if show_new or user is None:
        body = f"""
        <div class="card">
          <h2>Create a profile</h2>
          <form method="post" action="/user">
            <div class="grid">
              <div><label>Name</label><input name="name" required></div>
              <div><label>Age</label><input name="age" type="number" value="25" required></div>
              <div><label>Gender</label><select name="gender">
                <option>female</option><option>male</option><option>other</option>
              </select></div>
              <div><label>Height (cm)</label><input name="height_cm" type="number" value="165" step="0.1"></div>
              <div><label>Weight (kg)</label><input name="weight_kg" type="number" value="60" step="0.1"></div>
              <div><label>Activity</label><select name="activity_level">
                {''.join(f'<option>{a}</option>' for a in ACTIVITY_FACTORS)}
              </select></div>
              <div><label>Goal</label><select name="goal">
                {''.join(f'<option value="{g}">{g}</option>' for g in GOAL_ADJUSTMENT)}
              </select></div>
            </div>
            <p><button type="submit">Create profile</button></p>
          </form>
        </div>"""
        return page("New profile", body, user.id if user else None,
                    tracker.list_users(conn))

    summary = profile_summary(user)
    lo, hi = summary["healthy_weight_range"]
    m = summary["macros"]
    body = f"""
    <div class="card">
      <h2>{esc(user.name)}</h2>
      <p class="hint">Age {user.age} · {esc(user.gender)} ·
        {user.height_cm:.0f} cm · {user.weight_kg:.0f} kg ·
        activity {esc(user.activity_level)} · goal {esc(user.goal)}</p>
      <div class="grid">
        <div class="stat"><div class="value">{summary['bmi']}</div>
          <div class="label">{esc(summary['bmi_category'])}</div></div>
        <div class="stat"><div class="value">{summary['bmr']:.0f}</div>
          <div class="label">BMR kcal</div></div>
        <div class="stat"><div class="value">{summary['tdee']:.0f}</div>
          <div class="label">TDEE kcal</div></div>
        <div class="stat"><div class="value">{summary['target_calories']:.0f}</div>
          <div class="label">Target kcal</div></div>
      </div>
      <p class="hint" style="margin-top:12px">
        Healthy weight range: {lo}-{hi} kg &nbsp;|&nbsp;
        Protein {m['protein_g']}g · Carbs {m['carbs_g']}g · Fat {m['fat_g']}g</p>
    </div>"""
    return page("Profile", body, user.id, tracker.list_users(conn))


def render_foods(conn, user, term: str = "", category: str = "") -> str:
    if term:
        foods = tracker.search_foods(conn, term)
    elif category:
        foods = tracker.list_foods(conn, category)
    else:
        foods = tracker.list_foods(conn)

    cats = tracker.list_categories(conn)
    cat_options = "".join(
        f'<option value="{esc(c)}"{" selected" if c == category else ""}>{esc(c)}</option>'
        for c in cats
    )
    rows = "".join(
        f"<tr><td>{esc(f.name)}</td><td>{esc(f.category)}</td>"
        f"<td>{esc(f.serving_desc)}</td><td>{f.calories:.0f}</td>"
        f"<td>{f.protein_g:.0f}</td><td>{f.carbs_g:.0f}</td><td>{f.fat_g:.0f}</td>"
        f"<td>{f.fiber_g:.1f}</td><td>{f.iron_mg:.1f}</td>"
        f"<td>{f.calcium_mg:.0f}</td><td>{f.vitamin_c_mg:.0f}</td></tr>"
        for f in foods
    )
    body = f"""
    <div class="card">
      <h2>Food database ({len(foods)} items)</h2>
      <form class="inline" method="get" action="/foods">
        <input type="hidden" name="user" value="{user.id}">
        <div style="flex:2"><label>Search by name</label>
          <input name="q" value="{esc(term)}" placeholder="e.g. dal"></div>
        <div style="flex:1"><label>Category</label>
          <select name="category"><option value="">All</option>{cat_options}</select></div>
        <button type="submit">Filter</button>
      </form>
    </div>
    <div class="card">
      <table>
        <tr><th>Name</th><th>Category</th><th>Serving</th><th>kcal</th>
        <th>P</th><th>C</th><th>F</th><th>Fibre</th><th>Iron</th>
        <th>Ca</th><th>Vit C</th></tr>
        {rows}
      </table>
    </div>"""
    return page("Foods", body, user.id, tracker.list_users(conn))


def render_week(conn, user) -> str:
    summary = reports.weekly_summary(conn, user.id)
    if not summary["days"]:
        body = "<div class='card'><h2>Weekly report</h2>" \
               "<p class='empty'>No meals logged this week.</p></div>"
        return page("Weekly", body, user.id, tracker.list_users(conn))

    target = profile_summary(user)["target_calories"]
    rows = "".join(
        f"<tr><td>{esc(d['date'])}</td><td>{d['calories']:.0f}</td>"
        f"<td>{d['protein_g']:.0f}</td><td>{d['carbs_g']:.0f}</td>"
        f"<td>{d['fat_g']:.0f}</td>"
        f"<td style='width:180px'>{progress(d['calories'] / target * 100, 'over' if d['calories'] > target * 1.1 else '')}</td></tr>"
        for d in summary["days"]
    )
    avg = summary["averages"]
    body = f"""
    <div class="card">
      <h2>Weekly report &middot; {esc(summary['start'])} to {esc(summary['end'])}</h2>
      <div class="grid">
        <div class="stat"><div class="value">{avg['calories']:.0f}</div>
          <div class="label">avg kcal/day</div></div>
        <div class="stat"><div class="value">{summary['logged_days']}</div>
          <div class="label">days logged</div></div>
        <div class="stat"><div class="value">{target:.0f}</div>
          <div class="label">target kcal</div></div>
      </div>
    </div>
    <div class="card">
      <table><tr><th>Date</th><th>kcal</th><th>Protein</th><th>Carbs</th>
      <th>Fat</th><th></th></tr>{rows}</table>
    </div>"""
    return page("Weekly", body, user.id, tracker.list_users(conn))


# --------------------------------------------------------------------------
# Request handling
# --------------------------------------------------------------------------
def synchronized(method):
    """Serialise request handling so the shared SQLite connection is safe."""
    def wrapper(self, *args, **kwargs):
        with self.server.lock:
            return method(self, *args, **kwargs)
    return wrapper


class PoshansathiHandler(BaseHTTPRequestHandler):
    conn = None  # set on the server instance

    def log_message(self, fmt, *args):  # quieter console
        pass

    # -- helpers -----------------------------------------------------------
    def _selected_user(self, params: dict):
        users = tracker.list_users(self.conn)
        raw = params.get("user", [None])[0]
        if raw and raw.isdigit():
            user = tracker.get_user(self.conn, int(raw))
            if user:
                return user, users
        return (users[0] if users else None), users

    def _send(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    # -- GET ---------------------------------------------------------------
    @synchronized
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        user, users = self._selected_user(params)

        if user is None:
            welcome = (
                "<div class='card'><h2>Welcome to Poshansathi</h2>"
                "<p>Create your first profile to get started.</p>"
                "<p><a class='plain' href='/profile?new=1'>"
                "Create a profile &rarr;</a></p></div>"
            )
            self._send(page("Welcome", welcome, None, users))
            return

        path = parsed.path
        if path == "/":
            day = params.get("date", [date.today().isoformat()])[0]
            body = render_dashboard(self.conn, user, day)
        elif path == "/profile":
            body = render_profile(self.conn, user, show_new="new" in params)
        elif path == "/foods":
            term = params.get("q", [""])[0]
            category = params.get("category", [""])[0]
            body = render_foods(self.conn, user, term, category)
        elif path == "/week":
            body = render_week(self.conn, user)
        else:
            body = page("Not found", "<div class='card'><h2>404</h2></div>",
                        user.id, users)
        self._send(body)

    # -- POST --------------------------------------------------------------
    @synchronized
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        data = {k: v[0] for k, v in parse_qs(raw).items()}
        path = urlparse(self.path).path
        user_id = int(data.get("user", 0) or 0)

        if path == "/log":
            tracker.log_meal(
                self.conn, user_id,
                data.get("date", date.today().isoformat()),
                data.get("meal", "snack"),
                int(data["food"]),
                float(data.get("quantity", 1) or 1),
            )
            self._redirect(f"/?user={user_id}")
        elif path == "/delete":
            tracker.delete_entry(self.conn, int(data["entry"]))
            self._redirect(f"/?user={user_id}&date={data.get('date', '')}")
        elif path == "/user":
            new_id = tracker.create_user(
                self.conn,
                data.get("name", "User"),
                int(data.get("age", 25) or 25),
                data.get("gender", "other"),
                float(data.get("height_cm", 165) or 165),
                float(data.get("weight_kg", 60) or 60),
                data.get("activity_level", "moderate"),
                data.get("goal", "maintain"),
            )
            self._redirect(f"/profile?user={new_id}")
        else:
            self._redirect("/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Poshansathi web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    conn = database.init_db(check_same_thread=False)
    PoshansathiHandler.conn = conn
    server = ThreadingHTTPServer((args.host, args.port), PoshansathiHandler)
    server.lock = threading.Lock()
    print(f"Poshansathi is running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()